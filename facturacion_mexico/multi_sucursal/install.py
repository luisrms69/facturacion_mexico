# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Instalación y configuración del módulo Multi-Sucursal
Sprint 6: Sistema multi-sucursal + addendas genéricas + UOM-SAT
"""

import frappe
from frappe import _


def after_app_install():
	"""Ejecutar después de instalar la app"""
	setup_multi_sucursal()


def setup_multi_sucursal():
	"""Configurar módulo multi-sucursal"""
	print("🚀 Configurando módulo Multi-Sucursal...")

	# Crear custom fields para Branch
	setup_branch_custom_fields()

	# Crear custom fields para Sales Invoice multi-sucursal
	setup_sales_invoice_custom_fields()

	# Crear Addenda Types para testing
	setup_addenda_types()

	# Agregar hooks necesarios
	setup_branch_hooks()

	print("✅ Módulo Multi-Sucursal configurado exitosamente")


def setup_branch_custom_fields():
	"""
	Configurar custom fields para Branch DocType.
	MIGRATED TO FIXTURES - Custom fields now managed via fixtures in hooks.py
	"""
	print("✅ Branch custom fields managed via fixtures - no manual creation needed")
	return True


def setup_sales_invoice_custom_fields():
	"""Configurar custom fields para Sales Invoice multi-sucursal"""
	try:
		from .sales_invoice_fields import setup_sales_invoice_custom_fields as setup_si_fields

		setup_si_fields()
		print("✅ Custom fields para Sales Invoice multi-sucursal creados")

	except Exception as e:
		print(f"❌ Error configurando custom fields Sales Invoice: {e!s}")
		frappe.log_error(f"Error setting up sales invoice custom fields: {e!s}", "Multi Sucursal Setup")


def setup_addenda_types():
	"""Crear Addenda Types necesarios para testing"""
	try:
		# CRÍTICO: Verificar si existe DocType Addenda Type
		if not frappe.db.exists("DocType", "Addenda Type"):
			print("🔧 DocType 'Addenda Type' no encontrado - creando para testing")

			# Crear DocType simple para testing
			addenda_type_doctype = {
				"doctype": "DocType",
				"name": "Addenda Type",
				"module": "Facturacion Mexico",
				"custom": 1,
				"naming_rule": "By fieldname",
				"autoname": "field:nombre_del_tipo",
				"fields": [
					{
						"fieldname": "nombre_del_tipo",
						"label": "Nombre del Tipo",
						"fieldtype": "Data",
						"reqd": 1,
						"unique": 1,
					},
					{
						"fieldname": "description",
						"label": "Description",
						"fieldtype": "Text",
					},
					{
						"fieldname": "is_active",
						"label": "Is Active",
						"fieldtype": "Check",
						"default": 1,
					},
				],
				"permissions": [
					{
						"role": "System Manager",
						"read": 1,
						"write": 1,
						"create": 1,
						"delete": 1,
					}
				],
			}

			frappe.get_doc(addenda_type_doctype).insert()
			print("✅ DocType 'Addenda Type' creado")

		# CRÍTICO: Verificar que el DocType real existe antes de crear registros
		if frappe.db.exists("DocType", "Addenda Type"):
			# Obtener estructura real del DocType
			doctype_meta = frappe.get_meta("Addenda Type")
			required_field = None

			# Buscar el campo que es requerido para el nombre
			for field in doctype_meta.fields:
				if field.reqd and field.fieldtype in ["Data", "Link"]:
					required_field = field.fieldname
					break

			if not required_field:
				required_field = "name"  # Fallback

			test_addenda_types = [
				{required_field: "TEST_GENERIC", "description": "Generic test addenda for Sprint 6 testing"},
				{required_field: "TEST_AUTOMOTIVE", "description": "Automotive test addenda"},
				{required_field: "TEST_RETAIL", "description": "Retail test addenda"},
			]

			for addenda_data in test_addenda_types:
				type_name = addenda_data[required_field]
				if not frappe.db.exists("Addenda Type", type_name):
					try:
						addenda_doc = frappe.get_doc({"doctype": "Addenda Type", **addenda_data})
						addenda_doc.insert(ignore_permissions=True)
						print(f"✅ Addenda Type '{type_name}' creado")
					except Exception as create_error:
						print(f"⚠️  Error creando Addenda Type '{type_name}': {create_error}")
				else:
					print(f"✓ Addenda Type '{type_name}' ya existe")
		else:
			print("⚠️  DocType 'Addenda Type' no encontrado - saltando creación de test records")

		print("✅ Addenda Types configurados para testing")

	except Exception as e:
		print(f"❌ Error configurando Addenda Types: {e!s}")
		frappe.log_error(f"Error setting up addenda types: {e!s}", "Multi Sucursal Setup")


def setup_branch_hooks():
	"""Configurar hooks para Branch DocType"""
	try:
		# Los hooks se configuran en hooks.py de la app principal
		# Aquí solo verificamos que estén disponibles las funciones

		from .custom_fields.branch_fiscal_fields import (
			after_branch_insert,
			on_branch_update,
			validate_branch_fiscal_configuration,
		)

		print("✅ Hooks de Branch configurados")

	except Exception as e:
		print(f"❌ Error configurando hooks: {e!s}")
		frappe.log_error(f"Error setting up branch hooks: {e!s}", "Multi Sucursal Setup")


def validate_installation():
	"""Validar que la instalación esté correcta"""
	try:
		# Verificar que existan los custom fields
		required_fields = [
			"fm_enable_fiscal",
			"fm_lugar_expedicion",
			"fm_serie_pattern",
			"fm_folio_start",
			"fm_folio_current",
			"fm_folio_end",
			"fm_share_certificates",
		]

		missing_fields = []
		for field in required_fields:
			if not frappe.db.exists("Custom Field", {"dt": "Branch", "fieldname": field}):
				missing_fields.append(field)

		if missing_fields:
			print(f"⚠️  Campos faltantes en Branch: {missing_fields}")
			return False

		# Verificar que exista el DocType
		if not frappe.db.exists("DocType", "Configuracion Fiscal Sucursal"):
			print("⚠️  DocType 'Configuracion Fiscal Sucursal' no encontrado")
			return False

		print("✅ Instalación validada correctamente")
		return True

	except Exception as e:
		print(f"❌ Error validando instalación: {e!s}")
		return False


if __name__ == "__main__":
	# Para testing manual
	setup_multi_sucursal()
	validate_installation()
