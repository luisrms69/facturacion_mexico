# Copyright (c) 2026, Buzola and contributors
"""Importador de REP históricos → Payment Entry + Complemento Pago MX.

Módulo SEPARADO. NO modifica `cfdi_recibidos` ni `cfdi_emitidos`. Reutiliza el modelo
existente `Complemento Pago MX` como representación fiscal e idempotencia.

Direcciones:
- **EMITIDO** (emisor == Company): Customer = receptor · Payment Entry **Receive** · Sales Invoice.
- **RECIBIDO** (receptor == Company): Supplier = emisor · Payment Entry **Pay** · Purchase Invoice.

Reglas clave:
- **Idempotencia** = `Complemento Pago MX.folio_fiscal` == UUID real del REP (unique).
- **Reconciliación fuerte** por DoctoRelacionado: factura única por UUID · contraparte coincide ·
  `MonedaDR == moneda factura` · `ImpSaldoAnt == outstanding previo` · `ImpSaldoInsoluto ==
  ImpSaldoAnt - ImpPagado` · `ImpPagado ≤ ImpSaldoAnt`. Cuadre del pago con **Decimal**:
  `Monto ≈ Σ(ImpPagado / EquivalenciaDR)` (EquivalenciaDR = unidades de MonedaDR por 1 de MonedaP).
- **Orden cronológico** por `FechaPago` (así, aplicar la parcialidad N exige que 1..N-1 ya estén
  aplicadas → `ImpSaldoAnt == outstanding`). No se exige que todas las parcialidades estén en el
  mismo lote: basta que el outstanding real coincida con `ImpSaldoAnt`.
- **Monedas:** soporta `MonedaP == MonedaDR` (MXN/MXN, USD/USD) y también `MonedaP != MonedaDR`
  (conversión cruzada) usando tasas DERIVADAS de datos reales — `MonedaP->MXN = EquivalenciaDR x
  conversion_rate` de la factura (no se inventan tasas). Requiere tasa MonedaP->MXN uniforme entre
  documentos y cuenta bancaria en MonedaP; si no, `ERROR_MULTIMONEDA_CRUZADA`/`ERROR_CUENTA`. Si
  ERPNext no puede representar el pago, el savepoint revierte → fail-closed (nunca asiento incorrecto).
- **Cuentas fail-closed:** Receive exige `paid_to` explícito del manifest; Pay exige `paid_from`.
  NO se autoselecciona caja/banco; FormaDePagoP no determina cuenta; Mode of Payment no se usa
  para inferir cuenta.
- **REP cancelado** (señal explícita del lote): Complemento histórico Cancelado, SIN Payment Entry.
- **Múltiples nodos `Pago`** → `ERROR_MULTIPLE_PAGOS` (el modelo representa 1 Pago / 1 payment_entry).
- **Sin PAC.** `fm_creation_source` vacío (evita ofrecer cancelación PAC de un REP no timbrado aquí).

Ejecución:
  bench --site <site> execute facturacion_mexico.cfdi_historico_rep.importer.run \
    --kwargs "{'source_dir': '<ruta>', 'manifest': '<manifest.json>', 'dry_run': 1}"
"""

import csv
import json
import os
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.utils import flt, getdate
from frappe.utils.file_manager import save_file

from facturacion_mexico.cfdi_historico_rep.rep_parser import parse_rep

_DIR_EMITIDO = "EMITIDO"
_DIR_RECIBIDO = "RECIBIDO"

_STATES = (
	"total_xml",
	"CREADA_VIGENTE",
	"REGISTRADO_CANCELADO",
	"EXISTING",
	"SKIP_NO_APLICABLE",
	"ERROR_PARSE",
	"ERROR_COMPANY_RFC",
	"ERROR_AMBIGUO",
	"ERROR_CONTRAPARTE",
	"ERROR_DOC_NOT_FOUND",
	"ERROR_MONEDA",
	"ERROR_MULTIMONEDA_CRUZADA",
	"ERROR_SALDO_ANT",
	"ERROR_SALDO_INSOLUTO",
	"ERROR_IMPPAGADO",
	"ERROR_MONTO",
	"ERROR_CATALOGO",
	"ERROR_CUENTA",
	"ERROR_MULTIPLE_PAGOS",
	"ERROR_OTHER",
)


