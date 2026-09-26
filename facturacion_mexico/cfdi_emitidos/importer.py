# Copyright (c) 2026, Buzola and contributors
"""Motor genérico de importación masiva: CFDI XML de venta -> Sales Invoice (Draft).

Capacidad reusable de `facturacion_mexico`. Cada CFDI de Ingreso VIGENTE produce una
Sales Invoice nativa en `docstatus = 0` (Draft) con su XML original adjunto.

NO hace Submit, NO timbra, NO llama al PAC, NO crea Payment Entry, NO crea Items ni
Customers. El precio SIEMPRE viene del XML. Idempotente por UUID usando el campo
canónico `Sales Invoice.fm_folio_fiscal` (Folio Fiscal SAT = UUID).

El motor NO contiene datos de ningún cliente. La configuración específica de una
corrida (empresa, cuentas, mapping NoIdentificacion->item_code) se pasa como un
**manifest** (dict o ruta a JSON) externo al repositorio.

Ejecución (contexto Frappe, nunca python directo):

  # DRY-RUN (no escribe en BD):
  bench --site <site> execute \
    facturacion_mexico.cfdi_emitidos.importer.run \
    --kwargs "{'source_dir': '<ruta_xml>', 'manifest': '<ruta_manifest.json>', 'dry_run': 1}"

  # APLICAR (crea las Sales Invoice READY en Draft):
  bench --site <site> execute \
    facturacion_mexico.cfdi_emitidos.importer.run \
    --kwargs "{'source_dir': '<ruta_xml>', 'manifest': '<ruta_manifest.json>', 'dry_run': 0}"

Manifest (JSON) — campos:
  company            (str, requerido) Company destino.
  item_map           (dict, requerido) NoIdentificacion CFDI -> item_code REAL del site.
  iva_account        (str, requerido si hay traslados) cuenta para el IVA trasladado.
  default_cost_center(str, opcional) default si el Customer no tiene uno; si se omite,
                     se usa el cost_center por defecto de la Company.
  cancelled_marker   (str, opcional, default 'cancel') subcadena en el nombre de archivo
                     que marca un CFDI cancelado (se omite del alta).
  tolerance          (float, opcional, default 0.05) tolerancia decimal de reconciliación.
"""

import csv
import json
import os

import frappe
from frappe import _
from frappe.utils import flt, getdate

from facturacion_mexico.cfdi_emitidos.parser import CFDIError, is_ingreso, normalize_uuid, parse_cfdi


# ----------------------------------------------------------------- configuración
class RunConfig:
	"""Configuración de una corrida del importador, cargada desde un manifest (dict o JSON)."""

	def __init__(self, manifest):
		"""Carga y valida el manifest (company, item_map, cuentas y defaults de la corrida)."""
		cfg = manifest
		if isinstance(manifest, str):
			with open(manifest, encoding="utf-8") as fh:  # nosemgrep: frappe-security-file-traversal
				cfg = json.load(fh)
		cfg = cfg or {}
		self.company = cfg.get("company")
		if not self.company:
			frappe.throw(_("manifest.company es requerido"))
		self.item_map = cfg.get("item_map") or {}
		if not self.item_map:
			frappe.throw(_("manifest.item_map es requerido (NoIdentificacion -> item_code)"))
		self.iva_account = cfg.get("iva_account")
		self.cancelled_marker = (cfg.get("cancelled_marker") or "cancel").lower()
		self.tolerance = flt(cfg.get("tolerance") or 0.05)
		self.default_cost_center = cfg.get("default_cost_center") or frappe.db.get_value(
			"Company", self.company, "cost_center"
		)
		self.company_currency = frappe.db.get_value("Company", self.company, "default_currency")


# ------------------------------------------------------------------ resolución

# RFC genérico del SAT para receptores extranjeros. Con este RFC el tax_id NO
# identifica al Customer (todos los extranjeros lo comparten), así que la
# resolución se hace por la evidencia adicional del CFDI (NumRegIdTrib,
# ResidenciaFiscal, Nombre) contra los datos reales del Customer.
RFC_EXTRANJERO_GENERICO = "XEXX010101000"

# Mapa mínimo ISO-3 (ResidenciaFiscal SAT) -> nombres de país tal como los guarda
# ERPNext (Country / Address.country). Solo se usa como DESEMPATE, nunca como
# requisito: si no se puede mapear, no se filtra por país.
_RESIDENCIA_A_PAIS = {
	"MEX": {"mexico", "méxico"},
	"USA": {"united states", "estados unidos", "estados unidos de américa"},
	"CAN": {"canada", "canadá"},
	"COL": {"colombia"},
	"ECU": {"ecuador"},
	"ARG": {"argentina"},
	"BRA": {"brazil", "brasil"},
	"CHL": {"chile"},
	"ESP": {"spain", "españa"},
	"PER": {"peru", "perú"},
}


