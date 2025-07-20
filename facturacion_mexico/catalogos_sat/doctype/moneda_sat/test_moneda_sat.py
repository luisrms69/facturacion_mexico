"""
Tests para Moneda SAT DocType
"""

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase


class TestMonedaSAT(FrappeTestCase):
	"""Tests para Moneda SAT."""

	def test_create_moneda_sat(self):
		"""Test básico de creación."""
		# Crear moneda SAT
		moneda = frappe.new_doc("Moneda SAT")
		moneda.code = "MXN"
		moneda.description = "Peso Mexicano"
		moneda.decimales = 2

		# No debe lanzar error
		moneda.validate()

		# Verificar datos
		self.assertEqual(moneda.code, "MXN")
		self.assertEqual(moneda.description, "Peso Mexicano")
		self.assertEqual(moneda.decimales, 2)

	def test_code_validation(self):
		"""Test validación de código."""
		moneda = frappe.new_doc("Moneda SAT")
		moneda.description = "Test"

		# Código inválido debe fallar
		moneda.code = "MX"  # Muy corto
		with self.assertRaises(frappe.ValidationError):
			moneda.validate()

		moneda.code = "MXNN"  # Muy largo
		with self.assertRaises(frappe.ValidationError):
			moneda.validate()

		moneda.code = "M12"  # No alfabético
		with self.assertRaises(frappe.ValidationError):
			moneda.validate()

		# Código válido no debe fallar
		moneda.code = "USD"
		moneda.validate()  # No debe lanzar error
		self.assertEqual(moneda.code, "USD")  # Debe convertir a mayúsculas


if __name__ == "__main__":
	unittest.main()
