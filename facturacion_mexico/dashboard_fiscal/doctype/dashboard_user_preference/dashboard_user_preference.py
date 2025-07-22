# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import json
from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document


class DashboardUserPreference(Document):
	def validate(self):
		"""Validaciones de las preferencias del usuario"""
		self.validate_unique_user()
		self.validate_refresh_interval()
		self.validate_layout_json()

	def validate_unique_user(self):
		"""Asegurar que solo exista una preferencia por usuario"""
		if self.is_new():
			existing = frappe.db.exists("Dashboard User Preference", {"user": self.user})
			if existing and existing != self.name:
				frappe.throw(_("Ya existe una configuración para el usuario {0}").format(self.user))

	def validate_refresh_interval(self):
		"""Validar intervalo de refresh"""
		if self.auto_refresh_enabled and self.refresh_interval:
			if self.refresh_interval < 30:
				frappe.throw(_("El intervalo de refresh no puede ser menor a 30 segundos"))
			elif self.refresh_interval > 3600:
				frappe.throw(_("El intervalo de refresh no puede ser mayor a 1 hora"))

	def validate_layout_json(self):
		"""Validar que el JSON del layout sea válido"""
		if self.dashboard_layout:
			try:
				if isinstance(self.dashboard_layout, str):
					json.loads(self.dashboard_layout)
			except json.JSONDecodeError:
				frappe.throw(_("El layout del dashboard contiene JSON inválido"))

	def before_save(self):
		"""Acciones antes de guardar"""
		# Actualizar último acceso si es una actualización
		if not self.is_new():
			self.last_viewed = datetime.now()

	def get_layout_config(self):
		"""Obtener configuración de layout parseada"""
		if self.dashboard_layout:
			if isinstance(self.dashboard_layout, str):
				return json.loads(self.dashboard_layout)
			return self.dashboard_layout
		return self.get_default_layout()

	def get_default_layout(self):
		"""Obtener layout por defecto"""
		return {
			"grid": "4x4",
			"widgets": [
				{"code": "fiscal_health_score", "position": {"row": 1, "col": 1, "width": 4, "height": 1}},
				{"code": "timbrado_overview", "position": {"row": 2, "col": 1, "width": 2, "height": 1}},
				{"code": "ppd_overview", "position": {"row": 2, "col": 3, "width": 2, "height": 1}},
				{"code": "alerts_panel", "position": {"row": 3, "col": 1, "width": 4, "height": 1}},
			],
			"theme": self.dashboard_theme or "Light",
			"auto_refresh": self.auto_refresh_enabled,
			"refresh_interval": self.refresh_interval or 300,
		}

	def update_layout(self, new_layout):
		"""Actualizar layout del dashboard"""
		if isinstance(new_layout, dict):
			self.dashboard_layout = json.dumps(new_layout)
		else:
			self.dashboard_layout = new_layout
		self.save()

	def add_favorite_widget(self, widget_code):
		"""Agregar widget a favoritos"""
		# Esta función se usaría con el child table Dashboard Widget Favorite
		# cuando se implemente ese DocType
		pass

	def hide_widget(self, widget_code):
		"""Ocultar un widget"""
		# Esta función se usaría con el child table Dashboard Widget Hidden
		# cuando se implemente ese DocType
		pass

	def get_notification_settings(self):
		"""Obtener configuraciones de notificaciones"""
		if self.notification_preferences:
			if isinstance(self.notification_preferences, str):
				return json.loads(self.notification_preferences)
			return self.notification_preferences

		# Configuración por defecto
		return {
			"alert_types": ["Error", "Warning"],
			"modules": ["Timbrado", "PPD"],
			"email_enabled": self.email_digest_enabled,
			"mobile_enabled": self.mobile_notifications,
			"frequency": self.alert_frequency or "Every 15 minutes",
		}


@frappe.whitelist()
def get_user_preferences(user=None):
	"""Obtener preferencias de usuario (API pública)"""
	if not user:
		user = frappe.session.user

	preferences = frappe.db.exists("Dashboard User Preference", {"user": user})

	if preferences:
		doc = frappe.get_doc("Dashboard User Preference", preferences)
		return {
			"success": True,
			"data": {
				"layout": doc.get_layout_config(),
				"theme": doc.dashboard_theme,
				"auto_refresh": doc.auto_refresh_enabled,
				"refresh_interval": doc.refresh_interval,
				"date_range": doc.custom_date_range,
				"notifications": doc.get_notification_settings(),
			},
		}
	else:
		# Crear preferencias por defecto
		default_pref = frappe.new_doc("Dashboard User Preference")
		default_pref.user = user
		default_pref.insert()

		return {
			"success": True,
			"data": {
				"layout": default_pref.get_default_layout(),
				"theme": "Light",
				"auto_refresh": True,
				"refresh_interval": 300,
				"date_range": "This Month",
				"notifications": default_pref.get_notification_settings(),
			},
		}


@frappe.whitelist()
def save_user_layout(layout_data):
	"""Guardar layout personalizado del usuario"""
	user = frappe.session.user

	try:
		# Validar que el layout_data sea JSON válido
		if isinstance(layout_data, str):
			layout_data = json.loads(layout_data)

		preferences = frappe.db.exists("Dashboard User Preference", {"user": user})

		if preferences:
			doc = frappe.get_doc("Dashboard User Preference", preferences)
		else:
			doc = frappe.new_doc("Dashboard User Preference")
			doc.user = user

		doc.update_layout(layout_data)

		return {"success": True, "message": _("Layout guardado exitosamente")}

	except Exception as e:
		frappe.log_error(f"Error guardando layout de usuario: {e!s}")
		return {"success": False, "message": _("Error al guardar layout: {0}").format(str(e))}
