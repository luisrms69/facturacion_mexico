# Copyright (c) 2025, Frappe Technologies and Contributors
# See license.txt

import json
import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe import _


class TestDashboardUserPreferenceLayer2Integration(unittest.TestCase):
	"""Layer 2: Integration tests para Dashboard User Preference con cache y registry integrado"""

	def setUp(self):
		"""Setup para cada test Layer 2"""
		# Limpiar datos de test previos
		try:
			frappe.db.delete("Dashboard User Preference", {"user": ["like", "%test%"]})
			frappe.db.commit()
		except Exception:
			pass

		# Crear usuario de test si no existe
		self.test_user = "test.dashboard.layer2@example.com"
		if not frappe.db.exists("User", self.test_user):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": self.test_user,
					"first_name": "Test",
					"last_name": "Dashboard Layer2",
					"send_welcome_email": 0,
				}
			)
			user.insert(ignore_permissions=True)

	def tearDown(self):
		"""Cleanup después de cada test"""
		frappe.db.rollback()

	@patch("frappe.cache")
	def test_preference_caching_integration(self, mock_cache):
		"""LAYER 2: Test integración cache preferences con performance optimization"""

		# Mock cache behavior
		mock_cache_instance = MagicMock()
		mock_cache.return_value = mock_cache_instance

		# Mock cached preference data
		cached_preferences = {
			"theme": "dark",
			"auto_refresh": True,
			"refresh_interval": 300,
			"dashboard_layout": json.dumps(
				{"widgets": [{"id": "cached-widget", "position": {"row": 1, "col": 1}}], "version": "1.0"}
			),
			"last_cached": frappe.utils.now(),
		}

		mock_cache_instance.get.return_value = cached_preferences

		# Create preference document
		preference = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": self.test_user,
				"theme": "light",  # Different from cache
				"auto_refresh": 1,
				"refresh_interval": 600,
			}
		)
		preference.insert()

		# Import caching integration
		from facturacion_mexico.dashboard_fiscal.doctype.dashboard_user_preference.dashboard_user_preference import (
			cache_user_preferences,
			get_cached_preferences,
			invalidate_preference_cache,
		)

		# Test cached preference retrieval
		cached_prefs = get_cached_preferences(self.test_user)
		self.assertIsInstance(cached_prefs, dict)
		self.assertEqual(cached_prefs["theme"], "dark")  # From cache
		self.assertEqual(cached_prefs["refresh_interval"], 300)

		# Test preference caching
		new_preferences = {
			"theme": "auto",
			"auto_refresh": False,
			"refresh_interval": 900,
			"custom_settings": {"compact_mode": True},
		}

		cache_result = cache_user_preferences(self.test_user, new_preferences, ttl=1800)
		self.assertTrue(cache_result.get("success"))

		# Test cache invalidation
		invalidation_result = invalidate_preference_cache(self.test_user)
		self.assertTrue(invalidation_result.get("success"))

		# Validate cache interaction
		self.assertTrue(mock_cache_instance.get.called)
		self.assertTrue(mock_cache_instance.set.called)
		self.assertTrue(mock_cache_instance.delete.called)

	@patch("frappe.get_hooks")
	@patch("frappe.call")
	def test_preference_hooks_integration(self, mock_call, mock_get_hooks):
		"""LAYER 2: Test integración hooks preferences con system events"""

		# Mock hooks configuration
		mock_get_hooks.return_value = {
			"dashboard_preference_change": [
				"facturacion_mexico.dashboard_fiscal.hooks.on_preference_change",
				"facturacion_mexico.dashboard_fiscal.hooks.update_dashboard_cache",
			]
		}

		# Mock hook execution results
		mock_call.return_value = {"success": True, "message": "Hooks executed successfully"}

		# Create preference
		preference = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": self.test_user,
				"theme": "dark",
				"auto_refresh": 1,
				"refresh_interval": 300,
				"show_notifications": 1,
			}
		)
		preference.insert()

		# Modify preference to trigger hooks
		preference.theme = "light"
		preference.refresh_interval = 600
		preference.save()

		# Import hooks integration
		from facturacion_mexico.dashboard_fiscal.doctype.dashboard_user_preference.dashboard_user_preference import (
			get_hook_execution_log,
			trigger_preference_change_hooks,
		)

		# Test hook triggering
		hook_result = trigger_preference_change_hooks(preference)
		self.assertIsInstance(hook_result, dict)
		self.assertIn("executed_hooks", hook_result)
		self.assertIn("success_count", hook_result)

		# Test hook execution log
		hook_log = get_hook_execution_log(self.test_user)
		self.assertIsInstance(hook_log, list)

		# Validate hook integration
		self.assertTrue(mock_get_hooks.called)

	@patch("frappe.db.get_list")
	def test_preference_registry_integration(self, mock_get_list):
		"""LAYER 2: Test integración registry preferences con module system"""

		# Mock registry data
		mock_get_list.return_value = [
			{
				"name": "widget_fiscal_overview",
				"widget_type": "kpi_grid",
				"enabled": True,
				"permissions": ["read", "export"],
				"module": "dashboard_fiscal",
			},
			{
				"name": "widget_alerts_panel",
				"widget_type": "alert_list",
				"enabled": True,
				"permissions": ["read", "write"],
				"module": "dashboard_fiscal",
			},
			{
				"name": "widget_compliance_chart",
				"widget_type": "line_chart",
				"enabled": False,
				"permissions": ["read"],
				"module": "compliance_tracking",
			},
		]

		# Create preference with complex layout
		complex_layout = {
			"version": "1.2",
			"widgets": [
				{"id": "widget_fiscal_overview", "enabled": True, "position": {"row": 1, "col": 1}},
				{"id": "widget_alerts_panel", "enabled": True, "position": {"row": 1, "col": 2}},
				{"id": "widget_compliance_chart", "enabled": False, "position": {"row": 2, "col": 1}},
			],
			"global_settings": {"theme_mode": "adaptive", "animation_enabled": True},
		}

		preference = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": self.test_user,
				"theme": "auto",
				"dashboard_layout": json.dumps(complex_layout),
				"auto_refresh": 1,
				"refresh_interval": 300,
			}
		)
		preference.insert()

		# Import registry integration
		from facturacion_mexico.dashboard_fiscal.doctype.dashboard_user_preference.dashboard_user_preference import (
			filter_enabled_widgets,
			get_available_widgets,
			validate_layout_with_registry,
		)

		# Test layout validation with registry
		validation_result = validate_layout_with_registry(preference.get_layout_config())
		self.assertIsInstance(validation_result, dict)
		self.assertIn("valid_widgets", validation_result)
		self.assertIn("invalid_widgets", validation_result)

		# Should identify enabled widgets
		valid_widgets = validation_result["valid_widgets"]
		self.assertGreater(len(valid_widgets), 0)

		# Test available widgets retrieval
		available_widgets = get_available_widgets(self.test_user)
		self.assertIsInstance(available_widgets, list)
		self.assertGreater(len(available_widgets), 0)

		# Test enabled widget filtering
		enabled_widgets = filter_enabled_widgets(preference.get_layout_config())
		self.assertIsInstance(enabled_widgets, list)

		# Validate business logic
		enabled_widget_ids = [w["id"] for w in enabled_widgets]
		self.assertIn("widget_fiscal_overview", enabled_widget_ids)
		self.assertIn("widget_alerts_panel", enabled_widget_ids)
		self.assertNotIn("widget_compliance_chart", enabled_widget_ids)  # Disabled

	@patch("frappe.session")
	@patch("frappe.db.get_value")
	def test_preference_personalization_integration(self, mock_get_value, mock_session):
		"""LAYER 2: Test integración personalización preferences con user context"""

		# Mock session data
		mock_session.user = self.test_user
		mock_session.data = {
			"user_roles": ["Dashboard User", "System User"],
			"company": "Test Company",
			"user_timezone": "America/Mexico_City",
			"user_language": "es",
		}

		# Mock user profile data
		mock_get_value.side_effect = lambda doctype, name, field: {
			("User", self.test_user, "time_zone"): "America/Mexico_City",
			("User", self.test_user, "language"): "es",
			("User", self.test_user, "role_profile"): "Dashboard User",
		}.get((doctype, name, field))

		# Create personalized preference
		preference = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": self.test_user,
				"theme": "auto",
				"auto_refresh": 1,
				"refresh_interval": 300,
				"show_notifications": 1,
				"notification_email": 1,
				"notification_browser": 1,
			}
		)
		preference.insert()

		# Import personalization integration
		from facturacion_mexico.dashboard_fiscal.doctype.dashboard_user_preference.dashboard_user_preference import (
			adapt_preferences_to_user_profile,
			apply_user_context_personalization,
			get_personalized_defaults,
		)

		# Test user context personalization
		personalization_result = apply_user_context_personalization(preference)
		self.assertIsInstance(personalization_result, dict)
		self.assertIn("applied_personalizations", personalization_result)
		self.assertIn("context_adaptations", personalization_result)

		# Test personalized defaults
		personalized_defaults = get_personalized_defaults(self.test_user)
		self.assertIsInstance(personalized_defaults, dict)
		self.assertIn("theme", personalized_defaults)
		self.assertIn("refresh_interval", personalized_defaults)

		# Test profile adaptation
		profile_adaptations = adapt_preferences_to_user_profile(preference)
		self.assertIsInstance(profile_adaptations, dict)
		self.assertIn("role_based_settings", profile_adaptations)
		self.assertIn("language_settings", profile_adaptations)

		# Validate personalization logic
		self.assertIn("Dashboard User", profile_adaptations["role_based_settings"]["allowed_roles"])

	@patch("frappe.enqueue")
	def test_preference_async_processing_integration(self, mock_enqueue):
		"""LAYER 2: Test procesamiento async preferences con background jobs"""

		# Mock enqueue behavior
		mock_enqueue.return_value = {"job_id": "pref_process_456"}

		# Create preference for async processing
		preference = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": self.test_user,
				"theme": "dark",
				"dashboard_layout": json.dumps(
					{
						"widgets": [
							{"id": "complex_widget_1", "config": {"heavy_computation": True}},
							{"id": "complex_widget_2", "config": {"data_intensive": True}},
						],
						"require_processing": True,
					}
				),
				"auto_refresh": 1,
				"refresh_interval": 180,
			}
		)
		preference.insert()

		# Import async processing
		from facturacion_mexico.dashboard_fiscal.doctype.dashboard_user_preference.dashboard_user_preference import (
			optimize_preference_performance,
			process_preference_layout_async,
			validate_preference_background,
		)

		# Test async layout processing
		async_result = process_preference_layout_async(preference.name, background=True)
		self.assertIsInstance(async_result, dict)
		self.assertIn("job_id", async_result)
		self.assertEqual(async_result["job_id"], "pref_process_456")

		# Test background validation
		validation_job = validate_preference_background(
			preference.name, {"validate_widgets": True, "check_permissions": True, "optimize_layout": True}
		)
		self.assertIsInstance(validation_job, dict)
		self.assertIn("job_scheduled", validation_job)

		# Test performance optimization
		optimization_result = optimize_preference_performance(preference.name)
		self.assertIsInstance(optimization_result, dict)
		self.assertIn("optimization_applied", optimization_result)

		# Validate async integration
		self.assertTrue(mock_enqueue.called)
		self.assertGreater(mock_enqueue.call_count, 0)

		# Validate job parameters
		enqueue_calls = mock_enqueue.call_args_list
		for call in enqueue_calls:
			args, kwargs = call
			self.assertIn("method", kwargs)
			self.assertIn("queue", kwargs)

	@patch("frappe.realtime.emit")
	def test_preference_realtime_sync_integration(self, mock_emit):
		"""LAYER 2: Test sincronización realtime preferences con WebSocket"""

		# Create preference
		preference = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": self.test_user,
				"theme": "light",
				"auto_refresh": 1,
				"refresh_interval": 300,
				"show_notifications": 1,
			}
		)
		preference.insert()

		# Import realtime sync integration
		from facturacion_mexico.dashboard_fiscal.doctype.dashboard_user_preference.dashboard_user_preference import (
			broadcast_preference_change,
			handle_realtime_preference_update,
			sync_preference_realtime,
		)

		# Test realtime sync
		sync_result = sync_preference_realtime(preference)
		self.assertIsInstance(sync_result, dict)
		self.assertIn("sync_success", sync_result)
		self.assertIn("clients_notified", sync_result)

		# Test preference change broadcast
		changes = {"theme": {"old": "light", "new": "dark"}, "refresh_interval": {"old": 300, "new": 600}}

		broadcast_result = broadcast_preference_change(self.test_user, changes)
		self.assertIsInstance(broadcast_result, dict)
		self.assertIn("broadcast_sent", broadcast_result)

		# Test realtime update handling
		update_data = {
			"preference_id": preference.name,
			"changes": changes,
			"timestamp": frappe.utils.now(),
			"source": "user_interface",
		}

		handle_result = handle_realtime_preference_update(update_data)
		self.assertIsInstance(handle_result, dict)
		self.assertIn("update_processed", handle_result)

		# Validate realtime integration
		self.assertTrue(mock_emit.called)
		emit_calls = mock_emit.call_args_list
		for call in emit_calls:
			args, kwargs = call
			self.assertIn("event", kwargs)
			self.assertIn("message", kwargs)


def run_tests():
	"""Función para correr todos los tests de este módulo"""
	import unittest

	loader = unittest.TestLoader()
	suite = loader.loadTestsFromTestCase(TestDashboardUserPreferenceLayer2Integration)
	runner = unittest.TextTestRunner(verbosity=2)
	return runner.run(suite)


if __name__ == "__main__":
	run_tests()
