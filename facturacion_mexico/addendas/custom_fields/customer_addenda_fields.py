# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Customer Addenda Custom Fields - Sprint 6 Phase 3
Custom fields para gestión de addendas genéricas por cliente
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def create_customer_addenda_fields():
	"""Crear custom fields para addendas en Customer"""

	custom_fields = {
		"Customer": [
			{
				"fieldname": "fm_addenda_section",
				"fieldtype": "Section Break",
				"label": "Configuración de Addendas",
				"insert_after": "fm_rfc",
				"collapsible": 1,
			},
			{
				"fieldname": "fm_requires_addenda",
				"fieldtype": "Check",
				"label": "Requiere Addenda",
				"insert_after": "fm_addenda_section",
				"description": "Marcar si este cliente requiere addenda en sus facturas",
			},
			{
				"fieldname": "fm_addenda_type",
				"fieldtype": "Link",
				"label": "Tipo de Addenda",
				"options": "Addenda Type",
				"insert_after": "fm_requires_addenda",
				"depends_on": "eval:doc.fm_requires_addenda",
				"mandatory_depends_on": "eval:doc.fm_requires_addenda",
			},
			{
				"fieldname": "fm_addenda_defaults",
				"fieldtype": "Code",
				"label": "Valores Por Defecto (JSON)",
				"options": "JSON",
				"insert_after": "fm_addenda_type",
				"depends_on": "eval:doc.fm_requires_addenda",
				"description": "Valores por defecto en formato JSON para campos de la addenda",
			},
			{
				"fieldname": "fm_addenda_auto_detected",
				"fieldtype": "Check",
				"label": "Auto-detectado",
				"insert_after": "fm_addenda_defaults",
				"depends_on": "eval:doc.fm_requires_addenda",
				"read_only": 1,
				"description": "Campo automático - indica si fue detectado por el sistema",
			},
			{
				"fieldname": "fm_addenda_validation_override",
				"fieldtype": "Check",
				"label": "Omitir Validaciones",
				"insert_after": "fm_addenda_auto_detected",
				"depends_on": "eval:doc.fm_requires_addenda",
				"description": "Permitir generar factura aunque falten campos de addenda",
			},
		]
	}

	try:
		create_custom_fields(custom_fields, update=True)
		frappe.db.commit()
		return {"success": True, "message": "Custom fields de addenda creados exitosamente"}
	except Exception as e:
		frappe.log_error(f"Error creando custom fields de addenda: {e!s}", "Customer Addenda Fields")
		return {"success": False, "message": f"Error: {e!s}"}


def remove_customer_addenda_fields():
	"""Remover custom fields de addendas (para desarrollo/testing)"""

	field_names = [
		"fm_addenda_section",
		"fm_requires_addenda",
		"fm_addenda_type",
		"fm_addenda_defaults",
		"fm_addenda_auto_detected",
		"fm_addenda_validation_override",
	]

	try:
		for field_name in field_names:
			frappe.db.sql(
				"""
                DELETE FROM `tabCustom Field`
                WHERE dt = 'Customer' AND fieldname = %s
            """,
				field_name,
			)

		frappe.db.commit()
		frappe.clear_cache()
		return {"success": True, "message": "Custom fields de addenda removidos exitosamente"}
	except Exception as e:
		frappe.log_error(f"Error removiendo custom fields de addenda: {e!s}", "Customer Addenda Fields")
		return {"success": False, "message": f"Error: {e!s}"}


# API endpoints
@frappe.whitelist()
def setup_customer_addenda_fields():
	"""API para crear custom fields de addenda"""
	return create_customer_addenda_fields()


@frappe.whitelist()
def remove_addenda_fields():
	"""API para remover custom fields de addenda"""
	return remove_customer_addenda_fields()
