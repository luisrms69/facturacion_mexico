"""
Test Base Dashboard - Testing básico del módulo Dashboard Fiscal
Aplicando Framework de Testing 4-Layer del Custom Fields Migration Sprint
"""

import json
import unittest
from unittest.mock import MagicMock, patch

import frappe

from facturacion_mexico.dashboard_fiscal.cache_manager import DashboardCache
from facturacion_mexico.dashboard_fiscal.dashboard_registry import DashboardRegistry


class TestBaseDashboard(unittest.TestCase):
	"""Tests básicos del sistema de dashboard fiscal"""

	def setUp(self):
		"""Setup para cada test"""
		# Limpiar registry y cache para testing aislado
		DashboardRegistry.reset_registry()
		DashboardCache.clear_all_cache()

	def tearDown(self):
		"""Cleanup después de cada test"""
		DashboardRegistry.reset_registry()
		DashboardCache.clear_all_cache()

	def test_dashboard_registry_initialization(self):
		"""Test inicialización del registry"""
		# Test que el registry se inicializa correctamente
		DashboardRegistry.initialize()

		stats = DashboardRegistry.get_registry_stats()
		self.assertIsInstance(stats, dict)
		self.assertIn("initialized", stats)
		self.assertTrue(stats["initialized"])

	def test_dashboard_registry_kpi_registration(self):
		"""Test registro de KPIs en el registry"""

		# Test registro de KPI
		def test_kpi():
			return {"test": "value"}

		DashboardRegistry.register_kpi("test_module", {"test_kpi": test_kpi})

		# Verificar que se registró
		module_kpis = DashboardRegistry.get_module_kpis("test_module")
		self.assertIn("test_kpi", module_kpis)
		self.assertEqual(module_kpis["test_kpi"], test_kpi)

	def test_dashboard_registry_widget_registration(self):
		"""Test registro de widgets"""
		widget_config = {"code": "test_widget", "name": "Test Widget", "type": "kpi", "module": "test_module"}

		DashboardRegistry.register_widget(widget_config)

		# Verificar registro
		all_widgets = DashboardRegistry.get_all_widgets()
		self.assertIn("test_widget", all_widgets)
		self.assertEqual(all_widgets["test_widget"]["name"], "Test Widget")

	def test_cache_manager_basic_functionality(self):
		"""Test funcionalidad básica del cache manager"""
		# Test función básica de cache
		call_count = 0

		def test_function(param1="default"):
			nonlocal call_count
			call_count += 1
			return f"result_{param1}_{call_count}"

		# Primera llamada - debería ejecutar función
		result1 = DashboardCache.get_or_set("test_key", test_function, ttl=3600, param1="test")
		self.assertEqual(result1, "result_test_1")
		self.assertEqual(call_count, 1)

		# Segunda llamada - debería usar cache
		result2 = DashboardCache.get_or_set("test_key", test_function, ttl=3600, param1="test")
		self.assertEqual(result2, "result_test_1")  # Mismo resultado
		self.assertEqual(call_count, 1)  # No se ejecutó de nuevo

	def test_cache_manager_invalidation(self):
		"""Test invalidación de cache por patrones"""
		# Crear varias entradas de cache
		DashboardCache.get_or_set("test_timbrado", lambda: "data1", ttl=3600)
		DashboardCache.get_or_set("test_ppd", lambda: "data2", ttl=3600)
		DashboardCache.get_or_set("other_module", lambda: "data3", ttl=3600)

		# Verificar que están en cache
		stats = DashboardCache.get_cache_stats()
		self.assertGreater(stats["cache_size"], 0)

		# Invalidar por patrón
		invalidated = DashboardCache.invalidate_pattern("test_")
		self.assertGreaterEqual(invalidated, 2)  # Al menos test_timbrado y test_ppd

	@patch("frappe.get_single")
	def test_dashboard_config_doctype_integration(self, mock_get_single):
		"""Test integración con DocType de configuración"""
		# Mock de configuración
		mock_config = MagicMock()
		mock_config.refresh_interval = 300
		mock_config.enable_auto_refresh = True
		mock_config.cache_duration = 3600
		mock_config.dashboard_theme = "light"
		mock_get_single.return_value = mock_config

		from facturacion_mexico.dashboard_fiscal.doctype.fiscal_dashboard_config.fiscal_dashboard_config import (
			FiscalDashboardConfig,
		)

		# Test obtener configuración
		config = FiscalDashboardConfig.get_config()
		self.assertIsInstance(config, dict)
		self.assertEqual(config["refresh_interval"], 300)
		self.assertEqual(config["dashboard_theme"], "light")
		self.assertTrue(config["enable_auto_refresh"])

	def test_registry_error_handling(self):
		"""Test manejo de errores en registry"""

		# Test KPI que arroja error
		def error_kpi():
			raise ValueError("Test error")

		DashboardRegistry.register_kpi("error_module", {"error_kpi": error_kpi})

		# Evaluar KPI con error - no debería explotar
		result = DashboardRegistry.evaluate_kpi("error_module", "error_kpi")
		self.assertIsNone(result)  # Debería retornar None en caso de error

	def test_cache_error_handling(self):
		"""Test manejo de errores en cache"""

		def error_function():
			raise Exception("Test error")

		# Cache debería manejar error gracefully
		result = DashboardCache.get_or_set("error_key", error_function, ttl=3600)
		self.assertIsNone(result)  # Graceful degradation

		# Stats deberían reflejar el error
		stats = DashboardCache.get_cache_stats()
		self.assertGreater(stats["stats"]["errors"], 0)

	def test_cache_stats_calculation(self):
		"""Test cálculo de estadísticas de cache"""
		# Generar datos de prueba
		DashboardCache.get_or_set("hit_test", lambda: "data", ttl=3600)
		DashboardCache.get_or_set("hit_test", lambda: "data", ttl=3600)  # Hit

		stats = DashboardCache.get_cache_stats()

		# Verificar estructura de stats
		required_keys = ["cache_size", "hit_ratio", "stats", "memory_estimate_bytes"]
		for key in required_keys:
			self.assertIn(key, stats)

		# Verificar hit ratio calculation
		self.assertGreaterEqual(stats["hit_ratio"], 0)
		self.assertLessEqual(stats["hit_ratio"], 100)

	def test_registry_module_widgets_filter(self):
		"""Test filtrado de widgets por módulo"""
		# Registrar widgets de diferentes módulos
		DashboardRegistry.register_widget(
			{"code": "widget1", "name": "Widget 1", "type": "kpi", "module": "module_a"}
		)
		DashboardRegistry.register_widget(
			{"code": "widget2", "name": "Widget 2", "type": "chart", "module": "module_b"}
		)
		DashboardRegistry.register_widget(
			{"code": "widget3", "name": "Widget 3", "type": "kpi", "module": "module_a"}
		)

		# Test filtrado por módulo
		module_a_widgets = DashboardRegistry.get_module_widgets("module_a")
		self.assertEqual(len(module_a_widgets), 2)
		self.assertIn("widget1", module_a_widgets)
		self.assertIn("widget3", module_a_widgets)

		module_b_widgets = DashboardRegistry.get_module_widgets("module_b")
		self.assertEqual(len(module_b_widgets), 1)
		self.assertIn("widget2", module_b_widgets)


