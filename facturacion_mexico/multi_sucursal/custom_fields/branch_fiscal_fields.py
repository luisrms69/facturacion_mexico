# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Custom Fields para Branch DocType - Sprint 6 Multi-Sucursal
Campos fiscales necesarios para gestión multi-sucursal según arquitectura Sprint 6
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

# REMOVED: create_branch_fiscal_custom_fields() function
# Custom fields are now managed through fixtures in hooks.py
# This function was eliminated as part of Issue #31 FASE 3 cleanup


def remove_branch_fiscal_custom_fields():
	"""
	Eliminar custom fields fiscales de Branch (para rollback si es necesario)
	"""
	field_names = [
		"fiscal_configuration_section",
		"fm_enable_fiscal",
		"fm_lugar_expedicion",
		"folio_management_section",
		"fm_serie_pattern",
		"column_break_folios_1",
		"fm_folio_start",
		"fm_folio_current",
		"column_break_folios_2",
		"fm_folio_end",
		"fm_folio_warning_threshold",
		"certificate_management_section",
		"fm_share_certificates",
		"fm_certificate_ids",
		"statistics_section",
		"fm_last_invoice_date",
		"column_break_stats_1",
		"fm_monthly_average",
		"column_break_stats_2",
		"fm_days_until_exhaustion",
	]

	try:
		for field_name in field_names:
			if frappe.db.exists("Custom Field", {"dt": "Branch", "fieldname": field_name}):
				frappe.delete_doc("Custom Field", {"dt": "Branch", "fieldname": field_name})

		print("✅ Custom fields fiscales de Branch eliminados")
		return True

	except Exception as e:
		print(f"❌ Error eliminando custom fields: {e!s}")
		frappe.log_error(f"Error removing branch custom fields: {e!s}", "Branch Custom Fields Removal")
		return False


def validate_branch_fiscal_configuration(doc, method):
	"""
	Hook de validación para Branch con configuración fiscal
	Se ejecuta en validate del Branch
	"""
	if not doc.get("fm_enable_fiscal"):
		return

	# Validar lugar de expedición
	if not doc.get("fm_lugar_expedicion"):
		frappe.throw(_("Lugar de expedición es obligatorio para sucursales fiscales"))

	# Validar formato de código postal
	lugar_expedicion = doc.get("fm_lugar_expedicion", "").strip()
	if not lugar_expedicion.isdigit() or len(lugar_expedicion) != 5:
		frappe.throw(_("Lugar de expedición debe ser un código postal de 5 dígitos"))

	# Validar rangos de folios
	folio_start = doc.get("fm_folio_start", 0)
	folio_end = doc.get("fm_folio_end", 0)

	if folio_start < 1:
		frappe.throw(_("Folio inicial debe ser mayor a 0"))

	if folio_end and folio_end <= folio_start:
		frappe.throw(_("Folio final debe ser mayor al folio inicial"))

	# Establecer folio actual si no existe
	if not doc.get("fm_folio_current"):
		doc.fm_folio_current = folio_start

	# REGLA #34: Fortalecer validación con fallbacks robustos
	# Validar umbral de advertencia con defensive handling
	warning_threshold = doc.get("fm_folio_warning_threshold")
	if warning_threshold is None or (isinstance(warning_threshold, int | float) and warning_threshold < 1):
		doc.fm_folio_warning_threshold = 100

	print(f"✅ Branch '{doc.name}' validado para configuración fiscal")


def after_branch_insert(doc, method):
	"""
	Hook después de insertar Branch
	Crear Configuracion Fiscal Sucursal automáticamente si es fiscal
	"""
	if doc.get("fm_enable_fiscal"):
		try:
			# Importar aquí para evitar circular imports
			from facturacion_mexico.multi_sucursal.doctype.configuracion_fiscal_sucursal.configuracion_fiscal_sucursal import (
				create_default_config,
			)

			create_default_config(doc.name)
			print(f"✅ Configuración fiscal creada automáticamente para sucursal '{doc.name}'")

		except Exception as e:
			frappe.log_error(
				f"Error creating default fiscal config for branch {doc.name}: {e!s}", "Branch Auto Config"
			)
			print(f"⚠️  Error creando configuración automática: {e!s}")


def on_branch_update(doc, method):
	"""
	Hook de actualización de Branch
	Sincronizar cambios con Configuracion Fiscal Sucursal
	"""
	if doc.get("fm_enable_fiscal"):
		try:
			# Buscar configuración fiscal existente
			config_name = frappe.db.get_value("Configuracion Fiscal Sucursal", {"branch": doc.name})

			if config_name:
				config_doc = frappe.get_doc("Configuracion Fiscal Sucursal", config_name)

				# Sincronizar campos críticos
				config_doc.serie_fiscal = doc.get("fm_serie_pattern", "")
				config_doc.folio_current = doc.get("fm_folio_current", 0)
				config_doc.folio_warning_threshold = doc.get("fm_folio_warning_threshold", 100)

				config_doc.save()
				print(f"✅ Configuración fiscal sincronizada para '{doc.name}'")

		except Exception as e:
			frappe.log_error(
				f"Error syncing fiscal config for branch {doc.name}: {e!s}", "Branch Config Sync"
			)
