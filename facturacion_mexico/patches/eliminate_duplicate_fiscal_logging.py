#!/usr/bin/env python3
"""
Patch para eliminar sistema duplicado de logging fiscal (Fiscal Attempt Log)
Mantiene solo FacturAPI Response Log como sistema unificado
"""

import frappe


def execute():
	"""Ejecutar eliminación segura de sistema duplicado de logging fiscal"""

	frappe.logger().info("🔄 INICIANDO ELIMINACION DE LOGGING DUPLICADO")

	# PASO 1: Eliminar Custom Field fm_fiscal_attempts
	eliminate_custom_field()

	# PASO 2: Eliminar DocType Fiscal Attempt Log
	eliminate_doctype()

	# PASO 3: Limpiar referencias en hooks
	clean_hooks_references()

	frappe.logger().info("✅ ELIMINACION DE LOGGING DUPLICADO COMPLETADA")


def eliminate_custom_field():
	"""Eliminar Custom Field fm_fiscal_attempts de Sales Invoice"""
	field_id = "Sales Invoice-fm_fiscal_attempts"

	frappe.logger().info(f"🗑️ Eliminando Custom Field: {field_id}")

	# Verificar que existe antes de eliminar
	if frappe.db.exists("Custom Field", field_id):
		# Crear backup del campo antes de eliminar
		backup_custom_field(field_id)

		# Eliminar Custom Field
		frappe.delete_doc("Custom Field", field_id, force=True)
		frappe.logger().info(f"✅ Custom Field {field_id} eliminado")
	else:
		frappe.logger().info(f"i Custom Field {field_id} no existe - skip")


def eliminate_doctype():
	"""Eliminar DocType Fiscal Attempt Log"""
	doctype_name = "Fiscal Attempt Log"

	frappe.logger().info(f"🗑️ Eliminando DocType: {doctype_name}")

	# Verificar que existe antes de eliminar
	if frappe.db.exists("DocType", doctype_name):
		# Verificar que no tiene datos críticos
		count = frappe.db.count(doctype_name)
		if count > 0:
			frappe.logger().warning(
				f"⚠️ DocType {doctype_name} tiene {count} registros - eliminando de todas formas (funcionalidad duplicada)"
			)

		# Eliminar DocType
		frappe.delete_doc("DocType", doctype_name, force=True)
		frappe.logger().info(f"✅ DocType {doctype_name} eliminado")
	else:
		frappe.logger().info(f"i DocType {doctype_name} no existe - skip")


def clean_hooks_references():
	"""Limpiar referencias en hooks.py si existen"""
	frappe.logger().info("🧹 Limpiando referencias en hooks")

	# Esta función es informativa - las referencias en hooks.py se limpiarán manualmente
	# porque el patch no debe modificar archivos de código fuente
	frappe.logger().info("i Referencias en hooks.py deben limpiarse manualmente después del patch")


def backup_custom_field(field_id):
	"""Crear backup del Custom Field antes de eliminar"""
	try:
		cf = frappe.get_doc("Custom Field", field_id)
		backup_data = cf.as_dict()

		# Guardar backup en archivo temporal
		import datetime
		import json

		timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
		backup_file = f"/tmp/backup_custom_field_{field_id.replace('-', '_')}_{timestamp}.json"

		with open(backup_file, "w", encoding="utf-8") as f:
			json.dump(backup_data, f, indent=2, default=str, ensure_ascii=False)

		frappe.logger().info(f"💾 Backup del Custom Field guardado en: {backup_file}")

	except Exception as e:
		frappe.logger().error(f"❌ Error creando backup del Custom Field: {e}")
		# No fallar el patch por errores de backup


if __name__ == "__main__":
	# Para testing directo
	execute()
