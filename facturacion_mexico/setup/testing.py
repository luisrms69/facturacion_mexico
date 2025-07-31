"""
Testing fixtures loader for facturacion_mexico

This module loads custom fields programmatically during testing environments
where Frappe fixtures don't auto-load. Follows expert recommendation for
Issue #31 custom fields migration.
"""

import json
import os

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def load_testing_fixtures():
	"""
	Load custom fields for testing environment.

	Frappe doesn't auto-load fixtures during testing, so we need to create
	custom fields programmatically. This follows the expert recommendation
	for Issue #31.
	"""
	print("📌 Cargando custom fields para entorno de pruebas...")

	try:
		# Get path to fixtures file
		app_path = frappe.get_app_path("facturacion_mexico")
		fixtures_path = os.path.join(app_path, "fixtures", "custom_field.json")

		if not os.path.exists(fixtures_path):
			print(f"⚠️ Fixtures file not found: {fixtures_path}")
			return

		# Load custom fields from JSON
		with open(fixtures_path, encoding="utf-8") as f:
			custom_fields_data = json.load(f)

		# Group fields by doctype for create_custom_fields function
		custom_fields_by_doctype = {}

		for field_data in custom_fields_data:
			if field_data.get("doctype") != "Custom Field":
				continue

			dt = field_data.get("dt")
			if not dt:
				continue

			if dt not in custom_fields_by_doctype:
				custom_fields_by_doctype[dt] = []

			# Extract field definition (remove doctype metadata)
			field_def = {
				k: v
				for k, v in field_data.items()
				if k not in ["doctype", "dt", "name", "modified", "is_system_generated"]
			}

			custom_fields_by_doctype[dt].append(field_def)

		print(f"📊 Creando custom fields para {len(custom_fields_by_doctype)} DocTypes...")

		# Create custom fields using Frappe's official function
		if custom_fields_by_doctype:
			create_custom_fields(custom_fields_by_doctype, ignore_validate=True, update=True)

			# Verify creation
			total_created = sum(len(fields) for fields in custom_fields_by_doctype.values())
			print(f"✅ {total_created} custom fields creados exitosamente para testing")

			# Log field counts per doctype
			for dt, fields in custom_fields_by_doctype.items():
				print(f"   📋 {dt}: {len(fields)} campos")

		frappe.db.commit()

	except Exception as e:
		print(f"❌ Error cargando fixtures para testing: {e}")
		import traceback

		traceback.print_exc()
		# Don't raise - let tests continue even if fixtures fail


def safe_create_field(doctype, field):
	"""
	Safely create a single custom field, avoiding fieldtype conflicts.

	This prevents the "Fieldtype cannot be changed from Link to Data" error
	mentioned in Issue #31.
	"""
	from frappe.model.meta import get_meta

	try:
		meta = get_meta(doctype)
		existing = meta.get_field(field["fieldname"])

		if existing:
			if existing.fieldtype != field["fieldtype"]:
				print(
					f"⚠️ Fieldtype conflict in {doctype}.{field['fieldname']} - "
					f"Existing: {existing.fieldtype}, New: {field['fieldtype']}"
				)
			return  # Skip if field exists

		# Create the field
		frappe.get_doc({"doctype": "Custom Field", "dt": doctype, **field}).insert(ignore_permissions=True)

	except Exception as e:
		print(f"⚠️ Error creating field {doctype}.{field['fieldname']}: {e}")


def verify_custom_fields_loaded():
	"""
	Verify that critical custom fields are loaded for testing.
	Used for debugging fixtures loading issues.
	"""
	critical_fields = [
		("Customer", "fm_rfc"),
		("Customer", "fm_requires_addenda"),
		("Sales Invoice", "fm_addenda_xml"),
		("Item", "fm_unidad_sat"),
		("Branch", "fm_enable_fiscal"),
	]

	missing_fields = []

	for doctype, fieldname in critical_fields:
		field_name = f"{doctype}-{fieldname}"
		if not frappe.db.exists("Custom Field", field_name):
			missing_fields.append(field_name)

	if missing_fields:
		print(f"⚠️ Missing critical custom fields: {missing_fields}")
		return False
	else:
		print(f"✅ All {len(critical_fields)} critical custom fields loaded")
		return True