def _norm_nombre(value):
	"""Normaliza un nombre fiscal para comparación robusta (may/espacios/puntuación)."""
	s = (value or "").upper()
	for ch in (",", ".", "'"):
		s = s.replace(ch, " ")
	return " ".join(s.split())


def _customer_paises(name):
	"""Países (en minúsculas) de las direcciones ligadas a un Customer."""
	links = frappe.get_all(
		"Dynamic Link",
		filters={"link_doctype": "Customer", "link_name": name, "parenttype": "Address"},
		fields=["parent"],
	)
	paises = set()
	for lk in links:
		pais = frappe.db.get_value("Address", lk.parent, "country")
		if pais:
			paises.add(pais.strip().lower())
	return paises


def _residencia_coincide(residencia, name):
	"""True si la ResidenciaFiscal (ISO-3) coincide con algún país del Customer."""
	esperados = _RESIDENCIA_A_PAIS.get((residencia or "").upper())
	if not esperados:
		return False
	return bool(esperados & _customer_paises(name))


def _resolve_customer_extranjero(receptor):
	"""Resuelve un Customer para un receptor extranjero (RFC genérico XEXX).

	Usa, en este orden, la evidencia del CFDI contra los datos reales del maestro:
	  1. NumRegIdTrib contra su hogar canónico `fm_num_reg_id_trib`; fallback histórico a `tax_id`;
	  2. coincidencia inequívoca por Nombre fiscal;
	  3. ResidenciaFiscal/país como desempate cuando el Nombre no es único.
	Devuelve (customer|None, error|None): 1 match -> ok; 0 -> ERROR_CUSTOMER; >1 -> ERROR_CUSTOMER_AMB.
	"""
	receptor = receptor or {}
	numreg = (receptor.get("receptor_num_reg_id_trib") or "").strip()
	residencia = (receptor.get("receptor_residencia_fiscal") or "").strip().upper()
	nombre = _norm_nombre(receptor.get("receptor_nombre"))

	# 1. El número de identidad tributaria extranjero: primero en su hogar canónico
	#    (fm_num_reg_id_trib); si no hay match, fallback histórico contra tax_id (por si se
	#    registró ahí antes de existir el campo). Ambigüedad en cualquiera -> AMB.
	if numreg:
		for _campo in ("fm_num_reg_id_trib", "tax_id"):
			directo = frappe.get_all("Customer", filters={_campo: numreg}, fields=["name"])
			if len(directo) == 1:
				return directo[0].name, None
			if len(directo) > 1:
				return None, "ERROR_CUSTOMER_AMB"

	# Pool de candidatos: los Customers que comparten el RFC genérico.
	pool = frappe.get_all(
		"Customer",
		filters={"tax_id": RFC_EXTRANJERO_GENERICO},
		fields=["name", "customer_name"],
	)
	if not pool:
		return None, "ERROR_CUSTOMER"

	# 2. Coincidencia por Nombre fiscal.
	por_nombre = [c for c in pool if nombre and _norm_nombre(c.customer_name) == nombre]
	if len(por_nombre) == 1:
		return por_nombre[0].name, None

	# 3. Desempate por ResidenciaFiscal/país.
	base = por_nombre or pool
	if residencia:
		por_pais = [c for c in base if _residencia_coincide(residencia, c.name)]
		if len(por_pais) == 1:
			return por_pais[0].name, None
		if len(por_pais) > 1:
			return None, "ERROR_CUSTOMER_AMB"

	if len(por_nombre) > 1:
		return None, "ERROR_CUSTOMER_AMB"
	return None, "ERROR_CUSTOMER"


def resolve_customer(rfc, receptor=None):
	"""Resuelve el Customer del receptor de un CFDI.

	RFC distinto del genérico extranjero -> match por `tax_id` (comportamiento actual).
	RFC genérico extranjero (XEXX010101000) -> NO se resuelve solo por RFC; se usa la
	evidencia adicional del CFDI (`receptor`) vía `_resolve_customer_extranjero`.
	"""
	rfc = (rfc or "").strip().upper()
	if rfc == RFC_EXTRANJERO_GENERICO:
		if not receptor:
			return None, "ERROR_CUSTOMER"
		return _resolve_customer_extranjero(receptor)

	rows = frappe.get_all("Customer", filters={"tax_id": rfc}, fields=["name"])
	if len(rows) == 1:
		return rows[0].name, None
	if len(rows) == 0:
		return None, "ERROR_CUSTOMER"
	return None, "ERROR_CUSTOMER_AMB"


