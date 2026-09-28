"""Tests — importador de REP históricos → Payment Entry + Complemento Pago MX.

Cubre: parser REP 2.0 real; reconciliación fuerte (SaldoAnt/Insoluto/ImpPagado/Monto/moneda/
contraparte); direcciones EMITIDO (Receive) y RECIBIDO (Pay); cancelado (sin PE); idempotencia;
cuentas fail-closed; multimoneda cruzada fail-closed. Boundary mockeado. `unittest.TestCase`.
"""

import os
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

import frappe

from facturacion_mexico.cfdi_historico_rep import importer, rep_parser

CO_RFC = "AAA010101AAA"
CUS_RFC = "CUS010101AAA"
SUP_RFC = "SUP010101AAA"
UUID = "11111111-1111-4111-8111-111111111111"

_REP = (
	'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Version="4.0" '
	'TipoDeComprobante="P" Fecha="2026-06-15T12:00:00" LugarExpedicion="64000" Moneda="XXX" '
	'SubTotal="0" Total="0">'
	'<cfdi:Emisor Rfc="{erfc}" Nombre="E" RegimenFiscal="601"/>'
	'<cfdi:Receptor Rfc="{rrfc}" Nombre="R" DomicilioFiscalReceptor="06000" '
	'RegimenFiscalReceptor="612" UsoCFDI="CP01"/>'
	"<cfdi:Complemento>"
	'<tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
	'Version="1.1" UUID="{uuid}" FechaTimbrado="2026-06-15T12:00:05"/>'
	'<pago20:Pagos xmlns:pago20="http://www.sat.gob.mx/Pagos20" Version="2.0">'
	'<pago20:Pago FechaPago="2026-06-15T12:00:00" FormaDePagoP="03" MonedaP="MXN" Monto="{monto}">'
	'<pago20:DoctoRelacionado IdDocumento="{iddoc}" MonedaDR="MXN" EquivalenciaDR="1" '
	'NumParcialidad="1" ImpSaldoAnt="{monto}" ImpPagado="{monto}" ImpSaldoInsoluto="0" ObjetoImpDR="02"/>'
	"</pago20:Pago></pago20:Pagos></cfdi:Complemento></cfdi:Comprobante>"
)


def _rep_xml(erfc=CO_RFC, rrfc=CUS_RFC, uuid=UUID, iddoc="SI-UUID-1", monto="1160.00"):
	return _REP.format(erfc=erfc, rrfc=rrfc, uuid=uuid, iddoc=iddoc, monto=monto).encode("utf-8")


def _cfg():
	return types.SimpleNamespace(
		company="Test Co",
		company_rfc=CO_RFC,
		cancelled_marker="cancel",
		tolerance=0.05,
		paid_to_account="Banco - TC",
		paid_from_account="Banco - TC",
		paid_to_accounts={},
		paid_from_accounts={},
		company_currency="MXN",
	)


def _tmpfile(name="rep.xml"):
	d = tempfile.mkdtemp()
	p = os.path.join(d, name)
	with open(p, "wb") as fh:
		fh.write(b"<x/>")
	return p


def _pago(monto=1160.0, moneda_p="MXN", docs=None):
	return {
		"fecha_pago": "2026-06-15 12:00:00",
		"forma_pago": "03",
		"moneda_p": moneda_p,
		"tipo_cambio_p": "1",
		"monto": str(monto),
		"num_operacion": "OP1",
		"rfc_emisor_cta_ord": "",
		"nom_banco_ord_ext": "",
		"cta_ordenante": "",
		"rfc_emisor_cta_ben": "",
		"cta_beneficiario": "",
		"docs": docs if docs is not None else [_doc(monto)],
		"impuestos_p": [],
	}


