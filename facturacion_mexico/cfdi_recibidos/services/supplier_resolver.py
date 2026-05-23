"""
SupplierResolver — resuelve el proveedor de un CFDI Recibido por RFC.

Busca Supplier donde tax_id == supplier_rfc del CFDI.
No autocrea proveedores.
"""

import frappe


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

	doc.db_set("status", "Falta proveedor")
	return _result("falta_proveedor", None, f"No existe Supplier con RFC {doc.supplier_rfc}")


def _assign_supplier(doc, supplier_name: str, manual: bool) -> dict:
	"""Asigna el proveedor y avanza el estado del CFDI."""
	if not frappe.db.exists("Supplier", supplier_name):
		return _result("error", None, f"Proveedor {supplier_name} no existe")

	doc.db_set("supplier", supplier_name)

	# Advance status: check if concepts need classification next
	current_status = frappe.db.get_value("CFDI Recibido", doc.name, "status")
	if current_status in ("Falta proveedor", "Cargado", "Parseado"):
		doc.db_set("status", "Parseado")

	source = "manual" if manual else "RFC"
	return _result("ok", supplier_name, f"Proveedor asignado por {source}")


def _result(status: str, supplier: str | None, message: str) -> dict:
	return {"status": status, "supplier": supplier, "message": message}
