# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def get_context(context):
	"""Contexto para la página del Dashboard Fiscal"""

	# Verificar permisos
	if not frappe.has_permission("Dashboard Widget Config", "read"):
		frappe.throw(_("No tiene permisos para acceder al Dashboard Fiscal"))

	# Configuración básica
	context.no_cache = 1
	context.show_sidebar = True
	context.page_title = "Dashboard Fiscal"

	# Obtener empresa por defecto
	user_prefs = get_user_dashboard_preferences()
	default_company = user_prefs.get("company") or frappe.defaults.get_user_default("Company")

	# Información del contexto
	context.update(
		{
			"default_company": default_company,
			"user_preferences": user_prefs,
			"dashboard_config": get_dashboard_configuration(),
			"available_companies": get_available_companies(),
			"user_roles": frappe.get_roles(frappe.session.user),
			"refresh_interval": user_prefs.get("refresh_interval", 300),
			"theme": user_prefs.get("theme", "Light"),
		}
	)


def get_user_dashboard_preferences():
	"""Obtener preferencias de dashboard del usuario actual"""
	user = frappe.session.user

	try:
		prefs = frappe.db.exists("Dashboard User Preference", {"user": user})
		if prefs:
			doc = frappe.get_doc("Dashboard User Preference", prefs)
			return {
				"company": doc.default_company,
				"theme": doc.dashboard_theme,
				"auto_refresh": doc.auto_refresh_enabled,
				"refresh_interval": doc.refresh_interval,
				"date_range": doc.custom_date_range,
				"layout": doc.get_layout_config(),
			}
	except Exception:
		pass

	# Valores por defecto
	return {
		"company": frappe.defaults.get_user_default("Company"),
		"theme": "Light",
		"auto_refresh": True,
		"refresh_interval": 300,
		"date_range": "This Month",
		"layout": get_default_layout(),
	}


def get_dashboard_configuration():
	"""Obtener configuración global del dashboard"""
	try:
		config = frappe.get_single("Fiscal Dashboard Config")
		return {
			"enabled": True,
			"global_refresh_interval": config.refresh_interval,
			"auto_refresh_enabled": config.enable_auto_refresh,
			"cache_duration": config.cache_duration,
			"show_monetary_in_thousands": config.show_monetary_in_thousands,
			"performance_mode": config.performance_mode,
			"alerts_enabled": config.enable_alerts,
		}
	except Exception:
		# Configuración por defecto si no existe
		return {
			"enabled": True,
			"global_refresh_interval": 300,
			"auto_refresh_enabled": True,
			"cache_duration": 3600,
			"show_monetary_in_thousands": False,
			"performance_mode": False,
			"alerts_enabled": True,
		}


def get_available_companies():
	"""Obtener empresas disponibles para el usuario"""
	companies = []

	try:
		# Obtener empresas basadas en permisos del usuario
		companies = frappe.get_all(
			"Company",
			fields=["name", "company_name", "default_currency"],
			filters={"disabled": 0},
			order_by="company_name",
		)

		# Verificar permisos por empresa si es necesario
		user_companies = []
		for company in companies:
			if frappe.has_permission("Company", "read", doc=company.name):
				user_companies.append(company)

		return user_companies

	except Exception as e:
		frappe.log_error(f"Error obteniendo empresas: {e!s}")
		return []


def get_default_layout():
	"""Layout por defecto del dashboard"""
	return {
		"grid": "4x4",
		"widgets": [
			{
				"code": "fiscal_health_score",
				"name": "Score de Salud Fiscal",
				"type": "metric",
				"position": {"row": 1, "col": 1, "width": 4, "height": 1},
				"priority": 1,
			},
			{
				"code": "timbrado_overview",
				"name": "Resumen Timbrado",
				"type": "kpi_grid",
				"position": {"row": 2, "col": 1, "width": 2, "height": 1},
				"priority": 2,
			},
			{
				"code": "ppd_overview",
				"name": "Resumen PPD",
				"type": "kpi_grid",
				"position": {"row": 2, "col": 3, "width": 2, "height": 1},
				"priority": 3,
			},
			{
				"code": "ereceipts_overview",
				"name": "Resumen E-Receipts",
				"type": "kpi_grid",
				"position": {"row": 3, "col": 1, "width": 2, "height": 1},
				"priority": 4,
			},
			{
				"code": "facturas_globales_overview",
				"name": "Resumen Facturas Globales",
				"type": "kpi_grid",
				"position": {"row": 3, "col": 3, "width": 2, "height": 1},
				"priority": 5,
			},
			{
				"code": "alerts_panel",
				"name": "Alertas Activas",
				"type": "alerts",
				"position": {"row": 4, "col": 1, "width": 4, "height": 1},
				"priority": 6,
			},
		],
	}