def _doc(monto=1160.0, moneda_dr="MXN", eq="1", saldo_ant=None, insol="0", iddoc="SI-UUID-1"):
	sa = str(monto) if saldo_ant is None else str(saldo_ant)
	return {
		"id_documento": iddoc,
		"serie": "A",
		"folio": "1",
		"moneda_dr": moneda_dr,
		"equivalencia_dr": eq,
		"num_parcialidad": "1",
		"imp_saldo_ant": sa,
		"imp_pagado": str(monto),
		"imp_saldo_insoluto": insol,
		"objeto_imp_dr": "02",
	}


def _parsed(emisor=CO_RFC, receptor=CUS_RFC, pagos=None):
	return {
		"tipo": "P",
		"version": "4.0",
		"uuid": UUID,
		"emisor_rfc": emisor,
		"receptor_rfc": receptor,
		"fecha_timbrado": "",
		"no_certificado_sat": "",
		"cfdi_relacionados": None,
		"pagos": pagos if pagos is not None else [_pago()],
	}


def _inv(**o):
	base = {"name": "INV-1", "outstanding_amount": 1160.0, "currency": "MXN", "conversion_rate": 1.0}
	base.update(o)
	return frappe._dict(base)


# ── parser real ───────────────────────────────────────────────────────────────


class TestParser(unittest.TestCase):
	def test_parsea(self):
		d = rep_parser.parse_rep(_rep_xml())
		self.assertEqual(d["tipo"], "P")
		self.assertEqual(d["uuid"], UUID)
		self.assertEqual(d["pagos"][0]["docs"][0]["imp_pagado"], "1160.00")

	def test_rechaza_no_p(self):
		with self.assertRaises(ValueError):
			rep_parser.parse_rep(_rep_xml().replace(b'"P"', b'"I"'))


# ── reconciliación (resolvers mockeados) ──────────────────────────────────────


