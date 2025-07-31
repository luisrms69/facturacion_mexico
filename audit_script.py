import frappe

# Get all custom fields for our app
custom_fields = frappe.db.sql(
	"""
    SELECT dt, fieldname, label, fieldtype, insert_after
    FROM `tabCustom Field`
    WHERE fieldname LIKE 'fm_%' OR fieldname LIKE '%fiscal%' OR fieldname LIKE '%sat%' OR fieldname LIKE '%rfc%'
    ORDER BY dt, fieldname
""",
	as_dict=True,
)

print(f"🔍 AUDITORÍA CUSTOM FIELDS - Total encontrados: {len(custom_fields)}")
print("=" * 80)

# Group by DocType
doctypes = {}
for field in custom_fields:
	dt = field.dt
	if dt not in doctypes:
		doctypes[dt] = []
	doctypes[dt].append(field)

# Print grouped results
for dt, fields in doctypes.items():
	print(f"\n📋 === {dt} === ({len(fields)} campos)")
	for field in fields:
		print(f"   {field.fieldname:<30} | {field.fieldtype:<15} | {field.label}")

print("\n" + "=" * 80)
print(f"📊 RESUMEN: {len(doctypes)} DocTypes afectados, {len(custom_fields)} custom fields total")

# Generate fixtures format for hooks.py
print("\n🔧 FORMATO PARA FIXTURES (hooks.py):")
print("fixtures = [")
print("    {")
print('        "dt": "Custom Field",')
print('        "filters": [')
print("            [")
print('                "name",')
print('                "in",')
print("                [")

for field in custom_fields:
	print(f'                    "{field.dt}-{field.fieldname}",')

print("                ]")
print("            ]")
print("        ]")
print("    }")
print("]")

# Save to file for reference
with open("/home/erpnext/frappe-bench/apps/facturacion_mexico/CUSTOM_FIELDS_AUDIT_RESULTS.txt", "w") as f:
	f.write(f"AUDITORÍA CUSTOM FIELDS - Total encontrados: {len(custom_fields)}\n")
	f.write("=" * 80 + "\n")

	for dt, fields in doctypes.items():
		f.write(f"\n=== {dt} === ({len(fields)} campos)\n")
		for field in fields:
			f.write(f"   {field.fieldname:<30} | {field.fieldtype:<15} | {field.label}\n")

	f.write("\n" + "=" * 80 + "\n")
	f.write(f"RESUMEN: {len(doctypes)} DocTypes afectados, {len(custom_fields)} custom fields total\n")

print("\n✅ Resultados guardados en: CUSTOM_FIELDS_AUDIT_RESULTS.txt")
