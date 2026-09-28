# Copyright (c) 2026, Buzola and contributors
"""Importador masivo histórico: CFDI XML de compra -> Purchase Invoice (Draft).

Módulo SEPARADO que **reutiliza sin modificar** el pipeline de `cfdi_recibidos`:
`CFDIRecibidoParser`, `ingest_xml()` y `build_purchase_invoice()`. NO duplica su lógica
ni toca ese paquete.

Reglas de esta carga histórica:
- **dry_run** = preflight 100% READ-ONLY: parsea y reporta qué ocurriría; NO llama
  `ingest_xml()`, NO escribe BD ni archivos.
- **apply** reutiliza el pipeline real (crea `CFDI Recibido` — donde vive el UUID único y el
  XML adjunto — y la **Purchase Invoice en Draft**). NO Submit, NO Payment Entry, NO PAC.
- **Fail-closed de proveedor:** antes de llamar `ingest_xml()` se verifica que exista Supplier
  por RFC. Si falta, NO se llama al pipeline (para no disparar su auto-creación), se reporta
  `ERROR_SUPPLIER_MISSING` y el proveedor se acumula en un CSV para carga por Data Import.
  **Este importador NUNCA crea Suppliers.**
- **Idempotencia por UUID:** si el UUID ya tiene Purchase Invoice (incluso cancelada), NO se
  recrea nada: se reporta `EXISTING_PI` con nombre y `docstatus`.
- **Fail-closed de Item/cuenta/impuesto:** los lanza `build_purchase_invoice()` como
  ValidationError; el archivo se revierte (savepoint) y se reporta el estado correspondiente.

Ejecución (contexto Frappe, nunca python directo):

  # DRY-RUN (no escribe nada):
  bench --site <site> execute \
    facturacion_mexico.cfdi_historico_compras.importer.run \
    --kwargs "{'source_dir': '<ruta_xml>', 'manifest': '<ruta_manifest.json>', 'dry_run': 1}"

  # APLICAR (crea CFDI Recibido + Purchase Invoice Draft de las READY):
  bench --site <site> execute \
    facturacion_mexico.cfdi_historico_compras.importer.run \
    --kwargs "{'source_dir': '<ruta_xml>', 'manifest': '<ruta_manifest.json>', 'dry_run': 0}"

Manifest (JSON) — campos:
  company  (str, requerido) Company destino (su RFC debe coincidir con el Receptor del CFDI).
"""

import csv
import json
import os

import frappe
from frappe import _

# Reutilización del pipeline existente (NO se modifica cfdi_recibidos).
from facturacion_mexico.cfdi_recibidos.parsers.cfdi_recibido_parser import CFDIRecibidoParser
from facturacion_mexico.cfdi_recibidos.services.purchase_invoice_builder import build_purchase_invoice
from facturacion_mexico.cfdi_recibidos.services.xml_ingestion import ingest_xml

_TIPO_COMPRA = "I"  # solo CFDI de Ingreso aplica al flujo de compras recibidas


# ----------------------------------------------------------------- configuración
class RunConfig:
	"""Configuración de una corrida, cargada desde un manifest (dict o ruta JSON)."""

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


# ------------------------------------------------------------------- utilidades
def _scan_xml(source_dir: str) -> list:
	"""Lista determinista de rutas .xml bajo source_dir (recursivo)."""
	paths = []
	for root, _dirs, files in os.walk(source_dir):
		for fn in files:
			if fn.lower().endswith(".xml"):
				paths.append(os.path.join(root, fn))
	return sorted(paths)


def resolve_supplier_by_rfc(rfc: str):
	"""Resuelve Supplier por tax_id. Retorna (name, motivo_error).

	motivo_error ∈ {None, "sin_rfc", "missing", "ambiguous"}.
	NUNCA crea Supplier (fail-closed)."""
	if not rfc:
		return None, "sin_rfc"
	rows = frappe.get_all("Supplier", filters={"tax_id": rfc}, fields=["name"])
	if len(rows) == 1:
		return rows[0].name, None
	if len(rows) == 0:
		return None, "missing"
	return None, "ambiguous"