class RunConfig:
	def __init__(self, manifest):
		cfg = manifest
		if isinstance(manifest, str):
			with open(manifest, encoding="utf-8") as fh:  # nosemgrep: frappe-security-file-traversal
				cfg = json.load(fh)
		cfg = cfg or {}
		self.company = cfg.get("company")
		if not self.company:
			frappe.throw(_("manifest.company es requerido"))
		self.company_rfc = (frappe.db.get_value("Company", self.company, "tax_id") or "").upper()
		self.cancelled_marker = (cfg.get("cancelled_marker") or "cancel").lower()
		self.tolerance = flt(cfg.get("tolerance") or 0.05)
		# Cuentas EXPLÍCITAS (sin autoselección): Receive→paid_to, Pay→paid_from.
		self.paid_to_account = cfg.get("paid_to_account") or None
		self.paid_from_account = cfg.get("paid_from_account") or None
		self.company_currency = frappe.db.get_value("Company", self.company, "default_currency") or "MXN"


# ------------------------------------------------------------------- utilidades
def _to_moneda_p(imp_pagado, equivalencia) -> Decimal:
	"""Convierte ImpPagado (MonedaDR) → MonedaP: ImpPagado / EquivalenciaDR, redondeo 2 dec."""
	imp = Decimal(str(imp_pagado or 0))
	eq = Decimal(str(equivalencia or 1))
	if eq == 0:
		eq = Decimal("1")
	return (imp / eq).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _scan_xml(source_dir: str) -> list:
	paths = []
	for root, _dirs, files in os.walk(source_dir):
		for fn in files:
			if fn.lower().endswith(".xml"):
				paths.append(os.path.join(root, fn))
	return sorted(paths)


# ------------------------------------------------------------------- resolución
def existing_complemento(uuid: str):
	if not uuid:
		return None
	return frappe.db.get_value(
		"Complemento Pago MX", {"folio_fiscal": uuid}, ["name", "docstatus", "status"], as_dict=True
	)


def resolve_customer_by_rfc(rfc: str):
	rows = frappe.get_all("Customer", filters={"tax_id": rfc}, fields=["name"])
	if len(rows) == 1:
		return rows[0].name, None
	return None, ("ambiguous" if len(rows) > 1 else "missing")


def resolve_supplier_by_rfc(rfc: str):
	rows = frappe.get_all("Supplier", filters={"tax_id": rfc}, fields=["name"])
	if len(rows) == 1:
		return rows[0].name, None
	return None, ("ambiguous" if len(rows) > 1 else "missing")


def resolve_si_by_uuid(uuid: str):
	"""Sales Invoice por UUID (fm_folio_fiscal o vía FFM.fm_uuid). (dict|None, error)."""
	if not uuid:
		return None, "missing"
	flds = ["name", "outstanding_amount", "currency", "conversion_rate", "customer"]
	rows = frappe.get_all("Sales Invoice", filters={"fm_folio_fiscal": uuid}, fields=flds)
	if not rows:
		ffm = frappe.get_all("Factura Fiscal Mexico", filters={"fm_uuid": uuid}, fields=["name"])
		if len(ffm) == 1:
			rows = frappe.get_all("Sales Invoice", filters={"fm_factura_fiscal_mx": ffm[0].name}, fields=flds)
	if len(rows) == 1:
		return rows[0], None
	return None, ("ambiguous" if len(rows) > 1 else "missing")


