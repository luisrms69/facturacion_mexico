"""
fiscal_state/api.py

Endpoint único para obtener el estado fiscal de cualquier doctype soportado.
Read-only — no modifica ningún documento.
"""

import frappe
from frappe import _


@frappe.whitelist()
def get_fiscal_ui_state(doctype: str, name: str) -> dict:
	"""
	Retorna el estado fiscal centralizado para un documento.

	Args:
		doctype: DocType del documento (ej. "Payment Entry")
		name: Nombre del documento

	Returns:
		dict con facts, actions y messages para consumo de la UI.

	Raises:
		frappe.PermissionError: Si el usuario no tiene permiso de lectura.
		frappe.DoesNotExistError: Si el documento no existe.
		NotImplementedError: Si el doctype no está soportado aún.
	"""
	if not frappe.has_permission(doctype, "read", name):
		frappe.throw(_("Sin permisos para leer {0}: {1}").format(doctype, name), frappe.PermissionError)

	if doctype == "Payment Entry":
		from facturacion_mexico.fiscal_state.payment_entry_state import (
			get_payment_entry_fiscal_state,
		)

		return get_payment_entry_fiscal_state(name)

	if doctype == "Sales Invoice":
		from facturacion_mexico.fiscal_state.sales_invoice_state import (
			get_sales_invoice_fiscal_state,
		)

		return get_sales_invoice_fiscal_state(name)

	if doctype == "Factura Fiscal Mexico":
		from facturacion_mexico.fiscal_state.ffm_state import get_ffm_fiscal_state

		return get_ffm_fiscal_state(name)

	if doctype == "Complemento Pago MX":
		from facturacion_mexico.fiscal_state.complemento_state import get_complemento_fiscal_state

		return get_complemento_fiscal_state(name)

	frappe.throw(
		_("fiscal_state: doctype '{0}' no está soportado aún.").format(doctype),
		title=_("No implementado"),
	)