def existing_pi_for_uuid(uuid: str):
	"""Purchase Invoice existente por UUID (o None). Incluye docstatus (0/1/2)."""
	if not uuid:
		return None
	return frappe.db.get_value(
		"Purchase Invoice", {"fm_cfdi_uuid": uuid}, ["name", "docstatus"], as_dict=True
	)


def _map_build_error(msg: str) -> str:
	"""Clasifica un ValidationError de build_purchase_invoice en un estado de reporte."""
	m = (msg or "").lower()
	if "item_code" in m or "clasifi" in m:
		return "ERROR_ITEM"
	if "cuenta" in m or "account" in m:
		return "ERROR_ACCOUNT"
	if "impuesto" in m or "regla" in m:
		return "ERROR_TAX"
	if "grand_total" in m or "tolerancia" in m:
		return "ERROR_TOTAL"
	return "ERROR_OTHER"


_COUNT_KEYS = (
	"total_xml",
	"READY",
	"CREADA",
	"EXISTING_PI",
	"SKIP_NO_APLICABLE",
	"ERROR_PARSE",
	"ERROR_RECEPTOR_RFC",
	"ERROR_SUPPLIER_MISSING",
	"ERROR_SUPPLIER_AMB",
	"ERROR_ITEM",
	"ERROR_ACCOUNT",
	"ERROR_TAX",
	"ERROR_TOTAL",
	"ERROR_OTHER",
)