def resolve_pi_by_uuid(uuid: str):
	"""Purchase Invoice por UUID (fm_cfdi_uuid, unique). (dict|None, error)."""
	if not uuid:
		return None, "missing"
	flds = ["name", "outstanding_amount", "currency", "conversion_rate", "supplier"]
	rows = frappe.get_all("Purchase Invoice", filters={"fm_cfdi_uuid": uuid}, fields=flds)
	if len(rows) == 1:
		return rows[0], None
	return None, ("ambiguous" if len(rows) > 1 else "missing")


def resolve_account_currency(account: str):
	"""Moneda de la cuenta (o None si no se puede determinar)."""
	if not account:
		return None
	return frappe.db.get_value("Account", account, "account_currency") or None


def _catalogo_ok(forma_pago: str, moneda: str) -> str:
	if forma_pago and not frappe.db.exists("Forma Pago SAT", forma_pago):
		return f"Forma Pago SAT '{forma_pago}'"
	if moneda and not frappe.db.exists("Moneda SAT", moneda):
		return f"Moneda SAT '{moneda}'"
	return ""


# ------------------------------------------------------------- reconciliación
def _reconciliar(pago: dict, direction: str, counterparty: str, tol: float):
	"""Valida cada DoctoRelacionado y el cuadre del pago.

	Retorna (ref_map, doc_links, exch_rate, estado_error, detalle).
	ref_map = [(inv_name, imp_pagado, currency)]; doc_links = {uuid: inv_name};
	exch_rate = tipo de cambio uniforme MonedaP→company (o 1.0). En error: (None, None, None, estado, detalle).
	"""
	moneda_p = (pago.get("moneda_p") or "MXN").strip()
	ref_map, doc_links = [], {}
	total_mp = Decimal("0")
	rates = set()
	for d in pago["docs"]:
		uuid = d["id_documento"]
		if direction == _DIR_EMITIDO:
			inv, err = resolve_si_by_uuid(uuid)
			party_field, dt = "customer", "Sales Invoice"
		else:
			inv, err = resolve_pi_by_uuid(uuid)
			party_field, dt = "supplier", "Purchase Invoice"
		if err:
			return None, None, None, "ERROR_DOC_NOT_FOUND", f"{dt} por UUID {uuid}: {err}"
		if (inv.get(party_field) or "") != counterparty:
			return (
				None,
				None,
				None,
				"ERROR_CONTRAPARTE",
				(f"{dt} {inv.name}: {party_field}={inv.get(party_field)} ≠ {counterparty}"),
			)
		inv_cur = (inv.currency or "MXN").strip()
		moneda_dr = (d.get("moneda_dr") or inv_cur).strip()
		if moneda_dr != inv_cur:
			return (
				None,
				None,
				None,
				"ERROR_MONEDA",
				f"MonedaDR {moneda_dr} ≠ moneda factura {inv_cur} ({inv.name})",
			)
		try:
			eq = Decimal(str(d.get("equivalencia_dr") or "1"))
		except InvalidOperation:
			return None, None, None, "ERROR_MONEDA", f"EquivalenciaDR inválida en {inv.name}"
		if eq <= 0:
			eq = Decimal("1")
		# Regla SAT: si MonedaDR == MonedaP, EquivalenciaDR debe ser 1.
		if moneda_p == moneda_dr and abs(eq - Decimal("1")) > Decimal("0.000001"):
			return (
				None,
				None,
				None,
				"ERROR_MONEDA",
				f"EquivalenciaDR {eq} != 1 con MonedaP==MonedaDR ({inv.name})",
			)
		# Tasa MonedaP->MXN derivada de datos REALES (no inventada):
		#   EquivalenciaDR (MonedaDR por MonedaP) x conversion_rate (MonedaDR->MXN) = MonedaP->MXN.
		derived_pay_rate = round(float(eq) * (flt(inv.conversion_rate) or 1.0), 6)

		saldo_ant = flt(d.get("imp_saldo_ant"))
		imp = flt(d.get("imp_pagado"))
		insol = flt(d.get("imp_saldo_insoluto"))
		out = flt(inv.outstanding_amount)
		if abs(saldo_ant - out) > tol:
			return (
				None,
				None,
				None,
				"ERROR_SALDO_ANT",
				(f"ImpSaldoAnt {saldo_ant} ≠ outstanding {out} de {inv.name} (¿falta parcialidad previa?)"),
			)
		if abs(insol - (saldo_ant - imp)) > tol:
			return (
				None,
				None,
				None,
				"ERROR_SALDO_INSOLUTO",
				(
					f"ImpSaldoInsoluto {insol} ≠ SaldoAnt-ImpPagado ({round(saldo_ant - imp, 2)}) en {inv.name}"
				),
			)
		if imp - saldo_ant > tol:
			return (
				None,
				None,
				None,
				"ERROR_IMPPAGADO",
				f"ImpPagado {imp} > ImpSaldoAnt {saldo_ant} en {inv.name}",
			)

		ref_map.append((inv.name, imp, inv_cur))
		doc_links[uuid] = inv.name
		total_mp += _to_moneda_p(imp, eq)
		rates.add(derived_pay_rate)  # MonedaP->MXN uniforme por pago

	# Cuadre del pago: Monto ≈ Σ(ImpPagado/EquivalenciaDR) (Decimal), tolerancia ∝ nº docs.
	monto = Decimal(str(pago.get("monto") or 0))
	if abs(total_mp - monto) > Decimal("0.01") * len(pago["docs"]):
		return None, None, None, "ERROR_MONTO", f"Σ(ImpPagado/EquivDR)={total_mp} ≠ Monto={monto}"

	# Tipo de cambio MonedaP->MXN uniforme (necesario para un exchange_rate único del PE).
	if len(rates) > 1:
		return (
			None,
			None,
			None,
			"ERROR_MULTIMONEDA_CRUZADA",
			(
				f"Tasas MonedaP->MXN distintas entre documentos {sorted(rates)} — no se puede fijar un exchange_rate único"
			),
		)
	exch_rate = rates.pop() if rates else 1.0
	return ref_map, doc_links, exch_rate, None, None


