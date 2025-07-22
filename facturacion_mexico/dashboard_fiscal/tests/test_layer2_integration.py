"""
Test Layer 2 Integration - Dashboard Fiscal
Business Logic Testing con Mocked Hooks y Dependencies
Aplicando Framework de Testing Granular del Custom Fields Migration Sprint
"""

import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import frappe

from facturacion_mexico.dashboard_fiscal.api import (
	error_response,
	get_active_alerts,
	get_dashboard_data,
	get_module_kpis,
	save_dashboard_layout,
	success_response,
)
from facturacion_mexico.dashboard_fiscal.cache_manager import DashboardCache
from facturacion_mexico.dashboard_fiscal.dashboard_registry import DashboardRegistry


class TestDashboardFiscalLayer2Integration(unittest.TestCase):
	"""Layer 2: Integration tests con mocking estratégico para business logic"""

	def setUp(self):
		"""Setup para cada test Layer 2"""
		# Limpiar registry y cache
		DashboardRegistry.reset_registry()
		DashboardCache.clear_all_cache()

		# Setup mock data común
		self.test_company = "Test Company LLC"
		self.test_user = "test@example.com"

	def tearDown(self):
		"""Cleanup después de cada test"""
		DashboardRegistry.reset_registry()
		DashboardCache.clear_all_cache()

	def test_dashboard_api_integration_with_mocked_registry(self):
		"""LAYER 2: Test integración API-Registry con registry mockeado"""

		# Mock del registry con datos de prueba
		mock_kpis = {
			"Timbrado": {"facturas_timbradas": lambda **kwargs: {"value": 150, "format": "number"}},
			"PPD": {"pagos_pendientes": lambda **kwargs: {"value": 25, "format": "number"}},
		}

		with patch.object(DashboardRegistry, "get_all_kpis", return_value=mock_kpis):
			with patch.object(DashboardRegistry, "evaluate_kpi") as mock_evaluate:
				# Configurar mock de evaluate_kpi
				def side_effect(module, kpi_name, **kwargs):
					if module == "Timbrado" and kpi_name == "facturas_timbradas":
						return {"value": 150, "format": "number", "subtitle": "Facturas timbradas"}
					elif module == "PPD" and kpi_name == "pagos_pendientes":
						return {"value": 25, "format": "number", "subtitle": "Pagos pendientes"}
					return None

				mock_evaluate.side_effect = side_effect

				# Mock configuración dashboard
				with patch("facturacion_mexico.dashboard_fiscal.api._get_dashboard_config") as mock_config:
					mock_config.return_value = {
						"refresh_interval": 300,
						"cache_duration": 3600,
						"enable_auto_refresh": True,
						"dashboard_theme": "light",
						"performance_mode": False,
					}

					# Mock company defaults
					with patch("frappe.defaults.get_user_default", return_value=self.test_company):
						with patch("frappe.has_permission", return_value=True):
							# Mock funciones auxiliares
							with patch(
								"facturacion_mexico.dashboard_fiscal.api._get_active_widgets", return_value=[]
							):
								with patch(
									"facturacion_mexico.dashboard_fiscal.api._get_active_alerts",
									return_value=[],
								):
									with patch(
										"facturacion_mexico.dashboard_fiscal.api._get_system_health_status",
										return_value={"status": "healthy"},
									):
										# Ejecutar test
										result = get_dashboard_data("month", self.test_company)

										# Validaciones
										self.assertTrue(result["success"])
										self.assertIn("data", result)
										self.assertIn("kpis", result["data"])

										# Validar que se llamó a evaluate_kpi correctamente
										self.assertEqual(mock_evaluate.call_count, 2)

										# Validar estructura de KPIs
										kpis = result["data"]["kpis"]
										self.assertIn("Timbrado", kpis)
										self.assertIn("PPD", kpis)
										self.assertEqual(kpis["Timbrado"]["facturas_timbradas"]["value"], 150)
										self.assertEqual(kpis["PPD"]["pagos_pendientes"]["value"], 25)

	def test_module_kpis_integration_with_error_handling(self):
		"""LAYER 2: Test get_module_kpis con error handling y business logic"""

		# Mock KPI que falla intermitentemente
		def failing_kpi(**kwargs):
			if kwargs.get("fail", False):
				raise Exception("Simulated KPI failure")
			return {"value": 100, "format": "number"}

		# Setup registry mock - get_module_kpis() should return KPIs for specific module
		mock_kpis = {"test_kpi": failing_kpi}

		with patch.object(DashboardRegistry, "get_module_kpis", return_value=mock_kpis):
			with patch.object(DashboardRegistry, "evaluate_kpi") as mock_evaluate:
				# Test caso exitoso
				mock_evaluate.return_value = {"value": 100, "format": "number"}
				result = get_module_kpis("TestModule")

				self.assertTrue(result["success"])
				self.assertIn("test_kpi", result["data"])

				# Reset mock y configurar error - limpiar cache primero
				DashboardCache.clear_all_cache()
				mock_evaluate.reset_mock()
				mock_evaluate.side_effect = Exception("KPI evaluation failed")
				result = get_module_kpis("TestModule")

				# Debe manejar gracefully el error
				self.assertTrue(result["success"])  # API no falla
				self.assertIn("test_kpi", result["data"])
				self.assertIsNone(result["data"]["test_kpi"]["value"])
				self.assertIn("error", result["data"]["test_kpi"])

	def test_alert_evaluation_integration_mocked(self):
		"""LAYER 2: Test evaluación de alertas con dependencies mockeadas"""

		# Test alertas del sistema (datos de prueba para referencia)

		# Mock evaluador de alertas
		def mock_alert_evaluator(**kwargs):
			return {
				"triggered": True,
				"message": "Quedan 50 créditos PAC",
				"priority": 8,
				"data": {"value": 50},
			}

		# Mock _get_active_alerts directly since it queries different DocTypes
		with patch("facturacion_mexico.dashboard_fiscal.api._get_active_alerts") as mock_get_active_alerts:
			# Return processed alert data
			mock_alert_data = [
				{
					"rule_name": "Créditos PAC bajos",
					"severity": "warning",
					"priority": 8,
					"message": "Quedan 50 créditos PAC",
					"module": "Timbrado",
					"triggered": True,
				}
			]
			mock_get_active_alerts.return_value = mock_alert_data

			result = get_active_alerts()

			# Validaciones
			self.assertTrue(result["success"])
			self.assertIn("alerts", result["data"])
			self.assertGreater(result["data"]["total_count"], 0)
			self.assertIn("by_severity", result["data"])
			self.assertIn("by_module", result["data"])

			# Validar estructura de alerta
			alert = result["data"]["alerts"][0]
			self.assertEqual(alert["rule_name"], "Créditos PAC bajos")
			self.assertEqual(alert["severity"], "warning")
			self.assertEqual(alert["module"], "Timbrado")

	def test_cache_integration_with_business_logic(self):
		"""LAYER 2: Test integración cache con business logic del dashboard"""

		# Mock función costosa
		expensive_function_calls = []

		def expensive_kpi_calculation(**kwargs):
			expensive_function_calls.append(kwargs)
			return {
				"value": len(expensive_function_calls) * 10,
				"calculation_time": datetime.now().isoformat(),
			}

		# Test caching behavior
		with patch.object(
			DashboardRegistry, "get_module_kpis", return_value={"expensive_kpi": expensive_kpi_calculation}
		):
			with patch.object(DashboardRegistry, "evaluate_kpi") as mock_evaluate:
				# Configure side_effect to call the function correctly
				def mock_eval_side_effect(module, kpi_name, **kwargs):
					return expensive_kpi_calculation(**kwargs)

				mock_evaluate.side_effect = mock_eval_side_effect

				# Primera llamada - debe llamar función
				result1 = get_module_kpis("TestModule")

				# Segunda llamada inmediata - debe usar cache
				result2 = get_module_kpis("TestModule")

				# Validar que cache funcionó
				self.assertTrue(result1["success"])
				self.assertTrue(result2["success"])

				# La función costosa solo se debe haber llamado una vez (cache hit en segunda)
				self.assertEqual(len(expensive_function_calls), 1)

	def test_permission_integration_mocked(self):
		"""LAYER 2: Test integración de permisos con business logic"""

		# Test sin permisos
		with patch("frappe.has_permission", return_value=False):
			with patch("frappe.defaults.get_user_default", return_value=self.test_company):
				result = get_dashboard_data("month", self.test_company)

				# Debe fallar por permisos
				self.assertFalse(result["success"])
				self.assertEqual(result["code"], "NO_PERMISSION")

		# Test con permisos
		with patch("frappe.has_permission", return_value=True):
			with patch("frappe.defaults.get_user_default", return_value=self.test_company):
				with patch("facturacion_mexico.dashboard_fiscal.api._get_dashboard_config") as mock_config:
					mock_config.return_value = {"cache_duration": 3600}
					with patch.object(DashboardRegistry, "get_all_kpis", return_value={}):
						with patch(
							"facturacion_mexico.dashboard_fiscal.api._get_active_widgets", return_value=[]
						):
							with patch(
								"facturacion_mexico.dashboard_fiscal.api._get_active_alerts", return_value=[]
							):
								with patch(
									"facturacion_mexico.dashboard_fiscal.api._get_system_health_status",
									return_value={},
								):
									result = get_dashboard_data("month", self.test_company)

									# Debe funcionar con permisos
									self.assertTrue(result["success"])

	def test_layout_save_integration_with_mocked_persistence(self):
		"""LAYER 2: Test save_dashboard_layout con persistencia mockeada"""

		test_layout = {
			"widgets": [
				{"id": "widget1", "position": {"row": 1, "col": 1}},
				{"id": "widget2", "position": {"row": 1, "col": 2}},
			],
			"theme": "dark",
			"auto_refresh": True,
		}

		# Mock frappe session
		with patch("frappe.session") as mock_session:
			mock_session.user = self.test_user
			# Mock existing preferences (not found)
			with patch("frappe.get_doc") as mock_get_doc:
				mock_get_doc.side_effect = frappe.DoesNotExistError()

				# Mock new document creation
				mock_new_doc = MagicMock()
				mock_new_doc.insert = MagicMock()

				with patch("frappe.get_doc", return_value=mock_new_doc):
					# Mock commit and cache operations
					with patch("frappe.db.commit"):
						with patch.object(DashboardCache, "invalidate_pattern") as mock_invalidate:
							result = save_dashboard_layout(test_layout)

							# Validaciones
							self.assertTrue(result["success"])
							self.assertTrue(result["data"]["layout_saved"])
							self.assertEqual(result["data"]["user"], self.test_user)

							# Verificar que se invalidó cache del usuario
							mock_invalidate.assert_called_once()

	def test_error_response_pattern_consistency(self):
		"""LAYER 2: Test consistencia de response patterns en error scenarios"""

		# Test error response structure
		error_result = error_response("Test error message", {"test": "data"}, "TEST_ERROR")

		# Validar estructura consistente
		required_fields = ["success", "data", "error", "code", "timestamp"]
		for field in required_fields:
			self.assertIn(field, error_result)

		self.assertFalse(error_result["success"])
		self.assertEqual(error_result["error"], "Test error message")
		self.assertEqual(error_result["code"], "TEST_ERROR")
		self.assertEqual(error_result["data"], {"test": "data"})

		# Test success response structure
		success_result = success_response({"result": "data"}, "Test success")

		required_success_fields = ["success", "data", "message", "timestamp"]
		for field in required_success_fields:
			self.assertIn(field, success_result)

		self.assertTrue(success_result["success"])
		self.assertEqual(success_result["message"], "Test success")
		self.assertEqual(success_result["data"], {"result": "data"})

	def test_registry_kpi_integration_with_context_passing(self):
		"""LAYER 2: Test integración Registry-KPI con context passing y filtering"""

		# Mock KPI que usa context
		def context_aware_kpi(**kwargs):
			company = kwargs.get("company", "Unknown")
			period = kwargs.get("period", "month")
			return {
				"value": 100 if company == self.test_company else 50,
				"context": {"company": company, "period": period},
				"format": "number",
			}

		# Setup registry con KPI context-aware
		with patch.object(
			DashboardRegistry, "get_module_kpis", return_value={"context_kpi": context_aware_kpi}
		):
			with patch.object(DashboardRegistry, "evaluate_kpi") as mock_evaluate:
				# Fix: evaluate_kpi se llama con (module, kpi_name, **kwargs)
				def mock_evaluate_side_effect(module, kpi_name, **kwargs):
					return context_aware_kpi(**kwargs)

				mock_evaluate.side_effect = mock_evaluate_side_effect

				# Test con company específica
				filters = {"company": self.test_company, "period": "week"}
				result = get_module_kpis("TestModule", filters)

				# Validaciones
				self.assertTrue(result["success"])
				self.assertIn("context_kpi", result["data"])

				# Verificar que se pasó el context correctamente
				mock_evaluate.assert_called_with(
					"TestModule", "context_kpi", company=self.test_company, period="week"
				)

	def test_widget_configuration_integration_mocked(self):
		"""LAYER 2: Test integración de configuración de widgets con mocking"""

		# Mock widgets configurados
		mock_widgets = [
			{
				"name": "widget1",
				"widget_code": "timbrado_summary",
				"widget_name": "Resumen Timbrado",
				"is_active": 1,
				"grid_position": "1,1",
				"module": "Timbrado",
			}
		]

		# Mock registry widgets
		mock_registry_widgets = {
			"timbrado_summary": {
				"title": "Timbrado Summary",
				"description": "Widget de resumen de timbrado",
				"kpis": ["facturas_timbradas", "tasa_exito"],
			}
		}

		with patch("frappe.defaults.get_user_default", return_value=self.test_company):
			with patch("frappe.has_permission", return_value=True):
				with patch(
					"facturacion_mexico.dashboard_fiscal.api._get_dashboard_config",
					return_value={"cache_duration": 3600},
				):
					with patch.object(DashboardRegistry, "get_all_kpis", return_value={}):
						with patch(
							"facturacion_mexico.dashboard_fiscal.api._get_active_widgets"
						) as mock_get_widgets:
							# Return enriched widget data as the function would
							enriched_widgets = [
								{
									**mock_widgets[0],
									"registry_config": mock_registry_widgets["timbrado_summary"],
								}
							]
							mock_get_widgets.return_value = enriched_widgets
							with patch.object(
								DashboardRegistry, "get_all_widgets", return_value=mock_registry_widgets
							):
								with patch(
									"facturacion_mexico.dashboard_fiscal.api._get_active_alerts",
									return_value=[],
								):
									with patch(
										"facturacion_mexico.dashboard_fiscal.api._get_system_health_status",
										return_value={},
									):
										result = get_dashboard_data("month", self.test_company)

										# Validaciones
										self.assertTrue(result["success"])
										self.assertIn("widgets", result["data"])

										# Verificar que widget fue enriquecido con registry config
										widgets = result["data"]["widgets"]
										self.assertEqual(len(widgets), 1)
										self.assertEqual(widgets[0]["widget_code"], "timbrado_summary")
										self.assertIn("registry_config", widgets[0])

	def test_health_score_calculation_integration(self):
		"""LAYER 2: Test cálculo de health score con integration de múltiples módulos"""

		# Mock módulos con diferentes scores
		mock_modules = {
			"Timbrado": {"kpi1": lambda **kwargs: {"value": 95}},  # Healthy
			"PPD": {"kpi2": lambda **kwargs: {"value": 60}},  # Warning
			"Motor Reglas": {"kpi3": lambda **kwargs: {"value": 85}},  # Good
		}

		with patch.object(DashboardRegistry, "get_all_kpis", return_value=mock_modules):
			with patch("frappe.defaults.get_user_default", return_value=self.test_company):
				# Mock cálculos de score por módulo
				with patch(
					"facturacion_mexico.dashboard_fiscal.api._calculate_module_health_score"
				) as mock_calc:

					def score_side_effect(module_name, company, date):
						scores = {
							"Timbrado": {
								"score": 95.0,
								"positive_factors": ["Timbrado funcionando bien"],
								"negative_factors": [],
								"recommendations": [],
							},
							"PPD": {
								"score": 60.0,
								"positive_factors": [],
								"negative_factors": ["Muchos pagos pendientes"],
								"recommendations": ["Revisar pagos vencidos"],
							},
							"Motor Reglas": {
								"score": 85.0,
								"positive_factors": ["Reglas ejecutándose correctamente"],
								"negative_factors": [],
								"recommendations": [],
							},
						}
						return scores.get(
							module_name,
							{
								"score": 0.0,
								"positive_factors": [],
								"negative_factors": [],
								"recommendations": [],
							},
						)

					mock_calc.side_effect = score_side_effect

					# Mock persistencia
					with patch("facturacion_mexico.dashboard_fiscal.api._save_fiscal_health_record"):
						from facturacion_mexico.dashboard_fiscal.api import get_fiscal_health_score

						result = get_fiscal_health_score(self.test_company)

						# Validaciones
						self.assertTrue(result["success"])
						self.assertIn("overall_score", result["data"])

						# Score promedio debe ser (95 + 60 + 85) / 3 = 80.0
						self.assertEqual(result["data"]["overall_score"], 80.0)

						# Debe incluir factores de todos los módulos
						self.assertIn("factors_positive", result["data"])
						self.assertIn("factors_negative", result["data"])
						self.assertIn("recommendations", result["data"])
