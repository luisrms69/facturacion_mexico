# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Eliminar campo fm_fiscal_attempts de Sales Invoice - funcionalidad duplicada."""
	try:
		fieldname = "fm_fiscal_attempts"
		doctype = "Sales Invoice"
		field_id = f"{doctype}-{fieldname}"

		if frappe.db.exists("Custom Field", field_id):
			frappe.logger().info(f"Eliminando Custom Field: {field_id}")
			frappe.delete_doc("Custom Field", field_id, force=True)
			frappe.logger().info(f"✅ Custom Field {field_id} eliminado exitosamente")
		else:
			frappe.logger().info(f"Custom Field {field_id} no existe - ya eliminado")

	except Exception as e:
		frappe.logger().error(f"❌ Error eliminando Custom Field fm_fiscal_attempts: {e!s}")
		# No fallar la migración por este error