def resolve_item(noid, cfg, cache):
	"""Resuelve el item_code para un NoIdentificacion vía el item_map del manifest (con cache)."""
	itc = cfg.item_map.get(noid)
	if not itc:
		return None, None
	if itc not in cache:
		cache[itc] = frappe.db.get_value("Item", itc, ["stock_uom", "fm_producto_servicio_sat"], as_dict=True)
	if not cache[itc]:
		return None, None  # mapeado pero el item no existe en el site
	return itc, cache[itc]


def _cost_center_for(customer, cfg):
	"""Cost center del Customer (fm_customer_default_cost_center) o el default del manifest."""
	return (
		frappe.db.get_value("Customer", customer, "fm_customer_default_cost_center")
		or cfg.default_cost_center
	)


def existing_si_for_uuid(uuid):
	"""Idempotencia por LLAVE CANÓNICA: Sales Invoice.fm_folio_fiscal == UUID.

	(Folio Fiscal SAT = UUID.) No depende del File adjunto: detecta también SI
	históricas con UUID pero sin attachment.
	Devuelve (name|None, estado): 0->(None,None); 1->(name,'SKIP_EXISTING'); >1->(None,'ERROR_DUPLICATE').
	"""
	rows = frappe.get_all("Sales Invoice", filters={"fm_folio_fiscal": uuid}, fields=["name"])
	if not rows:
		return None, None
	if len(rows) == 1:
		return rows[0].name, "SKIP_EXISTING"
	return None, "ERROR_DUPLICATE"


# --------------------------------------------------------------- construcción SI
def _set(doc, field, value):
	"""Asigna un campo SOLO si existe en el esquema del site (robusto a diferencias)."""
	if value is None or value == "":
		return
	if doc.meta.has_field(field):
		doc.set(field, value)


