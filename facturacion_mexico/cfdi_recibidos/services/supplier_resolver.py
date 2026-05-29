"""
SupplierResolver — resuelve y genera proveedores para CFDI Recibidos.

resolve_supplier(cfdi_recibido_name, supplier_override=None)
    Asigna Supplier a un CFDI por RFC o vinculación manual. No autocrea.

generate_missing_suppliers(cfdi_names=None)
    Crea Suppliers en lote para CFDIs en estado "Falta proveedor".
    Idempotente: si el Supplier ya existe por RFC, lo asigna sin duplicar.
    Retorna: {creados, ya_existian_y_asignados, omitidos, errores}
"""

import frappe

from facturacion_mexico.cfdi_recibidos.services.status_manager import (
	compute_stage,
	compute_supplier_stage,
)


def resolve_supplier(cfdi_recibido_name: str, supplier_override: str | None = None) -> dict:
	"""
	Intenta asignar el proveedor al CFDI Recibido.

	Si supplier_override se proporciona, usa ese Supplier directamente
	(vinculación manual desde UI aunque el RFC no coincida).
	Si no, busca por Supplier.tax_id == cfdi_recibido.supplier_rfc.

	Retorna: {status, supplier, message}
	"""
	doc = frappe.get_doc("CFDI Recibido", cfdi_recibido_name)

	if supplier_override:
		return _assign_supplier(doc, supplier_override, manual=True)

	if not doc.supplier_rfc:
		return _result("error", None, "El CFDI no tiene RFC de emisor")

	supplier = frappe.db.get_value("Supplier", {"tax_id": doc.supplier_rfc}, "name")

	if supplier:
		return _assign_supplier(doc, supplier, manual=False)

	stage = compute_supplier_stage(doc)
	doc.db_set("status", stage)
	return _result("falta_proveedor", None, f"No existe Supplier con RFC {doc.supplier_rfc}")


def _assign_supplier(doc, supplier_name: str, manual: bool) -> dict:
	"""Asigna el proveedor y recalcula la etapa del CFDI."""
	if not frappe.db.exists("Supplier", supplier_name):
		return _result("error", None, f"Proveedor {supplier_name} no existe")

	doc.db_set("supplier", supplier_name)
	doc.supplier = supplier_name

	stage = compute_supplier_stage(doc)
	doc.db_set("status", stage)

	source = "manual" if manual else "RFC"
	return _result("ok", supplier_name, f"Proveedor asignado por {source}")


def _result(status: str, supplier: str | None, message: str) -> dict:
	return {"status": status, "supplier": supplier, "message": message}


def generate_missing_suppliers(cfdi_names: list[str] | None = None) -> dict:
	"""
	Crea o asigna Supplier para CFDIs en estado 'Falta proveedor'.

	Si cfdi_names se provee, procesa solo esos documentos; los no candidatos
	van a omitidos. Sin cfdi_names, procesa todos los candidatos activos.
	Idempotente: dos ejecuciones no duplican Suppliers.
	Si Configuracion Fiscal Mexico tiene default_payment_terms_supplier, se asigna
	a proveedores nuevos. Los proveedores existentes no se modifican.
	"""
	creados = 0
	ya_existian_y_asignados = 0
	omitidos = 0
	errores = []

	candidate_filters = {
		"status": "Falta proveedor",
		"no_procesar": 0,
		"supplier_rfc": ["is", "set"],
		"supplier_name": ["is", "set"],
		"supplier": ["is", "not set"],
	}

	if cfdi_names:
		candidates = frappe.get_all(
			"CFDI Recibido",
			filters={**candidate_filters, "name": ["in", cfdi_names]},
			fields=["name", "supplier_rfc", "supplier_name", "company"],
		)
		candidate_set = {c.name for c in candidates}
		omitidos = sum(1 for n in cfdi_names if n not in candidate_set)
	else:
		candidates = frappe.get_all(
			"CFDI Recibido",
			filters=candidate_filters,
			fields=["name", "supplier_rfc", "supplier_name", "company"],
		)

	# Cache RFC → Supplier.name para evitar duplicados dentro del mismo lote
	rfc_to_supplier: dict[str, str] = {}
	# Cache company → payment_terms para evitar queries repetidas
	company_pt_cache: dict[str, str | None] = {}

	for cfdi in candidates:
		rfc = cfdi.supplier_rfc
		company = cfdi.company
		try:
			# Primero buscar en cache del lote, luego en BD
			existing = rfc_to_supplier.get(rfc) or frappe.db.get_value("Supplier", {"tax_id": rfc}, "name")
			if existing:
				rfc_to_supplier[rfc] = existing
				frappe.db.set_value(
					"CFDI Recibido",
					cfdi.name,
					{"supplier": existing, "status": "Proveedor encontrado"},
				)
				ya_existian_y_asignados += 1
				continue

			supplier_group = _get_default_supplier_group()
			if not supplier_group:
				errores.append(
					{
						"name": cfdi.name,
						"message": "No se encontró Supplier Group en ERPNext. Configure al menos un grupo de proveedores.",
					}
				)
				continue

			if company not in company_pt_cache:
				company_pt_cache[company] = _get_default_payment_terms(company)
			payment_terms = company_pt_cache[company]

			sup = frappe.new_doc("Supplier")
			sup.supplier_name = cfdi.supplier_name
			sup.supplier_group = supplier_group
			sup.supplier_type = "Company"
			sup.tax_id = rfc
			if payment_terms:
				sup.payment_terms = payment_terms
			sup.insert(ignore_permissions=True)

			rfc_to_supplier[rfc] = sup.name
			frappe.db.set_value(
				"CFDI Recibido",
				cfdi.name,
				{"supplier": sup.name, "status": "Proveedor encontrado"},
			)
			creados += 1

		except Exception as e:
			errores.append({"name": cfdi.name, "message": str(e)})

	return {
		"creados": creados,
		"ya_existian_y_asignados": ya_existian_y_asignados,
		"omitidos": omitidos,
		"errores": errores,
	}


def _get_default_supplier_group() -> str | None:
	"""
	Detecta el primer Supplier Group hoja (no raíz) disponible en ERPNext.
	Fallback: cualquier grupo si no hay hojas. None si no existe ninguno.
	"""
	group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
	if group:
		return group
	return frappe.db.get_value("Supplier Group", {}, "name")


def _get_default_payment_terms(company: str) -> str | None:
	"""
	Lee default_payment_terms_supplier de Configuracion CFDI Recibidos para la empresa.
	Retorna None si no existe la configuración o el campo está vacío.
	"""
	config_name = f"CFDI-REC-CFG-{company}"
	if not frappe.db.exists("Configuracion CFDI Recibidos", config_name):
		return None
	return (
		frappe.db.get_value(
			"Configuracion CFDI Recibidos",
			config_name,
			"default_payment_terms_supplier",
		)
		or None
	)
