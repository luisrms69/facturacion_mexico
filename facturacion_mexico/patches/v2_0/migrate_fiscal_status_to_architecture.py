# Migration patch: Estados fiscales legacy → Arquitectura resiliente
# Fecha: 2025-08-07
# Propósito: Migrar datos existentes a nuevos estados arquitectura según TAREA_2_4_VALIDACION_FLUJOS_CRITICOS.md

import frappe


def execute():
	"""
	Migrar estados fiscales de legacy a arquitectura resiliente.

	EQUIVALENCIAS DOCUMENTADAS:
	- "Pendiente" → "BORRADOR"
	- "Timbrada" → "TIMBRADO"
	- "Cancelada" → "CANCELADO"
	- "Error" → "ERROR"
	- "Solicitud Cancelación" → "PENDIENTE_CANCELACION"
	"""

	# Mapeo estados legacy → arquitectura
	status_mapping = {
		"Pendiente": "BORRADOR",
		"Timbrada": "TIMBRADO",
		"Cancelada": "CANCELADO",
		"Error": "ERROR",
		"Solicitud Cancelación": "PENDIENTE_CANCELACION",
	}

	try:
		frappe.logger().info("🚀 Iniciando migración estados fiscales a arquitectura resiliente...")

		# Migrar DocType: Factura Fiscal Mexico
		ffm_updated = 0
		for old_status, new_status in status_mapping.items():
			frappe.db.sql(
				"""
				UPDATE `tabFactura Fiscal Mexico`
				SET fm_fiscal_status = %s
				WHERE fm_fiscal_status = %s
			""",
				(new_status, old_status),
			)

			count = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
			if count > 0:
				ffm_updated += count
				frappe.logger().info(
					f"✅ Factura Fiscal Mexico: {count} registros {old_status} → {new_status}"
				)

		# Migrar DocType: Sales Invoice
		si_updated = 0
		for old_status, new_status in status_mapping.items():
			frappe.db.sql(
				"""
				UPDATE `tabSales Invoice`
				SET fm_fiscal_status = %s
				WHERE fm_fiscal_status = %s
			""",
				(new_status, old_status),
			)

			count = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
			if count > 0:
				si_updated += count
				frappe.logger().info(f"✅ Sales Invoice: {count} registros {old_status} → {new_status}")

		# Commit cambios
		frappe.db.commit()

		# Resultado final
		total_updated = ffm_updated + si_updated
		frappe.logger().info(f"🎯 Migración completada: {total_updated} registros actualizados")
		frappe.logger().info(f"   - Factura Fiscal Mexico: {ffm_updated} registros")
		frappe.logger().info(f"   - Sales Invoice: {si_updated} registros")

		print(f"✅ PATCH EJECUTADO: {total_updated} estados fiscales migrados a arquitectura resiliente")

	except Exception as e:
		frappe.logger().error(f"❌ Error en migración estados fiscales: {e}")
		frappe.db.rollback()
		raise e
