"""
Tests para Impuesto SAT DocType
"""

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase


class TestImpuestoSAT(FrappeTestCase):
	"""Tests para Impuesto SAT."""

	def test_create_impuesto_sat(self):
		"""Test básico de creación."""
		# Crear impuesto SAT
		impuesto = frappe.new_doc("Impuesto SAT")
		impuesto.code = "002"
		impuesto.description = "IVA"

		# No debe lanzar error
		impuesto.validate()

		# Verificar datos
		self.assertEqual(impuesto.code, "002")
		self.assertEqual(impuesto.description, "IVA")

	def test_code_validation(self):
		"""Test validación de código."""
		impuesto = frappe.new_doc("Impuesto SAT")
		impuesto.description = "Test"

		# Código inválido debe fallar
		impuesto.code = "12"  # Muy corto
		with self.assertRaises(frappe.ValidationError):
			impuesto.validate()

		impuesto.code = "1234"  # Muy largo
		with self.assertRaises(frappe.ValidationError):
			impuesto.validate()

		impuesto.code = "ABC"  # No numérico
		with self.assertRaises(frappe.ValidationError):
			impuesto.validate()

		# Código válido no debe fallar
		impuesto.code = "002"
		impuesto.validate()  # No debe lanzar error


if __name__ == "__main__":
	unittest.main()
