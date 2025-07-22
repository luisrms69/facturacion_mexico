# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def get_context(context):
	"""Configurar contexto para la página del dashboard fiscal"""

	context.no_cache = 1
	context.title = _("Dashboard Fiscal")

	# Verificar permisos
	if not frappe.has_permission("Fiscal Dashboard Config"):
		frappe.throw(_("No tienes permisos para acceder al Dashboard Fiscal"))

	# Obtener configuración del dashboard
	try:
		from facturacion_mexico.dashboard_fiscal.doctype.fiscal_dashboard_config.fiscal_dashboard_config import (
			FiscalDashboardConfig,
		)

		dashboard_config = FiscalDashboardConfig.get_config()
	except Exception:
		# Configuración por defecto si no existe
		dashboard_config = {
			"refresh_interval": 300,
			"cache_duration": 3600,
			"enable_auto_refresh": True,
			"dashboard_theme": "light",
			"performance_mode": False,
		}

	# Obtener layout de widgets
	try:
		from facturacion_mexico.dashboard_fiscal.doctype.dashboard_widget_config.dashboard_widget_config import (
			DashboardWidgetConfig,
		)

		dashboard_layout = DashboardWidgetConfig.get_dashboard_layout()
	except Exception:
		dashboard_layout = {}

	# Obtener módulos disponibles y sus KPIs
	try:
		from facturacion_mexico.dashboard_fiscal.dashboard_registry import DashboardRegistry

		DashboardRegistry.initialize()
		available_modules = list(DashboardRegistry.get_all_kpis().keys())
	except Exception:
		available_modules = []

	# Configurar contexto
	context.dashboard_config = dashboard_config
	context.dashboard_layout = dashboard_layout
	context.available_modules = available_modules
	context.user_company = frappe.defaults.get_user_default("Company")

	# Metadatos para el frontend
	context.meta_data = {
		"api_base": "/api/resource/fiscal-dashboard",
		"refresh_interval": dashboard_config.get("refresh_interval", 300) * 1000,  # Convertir a ms
		"cache_duration": dashboard_config.get("cache_duration", 3600),
		"theme": dashboard_config.get("dashboard_theme", "light"),
		"auto_refresh": dashboard_config.get("enable_auto_refresh", True),
		"performance_mode": dashboard_config.get("performance_mode", False),
	}

	return context
