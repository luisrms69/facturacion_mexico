#!/usr/bin/env python3
"""
Script para crear Custom Field: fm_cfdi_use en Factura Fiscal Mexico
Método oficial Frappe: consola + export-fixtures
"""

import frappe


def create_cfdi_use_field():
	"""Crear campo fm_cfdi_use en Factura Fiscal Mexico"""

	# Verificar si ya existe
	if frappe.db.exists("Custom Field", "Factura Fiscal Mexico-fm_cfdi_use"):
		print("❌ Campo fm_cfdi_use ya existe")
		return

	# Crear usando método oficial Frappe
	custom_field = frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": "Factura Fiscal Mexico",
			"fieldname": "fm_cfdi_use",
			"label": "Uso del CFDI",
			"fieldtype": "Link",
			"options": "Uso CFDI SAT",
			"insert_after": "status",
			"reqd": 1,
			"description": "Uso que se dará al comprobante fiscal",
			"allow_on_submit": 1,
		}
	)

	custom_field.insert()
	frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required for custom field creation script to persist changes immediately

	print("✅ Campo fm_cfdi_use creado exitosamente")
	print(f"   Name: {custom_field.name}")
	print(f"   DocType: {custom_field.dt}")
	print(f"   Fieldtype: {custom_field.fieldtype}")


if __name__ == "__main__":
	create_cfdi_use_field()
