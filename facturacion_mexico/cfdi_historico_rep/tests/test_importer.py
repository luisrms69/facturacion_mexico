"""Tests — importador de REP históricos → Payment Entry + Complemento Pago MX.

Cubre: parser REP 2.0 real; REP vigente (crea PE + Complemento); REP cancelado (Complemento
sin PE); idempotencia por folio_fiscal; fail-closed de SI inexistente y de reconciliación.

Parser real (`secure_xml`); creación de docs y lookups mockeados. `unittest.TestCase`.
"""

import os
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

import frappe

from facturacion_mexico.cfdi_historico_rep import importer, rep_parser

CO_RFC = "AAA010101AAA"
UUID = "11111111-1111-4111-8111-111111111111"

# REP mínimo válido (CFDI 4.0 tipo P + Pagos 2.0)
_REP = (
	'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Version="4.0" '
	'TipoDeComprobante="P" Fecha="2026-06-15T12:00:00" LugarExpedicion="64000" '
	'Moneda="XXX" SubTotal="0" Total="0">'
	'<cfdi:Emisor Rfc="{erfc}" Nombre="Empresa SA" RegimenFiscal="601"/>'
	'<cfdi:Receptor Rfc="{rrfc}" Nombre="Cliente Uno" DomicilioFiscalReceptor="06000" '
	'RegimenFiscalReceptor="612" UsoCFDI="CP01"/>'
	"{rel}"
	"<cfdi:Complemento>"
	'<tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
	'Version="1.1" UUID="{uuid}" FechaTimbrado="2026-06-15T12:00:05" NoCertificadoSAT="00001000000000000001"/>'
	'<pago20:Pagos xmlns:pago20="http://www.sat.gob.mx/Pagos20" Version="2.0">'
	'<pago20:Totales MontoTotalPagos="{monto}"/>'
	'<pago20:Pago FechaPago="2026-06-15T12:00:00" FormaDePagoP="03" MonedaP="MXN" '
	'Monto="{monto}" NumOperacion="OP123">'
	'<pago20:DoctoRelacionado IdDocumento="{iddoc}" Serie="A" Folio="1" MonedaDR="MXN" '
	'EquivalenciaDR="1" NumParcialidad="1" ImpSaldoAnt="{monto}" ImpPagado="{monto}" '
	'ImpSaldoInsoluto="0" ObjetoImpDR="02"/>'
	"</pago20:Pago>"
	"</pago20:Pagos>"
	"</cfdi:Complemento>"
	"</cfdi:Comprobante>"
)


def _rep_xml(erfc=CO_RFC, rrfc="CUS010101AAA", uuid=UUID, iddoc="SI-UUID-1", monto="1160.00", rel=""):
	return _REP.format(erfc=erfc, rrfc=rrfc, uuid=uuid, iddoc=iddoc, monto=monto, rel=rel).encode("utf-8")


def _cfg():
	return types.SimpleNamespace(
		company="Test Co",
		company_rfc=CO_RFC,
		cancelled_marker="cancel",
		tolerance=0.05,
		paid_to_account="Cash - TC",
		company_currency="MXN",
	)


def _tmpfile(name="rep.xml"):
	d = tempfile.mkdtemp()
	p = os.path.join(d, name)
	with open(p, "wb") as fh:
		fh.write(b"<x/>")
	return p


# ── parser real ───────────────────────────────────────────────────────────────


