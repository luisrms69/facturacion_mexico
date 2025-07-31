#!/usr/bin/env python3

import os

os.chdir("/home/erpnext/frappe-bench")

# Fields from hooks.py that should exist
expected_item_fields = [
	"Item-fm_clasificacion_sat_section",
	"Item-fm_producto_servicio_sat",
	"Item-fm_column_break_item_sat",
	"Item-fm_unidad_sat",
]

print("🔍 VERIFICANDO CAMPOS ITEM DEFINIDOS VS EXISTENTES")
print("=" * 60)

# Check which ones actually exist
script_content = """
import frappe

expected_fields = [
    "Item-fm_clasificacion_sat_section",
    "Item-fm_producto_servicio_sat",
    "Item-fm_column_break_item_sat",
    "Item-fm_unidad_sat"
]
existing_fields = []
missing_fields = []

for field_name in expected_fields:
    if frappe.db.exists("Custom Field", field_name):
        existing_fields.append(field_name)
        # Get field details
        field = frappe.get_doc("Custom Field", field_name)
        print(f"✅ {field_name}")
        print(f"   Type: {field.fieldtype}, Options: {field.options}, Label: {field.label}")
    else:
        missing_fields.append(field_name)
        print(f"❌ {field_name} - MISSING")

print(f"\\n📊 RESUMEN:")
print(f"✅ Existentes: {len(existing_fields)}")
print(f"❌ Faltantes: {len(missing_fields)}")

if missing_fields:
    print(f"\\n🚨 CAMPOS FALTANTES QUE DEBEN CREARSE:")
    for field in missing_fields:
        print(f"  - {field}")
"""

import subprocess

result = subprocess.run(
	["bench", "--site", "facturacion.dev", "console"], input=script_content, text=True, capture_output=True
)
print(result.stdout)
if result.stderr:
	print("STDERR:", result.stderr)
