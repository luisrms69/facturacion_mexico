# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 1 Unit Tests - Branch Manager
Sprint 6: Tests para el gestor centralizado de sucursales multi-sucursal
"""

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.multi_sucursal.branch_manager import (
	BranchManager,
	get_certificate_optimization_suggestions,
	get_company_branch_health_summary,
)


class TestBranchManager(FrappeTestCase):
	"""Tests para Branch Manager Multi-Sucursal"""

	@classmethod
	def setUpClass(cls):
		"""Setup para toda la clase de tests"""
		super().setUpClass()

		# Crear empresa de test si no existe
		if not frappe.db.exists("Company", "_Test Company Branch Manager"):
			company = frappe.new_doc("Company")
			company.company_name = "_Test Company Branch Manager"
			company.abbr = "TCBM"
			company.default_currency = "MXN"
			company.country = "Mexico"
			company.insert(ignore_permissions=True)
			frappe.db.commit()

	def setUp(self):
		"""Setup para cada test individual"""
		frappe.clear_cache()

		# Variables de test
		self.test_company = "_Test Company Branch Manager"

		# Crear sucursales de test
		self.create_test_branches()

	def tearDown(self):
		"""Cleanup después de cada test"""
		try:
			# Eliminar configuraciones fiscales de test
			configs = frappe.get_all("Configuracion Fiscal Sucursal", filters={"company": self.test_company})
			for config in configs:
				frappe.delete_doc("Configuracion Fiscal Sucursal", config.name, ignore_permissions=True)

			# Eliminar branches de test
			branches = frappe.get_all("Branch", filters={"company": self.test_company})
			for branch in branches:
				frappe.delete_doc("Branch", branch.name, ignore_permissions=True)

		except Exception as e:
			# No fallar por cleanup
			print(f"Cleanup warning: {e!s}")

	def create_test_branches(self):
		"""Crear sucursales de test"""
		try:
			branches_data = [
				{
					"name": "_Test Branch Manager 1",
					"shared_certs": True,
					"folios": {"start": 1, "current": 50, "end": 1000, "threshold": 100},
				},
				{
					"name": "_Test Branch Manager 2",
					"shared_certs": False,
					"folios": {"start": 1, "current": 950, "end": 1000, "threshold": 100},  # Crítico
				},
				{
					"name": "_Test Branch Manager 3",
					"shared_certs": True,
					"folios": {"start": 1, "current": 900, "end": 1000, "threshold": 100},  # Advertencia
				},
			]

			for branch_data in branches_data:
				if not frappe.db.exists("Branch", branch_data["name"]):
					branch = frappe.new_doc("Branch")
					branch.branch = branch_data["name"]
					branch.company = self.test_company
					branch.fm_enable_fiscal = 1
					branch.fm_lugar_expedicion = "01000"
					branch.fm_share_certificates = branch_data["shared_certs"]

					# Configurar folios
					folios = branch_data["folios"]
					branch.fm_folio_start = folios["start"]
					branch.fm_folio_current = folios["current"]
					branch.fm_folio_end = folios["end"]
					branch.fm_folio_warning_threshold = folios["threshold"]

					branch.insert(ignore_permissions=True)

			frappe.db.commit()

		except Exception as e:
			print(f"Warning: Could not create test branches: {e!s}")

	def test_branch_manager_creation(self):
		"""Test: Crear instancia del BranchManager"""
		manager = BranchManager(self.test_company)

		self.assertEqual(manager.company, self.test_company)
		self.assertIsNone(manager._fiscal_branches)  # Inicialmente None, se carga lazy

	def test_get_fiscal_branches(self):
		"""Test: Obtener sucursales fiscales"""
		manager = BranchManager(self.test_company)
		branches = manager.get_fiscal_branches()

		self.assertIsInstance(branches, list)
		self.assertGreaterEqual(len(branches), 3, "Debe encontrar al menos 3 sucursales de test")

		# Verificar que todas las sucursales son fiscales
		for branch in branches:
			self.assertIn("name", branch)
			self.assertIn("branch", branch)
			self.assertIn("fm_enable_fiscal", branch)  # Debería estar en los campos

	def test_get_branch_health_summary(self):
		"""Test: Obtener resumen de salud de sucursales"""
		manager = BranchManager(self.test_company)
		summary = manager.get_branch_health_summary()

		# Verificar estructura del resumen
		expected_keys = [
			"total_branches",
			"healthy_branches",
			"warning_branches",
			"critical_branches",
			"branches_with_certificates",
			"branches_needing_attention",
			"certificate_summary",
			"folio_summary",
			"branches_detail",
		]

		for key in expected_keys:
			self.assertIn(key, summary)

		# Verificar que hay sucursales
		self.assertGreater(summary["total_branches"], 0)

		# Verificar detalles de sucursales
		self.assertIsInstance(summary["branches_detail"], list)
		self.assertEqual(len(summary["branches_detail"]), summary["total_branches"])

		# Verificar estructura de cada detalle de sucursal
		for branch_detail in summary["branches_detail"]:
			required_detail_keys = [
				"branch_name",
				"branch_label",
				"health_status",
				"health_score",
				"needs_attention",
				"certificate_summary",
				"folio_info",
			]
			for key in required_detail_keys:
				self.assertIn(key, branch_detail)

	def test_folio_status_analysis(self):
		"""Test: Análisis de estado de folios"""
		manager = BranchManager(self.test_company)

		# Crear datos de prueba para diferentes estados de folios
		test_cases = [
			{
				"name": "Test Normal",
				"fm_folio_current": 50,
				"fm_folio_end": 1000,
				"fm_folio_start": 1,
				"fm_folio_warning_threshold": 100,
				"expected_status": "healthy",
			},
			{
				"name": "Test Warning",
				"fm_folio_current": 950,
				"fm_folio_end": 1000,
				"fm_folio_start": 1,
				"fm_folio_warning_threshold": 100,
				"expected_status": "warning",
			},
			{
				"name": "Test Critical",
				"fm_folio_current": 980,
				"fm_folio_end": 1000,
				"fm_folio_start": 1,
				"fm_folio_warning_threshold": 100,
				"expected_status": "critical",
			},
		]

		for test_case in test_cases:
			folio_info = manager._analyze_folio_status(test_case)

			self.assertIn("status", folio_info)
			self.assertIn("remaining_folios", folio_info)
			self.assertIn("percentage_used", folio_info)
			self.assertIn("message", folio_info)

			# Verificar cálculos
			expected_remaining = test_case["fm_folio_end"] - test_case["fm_folio_current"]
			self.assertEqual(folio_info["remaining_folios"], expected_remaining)

	def test_certificate_distribution_summary(self):
		"""Test: Resumen de distribución de certificados"""
		manager = BranchManager(self.test_company)
		distribution = manager.get_certificate_distribution_summary()

		# Verificar estructura
		expected_keys = [
			"shared_pool_branches",
			"specific_cert_branches",
			"no_cert_branches",
			"certificate_types",
			"total_unique_certificates",
			"branches_detail",
		]

		for key in expected_keys:
			self.assertIn(key, distribution)

		# Verificar que los conteos suman el total
		total_branches = (
			distribution["shared_pool_branches"]
			+ distribution["specific_cert_branches"]
			+ distribution["no_cert_branches"]
		)

		branches = manager.get_fiscal_branches()
		self.assertEqual(total_branches, len(branches))

	def test_certificate_optimization_suggestions(self):
		"""Test: Sugerencias de optimización de certificados"""
		manager = BranchManager(self.test_company)
		suggestions = manager.suggest_certificate_optimization()

		self.assertIsInstance(suggestions, list)

		# Si hay sugerencias, verificar estructura
		for suggestion in suggestions:
			required_keys = ["type", "priority", "title", "description", "recommendation"]
			for key in required_keys:
				self.assertIn(key, suggestion)

			# Verificar valores válidos
			self.assertIn(suggestion["type"], ["optimization", "critical", "warning"])
			self.assertIn(suggestion["priority"], ["high", "medium", "low"])

	def test_integration_status(self):
		"""Test: Estado de integración con otros sistemas"""
		manager = BranchManager(self.test_company)
		integration_status = manager.get_integration_status()

		# Verificar estructura
		expected_integrations = ["facturapi_integration", "dashboard_integration", "certificate_system"]
		for integration in expected_integrations:
			self.assertIn(integration, integration_status)

		# Verificar estructura de FacturAPI
		facturapi_config = integration_status["facturapi_integration"]
		self.assertIn("configured", facturapi_config)
		self.assertIn("sandbox_mode", facturapi_config)
		self.assertIn("note", facturapi_config)

		# Verificar que el note explica que FacturAPI usa API keys
		self.assertIn("API keys globales", facturapi_config["note"])

		# Verificar estructura del dashboard
		dashboard_config = integration_status["dashboard_integration"]
		self.assertIn("enabled", dashboard_config)
		self.assertIn("health_monitoring", dashboard_config)
		self.assertTrue(dashboard_config["health_monitoring"])  # Debe ser True

		# Verificar sistema de certificados
		cert_system = integration_status["certificate_system"]
		self.assertEqual(cert_system["type"], "multibranch_selector")
		self.assertTrue(cert_system["supports_shared_pool"])
		self.assertTrue(cert_system["supports_branch_specific"])
		self.assertTrue(cert_system["health_monitoring"])

	def test_api_get_company_branch_health_summary(self):
		"""Test: API get_company_branch_health_summary"""
		result = get_company_branch_health_summary(self.test_company)

		self.assertIsInstance(result, dict)
		self.assertIn("success", result)

		if result["success"]:
			self.assertIn("data", result)
			self.assertIn("total_branches", result["data"])

	def test_api_get_certificate_optimization_suggestions(self):
		"""Test: API get_certificate_optimization_suggestions"""
		result = get_certificate_optimization_suggestions(self.test_company)

		self.assertIsInstance(result, dict)
		self.assertIn("success", result)
		self.assertIn("suggestions", result)
		self.assertIn("count", result)

		if result["success"]:
			self.assertEqual(result["count"], len(result["suggestions"]))

	def test_health_score_calculation(self):
		"""Test: Cálculo de health score"""
		manager = BranchManager(self.test_company)

		# Test con certificados buenos y folios normales
		good_cert_health = {"total_certificates": 2, "expired": 0, "critical": 0, "expiring_soon": 0}

		good_folio_info = {"status": "healthy"}

		result = manager._determine_overall_branch_health(good_cert_health, good_folio_info)

		self.assertIn("status", result)
		self.assertIn("score", result)
		self.assertIn("needs_attention", result)
		self.assertIn("issues", result)
		self.assertIn("recommendations", result)

		# Con certificados buenos y folios sanos, debería estar saludable
		self.assertGreaterEqual(result["score"], 80)
		self.assertEqual(result["status"], "healthy")

		# Test con certificados críticos
		bad_cert_health = {
			"total_certificates": 0,  # Sin certificados
			"expired": 1,
			"critical": 1,
			"expiring_soon": 1,
		}

		critical_folio_info = {"status": "critical"}

		result_bad = manager._determine_overall_branch_health(bad_cert_health, critical_folio_info)

		# Con problemas, score debería ser bajo
		self.assertLess(result_bad["score"], 60)
		self.assertEqual(result_bad["status"], "critical")
		self.assertTrue(result_bad["needs_attention"])
		self.assertGreater(len(result_bad["issues"]), 0)


if __name__ == "__main__":
	unittest.main()