class TestParser(unittest.TestCase):
	def test_parsea_rep(self):
		d = rep_parser.parse_rep(_rep_xml())
		self.assertEqual(d["tipo"], "P")
		self.assertEqual(d["uuid"], UUID)
		self.assertEqual(d["emisor_rfc"], CO_RFC)
		self.assertEqual(len(d["pagos"]), 1)
		self.assertEqual(d["pagos"][0]["forma_pago"], "03")
		self.assertEqual(d["pagos"][0]["docs"][0]["id_documento"], "SI-UUID-1")
		self.assertEqual(d["pagos"][0]["docs"][0]["imp_pagado"], "1160.00")

	def test_rechaza_no_pago(self):
		xml = _rep_xml().replace(b'TipoDeComprobante="P"', b'TipoDeComprobante="I"')
		with self.assertRaises(ValueError):
			rep_parser.parse_rep(xml)

	def test_cfdi_relacionados_solo_si_presente(self):
		rel = (
			'<cfdi:CfdiRelacionados TipoRelacion="04">'
			'<cfdi:CfdiRelacionado UUID="OLD-UUID-9"/></cfdi:CfdiRelacionados>'
		)
		d = rep_parser.parse_rep(_rep_xml(rel=rel))
		self.assertEqual(d["cfdi_relacionados"]["tipo_relacion"], "04")
		self.assertEqual(d["cfdi_relacionados"]["uuids"], ["OLD-UUID-9"])
		# sin el nodo → None
		self.assertIsNone(rep_parser.parse_rep(_rep_xml())["cfdi_relacionados"])


# ── orquestación ────────────────────────────────────────────────────────────


def _parsed(monto=1160.0, docs=None, pagos_n=1):
	pago = {
		"fecha_pago": "2026-06-15 12:00:00",
		"forma_pago": "03",
		"moneda_p": "MXN",
		"tipo_cambio_p": "1",
		"monto": str(monto),
		"num_operacion": "OP1",
		"rfc_emisor_cta_ord": "",
		"nom_banco_ord_ext": "",
		"cta_ordenante": "",
		"rfc_emisor_cta_ben": "",
		"cta_beneficiario": "",
		"docs": docs
		if docs is not None
		else [
			{
				"id_documento": "SI-UUID-1",
				"serie": "A",
				"folio": "1",
				"moneda_dr": "MXN",
				"equivalencia_dr": "1",
				"num_parcialidad": "1",
				"imp_saldo_ant": str(monto),
				"imp_pagado": str(monto),
				"imp_saldo_insoluto": "0",
				"objeto_imp_dr": "02",
			}
		],
		"impuestos_p": [],
	}
	return {
		"tipo": "P",
		"version": "4.0",
		"uuid": UUID,
		"emisor_rfc": CO_RFC,
		"receptor_rfc": "CUS010101AAA",
		"fecha_timbrado": "",
		"no_certificado_sat": "",
		"cfdi_relacionados": None,
		"pagos": [pago] * pagos_n,
	}


def _run_process(
	path,
	cfg,
	dry_run,
	*,
	parsed=None,
	existing=None,
	customer=("C-1", None),
	si=None,
	catalogo="",
	pe="PE-1",
	comp="COMP-1",
):
	parsed = parsed or _parsed()
	if si is None:
		si = (frappe._dict(name="SI-1", outstanding_amount=1160.0, currency="MXN", customer="C-1"), None)
	with (
		patch.object(importer, "parse_rep", return_value=parsed),
		patch.object(importer, "existing_complemento", return_value=existing),
		patch.object(importer, "resolve_customer_by_rfc", return_value=customer),
		patch.object(importer, "resolve_si_by_uuid", return_value=si),
		patch.object(importer, "_catalogo_ok", return_value=catalogo),
		patch.object(importer, "_crear_payment_entry", return_value=pe) as m_pe,
		patch.object(importer, "_crear_complemento", return_value=comp) as m_comp,
		patch.object(importer.frappe.db, "savepoint", MagicMock()),
		patch.object(importer.frappe.db, "rollback", MagicMock()),
		patch.object(importer.frappe.db, "commit", MagicMock()),
	):
		entry = importer._process_file(path, cfg, dry_run, 0)
	return entry, m_pe, m_comp


