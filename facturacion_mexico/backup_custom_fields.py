"""
Script de Backup de Custom Fields - Migración Preventiva
Ejecutar desde: bench --site facturacion.dev execute facturacion_mexico.backup_custom_fields.backup_custom_fields
"""

import json
import os
from datetime import datetime

import frappe


def backup_custom_fields():
	"""Respaldar todos los custom fields actuales antes de migración"""

	fields_to_backup = [
		# Sales Invoice (7 campos)
		("Sales Invoice", "cfdi_use"),
		("Sales Invoice", "payment_method_sat"),
		("Sales Invoice", "fiscal_status"),
		("Sales Invoice", "uuid_fiscal"),
		("Sales Invoice", "factura_fiscal_mx"),
		("Sales Invoice", "informacion_fiscal_mx_section"),
		("Sales Invoice", "column_break_fiscal_mx"),
		# Customer (5 campos)
		("Customer", "rfc"),
		("Customer", "regimen_fiscal"),
		("Customer", "uso_cfdi_default"),
		("Customer", "informacion_fiscal_mx_section"),
		("Customer", "column_break_fiscal_customer"),
		# Item (4 campos)
		("Item", "producto_servicio_sat"),
		("Item", "unidad_sat"),
		("Item", "clasificacion_sat_section"),
		("Item", "column_break_item_sat"),
	]

	backup_data = {
		"fields": [],
		"timestamp": datetime.now().isoformat(),
		"app": "facturacion_mexico",
		"migration_type": "custom_fields_prefix_migration",
		"total_fields": len(fields_to_backup),
		"site": frappe.local.site,
	}

	print(f"🔧 Iniciando backup de {len(fields_to_backup)} custom fields en site {frappe.local.site}...")

	found_count = 0
	not_found_count = 0
	error_count = 0

	for dt, fieldname in fields_to_backup:
		try:
			if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname}):
				field = frappe.get_doc("Custom Field", {"dt": dt, "fieldname": fieldname})
				field_dict = field.as_dict()
				# Convertir datetime objects a strings para JSON serialization
				for key, value in field_dict.items():
					if hasattr(value, "isoformat"):
						field_dict[key] = value.isoformat()

				backup_data["fields"].append({"doctype": dt, "fieldname": fieldname, "data": field_dict})
				found_count += 1
				print(f"✅ Respaldado: {dt}.{fieldname}")
			else:
				not_found_count += 1
				print(f"⚠️ No encontrado: {dt}.{fieldname}")
				backup_data["fields"].append(
					{"doctype": dt, "fieldname": fieldname, "data": None, "status": "not_found"}
				)
		except Exception as e:
			error_count += 1
			print(f"❌ Error respaldando {dt}.{fieldname}: {e!s}")
			backup_data["fields"].append(
				{"doctype": dt, "fieldname": fieldname, "data": None, "status": "error", "error": str(e)}
			)

	# Crear directorio de backups en el site
	site_path = frappe.get_site_path()
	backup_dir = os.path.join(site_path, "custom_field_backups")
	os.makedirs(backup_dir, exist_ok=True)

	# Guardar backup con timestamp
	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	backup_file = os.path.join(backup_dir, f"custom_fields_backup_{timestamp}.json")

	with open(backup_file, "w", encoding="utf-8") as f:
		json.dump(backup_data, f, indent=2, ensure_ascii=False)

	print(f"\n📁 Backup guardado en: {backup_file}")

	# Resumen
	print("\n📊 RESUMEN DEL BACKUP:")
	print(f"✅ Respaldados exitosamente: {found_count}")
	print(f"⚠️ No encontrados: {not_found_count}")
	print(f"❌ Errores: {error_count}")
	print(f"📂 Total procesados: {len(fields_to_backup)}")

	# Verificar que tenemos al menos los campos críticos
	critical_fields = ["cfdi_use", "rfc", "producto_servicio_sat"]
	found_critical = [f for f in backup_data["fields"] if f["fieldname"] in critical_fields and f.get("data")]

	if len(found_critical) >= len(critical_fields):
		print("\n✅ BACKUP EXITOSO - Campos críticos respaldados correctamente")
	else:
		print("\n⚠️ ADVERTENCIA - Faltan algunos campos críticos en el backup")
		print(f"Críticos encontrados: {[f['fieldname'] for f in found_critical]}")

	return backup_file


def list_current_custom_fields():
	"""Listar custom fields actuales para verificación"""

	print("📋 CUSTOM FIELDS ACTUALES EN EL SISTEMA:")
	print("=" * 50)

	for doctype in ["Sales Invoice", "Customer", "Item"]:
		print(f"\n📄 {doctype}:")

		fields = frappe.get_all(
			"Custom Field",
			filters={"dt": doctype},
			fields=["fieldname", "label", "fieldtype", "insert_after"],
			order_by="idx",
		)

		for field in fields:
			prefix_status = "🟢 fm_" if field.fieldname.startswith("fm_") else "🔴 NO PREFIX"
			print(f"   {prefix_status} {field.fieldname} ({field.fieldtype}) - {field.label}")

	return len(fields)
