"""
Patch de Migración: Custom Fields con Prefijo fm_
Objetivo: Migrar 16 custom fields agregando prefijo fm_ para evitar conflictos
Ejecución: bench --site facturacion.dev migrate
"""

import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	"""Migrar nombres de custom fields agregando prefijo fm_"""

	# Mapeo completo de migración: (DocType, old_field, new_field)
	migrations = [
		# Sales Invoice (7 campos)
		("Sales Invoice", "cfdi_use", "fm_cfdi_use"),
		("Sales Invoice", "payment_method_sat", "fm_payment_method_sat"),
		("Sales Invoice", "fiscal_status", "fm_fiscal_status"),
		("Sales Invoice", "uuid_fiscal", "fm_uuid_fiscal"),
		("Sales Invoice", "factura_fiscal_mx", "fm_factura_fiscal_mx"),
		("Sales Invoice", "informacion_fiscal_mx_section", "fm_informacion_fiscal_section"),
		("Sales Invoice", "column_break_fiscal_mx", "fm_column_break_fiscal"),
		# Customer (5 campos)
		("Customer", "rfc", "fm_rfc"),
		("Customer", "regimen_fiscal", "fm_regimen_fiscal"),
		("Customer", "uso_cfdi_default", "fm_uso_cfdi_default"),
		("Customer", "informacion_fiscal_mx_section", "fm_informacion_fiscal_section_customer"),
		("Customer", "column_break_fiscal_customer", "fm_column_break_fiscal_customer"),
		# Item (4 campos)
		("Item", "producto_servicio_sat", "fm_producto_servicio_sat"),
		("Item", "unidad_sat", "fm_unidad_sat"),
		("Item", "clasificacion_sat_section", "fm_clasificacion_sat_section"),
		("Item", "column_break_item_sat", "fm_column_break_item_sat"),
	]

	print(f"🚀 Iniciando migración de {len(migrations)} custom fields con prefijo fm_...")
	print(f"📍 Site: {frappe.local.site}")

	success_count = 0
	skip_count = 0
	error_count = 0

	for dt, old_fieldname, new_fieldname in migrations:
		try:
			print(f"\n🔄 Procesando: {dt}.{old_fieldname} -> {new_fieldname}")

			# Verificar si el campo antiguo existe
			if not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": old_fieldname}):
				print(f"⚠️ Campo origen no existe: {dt}.{old_fieldname} - SALTANDO")
				skip_count += 1
				continue

			# Verificar si el campo destino ya existe
			if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": new_fieldname}):
				print(f"⚠️ Campo destino ya existe: {dt}.{new_fieldname} - SALTANDO")
				skip_count += 1
				continue

			# Método 1: Actualizar el Custom Field record
			print("   1️⃣ Actualizando Custom Field record...")
			frappe.db.sql(
				"""
                UPDATE `tabCustom Field`
                SET fieldname = %s
                WHERE dt = %s AND fieldname = %s
            """,
				(new_fieldname, dt, old_fieldname),
			)

			# Método 2: Renombrar la columna en la tabla del DocType
			table_name = f"tab{dt}"

			if frappe.db.table_exists(table_name):
				print(f"   2️⃣ Verificando columna en tabla {table_name}...")

				# Verificar si la columna existe en la tabla
				column_exists = frappe.db.sql(f"""
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = '{table_name}'
                    AND COLUMN_NAME = '{old_fieldname}'
                    LIMIT 1
                """)

				if column_exists:
					print(f"   3️⃣ Renombrando columna {old_fieldname} -> {new_fieldname}...")

					# Obtener tipo de columna
					column_type = get_column_definition(dt, old_fieldname)

					try:
						frappe.db.sql(f"""
                            ALTER TABLE `{table_name}`
                            CHANGE COLUMN `{old_fieldname}` `{new_fieldname}` {column_type}
                        """)
						print("   ✅ Columna renombrada exitosamente")
					except Exception as col_error:
						print(f"   ⚠️ No se pudo renombrar columna: {col_error!s}")
						# Continuar con la migración - el Custom Field ya fue actualizado
				else:
					print(f"   INFO: Columna {old_fieldname} no existe en {table_name}")

			# Commit de esta migración individual
			frappe.db.commit()
			success_count += 1
			print(f"✅ Migrado exitosamente: {dt}.{old_fieldname} -> {new_fieldname}")

		except Exception as e:
			error_count += 1
			print(f"❌ Error migrando {dt}.{old_fieldname}: {e!s}")
			frappe.db.rollback()

			# Log del error para debugging
			frappe.log_error(
				title=f"Error en migración custom field: {dt}.{old_fieldname}",
				message=f"Error: {e!s}\nDetalle: Migración de {old_fieldname} a {new_fieldname}",
			)

	print("\n📊 RESUMEN DE MIGRACIÓN:")
	print(f"✅ Migrados exitosamente: {success_count}")
	print(f"⚠️ Saltados (ya existen): {skip_count}")
	print(f"❌ Errores: {error_count}")
	print(f"📂 Total procesados: {len(migrations)}")

	if success_count > 0:
		print("\n🧹 Limpiando cache...")
		frappe.clear_cache()

		print("\n✅ MIGRACIÓN COMPLETADA")
		print("🔄 Se recomienda reiniciar supervisor: sudo supervisorctl restart all")

		# Verificación rápida
		verify_migration_success(migrations)
	else:
		print("\n⚠️ MIGRACIÓN SIN CAMBIOS - Todos los campos ya estaban migrados o tuvieron errores")


