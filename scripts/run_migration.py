#!/usr/bin/env python3
import frappe

frappe.init("facturacion.dev")
frappe.connect()
exec(open("/home/erpnext/frappe-bench/apps/facturacion_mexico/scripts/migrate_fiscal_fields.py").read())
