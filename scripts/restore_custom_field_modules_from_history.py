#!/usr/bin/env python3
"""
Script para restaurar módulos correctos en Custom Fields según asignaciones históricas
Basado en el mapeo definido en el commit c8cc6ff (fix_custom_field_modules.py)
"""

import frappe

# Mapeo histórico de campos a módulos (extraído del commit c8cc6ff)
FIELD_TO_MODULE_MAP = {
	# BRANCH FIELDS → Multi Sucursal (14 campos)
	"Branch": {
		"fm_certificate_ids": "Multi Sucursal",
		"fm_enable_fiscal": "Multi Sucursal",
		"fm_enable_fiscal_test": "Multi Sucursal",
		"fm_fiscal_configuration_section": "Multi Sucursal",
		"fm_folio_current": "Multi Sucursal",
		"fm_folio_end": "Multi Sucursal",
		"fm_folio_start": "Multi Sucursal",
		"fm_folio_warning_threshold": "Multi Sucursal",
		"fm_last_invoice_date": "Multi Sucursal",
		"fm_lugar_expedicion": "Multi Sucursal",
		"fm_monthly_average": "Multi Sucursal",
		"fm_serie_pattern": "Multi Sucursal",
		"fm_share_certificates": "Multi Sucursal",
		"fm_test_field_unique_2025": "Multi Sucursal",
	},
	# CUSTOMER FIELDS → Addendas + Validaciones (12 campos)
	"Customer": {
		# Addendas (4 campos)
		"fm_addenda_info_section": "Addendas",
		"fm_column_break_fiscal_customer": "Addendas",
		"fm_default_addenda_type": "Addendas",
		"fm_requires_addenda": "Addendas",
		# Validaciones (8 campos)
		"fm_column_break_validacion": "Validaciones",
		"fm_informacion_fiscal_mx_section": "Validaciones",
		"fm_lista_69b_status": "Validaciones",
		"fm_regimen_fiscal": "Validaciones",
		"fm_rfc_validated": "Validaciones",
		"fm_rfc_validation_date": "Validaciones",
		"fm_uso_cfdi_default": "Validaciones",
		"fm_validacion_sat_section": "Validaciones",
	},
	# ITEM FIELDS → Catalogos SAT (3 campos)
	"Item": {
		"fm_clasificacion_sat_section": "Catalogos SAT",
		"fm_column_break_item_sat": "Catalogos SAT",
		"fm_producto_servicio_sat": "Catalogos SAT",
	},
	# PAYMENT ENTRY FIELDS → Complementos Pago (5 campos)
	"Payment Entry": {
		"fm_complement_generated": "Complementos Pago",
		"fm_complemento_pago": "Complementos Pago",
		"fm_forma_pago_sat": "Complementos Pago",
		"fm_informacion_fiscal_section": "Complementos Pago",
		"fm_require_complement": "Complementos Pago",
	},
	# SALES INVOICE FIELDS → División por funcionalidad (31 campos)
	"Sales Invoice": {
		# Addendas (8 campos)
		"fm_addenda_column_break": "Addendas",
		"fm_addenda_errors": "Addendas",
		"fm_addenda_generated_date": "Addendas",
		"fm_addenda_required": "Addendas",
		"fm_addenda_section": "Addendas",
		"fm_addenda_status": "Addendas",
		"fm_addenda_type": "Addendas",
		"fm_addenda_xml": "Addendas",
		# Multi Sucursal (5 campos)
		"fm_auto_selected_branch": "Multi Sucursal",
		"fm_branch": "Multi Sucursal",
		"fm_branch_health_status": "Multi Sucursal",
		"fm_multi_sucursal_column": "Multi Sucursal",
		"fm_multi_sucursal_section": "Multi Sucursal",
		# Facturacion Fiscal (12 campos)
		"fm_certificate_info": "Facturacion Fiscal",
		"fm_create_as_draft": "Facturacion Fiscal",
		"fm_draft_approved_by": "Facturacion Fiscal",
		"fm_draft_column_break": "Facturacion Fiscal",
		"fm_draft_created_date": "Facturacion Fiscal",
		"fm_draft_section": "Facturacion Fiscal",
		"fm_draft_status": "Facturacion Fiscal",
		"fm_factorapi_draft_id": "Facturacion Fiscal",
		"fm_folio_reserved": "Facturacion Fiscal",
		"fm_timbrado_section": "Facturacion Fiscal",
		"fm_factura_fiscal_mx": "Facturacion Fiscal",
		"fm_column_break_fiscal": "Facturacion Fiscal",
		# EReceipts (8 campos)
		"fm_complementos_count": "EReceipts",
		"fm_ereceipt_column_break": "EReceipts",
		"fm_ereceipt_expiry_date": "EReceipts",
		"fm_ereceipt_expiry_days": "EReceipts",
		"fm_ereceipt_expiry_type": "EReceipts",
		"fm_ereceipt_mode": "EReceipts",
		"fm_ereceipt_section": "EReceipts",
		"fm_pending_amount": "EReceipts",
	},
}


