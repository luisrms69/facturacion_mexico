# Copyright (c) 2026, Buzola and contributors
"""Preparación de Customers/Suppliers desde lotes de XML CFDI (V1 — SOLO LECTURA).

Funcionalidad satélite SEPARADA. NO toca `cfdi_recibidos` ni `cfdi_emitidos`. NO crea
Customer ni Supplier: solo lee, consolida terceros únicos y genera CSV listos para
**Data Import** (a los que después se les agregan defaults explícitos: Customer Group,
Territory, Supplier Group, etc. — que este módulo NO inventa).

Flujo por XML:
  parse local (secure_xml) → identifica la Company por su RFC (Emisor o Receptor) →
  determina el rol de la contraparte (Emisor de la empresa ⇒ contraparte = Receptor = Customer;
  Receptor de la empresa ⇒ contraparte = Emisor = Supplier) → extrae SOLO datos confiables del XML →
  consolida por RFC (para extranjero genérico XEXX NO se asume identidad solo por RFC: se usa
  NumRegIdTrib / nombre / residencia) → detecta si ya existe en ERPNext.

Estados: EXISTENTE · A_CREAR_CUSTOMER · A_CREAR_SUPPLIER · DATOS_INSUFICIENTES ·
         ERROR_PARSE · ERROR_COMPANY_RFC · ERROR_AMBIGUO

Sin PAC/SAT/red. V1 NO escribe BD de ninguna forma (el flag dry_run se acepta por simetría
pero no habilita ninguna escritura).

Ejecución:
  bench --site <site> execute \
    facturacion_mexico.preparacion_terceros.preparador.run \
    --kwargs "{'source_dir': '<ruta_xml>', 'report_dir': '<ruta_salida>'}"
"""

import csv
import json
import os
import re
import unicodedata

import frappe
from frappe import _

from facturacion_mexico.utils.secure_xml import secure_parse_xml

# Namespace CFDI 4.0 (se tolera el declarado en el propio XML).
_NS_CFDI = "http://www.sat.gob.mx/cfd/4"
# RFC genéricos SAT (estables; no es lógica fiscal, son identificadores del catálogo).
_RFC_EXTRANJERO = "XEXX010101000"

_STATES = (
	"EXISTENTE",
	"A_CREAR_CUSTOMER",
	"A_CREAR_SUPPLIER",
	"DATOS_INSUFICIENTES",
	"ERROR_PARSE",
	"ERROR_COMPANY_RFC",
	"ERROR_AMBIGUO",
)


# ------------------------------------------------------------------- parse local
def parse_partes_cfdi(raw: bytes) -> dict:
	"""Extrae atributos fiscales de Comprobante/Emisor/Receptor. Parse seguro (XXE-safe).

	No interpreta impuestos ni conceptos: solo identidad de las partes."""
	root = secure_parse_xml(raw, "lxml")
	tag = root.tag if isinstance(root.tag, str) else ""
	ns = tag[tag.find("{") + 1 : tag.find("}")] if tag.startswith("{") else _NS_CFDI

	def q(name):
		return f"{{{ns}}}{name}"

	emisor = root.find(q("Emisor"))
	receptor = root.find(q("Receptor"))
	if emisor is None or receptor is None:
		raise ValueError("CFDI sin nodo Emisor/Receptor")

	return {
		"version": root.get("Version", ""),
		"tipo": root.get("TipoDeComprobante", ""),
		"lugar_expedicion": root.get("LugarExpedicion", ""),
		"emisor_rfc": (emisor.get("Rfc", "") or "").strip(),
		"emisor_nombre": (emisor.get("Nombre", "") or "").strip(),
		"emisor_regimen": (emisor.get("RegimenFiscal", "") or "").strip(),
		"receptor_rfc": (receptor.get("Rfc", "") or "").strip(),
		"receptor_nombre": (receptor.get("Nombre", "") or "").strip(),
		"receptor_regimen": (receptor.get("RegimenFiscalReceptor", "") or "").strip(),
		"receptor_cp": (receptor.get("DomicilioFiscalReceptor", "") or "").strip(),
		"receptor_residencia": (receptor.get("ResidenciaFiscal", "") or "").strip(),
		"receptor_numreg": (receptor.get("NumRegIdTrib", "") or "").strip(),
	}


# ------------------------------------------------------------------- utilidades
def _norm_name(s: str) -> str:
	"""Normaliza razón social para dedupe de extranjeros (sin acentos, mayúsculas, sin puntuación)."""
	s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
	s = re.sub(r"[^A-Za-z0-9]+", " ", s).strip().upper()
	return re.sub(r"\s+", " ", s)


