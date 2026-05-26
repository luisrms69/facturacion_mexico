"""
SupplierResolver — resuelve el proveedor de un CFDI Recibido por RFC.

Busca Supplier donde tax_id == supplier_rfc del CFDI.
No autocrea proveedores.
"""

import frappe

from facturacion_mexico.cfdi_recibidos.services.status_manager import compute_supplier_stage


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