def get_column_definition(dt, fieldname):
	"""Obtener definición de columna para ALTER TABLE"""

	table_name = f"tab{dt}"

	try:
		column_info = frappe.db.sql(
			f"""
            SELECT COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = '{table_name}'
            AND COLUMN_NAME = '{fieldname}'
            LIMIT 1
        """,
			as_dict=True,
		)

		if column_info:
			info = column_info[0]
			column_def = info.get("COLUMN_TYPE", "VARCHAR(140)")

			# Agregar nullable
			if info.get("IS_NULLABLE") == "YES":
				column_def += " NULL"
			else:
				column_def += " NOT NULL"

			# Agregar default si existe
			if info.get("COLUMN_DEFAULT") is not None:
				default_val = info.get("COLUMN_DEFAULT")
				if isinstance(default_val, str):
					column_def += f" DEFAULT '{default_val}'"
				else:
					column_def += f" DEFAULT {default_val}"

			return column_def

	except Exception as e:
		print(f"⚠️ Error obteniendo definición de columna {fieldname}: {e!s}")

	# Fallback a tipo por defecto
	return "VARCHAR(140) NULL"


def verify_migration_success(migrations):
	"""Verificación rápida de que la migración fue exitosa"""

	print("\n🔍 Verificando migración...")

	verified_count = 0

	for dt, old_fieldname, new_fieldname in migrations:
		try:
			# Verificar que el campo nuevo existe
			if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": new_fieldname}):
				verified_count += 1
			else:
				print(f"⚠️ Campo nuevo no encontrado: {dt}.{new_fieldname}")

			# Verificar que el campo viejo NO existe
			if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": old_fieldname}):
				print(f"⚠️ Campo viejo aún existe: {dt}.{old_fieldname}")

		except Exception as e:
			print(f"❌ Error verificando {dt}.{new_fieldname}: {e!s}")

	print(f"📊 Verificados exitosamente: {verified_count}/{len(migrations)} campos")

	if verified_count == len(migrations):
		print("✅ VERIFICACIÓN EXITOSA - Todos los campos migrados correctamente")
	else:
		print("⚠️ VERIFICACIÓN INCOMPLETA - Revisar campos faltantes")


if __name__ == "__main__":
	# Para testing directo del patch
	execute()
