"""
API pública de CFDI Recibidos.

Endpoints Fase 1:
    upload_xml       — carga uno o varios XMLs CFDI y los persiste como CFDI Recibido.

Endpoints Fase 2:
    resolve_supplier  — asigna proveedor por RFC o vinculación manual.
    classify_concepts — aplica CFDI Concepto Mapping sobre conceptos del CFDI.
    save_mapping_rule — crea o actualiza una regla de clasificación.
"""

import frappe
from frappe import _

from facturacion_mexico.cfdi_recibidos.services.xml_ingestion import ingest_xml


@frappe.whitelist()
def upload_xml(company: str) -> list[dict]:
	"""
	Carga uno o varios XMLs CFDI 4.0 y los procesa como CFDI Recibido.

	Parámetros (form-data):
	    company   — nombre de la empresa en ERPNext
	    files     — uno o más archivos XML (campo "files" o "file")

	Retorna lista de resultados por archivo:
	    file_name     — nombre del archivo recibido
	    status        — "ok" | "duplicado" | "error"
	    cfdi_recibido — nombre del doc creado (None si duplicado sin doc nuevo)
	    uuid          — UUID extraído del XML
	    message       — descripción del resultado
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
	  - Listo: todos los conceptos tienen regla aplicable
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
