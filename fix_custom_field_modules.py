#!/usr/bin/env python3
"""
Script para corregir "module": null en custom_field.json
Basado en análisis de funcionalidad por DocType

Generado por Claude Code para resolver ModuleNotFoundError en bench migrate
"""

import json
import os

# Mapeo de campos específicos a módulos basado en funcionalidad
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
		# Addendas (3 campos)
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
		# Multi Sucursal (4 campos)
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
		# EReceipts (7 campos)
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


def fix_custom_field_modules():
	"""Corregir módulos null en custom_field.json"""

	file_path = (
		"/home/erpnext/frappe-bench/apps/facturacion_mexico/facturacion_mexico/fixtures/custom_field.json"
	)

	print("🔧 Iniciando corrección de módulos en custom_field.json...")

	# Cargar archivo JSON
	try:
		with open(file_path, "r", encoding="utf-8") as f:
			data = json.load(f)
	except Exception as e:
		print(f"❌ Error leyendo archivo: {e}")
		return False

	corrections_made = 0
	fields_processed = 0

	# Procesar cada entrada
	for entry in data:
		if entry.get("doctype") != "Custom Field":
			continue

		fields_processed += 1
		dt = entry.get("dt")
		fieldname = entry.get("fieldname")
		current_module = entry.get("module")

		# Solo corregir si module es null
		if current_module is None:
			# Buscar módulo correcto
			if dt in FIELD_TO_MODULE_MAP and fieldname in FIELD_TO_MODULE_MAP[dt]:
				new_module = FIELD_TO_MODULE_MAP[dt][fieldname]
				entry["module"] = new_module
				corrections_made += 1
				print(f"✅ {dt}.{fieldname} → {new_module}")
			else:
				print(f"⚠️  Campo no encontrado en mapeo: {dt}.{fieldname}")

	# Guardar archivo corregido
	try:
		with open(file_path, "w", encoding="utf-8") as f:
			json.dump(data, f, indent=2, ensure_ascii=False)
	except Exception as e:
		print(f"❌ Error escribiendo archivo: {e}")
		return False

	print(f"\n📊 RESUMEN:")
	print(f"   Campos procesados: {fields_processed}")
	print(f"   Correcciones realizadas: {corrections_made}")
	print(f"   Archivo actualizado: {file_path}")

	return corrections_made > 0


if __name__ == "__main__":
	success = fix_custom_field_modules()
	if success:
		print("\n🎉 Corrección completada exitosamente!")
		print("   Ahora puedes ejecutar: bench --site facturacion.dev migrate")
	else:
		print("\n❌ Error en la corrección")
