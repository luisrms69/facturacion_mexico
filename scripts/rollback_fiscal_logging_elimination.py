#!/usr/bin/env python3
"""
Script de rollback para revertir eliminación de sistema Fiscal Attempt Log
USAR SOLO SI EL PATCH CAUSÓ PROBLEMAS
"""

import glob
import json
import os

import frappe


def execute():
	"""Revertir eliminación de sistema Fiscal Attempt Log"""

	print("🔄 INICIANDO ROLLBACK DE ELIMINACION FISCAL LOGGING")

	# PASO 1: Restaurar Custom Field desde backup
	restore_custom_field_from_backup()

	# PASO 2: Recrear DocType Fiscal Attempt Log desde fixtures
	restore_doctype_from_git()

	print("✅ ROLLBACK COMPLETADO - Revisar sistema manualmente")


def restore_custom_field_from_backup():
	"""Restaurar Custom Field desde archivo de backup"""
	field_id = "Sales Invoice-fm_fiscal_attempts"

	# Buscar archivo de backup más reciente
	backup_pattern = f"/tmp/backup_custom_field_{field_id.replace('-', '_')}_*.json"
	backup_files = glob.glob(backup_pattern)

	if not backup_files:
		print(f"❌ No se encontró backup para {field_id}")
		return

	# Usar el backup más reciente
	latest_backup = max(backup_files, key=os.path.getctime)
	print(f"📁 Restaurando desde: {latest_backup}")

	try:
		with open(latest_backup, encoding="utf-8") as f:
			backup_data = json.load(f)

		# Crear nuevo Custom Field
		cf = frappe.new_doc("Custom Field")
		cf.update(backup_data)
		cf.insert(ignore_permissions=True)

		print(f"✅ Custom Field {field_id} restaurado")

	except Exception as e:
		print(f"❌ Error restaurando Custom Field: {e}")


def restore_doctype_from_git():
	"""Instrucciones para restaurar DocType desde Git"""
	print("\n📋 INSTRUCCIONES MANUALES PARA RESTAURAR DOCTYPE:")
	print("1. git checkout HEAD~1 -- facturacion_mexico/facturacion_fiscal/doctype/fiscal_attempt_log/")
	print("2. bench --site facturacion.dev migrate")
	print("3. Verificar que el DocType funciona correctamente")


if __name__ == "__main__":
	execute()