def build_si(cfdi, cfg, item_cache):
	"""Construye el doc Sales Invoice (en memoria, sin insertar). Devuelve (doc, meta)."""
	customer, err = resolve_customer(cfdi["receptor_rfc"], cfdi)
	if err:
		return None, {"estado": err, "detalle": f"RFC {cfdi['receptor_rfc']}"}

	# Descuento fiscal (Concepto@Descuento / Comprobante@Descuento): el importador aún NO
	# representa el descuento del CFDI. En vez de fabricar totales incorrectos o destruir un
	# descuento legítimo, se reporta como gap y NO se importa. El caso SIN descuento (el de
	# esta carga) sigue funcionando de forma segura. Ver gap documentado.
	if flt(cfdi.get("descuento")) > cfg.tolerance or any(
		flt(c["descuento"]) > cfg.tolerance for c in cfdi["conceptos"]
	):
		return None, {
			"estado": "ERROR_DESCUENTO",
			"detalle": "CFDI con Descuento (Concepto/Comprobante) — no soportado aún por el importador",
		}

	lineas = []
	for c in cfdi["conceptos"]:
		itc, meta = resolve_item(c["noid"], cfg, item_cache)
		if not itc:
			return None, {"estado": "ERROR_ITEM", "detalle": f"NoIdentificacion {c['noid']!r} sin Item"}
		lineas.append((c, itc, meta))

	moneda = cfdi["moneda"]
	tc = flt(cfdi["tipo_cambio"]) if cfdi["tipo_cambio"] else 1.0
	cc = _cost_center_for(customer, cfg)
	metodo = (cfdi["metodo_pago"] or "").upper()

	doc = frappe.new_doc("Sales Invoice")
	doc.customer = customer
	doc.company = cfg.company
	# Captura histórica: fecha Y hora del CFDI (Comprobante.Fecha = 'YYYY-MM-DDTHH:MM:SS'),
	# no la hora de ejecución del import.
	doc.set_posting_time = 1
	doc.posting_date = getdate(cfdi["fecha"][:10])
	doc.posting_time = cfdi["fecha"][11:19] if "T" in (cfdi["fecha"] or "") else "00:00:00"
	doc.currency = moneda
	doc.conversion_rate = tc if moneda != cfg.company_currency else 1.0
	doc.cost_center = cc
	doc.update_stock = 0
	# Señal transitoria específica del importador histórico: el CFDI ya fue timbrado fuera del ERP;
	# sus impuestos vienen del XML (fuente de verdad). El guard de `_set_stct_by_branch` la usa para
	# NO imponer STCT nacional/frontera sobre estos documentos. Transitoria (solo durante la
	# construcción/insert de esta carga); no persiste ni afecta ediciones posteriores del flujo normal.
	doc.flags.fm_from_cfdi_emitidos = True
	# Evidencia territorial del XML histórico (transitoria, sin campo persistente): el
	# clasificador de ventas extranjeras le da precedencia sobre los datos maestros actuales,
	# para no reinterpretar la historia si el Customer cambió. Ver clasificacion.clasificar_desde_cfdi.
	doc.flags.fm_cfdi_territorial = {
		"receptor_rfc": cfdi.get("receptor_rfc"),
		"receptor_residencia_fiscal": cfdi.get("receptor_residencia_fiscal"),
		"receptor_num_reg_id_trib": cfdi.get("receptor_num_reg_id_trib"),
	}
	# Campos fiscales México — solo se asignan si EXISTEN en el esquema del site.
	if metodo == "PPD":
		_set(doc, "fm_es_ppd", 1)
	elif metodo == "PUE":
		_set(doc, "fm_es_ppd", 0)
	_set(doc, "fm_payment_method_sat", metodo if metodo in ("PUE", "PPD") else None)
	_set(doc, "fm_cfdi_use", cfdi["uso_cfdi"])
	_set(doc, "fm_forma_pago_timbrado", cfdi["forma_pago"])
	# fm_folio_fiscal = UUID: llave canónica de idempotencia (no el File adjunto).
	_set(doc, "fm_folio_fiscal", cfdi["uuid"])
	_set(doc, "fm_serie_folio", f"{cfdi['serie']}-{cfdi['folio']}" if cfdi.get("serie") else cfdi["folio"])
	_set(doc, "fm_lugar_expedicion", cfdi.get("lugar_expedicion"))

	for c, itc, meta in lineas:
		row = doc.append("items", {})
		row.item_code = itc
		row.qty = c["cantidad"]
		row.rate = c["valor_unitario"]
		# Precio de referencia = ValorUnitario del CFDI (histórico), NO el Item Price maestro.
		# Enviar price_list_rate == rate hace que ERPNext conserve ambos y NO fabrique
		# discount_amount (en calculate_item_rate, rate == price_list_rate => sin descuento).
		row.price_list_rate = c["valor_unitario"]
		row.uom = meta["stock_uom"]
		row.cost_center = cc
		# Preservar la descripción histórica del CFDI (evidencia), no la del Item maestro.
		row.description = c["descripcion"]
		_set(row, "fm_descripcion_cfdi", c["descripcion"])

	# Impuestos: reproducir EXACTO el CFDI. Si hay traslados, una fila "Actual" con el
	# importe real del XML sobre la cuenta IVA del manifest (evita drift de redondeo por línea).
	if cfdi["total_traslados"] > 0:
		if not cfg.iva_account:
			return None, {"estado": "ERROR_TAX", "detalle": "manifest.iva_account requerido (hay traslados)"}
		doc.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": cfg.iva_account,
				"description": "IVA trasladado (histórico CFDI)",
				"tax_amount": cfdi["total_traslados"],
				"cost_center": cc,
			},
		)
	return doc, {"estado": "READY", "customer": customer}


def reconcile_amounts(doc, cfdi, tol):
	"""Compara importes ERPNext vs CFDI. Devuelve (ok, diffs)."""
	checks = {
		"subtotal": (flt(doc.net_total, 2), flt(cfdi["subtotal"], 2)),
		"iva": (flt(doc.total_taxes_and_charges, 2), flt(cfdi["total_traslados"], 2)),
		"total": (flt(doc.grand_total, 2), flt(cfdi["total"], 2)),
		"lineas": (len(doc.items), len(cfdi["conceptos"])),
	}
	diffs = {}
	for k, (erp, xml) in checks.items():
		d = round(flt(erp) - flt(xml), 4)
		if abs(d) > (tol if k != "lineas" else 0):
			diffs[k] = {"erp": erp, "xml": xml, "diff": d}
	return (not diffs), diffs


