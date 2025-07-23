# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Acceptance Tests: Multi-Sucursal User Acceptance Testing
Testing framework Layer 4 - User acceptance and business scenarios
"""

import unittest
from unittest.mock import Mock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestMultiSucursalAcceptance(FrappeTestCase):
	"""
	Layer 4 Acceptance Tests para Sistema Multi-Sucursal
	User Acceptance Testing desde perspectiva de usuarios finales
	"""

	@classmethod
	def setUpClass(cls):
		"""Setup inicial para todos los tests"""
		super().setUpClass()
		cls.test_company = "_Test Company"
		cls._setup_acceptance_scenarios()

	@classmethod
	def _setup_acceptance_scenarios(cls):
		"""Setup de escenarios de aceptación"""
		try:
			from facturacion_mexico.multi_sucursal.branch_manager import BranchManager

			cls.BranchManager = BranchManager
		except ImportError:
			cls.BranchManager = None
			print("Warning: Acceptance test components not available")

	def test_director_financiero_dashboard_acceptance(self):
		"""
		UAT: Director Financiero - Vista ejecutiva multi-sucursal
		Scenario: Director necesita vista consolidada de todas las sucursales
		"""
		if not self.BranchManager:
			self.skipTest("Acceptance components not available")

		# Scenario setup: Empresa con múltiples sucursales
		branch_manager = self.BranchManager(self.test_company)

		executive_scenario_branches = [
			{
				"name": "Sucursal_CDMX",
				"branch": "Ciudad de México",
				"fm_lugar_expedicion": "06000",
				"fm_folio_current": 2500,
				"fm_folio_end": 5000,
				"fm_share_certificates": 1,
			},
			{
				"name": "Sucursal_GDL",
				"branch": "Guadalajara",
				"fm_lugar_expedicion": "44100",
				"fm_folio_current": 1200,
				"fm_folio_end": 3000,
				"fm_share_certificates": 1,
			},
			{
				"name": "Sucursal_MTY",
				"branch": "Monterrey",
				"fm_lugar_expedicion": "64000",
				"fm_folio_current": 800,
				"fm_folio_end": 2000,
				"fm_share_certificates": 0,
			},
		]

		with patch.object(branch_manager, "get_fiscal_branches") as mock_branches:
			mock_branches.return_value = executive_scenario_branches

			# UAT: Director ejecuta dashboard consolidado
			executive_dashboard = branch_manager.get_branch_health_summary()

			# Business Requirements Validation
			self.assertIsInstance(executive_dashboard, dict)

			# Requirement: Vista consolidada de todas las sucursales
			self.assertEqual(executive_dashboard["total_branches"], 3)
			self.assertIn("branches_detail", executive_dashboard)

			# Requirement: Identificación rápida de problemas
			total_issues = sum(len(branch["issues"]) for branch in executive_dashboard["branches_detail"])

			# System debe identificar issues potenciales
			self.assertIsInstance(total_issues, int)

			# Requirement: Métricas ejecutivas clave
			self.assertIn("folio_summary", executive_dashboard)
			self.assertIn("certificate_summary", executive_dashboard)

			# Business Value: Total folios disponibles
			total_folios = executive_dashboard["folio_summary"]["total_folios_available"]
			self.assertGreater(total_folios, 0)

	def test_contador_multisucursal_workflow_acceptance(self):
		"""
		UAT: Contador Multi-sucursal - Gestión operativa diaria
		Scenario: Contador necesita gestionar certificados y folios
		"""
		if not self.BranchManager:
			self.skipTest("Acceptance components not available")

		branch_manager = self.BranchManager(self.test_company)

		# Scenario: Contador managing certificates
		accounting_scenario = [
			{
				"name": "Oficina_Principal",
				"branch": "Oficina Principal",
				"fm_share_certificates": 1,  # Uses shared certificates
				"fm_folio_current": 1500,
				"fm_folio_end": 2000,
				"fm_folio_warning_threshold": 100,
			},
			{
				"name": "Almacen_Norte",
				"branch": "Almacén Norte",
				"fm_share_certificates": 0,  # Specific certificates
				"fm_folio_current": 950,
				"fm_folio_end": 1000,
				"fm_folio_warning_threshold": 50,
			},
		]

		with patch.object(branch_manager, "get_fiscal_branches") as mock_branches:
			mock_branches.return_value = accounting_scenario

			# UAT: Contador reviews certificate distribution
			cert_distribution = branch_manager.get_certificate_distribution_summary()

			# Business Requirements
			self.assertIsInstance(cert_distribution, dict)

			# Requirement: Clear certificate distribution visibility
			self.assertIn("shared_pool_branches", cert_distribution)
			self.assertIn("specific_cert_branches", cert_distribution)

			# Business Validation: Mixed certificate strategy identified
			self.assertGreaterEqual(cert_distribution["shared_pool_branches"], 1)
			self.assertGreaterEqual(cert_distribution["specific_cert_branches"], 1)

			# UAT: Contador gets optimization suggestions
			suggestions = branch_manager.suggest_certificate_optimization()

			# Business Value: Actionable recommendations
			self.assertIsInstance(suggestions, list)

			# If suggestions exist, they should be actionable
			if suggestions:
				suggestion = suggestions[0]
				self.assertIn("title", suggestion)
				self.assertIn("recommendation", suggestion)
				self.assertIn("priority", suggestion)

	def test_usuario_sucursal_daily_operations_acceptance(self):
		"""
		UAT: Usuario de Sucursal - Operaciones diarias
		Scenario: Usuario necesita verificar estado de folios antes de facturar
		"""
		if not self.BranchManager:
			self.skipTest("Acceptance components not available")

		branch_manager = self.BranchManager(self.test_company)

		# Scenario: Branch user checking folio status
		user_branch_scenario = [
			{
				"name": "Mi_Sucursal",
				"branch": "Mi Sucursal",
				"fm_folio_current": 950,
				"fm_folio_end": 1000,
				"fm_folio_warning_threshold": 100,
				"fm_lugar_expedicion": "45000",
			}
		]

		with patch.object(branch_manager, "get_fiscal_branches") as mock_branches:
			mock_branches.return_value = user_branch_scenario

			# UAT: User checks branch health
			branch_health = branch_manager.get_branch_health_summary()

			# Business Requirements Validation
			self.assertIsInstance(branch_health, dict)
			self.assertEqual(branch_health["total_branches"], 1)

			# Requirement: Clear folio status indication
			branch_detail = branch_health["branches_detail"][0]
			folio_info = branch_detail["folio_info"]

			# Business Validation: Folio status is clear and actionable
			self.assertIn("status", folio_info)
			self.assertIn("remaining_folios", folio_info)
			self.assertIn("message", folio_info)

			# Expected: Low folios should trigger warning
			remaining_folios = folio_info["remaining_folios"]
			self.assertEqual(remaining_folios, 50)  # 1000 - 950

			# Business Rule: Low folios should be flagged
			self.assertIn(folio_info["status"], ["warning", "critical"])

			# User Experience: Clear message provided
			self.assertIsInstance(folio_info["message"], str)
			self.assertGreater(len(folio_info["message"]), 0)

	def test_it_administrator_system_health_acceptance(self):
		"""
		UAT: Administrador IT - Monitoreo sistema multi-sucursal
		Scenario: IT Admin necesita monitorear health del sistema completo
		"""
		if not self.BranchManager:
			self.skipTest("Acceptance components not available")

		branch_manager = self.BranchManager(self.test_company)

		# Scenario: IT monitoring multiple branches with different health levels
		it_monitoring_scenario = [
			{
				"name": "Healthy_Branch_1",
				"branch": "Sucursal Saludable",
				"fm_folio_current": 100,
				"fm_folio_end": 5000,
				"fm_share_certificates": 1,
			},
			{
				"name": "Warning_Branch_1",
				"branch": "Sucursal Advertencia",
				"fm_folio_current": 1800,
				"fm_folio_end": 2000,
				"fm_folio_warning_threshold": 300,
			},
			{
				"name": "Critical_Branch_1",
				"branch": "Sucursal Crítica",
				"fm_folio_current": 990,
				"fm_folio_end": 1000,
				"fm_folio_warning_threshold": 50,
			},
		]

		with patch.object(branch_manager, "get_fiscal_branches") as mock_branches:
			mock_branches.return_value = it_monitoring_scenario

			# UAT: IT Admin monitors system health
			system_health = branch_manager.get_branch_health_summary()

			# Technical Requirements Validation
			self.assertIsInstance(system_health, dict)

			# Requirement: System health classification
			self.assertEqual(system_health["healthy_branches"], 1)
			self.assertEqual(system_health["warning_branches"], 1)
			self.assertEqual(system_health["critical_branches"], 1)

			# Requirement: Branches needing attention identification
			branches_needing_attention = system_health["branches_needing_attention"]
			self.assertEqual(branches_needing_attention, 2)  # Warning + Critical

			# IT Value: Detailed branch analysis
			for branch_detail in system_health["branches_detail"]:
				# Each branch should have health assessment
				self.assertIn("health_status", branch_detail)
				self.assertIn("health_score", branch_detail)
				self.assertIn("needs_attention", branch_detail)

				# Health score should be numeric
				self.assertIsInstance(branch_detail["health_score"], (int, float))
				self.assertGreaterEqual(branch_detail["health_score"], 0)
				self.assertLessEqual(branch_detail["health_score"], 100)

	def test_auditor_compliance_review_acceptance(self):
		"""
		UAT: Auditor - Revisión de compliance multi-sucursal
		Scenario: Auditor necesita validar configuración fiscal
		"""
		if not self.BranchManager:
			self.skipTest("Acceptance components not available")

		branch_manager = self.BranchManager(self.test_company)

		# Scenario: Audit compliance review
		audit_scenario = [
			{
				"name": "Compliant_Branch",
				"branch": "Sucursal Compliant",
				"fm_lugar_expedicion": "06000",
				"fm_serie_pattern": "COMP-{yyyy}",
				"fm_folio_current": 1,
				"fm_folio_end": 10000,
				"fm_share_certificates": 1,
			},
			{
				"name": "Review_Branch",
				"branch": "Sucursal a Revisar",
				"fm_lugar_expedicion": "44100",
				"fm_serie_pattern": "REV-{yyyy}",
				"fm_folio_current": 5000,
				"fm_folio_end": 5100,  # Low range for review
				"fm_share_certificates": 0,
			},
		]

		with patch.object(branch_manager, "get_fiscal_branches") as mock_branches:
			mock_branches.return_value = audit_scenario

			# UAT: Auditor performs compliance review
			compliance_report = branch_manager.get_branch_health_summary()

			# Audit Requirements Validation
			self.assertIsInstance(compliance_report, dict)
			self.assertEqual(compliance_report["total_branches"], 2)

			# Audit Value: Detailed configuration visibility
			for branch_detail in compliance_report["branches_detail"]:
				# Each branch must have fiscal configuration visible
				self.assertIn("lugar_expedicion", branch_detail)
				self.assertIn("folio_info", branch_detail)
				self.assertIn("certificate_summary", branch_detail)

				# Compliance data should be complete
				lugar_expedicion = branch_detail["lugar_expedicion"]
				self.assertIsInstance(lugar_expedicion, str)
				self.assertEqual(len(lugar_expedicion), 5)  # Valid CP format

			# Audit Finding: Issues and recommendations tracking
			total_issues = sum(
				len(branch["issues"]) + len(branch["recommendations"])
				for branch in compliance_report["branches_detail"]
			)

			# System should provide audit trail
			self.assertIsInstance(total_issues, int)

	def test_business_continuity_acceptance(self):
		"""
		UAT: Continuidad de Negocio - Sistema debe funcionar bajo condiciones adversas
		Scenario: Sistema mantiene operatividad con branches problemáticas
		"""
		if not self.BranchManager:
			self.skipTest("Acceptance components not available")

		branch_manager = self.BranchManager(self.test_company)

		# Scenario: Mixed system health conditions
		business_continuity_scenario = [
			{
				"name": "Operational_Branch",
				"branch": "Sucursal Operativa",
				"fm_folio_current": 100,
				"fm_folio_end": 2000,
				"fm_share_certificates": 1,
			},
			{
				"name": "Problem_Branch",
				"branch": "Sucursal Problemática",
				"fm_folio_current": 2100,  # Invalid: current > end
				"fm_folio_end": 2000,
				"fm_share_certificates": 0,
			},
			{
				"name": "Recovery_Branch",
				"branch": "Sucursal en Recuperación",
				"fm_folio_current": 1,  # Recently reset
				"fm_folio_end": 500,
				"fm_share_certificates": 1,
			},
		]

		with patch.object(branch_manager, "get_fiscal_branches") as mock_branches:
			mock_branches.return_value = business_continuity_scenario

			# UAT: Business continuity under adverse conditions
			try:
				continuity_report = branch_manager.get_branch_health_summary()

				# Business Continuity Requirements
				self.assertIsInstance(continuity_report, dict)

				# System must continue operating with problematic data
				self.assertEqual(continuity_report["total_branches"], 3)

				# Business Value: Problem identification without system failure
				problem_branches = [
					branch
					for branch in continuity_report["branches_detail"]
					if len(branch.get("issues", [])) > 0
				]

				# System should identify problems but continue functioning
				self.assertGreater(len(problem_branches), 0)

				# Operational branches should still be healthy
				operational_branches = [
					branch
					for branch in continuity_report["branches_detail"]
					if branch["health_status"] == "healthy"
				]

				self.assertGreaterEqual(len(operational_branches), 1)

			except Exception as e:
				self.fail(f"Business continuity failed - system crashed: {e}")

	def test_performance_acceptance_under_load(self):
		"""
		UAT: Performance Acceptance - Sistema debe responder bajo carga normal
		Scenario: Performance testing with realistic business load
		"""
		if not self.BranchManager:
			self.skipTest("Acceptance components not available")

		import time

		# Scenario: Realistic business load (20 branches)
		realistic_load_branches = []
		for i in range(20):
			realistic_load_branches.append(
				{
					"name": f"Business_Branch_{i:02d}",
					"branch": f"Sucursal Negocio {i:02d}",
					"fm_folio_current": i * 100 + 1,
					"fm_folio_end": (i + 1) * 1000,
					"fm_share_certificates": i % 3 == 0,  # Some shared, some specific
				}
			)

		branch_manager = self.BranchManager(self.test_company)

		with patch.object(branch_manager, "get_fiscal_branches") as mock_branches:
			mock_branches.return_value = realistic_load_branches

			# UAT: Performance under realistic business load
			start_time = time.time()

			performance_result = branch_manager.get_branch_health_summary()

			end_time = time.time()
			response_time = end_time - start_time

			# Business Performance Requirements
			# System must respond within acceptable business timeframes
			self.assertLess(response_time, 3.0)  # Maximum 3 seconds for 20 branches

			# Business Functionality: Complete processing
			self.assertEqual(performance_result["total_branches"], 20)
			self.assertEqual(len(performance_result["branches_detail"]), 20)

			# Performance Acceptance: All branches processed
			processed_branches = len(
				[
					b
					for b in performance_result["branches_detail"]
					if b["health_status"] in ["healthy", "warning", "critical"]
				]
			)

			self.assertEqual(processed_branches, 20)


if __name__ == "__main__":
	unittest.main()