# --------------------------------------------------------------- proceso por XML
def _process_file(path: str, cfg: RunConfig, dry_run: bool, index: int) -> dict:
	"""Procesa un XML y retorna el `entry` del reporte.

	En dry_run es 100% READ-ONLY (no llama ingest_xml/build ni escribe).
	En apply reutiliza el pipeline con savepoint por archivo.
	Cuando falta el proveedor, agrega en el entry los datos para el CSV de faltantes.
	"""
	fn = os.path.basename(path)
	entry = {"archivo": fn}

	try:
		with open(path, "rb") as fh:  # nosemgrep: frappe-security-file-traversal
			raw = fh.read()
	except OSError as exc:
		return {**entry, "estado": "ERROR_OTHER", "detalle": f"lectura: {exc}"}

	# Parseo (en memoria) usando el parser real del pipeline.
	try:
		data = CFDIRecibidoParser(raw).parse()
	except Exception as exc:
		return {**entry, "estado": "ERROR_PARSE", "detalle": str(exc)[:300]}

	uuid = data.get("uuid", "") or ""
	supplier_rfc = data.get("supplier_rfc", "") or ""
	entry.update(
		{
			"uuid": uuid,
			"serie": data.get("serie", ""),
			"folio": data.get("folio", ""),
			"supplier_rfc": supplier_rfc,
			"tipo": data.get("cfdi_type", ""),
			"total_xml": data.get("total", ""),
		}
	)

	# --- Pre-checks READ-ONLY (compartidos por dry_run y apply) ---

	# 1) tipo aplicable
	if data.get("cfdi_type", "") != _TIPO_COMPRA:
		return {**entry, "estado": "SKIP_NO_APLICABLE", "detalle": f"tipo={data.get('cfdi_type')!r}"}

	# 2) receptor == empresa
	receiver_rfc = (data.get("receiver_rfc", "") or "").upper()
	if not (cfg.company_rfc and receiver_rfc == cfg.company_rfc):
		return {
			**entry,
			"estado": "ERROR_RECEPTOR_RFC",
			"detalle": f"receptor {receiver_rfc or '—'} ≠ empresa {cfg.company_rfc or '—'}",
		}

	# 3) idempotencia: UUID con PI existente (incluso cancelada) -> reportar, no recrear
	pi = existing_pi_for_uuid(uuid)
	if pi:
		return {
			**entry,
			"estado": "EXISTING_PI",
			"purchase_invoice": pi.name,
			"docstatus_pi": pi.docstatus,
			"detalle": f"PI existente {pi.name} (docstatus={pi.docstatus}) — no se recrea",
		}

	# 4) fail-closed de proveedor (NUNCA se crea aquí)
	supplier, motivo = resolve_supplier_by_rfc(supplier_rfc)
	if motivo == "ambiguous":
		return {**entry, "estado": "ERROR_SUPPLIER_AMB", "detalle": f"varios Supplier con RFC {supplier_rfc}"}
	if motivo in ("missing", "sin_rfc"):
		return {
			**entry,
			"estado": "ERROR_SUPPLIER_MISSING",
			"detalle": f"no existe Supplier con RFC {supplier_rfc or '—'}",
			# payload para el CSV de proveedores faltantes:
			"_missing_supplier": {
				"supplier_rfc": supplier_rfc,
				"supplier_name": data.get("supplier_name", "") or "",
				"supplier_tax_regime": data.get("supplier_tax_regime", "") or "",
				"archivo": fn,
				"uuid": uuid,
			},
		}
	entry["supplier"] = supplier

	# --- dry_run: reporta proyección sin escribir nada ---
	if dry_run:
		cfdi_existente = frappe.db.get_value("CFDI Recibido", {"uuid": uuid}, "name")
		nota = (
			"crearía CFDI Recibido + PI Draft"
			if not cfdi_existente
			else (f"CFDI Recibido {cfdi_existente} ya existe; construiría la PI Draft")
		)
		return {**entry, "estado": "READY", "detalle": nota}

	# --- apply: reutiliza el pipeline real, savepoint por archivo ---
	sp = "cfdihist_" + (uuid[:8] if uuid else str(index))
	frappe.db.savepoint(sp)
	try:
		ing = ingest_xml(raw, cfg.company, fn)  # supplier ya existe -> no auto-crea
		cfdi_name = ing.get("cfdi_recibido")
		if not cfdi_name:
			raise RuntimeError(f"ingest sin doc [{ing.get('status')}]: {ing.get('message')}")

		result = build_purchase_invoice(cfdi_name)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit - durabilidad por factura en carga por lote

		if result.get("recovered"):
			rec = frappe.db.get_value(
				"Purchase Invoice", result["purchase_invoice"], ["docstatus"], as_dict=True
			)
			return {
				**entry,
				"estado": "EXISTING_PI",
				"purchase_invoice": result["purchase_invoice"],
				"docstatus_pi": rec.docstatus if rec else None,
				"cfdi_recibido": cfdi_name,
				"detalle": "PI ya existía para el UUID — no se recreó",
			}
		return {
			**entry,
			"estado": "CREADA",
			"purchase_invoice": result["purchase_invoice"],
			"docstatus_pi": 0,
			"cfdi_recibido": cfdi_name,
		}
	except frappe.ValidationError as exc:
		frappe.db.rollback(save_point=sp)
		return {**entry, "estado": _map_build_error(str(exc)), "detalle": str(exc)[:300]}
	except Exception as exc:
		frappe.db.rollback(save_point=sp)
		return {**entry, "estado": "ERROR_OTHER", "detalle": f"{type(exc).__name__}: {exc}"[:300]}


