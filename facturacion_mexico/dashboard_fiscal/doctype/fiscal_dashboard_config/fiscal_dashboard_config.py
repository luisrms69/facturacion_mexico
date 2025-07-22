# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class FiscalDashboardConfig(Document):
	"""Configuración global del Dashboard Fiscal"""

	def validate(self):
		"""Validar configuración del dashboard"""
		self.validate_intervals()
		self.validate_json_config()

	def validate_intervals(self):
		"""Validar que los intervalos sean lógicos"""
		if self.refresh_interval and self.refresh_interval < 30:
			frappe.throw(_("El intervalo de actualización no puede ser menor a 30 segundos"))

		if self.cache_duration and self.cache_duration < 300:
			frappe.throw(_("La duración del cache no puede ser menor a 5 minutos (300 segundos)"))

		# Validar que el cache sea al menos 2x el refresh interval
		if self.cache_duration and self.refresh_interval:
			if self.cache_duration < (self.refresh_interval * 2):
				frappe.throw(
					_("La duración del cache debe ser al menos el doble del intervalo de actualización")
				)

	def validate_json_config(self):
		"""Validar configuración JSON del layout"""
		if self.default_widgets_layout:
			try:
				import json

				layout_data = (
					json.loads(self.default_widgets_layout)
					if isinstance(self.default_widgets_layout, str)
					else self.default_widgets_layout
				)

				# Validar estructura básica
				if not isinstance(layout_data, dict):
					frappe.throw(_("El layout debe ser un objeto JSON válido"))

				# Validar que tenga estructura esperada
				if "default_layout" in layout_data:
					self.validate_widget_layout(layout_data["default_layout"])

			except (json.JSONDecodeError, TypeError) as e:
				frappe.throw(_("Configuración JSON inválida en layout de widgets: {0}").format(str(e)))

	def validate_widget_layout(self, layout_list):
		"""Validar estructura del layout de widgets"""
		if not isinstance(layout_list, list):
			frappe.throw(_("El layout debe ser una lista de widgets"))

		for widget in layout_list:
			if not isinstance(widget, dict):
				continue

			# Validar campos requeridos
			required_fields = ["code", "position"]
			for field in required_fields:
				if field not in widget:
					frappe.throw(_("Widget faltante campo requerido: {0}").format(field))

			# Validar posición
			position = widget.get("position", {})
			if isinstance(position, dict):
				for pos_field in ["row", "col", "width", "height"]:
					if pos_field in position:
						value = position[pos_field]
						if not isinstance(value, int) or value < 1 or value > 4:
							frappe.throw(_("Posición {0} debe estar entre 1 y 4").format(pos_field))

	def on_update(self):
		"""Acciones después de actualizar configuración"""
		# Invalidar cache relacionado
		try:
			from facturacion_mexico.dashboard_fiscal.cache_manager import DashboardCache

			DashboardCache.invalidate_pattern("dashboard_config")
			DashboardCache.invalidate_pattern("dashboard_main")
		except ImportError:
			pass

		# Log del cambio de configuración
		frappe.logger().info("Configuración del Dashboard Fiscal actualizada")

	@staticmethod
	def get_config():
		"""Obtener configuración actual del dashboard de forma segura"""
		try:
			config = frappe.get_single("Fiscal Dashboard Config")
			return {
				"refresh_interval": config.refresh_interval or 300,
				"enable_auto_refresh": bool(config.enable_auto_refresh),
				"cache_duration": config.cache_duration or 3600,
				"performance_mode": bool(config.performance_mode),
				"default_period": config.default_period or "month",
				"dashboard_theme": config.dashboard_theme or "light",
				"show_trend_indicators": bool(config.show_trend_indicators),
				"enable_drill_down": bool(config.enable_drill_down),
				"show_monetary_in_thousands": bool(config.show_monetary_in_thousands),
				"default_widgets_layout": config.default_widgets_layout,
				"enable_alerts": bool(config.enable_alerts),
				"alert_check_frequency": config.alert_check_frequency or "15min",
			}
		except Exception:
			# Retornar configuración por defecto si no existe
			return {
				"refresh_interval": 300,
				"enable_auto_refresh": True,
				"cache_duration": 3600,
				"performance_mode": False,
				"default_period": "month",
				"dashboard_theme": "light",
				"show_trend_indicators": True,
				"enable_drill_down": True,
				"show_monetary_in_thousands": False,
				"default_widgets_layout": None,
				"enable_alerts": True,
				"alert_check_frequency": "15min",
			}

	@staticmethod
	def create_default_config():
		"""Crear configuración por defecto si no existe"""
		try:
			if not frappe.db.exists("Fiscal Dashboard Config", "Fiscal Dashboard Config"):
				# Configuración por defecto con layout básico
				default_layout = {
					"default_layout": [
						{
							"code": "fiscal_health_score",
							"position": {"row": 1, "col": 1, "width": 4, "height": 1},
						},
						{
							"code": "timbrado_overview",
							"position": {"row": 2, "col": 1, "width": 2, "height": 1},
						},
						{"code": "ppd_overview", "position": {"row": 2, "col": 3, "width": 2, "height": 1}},
						{"code": "alerts_panel", "position": {"row": 3, "col": 1, "width": 4, "height": 1}},
					]
				}

				default_config = frappe.get_doc(
					{
						"doctype": "Fiscal Dashboard Config",
						"refresh_interval": 300,
						"enable_auto_refresh": 1,
						"cache_duration": 3600,
						"performance_mode": 0,
						"default_period": "month",
						"dashboard_theme": "light",
						"show_trend_indicators": 1,
						"enable_drill_down": 1,
						"show_monetary_in_thousands": 0,
						"default_widgets_layout": default_layout,
						"enable_alerts": 1,
						"alert_check_frequency": "15min",
					}
				)

				default_config.insert(ignore_permissions=True)
				frappe.db.commit()

				frappe.logger().info("Configuración por defecto del Dashboard Fiscal creada")

		except Exception as e:
			frappe.logger().error(f"Error creando configuración por defecto del dashboard: {e}")


def get_dashboard_config():
	"""Función auxiliar para obtener configuración (para compatibilidad)"""
	return FiscalDashboardConfig.get_config()
