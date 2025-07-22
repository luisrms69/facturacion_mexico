# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Instalación y configuración del módulo Multi-Sucursal
Sprint 6: Sistema multi-sucursal + addendas genéricas + UOM-SAT
"""

import frappe
from frappe import _


def after_app_install():
	"""Ejecutar después de instalar la app"""
	setup_multi_sucursal()


def setup_multi_sucursal():
	"""Configurar módulo multi-sucursal"""
	print("🚀 Configurando módulo Multi-Sucursal...")

	# Crear custom fields para Branch
	setup_branch_custom_fields()

	# Agregar hooks necesarios
	setup_branch_hooks()

	print("✅ Módulo Multi-Sucursal configurado exitosamente")


def setup_branch_custom_fields():
	"""Configurar custom fields para Branch DocType"""
	try:
		from .custom_fields.branch_fiscal_fields import create_branch_fiscal_custom_fields

		result = create_branch_fiscal_custom_fields()
		if result:
			print("✅ Custom fields para Branch creados")
		else:
			print("⚠️  Error creando custom fields para Branch")

	except Exception as e:
		print(f"❌ Error configurando custom fields: {e!s}")
		frappe.log_error(f"Error setting up branch custom fields: {e!s}", "Multi Sucursal Setup")


def setup_branch_hooks():
	"""Configurar hooks para Branch DocType"""
	try:
		# Los hooks se configuran en hooks.py de la app principal
		# Aquí solo verificamos que estén disponibles las funciones

		from .custom_fields.branch_fiscal_fields import (
			after_branch_insert,
			on_branch_update,
			validate_branch_fiscal_configuration,
		)

		print("✅ Hooks de Branch configurados")

	except Exception as e:
		print(f"❌ Error configurando hooks: {e!s}")
		frappe.log_error(f"Error setting up branch hooks: {e!s}", "Multi Sucursal Setup")


def validate_installation():
	"""Validar que la instalación esté correcta"""
	try:
		# Verificar que existan los custom fields
		required_fields = [
			"fm_enable_fiscal",
			"fm_lugar_expedicion",
			"fm_serie_pattern",
			"fm_folio_start",
			"fm_folio_current",
			"fm_folio_end",
			"fm_share_certificates",
		]

		missing_fields = []
		for field in required_fields:
			if not frappe.db.exists("Custom Field", {"dt": "Branch", "fieldname": field}):
				missing_fields.append(field)

		if missing_fields:
			print(f"⚠️  Campos faltantes en Branch: {missing_fields}")
			return False

		# Verificar que exista el DocType
		if not frappe.db.exists("DocType", "Configuracion Fiscal Sucursal"):
			print("⚠️  DocType 'Configuracion Fiscal Sucursal' no encontrado")
			return False

		print("✅ Instalación validada correctamente")
		return True

	except Exception as e:
		print(f"❌ Error validando instalación: {e!s}")
		return False


if __name__ == "__main__":
	# Para testing manual
	setup_multi_sucursal()
	validate_installation()
