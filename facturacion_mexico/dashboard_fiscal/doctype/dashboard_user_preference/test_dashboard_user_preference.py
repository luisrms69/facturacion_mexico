# Copyright (c) 2025, Frappe Technologies and Contributors
# See license.txt

import json
import unittest

import frappe
from frappe import _


class TestDashboardUserPreference(unittest.TestCase):
	"""Tests Layer 1 para Dashboard User Preference DocType"""

	def setUp(self):
		"""Setup básico para cada test"""
		# Limpiar datos de test previos si la tabla existe
		try:
			frappe.db.delete("Dashboard User Preference", {"user": ["like", "%test%"]})
			frappe.db.commit()
		except Exception:
			# La tabla puede no existir aún, es normal en tests
			pass

		# Crear usuario de test si no existe
		if not frappe.db.exists("User", "test.dashboard@example.com"):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": "test.dashboard@example.com",
					"first_name": "Test",
					"last_name": "Dashboard",
					"send_welcome_email": 0,
				}
			)
			user.insert(ignore_permissions=True)

	def tearDown(self):
		"""Cleanup después de cada test"""
		frappe.db.rollback()

	def test_doctype_creation(self):
		"""Test: Crear una Dashboard User Preference básica"""
		preference = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": "test.dashboard@example.com",
				"theme": "light",
				"auto_refresh": 1,
				"refresh_interval": 300,
				"show_notifications": 1,
				"notification_email": 1,
			}
		)

		preference.insert()
		self.assertEqual(preference.user, "test.dashboard@example.com")
		self.assertEqual(preference.theme, "light")
		self.assertTrue(preference.auto_refresh)

	def test_theme_validation(self):
		"""Test: Validar temas válidos"""
		valid_themes = ["light", "dark", "auto"]

		for theme in valid_themes:
			preference = frappe.get_doc(
				{
					"doctype": "Dashboard User Preference",
					"user": "test.dashboard@example.com",
					"theme": theme,
					"auto_refresh": 1,
					"refresh_interval": 300,
				}
			)
			preference.insert()
			self.assertEqual(preference.theme, theme)
			preference.delete()

	def test_refresh_interval_validation(self):
		"""Test: Validar intervalos de refresh válidos"""
		valid_intervals = [60, 300, 600, 900, 1800]  # Segundos

		for interval in valid_intervals:
			preference = frappe.get_doc(
				{
					"doctype": "Dashboard User Preference",
					"user": "test.dashboard@example.com",
					"theme": "light",
					"auto_refresh": 1,
					"refresh_interval": interval,
				}
			)
			preference.insert()
			self.assertEqual(preference.refresh_interval, interval)
			preference.delete()

	def test_dashboard_layout_json_valid(self):
		"""Test: Dashboard layout JSON válido"""
		layout = {
			"widgets": [
				{"id": "kpi-overview", "position": {"row": 1, "col": 1, "width": 2, "height": 1}},
				{"id": "alerts-panel", "position": {"row": 1, "col": 3, "width": 2, "height": 1}},
			],
			"custom_config": {"show_legend": True, "animation_enabled": False},
		}

		preference = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": "test.dashboard@example.com",
				"theme": "dark",
				"dashboard_layout": json.dumps(layout),
				"auto_refresh": 0,
			}
		)

		preference.insert()
		stored_layout = json.loads(preference.dashboard_layout)
		self.assertEqual(len(stored_layout["widgets"]), 2)
		self.assertEqual(stored_layout["custom_config"]["show_legend"], True)

	def test_dashboard_layout_empty(self):
		"""Test: Dashboard layout vacío es válido"""
		preference = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": "test.dashboard@example.com",
				"theme": "light",
				"auto_refresh": 1,
				"refresh_interval": 300,
			}
		)

		preference.insert()
		# dashboard_layout puede ser None/vacío
		self.assertTrue(preference.dashboard_layout is None or preference.dashboard_layout == "")

	def test_get_layout_config_method(self):
		"""Test: Método get_layout_config"""
		layout = {"test": "config", "widgets": []}

		preference = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": "test.dashboard@example.com",
				"theme": "auto",
				"dashboard_layout": json.dumps(layout),
				"auto_refresh": 1,
				"refresh_interval": 600,
			}
		)

		preference.insert()

		# Test método get_layout_config
		config = preference.get_layout_config()
		self.assertEqual(config["test"], "config")
		self.assertEqual(config["widgets"], [])

	def test_get_layout_config_default(self):
		"""Test: Método get_layout_config con default"""
		preference = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": "test.dashboard@example.com",
				"theme": "light",
				"auto_refresh": 0,
			}
		)

		preference.insert()

		# Sin layout configurado debería devolver default
		config = preference.get_layout_config()
		self.assertIsInstance(config, dict)
		# Debería tener estructura default
		self.assertIn("widgets", config)

	def test_user_uniqueness(self):
		"""Test: Un usuario solo puede tener una preferencia"""
		# Primera preferencia
		preference1 = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": "test.dashboard@example.com",
				"theme": "light",
				"auto_refresh": 1,
				"refresh_interval": 300,
			}
		)
		preference1.insert()

		# Segunda preferencia para el mismo usuario debería fallar
		preference2 = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": "test.dashboard@example.com",
				"theme": "dark",
				"auto_refresh": 0,
				"refresh_interval": 600,
			}
		)

		with self.assertRaises(frappe.DuplicateEntryError):
			preference2.insert()

	def test_notification_settings(self):
		"""Test: Configuración de notificaciones"""
		preference = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": "test.dashboard@example.com",
				"theme": "dark",
				"auto_refresh": 1,
				"refresh_interval": 300,
				"show_notifications": 1,
				"notification_email": 1,
				"notification_browser": 1,
				"alert_sound": 0,
			}
		)

		preference.insert()
		self.assertTrue(preference.show_notifications)
		self.assertTrue(preference.notification_email)
		self.assertTrue(preference.notification_browser)
		self.assertFalse(preference.alert_sound)

	def test_auto_refresh_logic(self):
		"""Test: Lógica de auto refresh"""
		# Con auto refresh habilitado
		preference = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": "test.dashboard@example.com",
				"theme": "light",
				"auto_refresh": 1,
				"refresh_interval": 180,
			}
		)
		preference.insert()

		self.assertTrue(preference.auto_refresh)
		self.assertEqual(preference.refresh_interval, 180)

		# Deshabilitar auto refresh
		preference.auto_refresh = 0
		preference.save()
		self.assertFalse(preference.auto_refresh)

	def test_complex_dashboard_layout(self):
		"""Test: Layout complejo del dashboard"""
		complex_layout = {
			"version": "1.0",
			"grid": {"rows": 4, "cols": 6, "cell_height": 100},
			"widgets": [
				{
					"id": "fiscal-health-overview",
					"type": "kpi_grid",
					"position": {"row": 1, "col": 1, "width": 3, "height": 1},
					"config": {"refresh_rate": 300, "show_trend": True},
				},
				{
					"id": "alert-panel",
					"type": "alert_list",
					"position": {"row": 1, "col": 4, "width": 3, "height": 2},
					"config": {"max_alerts": 10, "auto_dismiss": False},
				},
				{
					"id": "monthly-chart",
					"type": "line_chart",
					"position": {"row": 2, "col": 1, "width": 3, "height": 2},
					"config": {"period": "monthly", "show_legend": True, "animation": False},
				},
			],
			"filters": {"company": "Test Company", "period": "current_month"},
			"user_settings": {"compact_mode": False, "dark_theme_auto": True},
		}

		preference = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": "test.dashboard@example.com",
				"theme": "auto",
				"dashboard_layout": json.dumps(complex_layout),
				"auto_refresh": 1,
				"refresh_interval": 300,
			}
		)

		preference.insert()

		# Verificar que el JSON se guardó y cargó correctamente
		loaded_layout = preference.get_layout_config()
		self.assertEqual(loaded_layout["version"], "1.0")
		self.assertEqual(len(loaded_layout["widgets"]), 3)
		self.assertEqual(loaded_layout["grid"]["rows"], 4)
		self.assertEqual(loaded_layout["filters"]["company"], "Test Company")


def run_tests():
	"""Función para correr todos los tests de este módulo"""
	loader = unittest.TestLoader()
	suite = loader.loadTestsFromTestCase(TestDashboardUserPreference)
	runner = unittest.TextTestRunner(verbosity=2)
	return runner.run(suite)


if __name__ == "__main__":
	run_tests()
