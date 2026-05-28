"""
API pública de CFDI Recibidos.

Endpoints Fase 1:
    upload_xml              — carga uno o varios XMLs CFDI y los persiste como CFDI Recibido.

Endpoints Fase 2:
    resolve_supplier        — asigna proveedor por RFC o vinculación manual.
    classify_concepts       — aplica CFDI Concepto Mapping sobre conceptos del CFDI.
    save_mapping_rule       — crea o actualiza una regla de clasificación.

Endpoints Hito B:
    generate_missing_suppliers — crea Suppliers en lote para CFDIs en "Falta proveedor".

Endpoints C.2 — Department:
    get_department_candidates  — CFDIs con proveedor pero sin departamento asignado.
    assign_departments         — asigna departamento en lote, valida contra configuración.

Endpoints Fase 3:
    build_purchase_invoice  — convierte CFDI Recibido Clasificado a Purchase Invoice Draft.
    suggest_supplier_from_cfdi — sugiere datos de proveedor sin crearlo automáticamente.
"""

import frappe
from frappe import _

from facturacion_mexico.cfdi_recibidos.services.xml_ingestion import ingest_xml

# Estados del CFDI Recibido que permiten intentar la conversión a PI
_ALLOWED_STATUSES_FOR_BUILD = {"Clasificado", "Error conversión", "Convertido a PI"}


@frappe.whitelist()
def upload_xml(company: str) -> list[dict]:
	"""
	Carga uno o varios XMLs CFDI 4.0 y los procesa como CFDI Recibido.

	Parámetros (form-data):
	    company   — nombre de la empresa en ERPNext
	    files     — uno o más archivos XML (campo "files" o "file")

	Retorna lista de resultados por archivo:
	    file_name     — nombre del archivo recibido
	    status        — etapa del CFDI ("Falta proveedor" | "Falta clasificación" | "Clasificado" |
	                    "duplicado" | "error")
	    cfdi_recibido — nombre del doc creado (None si duplicado sin doc nuevo)
	    uuid          — UUID extraído del XML
	    message       — descripción del resultado
	    next_action   — acción sugerida al usuario (None para duplicado/error)
	"""
	if not company:
		frappe.throw(_("El campo 'company' es obligatorio"), frappe.MandatoryError)

	# Frappe expone archivos subidos en frappe.request.files
	files = frappe.request.files
	if not files:
		frappe.throw(_("No se recibieron archivos XML"), frappe.ValidationError)

	results = []

	# Soporta campo "files" (múltiples) o "file" (singular)
	file_list = files.getlist("files") or files.getlist("file") or list(files.values())

	for uploaded_file in file_list:
		file_name = getattr(uploaded_file, "filename", "cfdi.xml") or "cfdi.xml"
		try:
			xml_bytes = uploaded_file.read()
			result = ingest_xml(xml_bytes, company, file_name=file_name)
		except Exception as e:
			frappe.log_error(
				message=f"Archivo: {file_name} | Empresa: {company} | Error: {e}",
				title="CFDI Recibidos Upload Error",
			)
			result = {
				"status": "error",
				"cfdi_recibido": None,
				"uuid": None,
				"message": str(e),
				"next_action": None,
			}

		results.append({"file_name": file_name, **result})

	return results


@frappe.whitelist()
def resolve_supplier(cfdi_recibido: str, supplier: str | None = None) -> dict:
	"""
	Asigna el proveedor al CFDI Recibido.

	Sin `supplier`: busca automáticamente por Supplier.tax_id == supplier_rfc.
	Con `supplier`: vinculación manual (aunque el RFC no coincida).
	No autocrea Suppliers.
	"""
	from facturacion_mexico.cfdi_recibidos.services.supplier_resolver import (
		resolve_supplier as _resolve,
	)

	if not cfdi_recibido:
		frappe.throw(_("El campo 'cfdi_recibido' es obligatorio"), frappe.MandatoryError)

	return _resolve(cfdi_recibido, supplier_override=supplier or None)


@frappe.whitelist()
def classify_concepts(cfdi_recibido: str) -> dict:
	"""
	Aplica reglas de CFDI Concepto Mapping sobre todos los conceptos.

	Actualiza status del CFDI Recibido:
	  - Clasificado: todos los conceptos tienen item_code asignado
	  - Falta clasif.: al menos uno sin regla
	"""
	from facturacion_mexico.cfdi_recibidos.services.concept_classifier import (
		classify_concepts as _classify,
	)

	if not cfdi_recibido:
		frappe.throw(_("El campo 'cfdi_recibido' es obligatorio"), frappe.MandatoryError)

	return _classify(cfdi_recibido)