class TestReconciliar(unittest.TestCase):
	def _rec(self, pago, direction=importer._DIR_EMITIDO, cp="C-1", inv=None, is_pi=False):
		inv = inv if inv is not None else _inv(customer="C-1", supplier="S-1")
		target = "resolve_pi_by_uuid" if is_pi else "resolve_si_by_uuid"
		with patch.object(importer, target, return_value=(inv, None)):
			return importer._reconciliar(pago, direction, cp, 0.05)

	def test_ok_emitido(self):
		rm, _dl, ex, est, _det = self._rec(_pago(1160.0))
		self.assertIsNone(est)
		self.assertEqual(rm, [("INV-1", 1160.0, "MXN")])
		self.assertEqual(ex, 1.0)

	def test_doc_not_found(self):
		with patch.object(importer, "resolve_si_by_uuid", return_value=(None, "missing")):
			_rm, _dl, _ex, est, _d = importer._reconciliar(_pago(), importer._DIR_EMITIDO, "C-1", 0.05)
		self.assertEqual(est, "ERROR_DOC_NOT_FOUND")

	def test_contraparte(self):
		_rm, _dl, _ex, est, _d = self._rec(_pago(), cp="OTRO", inv=_inv(customer="C-1"))
		self.assertEqual(est, "ERROR_CONTRAPARTE")

	def test_moneda_dr_distinta_factura(self):
		_r, _l, _e, est, _d = self._rec(
			_pago(docs=[_doc(moneda_dr="USD")]), inv=_inv(customer="C-1", currency="MXN")
		)
		self.assertEqual(est, "ERROR_MONEDA")

	def test_cross_mxn_inv_usd_pay(self):
		# Factura MXN (conv 1), pago USD, EquivalenciaDR=17 (MXN por USD). ImpPagado 1700 MXN / 17 = 100 USD.
		pago = _pago(monto=100, moneda_p="USD", docs=[_doc(1700.0, "MXN", "17")])
		inv = _inv(customer="C-1", currency="MXN", conversion_rate=1.0, outstanding_amount=1700.0)
		_rm, _l, ex, est, _d = self._rec(pago, inv=inv)
		self.assertIsNone(est)
		self.assertEqual(ex, 17.0)  # MonedaP(USD)->MXN

	def test_cross_usd_inv_mxn_pay(self):
		# Factura USD (conv 20), pago MXN, EquivalenciaDR=0.05 (USD por MXN). ImpPagado 100 USD / 0.05 = 2000 MXN.
		pago = _pago(monto=2000, moneda_p="MXN", docs=[_doc(100.0, "USD", "0.05")])
		inv = _inv(customer="C-1", currency="USD", conversion_rate=20.0, outstanding_amount=100.0)
		_rm, _l, ex, est, _d = self._rec(pago, inv=inv)
		self.assertIsNone(est)
		self.assertEqual(ex, 1.0)  # MonedaP(MXN)->MXN

	def test_cross_no_uniforme(self):
		inv1 = _inv(
			name="SI-1", customer="C-1", currency="MXN", conversion_rate=1.0, outstanding_amount=1700.0
		)
		inv2 = _inv(
			name="SI-2", customer="C-1", currency="MXN", conversion_rate=1.0, outstanding_amount=1800.0
		)
		docs = [_doc(1700.0, "MXN", "17", iddoc="U1"), _doc(1800.0, "MXN", "18", iddoc="U2")]
		pago = _pago(monto=200, moneda_p="USD", docs=docs)  # derived 17 y 18 → no uniforme
		with patch.object(importer, "resolve_si_by_uuid", side_effect=[(inv1, None), (inv2, None)]):
			_r, _l, _e, est, _d = importer._reconciliar(pago, importer._DIR_EMITIDO, "C-1", 0.05)
		self.assertEqual(est, "ERROR_MULTIMONEDA_CRUZADA")

	def test_equivalencia_ne1_misma_moneda(self):
		pago = _pago(docs=[_doc(eq="1.5")])
		_r, _l, _e, est, _d = self._rec(pago, inv=_inv(customer="C-1", currency="MXN"))
		self.assertEqual(est, "ERROR_MONEDA")

	def test_saldo_ant_no_coincide(self):
		# ImpSaldoAnt=1160 pero outstanding=500 → falta parcialidad previa
		pago = _pago(1160.0)
		_r, _l, _e, est, _d = self._rec(pago, inv=_inv(customer="C-1", outstanding_amount=500.0))
		self.assertEqual(est, "ERROR_SALDO_ANT")

	def test_saldo_insoluto_incoherente(self):
		# SaldoAnt=1160, ImpPagado=1160 pero Insoluto=100 (debería 0)
		pago = _pago(docs=[_doc(1160.0, insol="100")])
		_r, _l, _e, est, _d = self._rec(pago, inv=_inv(customer="C-1", outstanding_amount=1160.0))
		self.assertEqual(est, "ERROR_SALDO_INSOLUTO")

	def test_imppagado_mayor_saldo_ant(self):
		# ImpPagado 1160 > SaldoAnt 1000
		doc = _doc(1160.0, saldo_ant=1000.0, insol="-160")
		pago = _pago(docs=[doc])
		_r, _l, _e, est, _d = self._rec(pago, inv=_inv(customer="C-1", outstanding_amount=1000.0))
		self.assertEqual(est, "ERROR_IMPPAGADO")

	def test_monto_no_cuadra(self):
		# Monto 999 ≠ ImpPagado 1160
		pago = _pago(1160.0)
		pago["monto"] = "999.00"
		_r, _l, _e, est, _d = self._rec(pago, inv=_inv(customer="C-1", outstanding_amount=1160.0))
		self.assertEqual(est, "ERROR_MONTO")

	def test_recibido_ok(self):
		inv = _inv(name="PI-1", supplier="S-1", customer=None, outstanding_amount=1160.0)
		rm, _dl, _ex, est, _d = self._rec(
			_pago(1160.0), direction=importer._DIR_RECIBIDO, cp="S-1", inv=inv, is_pi=True
		)
		self.assertIsNone(est)
		self.assertEqual(rm[0][0], "PI-1")


# ── _process_file: dirección / dispatch / apply ───────────────────────────────


