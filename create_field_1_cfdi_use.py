#!/usr/bin/env python3
"""
Crear campo fm_cfdi_use en Factura Fiscal Mexico
Basado en validaciones del código Python existente
"""

import os
import sys

sys.path.append("/home/erpnext/frappe-bench")
sys.path.append("/home/erpnext/frappe-bench/apps/frappe")
os.chdir("/home/erpnext/frappe-bench")

import frappe

frappe.init(site="facturacion.dev")
frappe.connect()

# Crear campo fm_cfdi_use
if not frappe.db.exists("Custom Field", "Factura Fiscal Mexico-fm_cfdi_use"):
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
	frappe.db.commit()
	print("✅ Campo fm_cfdi_use creado exitosamente")
	print(f"   Name: {custom_field.name}")
else:
	print("❌ Campo fm_cfdi_use ya existe")
