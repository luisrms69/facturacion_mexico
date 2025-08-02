# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Multi Sucursal Custom Fields
Campos personalizados para sistema multi-sucursal
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def get_custom_fields():
	"""Definir custom fields para sistema multi-sucursal"""

	custom_fields = {
		"Branch": [
			{
				"fieldname": "fm_fiscal_settings_section",
				"fieldtype": "Section Break",
				"label": "Configuración Fiscal",
				"insert_after": "disabled",
			},
			{
				"fieldname": "fm_enable_fiscal",
				"fieldtype": "Check",
				"label": "Habilitar Facturación",
				"description": "Activar esta sucursal para emisión de facturas",
				"insert_after": "fm_fiscal_settings_section",
				"default": 0,
			},
			{
				"fieldname": "fm_lugar_expedicion",
				"fieldtype": "Data",
				"label": "Lugar de Expedición",
				"description": "Código postal fiscal para esta sucursal",
				"insert_after": "fm_enable_fiscal",
				"depends_on": "eval:doc.fm_enable_fiscal",
			},
			{
				"fieldname": "fm_serie_pattern",
				"fieldtype": "Data",
				"label": "Patrón de Serie",
				"description": "Patrón para generar series (ej: SUC1-{yyyy})",
				"insert_after": "fm_lugar_expedicion",
				"depends_on": "eval:doc.fm_enable_fiscal",
			},
			{
				"fieldname": "fm_folio_column_break",
				"fieldtype": "Column Break",
				"insert_after": "fm_serie_pattern",
			},
			{
				"fieldname": "fm_folio_start",
				"fieldtype": "Int",
				"label": "Folio Inicial",
				"description": "Primer folio asignado a esta sucursal",
				"insert_after": "fm_folio_column_break",
				"depends_on": "eval:doc.fm_enable_fiscal",
				"default": 1,
			},
			{
				"fieldname": "fm_folio_current",
				"fieldtype": "Int",
				"label": "Folio Actual",
				"description": "Último folio utilizado",
				"insert_after": "fm_folio_start",
				"depends_on": "eval:doc.fm_enable_fiscal",
				"read_only": 1,
				"default": 1,
			},
			{
				"fieldname": "fm_folio_end",
				"fieldtype": "Int",
				"label": "Folio Final",
				"description": "Último folio disponible para esta sucursal",
				"insert_after": "fm_folio_current",
				"depends_on": "eval:doc.fm_enable_fiscal",
				"default": 1000,
			},
			{
				"fieldname": "fm_certificate_section",
				"fieldtype": "Section Break",
				"label": "Certificados",
				"insert_after": "fm_folio_end",
			},
			{
				"fieldname": "fm_share_certificates",
				"fieldtype": "Check",
				"label": "Compartir Certificados",
				"description": "Usar certificados de pool compartido de la empresa",
				"insert_after": "fm_certificate_section",
				"depends_on": "eval:doc.fm_enable_fiscal",
				"default": 1,
			},
		],
		"Sales Invoice": [
			{
				"fieldname": "fm_multibranch_section",
				"fieldtype": "Section Break",
				"label": "Multi Sucursal",
				"insert_after": "naming_series",
			},
			{
				"fieldname": "fm_branch",
				"fieldtype": "Link",
				"options": "Branch",
				"label": "Sucursal",
				"description": "Sucursal que emite esta factura",
				"insert_after": "fm_multibranch_section",
			},
			{
				"fieldname": "fm_lugar_expedicion_override",
				"fieldtype": "Data",
				"label": "Lugar Expedición (Override)",
				"description": "Sobrescribir lugar de expedición de la sucursal",
				"insert_after": "fm_branch",
				"depends_on": "eval:doc.fm_branch",
			},
		],
	}

	return custom_fields


def apply_custom_fields():
	"""
	DESACTIVADO - MIGRADO A FIXTURES

	Esta función ha sido desactivada como parte de la migración arquitectural de Issue #31.
	Los custom fields multi-sucursal ahora se gestionan exclusivamente a través de fixtures en hooks.py.

	RAZÓN: Prevenir creación duplicada de campos durante migraciones.
	"""
	print("⚠️ apply_custom_fields() DESACTIVADO - Campos gestionados por fixtures")
	print("📍 Ver hooks.py para custom fields multi-sucursal")
	return

	# CÓDIGO ORIGINAL COMENTADO - NO ELIMINAR PARA REFERENCIA
	# try:
	# 	custom_fields = get_custom_fields()
	# 	create_custom_fields(custom_fields, update=True)
	# 	frappe.db.commit()
	# 	print("✅ Custom fields multi-sucursal aplicados exitosamente")
	# except Exception as e:
	# 	frappe.db.rollback()
	# 	print(f"❌ Error aplicando custom fields: {e}")
	# 	raise


def remove_custom_fields():
	"""Remover custom fields del sistema"""
	try:
		custom_fields = get_custom_fields()

		for doctype, fields in custom_fields.items():
			for field in fields:
				fieldname = field.get("fieldname")
				if frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname}):
					frappe.delete_doc("Custom Field", {"dt": doctype, "fieldname": fieldname})

		frappe.db.commit()
		print("✅ Custom fields multi-sucursal removidos exitosamente")

	except Exception as e:
		frappe.db.rollback()
		print(f"❌ Error removiendo custom fields: {e}")
		raise


if __name__ == "__main__":
	# DESACTIVADO - Migrado a fixtures en hooks.py
	print("⚠️ MULTI-SUCURSAL: Custom fields ahora gestionados por fixtures")
	print("📍 No se ejecutará apply_custom_fields() - Ver hooks.py")
