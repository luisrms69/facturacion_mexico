# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Sales Invoice Custom Fields - Sprint 6 Phase 2 Step 5
Custom fields para integración multi-sucursal en Sales Invoice
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def setup_sales_invoice_custom_fields():
	"""
	DESACTIVADO - MIGRADO A FIXTURES

	Esta función ha sido desactivada como parte de la migración arquitectural de Issue #31.
	Los campos fm_lugar_expedicion y fm_serie_folio han sido migrados a Factura Fiscal Mexico.

	RAZÓN: Prevenir creación duplicada de campos fiscales durante migraciones.
	"""
	print("⚠️ setup_sales_invoice_custom_fields() DESACTIVADO")
	print("📍 Campos fm_lugar_expedicion y fm_serie_folio migrados a Factura Fiscal Mexico")
	return

	custom_fields = {
		"Sales Invoice": [
			{
				"fieldname": "fm_multi_sucursal_section",
				"fieldtype": "Section Break",
				"label": "Configuración Multi-Sucursal",
				"insert_after": "fm_requires_stamp",
				"collapsible": 1,
			},
			{
				"fieldname": "fm_branch",
				"fieldtype": "Link",
				"label": "Sucursal Fiscal",
				"options": "Branch",
				"insert_after": "fm_multi_sucursal_section",
				"description": "Sucursal responsable de la facturación fiscal",
				"mandatory_depends_on": "eval:doc.fm_requires_stamp",
				"depends_on": "eval:doc.fm_requires_stamp",
			},
			{
				"fieldname": "fm_lugar_expedicion",
				"fieldtype": "Data",
				"label": "Lugar de Expedición",
				"insert_after": "fm_branch",
				"description": "Código postal del lugar de expedición (tomado de la sucursal)",
				"read_only": 1,
				"depends_on": "eval:doc.fm_requires_stamp && doc.fm_branch",
			},
			{
				"fieldname": "fm_serie_folio",
				"fieldtype": "Data",
				"label": "Serie y Folio",
				"insert_after": "fm_lugar_expedicion",
				"description": "Serie y folio asignado por la sucursal",
				"read_only": 1,
				"depends_on": "eval:doc.fm_requires_stamp && doc.fm_branch",
			},
			{
				"fieldname": "fm_folio_reserved",
				"fieldtype": "Check",
				"label": "Folio Reservado",
				"insert_after": "fm_serie_folio",
				"description": "Indica si el folio está reservado para esta factura",
				"read_only": 1,
				"default": 0,
				"depends_on": "eval:doc.fm_requires_stamp && doc.fm_branch",
			},
			{
				"fieldname": "fm_multi_sucursal_column",
				"fieldtype": "Column Break",
				"insert_after": "fm_folio_reserved",
			},
			{
				"fieldname": "fm_certificate_info",
				"fieldtype": "Small Text",
				"label": "Información del Certificado",
				"insert_after": "fm_multi_sucursal_column",
				"description": "Certificado digital asignado por la sucursal",
				"read_only": 1,
				"depends_on": "eval:doc.fm_requires_stamp && doc.fm_branch",
			},
			{
				"fieldname": "fm_branch_health_status",
				"fieldtype": "Select",
				"label": "Estado de la Sucursal",
				"insert_after": "fm_certificate_info",
				"options": "\nHealthy\nWarning\nCritical\nInactive",
				"description": "Estado actual de la sucursal fiscal",
				"read_only": 1,
				"depends_on": "eval:doc.fm_requires_stamp && doc.fm_branch",
			},
			{
				"fieldname": "fm_auto_selected_branch",
				"fieldtype": "Check",
				"label": "Sucursal Auto-Seleccionada",
				"insert_after": "fm_branch_health_status",
				"description": "Indica si la sucursal fue seleccionada automáticamente",
				"read_only": 1,
				"default": 0,
				"depends_on": "eval:doc.fm_requires_stamp && doc.fm_branch",
			},
		]
	}

	create_custom_fields(custom_fields, update=True)
	print("✅ Custom fields de Sales Invoice creados exitosamente")


def remove_sales_invoice_custom_fields():
	"""
	Remover custom fields de Sales Invoice (para rollback)
	"""

	fields_to_remove = [
		"fm_multi_sucursal_section",
		"fm_branch",
		"fm_lugar_expedicion",
		"fm_serie_folio",
		"fm_folio_reserved",
		"fm_multi_sucursal_column",
		"fm_certificate_info",
		"fm_branch_health_status",
		"fm_auto_selected_branch",
	]

	for fieldname in fields_to_remove:
		try:
			# Eliminar custom field si existe
			if frappe.db.exists("Custom Field", {"dt": "Sales Invoice", "fieldname": fieldname}):
				frappe.delete_doc("Custom Field", {"dt": "Sales Invoice", "fieldname": fieldname})
				print(f"✅ Campo {fieldname} eliminado")
		except Exception as e:
			print(f"⚠️  Error eliminando campo {fieldname}: {e}")

	# Manual commit required for custom field cleanup in development
	frappe.db.commit()  # nosemgrep
	print("✅ Custom fields de Sales Invoice removidos")


if __name__ == "__main__":
	# DESACTIVADO - Migrado a fixtures en hooks.py
	print("⚠️ SALES_INVOICE_FIELDS: Campos migrados a Factura Fiscal Mexico")
	print("📍 No se ejecutará setup_sales_invoice_custom_fields()")
