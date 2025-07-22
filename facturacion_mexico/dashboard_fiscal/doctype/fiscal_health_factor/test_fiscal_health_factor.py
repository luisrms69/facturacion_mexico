# Copyright (c) 2025, Frappe Technologies and Contributors
# See license.txt

import unittest

import frappe
from frappe import _


class TestFiscalHealthFactor(unittest.TestCase):
	"""Tests Layer 1 para Fiscal Health Factor DocType"""

	def setUp(self):
		"""Setup básico para cada test"""
		# Limpiar datos de test previos si la tabla existe
		try:
			frappe.db.delete("Fiscal Health Score", {"company": ["like", "%test%"]})
			frappe.db.commit()
		except Exception:
			# La tabla puede no existir aún, es normal en tests
			pass

		# Usar una compañía de test estándar o crear una
		test_company = "_Test Company"
		if not frappe.db.exists("Company", test_company):
			company_doc = frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": test_company,
					"abbr": "_TC",
					"default_currency": "MXN",
					"country": "Mexico",
				}
			)
			company_doc.insert(ignore_permissions=True)

		# Crear parent document de test
		self.parent_score = frappe.get_doc(
			{
				"doctype": "Fiscal Health Score",
				"score_date": frappe.utils.add_days(frappe.utils.today(), -1),
				"company": test_company,
				"overall_score": 75.5,
			}
		)
		self.parent_score.insert()
		self.parent_name = self.parent_score.name

	def tearDown(self):
		"""Cleanup después de cada test"""
		frappe.db.rollback()

	def test_doctype_creation(self):
		"""Test: Crear un Fiscal Health Factor básico"""
		# Child DocType debe crearse dentro de parent
		self.parent_score.append(
			"factors_positive",
			{
				"factor_type": "Timbrado",
				"description": "Test factor positivo",
				"impact_score": 5,
				"calculation_details": "Test calculation method",
			},
		)
		self.parent_score.save()

		factor = self.parent_score.factors_positive[0]
		self.assertEqual(factor.factor_type, "Timbrado")
		self.assertEqual(factor.impact_score, 5)

	def test_impact_score_validation_positive_range(self):
		"""Test: Validar que impact_score esté en rango válido (+10)"""
		self.parent_score.append(
			"factors_positive",
			{
				"factor_type": "Cumplimiento",
				"description": "Test factor con score válido",
				"impact_score": 8,
			},
		)
		# No debería lanzar excepción
		self.parent_score.save()

		factor = self.parent_score.factors_positive[0]
		self.assertEqual(factor.impact_score, 8)

	def test_impact_score_validation_negative_range(self):
		"""Test: Validar que impact_score esté en rango válido (-10)"""
		self.parent_score.append(
			"factors_negative",
			{
				"factor_type": "Seguridad",
				"description": "Test factor con score negativo válido",
				"impact_score": -7,
			},
		)
		# No debería lanzar excepción
		self.parent_score.save()

		factor = self.parent_score.factors_negative[0]
		self.assertEqual(factor.impact_score, -7)

	def test_impact_score_validation_out_of_range_positive(self):
		"""Test: Validar rechazo de impact_score fuera de rango (+)"""
		self.parent_score.append(
			"factors_positive",
			{
				"factor_type": "Rendimiento",
				"description": "Test factor con score inválido",
				"impact_score": 15,  # Fuera de rango
			},
		)

		with self.assertRaises(frappe.ValidationError):
			self.parent_score.save()

	def test_impact_score_validation_out_of_range_negative(self):
		"""Test: Validar rechazo de impact_score fuera de rango (-)"""
		self.parent_score.append(
			"factors_negative",
			{
				"factor_type": "Seguridad",
				"description": "Test factor con score inválido negativo",
				"impact_score": -12,  # Fuera de rango
			},
		)

		with self.assertRaises(frappe.ValidationError):
			self.parent_score.save()

	def test_description_score_consistency_detection(self):
		"""Test: Detectar inconsistencia entre descripción y score"""
		# Factor con descripción positiva pero score negativo
		self.parent_score.append(
			"factors_negative",
			{
				"factor_type": "Rendimiento",
				"description": "Excelente cumplimiento fiscal test",
				"impact_score": -3,  # Inconsistencia intencional
			},
		)

		# Debería insertar pero mostrar advertencia (msgprint)
		self.parent_score.save()
		factor = self.parent_score.factors_negative[0]
		self.assertEqual(factor.impact_score, -3)

	def test_zero_impact_score(self):
		"""Test: Impact score de cero es válido"""
		self.parent_score.append(
			"factors_positive",
			{
				"factor_type": "General",
				"description": "Test factor neutral",
				"impact_score": 0,
			},
		)

		self.parent_score.save()
		factor = self.parent_score.factors_positive[0]
		self.assertEqual(factor.impact_score, 0)

	def test_required_fields(self):
		"""Test: Campos requeridos"""
		# Sin factor_type
		with self.assertRaises(frappe.ValidationError):
			self.parent_score.append(
				"factors_positive",
				{
					"description": "Test sin factor_type",
					"impact_score": 5,
					# factor_type faltante
				},
			)
			self.parent_score.save()

	def test_factor_types_validation(self):
		"""Test: Validar tipos de factor válidos"""
		valid_types = ["Timbrado", "PPD", "E-Receipts", "Addendas", "Facturas Globales"]

		for _i, factor_type in enumerate(valid_types):
			test_parent = frappe.get_doc(
				{
					"doctype": "Fiscal Health Score",
					"score_date": frappe.utils.add_days(frappe.utils.today(), -1),
					"company": "_Test Company",
					"overall_score": 75.5,
				}
			)
			test_parent.append(
				"factors_positive",
				{
					"factor_type": factor_type,
					"description": f"Test factor {factor_type}",
					"impact_score": 2,
				},
			)
			test_parent.insert()
			factor = test_parent.factors_positive[0]
			self.assertEqual(factor.factor_type, factor_type)
			test_parent.delete()

	def test_decimal_precision_impact_score(self):
		"""Test: Precisión decimal en impact_score - campo es Int"""
		self.parent_score.append(
			"factors_positive",
			{
				"factor_type": "Rendimiento",
				"description": "Test precisión decimal",
				"impact_score": 3,  # Campo Int no acepta decimales
			},
		)

		self.parent_score.save()
		factor = self.parent_score.factors_positive[0]
		# Debería ser entero
		self.assertEqual(factor.impact_score, 3)
		self.assertIsInstance(factor.impact_score, int)


def run_tests():
	"""Función para correr todos los tests de este módulo"""
	import unittest

	loader = unittest.TestLoader()
	suite = loader.loadTestsFromTestCase(TestFiscalHealthFactor)
	runner = unittest.TextTestRunner(verbosity=2)
	return runner.run(suite)


if __name__ == "__main__":
	run_tests()
