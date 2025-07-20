"""
Tests Simplificados para Payment Tracking MX - Sprint 2
Cumple reglas Buzola: tests funcionales antes de commit
"""

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

# REGLA #43A: Skip test records para evitar LinkValidationError
frappe.flags.skip_test_records = True


class TestPaymentTrackingMXSimple(FrappeTestCase):
	"""Tests básicos funcionales para cumplir reglas de commit."""

	def setUp(self):
		"""Setup para cada test."""
		frappe.flags.skip_test_records = True
		frappe.set_user("Administrator")

	def test_payment_tracking_creation(self):
		"""Test básico: crear Payment Tracking MX."""
		tracking = frappe.new_doc("Payment Tracking MX")
		tracking.sales_invoice = "TEST-SINV-001"
		tracking.payment_entry = "TEST-PE-001"
		tracking.amount_paid = 1000.0
		tracking.balance_before = 5000.0
		tracking.parcialidad_number = 1

		# Calcular balance
		tracking.calculate_balance_after()

		# Verificar cálculo
		self.assertEqual(tracking.balance_after, 4000.0)

	def test_amount_validation_positive(self):
		"""Test validación: montos válidos."""
		tracking = frappe.new_doc("Payment Tracking MX")
		tracking.amount_paid = 1000.0
		tracking.balance_before = 5000.0

		# No debe fallar con montos válidos
		try:
			tracking.validate_amounts()
		except Exception as e:
			self.fail(f"Validación falló con montos válidos: {e}")

	def test_amount_validation_negative(self):
		"""Test validación: monto inválido."""
		tracking = frappe.new_doc("Payment Tracking MX")
		tracking.amount_paid = 0  # Inválido
		tracking.balance_before = 5000.0

		# Debe fallar con monto cero
		with self.assertRaises(frappe.ValidationError):
			tracking.validate_amounts()

	def test_helper_functions_exist(self):
		"""Test que las funciones helper existen."""
		from facturacion_mexico.complementos_pago.doctype.payment_tracking_mx.payment_tracking_mx import (
			get_invoice_balance,
			get_next_parcialidad_number,
		)

		# Verificar que las funciones existen
		self.assertTrue(callable(get_invoice_balance))
		self.assertTrue(callable(get_next_parcialidad_number))


if __name__ == "__main__":
	unittest.main()