@frappe.whitelist()
def save_mapping_rule(
	target_type: str,
	supplier_rfc: str = "",
	sat_product_key: str = "",
	target_item: str = "",
	target_account: str = "",
	target_cost_center: str = "",
	company: str = "",
) -> dict:
	"""
	Crea o actualiza una regla de CFDI Concepto Mapping.

	Si ya existe una regla con la misma combinación company+supplier_rfc+sat_product_key,
	la actualiza. Si no, crea una nueva.

	Retorna: {status, mapping, message}
	"""
	if target_type not in ("Item", "ExpenseAccount"):
		frappe.throw(_("target_type debe ser 'Item' o 'ExpenseAccount'"), frappe.ValidationError)

	# Check for existing rule with same key combination — company siempre incluido en la clave
	filters = {
		"supplier_rfc": supplier_rfc,
		"sat_product_key": sat_product_key,
		"company": company if company else ["in", ["", None]],
	}

	existing = frappe.db.get_value("CFDI Concepto Mapping", filters, "name")

	if existing:
		doc = frappe.get_doc("CFDI Concepto Mapping", existing)
	else:
		doc = frappe.new_doc("CFDI Concepto Mapping")
		doc.company = company or None
		doc.supplier_rfc = supplier_rfc
		doc.sat_product_key = sat_product_key

	doc.target_type = target_type
	doc.target_item = target_item or None
	doc.target_account = target_account or None
	doc.target_cost_center = target_cost_center or None
	doc.is_active = 1

	doc.save(ignore_permissions=True)

	action = "actualizada" if existing else "creada"
	return {"status": "ok", "mapping": doc.name, "message": f"Regla {action}: {doc.name}"}


@frappe.whitelist()
def generate_missing_suppliers(cfdi_names=None) -> dict:
	"""
	Crea Suppliers en lote para CFDIs en estado 'Falta proveedor'.

	Parámetros:
	    cfdi_names — JSON array de nombres de CFDI Recibido (opcional).
	                 Sin valor: procesa todos los candidatos activos.

	Retorna:
	    creados               — Suppliers nuevos creados y asignados
	    ya_existian_y_asignados — Suppliers preexistentes asignados
	    omitidos              — CFDIs no candidatos (pasados en cfdi_names)
	    errores               — lista de {name, message} con fallos por CFDI
	"""
	from facturacion_mexico.cfdi_recibidos.services.supplier_resolver import (
		generate_missing_suppliers as _generate,
	)

	names = frappe.parse_json(cfdi_names) if cfdi_names else None
	return _generate(names)


_TERMINAL_STATUSES = frozenset(
	["XML inválido", "No aplicable", "No procesar", "Convertido a PI", "Error conversión"]
)


@frappe.whitelist()
def get_department_candidates(company: str = "") -> list[dict]:
	"""
	Retorna CFDIs con proveedor asignado y sin departamento.

	Candidatos: supplier definido, department vacío, no_procesar=0,
	status fuera de terminales.
	"""
	filters: dict = {
		"supplier": ["is", "set"],
		"department": ["is", "not set"],
		"no_procesar": 0,
		"status": ["not in", list(_TERMINAL_STATUSES)],
	}
	if company:
		filters["company"] = company

	return frappe.get_all(
		"CFDI Recibido",
		filters=filters,
		fields=[
			"name",
			"supplier",
			"supplier_name",
			"supplier_rfc",
			"company",
			"total",
			"issue_date",
			"status",
		],
		order_by="issue_date desc",
		limit=500,
	)