def _attach_file(si_name, file_name, content, use_filesystem=False):
	"""Adjunta `content` como File privado nativo ligado a la Sales Invoice.

	Idempotente: si ya existe un File con ese `file_name` adjunto a esa SI, NO lo
	vuelve a crear (evita duplicar attachments en reejecuciones).

	`use_filesystem=True` (usado para PDF): escribe el blob a disco y referencia el
	`file_url` con `flags.copy_from_existing_file` — idéntico patrón a
	`File.create_attachment_copy` del framework. Así `File.before_insert` retorna
	antes de `write_file()/check_content()` y NO se ejecuta `pdf_contains_js`
	(PyPDF2), que parsea el PDF entero (lento; emite 'startxref'/'Object Streams').
	El PDF se conserva íntegro; solo se omite el escaneo antivirus/JS innecesario en
	esta importación controlada server-side.

	Devuelve (file_url, creado: bool).
	"""
	existing = frappe.get_all(
		"File",
		filters={
			"attached_to_doctype": "Sales Invoice",
			"attached_to_name": si_name,
			"file_name": file_name,
		},
		fields=["file_url"],
		limit=1,
	)
	if existing:
		return existing[0].file_url, False

	f = frappe.new_doc("File")
	f.is_private = 1
	f.attached_to_doctype = "Sales Invoice"
	f.attached_to_name = si_name
	f.flags.ignore_permissions = True
	if use_filesystem:
		from frappe.utils.file_manager import save_file_on_filesystem

		saved = save_file_on_filesystem(file_name, content, is_private=1)
		f.file_name = saved["file_name"]
		f.file_url = saved["file_url"]
		f.flags.copy_from_existing_file = True
	else:
		f.file_name = file_name
		f.content = content
	f.insert()
	return f.file_url, True


def _attach_xml(si_name, uuid, raw):
	"""Adjunta el XML original (fuente de verdad) como File privado ligado a la SI."""
	return _attach_file(si_name, f"CFDI-{uuid}.xml", raw)


def _find_pdf_for(xml_path):
	"""Ruta del PDF correspondiente a un XML, de forma DETERMINISTA.

	Regla: mismo stem (nombre sin extensión) en el MISMO directorio que el XML
	(`<stem>.xml` -> `<stem>.pdf`). Sin fuzzy matching. Devuelve la ruta o None.
	"""
	stem = os.path.splitext(xml_path)[0]
	for ext in (".pdf", ".PDF"):
		cand = stem + ext
		if os.path.isfile(cand):
			return cand
	return None


def _scan_source(source_dir):
	"""Escanea el directorio y separa XML, PDF y PDF huérfanos (sin XML hermano).

	La asociación XML<->PDF es por stem+directorio (determinista). Un PDF es
	huérfano si en su mismo directorio NO existe `<stem>.xml`/`<stem>.XML`.
	"""
	xml_paths, pdf_paths, orphan_pdfs = [], [], []
	for base, _dirs, files in os.walk(source_dir):
		for fn in sorted(files):
			low = fn.lower()
			full = os.path.join(base, fn)
			if low.endswith(".xml"):
				xml_paths.append(full)
			elif low.endswith(".pdf"):
				pdf_paths.append(full)
	for p in pdf_paths:
		stem = os.path.splitext(p)[0]
		if not (os.path.isfile(stem + ".xml") or os.path.isfile(stem + ".XML")):
			orphan_pdfs.append(p)
	xml_paths.sort()
	orphan_pdfs.sort()
	return {"xml": xml_paths, "pdf": pdf_paths, "orphan_pdf": orphan_pdfs}


