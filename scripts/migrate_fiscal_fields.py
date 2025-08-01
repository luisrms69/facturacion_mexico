#!/usr/bin/env python3
"""
Script de migración arquitectural: Sales Invoice → Factura Fiscal Mexico
Migra todos los campos fm_* de Sales Invoice a Factura Fiscal Mexico
"""

import frappe
from frappe import _


def get_sales_invoice_fm_fields():
	"""Obtener todos los campos fm_* de Sales Invoice"""
	fields = frappe.get_all(
		"Custom Field",
		filters={"dt": "Sales Invoice", "fieldname": ["like", "fm_%"]},
		fields=[
			"fieldname",
			"label",
			"fieldtype",
			"options",
			"length",
			"precision",
			"default",
			"reqd",
			"unique",
			"read_only",
			"hidden",
			"print_hide",
			"allow_on_submit",
			"depends_on",
			"mandatory_depends_on",
			"read_only_depends_on",
			"insert_after",
			"description",
			"permlevel",
			"width",
			"collapsible",
			"collapsible_depends_on",
		],
	)

	print(f"✅ Encontrados {len(fields)} campos fm_* en Sales Invoice")
	return fields


def create_fields_in_factura_fiscal(fields):
	"""Crear campos en Factura Fiscal Mexico"""

	# Campos que NO debemos migrar (mantener solo en Sales Invoice)
	excluded_fields = {
		"fm_factura_fiscal_mx",  # Es la referencia, debe quedarse en SI
	}

	created = 0
	skipped = 0

	for field_data in fields:
		fieldname = field_data["fieldname"]

		# Saltar campos excluidos
		if fieldname in excluded_fields:
			print(f"⏭️  Saltando {fieldname} (debe permanecer en Sales Invoice)")
			skipped += 1
			continue

		# Verificar si ya existe
		if frappe.db.exists("Custom Field", f"Factura Fiscal Mexico-{fieldname}"):
			print(f"⚠️  Campo {fieldname} ya existe en Factura Fiscal Mexico")
			skipped += 1
			continue

		# Preparar datos del campo
		new_field = {
			"doctype": "Custom Field",
			"dt": "Factura Fiscal Mexico",
			"fieldname": fieldname,
			"label": field_data["label"],
			"fieldtype": field_data["fieldtype"],
			"options": field_data["options"],
			"length": field_data["length"],
			"precision": field_data["precision"],
			"default": field_data["default"],
			"reqd": 0,  # Nunca mandatory en Factura Fiscal Mexico
			"unique": field_data["unique"],
			"read_only": field_data["read_only"],
			"hidden": field_data["hidden"],
			"print_hide": field_data["print_hide"],
			"allow_on_submit": 1,  # Siempre permitir edición
			"depends_on": field_data["depends_on"],
			"mandatory_depends_on": None,  # Eliminar mandatory_depends_on
			"read_only_depends_on": field_data["read_only_depends_on"],
			"insert_after": field_data["insert_after"] if field_data["insert_after"] else "uuid",
			"description": field_data["description"],
			"permlevel": 0,  # Siempre permlevel 0
			"width": field_data["width"],
			"collapsible": field_data["collapsible"],
			"collapsible_depends_on": field_data["collapsible_depends_on"],
		}

		try:
			# Crear el campo
			custom_field = frappe.get_doc(new_field)
			custom_field.insert()
			print(f"✅ Creado: {fieldname} - {field_data['label']}")
			created += 1

		except Exception as e:
			print(f"❌ Error creando {fieldname}: {e!s}")

	return created, skipped


def run_migration():
	"""Ejecutar migración completa"""
	print("=" * 60)
	print("🚀 INICIANDO MIGRACIÓN DE CAMPOS FISCALES")
	print("   Sales Invoice → Factura Fiscal Mexico")
	print("=" * 60)

	try:
		# Paso 1: Obtener campos de Sales Invoice
		print("\n📋 PASO 1: Auditoría de campos")
		si_fields = get_sales_invoice_fm_fields()

		# Paso 2: Crear campos en Factura Fiscal Mexico
		print("\n🏗️  PASO 2: Creación de campos")
		created, skipped = create_fields_in_factura_fiscal(si_fields)

		# Commit cambios
		frappe.db.commit()

		# Resumen
		print("\n" + "=" * 60)
		print("📊 RESUMEN DE MIGRACIÓN:")
		print(f"   Total campos encontrados: {len(si_fields)}")
		print(f"   Campos creados: {created}")
		print(f"   Campos saltados: {skipped}")
		print("   ✅ Migración de campos completada exitosamente")
		print("=" * 60)

		return {"created": created, "skipped": skipped, "total": len(si_fields)}

	except Exception as e:
		frappe.db.rollback()
		print(f"\n❌ ERROR EN MIGRACIÓN: {e!s}")
		raise


if __name__ == "__main__":
	# Ejecutar desde consola de Frappe
	result = run_migration()