def _is_extranjero(rfc: str, residencia: str) -> bool:
	if (rfc or "").upper() == _RFC_EXTRANJERO:
		return True
	r = (residencia or "").upper()
	return bool(r) and r != "MEX"


def load_company_rfcs(scope_company: str | None = None) -> dict:
	"""Mapa RFC(upper) -> nombre de Company. Si scope_company, solo esa."""
	if scope_company:
		rfc = frappe.db.get_value("Company", scope_company, "tax_id")
		return {rfc.upper(): scope_company} if rfc else {}
	rows = frappe.get_all("Company", fields=["name", "tax_id"])
	return {r.tax_id.upper(): r.name for r in rows if r.tax_id}


def _scan_xml(source_dir: str) -> list:
	paths = []
	for root, _dirs, files in os.walk(source_dir):
		for fn in files:
			if fn.lower().endswith(".xml"):
				paths.append(os.path.join(root, fn))
	return sorted(paths)


# --------------------------------------------------- rol + datos de la contraparte
def _role_and_counterparty(data: dict, company_rfcs: dict):
	"""Determina (rol, company, counterparty_dict) o (estado_error, detalle).

	Retorna un dict: {"error": <estado>, "detalle": ...} o
	{"role": "Customer"|"Supplier", "company": <name>, "party": {...}}.
	"""
	emisor_rfc = (data["emisor_rfc"] or "").upper()
	receptor_rfc = (data["receptor_rfc"] or "").upper()
	emisor_co = emisor_rfc in company_rfcs
	receptor_co = receptor_rfc in company_rfcs

	if emisor_co and receptor_co:
		return {"error": "ERROR_AMBIGUO", "detalle": "Emisor y Receptor son Company (intercompañía)"}
	if emisor_co:
		# La empresa EMITE -> la contraparte es el Receptor -> Customer
		party = {
			"role": "Customer",
			"rfc": data["receptor_rfc"],
			"nombre": data["receptor_nombre"],
			"regimen": data["receptor_regimen"],
			"cp": data["receptor_cp"],
			"residencia": data["receptor_residencia"],
			"numreg": data["receptor_numreg"],
		}
		return {"role": "Customer", "company": company_rfcs[emisor_rfc], "party": party}
	if receptor_co:
		# La empresa RECIBE -> la contraparte es el Emisor -> Supplier
		# (el Emisor no lleva ResidenciaFiscal/NumRegIdTrib en el CFDI; su CP = LugarExpedicion)
		party = {
			"role": "Supplier",
			"rfc": data["emisor_rfc"],
			"nombre": data["emisor_nombre"],
			"regimen": data["emisor_regimen"],
			"cp": data["lugar_expedicion"],
			"residencia": "",
			"numreg": "",
		}
		return {"role": "Supplier", "company": company_rfcs[receptor_rfc], "party": party}
	return {"error": "ERROR_COMPANY_RFC", "detalle": "Ni Emisor ni Receptor corresponden a una Company"}


def _dedupe_key(party: dict):
	"""Clave de consolidación. None si no se puede identificar de forma confiable.

	Nacional: (role, RFC). Extranjero genérico: NO por RFC -> NumRegIdTrib, o nombre+residencia."""
	role = party["role"]
	rfc = (party["rfc"] or "").upper()
	if not rfc:
		return None
	if _is_extranjero(party["rfc"], party["residencia"]):
		if party["numreg"]:
			return (role, "XEXX", "TIN:" + party["numreg"].upper())
		if party["nombre"]:
			return (role, "XEXX", "NAME:" + _norm_name(party["nombre"]), (party["residencia"] or "").upper())
		return None  # extranjero sin NumRegIdTrib ni nombre -> insuficiente
	return (role, rfc)


# ------------------------------------------------ existencia en ERPNext (read-only)
def _customer_exists(party: dict):
	"""(estado, matches) para un Customer. Extranjero genérico se resuelve por fm_num_reg_id_trib."""
	if _is_extranjero(party["rfc"], party["residencia"]):
		if not party["numreg"] or not frappe.db.has_column("Customer", "fm_num_reg_id_trib"):
			return "DATOS_INSUFICIENTES", []
		rows = frappe.get_all("Customer", filters={"fm_num_reg_id_trib": party["numreg"]}, fields=["name"])
	else:
		rows = frappe.get_all("Customer", filters={"tax_id": party["rfc"]}, fields=["name"])
	if len(rows) > 1:
		return "ERROR_AMBIGUO", [r.name for r in rows]
	if len(rows) == 1:
		return "EXISTENTE", [rows[0].name]
	return "A_CREAR_CUSTOMER", []