def _run(
	path,
	cfg,
	dry_run,
	*,
	parsed=None,
	existing=None,
	inv=None,
	is_pi=False,
	cust=("C-1", None),
	sup=("S-1", None),
	acc_cur=None,
	pe="PE-1",
	comp="COMP-1",
):
	parsed = parsed or _parsed()
	inv = inv if inv is not None else _inv(customer="C-1", supplier="S-1")
	with (
		patch.object(importer, "parse_rep", return_value=parsed),
		patch.object(importer, "existing_complemento", return_value=existing),
		patch.object(importer, "resolve_customer_by_rfc", return_value=cust),
		patch.object(importer, "resolve_supplier_by_rfc", return_value=sup),
		patch.object(importer, "resolve_si_by_uuid", return_value=(inv, None)),
		patch.object(importer, "resolve_pi_by_uuid", return_value=(inv, None)),
		patch.object(importer, "resolve_account_currency", return_value=acc_cur),
		patch.object(importer, "_catalogo_ok", return_value=""),
		patch.object(importer, "_crear_payment_entry", return_value=pe) as m_pe,
		patch.object(importer, "_crear_complemento", return_value=comp) as m_comp,
		patch.object(importer.frappe.db, "savepoint", MagicMock()),
		patch.object(importer.frappe.db, "rollback", MagicMock()),
		patch.object(importer.frappe.db, "commit", MagicMock()),
	):
		entry = importer._process_file(path, cfg, dry_run, 0)
	return entry, m_pe, m_comp


class TestEmitido(unittest.TestCase):
	def test_apply(self):
		entry, m_pe, m_comp = _run(_tmpfile(), _cfg(), False, inv=_inv(customer="C-1"))
		self.assertEqual(entry["estado"], "CREADA_VIGENTE")
		self.assertEqual(entry["direccion"], importer._DIR_EMITIDO)
		self.assertEqual(m_pe.call_args.args[5], importer._DIR_EMITIDO)  # direction
		self.assertEqual(m_pe.call_args.args[6], "Banco - TC")  # paid_to account
		m_comp.assert_called_once()

	def test_dryrun_no_crea(self):
		entry, m_pe, _mc = _run(_tmpfile(), _cfg(), True, inv=_inv(customer="C-1"))
		self.assertEqual(entry["estado"], "CREADA_VIGENTE")
		m_pe.assert_not_called()


class TestRecibido(unittest.TestCase):
	def test_apply_pay(self):
		p = _parsed(emisor=SUP_RFC, receptor=CO_RFC)
		inv = _inv(name="PI-1", supplier="S-1", outstanding_amount=1160.0)
		entry, m_pe, _m_comp = _run(_tmpfile(), _cfg(), False, parsed=p, inv=inv, is_pi=True)
		self.assertEqual(entry["estado"], "CREADA_VIGENTE")
		self.assertEqual(entry["direccion"], importer._DIR_RECIBIDO)
		self.assertEqual(m_pe.call_args.args[5], importer._DIR_RECIBIDO)
		self.assertEqual(m_pe.call_args.args[6], "Banco - TC")  # paid_from account


class TestCancelado(unittest.TestCase):
	def test_sin_pe(self):
		entry, m_pe, m_comp = _run(_tmpfile("REP_Cancelado.xml"), _cfg(), False, inv=_inv(customer="C-1"))
		self.assertEqual(entry["estado"], "REGISTRADO_CANCELADO")
		m_pe.assert_not_called()
		# _crear_complemento(cfg, parsed, pagos_data, estatus, direction, raw)
		self.assertEqual(m_comp.call_args.args[3], "Cancelado")  # estatus
		self.assertIsNone(m_comp.call_args.args[2][0]["pe_name"])  # sin Payment Entry


class TestIdempotencia(unittest.TestCase):
	def test_existing(self):
		ex = frappe._dict(name="COMP-9", docstatus=1, status="Timbrado")
		entry, m_pe, m_comp = _run(_tmpfile(), _cfg(), False, existing=ex)
		self.assertEqual(entry["estado"], "EXISTING")
		m_pe.assert_not_called()
		m_comp.assert_not_called()


