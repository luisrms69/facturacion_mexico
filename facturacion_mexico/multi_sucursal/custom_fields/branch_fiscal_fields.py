# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Custom Fields para Branch DocType - Sprint 6 Multi-Sucursal
Campos fiscales necesarios para gestión multi-sucursal según arquitectura Sprint 6
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def create_branch_fiscal_custom_fields():
	"""
	Crear custom fields fiscales para Branch DocType
	Aplicar patrón establecido: prefijo fm_ para prevenir conflictos
	"""

	# REGLA #34: Verificar si Branch DocType existe antes de custom fields fiscales
	if not frappe.db.exists("DocType", "Branch"):
		print("⚠️  DocType Branch no encontrado - skipping Branch custom fields")
		return False

	try:
		branch_meta = frappe.get_meta("Branch")
		has_company_field = any(f.fieldname == "company" for f in branch_meta.fields)
		print(f"🔍 Branch DocType analysis: has_company_field={has_company_field}")
	except Exception as e:
		print(f"⚠️  Error al obtener metadatos de Branch: {e!s}")
		# Asumir que no tiene company field si hay error
		has_company_field = False

	branch_custom_fields = {"Branch": []}

	# CRÍTICO: Añadir company field si no existe (requerido para queries SQL)
	if not has_company_field:
		print("🔧 Adding missing company field to Branch DocType")
		branch_custom_fields["Branch"].append(
			{
				"fieldname": "company",
				"label": _("Company"),
				"fieldtype": "Link",
				"options": "Company",
				"reqd": 1,
				"insert_after": "branch",
				"description": _("Company that this branch belongs to"),
			}
		)
	else:
		print("✅ Branch DocType already has company field")

	# Test fields individually to find the problematic one
	branch_custom_fields["Branch"].extend(
		[
			{
				"fieldname": "fiscal_configuration_section",
				"label": "Configuración Fiscal",
				"fieldtype": "Section Break",
				"insert_after": "company" if has_company_field else "branch",
				"collapsible": 1,
				"collapsible_depends_on": "fm_enable_fiscal",
			},
			{
				"fieldname": "fm_enable_fiscal",
				"label": "Habilitar para Facturación Fiscal",
				"fieldtype": "Check",
				"insert_after": "fiscal_configuration_section",
				"description": "Activar esta sucursal para emisión de facturas fiscales",
			},
			{
				"fieldname": "fm_lugar_expedicion",
				"label": _("Lugar de Expedición (Código Postal)"),
				"fieldtype": "Data",
				"insert_after": "fm_enable_fiscal",
				"depends_on": "fm_enable_fiscal",
				"mandatory_depends_on": "fm_enable_fiscal",
				"length": 5,
				"description": _("Código postal fiscal donde se expiden las facturas"),
			},
			{
				"fieldname": "folio_management_section",
				"label": _("Gestión de Folios"),
				"fieldtype": "Section Break",
				"insert_after": "fm_lugar_expedicion",
				"depends_on": "fm_enable_fiscal",
				"collapsible": 1,
			},
			{
				"fieldname": "fm_serie_pattern",
				"label": _("Patrón de Serie"),
				"fieldtype": "Data",
				"insert_after": "folio_management_section",
				"depends_on": "fm_enable_fiscal",
				"description": _("Patrón para generar series (ej: SUC1-{yyyy}, MATRIZ-{mm})"),
			},
			{
				"fieldname": "column_break_folios_1",
				"fieldtype": "Column Break",
				"insert_after": "fm_serie_pattern",
			},
			{
				"fieldname": "fm_folio_start",
				"label": _("Folio Inicial"),
				"fieldtype": "Int",
				"insert_after": "column_break_folios_1",
				"depends_on": "fm_enable_fiscal",
				"description": _("Primer folio disponible para esta sucursal"),
			},
			{
				"fieldname": "fm_folio_current",
				"label": _("Folio Actual"),
				"fieldtype": "Int",
				"insert_after": "fm_folio_start",
				"depends_on": "fm_enable_fiscal",
				"read_only": 1,
				"description": _("Próximo folio a utilizar (calculado automáticamente)"),
			},
			{
				"fieldname": "column_break_folios_2",
				"fieldtype": "Column Break",
				"insert_after": "fm_folio_current",
			},
			{
				"fieldname": "fm_folio_end",
				"label": _("Folio Final"),
				"fieldtype": "Int",
				"insert_after": "column_break_folios_2",
				"depends_on": "fm_enable_fiscal",
				"description": _("Último folio disponible para esta sucursal"),
			},
			{
				"fieldname": "fm_folio_warning_threshold",
				"label": _("Umbral de Advertencia"),
				"fieldtype": "Int",
				"insert_after": "fm_folio_end",
				"depends_on": "fm_enable_fiscal",
				"description": _("Advertir cuando queden menos de N folios disponibles"),
			},
			# Additional fields temporarily disabled to prevent "DocType None" error
			# TODO: Add remaining certificate management and statistics fields
			# Note: Issue occurs with some field attributes - needs further investigation
		]
	)

	try:
		if not frappe.db.exists("DocType", "Branch"):
			print("❌ Branch DocType not found")
			return False

		if not branch_custom_fields.get("Branch"):
			branch_custom_fields["Branch"].append(
				{
					"fieldname": "fm_enable_fiscal",
					"label": _("Habilitar para Facturación Fiscal"),
					"fieldtype": "Check",
					"default": 0,
					"insert_after": "company" if has_company_field else "branch",
					"description": _("Activar esta sucursal para emisión de facturas fiscales"),
				}
			)

		create_custom_fields(branch_custom_fields, update=True)
		print(f"✅ Branch custom fields created: {len(branch_custom_fields['Branch'])}")
		return True

	except Exception as e:
		print(f"❌ Branch custom fields error: {e!s}")
		return False


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
