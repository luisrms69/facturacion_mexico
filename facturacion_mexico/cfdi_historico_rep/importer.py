# Copyright (c) 2026, Buzola and contributors
"""Importador de REP históricos → Payment Entry + Complemento Pago MX.

Módulo SEPARADO. NO modifica `complementos_pago`, `cfdi_recibidos` ni `cfdi_emitidos`.
Reutiliza el modelo existente `Complemento Pago MX` como representación fiscal e idempotencia.

Decisiones vigentes:
- **Idempotencia** = `Complemento Pago MX.folio_fiscal` == UUID real del REP (campo unique).
- **REP vigente:** crea Payment Entry NATIVO y lo hace `submit()` (reconstruye GL + outstanding;
  la reclasificación fiscal PPD existente se deja operar normalmente) + Complemento Pago MX
  (folio_fiscal=UUID, datos del REP, documentos relacionados, impuestos, XML original),
  submit del Complemento SIN llamar al PAC.
- **REP cancelado:** se preserva fiscalmente (Complemento con estatus Cancelado + XML), SIN crear
  Payment Entry (no aplica pago). El estado cancelado viene de una **señal explícita del lote**
  (`cancelled_marker` en el nombre), NO se infiere del XML.
- `fm_creation_source` se deja **vacío** (no "Timbrado directo") para que la UI NO ofrezca
  cancelación PAC de un REP que no timbramos (ver complemento_state can_cancel). No se agrega
  opción nueva ni se toca fixture.
- **Fail-closed:** si un REP no reconcilia inequívocamente con sus facturas, se reporta excepción
  y NO se inventa nada (ni PE, ni relación de sustitución).

Ejecución:
  bench --site <site> execute facturacion_mexico.cfdi_historico_rep.importer.run \
    --kwargs "{'source_dir': '<ruta>', 'manifest': '<manifest.json>', 'dry_run': 1}"
"""

import csv
import json
import os

import frappe
from frappe import _
from frappe.utils import flt, getdate
from frappe.utils.file_manager import save_file

from facturacion_mexico.cfdi_historico_rep.rep_parser import parse_rep