# -------------------------------------------------------- construcción (apply)
def _crear_payment_entry(cfg, parsed, pago, ref_map, exch_rate, direction, account):
	"""Crea y SUBMIT un Payment Entry nativo. Receive (emitido) / Pay (recibido)."""
	moneda_p = (pago.get("moneda_p") or "MXN").strip()
	pe = frappe.new_doc("Payment Entry")
	pe.company = cfg.company
	pe.posting_date = getdate(pago["fecha_pago"])
	pe.reference_no = pago.get("num_operacion") or parsed["uuid"][:20]
	pe.reference_date = getdate(pago["fecha_pago"])
	inv_dt = "Sales Invoice" if direction == _DIR_EMITIDO else "Purchase Invoice"

	if direction == _DIR_EMITIDO:
		pe.payment_type = "Receive"
		pe.party_type = "Customer"
		pe.party = resolve_customer_by_rfc(parsed["receptor_rfc"])[0]
		pe.paid_to = account  # cuenta de depósito (banco/efectivo) explícita
		if moneda_p != cfg.company_currency:
			pe.target_exchange_rate = flt(exch_rate) or 1.0
	else:
		pe.payment_type = "Pay"
		pe.party_type = "Supplier"
		pe.party = resolve_supplier_by_rfc(parsed["emisor_rfc"])[0]
		pe.paid_from = account  # cuenta origen (banco/efectivo) explícita
		if moneda_p != cfg.company_currency:
			pe.source_exchange_rate = flt(exch_rate) or 1.0

	# Montos: en MonedaP y su equivalente en moneda de la empresa (base = Monto x exch_rate).
	# Para misma moneda que la empresa, base == Monto. ERPNext valida el resto (dif/exchange g/l).
	monto = flt(pago["monto"])
	base = round(monto * (flt(exch_rate) or 1.0), 2)
	same_cur = moneda_p == cfg.company_currency
	if direction == _DIR_EMITIDO:  # Receive: recibe en MonedaP; acredita CxC en moneda empresa
		pe.received_amount = monto
		pe.paid_amount = monto if same_cur else base
	else:  # Pay: paga en MonedaP; debita CxP en moneda empresa
		pe.paid_amount = monto
		pe.received_amount = monto if same_cur else base
	for inv_name, imp, _cur in ref_map:
		pe.append(
			"references",
			{"reference_doctype": inv_dt, "reference_name": inv_name, "allocated_amount": flt(imp)},
		)
	pe.flags.ignore_permissions = True
	pe.insert()
	pe.submit()  # nativo: GL + Payment Ledger + outstanding (+ reclasificación PPD si hay mapeo)
	return pe.name


