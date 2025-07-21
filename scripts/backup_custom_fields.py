#!/usr/bin/env python3
"""
Script de Backup de Custom Fields - Migración Preventiva
Proyecto: facturacion_mexico
Función: Respaldar custom fields antes de migrar a prefijo fm_
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
	}

	print(f"🔧 Iniciando backup de {len(fields_to_backup)} custom fields...")

	for dt, fieldname in fields_to_backup:
		try:
			if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname}):
				field = frappe.get_doc("Custom Field", {"dt": dt, "fieldname": fieldname})
				backup_data["fields"].append({"doctype": dt, "fieldname": fieldname, "data": field.as_dict()})
				print(f"✅ Respaldado: {dt}.{fieldname}")
			else:
				print(f"⚠️ No encontrado: {dt}.{fieldname}")
				backup_data["fields"].append(
					{"doctype": dt, "fieldname": fieldname, "data": None, "status": "not_found"}
				)
		except Exception as e:
			print(f"❌ Error respaldando {dt}.{fieldname}: {e!s}")
			backup_data["fields"].append(
				{"doctype": dt, "fieldname": fieldname, "data": None, "status": "error", "error": str(e)}
			)

	# Crear directorio de backups si no existe
	backup_dir = os.path.join(frappe.get_site_path(), "custom_field_backups")
	os.makedirs(backup_dir, exist_ok=True)

	# Guardar backup con timestamp
	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	backup_file = os.path.join(backup_dir, f"custom_fields_backup_{timestamp}.json")

	with open(backup_file, "w", encoding="utf-8") as f:
		json.dump(backup_data, f, indent=2, ensure_ascii=False)

	# Crear también un backup de la estructura de las tablas
	table_backup = backup_table_structure(fields_to_backup)
	table_backup_file = os.path.join(backup_dir, f"table_structure_backup_{timestamp}.json")

	with open(table_backup_file, "w", encoding="utf-8") as f:
		json.dump(table_backup, f, indent=2, ensure_ascii=False)

	print(f"\n📁 Backup custom fields guardado en: {backup_file}")
	print(f"📁 Backup estructura tablas guardado en: {table_backup_file}")

	# Resumen
	backed_up = len([f for f in backup_data["fields"] if f.get("data")])
	not_found = len([f for f in backup_data["fields"] if f.get("status") == "not_found"])
	errors = len([f for f in backup_data["fields"] if f.get("status") == "error"])

	print("\n📊 RESUMEN DEL BACKUP:")
	print(f"✅ Respaldados exitosamente: {backed_up}")
	print(f"⚠️ No encontrados: {not_found}")
	print(f"❌ Errores: {errors}")
	print(f"📂 Total procesados: {len(fields_to_backup)}")

	return backup_file


def backup_table_structure(fields_to_backup):
	"""Respaldar estructura de columnas en las tablas"""

	table_backup = {"timestamp": datetime.now().isoformat(), "tables": {}}

	# Obtener docypes únicos
	doctypes = list(set([dt for dt, _ in fields_to_backup]))

	for dt in doctypes:
		table_name = f"tab{dt}"

		try:
			if frappe.db.table_exists(table_name):
				columns = frappe.db.sql(
					f"""
                    SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = '{table_name}'
                    AND COLUMN_NAME IN ({
                        ','.join([f"'{fn}'" for _, fn in fields_to_backup if _ == dt])
                    })
                    ORDER BY ORDINAL_POSITION
                """,
					as_dict=True,
				)

				table_backup["tables"][dt] = {"table_name": table_name, "columns": columns}

				print(f"✅ Estructura respaldada para tabla: {table_name} ({len(columns)} columnas)")
			else:
				print(f"⚠️ Tabla no existe: {table_name}")

		except Exception as e:
			print(f"❌ Error respaldando estructura de {table_name}: {e!s}")

	return table_backup


def restore_custom_fields_from_backup(backup_file):
	"""Función de rollback - restaurar custom fields desde backup"""

	print(f"🔄 Restaurando custom fields desde: {backup_file}")

	if not os.path.exists(backup_file):
		print(f"❌ Archivo de backup no encontrado: {backup_file}")
		return False

	try:
		with open(backup_file, encoding="utf-8") as f:
			backup_data = json.load(f)

		restored_count = 0
		error_count = 0

		for field_backup in backup_data["fields"]:
			if not field_backup.get("data"):
				continue

			try:
				dt = field_backup["doctype"]
				fieldname = field_backup["fieldname"]
				field_data = field_backup["data"]

				# Verificar si ya existe
				if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname}):
					print(f"⚠️ Campo ya existe, saltando: {dt}.{fieldname}")
					continue

				# Restaurar custom field
				field_doc = frappe.get_doc(field_data)
				field_doc.insert(ignore_permissions=True)

				restored_count += 1
				print(f"✅ Restaurado: {dt}.{fieldname}")

			except Exception as e:
				error_count += 1
				print(f"❌ Error restaurando {field_backup['doctype']}.{field_backup['fieldname']}: {e!s}")

		frappe.db.commit()

		print("\n📊 RESUMEN DE RESTAURACIÓN:")
		print(f"✅ Restaurados: {restored_count}")
		print(f"❌ Errores: {error_count}")

		return restored_count > 0

	except Exception as e:
		print(f"❌ Error general en restauración: {e!s}")
		frappe.db.rollback()
		return False


if __name__ == "__main__":
	frappe.init(site="facturacion.dev")
	frappe.connect()

	try:
		backup_file = backup_custom_fields()
		print("\n✅ BACKUP COMPLETADO EXITOSAMENTE")
		print(f"📁 Archivo: {backup_file}")

	except Exception as e:
		print(f"❌ ERROR CRÍTICO EN BACKUP: {e!s}")

	finally:
		frappe.destroy()
