# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Custom Fields Management - MIGRATED TO FIXTURES

IMPORTANT: All custom field creation functions have been removed as part of Issue #31 critical migration.
Custom fields are now managed exclusively through fixtures in hooks.py following Frappe best practices.

REMOVED FUNCTIONS (now replaced by fixtures):
- create_sales_invoice_custom_fields()
- create_customer_custom_fields()
- create_item_custom_fields()
- create_payment_entry_custom_fields()
- create_sales_invoice_sprint2_custom_fields()
- create_customer_sprint2_custom_fields()
- create_all_custom_fields()
- create_addenda_custom_fields()
- create_ereceipt_custom_fields()

MIGRATION COMPLETED: 2025-07-31
See: /home/erpnext/frappe-bench/apps/buzola-internal/projects/facturacion_mexico/ISSUE_31_CRITICAL_MIGRATION_PLAN.md

All custom fields are now automatically created during installation via fixtures mechanism.
No manual intervention required.

FRAPPE OFFICIAL RECOMMENDATION: Use fixtures for custom fields, not manual functions.
Per official documentation: fixtures are the recommended approach for managing custom fields.
"""

import frappe
from frappe import _

# Legacy imports kept for backward compatibility
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def get_custom_fields_info():
	"""
	Information function about custom fields management.
	Returns info about the fixtures-based approach.
	"""
	return {
		"status": "MIGRATED_TO_FIXTURES",
		"migration_date": "2025-07-31",
		"issue": "#31",
		"total_fields": 75,
		"doctypes_affected": ["Sales Invoice", "Customer", "Item", "Payment Entry", "Branch"],
		"fixtures_location": "facturacion_mexico/hooks.py",
		"manual_functions_removed": 10,
		"message": "All custom fields are now managed via fixtures. No manual functions needed.",
	}


# Keep this file for potential utility functions in the future
# All custom field creation is now handled by fixtures in hooks.py

# REMOVED: All manual custom field creation functions have been permanently removed
# as per Issue #31 critical migration. Frappe official documentation clearly states
# that fixtures are the recommended approach, not manual functions.
#
# Custom fields are now exclusively managed through fixtures in hooks.py
# and properly exported using 'bench export-fixtures' command.
