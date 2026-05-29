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

Endpoints Motor de Resolución de Items:
    get_item_resolution_options        — propone opciones de Item para un concepto.
    assign_item_to_concepto            — confirma la asignación de Item a un concepto.
    create_specific_item_from_concepto — crea Item específico y lo asigna.
    create_grouping_item_from_concepto — crea Item agrupador y lo asigna.
    assign_generic_item_to_concepto    — asigna Item genérico GASTO-* al concepto.
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
	Auto-asigna Items a conceptos sin item_code, exclusivamente por coincidencia
	no_identificacion del proveedor ↔ item_code existente en el sistema.

	Cualquier otra resolución (Reglas configuradas, texto, genérico) requiere
	decisión explícita del usuario a través del botón "Resolver Items pendientes".

	Rechaza ítems que no pasen validate_expense_item.
	Actualiza status con compute_stage tras las asignaciones.

	Retorna: {auto_clasificados, pendientes, status}
	"""
	from facturacion_mexico.cfdi_recibidos.services.item_resolution_engine import (
		get_resolution_options,
	)
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

	auto_clasificados = 0
	pendientes = 0

	for concepto in doc.conceptos or []:
		if concepto.item_code:
			continue

		opts = get_resolution_options(
			{
				"sat_product_key": concepto.sat_product_key or "",
				"no_identificacion": concepto.no_identificacion or "",
				"description": concepto.description or "",
				"item_group": concepto.item_group or "",
			},
			{
				"company": doc.company,
				"supplier": doc.supplier or "",
				"supplier_rfc": doc.supplier_rfc or "",
			},
		)

		primary = opts.get("primary")
		# Auto-asignación solo por coincidencia exacta no_identificacion ↔ item_code.
		# Reglas configuradas (Mapeado) y texto (Sugerido) requieren decisión explícita del usuario.
		if not primary or primary["item_resolution"] != "Código proveedor":
			pendientes += 1
			continue

		ok, _reason = validate_expense_item(primary["item_code"])
		if not ok:
			pendientes += 1
			continue

		item_group = frappe.db.get_value("Item", primary["item_code"], "item_group") or ""
		frappe.db.set_value(
			"CFDI Recibido Concepto",
			concepto.name,
			{
				"item_code": primary["item_code"],
				"item_resolution": primary["item_resolution"],
				"item_group": item_group,
				"item_match_reason": primary["match_reason"],
				"item_match_confidence": primary["match_confidence"],
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


# ---------------------------------------------------------------------------
# Motor de resolución de Items
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_item_resolution_options(cfdi_recibido: str, concepto_name: str) -> dict:
	"""
	Propone opciones de Item para un concepto específico usando el motor de resolución.

	Retorna: {primary, alternatives, generic, can_create}
	Cada opción incluye: item_code, item_name, item_group,
	                     item_resolution, match_reason, match_confidence
	"""
	from facturacion_mexico.cfdi_recibidos.services.item_resolution_engine import (
		get_resolution_options,
	)

	if not cfdi_recibido or not concepto_name:
		frappe.throw(_("cfdi_recibido y concepto_name son obligatorios"), frappe.MandatoryError)

	doc = frappe.get_doc("CFDI Recibido", cfdi_recibido)
	concepto = next((c for c in doc.conceptos if c.name == concepto_name), None)
	if not concepto:
		frappe.throw(
			_("Concepto {0} no encontrado en {1}").format(concepto_name, cfdi_recibido),
			frappe.DoesNotExistError,
		)

	return get_resolution_options(
		{
			"sat_product_key": concepto.sat_product_key or "",
			"no_identificacion": concepto.no_identificacion or "",
			"description": concepto.description or "",
			"item_group": concepto.item_group or "",
		},
		{
			"company": doc.company,
			"supplier": doc.supplier or "",
			"supplier_rfc": doc.supplier_rfc or "",
		},
	)


@frappe.whitelist()
def assign_item_to_concepto(
	concepto_name: str,
	item_code: str,
	item_resolution: str,
	match_reason: str = "",
	match_confidence: str = "Alta",
) -> dict:
	"""
	Confirma la asignación de un Item a un concepto CFDI Recibido.

	Actualiza item_code, item_resolution, item_match_reason, item_match_confidence,
	item_group en el concepto. Recalcula status del CFDI padre.

	Retorna: {status, concepto_name, item_code, cfdi_status}
	"""
	from facturacion_mexico.cfdi_recibidos.services.status_manager import compute_stage

	if not concepto_name or not item_code:
		frappe.throw(_("concepto_name e item_code son obligatorios"), frappe.MandatoryError)

	concepto_doc = frappe.get_doc("CFDI Recibido Concepto", concepto_name)
	item_group = frappe.db.get_value("Item", item_code, "item_group") or ""

	frappe.db.set_value(
		"CFDI Recibido Concepto",
		concepto_name,
		{
			"item_code": item_code,
			"item_resolution": item_resolution,
			"item_group": item_group,
			"item_match_reason": match_reason,
			"item_match_confidence": match_confidence,
		},
	)

	cfdi_name = concepto_doc.parent
	cfdi_doc = frappe.get_doc("CFDI Recibido", cfdi_name)
	nuevo_status = compute_stage(cfdi_doc)
	frappe.db.set_value("CFDI Recibido", cfdi_name, "status", nuevo_status)

	# Auto-crear Regla si hay no_identificacion — para recordar esta asignación
	if concepto_doc.no_identificacion and not item_code.startswith("GASTO-"):
		_auto_create_regla(
			cfdi_doc.supplier_rfc or "",
			concepto_doc.no_identificacion,
			item_code,
		)

	frappe.db.commit()

	return {
		"status": "ok",
		"concepto_name": concepto_name,
		"item_code": item_code,
		"cfdi_status": nuevo_status,
	}


@frappe.whitelist()
def create_specific_item_from_concepto(
	cfdi_recibido: str,
	concepto_name: str,
	item_code: str,
	item_name: str,
	item_group_name: str,
) -> dict:
	"""
	Crea un Item específico de gasto y lo asigna al concepto.

	El item se crea con is_purchase_item=1, is_stock_item=0, is_sales_item=0.
	La UOM se deriva de unit_key del concepto; por defecto "H87 - Pieza".

	Retorna: {status, item_code}
	"""
	return _create_item_and_assign(
		cfdi_recibido=cfdi_recibido,
		concepto_name=concepto_name,
		item_code=item_code,
		item_name=item_name,
		item_group_name=item_group_name,
		item_resolution="Nuevo especifico",
	)


@frappe.whitelist()
def create_grouping_item_from_concepto(
	cfdi_recibido: str,
	concepto_name: str,
	item_code: str,
	item_name: str,
	item_group_name: str,
) -> dict:
	"""
	Crea un Item agrupador de gasto y lo asigna al concepto.

	Mismo proceso que create_specific_item pero con item_resolution="Nuevo agrupador".
	Útil para crear ítems genéricos de una categoría nueva.

	Retorna: {status, item_code}
	"""
	return _create_item_and_assign(
		cfdi_recibido=cfdi_recibido,
		concepto_name=concepto_name,
		item_code=item_code,
		item_name=item_name,
		item_group_name=item_group_name,
		item_resolution="Nuevo agrupador",
	)


@frappe.whitelist()
def assign_generic_item_to_concepto(cfdi_recibido: str, concepto_name: str) -> dict:
	"""
	Asigna el Item genérico GASTO-* del item_group del concepto.

	Requiere que el concepto tenga item_group asignado y que exista
	exactamente un GASTO-* en ese grupo.

	Retorna: {status, item_code} o {status="not_found", item_code=None}
	"""
	from facturacion_mexico.cfdi_recibidos.services.item_resolution_engine import _resolve_generic

	if not cfdi_recibido or not concepto_name:
		frappe.throw(_("cfdi_recibido y concepto_name son obligatorios"), frappe.MandatoryError)

	doc = frappe.get_doc("CFDI Recibido", cfdi_recibido)
	concepto = next((c for c in doc.conceptos if c.name == concepto_name), None)
	if not concepto:
		frappe.throw(
			_("Concepto {0} no encontrado en {1}").format(concepto_name, cfdi_recibido),
			frappe.DoesNotExistError,
		)

	item_group = concepto.item_group or ""
	generic = _resolve_generic(item_group, set())

	if not generic:
		return {
			"status": "not_found",
			"item_code": None,
			"message": _("No hay Item genérico GASTO-* para el grupo '{0}'").format(item_group),
		}

	result = assign_item_to_concepto(
		concepto_name=concepto_name,
		item_code=generic["item_code"],
		item_resolution="Generico",
		match_reason=generic["match_reason"],
		match_confidence="Baja",
	)
	return {**result, "message": _("Item genérico asignado: {0}").format(generic["item_code"])}


# ---------------------------------------------------------------------------
# Helpers internos — creación de ítems
# ---------------------------------------------------------------------------


def _create_item_and_assign(
	cfdi_recibido: str,
	concepto_name: str,
	item_code: str,
	item_name: str,
	item_group_name: str,
	item_resolution: str,
) -> dict:
	"""Crea un Item de gasto y lo asigna al concepto."""
	from facturacion_mexico.cfdi_recibidos.services.item_validator import validate_expense_item

	if not all([cfdi_recibido, concepto_name, item_code, item_name, item_group_name]):
		frappe.throw(_("Todos los campos son obligatorios"), frappe.MandatoryError)

	if frappe.db.exists("Item", item_code):
		frappe.throw(
			_("Ya existe un Item con código '{0}'").format(item_code),
			frappe.DuplicateEntryError,
		)

	# Derivar UOM desde unit_key del concepto
	doc_cfdi = frappe.get_doc("CFDI Recibido", cfdi_recibido)
	concepto = next((c for c in doc_cfdi.conceptos if c.name == concepto_name), None)
	if not concepto:
		frappe.throw(
			_("Concepto {0} no encontrado en {1}").format(concepto_name, cfdi_recibido),
			frappe.DoesNotExistError,
		)

	uom = _uom_from_unit_key(concepto.unit_key or "")
	company = doc_cfdi.company

	item = frappe.new_doc("Item")
	item.item_code = item_code
	item.item_name = item_name
	item.item_group = item_group_name
	item.is_stock_item = 0
	item.is_purchase_item = 1
	item.is_sales_item = 0
	item.stock_uom = uom
	item.append("uoms", {"uom": uom, "conversion_factor": 1})

	expense_account = frappe.db.get_value(
		"Account",
		{"account_type": "Expense Account", "company": company, "is_group": 0},
		"name",
	)
	if expense_account:
		item.append(
			"item_defaults",
			{"company": company, "expense_account": expense_account, "default_warehouse": ""},
		)

	item.flags.ignore_validate = True
	item.insert(ignore_permissions=True)
	frappe.db.commit()

	ok, reason = validate_expense_item(item_code)
	if not ok:
		frappe.delete_doc("Item", item_code, force=True)
		frappe.db.commit()
		frappe.throw(
			_("El Item creado no pasa la validación de gasto: {0}").format(reason),
			frappe.ValidationError,
		)

	assign_item_to_concepto(
		concepto_name=concepto_name,
		item_code=item_code,
		item_resolution=item_resolution,
		match_reason=f"Creado desde concepto: {concepto.description or item_name}",
		match_confidence="Alta",
	)

	return {"status": "ok", "item_code": item_code}


def _uom_from_unit_key(unit_key: str) -> str:
	"""Devuelve el nombre completo de la UOM SAT desde la clave de unidad del CFDI."""
	from facturacion_mexico.cfdi_recibidos.services.uom_policy import SAT_UOMS

	if not unit_key:
		return "H87 - Pieza"
	for uom in SAT_UOMS:
		if uom.startswith(unit_key + " - "):
			return uom
	return "H87 - Pieza"


@frappe.whitelist()
def get_next_item_code_for_group(item_group: str) -> str:
	"""
	Genera el próximo item_code disponible para un grupo de gasto.
	Formato: {SLUG}-{NNN}, ej. PAPELERIA-001, COMBUSTIBLE-003.
	"""
	import unicodedata

	if not item_group:
		return ""

	# Slug: primera palabra del grupo, sin acentos, uppercase, max 12 chars
	clean = unicodedata.normalize("NFD", item_group)
	clean = "".join(c for c in clean if unicodedata.category(c) != "Mn")
	first_word = clean.strip().split()[0].upper()[:12]
	slug = "".join(c for c in first_word if c.isalnum())
	if not slug:
		slug = "GASTO"

	# Contar ítems existentes con ese prefijo para determinar consecutivo
	existing = frappe.get_all(
		"Item",
		filters={"item_code": ["like", f"{slug}-%"]},
		pluck="item_code",
	)
	# Extraer números para encontrar el máximo
	max_num = 0
	for code in existing:
		suffix = code[len(slug) + 1 :]
		if suffix.isdigit():
			max_num = max(max_num, int(suffix))
	return f"{slug}-{max_num + 1:03d}"


def _auto_create_regla(supplier_rfc: str, no_identificacion: str, item_code: str) -> None:
	"""Crea una Regla Item CFDI Recibido para recordar la asignación proveedor+no_identificacion."""
	if not supplier_rfc or not no_identificacion or not item_code:
		return
	existing = frappe.db.exists(
		"Regla Item CFDI Recibido",
		{"supplier_rfc": supplier_rfc, "keywords": no_identificacion, "target_item": item_code},
	)
	if existing:
		return
	rule = frappe.new_doc("Regla Item CFDI Recibido")
	rule.supplier_rfc = supplier_rfc
	rule.keywords = no_identificacion
	rule.target_item = item_code
	rule.match_reason = f"Auto: {supplier_rfc} / {no_identificacion}"
	rule.priority = 5
	rule.is_active = 1
	rule.insert(ignore_permissions=True)
