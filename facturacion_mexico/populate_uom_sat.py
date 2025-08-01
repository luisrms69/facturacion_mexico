# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
UOM SAT Population Script - Sprint 6 Phase Final
Poblar UOM nativo de ERPNext con 20 unidades SAT principales
Enfoque híbrido simple: sin custom fields, sin DocTypes adicionales
"""

import frappe
from frappe import _


def run():
	"""
	Poblar UOM nativo con 20 unidades SAT principales.

	Estrategia:
	- Formato: "CODIGO - Descripción" (similar a Mode of Payment SAT)
	- Sin custom fields adicionales
	- Aprovecha sistema UOM nativo ERPNext
	- Protegido contra re-ejecución
	"""

	try:
		# Verificar si ya se ejecutó este script (protección contra re-ejecución)
		# Usar mismo patrón que Mode of Payment: contar por filtro "like"
		existing_sat_uoms = frappe.db.count("UOM", {"uom_name": ["like", "% - %"]})
		if existing_sat_uoms >= 18:  # 90% de las 20 UOMs SAT
			print(f"⚠️  Script ya ejecutado anteriormente. Encontradas {existing_sat_uoms} UOMs SAT")
			print("   Para re-ejecutar, elimine primero las UOMs con formato 'CODIGO - Descripción'")
			return {"created": 0, "updated": 0, "skipped": existing_sat_uoms}

		# 20 UOMs SAT principales seleccionadas
		sat_uoms = [
			{"code": "H87", "name": "Pieza", "symbol": "pza"},
			{"code": "KGM", "name": "Kilogramo", "symbol": "kg"},
			{"code": "GRM", "name": "Gramo", "symbol": "g"},
			{"code": "LTR", "name": "Litro", "symbol": "L"},
			{"code": "MLT", "name": "Mililitro", "symbol": "mL"},
			{"code": "MTR", "name": "Metro", "symbol": "m"},
			{"code": "CMT", "name": "Centímetro", "symbol": "cm"},
			{"code": "MMT", "name": "Milímetro", "symbol": "mm"},
			{"code": "MTK", "name": "Metro cuadrado", "symbol": "m²"},
			{"code": "MTQ", "name": "Metro cúbico", "symbol": "m³"},
			{"code": "HUR", "name": "Hora", "symbol": "hr"},
			{"code": "MIN", "name": "Minuto", "symbol": "min"},
			{"code": "SEC", "name": "Segundo", "symbol": "s"},
			{"code": "DAY", "name": "Día", "symbol": "día"},
			{"code": "E48", "name": "Servicio", "symbol": "servicio"},
			{"code": "ACT", "name": "Actividad", "symbol": "actividad"},
			{"code": "E51", "name": "Trabajo", "symbol": "trabajo"},
			{"code": "MON", "name": "Mes", "symbol": "mes"},
			{"code": "ANN", "name": "Año", "symbol": "año"},
			{"code": "NA", "name": "No Aplica", "symbol": "N/A"},
		]

		created = 0
		updated = 0
		errors = []

		print("🚀 Iniciando población de UOMs SAT...")

		for uom_data in sat_uoms:
			try:
				uom_name = f"{uom_data['code']} - {uom_data['name']}"

				if frappe.db.exists("UOM", uom_name):
					# Asegurar que esté habilitado (similar a Mode of Payment)
					uom_doc = frappe.get_doc("UOM", uom_name)
					if not uom_doc.enabled:
						uom_doc.enabled = 1
						uom_doc.save()
						updated += 1
						print(f"🔄 Habilitado: {uom_name}")
				else:
					# Crear nuevo UOM
					uom_doc = frappe.get_doc(
						{"doctype": "UOM", "uom_name": uom_name, "enabled": 1, "must_be_whole_number": 0}
					)

					uom_doc.insert(ignore_permissions=True)
					created += 1
					print(f"✅ Creado: {uom_name}")

			except Exception as e:
				error_msg = f"Error procesando {uom_data['code']}: {str(e)}"
				errors.append(error_msg)
				print(f"❌ {error_msg}")

		# Commit cambios
		frappe.db.commit()

		result = {"created": created, "updated": updated, "errors": len(errors), "error_details": errors}

		print(f"🎉 UOMs SAT pobladas exitosamente:")
		print(f"   📝 Creadas: {created}")
		print(f"   🔄 Actualizadas: {updated}")
		print(f"   ❌ Errores: {len(errors)}")

		return result

	except Exception as e:
		frappe.log_error(f"Error poblando UOMs SAT: {str(e)}", "UOM SAT Population")
		print(f"💥 Error crítico: {str(e)}")
		return {"error": str(e), "created": 0}


def disable_generic_uoms():
	"""
	Desactivar UOMs genéricas ERPNext preservando las SAT.

	IMPORTANTE: Primero desactiva UOM Conversion Factors, luego UOMs
	"""

	try:
		print("🔧 Desactivando UOM Conversion Factors genéricos...")

		# 1. Desactivar UOM Conversion Factors que involucren UOMs genéricas
		conversion_updates = frappe.db.sql("""
            UPDATE `tabUOM Conversion Factor`
            SET disabled = 1
            WHERE (from_uom NOT LIKE '% - %' OR to_uom NOT LIKE '% - %')
            AND disabled = 0
        """)

		print(f"✅ UOM Conversion Factors desactivados")

		print("🔧 Desactivando UOMs genéricas...")

		# 2. Desactivar UOMs genéricas (que no tienen formato SAT)
		uom_updates = frappe.db.sql("""
            UPDATE `tabUOM`
            SET enabled = 0
            WHERE uom_name NOT LIKE '% - %'
            AND enabled = 1
        """)

		print(f"✅ UOMs genéricas desactivadas")

		# 3. Commit cambios
		frappe.db.commit()

		print("🎉 Desactivación completada exitosamente")

		return {
			"success": True,
			"message": "UOMs genéricas y conversiones desactivadas",
			"conversions_disabled": True,
			"uoms_disabled": True,
		}

	except Exception as e:
		frappe.log_error(f"Error desactivando UOMs genéricas: {str(e)}", "UOM SAT Disable")
		print(f"💥 Error desactivando UOMs: {str(e)}")
		return {"success": False, "error": str(e)}


def create_sat_conversion_factors():
	"""
	Crear factores de conversión básicos entre UOMs SAT.
	Solo conversiones físicamente coherentes.
	"""

	try:
		print("⚖️  Creando factores de conversión SAT...")

		# Conversiones físicamente coherentes
		sat_conversions = [
			# Masa
			{"from": "KGM - Kilogramo", "to": "GRM - Gramo", "factor": 1000},
			{"from": "GRM - Gramo", "to": "KGM - Kilogramo", "factor": 0.001},
			# Longitud
			{"from": "MTR - Metro", "to": "CMT - Centímetro", "factor": 100},
			{"from": "CMT - Centímetro", "to": "MTR - Metro", "factor": 0.01},
			{"from": "MTR - Metro", "to": "MMT - Milímetro", "factor": 1000},
			{"from": "MMT - Milímetro", "to": "MTR - Metro", "factor": 0.001},
			{"from": "CMT - Centímetro", "to": "MMT - Milímetro", "factor": 10},
			{"from": "MMT - Milímetro", "to": "CMT - Centímetro", "factor": 0.1},
			# Volumen
			{"from": "LTR - Litro", "to": "MLT - Mililitro", "factor": 1000},
			{"from": "MLT - Mililitro", "to": "LTR - Litro", "factor": 0.001},
			# Tiempo
			{"from": "HUR - Hora", "to": "MIN - Minuto", "factor": 60},
			{"from": "MIN - Minuto", "to": "HUR - Hora", "factor": 0.01667},
			{"from": "MIN - Minuto", "to": "SEC - Segundo", "factor": 60},
			{"from": "SEC - Segundo", "to": "MIN - Minuto", "factor": 0.01667},
			{"from": "HUR - Hora", "to": "SEC - Segundo", "factor": 3600},
			{"from": "SEC - Segundo", "to": "HUR - Hora", "factor": 0.000278},
			{"from": "ANN - Año", "to": "MON - Mes", "factor": 12},
			{"from": "MON - Mes", "to": "ANN - Año", "factor": 0.08333},
			{"from": "MON - Mes", "to": "DAY - Día", "factor": 30},
			{"from": "DAY - Día", "to": "MON - Mes", "factor": 0.03333},
		]

		created = 0
		updated = 0

		for conversion in sat_conversions:
			try:
				# Verificar que ambas UOMs existan
				if not frappe.db.exists("UOM", conversion["from"]):
					print(f"⚠️  UOM origen no existe: {conversion['from']}")
					continue

				if not frappe.db.exists("UOM", conversion["to"]):
					print(f"⚠️  UOM destino no existe: {conversion['to']}")
					continue

				# Verificar si ya existe la conversión
				existing = frappe.db.exists(
					"UOM Conversion Factor", {"from_uom": conversion["from"], "to_uom": conversion["to"]}
				)

				if existing:
					# Actualizar factor existente
					frappe.db.set_value("UOM Conversion Factor", existing, "value", conversion["factor"])
					frappe.db.set_value("UOM Conversion Factor", existing, "disabled", 0)
					updated += 1
					print(
						f"🔄 Actualizado: {conversion['from']} → {conversion['to']} ({conversion['factor']})"
					)
				else:
					# Crear nueva conversión
					conversion_doc = frappe.get_doc(
						{
							"doctype": "UOM Conversion Factor",
							"from_uom": conversion["from"],
							"to_uom": conversion["to"],
							"value": conversion["factor"],
							"disabled": 0,
						}
					)

					conversion_doc.insert(ignore_permissions=True)
					created += 1
					print(f"✅ Creado: {conversion['from']} → {conversion['to']} ({conversion['factor']})")

			except Exception as e:
				print(f"❌ Error creando conversión {conversion['from']} → {conversion['to']}: {str(e)}")

		frappe.db.commit()

		print(f"🎉 Conversiones SAT completadas:")
		print(f"   📝 Creadas: {created}")
		print(f"   🔄 Actualizadas: {updated}")

		return {
			"success": True,
			"created": created,
			"updated": updated,
			"message": f"Conversiones SAT creadas/actualizadas: {created + updated}",
		}

	except Exception as e:
		frappe.log_error(f"Error creando conversiones SAT: {str(e)}", "UOM SAT Conversions")
		print(f"💥 Error creando conversiones: {str(e)}")
		return {"success": False, "error": str(e)}


def get_uom_sat_status():
	"""
	Obtener estado actual de UOMs SAT para monitoreo.
	"""

	try:
		# Contar UOMs SAT
		sat_uoms = frappe.db.count("UOM", {"uom_name": ["like", "% - %"], "enabled": 1})

		# Contar UOMs genéricas activas
		generic_uoms = frappe.db.count("UOM", {"uom_name": ["not like", "% - %"], "enabled": 1})

		# Contar conversiones SAT
		sat_conversions = frappe.db.sql(
			"""
            SELECT COUNT(*) as count
            FROM `tabUOM Conversion Factor`
            WHERE from_uom LIKE '% - %'
            AND to_uom LIKE '% - %'
            AND disabled = 0
        """,
			as_dict=True,
		)[0]["count"]

		status = {
			"sat_uoms_active": sat_uoms,
			"generic_uoms_active": generic_uoms,
			"sat_conversions_active": sat_conversions,
			"migration_completed": sat_uoms >= 15 and generic_uoms == 0,
		}

		print("📊 Estado actual UOMs SAT:")
		print(f"   ✅ UOMs SAT activas: {sat_uoms}")
		print(f"   ⚠️  UOMs genéricas activas: {generic_uoms}")
		print(f"   🔄 Conversiones SAT activas: {sat_conversions}")
		print(f"   🎯 Migración completada: {'SÍ' if status['migration_completed'] else 'NO'}")

		return status

	except Exception as e:
		frappe.log_error(f"Error obteniendo estado UOMs: {str(e)}", "UOM SAT Status")
		return {"error": str(e)}


# APIs públicas para testing y monitoreo


@frappe.whitelist()
def populate_uoms_api():
	"""API para poblar UOMs SAT"""
	return run()


@frappe.whitelist()
def disable_generic_uoms_api():
	"""API para desactivar UOMs genéricas"""
	return disable_generic_uoms()


@frappe.whitelist()
def create_conversions_api():
	"""API para crear conversiones SAT"""
	return create_sat_conversion_factors()


@frappe.whitelist()
def get_status_api():
	"""API para obtener estado UOMs"""
	return get_uom_sat_status()


# Script de ejecución completa
def execute_full_migration():
	"""
	Ejecutar migración completa UOM-SAT:
	1. Poblar UOMs SAT
	2. Crear conversiones básicas
	3. Desactivar UOMs genéricas
	"""

	print("🚀 INICIANDO MIGRACIÓN COMPLETA UOM-SAT")
	print("=" * 50)

	# Paso 1: Poblar UOMs SAT
	print("\n📋 PASO 1: Poblando UOMs SAT...")
	populate_result = run()

	if populate_result.get("error"):
		print(f"💥 Fallo en población: {populate_result['error']}")
		return populate_result

	# Paso 2: Crear conversiones SAT
	print("\n⚖️  PASO 2: Creando conversiones SAT...")
	conversion_result = create_sat_conversion_factors()

	if not conversion_result.get("success"):
		print(f"⚠️  Advertencia en conversiones: {conversion_result.get('error', 'Error desconocido')}")

	# Paso 3: Desactivar UOMs genéricas
	print("\n🔧 PASO 3: Desactivando UOMs genéricas...")
	disable_result = disable_generic_uoms()

	if not disable_result.get("success"):
		print(f"⚠️  Advertencia desactivando genéricas: {disable_result.get('error', 'Error desconocido')}")

	# Paso 4: Verificar estado final
	print("\n📊 PASO 4: Verificando estado final...")
	status = get_uom_sat_status()

	print("\n🎉 MIGRACIÓN UOM-SAT COMPLETADA")
	print("=" * 50)

	return {
		"populate": populate_result,
		"conversions": conversion_result,
		"disable": disable_result,
		"final_status": status,
		"migration_success": status.get("migration_completed", False),
	}


if __name__ == "__main__":
	# Ejecución desde línea de comandos
	result = execute_full_migration()
	if result.get("migration_success"):
		print("✅ MIGRACIÓN EXITOSA")
	else:
		print("❌ MIGRACIÓN CON PROBLEMAS - Revisar logs")