def _crear_complemento(cfg, parsed, pago, pe_name, estatus, direction, doc_links, raw):
	"""Crea y SUBMIT un Complemento Pago MX (representación fiscal). NO llama al PAC."""
	tipo_doc = "Sales Invoice" if direction == _DIR_EMITIDO else "Purchase Invoice"
	comp = frappe.new_doc("Complemento Pago MX")
	comp.company = cfg.company
	# customer solo aplica al emitido; en recibido el proveedor queda vía documentos_relacionados→PI.
	if direction == _DIR_EMITIDO:
		comp.customer = resolve_customer_by_rfc(parsed["receptor_rfc"])[0]
	comp.payment_entry = pe_name  # None para cancelado
	comp.fecha_pago = pago["fecha_pago"]
	comp.forma_pago_p = pago["forma_pago"]
	comp.moneda_p = pago.get("moneda_p") or "MXN"
	comp.monto_p = flt(pago["monto"])
	comp.tipo_cambio_p = flt(pago.get("tipo_cambio_p")) or 1.0
	comp.uuid_sat = parsed["uuid"]
	comp.folio_fiscal = parsed["uuid"]  # ancla de idempotencia (unique)
	comp.id_documento = parsed["uuid"]
	comp.fecha_timbrado = parsed.get("fecha_timbrado") or None
	comp.no_certificado_sat = parsed.get("no_certificado_sat") or None
	comp.version = "2.0"
	comp.version_cfdi = "4.0"
	comp.status = "Timbrado" if estatus == "Vigente" else "Cancelado"
	comp.estatus_sat = estatus
	comp.fm_creation_source = ""  # vacío: NO "Timbrado directo" (evita cancelación PAC de la UI)
	comp.num_operacion = pago.get("num_operacion") or None
	comp.rfc_emisor_cta_ord = pago.get("rfc_emisor_cta_ord") or None
	comp.nom_banco_ord_ext = pago.get("nom_banco_ord_ext") or None
	comp.cta_ordenante = pago.get("cta_ordenante") or None
	comp.rfc_emisor_cta_ben = pago.get("rfc_emisor_cta_ben") or None
	comp.cta_beneficiario = pago.get("cta_beneficiario") or None

	for d in pago["docs"]:
		comp.append(
			"documentos_relacionados",
			{
				"id_documento": d["id_documento"],
				"serie": d.get("serie"),
				"folio": d.get("folio"),
				"moneda_dr": d.get("moneda_dr") or (pago.get("moneda_p") or "MXN"),
				"equivalencia_dr": flt(d.get("equivalencia_dr")) or 1.0,
				"num_parcialidad": int(d["num_parcialidad"]) if d.get("num_parcialidad") else 1,
				"imp_saldo_ant": flt(d.get("imp_saldo_ant")),
				"imp_pagado": flt(d.get("imp_pagado")),
				"imp_saldo_insoluto": flt(d.get("imp_saldo_insoluto")),
				"objeto_imp_dr": d.get("objeto_imp_dr") or "01",
				"tipo_documento": tipo_doc,
				"referencia_documento": doc_links.get(d["id_documento"]),
			},
		)
	for imp in pago.get("impuestos_p", []):
		comp.append(
			"detalles_impuestos",
			{
				"tipo_impuesto": imp["tipo_impuesto"],
				"impuesto": imp.get("impuesto"),
				"tipo_factor": imp.get("tipo_factor"),
				"tasa_cuota": flt(imp.get("tasa_cuota")),
				"base_dr": flt(imp.get("base")),
				"importe_dr": flt(imp.get("importe")),
			},
		)

	comp.flags.ignore_permissions = True
	comp.insert()
	save_file(
		fname=f"REP-{parsed['uuid']}.xml",
		content=raw,
		dt="Complemento Pago MX",
		dn=comp.name,
		is_private=True,
	)
	comp.submit()  # before_submit: folio único + timbrado info; NO PAC
	return comp.name