def _supplier_exists(party: dict):
	"""(estado, matches) para un Supplier. Extranjero genérico no es identificable de forma confiable."""
	if _is_extranjero(party["rfc"], party["residencia"]):
		# Supplier no tiene campo de TIN extranjero -> no se puede deduplicar/identificar con confianza.
		return "DATOS_INSUFICIENTES", []
	rows = frappe.get_all("Supplier", filters={"tax_id": party["rfc"]}, fields=["name"])
	if len(rows) > 1:
		return "ERROR_AMBIGUO", [r.name for r in rows]
	if len(rows) == 1:
		return "EXISTENTE", [rows[0].name]
	return "A_CREAR_SUPPLIER", []


def _resolve_estado(party: dict):
	"""Estado final del tercero. Requiere razón social para poder crearse."""
	if not party["rfc"]:
		return "DATOS_INSUFICIENTES", [], "sin RFC"
	estado, matches = (_customer_exists if party["role"] == "Customer" else _supplier_exists)(party)
	if estado.startswith("A_CREAR") and not party["nombre"]:
		return "DATOS_INSUFICIENTES", [], "sin razón social para crear"
	return estado, matches, ""


# ----------------------------------------------------------------- orquestación
def run(source_dir=None, manifest=None, dry_run=1, report_dir="/tmp", limit=None):
	"""Prepara terceros (Customer/Supplier) desde un directorio de XML CFDI. V1 solo lectura."""
	if not source_dir or not os.path.isdir(source_dir):
		frappe.throw(_("source_dir inválido: {0}").format(source_dir))

	scope = None
	if manifest:
		cfg = manifest
		if isinstance(manifest, str):
			with open(manifest, encoding="utf-8") as fh:  # nosemgrep: frappe-security-file-traversal
				cfg = json.load(fh)
		scope = (cfg or {}).get("company")

	company_rfcs = load_company_rfcs(scope)
	if not company_rfcs:
		frappe.throw(_("No hay Company con RFC (tax_id) configurado para identificar las partes."))

	paths = _scan_xml(source_dir)
	if limit:
		paths = paths[: int(limit)]

	detalle = []  # por archivo
	parties = {}  # dedupe_key -> party consolidado

	# Fase 1: parseo + rol + consolidación por RFC/evidencia
	for path in paths:
		fn = os.path.basename(path)
		try:
			with open(path, "rb") as fh:  # nosemgrep: frappe-security-file-traversal
				raw = fh.read()
			data = parse_partes_cfdi(raw)
		except Exception as exc:
			detalle.append({"archivo": fn, "estado": "ERROR_PARSE", "detalle": str(exc)[:200]})
			continue

		res = _role_and_counterparty(data, company_rfcs)
		if "error" in res:
			detalle.append({"archivo": fn, "estado": res["error"], "detalle": res["detalle"]})
			continue

		party = res["party"]
		key = _dedupe_key(party)
		entry = {
			"archivo": fn,
			"role": party["role"],
			"rfc": party["rfc"],
			"nombre": party["nombre"],
			"company": res["company"],
		}
		if key is None:
			entry["estado"] = "DATOS_INSUFICIENTES"
			entry["detalle"] = "extranjero sin NumRegIdTrib ni razón social"
			detalle.append(entry)
			continue

		p = parties.get(key)
		if p is None:
			parties[key] = {**party, "archivos": [fn]}
		else:
			p["archivos"].append(fn)
			# completar datos con la primera evidencia no vacía
			for f in ("nombre", "regimen", "cp", "residencia", "numreg"):
				if not p.get(f) and party.get(f):
					p[f] = party[f]
		entry["_key"] = key
		entry["dedupe_key"] = "|".join(str(x) for x in key)
		detalle.append(entry)

	# Fase 2: existencia (una vez por tercero único) — SOLO LECTURA
	key_estado = {}  # key -> estado final
	terceros = []
	for key, party in parties.items():
		estado, matches, motivo = _resolve_estado(party)
		key_estado[key] = estado
		terceros.append(
			{
				"role": party["role"],
				"rfc": party["rfc"],
				"nombre": party["nombre"],
				"regimen": party.get("regimen", ""),
				"cp": party.get("cp", ""),
				"residencia": party.get("residencia", ""),
				"numreg": party.get("numreg", ""),
				"estado": estado,
				"matches": matches,
				"motivo": motivo,
				"n_archivos": len(party["archivos"]),
			}
		)

	# Fase 3: estado final por archivo (propagado desde su tercero) + conteo por archivo
	counts = {k: 0 for k in _STATES}
	for e in detalle:
		k = e.pop("_key", None)
		if k is not None:
			e["estado"] = key_estado.get(k, "DATOS_INSUFICIENTES")
		counts[e["estado"]] = counts.get(e["estado"], 0) + 1

	rep = {
		"meta": {"source_dir": source_dir, "company_rfcs": list(company_rfcs.keys())},
		"resumen_archivos": counts,
		"resumen_terceros": _count_terceros(terceros),
		"terceros": terceros,
		"detalle": detalle,
	}
	_write_reports(rep, terceros, report_dir)
	_print_summary(rep)
	return {"resumen_archivos": counts, "resumen_terceros": rep["resumen_terceros"]}