def corregir_posting_time(source_dir=None, dry_run=1, report_dir="/tmp"):
	"""Corrección controlada: fija `posting_time` de SI históricas ya creadas a la hora
	REAL de su CFDI (Comprobante.Fecha). Toca EXCLUSIVAMENTE `posting_time` (nada más).

	Empareja por la llave canónica `fm_folio_fiscal == UUID`. Solo afecta Draft (docstatus=0).
	dry_run=1 (default) reporta sin escribir; dry_run=0 aplica vía frappe.db.set_value.
	"""
	if not source_dir or not os.path.isdir(source_dir):
		frappe.throw(f"source_dir inválido: {source_dir!r}")
	dry_run = int(dry_run)
	cambios, sin_si, ya_ok = [], [], 0
	for base, _dirs, files in os.walk(source_dir):
		for fn in sorted(files):
			if not fn.lower().endswith(".xml"):
				continue
			try:
				with open(os.path.join(base, fn), "rb") as fh:  # nosemgrep: frappe-security-file-traversal
					cfdi = parse_cfdi(fh.read())
			except CFDIError:
				continue
			fecha = cfdi["fecha"] or ""
			target = fecha[11:19] if "T" in fecha else "00:00:00"
			si = frappe.get_all(
				"Sales Invoice",
				filters={"fm_folio_fiscal": cfdi["uuid"], "docstatus": 0},
				fields=["name", "posting_time"],
			)
			if not si:
				sin_si.append(cfdi["uuid"])
				continue
			actual = str(si[0].get("posting_time") or "")[:8]
			if actual == target:
				ya_ok += 1
				continue
			cambios.append(
				{
					"sales_invoice": si[0].name,
					"uuid": cfdi["uuid"],
					"posting_time_actual": actual,
					"posting_time_nuevo": target,
				}
			)
			if not dry_run:
				# Este comando MODIFICA la base de datos (solo el campo posting_time).
				frappe.db.set_value(
					"Sales Invoice", si[0].name, "posting_time", target, update_modified=False
				)
	if not dry_run:
		frappe.db.commit()  # nosemgrep: frappe-manual-commit - importación por lote (durabilidad por factura)
	out = {
		"dry_run": dry_run,
		"a_corregir": len(cambios),
		"ya_correctas": ya_ok,
		"sin_si": len(sin_si),
		"detalle": cambios,
	}
	path = os.path.join(report_dir, "posting_time_%s.json" % ("dryrun" if dry_run else "apply"))
	with open(path, "w", encoding="utf-8") as fh:  # nosemgrep: frappe-security-file-traversal
		json.dump(out, fh, ensure_ascii=False, indent=2, default=str)
	print(
		f"posting_time — {'DRY-RUN' if dry_run else 'APLICADO'}: a_corregir={len(cambios)} "
		f"ya_ok={ya_ok} sin_si={len(sin_si)} · reporte={path}"
	)
	return {k: v for k, v in out.items() if k != "detalle"}