class TestDashboardConfigValidation(unittest.TestCase):
	"""Tests específicos para validación de configuración"""

	@unittest.skip("Skipping until DocTypes are installed in test site")
	def test_widget_layout_validation(self):
		"""Test validación de layout de widgets"""
		from facturacion_mexico.dashboard_fiscal.doctype.fiscal_dashboard_config.fiscal_dashboard_config import (
			FiscalDashboardConfig,
		)

		config = frappe.new_doc("Fiscal Dashboard Config")

		# Layout válido
		valid_layout = [{"code": "test_widget", "position": {"row": 1, "col": 1, "width": 2, "height": 1}}]

		# No debería arrojar error
		try:
			config.validate_widget_layout(valid_layout)
			validation_passed = True
		except Exception:
			validation_passed = False

		self.assertTrue(validation_passed)

		# Layout inválido - posición fuera de rango
		invalid_layout = [
			{
				"code": "test_widget",
				"position": {"row": 5, "col": 1, "width": 2, "height": 1},  # row > 4
			}
		]

		# Debería arrojar error
		with self.assertRaises(Exception):
			config.validate_widget_layout(invalid_layout)

	@unittest.skip("Skipping until DocTypes are installed in test site")
	def test_interval_validation(self):
		"""Test validación de intervalos"""
		from facturacion_mexico.dashboard_fiscal.doctype.fiscal_dashboard_config.fiscal_dashboard_config import (
			FiscalDashboardConfig,
		)

		config = frappe.new_doc("Fiscal Dashboard Config")

		# Configuración válida
		config.refresh_interval = 300
		config.cache_duration = 3600

		try:
			config.validate_intervals()
			validation_passed = True
		except Exception:
			validation_passed = False

		self.assertTrue(validation_passed)

		# Configuración inválida - cache menor que 2x refresh
		config.refresh_interval = 300
		config.cache_duration = 400  # Menor que 600 (300*2)

		with self.assertRaises(Exception):
			config.validate_intervals()


def run_basic_dashboard_tests():
	"""Ejecutar tests básicos del dashboard"""
	import sys

	# Configurar frappe para testing
	if hasattr(frappe.flags, "in_test"):
		frappe.flags.in_test = True

	# Crear test suite
	test_suite = unittest.TestSuite()

	# Agregar test cases
	test_suite.addTest(unittest.makeSuite(TestBaseDashboard))
	test_suite.addTest(unittest.makeSuite(TestDashboardConfigValidation))

	# Ejecutar tests
	runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
	result = runner.run(test_suite)

	return result.wasSuccessful()
