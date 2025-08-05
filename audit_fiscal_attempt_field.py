#!/usr/bin/env python3
"""
Auditoría completa antes de eliminar Custom Field fm_fiscal_attempts
Basado en estrategia ultra-segura de eliminación
"""

import json
import os
import subprocess

import frappe


def audit_custom_field_before_removal():
	"""Auditoría completa antes de eliminar Custom Field"""
	fieldname = "fm_fiscal_attempts"
	doctype = "Sales Invoice"
	field_id = f"{doctype}-{fieldname}"

	print(f"🔍 INICIANDO AUDITORÍA CUSTOM FIELD: {field_id}")

	# 1. Verificar existencia
	if not frappe.db.exists("Custom Field", field_id):
		print(f"✅ Campo {field_id} no existe - nada que eliminar")
		return False

	# 2. Auditar configuración del campo
	cf = frappe.get_doc("Custom Field", field_id)
	print("\n📋 CONFIGURACIÓN ACTUAL:")
	print(f"   Field Name: {cf.fieldname}")
	print(f"   Label: {cf.label}")
	print(f"   Field Type: {cf.fieldtype}")
	print(f"   Options: {cf.options}")
	print(f"   In List View: {cf.in_list_view}")
	print(f"   In Standard Filter: {cf.in_standard_filter}")
	print(f"   Hidden: {cf.hidden}")
	print(f"   Depends On: {cf.depends_on}")
	print(f"   Module: {cf.module}")
	print(f"   Insert After: {cf.insert_after}")

	# 3. Buscar referencias en Print Formats
	print("\n🔍 VERIFICANDO PRINT FORMATS...")
	print_formats_with_field = frappe.db.sql(
		"""
        SELECT name FROM `tabCustom Print Format`
        WHERE html LIKE %s
    """,
		(f"%{fieldname}%",),
	)

	if print_formats_with_field:
		print(f"⚠️  ENCONTRADOS {len(print_formats_with_field)} Print Formats con referencias:")
		for pf in print_formats_with_field:
			print(f"     - {pf[0]}")
	else:
		print("✅ Sin referencias en Print Formats")

	# 4. Buscar referencias en Reports
	print("\n🔍 VERIFICANDO REPORTS...")
	reports_with_field = frappe.db.sql(
		"""
        SELECT name FROM `tabReport`
        WHERE report_json LIKE %s OR query LIKE %s
    """,
		(f"%{fieldname}%", f"%{fieldname}%"),
	)

	if reports_with_field:
		print(f"⚠️  ENCONTRADOS {len(reports_with_field)} Reports con referencias:")
		for report in reports_with_field:
			print(f"     - {report[0]}")
	else:
		print("✅ Sin referencias en Reports")

	# 5. Buscar referencias en código
	print("\n🔍 VERIFICANDO REFERENCIAS EN CÓDIGO...")
	try:
		result = subprocess.run(
			["grep", "-r", fieldname, "/home/erpnext/frappe-bench/apps/facturacion_mexico/"],
			capture_output=True,
			text=True,
		)
		references = [line for line in result.stdout.splitlines() if line.strip()]
		print(f"📝 Referencias en código: {len(references)} encontradas")
		for ref in references[:5]:  # Mostrar solo las primeras 5
			print(f"     - {ref}")
		if len(references) > 5:
			print(f"     ... y {len(references)-5} más")
	except Exception as e:
		print(f"⚠️  Error buscando referencias: {e}")

	# 6. Verificar datos existentes
	print("\n🔍 VERIFICANDO DATOS EXISTENTES...")
	try:
		sales_invoices_with_data = frappe.db.sql(
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

		if sales_invoices_with_data:
			print(f"⚠️  ENCONTRADOS Sales Invoice con datos en {fieldname}:")
			for si in sales_invoices_with_data:
				print(f"     - {si.name}: {si.get(fieldname)}")
		else:
			print("✅ Sin datos en el campo a eliminar")
	except Exception as e:
		print(f"⚠️  Error verificando datos: {e}")

	# 7. Crear backup del Custom Field
	print("\n💾 CREANDO BACKUP...")
	backup_custom_field(field_id, cf)

	print(f"\n✅ AUDITORÍA COMPLETADA PARA {field_id}")
	return True


def backup_custom_field(field_id, cf):
	"""Crear backup del Custom Field antes de eliminar"""
	backup_data = cf.as_dict()

	# Guardar en archivo con timestamp
	import datetime

	timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
	backup_file = f"/tmp/backup_custom_field_{field_id.replace('-', '_')}_{timestamp}.json"

	try:
		with open(backup_file, "w", encoding="utf-8") as f:
			json.dump(backup_data, f, indent=2, default=str, ensure_ascii=False)

		print(f"💾 Backup guardado en: {backup_file}")
		return backup_file
	except Exception as e:
		print(f"❌ Error creando backup: {e}")
		return None


if __name__ == "__main__":
	frappe.init(site="facturacion.dev")
	frappe.connect()
	audit_custom_field_before_removal()
	frappe.destroy()