@frappe.whitelist()
def assign_departments(assignments: str) -> dict:
	"""
	Asigna departamento a múltiples CFDIs Recibidos en lote.

	assignments: JSON dict {cfdi_name: department_name, ...}

	Reglas:
	- CFDI ya con departamento → omitido
	- department vacío en el dict → omitido
	- departamento no registrado en Configuracion CFDI Recibidos de la empresa → omitido
	- resto → asignado; status recalculado con compute_stage

	Retorna: {asignados, omitidos, errores}
	"""
	from facturacion_mexico.cfdi_recibidos.services.status_manager import compute_stage

	data: dict = frappe.parse_json(assignments) if isinstance(assignments, str) else assignments

	asignados = 0
	omitidos = 0
	errores = []

	# Cache company → set of mapped departments (evita queries repetidas)
	config_cache: dict[str, set] = {}

	for cfdi_name, department in data.items():
		try:
			doc = frappe.get_doc("CFDI Recibido", cfdi_name)

			if doc.department:
				omitidos += 1
				continue

			if not department:
				omitidos += 1
				continue

			company = doc.company
			if company not in config_cache:
				config_name = f"CFDI-REC-CFG-{company}"
				if frappe.db.exists("Configuracion CFDI Recibidos", config_name):
					cfg = frappe.get_doc("Configuracion CFDI Recibidos", config_name)
					config_cache[company] = {row.department for row in cfg.mapeo_departamentos}
				else:
					config_cache[company] = set()

			if department not in config_cache[company]:
				omitidos += 1
				continue

			doc.department = department
			new_status = compute_stage(doc)
			frappe.db.set_value(
				"CFDI Recibido",
				cfdi_name,
				{"department": department, "status": new_status},
			)
			asignados += 1

		except Exception as e:
			errores.append({"name": cfdi_name, "message": str(e)})

	frappe.db.commit()
	return {"asignados": asignados, "omitidos": omitidos, "errores": errores}


@frappe.whitelist()
def build_purchase_invoice(cfdi_recibido: str) -> dict:
	"""
	Convierte CFDI Recibido Clasificado a Purchase Invoice Draft.

	Solo permite conversión en estados: Clasificado, Error conversión, Convertido a PI.
	En error actualiza el CFDI Recibido a 'Error conversión' con detalle del error.
	Idempotente por UUID: si ya existe PI para el UUID retorna recovered=True.

	Retorna:
	    status          — "ok" | "recovered" | "error"
	    purchase_invoice — nombre del PI creado/recuperado (None si error)
	    recovered       — True si la PI ya existía y se reparó el vínculo
	    message         — descripción del resultado
	"""
	if not cfdi_recibido:
		frappe.throw(_("El campo 'cfdi_recibido' es obligatorio"), frappe.MandatoryError)

	doc = frappe.get_doc("CFDI Recibido", cfdi_recibido)
	if doc.status not in _ALLOWED_STATUSES_FOR_BUILD:
		frappe.throw(
			_(
				"El CFDI debe estar en estado 'Clasificado' para convertirse a Purchase Invoice. Estado actual: {0}"
			).format(doc.status),
			frappe.ValidationError,
		)

	from facturacion_mexico.cfdi_recibidos.services.purchase_invoice_builder import (
		build_purchase_invoice as _build,
	)

	try:
		result = _build(cfdi_recibido)
		recovered = result.get("recovered", False)
		pi_name = result["purchase_invoice"]
		return {
			"status": "recovered" if recovered else "ok",
			"purchase_invoice": pi_name,
			"recovered": recovered,
			"message": (
				f"Purchase Invoice {pi_name} recuperada (idempotente)"
				if recovered
				else f"Purchase Invoice {pi_name} creada correctamente"
			),
		}
	except Exception as e:
		frappe.db.rollback()
		frappe.db.set_value(
			"CFDI Recibido",
			cfdi_recibido,
			{"status": "Error conversión", "error_message": str(e)[:500]},
		)
		if not isinstance(e, frappe.ValidationError):
			frappe.log_error(
				message=f"CFDI: {cfdi_recibido} | Error: {e}",
				title="CFDI Recibidos build_purchase_invoice Error",
			)
		return {"status": "error", "purchase_invoice": None, "recovered": False, "message": str(e)}


@frappe.whitelist()
def propose_item(
	cfdi_recibido: str,
	sat_product_key: str = "",
	no_identificacion: str = "",
	item_group: str = "",
) -> dict:
	"""
	Propone item_code e item_resolution para un concepto CFDI.
	Solo lectura — delega a ItemResolver sin modificar documentos.
	"""
	from facturacion_mexico.cfdi_recibidos.services.item_resolver import ItemResolver

	if not cfdi_recibido:
		frappe.throw(_("El campo 'cfdi_recibido' es obligatorio"), frappe.MandatoryError)

	doc = frappe.get_doc("CFDI Recibido", cfdi_recibido)
	return ItemResolver().propose(
		sat_product_key=sat_product_key,
		no_identificacion=no_identificacion,
		item_group=item_group,
		company=doc.company,
		supplier=doc.supplier or "",
		supplier_rfc=doc.supplier_rfc or "",
	)