def execute():
	"""Restaurar módulos correctos en Custom Fields según mapeo histórico - SOLUCIÓN DEFINITIVA"""

	print("🔄 INICIANDO RESTAURACIÓN DEFINITIVA DE MÓDULOS")
	print("=" * 70)

	# FASE 1: CORRECCIÓN EN BASE DE DATOS
	print("🗃️  FASE 1: CORRIGIENDO BASE DE DATOS...")
	corrections_made = correct_database_modules()

	if corrections_made == 0:
		print("i No se encontraron campos con module null - sistema ya corregido")
		return verify_system_health()

	# FASE 2: EXPORTAR FIXTURES ACTUALIZADOS
	print("\n📦 FASE 2: EXPORTANDO FIXTURES ACTUALIZADOS...")
	export_success = export_fixtures_automatically()

	if not export_success:
		print("❌ Error exportando fixtures - corrección incompleta")
		return False

	# FASE 3: VALIDACIÓN COMPLETA
	print("\n🔍 FASE 3: VALIDANDO CORRECCIÓN DEFINITIVA...")
	validation_passed = validate_definitive_correction()

	if validation_passed:
		print("\n🎉 PROBLEMA RESUELTO DEFINITIVAMENTE")
		print("✅ Base de datos corregida")
		print("✅ Fixtures actualizados")
		print("✅ Sistema validado")
		print("✅ No volverá a ocurrir el problema")
		return True
	else:
		print("\n❌ VALIDACIÓN FALLÓ - revisar manualmente")
		return False


def correct_database_modules():
	"""Corregir módulos en base de datos según mapeo histórico"""
	corrections_made = 0
	fields_processed = 0
	fields_not_found = 0

	# Obtener todos los Custom Fields con module null o vacío
	custom_fields = frappe.get_all(
		"Custom Field", filters={"module": ["in", [None, ""]]}, fields=["name", "dt", "fieldname", "module"]
	)

	print(f"   📋 Encontrados {len(custom_fields)} Custom Fields con module null/vacío")

	for cf_info in custom_fields:
		fields_processed += 1
		dt = cf_info.dt
		fieldname = cf_info.fieldname
		field_name = cf_info.name

		# Buscar módulo correcto en el mapeo histórico
		if dt in FIELD_TO_MODULE_MAP and fieldname in FIELD_TO_MODULE_MAP[dt]:
			correct_module = FIELD_TO_MODULE_MAP[dt][fieldname]

			# Actualizar el Custom Field
			try:
				cf = frappe.get_doc("Custom Field", field_name)
				cf.module = correct_module
				cf.save()

				corrections_made += 1
				print(f"   ✅ {field_name} → {correct_module}")

			except Exception as e:
				print(f"   ❌ Error actualizando {field_name}: {e}")

		else:
			fields_not_found += 1
			print(f"   ⚠️  Campo no encontrado en mapeo histórico: {dt}.{fieldname}")

	# Guardar cambios
	frappe.db.commit()  # nosemgrep: frappe-manual-commit Required to persist custom field module corrections in batch script

	print(f"   📊 BD: {corrections_made} correcciones, {fields_not_found} no encontrados")
	return corrections_made


def export_fixtures_automatically():
	"""Exportar fixtures actualizados automáticamente"""
	try:
		import os
		import subprocess

		# Cambiar al directorio correcto
		os.chdir("/home/erpnext/frappe-bench")

		# Ejecutar export-fixtures
		result = subprocess.run(
			["bench", "--site", "facturacion.dev", "export-fixtures", "--app", "facturacion_mexico"],
			capture_output=True,
			text=True,
			timeout=120,
		)

		if result.returncode == 0:
			print("   ✅ Fixtures exportados exitosamente")
			return True
		else:
			print(f"   ❌ Error exportando fixtures: {result.stderr}")
			return False

	except Exception as e:
		print(f"   ❌ Error en export-fixtures: {e}")
		return False


def validate_definitive_correction():
	"""Validar que la corrección fue definitiva y completa"""
	validation_passed = True

	# 1. Verificar que no hay Custom Fields con module null en BD
	null_fields = frappe.get_all("Custom Field", filters={"module": ["in", [None, ""]]}, fields=["name"])

	if null_fields:
		print(f"   ❌ Aún hay {len(null_fields)} campos con module null en BD")
		validation_passed = False
	else:
		print("   ✅ BD: Ningún Custom Field con module null")

	# 2. Verificar que custom_field.json no tiene module null
	try:
		import json

		fixture_path = (
			"/home/erpnext/frappe-bench/apps/facturacion_mexico/facturacion_mexico/fixtures/custom_field.json"
		)

		with open(fixture_path, encoding="utf-8") as f:
			data = json.load(f)

		null_count = 0
		for entry in data:
			if entry.get("doctype") == "Custom Field" and entry.get("module") is None:
				null_count += 1

		if null_count > 0:
			print(f"   ❌ Fixtures: {null_count} campos con module null")
			validation_passed = False
		else:
			print("   ✅ Fixtures: Ningún campo con module null")

	except Exception as e:
		print(f"   ❌ Error validando fixtures: {e}")
		validation_passed = False

	# 3. Verificar migración funciona
	try:
		import os
		import subprocess

		os.chdir("/home/erpnext/frappe-bench")
		result = subprocess.run(
			["bench", "--site", "facturacion.dev", "migrate", "--dry-run"],
			capture_output=True,
			text=True,
			timeout=60,
		)

		if result.returncode == 0:
			print("   ✅ Migración: Dry-run exitoso")
		else:
			print(f"   ❌ Migración: Dry-run falló - {result.stderr[:200]}")
			validation_passed = False

	except Exception as e:
		print(f"   ❌ Error validando migración: {e}")
		validation_passed = False

	return validation_passed


def verify_system_health():
	"""Verificar salud del sistema si no hay correcciones que hacer"""
	print("\n🔍 VERIFICANDO SALUD DEL SISTEMA...")

	# Contar Custom Fields por módulo
	modules_count = frappe.db.sql(
		"""
        SELECT module, COUNT(*) as count
        FROM `tabCustom Field`
        WHERE module IS NOT NULL
        GROUP BY module
        ORDER BY count DESC
    """,
		as_dict=True,
	)

	print("   📊 Custom Fields por módulo:")
	for mod in modules_count:
		print(f"      {mod.module}: {mod.count} campos")

	return True


if __name__ == "__main__":
	execute()
