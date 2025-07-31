# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Customer Addenda Custom Fields - MIGRATED TO FIXTURES

IMPORTANT: Custom field creation functions have been removed as part of Issue #31 critical migration.
Custom fields are now managed exclusively through fixtures in hooks.py following Frappe best practices.

REMOVED FUNCTIONS:
- create_customer_addenda_fields() - now replaced by fixtures

MIGRATION COMPLETED: 2025-07-31
All custom fields are now automatically created during installation via fixtures mechanism.
"""

import frappe
from frappe import _


def get_customer_addenda_fields_info():
	"""
	Information function about customer addenda fields management.
	Returns info about the fixtures-based approach.
	"""
	return {
		"status": "MIGRATED_TO_FIXTURES",
		"migration_date": "2025-07-31",
		"issue": "#31",
		"doctype": "Customer",
		"fields_created": [
			"fm_addenda_section",
			"fm_requires_addenda",
			"fm_addenda_type",
			"fm_addenda_defaults",
			"fm_addenda_auto_detected",
			"fm_addenda_validation_override",
		],
		"fixtures_location": "facturacion_mexico/hooks.py",
		"message": "Customer addenda fields are now managed via fixtures. No manual functions needed.",
	}


# Legacy removal function kept for development/testing purposes
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
def get_addenda_fields_status():
	"""API para obtener información sobre campos de addenda"""
	return get_customer_addenda_fields_info()


@frappe.whitelist()
def remove_addenda_fields():
	"""API para remover custom fields de addenda (solo para testing)"""
	return remove_customer_addenda_fields()