@frappe.whitelist()
def classify_all_concepts(cfdi_recibido: str) -> dict:
	"""
	Aplica niveles automáticos confiables de ItemResolver (Mapeado + Específico).
	No sobreescribe conceptos ya clasificados.
	No asigna Items genéricos GASTO-* automáticamente.
	Si no hay match, deja el concepto sin item_code (pendiente).
	Rechaza ítems que no pasen validate_expense_item.
	Actualiza status con compute_stage tras las asignaciones.

	Retorna: {auto_clasificados, pendientes, status}
	"""
	from facturacion_mexico.cfdi_recibidos.services.item_resolver import ItemResolver
	from facturacion_mexico.cfdi_recibidos.services.item_validator import validate_expense_item
	from facturacion_mexico.cfdi_recibidos.services.status_manager import compute_stage

	_PROTECTED = frozenset(
		["XML inválido", "No aplicable", "No procesar", "Convertido a PI", "Error conversión"]
	)

	if not cfdi_recibido:
		frappe.throw(_("El campo 'cfdi_recibido' es obligatorio"), frappe.MandatoryError)

	doc = frappe.get_doc("CFDI Recibido", cfdi_recibido)
	if doc.status in _PROTECTED:
		frappe.throw(
			_("No se puede clasificar un CFDI en estado '{0}'.").format(doc.status),
			frappe.ValidationError,
		)

	resolver = ItemResolver()
	auto_clasificados = 0
	pendientes = 0

	for concepto in doc.conceptos or []:
		if concepto.item_code:
			continue  # no sobreescribir

		proposal = resolver.propose(
			sat_product_key=concepto.sat_product_key or "",
			no_identificacion=concepto.no_identificacion or "",
			item_group=concepto.item_group or "",
			company=doc.company,
			supplier=doc.supplier or "",
			supplier_rfc=doc.supplier_rfc or "",
		)

		if not proposal["item_code"]:
			pendientes += 1
			continue

		ok, _reason = validate_expense_item(proposal["item_code"])
		if not ok:
			pendientes += 1
			continue

		item_group = frappe.db.get_value("Item", proposal["item_code"], "item_group")
		frappe.db.set_value(
			"CFDI Recibido Concepto",
			concepto.name,
			{
				"item_code": proposal["item_code"],
				"item_resolution": proposal["item_resolution"],
				"item_group": item_group,
			},
		)
		auto_clasificados += 1

	doc.reload()
	nuevo_status = compute_stage(doc)
	frappe.db.set_value("CFDI Recibido", cfdi_recibido, "status", nuevo_status)
	frappe.db.commit()

	return {"auto_clasificados": auto_clasificados, "pendientes": pendientes, "status": nuevo_status}


@frappe.whitelist()
def suggest_supplier_from_cfdi(cfdi_recibido: str) -> dict:
	"""
	Sugiere datos de proveedor basándose en el RFC del CFDI. No crea Supplier automáticamente.

	Casos de respuesta:
	  status="found"     — Supplier ya existe con tax_id == supplier_rfc
	  status="not_found" — No existe; retorna suggested_data para alta asistida
	  status="no_rfc"    — El CFDI no tiene RFC de proveedor

	Retorna:
	    status          — "found" | "not_found" | "no_rfc"
	    supplier_exists — bool
	    supplier        — nombre del Supplier encontrado (None si no existe)
	    message         — descripción del resultado
	    suggested_data  — dict con datos sugeridos para alta manual
	"""
	if not cfdi_recibido:
		frappe.throw(_("El campo 'cfdi_recibido' es obligatorio"), frappe.MandatoryError)

	doc = frappe.get_doc("CFDI Recibido", cfdi_recibido)
	supplier_rfc = doc.supplier_rfc or ""

	if not supplier_rfc:
		return {
			"status": "no_rfc",
			"supplier_exists": False,
			"supplier": None,
			"message": _("El CFDI no tiene RFC de proveedor"),
			"suggested_data": {},
		}

	existing = frappe.db.get_value(
		"Supplier",
		{"tax_id": supplier_rfc},
		["name", "supplier_name", "tax_id"],
		as_dict=True,
	)

	if existing:
		return {
			"status": "found",
			"supplier_exists": True,
			"supplier": existing.name,
			"message": _("Proveedor encontrado: {0} ({1})").format(existing.supplier_name, supplier_rfc),
			"suggested_data": {
				"supplier_name": existing.supplier_name,
				"tax_id": existing.tax_id,
			},
		}

	return {
		"status": "not_found",
		"supplier_exists": False,
		"supplier": None,
		"message": _("No existe Supplier con RFC {0}").format(supplier_rfc),
		"suggested_data": {
			"supplier_name": doc.supplier_name or supplier_rfc,
			"tax_id": supplier_rfc,
			"tax_regime": doc.supplier_tax_regime or "",
		},
	}