# ------------------------------------------------------------------ orquestador
def run(source_dir=None, manifest=None, dry_run=1, report_dir="/tmp", limit=None, uuids=None):
	"""Importa CFDI de un directorio. `uuids` (opcional, lista o str separada por comas/espacios)
	restringe la corrida EXCLUSIVAMENTE a esos UUID (dry-run o real). Sin `uuids`, procesa todo.
	"""
	if not source_dir or not os.path.isdir(source_dir):
		frappe.throw(f"source_dir inválido: {source_dir!r}")
	if not manifest:
		frappe.throw(_("manifest es requerido (dict o ruta a JSON con company/item_map/iva_account)"))
	cfg = RunConfig(manifest)
	dry_run = int(dry_run)

	# Filtro opcional por UUID (no hardcodeado; viene por parámetro).
	uuids_set = None
	if uuids:
		if isinstance(uuids, str):
			uuids = uuids.replace(",", " ").split()
		uuids_set = {normalize_uuid(u) for u in uuids if u}

	scan = _scan_source(source_dir)
	paths = scan["xml"]

	# Si se pidieron UUID específicos, restringir la lista de archivos a esos CFDI
	# (pre-parse ligero solo del UUID). La lógica e idempotencia del lote no cambian.
	if uuids_set is not None:
		seleccion = []
		for p in paths:
			try:
				with open(p, "rb") as fh:  # nosemgrep: frappe-security-file-traversal
					u = parse_cfdi(fh.read())["uuid"]
			except Exception:
				continue
			if u in uuids_set:
				seleccion.append(p)
		paths = seleccion

	if limit:
		paths = paths[: int(limit)]

	rep = {
		"meta": {"source_dir": source_dir, "dry_run": dry_run, "company": cfg.company},
		"resumen": {},
		"detalle": [],
		# PDF sin XML hermano: se reportan, NUNCA generan Sales Invoice.
		"pdf_huerfanos": [os.path.relpath(p, source_dir) for p in scan["orphan_pdf"]],
	}
	counts = {
		k: 0
		for k in (
			"total_xml",
			"vigentes",
			"cancelados",
			"READY",
			"CREADA",
			"SKIP_EXISTING",
			"SKIP_CANCELLED",
			"ERROR_CUSTOMER",
			"ERROR_CUSTOMER_AMB",
			"ERROR_ITEM",
			"ERROR_TAX",
			"ERROR_TOTAL",
			"ERROR_DESCUENTO",
			"ERROR_DUPLICATE",
			"ERROR_OTHER",
		)
	}
	item_cache = {}

	# Supresión LOCAL de creación/actualización de Item Price durante la importación.
	# insert_item_price() (dentro de get_item_details) retorna temprano si auto_insert=0.
	# Se muta el doc de Stock Settings CACHEADO en memoria (frappe.local, por request/job):
	# NO escribe en BD, NO cambia config global persistente, NO parchea core y NO contamina
	# otras operaciones concurrentes. Se restaura SIEMPRE (try/finally).
	_ss = frappe.get_cached_doc("Stock Settings")
	_orig_auto_insert = _ss.auto_insert_price_list_rate_if_missing
	_ss.auto_insert_price_list_rate_if_missing = 0

	try:
		for path in paths:
			fn = os.path.basename(path)
			counts["total_xml"] += 1
			entry = {"archivo": fn}
			try:
				with open(path, "rb") as fh:  # nosemgrep: frappe-security-file-traversal
					raw = fh.read()
			except OSError as exc:
				counts["ERROR_OTHER"] += 1
				rep["detalle"].append({**entry, "estado": "ERROR_OTHER", "detalle": f"lectura: {exc}"})
				continue

			if cfg.cancelled_marker in fn.lower():
				counts["cancelados"] += 1
				counts["SKIP_CANCELLED"] += 1
				rep["detalle"].append({**entry, "estado": "SKIP_CANCELLED"})
				continue
			counts["vigentes"] += 1

			try:
				cfdi = parse_cfdi(raw)
			except CFDIError as exc:
				counts["ERROR_OTHER"] += 1
				rep["detalle"].append({**entry, "estado": "ERROR_OTHER", "detalle": str(exc)})
				continue

			if not is_ingreso(cfdi):
				counts["ERROR_OTHER"] += 1
				rep["detalle"].append(
					{
						**entry,
						"uuid": cfdi["uuid"],
						"estado": "ERROR_OTHER",
						"detalle": f"TipoDeComprobante={cfdi.get('tipo')!r} (no Ingreso)",
					}
				)
				continue

			entry.update(
				{
					"uuid": cfdi["uuid"],
					"serie": cfdi["serie"],
					"folio": cfdi["folio"],
					"rfc": cfdi["receptor_rfc"],
					"moneda": cfdi["moneda"],
					"total_xml": cfdi["total"],
				}
			)

			existing, idem_estado = existing_si_for_uuid(cfdi["uuid"])
			if idem_estado == "SKIP_EXISTING":
				counts["SKIP_EXISTING"] += 1
				rep["detalle"].append({**entry, "estado": "SKIP_EXISTING", "sales_invoice": existing})
				continue
			if idem_estado == "ERROR_DUPLICATE":
				counts["ERROR_DUPLICATE"] += 1
				rep["detalle"].append(
					{
						**entry,
						"estado": "ERROR_DUPLICATE",
						"detalle": f"UUID {cfdi['uuid']} en >1 Sales Invoice",
					}
				)
				continue

			doc, meta = build_si(cfdi, cfg, item_cache)
			if doc is None:
				counts[meta["estado"]] = counts.get(meta["estado"], 0) + 1
				rep["detalle"].append({**entry, "estado": meta["estado"], "detalle": meta.get("detalle")})
				continue
			counts["READY"] += 1

			doc.flags.ignore_permissions = True
			if dry_run:
				# Dry-run NO destructivo: valida (dispara hooks fm) y calcula importes SIN insertar.
				try:
					doc.set_missing_values()
					doc.run_method("before_validate")
					doc.run_method("validate")
					ok, diffs = reconcile_amounts(doc, cfdi, cfg.tolerance)
					entry.update({"customer": meta["customer"], "total_erp": flt(doc.grand_total, 2)})
					# Informativo: qué adjuntos tendría al aplicar (XML siempre; PDF si hay hermano).
					entry["xml_adjunto"] = True
					entry["pdf_adjunto"] = bool(_find_pdf_for(path))
					if ok:
						entry["estado"] = "READY_OK"
					else:
						counts["READY"] -= 1
						counts["ERROR_TOTAL"] += 1
						entry["estado"] = "ERROR_TOTAL"
						entry["diferencias"] = diffs
				except Exception as exc:
					counts["READY"] -= 1
					counts["ERROR_OTHER"] += 1
					entry["estado"] = "ERROR_OTHER"
					entry["detalle"] = f"{type(exc).__name__}: {exc}"[:300]
				rep["detalle"].append(entry)
				continue

			# APLICAR: transacción por factura (insert + adjuntar XML + verificar + commit).
			sp = "cfdi_emit_" + cfdi["uuid"][:8]
			frappe.db.savepoint(sp)
			try:
				doc.insert()  # docstatus=0
				ok, diffs = reconcile_amounts(doc, cfdi, cfg.tolerance)
				entry.update(
					{
						"sales_invoice": doc.name,
						"customer": meta["customer"],
						"total_erp": flt(doc.grand_total, 2),
					}
				)
				if not ok:
					frappe.db.rollback(save_point=sp)
					counts["READY"] -= 1
					counts["ERROR_TOTAL"] += 1
					entry["estado"] = "ERROR_TOTAL"
					entry["diferencias"] = diffs
				else:
					# XML: fuente de verdad, siempre se adjunta (idempotente).
					_attach_xml(doc.name, cfdi["uuid"], raw)
					entry["xml_adjunto"] = True
					# PDF: si existe el hermano determinista, adjuntarlo también.
					pdf_path = _find_pdf_for(path)
					if pdf_path:
						with open(pdf_path, "rb") as fh:  # nosemgrep: frappe-security-file-traversal
							# use_filesystem=True: adjunta el PDF SIN reparseo (evita pdf_contains_js/PyPDF2).
							_attach_file(doc.name, f"CFDI-{cfdi['uuid']}.pdf", fh.read(), use_filesystem=True)
						entry["pdf_adjunto"] = True
					else:
						entry["pdf_adjunto"] = False
					frappe.db.commit()  # nosemgrep: frappe-manual-commit - importación por lote (durabilidad por factura)
					counts["CREADA"] += 1
					entry["estado"] = "CREADA"
			except Exception as exc:
				frappe.db.rollback(save_point=sp)
				counts["READY"] -= 1
				counts["ERROR_OTHER"] += 1
				entry["estado"] = "ERROR_OTHER"
				entry["detalle"] = f"{type(exc).__name__}: {exc}"[:300]
			rep["detalle"].append(entry)
	finally:
		# Restaurar SIEMPRE el valor en memoria del Single (no se tocó la BD),
		# incluso ante una excepción fuera del manejo por factura.
		_ss.auto_insert_price_list_rate_if_missing = _orig_auto_insert

	rep["resumen"] = counts
	_write_reports(rep, report_dir, dry_run)
	_print_summary(rep)
	return rep["resumen"]