# ----------------------------------------------------------------- proceso XML
def _process_file(path: str, cfg: RunConfig, dry_run: bool, index: int) -> dict:
	fn = os.path.basename(path)
	entry = {"archivo": fn}
	try:
		with open(path, "rb") as fh:  # nosemgrep: frappe-security-file-traversal
			raw = fh.read()
	except OSError as exc:
		return {**entry, "estado": "ERROR_OTHER", "detalle": f"lectura: {exc}"}

	try:
		parsed = parse_rep(raw)
	except ValueError as exc:
		if "no es tipo P" in str(exc):
			return {**entry, "estado": "SKIP_NO_APLICABLE", "detalle": str(exc)}
		return {**entry, "estado": "ERROR_PARSE", "detalle": str(exc)[:200]}
	except Exception as exc:
		return {**entry, "estado": "ERROR_PARSE", "detalle": str(exc)[:200]}

	uuid = parsed["uuid"]
	emisor = (parsed["emisor_rfc"] or "").upper()
	receptor = (parsed["receptor_rfc"] or "").upper()
	entry.update({"uuid": uuid, "emisor_rfc": parsed["emisor_rfc"], "receptor_rfc": parsed["receptor_rfc"]})

	# Idempotencia por folio_fiscal
	ex = existing_complemento(uuid)
	if ex:
		return {
			**entry,
			"estado": "EXISTING",
			"complemento": ex.name,
			"docstatus": ex.docstatus,
			"detalle": f"REP ya importado: {ex.name} (docstatus={ex.docstatus}, {ex.status})",
		}

	# Dirección por RFC de la Company
	co = cfg.company_rfc
	if co and emisor == co and receptor == co:
		return {**entry, "estado": "ERROR_AMBIGUO", "detalle": "emisor y receptor == Company"}
	if co and emisor == co:
		direction = _DIR_EMITIDO
	elif co and receptor == co:
		direction = _DIR_RECIBIDO
	else:
		return {
			**entry,
			"estado": "ERROR_COMPANY_RFC",
			"detalle": f"emisor {emisor} / receptor {receptor} ≠ Company {co or '—'}",
		}
	entry["direccion"] = direction

	# Un solo nodo Pago
	if len(parsed["pagos"]) != 1:
		return {
			**entry,
			"estado": "ERROR_MULTIPLE_PAGOS",
			"detalle": f"{len(parsed['pagos'])} nodos Pago (V1 soporta 1)",
		}
	pago = parsed["pagos"][0]
	entry.update({"fecha_pago": pago["fecha_pago"], "monto": pago["monto"], "moneda": pago["moneda_p"]})

	cancelado = cfg.cancelled_marker in fn.lower()  # señal EXPLÍCITA del lote

	# ── REP CANCELADO: preservar fiscalmente, SIN Payment Entry ──
	if cancelado:
		if parsed.get("cfdi_relacionados"):
			entry["cfdi_relacionados"] = parsed["cfdi_relacionados"]
		if dry_run:
			return {
				**entry,
				"estado": "REGISTRADO_CANCELADO",
				"detalle": "registraría Complemento Cancelado (sin PE)",
			}
		sp = "rephist_c_" + (uuid[:8] or str(index))
		frappe.db.savepoint(sp)
		try:
			# vínculo best-effort a la factura (informativo); no fail-closed para cancelado
			doc_links = {}
			for d in pago["docs"]:
				inv, _err = (
					resolve_si_by_uuid(d["id_documento"])
					if direction == _DIR_EMITIDO
					else resolve_pi_by_uuid(d["id_documento"])
				)
				if inv:
					doc_links[d["id_documento"]] = inv.name
			comp = _crear_complemento(cfg, parsed, pago, None, "Cancelado", direction, doc_links, raw)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit - durabilidad por REP en lote
			return {**entry, "estado": "REGISTRADO_CANCELADO", "complemento": comp}
		except Exception as exc:
			frappe.db.rollback(save_point=sp)
			return {**entry, "estado": "ERROR_OTHER", "detalle": f"{type(exc).__name__}: {exc}"[:300]}

	# ── REP VIGENTE ──
	# Contraparte
	if direction == _DIR_EMITIDO:
		cp, cperr = resolve_customer_by_rfc(receptor)
		cp_label = "Customer"
	else:
		cp, cperr = resolve_supplier_by_rfc(emisor)
		cp_label = "Supplier"
	if cperr:
		return {
			**entry,
			"estado": "ERROR_CONTRAPARTE",
			"detalle": f"{cp_label} RFC {receptor if direction == _DIR_EMITIDO else emisor}: {cperr}",
		}

	# Cuenta explícita (fail-closed, sin autoselección)
	account = cfg.paid_to_account if direction == _DIR_EMITIDO else cfg.paid_from_account
	if not account:
		rol_cta = "paid_to (Receive)" if direction == _DIR_EMITIDO else "paid_from (Pay)"
		return {
			**entry,
			"estado": "ERROR_CUENTA",
			"detalle": f"Falta cuenta explícita {rol_cta} en el manifest",
		}
	# La cuenta de banco/efectivo debe estar en MonedaP (no se convierte una cuenta de otra moneda).
	moneda_p = pago.get("moneda_p") or "MXN"
	acc_cur = resolve_account_currency(account)
	if acc_cur and acc_cur != moneda_p:
		return {
			**entry,
			"estado": "ERROR_CUENTA",
			"detalle": f"cuenta {account} ({acc_cur}) ≠ MonedaP {moneda_p}",
		}

	# Catálogos SAT del Complemento
	falta_cat = _catalogo_ok(pago["forma_pago"], pago.get("moneda_p") or "MXN")
	if falta_cat:
		return {**entry, "estado": "ERROR_CATALOGO", "detalle": f"catálogo faltante: {falta_cat}"}

	# Reconciliación fuerte
	ref_map, doc_links, exch_rate, err_estado, err_det = _reconciliar(pago, direction, cp, cfg.tolerance)
	if err_estado:
		return {**entry, "estado": err_estado, "detalle": err_det}

	if dry_run:
		tipo_pe = "Receive" if direction == _DIR_EMITIDO else "Pay"
		return {
			**entry,
			"estado": "CREADA_VIGENTE",
			"detalle": f"crearía PE {tipo_pe} ({pago['monto']}) + Complemento; refs={len(ref_map)}",
		}

	sp = "rephist_v_" + (uuid[:8] or str(index))
	frappe.db.savepoint(sp)
	try:
		pe_name = _crear_payment_entry(cfg, parsed, pago, ref_map, exch_rate, direction, account)
		comp = _crear_complemento(cfg, parsed, pago, pe_name, "Vigente", direction, doc_links, raw)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit - durabilidad por REP en lote
		return {**entry, "estado": "CREADA_VIGENTE", "payment_entry": pe_name, "complemento": comp}
	except frappe.ValidationError as exc:
		frappe.db.rollback(save_point=sp)
		return {**entry, "estado": "ERROR_OTHER", "detalle": f"PE/Complemento rechazado: {exc}"[:300]}
	except Exception as exc:
		frappe.db.rollback(save_point=sp)
		return {**entry, "estado": "ERROR_OTHER", "detalle": f"{type(exc).__name__}: {exc}"[:300]}