class TestVigente(unittest.TestCase):
	def test_apply_crea_pe_y_complemento(self):
		entry, m_pe, m_comp = _run_process(_tmpfile(), _cfg(), dry_run=False)
		self.assertEqual(entry["estado"], "CREADA_VIGENTE")
		self.assertEqual(entry["payment_entry"], "PE-1")
		self.assertEqual(entry["complemento"], "COMP-1")
		m_pe.assert_called_once()
		m_comp.assert_called_once()
		# el complemento se crea con estatus Vigente y pe_name
		self.assertEqual(m_comp.call_args.args[4], "Vigente")

	def test_dryrun_no_crea(self):
		entry, m_pe, m_comp = _run_process(_tmpfile(), _cfg(), dry_run=True)
		self.assertEqual(entry["estado"], "CREADA_VIGENTE")
		m_pe.assert_not_called()
		m_comp.assert_not_called()


class TestCancelado(unittest.TestCase):
	def test_registra_complemento_sin_pe(self):
		# nombre con marcador explícito 'cancel'
		entry, m_pe, m_comp = _run_process(_tmpfile("REP_Cancelado.xml"), _cfg(), dry_run=False)
		self.assertEqual(entry["estado"], "REGISTRADO_CANCELADO")
		m_pe.assert_not_called()  # NO aplica pago
		m_comp.assert_called_once()
		self.assertEqual(m_comp.call_args.args[3], None)  # pe_name None
		self.assertEqual(m_comp.call_args.args[4], "Cancelado")  # estatus

	def test_dryrun_cancelado(self):
		entry, m_pe, _mc = _run_process(_tmpfile("x_cancel.xml"), _cfg(), dry_run=True)
		self.assertEqual(entry["estado"], "REGISTRADO_CANCELADO")
		m_pe.assert_not_called()


class TestIdempotencia(unittest.TestCase):
	def test_existing_no_recrea(self):
		ex = frappe._dict(name="COMP-9", docstatus=1, status="Timbrado")
		entry, m_pe, m_comp = _run_process(_tmpfile(), _cfg(), dry_run=False, existing=ex)
		self.assertEqual(entry["estado"], "EXISTING")
		self.assertEqual(entry["complemento"], "COMP-9")
		m_pe.assert_not_called()
		m_comp.assert_not_called()


class TestFailClosed(unittest.TestCase):
	def test_si_inexistente(self):
		entry, m_pe, m_comp = _run_process(_tmpfile(), _cfg(), dry_run=False, si=(None, "missing"))
		self.assertEqual(entry["estado"], "ERROR_SI_NOT_FOUND")
		m_pe.assert_not_called()
		m_comp.assert_not_called()

	def test_reconciliacion_imppagado_mayor_outstanding(self):
		si = (frappe._dict(name="SI-1", outstanding_amount=100.0, currency="MXN", customer="C-1"), None)
		entry, m_pe, _mc = _run_process(_tmpfile(), _cfg(), dry_run=False, si=si)  # imp_pagado 1160 > 100
		self.assertEqual(entry["estado"], "ERROR_RECONCILIACION")
		m_pe.assert_not_called()

	def test_company_mismatch(self):
		p = _parsed()
		p["emisor_rfc"] = "OTR010101AAA"
		entry, m_pe, _mc = _run_process(_tmpfile(), _cfg(), dry_run=False, parsed=p)
		self.assertEqual(entry["estado"], "ERROR_COMPANY_RFC")
		m_pe.assert_not_called()

	def test_customer_inexistente(self):
		entry, m_pe, _mc = _run_process(_tmpfile(), _cfg(), dry_run=False, customer=(None, "missing"))
		self.assertEqual(entry["estado"], "ERROR_CUSTOMER")
		m_pe.assert_not_called()

	def test_multiple_pagos(self):
		entry, m_pe, _mc = _run_process(_tmpfile(), _cfg(), dry_run=False, parsed=_parsed(pagos_n=2))
		self.assertEqual(entry["estado"], "ERROR_MULTIPLE_PAGOS")
		m_pe.assert_not_called()

	def test_catalogo_faltante(self):
		entry, m_pe, _mc = _run_process(_tmpfile(), _cfg(), dry_run=False, catalogo="Moneda SAT 'MXN'")
		self.assertEqual(entry["estado"], "ERROR_CATALOGO")
		m_pe.assert_not_called()


if __name__ == "__main__":
	unittest.main()