def _write_reports(rep, report_dir, dry_run):
	"""Escribe los reportes JSON y CSV de la corrida en `report_dir`."""
	tag = "dryrun" if dry_run else "apply"
	stamp = frappe.utils.now().replace(":", "").replace(" ", "_").replace("-", "")[:15]
	base = os.path.join(report_dir, f"cfdi_emitidos_{tag}_{stamp}")
	with open(base + ".json", "w", encoding="utf-8") as fh:  # nosemgrep: frappe-security-file-traversal
		json.dump(rep, fh, ensure_ascii=False, indent=2, default=str)
	cols = [
		"archivo",
		"uuid",
		"serie",
		"folio",
		"rfc",
		"customer",
		"moneda",
		"total_xml",
		"total_erp",
		"sales_invoice",
		"xml_adjunto",
		"pdf_adjunto",
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


def _print_summary(rep):
	"""Imprime el resumen de contadores y excepciones de la corrida."""
	c = rep["resumen"]
	print(
		"\n=== CFDI emitidos → Sales Invoice — %s ===" % ("DRY-RUN" if rep["meta"]["dry_run"] else "APLICAR")
	)
	for k in (
		"total_xml",
		"vigentes",
		"cancelados",
		"SKIP_CANCELLED",
		"SKIP_EXISTING",
		"READY",
		"CREADA",
		"ERROR_CUSTOMER",
		"ERROR_CUSTOMER_AMB",
		"ERROR_ITEM",
		"ERROR_TAX",
		"ERROR_TOTAL",
		"ERROR_DESCUENTO",
		"ERROR_DUPLICATE",
		"ERROR_OTHER",
	):
		if c.get(k):
			print(f"  {k:20}: {c[k]}")
	huerfanos = rep.get("pdf_huerfanos") or []
	if huerfanos:
		print(f"  {'pdf_huerfanos':20}: {len(huerfanos)} (PDF sin XML — NO se importan)")
	print(f"  reporte JSON        : {rep['meta'].get('report_json')}")
	print(f"  reporte CSV         : {rep['meta'].get('report_csv')}")
	if huerfanos:
		print("  --- PDF huérfanos (sin XML correspondiente) ---")
		for h in huerfanos[:40]:
			print(f"    {h}")
	exc = [e for e in rep["detalle"] if e["estado"] not in ("READY_OK", "CREADA", "SKIP_CANCELLED")]
	if exc:
		print("  --- excepciones ---")
		for e in exc[:40]:
			print(
				f"    [{e['estado']}] {e.get('uuid') or e['archivo']}: {e.get('detalle') or e.get('diferencias') or ''}"
			)