class TestFailClosed(unittest.TestCase):
	def test_company_rfc(self):
		p = _parsed(emisor="OTR010101AAA", receptor="XXX010101AAA")
		entry, m_pe, _mc = _run(_tmpfile(), _cfg(), False, parsed=p)
		self.assertEqual(entry["estado"], "ERROR_COMPANY_RFC")
		m_pe.assert_not_called()

	def test_contraparte(self):
		entry, m_pe, _mc = _run(_tmpfile(), _cfg(), False, cust=(None, "missing"))
		self.assertEqual(entry["estado"], "ERROR_CONTRAPARTE")
		m_pe.assert_not_called()

	def test_cuenta_faltante(self):
		cfg = _cfg()
		cfg.paid_to_account = None  # emitido requiere paid_to
		entry, m_pe, _mc = _run(_tmpfile(), cfg, False, inv=_inv(customer="C-1"))
		self.assertEqual(entry["estado"], "ERROR_CUENTA")
		m_pe.assert_not_called()

	def test_cuenta_moneda_distinta(self):
		# Cuenta en USD pero MonedaP=MXN → fail-closed (no se convierte una cuenta de otra moneda)
		entry, m_pe, _mc = _run(_tmpfile(), _cfg(), False, inv=_inv(customer="C-1"), acc_cur="USD")
		self.assertEqual(entry["estado"], "ERROR_CUENTA")
		m_pe.assert_not_called()

	def test_saldo_ant_reconciliacion(self):
		# outstanding real 500 ≠ ImpSaldoAnt 1160 → ERROR_SALDO_ANT (vía _reconciliar real)
		entry, m_pe, _mc = _run(_tmpfile(), _cfg(), False, inv=_inv(customer="C-1", outstanding_amount=500.0))
		self.assertEqual(entry["estado"], "ERROR_SALDO_ANT")
		m_pe.assert_not_called()


# ── multi-Pago ────────────────────────────────────────────────────────────────


def _run_multi(parsed, cfg, invs, dry_run=False, filename="rep.xml", pe_side=None):
	"""Ejecuta _process_file con resolvers por-UUID (invs: {uuid: inv}). Retorna (entry, m_pe, m_comp, m_rb)."""

	def si_side(uuid):
		inv = invs.get(uuid)
		return (inv, None) if inv else (None, "missing")

	def default_pe(cfg_, parsed_, pago_, ref_map_, exch_, direction_, account_):
		return f"PE-{pago_['docs'][0]['id_documento']}"

	m_pe = MagicMock(side_effect=pe_side or default_pe)
	m_comp = MagicMock(return_value="COMP-1")
	m_rb = MagicMock()
	with (
		patch.object(importer, "parse_rep", return_value=parsed),
		patch.object(importer, "existing_complemento", return_value=None),
		patch.object(importer, "resolve_customer_by_rfc", return_value=("C-1", None)),
		patch.object(importer, "resolve_supplier_by_rfc", return_value=("S-1", None)),
		patch.object(importer, "resolve_si_by_uuid", side_effect=si_side),
		patch.object(importer, "resolve_pi_by_uuid", side_effect=si_side),
		patch.object(importer, "resolve_account_currency", return_value=None),
		patch.object(importer, "_catalogo_ok", return_value=""),
		patch.object(importer, "_crear_payment_entry", m_pe),
		patch.object(importer, "_crear_complemento", m_comp),
		patch.object(importer.frappe.db, "savepoint", MagicMock()),
		patch.object(importer.frappe.db, "rollback", m_rb),
		patch.object(importer.frappe.db, "commit", MagicMock()),
	):
		entry = importer._process_file(_tmpfile(filename), cfg, dry_run, 0)
	return entry, m_pe, m_comp, m_rb


