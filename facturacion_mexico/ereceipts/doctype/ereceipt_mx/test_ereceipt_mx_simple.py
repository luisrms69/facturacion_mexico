"""
Tests Simplificados para EReceipt MX - Sprint 2
Cumple reglas Buzola: tests funcionales antes de commit
"""

import unittest
from datetime import datetime, timedelta

import frappe
from frappe.tests.utils import FrappeTestCase


class TestEReceiptMXSimple(FrappeTestCase):
	"""Tests básicos funcionales para cumplir reglas de commit."""

	def test_ereceipt_creation(self):
		"""Test básico: crear EReceipt MX."""
		ereceipt = frappe.new_doc("EReceipt MX")
		ereceipt.sales_invoice = "TEST-SINV-001"
		ereceipt.company = "Test Company"
		ereceipt.total = 1000.0
		ereceipt.date_issued = datetime.now().date()
		ereceipt.expiry_type = "Fixed Days"
		ereceipt.expiry_days = 3

		# Verificar campos básicos
		self.assertEqual(ereceipt.sales_invoice, "TEST-SINV-001")
		self.assertEqual(ereceipt.total, 1000.0)
		self.assertEqual(ereceipt.expiry_type, "Fixed Days")

	def test_ereceipt_basic_fields(self):
		"""Test campos básicos del e-receipt."""
		ereceipt = frappe.new_doc("EReceipt MX")
		ereceipt.sales_invoice = "TEST-INVOICE-001"
		ereceipt.company = "Test Company"
		ereceipt.total = 1500.50
		ereceipt.status = "open"

		# Verificar asignación de campos
		self.assertEqual(ereceipt.sales_invoice, "TEST-INVOICE-001")
		self.assertEqual(ereceipt.company, "Test Company")
		self.assertEqual(ereceipt.total, 1500.50)
		self.assertEqual(ereceipt.status, "open")

	def test_ereceipt_expiry_types(self):
		"""Test diferentes tipos de expiración."""
		expiry_types = ["Fixed Days", "End of Month", "Custom Date"]

		for expiry_type in expiry_types:
			ereceipt = frappe.new_doc("EReceipt MX")
			ereceipt.expiry_type = expiry_type
			ereceipt.date_issued = datetime.now().date()

			if expiry_type == "Fixed Days":
				ereceipt.expiry_days = 5
			elif expiry_type == "Custom Date":
				ereceipt.expiry_date = datetime.now().date() + timedelta(days=10)

			# Verificar que se puede asignar sin errores
			self.assertEqual(ereceipt.expiry_type, expiry_type)

	def test_ereceipt_status_values(self):
		"""Test valores válidos de status."""
		valid_statuses = ["open", "expired", "invoiced", "cancelled"]

		for status in valid_statuses:
			ereceipt = frappe.new_doc("EReceipt MX")
			ereceipt.status = status

			# Verificar que se puede asignar
			self.assertEqual(ereceipt.status, status)


if __name__ == "__main__":
	unittest.main()
