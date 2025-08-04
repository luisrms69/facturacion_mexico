#!/usr/bin/env python3
"""
Script de auditoría del campo fm_fiscal_attempts
Ejecutar con: bench --site facturacion.dev execute facturacion_mexico.scripts.audit_field.run_audit
"""

import frappe


def run_audit():
	"""Ejecutar auditoría completa del campo fm_fiscal_attempts"""

	fieldname = "fm_fiscal_attempts"
	doctype = "Sales Invoice"
	field_id = f"{doctype}-{fieldname}"

	print(f"🔍 INICIANDO AUDITORÍA CUSTOM FIELD: {field_id}")

	# 1. Verificar existencia
	exists = frappe.db.exists("Custom Field", field_id)
	print(f"Campo existe: {exists}")

	if not exists:
		print(f"✅ Campo {field_id} NO EXISTE - nada que eliminar")
		return

	# 2. Configuración del campo
	cf = frappe.get_doc("Custom Field", field_id)
	print("\n📋 CONFIGURACIÓN ACTUAL:")
	print(f"   Field Name: {cf.fieldname}")
	print(f"   Label: {cf.label}")
	print(f"   Field Type: {cf.fieldtype}")
	print(f"   Options: {cf.options}")
	print(f"   Module: {cf.module}")
	print(f"   Hidden: {cf.hidden}")
	print(f"   Insert After: {cf.insert_after}")
	print(f"   In List View: {cf.in_list_view}")
	print(f"   In Standard Filter: {cf.in_standard_filter}")

	# 3. Referencias en Print Formats
	print("\n🔍 VERIFICANDO PRINT FORMATS:")
	pf_refs = frappe.db.sql(
		"""SELECT name FROM `tabCustom Print Format` WHERE html LIKE %s""", (f"%{fieldname}%",), as_dict=True
	)
	if pf_refs:
		print(f"⚠️  ENCONTRADOS {len(pf_refs)} Print Formats con referencias:")
		for pf in pf_refs:
			print(f"     - {pf.name}")
	else:
		print("✅ Sin referencias en Print Formats")

	# 4. Referencias en Reports
	print("\n🔍 VERIFICANDO REPORTS:")
	report_refs = frappe.db.sql(
		"""SELECT name FROM `tabReport` WHERE report_json LIKE %s OR query LIKE %s""",
		(f"%{fieldname}%", f"%{fieldname}%"),
		as_dict=True,
	)
	if report_refs:
		print(f"⚠️  ENCONTRADOS {len(report_refs)} Reports con referencias:")
		for report in report_refs:
			print(f"     - {report.name}")
	else:
		print("✅ Sin referencias en Reports")

	# 5. Datos existentes
	print("\n🔍 VERIFICANDO DATOS EXISTENTES:")
	try:
		# Verificar si la columna existe en la tabla
		column_exists = frappe.db.sql(
			f"""
            SELECT COUNT(*) as count
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'tabSales Invoice'
            AND COLUMN_NAME = '{fieldname}'
        """,
			as_dict=True,
		)

		if column_exists[0].count > 0:
			data_records = frappe.db.sql(
				f"""
                SELECT name, {fieldname}
                FROM `tabSales Invoice`
                WHERE {fieldname} IS NOT NULL
                AND {fieldname} != ''
                AND {fieldname} != '[]'
                LIMIT 5
            """,
				as_dict=True,
			)

			if data_records:
				print(f"⚠️  ENCONTRADOS {len(data_records)} Sales Invoice con datos:")
				for record in data_records:
					print(f"     - {record.name}: {record.get(fieldname)}")
			else:
				print("✅ Sin datos en el campo (safe to delete)")
		else:
			print("✅ Columna no existe en tabla Sales Invoice")

	except Exception as e:
		print(f"⚠️  Error verificando datos: {e}")

	# 6. Referencias en fixtures
	print("\n🔍 VERIFICANDO FIXTURES:")
	try:
		import os

		fixture_file = (
			"/home/erpnext/frappe-bench/apps/facturacion_mexico/facturacion_mexico/fixtures/custom_field.json"
		)
		if os.path.exists(fixture_file):
			with open(fixture_file) as f:
				content = f.read()
				if fieldname in content:
					print(f"⚠️  Campo {fieldname} encontrado en fixtures/custom_field.json")
				else:
					print(f"✅ Campo {fieldname} NO está en fixtures")
		else:
			print("✅ Archivo fixtures/custom_field.json no existe")
	except Exception as e:
		print(f"⚠️  Error verificando fixtures: {e}")

	print(f"\n✅ AUDITORÍA COMPLETADA PARA: {field_id}")

	# Crear summary de resultados
	return {
		"field_exists": exists,
		"field_id": field_id,
		"print_format_refs": len(pf_refs) if exists else 0,
		"report_refs": len(report_refs) if exists else 0,
		"safe_to_delete": exists and len(pf_refs) == 0 and len(report_refs) == 0,
	}