def _sortkey_fecha(path: str) -> str:
	"""FechaPago del REP para orden cronológico; '' si no parsea (se procesa igual y reporta error)."""
	try:
		with open(path, "rb") as fh:  # nosemgrep: frappe-security-file-traversal
			p = parse_rep(fh.read())
		return (p["pagos"][0]["fecha_pago"] if p.get("pagos") else "") or ""
	except Exception:
		return ""


# ----------------------------------------------------------------- orquestación
def run(source_dir=None, manifest=None, dry_run=1, report_dir="/tmp", limit=None):
	"""Importa REP históricos de un directorio, en orden cronológico por FechaPago."""
	if not source_dir or not os.path.isdir(source_dir):
		frappe.throw(_("source_dir inválido: {0}").format(source_dir))
	cfg = RunConfig(manifest)
	dry_run = bool(int(dry_run))

	paths = _scan_xml(source_dir)
	if limit:
		paths = paths[: int(limit)]
	paths.sort(key=_sortkey_fecha)  # orden cronológico por FechaPago

	counts = {k: 0 for k in _STATES}
	detalle = []
	for i, path in enumerate(paths):
		counts["total_xml"] += 1
		entry = _process_file(path, cfg, dry_run, i)
		counts[entry["estado"]] = counts.get(entry["estado"], 0) + 1
		detalle.append(entry)

	rep = {
		"meta": {"source_dir": source_dir, "dry_run": dry_run, "company": cfg.company},
		"resumen": counts,
		"detalle": detalle,
	}
	_write_reports(rep, report_dir, dry_run)
	_print_summary(rep)
	return rep["resumen"]