def _two_pagos(monto1=1000.0, monto2=2000.0, mon1="MXN", mon2="MXN", eq1="1", eq2="1"):
	pago1 = _pago(monto1, moneda_p=mon1, docs=[_doc(monto1, mon1, eq1, iddoc="U1")])
	pago1["fecha_pago"] = "2026-01-10 12:00:00"
	pago2 = _pago(monto2, moneda_p=mon2, docs=[_doc(monto2, mon2, eq2, iddoc="U2")])
	pago2["fecha_pago"] = "2026-02-10 12:00:00"
	return _parsed(pagos=[pago1, pago2])


class TestMultiPago(unittest.TestCase):
	def test_dos_pagos_dos_pe_un_complemento(self):
		parsed = _two_pagos()
		invs = {
			"U1": _inv(name="SI-1", customer="C-1", outstanding_amount=1000.0),
			"U2": _inv(name="SI-2", customer="C-1", outstanding_amount=2000.0),
		}
		entry, m_pe, m_comp, _rb = _run_multi(parsed, _cfg(), invs)
		self.assertEqual(entry["estado"], "CREADA_VIGENTE")
		self.assertEqual(m_pe.call_count, 2)  # N Payment Entry
		m_comp.assert_called_once()  # UN solo Complemento
		pagos_data = m_comp.call_args.args[2]
		self.assertEqual(sorted(pd["pago_idx"] for pd in pagos_data), [1, 2])
		self.assertTrue(all(pd["pe_name"] for pd in pagos_data))

	def test_dos_pagos_monedas_distintas_con_mapa_cuentas(self):
		# Pago1 MXN, Pago2 USD (factura USD, eq 1). Cuentas por moneda en el manifest.
		parsed = _two_pagos(monto1=1000.0, monto2=100.0, mon1="MXN", mon2="USD")
		# factura USD del pago2 con conversion_rate 20 (USD->MXN)
		invs = {
			"U1": _inv(
				name="SI-1", customer="C-1", currency="MXN", conversion_rate=1.0, outstanding_amount=1000.0
			),
			"U2": _inv(
				name="SI-2", customer="C-1", currency="USD", conversion_rate=20.0, outstanding_amount=100.0
			),
		}
		cfg = _cfg()
		cfg.paid_to_accounts = {"MXN": "Banco MXN - TC", "USD": "Banco USD - TC"}
		entry, m_pe, _m_comp, _rb = _run_multi(parsed, cfg, invs)
		self.assertEqual(entry["estado"], "CREADA_VIGENTE")
		self.assertEqual(m_pe.call_count, 2)

	def test_rollback_total_si_falla_segundo_pago(self):
		parsed = _two_pagos()
		invs = {
			"U1": _inv(name="SI-1", customer="C-1", outstanding_amount=1000.0),
			"U2": _inv(name="SI-2", customer="C-1", outstanding_amount=2000.0),
		}
		calls = {"n": 0}

		def pe_side(*a, **k):
			calls["n"] += 1
			if calls["n"] == 2:
				raise RuntimeError("PE2 falla")
			return "PE-1"

		entry, _m_pe, m_comp, m_rb = _run_multi(parsed, _cfg(), invs, pe_side=pe_side)
		self.assertEqual(entry["estado"], "ERROR_OTHER")
		m_rb.assert_called()  # rollback del REP completo
		m_comp.assert_not_called()  # no se crea el Complemento si falla un Pago

	def test_cancelado_multi_pago_sin_pe(self):
		parsed = _two_pagos()
		invs = {"U1": _inv(name="SI-1"), "U2": _inv(name="SI-2")}
		entry, m_pe, m_comp, _rb = _run_multi(parsed, _cfg(), invs, filename="REP_Cancelado.xml")
		self.assertEqual(entry["estado"], "REGISTRADO_CANCELADO")
		m_pe.assert_not_called()
		pagos_data = m_comp.call_args.args[2]
		self.assertEqual(len(pagos_data), 2)
		self.assertTrue(all(pd["pe_name"] is None for pd in pagos_data))


if __name__ == "__main__":
	unittest.main()