# ----------------------------------------------------------------- orquestación
def run(source_dir=None, manifest=None, dry_run=1, report_dir="/tmp", limit=None):
	"""Corre la importación histórica de CFDI de compra sobre un directorio de XML."""
	if not source_dir or not os.path.isdir(source_dir):
		frappe.throw(_("source_dir inválido: {0}").format(source_dir))
	cfg = RunConfig(manifest)
	dry_run = bool(int(dry_run))

	paths = _scan_xml(source_dir)
	if limit:
		paths = paths[: int(limit)]

	counts = {k: 0 for k in _COUNT_KEYS}
	detalle = []
	missing_suppliers = {}  # rfc -> payload (dedup por RFC)

	for i, path in enumerate(paths):
		counts["total_xml"] += 1
		entry = _process_file(path, cfg, dry_run, i)
		ms = entry.pop("_missing_supplier", None)
		if ms and ms.get("supplier_rfc"):
			missing_suppliers.setdefault(ms["supplier_rfc"], ms)
		counts[entry["estado"]] = counts.get(entry["estado"], 0) + 1
		detalle.append(entry)

	rep = {
		"meta": {"source_dir": source_dir, "dry_run": dry_run, "company": cfg.company},
		"resumen": counts,
		"detalle": detalle,
	}
	_write_reports(rep, list(missing_suppliers.values()), report_dir, dry_run)
	_print_summary(rep, missing_suppliers)
	return rep["resumen"]


def _write_reports(rep, missing_suppliers, report_dir, dry_run):
	"""Escribe reporte JSON + CSV de la corrida y el CSV de proveedores faltantes."""
	tag = "dryrun" if dry_run else "apply"
	stamp = frappe.utils.now().replace(":", "").replace(" ", "_").replace("-", "")[:15]
	base = os.path.join(report_dir, f"cfdi_historico_compras_{tag}_{stamp}")

	with open(base + ".json", "w", encoding="utf-8") as fh:  # nosemgrep: frappe-security-file-traversal
		json.dump(rep, fh, ensure_ascii=False, indent=2, default=str)

	cols = [
		"archivo",
		"uuid",
		"serie",
		"folio",
		"supplier_rfc",
		"supplier",
		"tipo",
		"total_xml",
		"purchase_invoice",
		"docstatus_pi",
		"cfdi_recibido",
		"estado",
		"detalle",
	]
	with open(  # nosemgrep: frappe-security-file-traversal
		base + ".csv", "w", encoding="utf-8", newline=""
	) as fh:
		w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
		w.writeheader()
		for e in rep["detalle"]:
			w.writerow(e)

	rep["meta"]["report_json"] = base + ".json"
	rep["meta"]["report_csv"] = base + ".csv"

	# CSV de proveedores faltantes (para Data Import). Solo si hay.
	if missing_suppliers:
		sup_path = base + "_proveedores_faltantes.csv"
		sup_cols = ["supplier_rfc", "supplier_name", "supplier_tax_regime", "archivo", "uuid"]
		with open(  # nosemgrep: frappe-security-file-traversal
			sup_path, "w", encoding="utf-8", newline=""
		) as fh:
			w = csv.DictWriter(fh, fieldnames=sup_cols, extrasaction="ignore")
			w.writeheader()
			for s in missing_suppliers:
				w.writerow(s)
		rep["meta"]["report_proveedores_faltantes"] = sup_path


def _print_summary(rep, missing_suppliers):
	"""Imprime resumen de contadores y excepciones de la corrida."""
	c = rep["resumen"]
	print(
		"\n=== CFDI histórico de compra → Purchase Invoice — %s ==="
		% ("DRY-RUN" if rep["meta"]["dry_run"] else "APLICAR")
	)
	for k in _COUNT_KEYS:
		if c.get(k):
			print(f"  {k:22}: {c[k]}")
	print(f"  {'reporte JSON':22}: {rep['meta'].get('report_json')}")
	print(f"  {'reporte CSV':22}: {rep['meta'].get('report_csv')}")
	if missing_suppliers:
		print(
			f"  {'proveedores faltantes':22}: {len(missing_suppliers)} -> {rep['meta'].get('report_proveedores_faltantes')}"
		)
	exc = [
		e
		for e in rep["detalle"]
		if e["estado"] not in ("READY", "CREADA", "EXISTING_PI", "SKIP_NO_APLICABLE")
	]
	if exc:
		print("  --- excepciones ---")
		for e in exc[:40]:
			print(f"    [{e['estado']}] {e.get('uuid') or e['archivo']}: {e.get('detalle') or ''}")