def _write_reports(rep, report_dir, dry_run):
	tag = "dryrun" if dry_run else "apply"
	stamp = frappe.utils.now().replace(":", "").replace(" ", "_").replace("-", "")[:15]
	base = os.path.join(report_dir, f"cfdi_historico_rep_{tag}_{stamp}")
	with open(base + ".json", "w", encoding="utf-8") as fh:  # nosemgrep: frappe-security-file-traversal
		json.dump(rep, fh, ensure_ascii=False, indent=2, default=str)
	cols = [
		"archivo",
		"uuid",
		"direccion",
		"emisor_rfc",
		"receptor_rfc",
		"fecha_pago",
		"monto",
		"moneda",
		"payment_entry",
		"complemento",
		"docstatus",
		"estado",
		"detalle",
	]
	with open(
		base + ".csv", "w", encoding="utf-8", newline=""
	) as fh:  # nosemgrep: frappe-security-file-traversal
		w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
		w.writeheader()
		for e in rep["detalle"]:
			w.writerow(e)
	rep["meta"]["report_json"] = base + ".json"
	rep["meta"]["report_csv"] = base + ".csv"


def _print_summary(rep):
	print(
		"\n=== REP históricos → Payment Entry — %s ===" % ("DRY-RUN" if rep["meta"]["dry_run"] else "APLICAR")
	)
	for k in _STATES:
		if rep["resumen"].get(k):
			print(f"  {k:26}: {rep['resumen'][k]}")
	print(f"  {'reporte JSON':26}: {rep['meta'].get('report_json')}")
	exc = [e for e in rep["detalle"] if e["estado"].startswith("ERROR")]
	if exc:
		print("  --- excepciones ---")
		for e in exc[:40]:
			print(f"    [{e['estado']}] {e.get('uuid') or e['archivo']}: {e.get('detalle') or ''}")