_STATES = (
	"total_xml",
	"CREADA_VIGENTE",
	"REGISTRADO_CANCELADO",
	"EXISTING",
	"SKIP_NO_APLICABLE",
	"ERROR_PARSE",
	"ERROR_COMPANY_RFC",
	"ERROR_CUSTOMER",
	"ERROR_SI_NOT_FOUND",
	"ERROR_RECONCILIACION",
	"ERROR_CATALOGO",
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
		# Cuenta de depósito para el Payment Entry (paid_to). Si no se da, default de la Company.
		self.paid_to_account = (
			cfg.get("paid_to_account")
			or frappe.db.get_value("Company", self.company, "default_cash_account")
			or frappe.db.get_value("Company", self.company, "default_bank_account")
		)
		self.company_currency = frappe.db.get_value("Company", self.company, "default_currency") or "MXN"


# ------------------------------------------------------------------- resolución
def existing_complemento(uuid: str):
	"""Complemento Pago MX con ese folio_fiscal (o None). Idempotencia por UUID del REP."""
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


def resolve_si_by_uuid(uuid: str):
	"""Localiza la Sales Invoice por UUID (fm_folio_fiscal, o vía FFM.fm_uuid). (dict|None, error)."""
	if not uuid:
		return None, "missing"
	rows = frappe.get_all(
		"Sales Invoice",
		filters={"fm_folio_fiscal": uuid},
		fields=["name", "outstanding_amount", "currency", "customer"],
	)
	if not rows:
		ffm = frappe.get_all("Factura Fiscal Mexico", filters={"fm_uuid": uuid}, fields=["name"])
		if len(ffm) == 1:
			rows = frappe.get_all(
				"Sales Invoice",
				filters={"fm_factura_fiscal_mx": ffm[0].name},
				fields=["name", "outstanding_amount", "currency", "customer"],
			)
	if len(rows) == 1:
		return rows[0], None
	return None, ("ambiguous" if len(rows) > 1 else "missing")


def _catalogo_ok(forma_pago: str, moneda: str) -> str:
	"""Verifica catálogos SAT requeridos por el Complemento. '' si ok, o el faltante."""
	if forma_pago and not frappe.db.exists("Forma Pago SAT", forma_pago):
		return f"Forma Pago SAT '{forma_pago}'"
	if moneda and not frappe.db.exists("Moneda SAT", moneda):
		return f"Moneda SAT '{moneda}'"
	return ""


def _scan_xml(source_dir: str) -> list:
	paths = []
	for root, _dirs, files in os.walk(source_dir):
		for fn in files:
			if fn.lower().endswith(".xml"):
				paths.append(os.path.join(root, fn))
	return sorted(paths)


# -------------------------------------------------------- construcción (apply)
def _crear_payment_entry(cfg: RunConfig, parsed: dict, pago: dict, si_map: list):
	"""Crea y SUBMIT un Payment Entry nativo (Receive) aplicando el pago contra las SI.

	si_map: lista de (si_name, imp_pagado). La reclasificación fiscal PPD existente opera normal.
	"""
	customer, _e = resolve_customer_by_rfc(parsed["receptor_rfc"])
	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Receive"
	pe.company = cfg.company
	pe.posting_date = getdate(pago["fecha_pago"])
	pe.party_type = "Customer"
	pe.party = customer
	pe.paid_to = cfg.paid_to_account
	pe.paid_amount = flt(pago["monto"])
	pe.received_amount = flt(pago["monto"])
	if (pago["moneda_p"] or "MXN") != cfg.company_currency:
		pe.source_exchange_rate = flt(pago["tipo_cambio_p"]) or 1.0
	pe.reference_no = pago.get("num_operacion") or parsed["uuid"][:20]
	pe.reference_date = getdate(pago["fecha_pago"])
	for si_name, imp_pagado in si_map:
		pe.append(
			"references",
			{
				"reference_doctype": "Sales Invoice",
				"reference_name": si_name,
				"allocated_amount": flt(imp_pagado),
			},
		)
	pe.flags.ignore_permissions = True
	pe.insert()
	pe.submit()  # nativo: GL + outstanding + reclasificación PPD existente
	return pe.name


def _crear_complemento(
	cfg: RunConfig, parsed: dict, pago: dict, pe_name, estatus: str, si_por_uuid: dict, raw: bytes
):
	"""Crea y SUBMIT un Complemento Pago MX como representación fiscal. NO llama al PAC."""
	customer, _e = resolve_customer_by_rfc(parsed["receptor_rfc"])
	comp = frappe.new_doc("Complemento Pago MX")
	comp.company = cfg.company
	comp.customer = customer
	comp.payment_entry = pe_name  # None para cancelado
	comp.fecha_pago = pago["fecha_pago"]
	comp.forma_pago_p = pago["forma_pago"]
	comp.moneda_p = pago["moneda_p"] or "MXN"
	comp.monto_p = flt(pago["monto"])
	comp.tipo_cambio_p = flt(pago["tipo_cambio_p"]) or 1.0
	comp.uuid_sat = parsed["uuid"]
	comp.folio_fiscal = parsed["uuid"]  # ancla de idempotencia (unique)
	comp.id_documento = parsed["uuid"]
	comp.fecha_timbrado = parsed.get("fecha_timbrado") or None
	comp.no_certificado_sat = parsed.get("no_certificado_sat") or None
	comp.version = "2.0"
	comp.version_cfdi = "4.0"
	comp.status = "Timbrado" if estatus == "Vigente" else "Cancelado"
	comp.estatus_sat = estatus  # "Vigente" | "Cancelado"
	comp.fm_creation_source = ""  # vacío: NO "Timbrado directo" (evita ofrecer cancelación PAC)
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
				"moneda_dr": d.get("moneda_dr") or "MXN",
				"equivalencia_dr": flt(d.get("equivalencia_dr")) or 1.0,
				"num_parcialidad": int(d["num_parcialidad"]) if d.get("num_parcialidad") else 1,
				"imp_saldo_ant": flt(d.get("imp_saldo_ant")),
				"imp_pagado": flt(d.get("imp_pagado")),
				"imp_saldo_insoluto": flt(d.get("imp_saldo_insoluto")),
				"objeto_imp_dr": d.get("objeto_imp_dr") or "01",
				"tipo_documento": "Sales Invoice",
				"referencia_documento": si_por_uuid.get(d["id_documento"]),
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
	# Adjuntar XML original del REP al Complemento (evidencia fiscal).
	save_file(
		fname=f"REP-{parsed['uuid']}.xml",
		content=raw,
		dt="Complemento Pago MX",
		dn=comp.name,
		is_private=True,
	)
	comp.submit()  # before_submit valida folio único + timbrado info; NO llama al PAC
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
	entry.update({"uuid": uuid, "emisor_rfc": parsed["emisor_rfc"], "receptor_rfc": parsed["receptor_rfc"]})

	# Idempotencia por folio_fiscal del Complemento
	ex = existing_complemento(uuid)
	if ex:
		return {
			**entry,
			"estado": "EXISTING",
			"complemento": ex.name,
			"docstatus": ex.docstatus,
			"detalle": f"REP ya importado: {ex.name} (docstatus={ex.docstatus}, {ex.status})",
		}

	# El REP debe ser emitido por la Company (emisor == company)
	if not (cfg.company_rfc and parsed["emisor_rfc"].upper() == cfg.company_rfc):
		return {
			**entry,
			"estado": "ERROR_COMPANY_RFC",
			"detalle": f"emisor {parsed['emisor_rfc']} ≠ empresa {cfg.company_rfc or '—'}",
		}

	# V1: un solo nodo Pago por REP
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
			entry["cfdi_relacionados"] = parsed["cfdi_relacionados"]  # informativo, no se infiere
		if dry_run:
			return {
				**entry,
				"estado": "REGISTRADO_CANCELADO",
				"detalle": "registraría Complemento Cancelado (sin PE)",
			}
		sp = "rephist_c_" + (uuid[:8] or str(index))
		frappe.db.savepoint(sp)
		try:
			# vincular SI si se localizan (informativo); no es fail-closed para cancelado
			si_por_uuid = {}
			for d in pago["docs"]:
				si, _err = resolve_si_by_uuid(d["id_documento"])
				if si:
					si_por_uuid[d["id_documento"]] = si.name
			comp = _crear_complemento(cfg, parsed, pago, None, "Cancelado", si_por_uuid, raw)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit - durabilidad por REP en lote
			return {**entry, "estado": "REGISTRADO_CANCELADO", "complemento": comp}
		except Exception as exc:
			frappe.db.rollback(save_point=sp)
			return {**entry, "estado": "ERROR_OTHER", "detalle": f"{type(exc).__name__}: {exc}"[:300]}

	# ── REP VIGENTE: reconciliar y crear PE + Complemento ──
	_cust, cerr = resolve_customer_by_rfc(parsed["receptor_rfc"])
	if cerr:
		return {
			**entry,
			"estado": "ERROR_CUSTOMER",
			"detalle": f"Customer RFC {parsed['receptor_rfc']}: {cerr}",
		}

	falta_cat = _catalogo_ok(pago["forma_pago"], pago["moneda_p"] or "MXN")
	if falta_cat:
		return {**entry, "estado": "ERROR_CATALOGO", "detalle": f"catálogo faltante: {falta_cat}"}

	# Reconciliar cada DoctoRelacionado con su SI (fail-closed)
	si_map = []
	si_por_uuid = {}
	for d in pago["docs"]:
		si, err = resolve_si_by_uuid(d["id_documento"])
		if err:
			return {
				**entry,
				"estado": "ERROR_SI_NOT_FOUND",
				"detalle": f"SI por UUID {d['id_documento']}: {err}",
			}
		imp = flt(d["imp_pagado"])
		# ImpPagado no puede exceder el outstanding real (dentro de tolerancia)
		if imp - flt(si.outstanding_amount) > cfg.tolerance:
			return {
				**entry,
				"estado": "ERROR_RECONCILIACION",
				"detalle": f"ImpPagado {imp} > outstanding {si.outstanding_amount} de {si.name}",
			}
		si_map.append((si.name, imp))
		si_por_uuid[d["id_documento"]] = si.name

	# suma de docs == monto del pago
	if abs(sum(i for _n, i in si_map) - flt(pago["monto"])) > max(0.01, cfg.tolerance):
		return {
			**entry,
			"estado": "ERROR_RECONCILIACION",
			"detalle": f"suma ImpPagado ({sum(i for _n, i in si_map)}) ≠ Monto ({pago['monto']})",
		}

	if dry_run:
		return {
			**entry,
			"estado": "CREADA_VIGENTE",
			"detalle": f"crearía PE (Receive, {pago['monto']}) + Complemento; refs={len(si_map)} SI",
		}

	sp = "rephist_v_" + (uuid[:8] or str(index))
	frappe.db.savepoint(sp)
	try:
		pe_name = _crear_payment_entry(cfg, parsed, pago, si_map)
		comp = _crear_complemento(cfg, parsed, pago, pe_name, "Vigente", si_por_uuid, raw)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit - durabilidad por REP en lote
		return {**entry, "estado": "CREADA_VIGENTE", "payment_entry": pe_name, "complemento": comp}
	except frappe.ValidationError as exc:
		frappe.db.rollback(save_point=sp)
		return {**entry, "estado": "ERROR_RECONCILIACION", "detalle": str(exc)[:300]}
	except Exception as exc:
		frappe.db.rollback(save_point=sp)
		return {**entry, "estado": "ERROR_OTHER", "detalle": f"{type(exc).__name__}: {exc}"[:300]}


# ----------------------------------------------------------------- orquestación
def run(source_dir=None, manifest=None, dry_run=1, report_dir="/tmp", limit=None):
	"""Importa REP históricos de un directorio. dry_run=1 (preflight read-only) por defecto."""
	if not source_dir or not os.path.isdir(source_dir):
		frappe.throw(_("source_dir inválido: {0}").format(source_dir))
	cfg = RunConfig(manifest)
	if not cfg.paid_to_account:
		frappe.throw(
			_("No se pudo resolver la cuenta de depósito (paid_to). Especifique manifest.paid_to_account.")
		)
	dry_run = bool(int(dry_run))

	paths = _scan_xml(source_dir)
	if limit:
		paths = paths[: int(limit)]

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
			print(f"  {k:22}: {rep['resumen'][k]}")
	print(f"  {'reporte JSON':22}: {rep['meta'].get('report_json')}")
	exc = [e for e in rep["detalle"] if e["estado"].startswith("ERROR")]
	if exc:
		print("  --- excepciones ---")
		for e in exc[:40]:
			print(f"    [{e['estado']}] {e.get('uuid') or e['archivo']}: {e.get('detalle') or ''}")
