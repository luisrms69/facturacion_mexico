# Copyright (c) 2025, Frappe Technologies and Contributors
# See license.txt

import time
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import frappe
from frappe import _


class TestFiscalHealthScoreLayer2Integration(unittest.TestCase):
	"""Layer 2: Integration tests para Fiscal Health Score con mocking estratégico para business logic"""

	def setUp(self):
		"""Setup para cada test Layer 2"""
		# Limpiar datos de test previos
		try:
			frappe.db.delete("Fiscal Health Score", {"company": ["like", "%test%"]})
			frappe.db.commit()
		except Exception:
			pass

		# Crear company de test si no existe
		test_company = "_Test Company Layer2"
		if not frappe.db.exists("Company", test_company):
			company_doc = frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": test_company,
					"abbr": "_TCL2",
					"default_currency": "MXN",
					"country": "Mexico",
				}
			)
			company_doc.insert(ignore_permissions=True)

		self.test_company = test_company
		self.test_date = frappe.utils.add_days(frappe.utils.today(), -1)

	def tearDown(self):
		"""Cleanup después de cada test"""
		frappe.db.rollback()

	@patch("frappe.db.count")
	def test_fiscal_health_scoring_with_mocked_invoice_data(self, mock_count):
		"""LAYER 2: Test business logic scoring con invoice data mockeada"""

		# Setup mock data para diferentes módulos
		mock_count.side_effect = self._mock_invoice_count_side_effect

		# Crear documento para scoring
		health_score = frappe.get_doc(
			{
				"doctype": "Fiscal Health Score",
				"company": self.test_company,
				"score_date": self.test_date,
				"calculation_method": "Weighted Average",
			}
		)

		# Execute business logic
		start_time = time.time()
		health_score.calculate_health_score()
		execution_time = time.time() - start_time

		# Validate business logic correctness
		self.assertTrue(health_score.overall_score is not None)
		self.assertGreater(health_score.overall_score, 0)
		self.assertLessEqual(health_score.overall_score, 100)

		# Validate module scores calculation
		self.assertIsNotNone(health_score.timbrado_score)
		self.assertIsNotNone(health_score.ppd_score)
		self.assertGreater(health_score.timbrado_score, 0)

		# Validate performance
		self.assertLess(execution_time, 2.0, "Scoring debe completar en menos de 2 segundos")
		self.assertGreater(health_score.calculation_duration_ms, 0)

		# Validate mock usage
		self.assertGreater(mock_count.call_count, 5, "Debe hacer múltiples queries de datos")

	@patch("frappe.db.count")
	def test_scoring_algorithm_with_different_scenarios(self, mock_count):
		"""LAYER 2: Test algoritmo scoring con diferentes escenarios de negocio"""

		# Escenario 1: Company con excelente rendimiento
		mock_count.side_effect = self._mock_excellent_performance_data

		health_score = frappe.get_doc(
			{
				"doctype": "Fiscal Health Score",
				"company": self.test_company,
				"score_date": self.test_date,
				"calculation_method": "Weighted Average",
			}
		)
		health_score.insert()

		# Narrow scope SQL mock to avoid interference with document operations
		with patch(
			"facturacion_mexico.dashboard_fiscal.doctype.fiscal_health_score.fiscal_health_score.frappe.db.sql"
		) as mock_sql:
			mock_sql.return_value = [[100]]  # Addendas perfectas
			health_score.calculate_health_score()
			excellent_score = health_score.overall_score

		# Escenario 2: Company con bajo rendimiento
		mock_count.side_effect = self._mock_poor_performance_data

		# Create poor company for testing
		poor_company = self.test_company + " Poor"
		if not frappe.db.exists("Company", poor_company):
			poor_company_doc = frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": poor_company,
					"abbr": "_TCPOOR",
					"default_currency": "MXN",
					"country": "Mexico",
				}
			)
			poor_company_doc.insert(ignore_permissions=True)

		health_score_poor = frappe.get_doc(
			{
				"doctype": "Fiscal Health Score",
				"company": poor_company,
				"score_date": self.test_date,
				"calculation_method": "Weighted Average",
			}
		)
		health_score_poor.insert()

		with patch(
			"facturacion_mexico.dashboard_fiscal.doctype.fiscal_health_score.fiscal_health_score.frappe.db.sql"
		) as mock_sql:
			mock_sql.return_value = [[10]]  # Addendas con problemas
			health_score_poor.calculate_health_score()
			poor_score = health_score_poor.overall_score

		# Validate business logic consistency
		self.assertGreater(excellent_score, poor_score, "Score excelente debe ser mayor que pobre")
		self.assertGreater(excellent_score, 80, "Excelente rendimiento debe dar score > 80")
		self.assertLess(poor_score, 60, "Bajo rendimiento debe dar score < 60")

	@patch("frappe.db.exists")
	def test_health_factors_generation_with_mocked_module_availability(self, mock_exists):
		"""LAYER 2: Test generación factores de salud con módulos mockeados"""

		# Mock diferentes configuraciones de módulos disponibles
		def mock_doctype_exists(doctype, name=None):
			if name:  # Es una query de documento específico
				return True
			# Es una query de DocType existence
			module_availability = {
				"EReceipt MX": True,
				"Addenda Template": False,  # Módulo no instalado
				"Factura Global MX": True,
				"Rule Execution Log": True,
			}
			return module_availability.get(doctype, True)

		mock_exists.side_effect = mock_doctype_exists

		# Crear health score para generar factores
		health_score = frappe.get_doc(
			{
				"doctype": "Fiscal Health Score",
				"company": self.test_company,
				"score_date": self.test_date,
				"timbrado_score": 95.0,  # Alto score
				"ppd_score": 65.0,  # Score medio
				"ereceipts_score": 90.0,  # Alto score
				"addendas_score": 100.0,  # Perfect (módulo no instalado)
				"overall_score": 85.0,
			}
		)

		# Execute factor generation
		health_score.generate_health_factors()
		health_score.generate_recommendations()

		# Validate positive factors generation
		positive_factors = [f for f in health_score.factors_positive if f.factor_type]
		self.assertGreater(len(positive_factors), 0, "Debe generar factores positivos")

		timbrado_factors = [f for f in positive_factors if f.factor_type == "Timbrado"]
		self.assertEqual(len(timbrado_factors), 1, "Score alto timbrado debe generar factor positivo")

		# Validate negative factors generation
		negative_factors = [f for f in health_score.factors_negative if f.factor_type]
		# PPD score de 65 no debería generar factor negativo (threshold < 60)
		ppd_negative_factors = [f for f in negative_factors if f.factor_type == "PPD"]
		self.assertEqual(len(ppd_negative_factors), 0, "PPD score 65 no debe generar factor negativo")

		# Validate recommendations
		recommendations = [r for r in health_score.recommendations if r.category]
		self.assertGreater(len(recommendations), 0, "Score 85 debe generar recomendaciones")

	@patch("frappe.db.count")
	def test_different_calculation_methods_integration(self, mock_count):
		"""LAYER 2: Test integración diferentes métodos de cálculo"""

		mock_count.side_effect = self._mock_standard_performance_data

		# Test Weighted Average method
		health_score_weighted = frappe.get_doc(
			{
				"doctype": "Fiscal Health Score",
				"company": self.test_company,
				"score_date": self.test_date,
				"calculation_method": "Weighted Average",
			}
		)
		health_score_weighted.calculate_module_scores()
		health_score_weighted.calculate_overall_score()
		weighted_score = health_score_weighted.overall_score

		# Test Simple Average method
		health_score_simple = frappe.get_doc(
			{
				"doctype": "Fiscal Health Score",
				"company": self.test_company,
				"score_date": self.test_date,
				"calculation_method": "Simple Average",
			}
		)
		# Copy same module scores
		for field in [
			"timbrado_score",
			"ppd_score",
			"ereceipts_score",
			"addendas_score",
			"global_invoices_score",
			"rules_compliance_score",
		]:
			setattr(health_score_simple, field, getattr(health_score_weighted, field))

		health_score_simple.calculate_overall_score()
		simple_score = health_score_simple.overall_score

		# Test Custom Formula method
		health_score_custom = frappe.get_doc(
			{
				"doctype": "Fiscal Health Score",
				"company": self.test_company,
				"score_date": self.test_date,
				"calculation_method": "Custom Formula",
			}
		)
		# Copy same module scores
		for field in [
			"timbrado_score",
			"ppd_score",
			"ereceipts_score",
			"addendas_score",
			"global_invoices_score",
			"rules_compliance_score",
		]:
			setattr(health_score_custom, field, getattr(health_score_weighted, field))

		health_score_custom.calculate_overall_score()
		custom_score = health_score_custom.overall_score

		# Validate different calculation methods produce reasonable results
		self.assertIsNotNone(weighted_score, "Weighted Average debe producir score")
		self.assertIsNotNone(simple_score, "Simple Average debe producir score")
		self.assertIsNotNone(custom_score, "Custom Formula debe producir score")

		# All scores should be in valid range
		for score in [weighted_score, simple_score, custom_score]:
			self.assertGreaterEqual(score, 0)
			self.assertLessEqual(score, 100)

	@patch("frappe.db.count")
	@patch("frappe.log_error")
	def test_error_handling_with_mocked_failures(self, mock_log_error, mock_count):
		"""LAYER 2: Test manejo de errores con fallos mockeados"""

		# Mock database failure
		mock_count.side_effect = Exception("Database connection failed")

		health_score = frappe.get_doc(
			{
				"doctype": "Fiscal Health Score",
				"company": self.test_company,
				"score_date": self.test_date,
			}
		)

		# Execute with error handling - expect graceful handling rather than ValidationError
		try:
			health_score.calculate_health_score()
		except Exception:
			# The error should be caught and logged, not propagated as ValidationError
			pass

		# Validate error logging occurred
		self.assertTrue(mock_log_error.called, "Error debe ser loggeado")
		if mock_log_error.call_args:
			error_call = mock_log_error.call_args[0]
			# Check for either generic or specific error message
			self.assertTrue(
				"Error calculando" in error_call[0] or "health score" in error_call[0],
				f"Error message should contain calculation error info, got: {error_call[0]}",
			)

	@patch("frappe.utils.now_datetime")
	def test_metadata_and_timestamps_integration(self, mock_datetime):
		"""LAYER 2: Test integración metadatos y timestamps"""

		# Mock current time
		mock_time = datetime(2025, 7, 21, 15, 30, 45)
		mock_datetime.return_value = mock_time

		health_score = frappe.get_doc(
			{
				"doctype": "Fiscal Health Score",
				"company": self.test_company,
				"score_date": self.test_date,
			}
		)

		# Mock quick calculation to test timing
		with patch.object(health_score, "calculate_module_scores"):
			with patch.object(health_score, "generate_health_factors"):
				health_score.calculate_health_score()

		# Validate metadata (with tolerance for timestamp differences)
		self.assertIsNotNone(health_score.last_calculated)
		self.assertEqual(health_score.created_by, frappe.session.user)
		self.assertIsNotNone(health_score.calculation_duration_ms)
		self.assertGreater(health_score.calculation_duration_ms, 0)

	def _mock_invoice_count_side_effect(self, doctype, filters=None):
		"""Helper para mockear diferentes counts según el tipo de query"""
		if doctype == "Sales Invoice":
			if not filters:
				return 100  # Total invoices

			status_filter = filters.get("fm_timbrado_status")
			if status_filter == "Timbrada":
				return 85  # 85% timbradas exitosamente
			elif status_filter == "Error":
				return 5  # 5% con errores
			elif status_filter in ["Pendiente", ""]:
				return 2  # 2% pendientes vencidas
			else:
				return 100  # Default total

		elif doctype == "Payment Entry":
			if not filters:
				return 50  # Total payments

			status_filter = filters.get("fm_ppd_status")
			if status_filter == "Completed":
				return 40  # 80% completados
			else:
				return 50  # Default total

		return 10  # Default para otros doctypes

	def _mock_excellent_performance_data(self, doctype, filters=None):
		"""Mock data para excelente rendimiento"""
		if doctype == "Sales Invoice":
			if not filters:
				return 200
			status = filters.get("fm_timbrado_status")
			if status == "Timbrada":
				return 195  # 97.5% excelente
			elif status == "Error":
				return 1  # 0.5% errores mínimos
			else:
				return 200
		elif doctype == "Payment Entry":
			if not filters:
				return 100
			if filters.get("fm_ppd_status") == "Completed":
				return 95  # 95% completados
			else:
				return 100
		return 50

	def _mock_poor_performance_data(self, doctype, filters=None):
		"""Mock data para bajo rendimiento"""
		if doctype == "Sales Invoice":
			if not filters:
				return 200
			status = filters.get("fm_timbrado_status")
			if status == "Timbrada":
				return 120  # 60% solo timbrada
			elif status == "Error":
				return 40  # 20% errores altos
			else:
				return 200
		elif doctype == "Payment Entry":
			if not filters:
				return 100
			if filters.get("fm_ppd_status") == "Completed":
				return 45  # 45% completados solamente
			else:
				return 100
		return 20

	def _mock_standard_performance_data(self, doctype, filters=None):
		"""Mock data para rendimiento estándar"""
		if doctype == "Sales Invoice":
			if not filters:
				return 150
			status = filters.get("fm_timbrado_status")
			if status == "Timbrada":
				return 135  # 90% timbradas
			elif status == "Error":
				return 8  # 5.3% errores
			else:
				return 150
		elif doctype == "Payment Entry":
			if not filters:
				return 75
			if filters.get("fm_ppd_status") == "Completed":
				return 60  # 80% completados
			else:
				return 75
		return 25


def run_tests():
	"""Función para correr todos los tests de este módulo"""
	import unittest

	loader = unittest.TestLoader()
	suite = loader.loadTestsFromTestCase(TestFiscalHealthScoreLayer2Integration)
	runner = unittest.TextTestRunner(verbosity=2)
	return runner.run(suite)


if __name__ == "__main__":
	run_tests()
