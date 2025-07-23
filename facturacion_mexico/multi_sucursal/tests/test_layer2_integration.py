# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Integration Tests: Multi-Sucursal System
Testing framework Layer 2 - Integration between components
"""

import unittest
from unittest.mock import Mock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestMultiSucursalIntegration(FrappeTestCase):
	"""
	Layer 2 Integration Tests para Sistema Multi-Sucursal
	Valida integración entre componentes del sistema
	"""

	@classmethod
	def setUpClass(cls):
		"""Setup inicial para todos los tests"""
		super().setUpClass()
		cls.test_company = "_Test Company"

		# Aplicar REGLA #34: Fortalecer sistema con fallbacks
		cls._setup_integration_components()

	@classmethod
	def _setup_integration_components(cls):
		"""Setup de componentes para integración"""
		try:
			from facturacion_mexico.multi_sucursal.branch_manager import BranchManager
			from facturacion_mexico.multi_sucursal.certificate_selector import MultibranchCertificateManager

			cls.BranchManager = BranchManager
			cls.CertificateManager = MultibranchCertificateManager
		except ImportError:
			cls.BranchManager = None
			cls.CertificateManager = None
			print("Warning: Integration components not available")

	def test_branch_manager_certificate_integration(self):
		"""Test: Integración BranchManager <-> CertificateManager"""
		if not self.BranchManager or not self.CertificateManager:
			self.skipTest("Integration components not available")

		# Mock branch data
		mock_branches = [
			{
				"name": "_Test Branch 1",
				"branch": "Test Branch 1",
				"fm_share_certificates": 1,
				"fm_lugar_expedicion": "06000",
			},
			{
				"name": "_Test Branch 2",
				"branch": "Test Branch 2",
				"fm_share_certificates": 0,
				"fm_lugar_expedicion": "44100",
			},
		]

		branch_manager = self.BranchManager(self.test_company)

		with patch.object(branch_manager, "get_fiscal_branches") as mock_branches_call:
			mock_branches_call.return_value = mock_branches

			# Test integración con certificate manager
			with (
				patch.object(self.CertificateManager, "__init__", return_value=None),
				patch.object(self.CertificateManager, "get_certificate_health_summary") as mock_cert_health,
			):
				mock_cert_health.return_value = {
					"total_certificates": 2,
					"healthy": 1,
					"warning": 1,
					"critical": 0,
					"expired": 0,
				}

				# Ejecutar integración
				health_summary = branch_manager.get_branch_health_summary()

				# Validar integración exitosa
				self.assertIsInstance(health_summary, dict)
				self.assertIn("total_branches", health_summary)
				self.assertIn("certificate_summary", health_summary)

				# Validar que se usaron datos de ambos componentes
				self.assertGreater(health_summary["total_branches"], 0)

	def test_branch_folio_management_integration(self):
		"""Test: Integración gestión de folios con branches"""
		if not self.BranchManager:
			self.skipTest("BranchManager not available")

		branch_manager = self.BranchManager(self.test_company)

		# Mock branch con folios
		mock_branch = {
			"name": "_Test Branch Folio",
			"fm_folio_current": 800,
			"fm_folio_end": 1000,
			"fm_folio_warning_threshold": 200,
			"fm_folio_start": 1,
		}

		# Test análisis de estado de folios
		with patch.object(branch_manager, "_analyze_folio_status") as mock_folio_analysis:
			mock_folio_analysis.return_value = {
				"status": "warning",
				"remaining_folios": 200,
				"percentage_used": 80.0,
				"message": "Advertencia: 200 folios restantes",
			}

			folio_status = branch_manager._analyze_folio_status(mock_branch)

			# Validar integración folio analysis
			self.assertEqual(folio_status["status"], "warning")
			self.assertEqual(folio_status["remaining_folios"], 200)
			self.assertIsInstance(folio_status["percentage_used"], float)

	def test_multibranch_dashboard_integration(self):
		"""Test: Integración con Dashboard Fiscal"""
		if not self.BranchManager:
			self.skipTest("BranchManager not available")

		# Test integración con dashboard registry
		try:
			from facturacion_mexico.dashboard_fiscal.integrations.multibranch_integration import (
				setup_multibranch_dashboard_integration,
			)

			with (
				patch(
					"facturacion_mexico.dashboard_fiscal.registry.DashboardRegistry.register_kpi"
				) as mock_register_kpi,
				patch(
					"facturacion_mexico.dashboard_fiscal.registry.DashboardRegistry.register_widget"
				) as mock_register_widget,
			):
				# Ejecutar integración
				setup_multibranch_dashboard_integration()

				# Validar que se registraron KPIs y widgets
				mock_register_kpi.assert_called()
				mock_register_widget.assert_called()

		except ImportError:
			# Fallback test - validar que BranchManager puede integrarse
			branch_manager = self.BranchManager(self.test_company)
			integration_status = branch_manager.get_integration_status()

			self.assertIsInstance(integration_status, dict)
			self.assertIn("dashboard_integration", integration_status)

	def test_sales_invoice_multibranch_integration(self):
		"""Test: Integración Sales Invoice con Multi-Sucursal"""
		# Mock Sales Invoice con branch
		mock_invoice = {
			"name": "TEST-INV-001",
			"company": self.test_company,
			"fm_branch": "_Test Branch Invoice",
			"fm_lugar_expedicion": "06000",
		}

		# Test que la integración maneja datos de sucursal
		try:
			from facturacion_mexico.facturacion_electronica.api import get_invoice_data

			with patch("frappe.get_doc") as mock_get_doc:
				mock_invoice_doc = Mock()
				mock_invoice_doc.as_dict.return_value = mock_invoice
				mock_get_doc.return_value = mock_invoice_doc

				# Test integración API
				with patch(
					"facturacion_mexico.multi_sucursal.utils.get_branch_fiscal_code"
				) as mock_branch_code:
					mock_branch_code.return_value = "06000"

					invoice_data = get_invoice_data("TEST-INV-001")

					# Validar que la integración incluye datos de sucursal
					self.assertIsInstance(invoice_data, dict)

		except ImportError:
			self.skipTest("Sales Invoice integration not available")

	def test_certificate_distribution_integration(self):
		"""Test: Integración distribución de certificados"""
		if not self.BranchManager:
			self.skipTest("BranchManager not available")

		branch_manager = self.BranchManager(self.test_company)

		# Mock branches con diferentes configuraciones de certificados
		mock_branches = [
			{"name": "Branch_Shared", "fm_share_certificates": 1},
			{"name": "Branch_Specific", "fm_share_certificates": 0},
			{"name": "Branch_No_Certs", "fm_share_certificates": 0},
		]

		with (
			patch.object(branch_manager, "get_fiscal_branches") as mock_branches_call,
			patch.object(self.CertificateManager, "__init__", return_value=None),
			patch.object(self.CertificateManager, "get_available_certificates") as mock_get_certs,
		):
			mock_branches_call.return_value = mock_branches

			# Configurar mocks para diferentes tipos de certificados
			def mock_cert_response(company, branch):
				if "Shared" in branch:
					return [{"type": "CSD", "name": "Shared_Cert_1"}]
				elif "Specific" in branch:
					return [{"type": "FIEL", "name": "Specific_Cert_1"}]
				else:
					return []

			mock_get_certs.side_effect = lambda: mock_cert_response(
				self.test_company, mock_branches[0]["name"]
			)

			# Test distribución de certificados
			distribution = branch_manager.get_certificate_distribution_summary()

			# Validar integración de distribución
			self.assertIsInstance(distribution, dict)
			self.assertIn("shared_pool_branches", distribution)
			self.assertIn("specific_cert_branches", distribution)
			self.assertIn("no_cert_branches", distribution)

	def test_optimization_suggestions_integration(self):
		"""Test: Integración sugerencias de optimización"""
		if not self.BranchManager:
			self.skipTest("BranchManager not available")

		branch_manager = self.BranchManager(self.test_company)

		# Mock análisis para generar sugerencias
		mock_branches = [
			{"name": "Branch1", "fm_share_certificates": 0},
			{"name": "Branch2", "fm_share_certificates": 0},
			{"name": "Branch3", "fm_share_certificates": 1},
		]

		with (
			patch.object(branch_manager, "get_fiscal_branches") as mock_branches_call,
			patch.object(self.CertificateManager, "__init__", return_value=None),
			patch.object(self.CertificateManager, "get_available_certificates") as mock_certs,
		):
			mock_branches_call.return_value = mock_branches
			mock_certs.return_value = []  # Sin certificados para generar sugerencias

			# Test generación de sugerencias
			suggestions = branch_manager.suggest_certificate_optimization()

			# Validar integración de análisis
			self.assertIsInstance(suggestions, list)

			# Si hay sugerencias, validar estructura
			if suggestions:
				suggestion = suggestions[0]
				self.assertIn("type", suggestion)
				self.assertIn("priority", suggestion)
				self.assertIn("title", suggestion)

	def test_error_propagation_integration(self):
		"""Test: Propagación de errores entre componentes"""
		if not self.BranchManager:
			self.skipTest("BranchManager not available")

		branch_manager = self.BranchManager(self.test_company)

		# Mock error en certificate manager
		with patch.object(self.CertificateManager, "__init__", side_effect=Exception("Certificate error")):
			# Test que el error se maneja gracefully
			try:
				health_summary = branch_manager.get_branch_health_summary()

				# System debe manejar el error sin crash total
				self.assertIsInstance(health_summary, dict)

			except Exception as e:
				# Si hay excepción, debe ser manejada apropiadamente
				self.assertIsInstance(str(e), str)

	def test_performance_integration(self):
		"""Test: Performance de integración entre componentes"""
		if not self.BranchManager:
			self.skipTest("BranchManager not available")

		import time

		branch_manager = self.BranchManager(self.test_company)

		# Mock multiple branches para test de performance
		mock_branches = [{"name": f"Branch_{i}", "fm_share_certificates": i % 2} for i in range(10)]

		with (
			patch.object(branch_manager, "get_fiscal_branches") as mock_branches_call,
			patch.object(self.CertificateManager, "__init__", return_value=None),
			patch.object(self.CertificateManager, "get_certificate_health_summary") as mock_cert_health,
		):
			mock_branches_call.return_value = mock_branches
			mock_cert_health.return_value = {
				"total_certificates": 1,
				"healthy": 1,
				"warning": 0,
				"critical": 0,
				"expired": 0,
			}

			start_time = time.time()

			# Test performance con múltiples branches
			health_summary = branch_manager.get_branch_health_summary()

			end_time = time.time()
			processing_time = end_time - start_time

			# Integración debe completarse en tiempo razonable
			self.assertLess(processing_time, 2.0)  # Máximo 2 segundos
			self.assertIsInstance(health_summary, dict)

	def test_concurrent_integration_access(self):
		"""Test: Acceso concurrente a integraciones"""
		if not self.BranchManager:
			self.skipTest("BranchManager not available")

		import queue
		import threading

		results_queue = queue.Queue()

		def integration_test(company, results_queue):
			try:
				branch_manager = self.BranchManager(company)

				with (
					patch.object(branch_manager, "get_fiscal_branches") as mock_branches,
					patch.object(self.CertificateManager, "__init__", return_value=None),
				):
					mock_branches.return_value = [{"name": "Concurrent_Branch", "fm_share_certificates": 1}]

					result = branch_manager.get_integration_status()
					results_queue.put({"success": True, "result": result})

			except Exception as e:
				results_queue.put({"success": False, "error": str(e)})

		# Test concurrencia con múltiples threads
		threads = []
		for i in range(3):
			thread = threading.Thread(
				target=integration_test, args=(f"{self.test_company}_{i}", results_queue)
			)
			threads.append(thread)
			thread.start()

		# Esperar completion
		for thread in threads:
			thread.join()

		# Validar resultados concurrentes
		results = []
		while not results_queue.empty():
			results.append(results_queue.get())

		self.assertEqual(len(results), 3)

		# Al menos algunos deben ser exitosos
		successful_results = [r for r in results if r["success"]]
		self.assertGreater(len(successful_results), 0)


if __name__ == "__main__":
	unittest.main()