def _count_terceros(terceros: list) -> dict:
	c = {k: 0 for k in _STATES}
	for t in terceros:
		c[t["estado"]] = c.get(t["estado"], 0) + 1
	return c


def _write_reports(rep, terceros, report_dir):
	stamp = frappe.utils.now().replace(":", "").replace(" ", "_").replace("-", "")[:15]
	base = os.path.join(report_dir, f"preparacion_terceros_{stamp}")

	with open(base + ".json", "w", encoding="utf-8") as fh:  # nosemgrep: frappe-security-file-traversal
		json.dump(rep, fh, ensure_ascii=False, indent=2, default=str)

	# reporte general CSV (por tercero consolidado)
	gen_cols = [
		"role",
		"rfc",
		"nombre",
		"regimen",
		"cp",
		"residencia",
		"numreg",
		"estado",
		"n_archivos",
		"motivo",
	]
	with open(
		base + ".csv", "w", encoding="utf-8", newline=""
	) as fh:  # nosemgrep: frappe-security-file-traversal
		w = csv.DictWriter(fh, fieldnames=gen_cols, extrasaction="ignore")
		w.writeheader()
		for t in terceros:
			w.writerow(t)

	# CSV Customers faltantes (Data Import) — solo datos confiables; group/territory se agregan aparte.
	cust = [t for t in terceros if t["estado"] == "A_CREAR_CUSTOMER"]
	if cust:
		path = base + "_customers_faltantes.csv"
		cols = [
			"customer_name",
			"tax_id",
			"fm_tax_regime",
			"fm_num_reg_id_trib",
			"codigo_postal_fiscal",
			"residencia_fiscal",
		]
		with open(path, "w", encoding="utf-8", newline="") as fh:  # nosemgrep: frappe-security-file-traversal
			w = csv.DictWriter(fh, fieldnames=cols)
			w.writeheader()
			for t in cust:
				w.writerow(
					{
						"customer_name": t["nombre"],
						"tax_id": t["rfc"],
						"fm_tax_regime": t["regimen"],
						"fm_num_reg_id_trib": t["numreg"],
						"codigo_postal_fiscal": t["cp"],
						"residencia_fiscal": t["residencia"],
					}
				)
		rep["meta"]["csv_customers_faltantes"] = path

	# CSV Suppliers faltantes (Data Import) — Supplier no tiene campos fiscales fm_*; CP/régimen informativos.
	sup = [t for t in terceros if t["estado"] == "A_CREAR_SUPPLIER"]
	if sup:
		path = base + "_suppliers_faltantes.csv"
		cols = ["supplier_name", "tax_id", "regimen_fiscal", "codigo_postal_fiscal"]
		with open(path, "w", encoding="utf-8", newline="") as fh:  # nosemgrep: frappe-security-file-traversal
			w = csv.DictWriter(fh, fieldnames=cols)
			w.writeheader()
			for t in sup:
				w.writerow(
					{
						"supplier_name": t["nombre"],
						"tax_id": t["rfc"],
						"regimen_fiscal": t["regimen"],
						"codigo_postal_fiscal": t["cp"],
					}
				)
		rep["meta"]["csv_suppliers_faltantes"] = path

	rep["meta"]["report_json"] = base + ".json"
	rep["meta"]["report_csv"] = base + ".csv"


def _print_summary(rep):
	print("\n=== Preparación de terceros desde CFDI (V1 SOLO LECTURA) ===")
	print("  --- por archivo ---")
	for k in _STATES:
		if rep["resumen_archivos"].get(k):
			print(f"    {k:20}: {rep['resumen_archivos'][k]}")
	print("  --- terceros únicos ---")
	for k in _STATES:
		if rep["resumen_terceros"].get(k):
			print(f"    {k:20}: {rep['resumen_terceros'][k]}")
	for label in ("report_json", "report_csv", "csv_customers_faltantes", "csv_suppliers_faltantes"):
		if rep["meta"].get(label):
			print(f"  {label:24}: {rep['meta'][label]}")
