"""
Tests para facturacion_mexico.setup.payment_terms.ensure_default_payment_terms.

Verifica creación idempotente de los 5 Payment Terms y 5 Payment Terms Templates FM.
"""

import unittest

import frappe

from facturacion_mexico.setup.payment_terms import _PAYMENT_TERMS, ensure_default_payment_terms

_PT_NAMES = [pt["name"] for pt in _PAYMENT_TERMS]


class TestEnsureDefaultPaymentTerms(unittest.TestCase):
	"""Creación idempotente de Payment Terms y Templates FM estándar."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Eliminar registros FM previos para probar creación desde cero
		for name in _PT_NAMES:
			if frappe.db.exists("Payment Terms Template", name):
				frappe.delete_doc("Payment Terms Template", name, force=True)
			if frappe.db.exists("Payment Term", name):
				frappe.delete_doc("Payment Term", name, force=True)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		# Dejar los registros creados — son datos de configuración útiles en el site de tests
		super().tearDownClass()

	def test_crea_cinco_payment_terms(self):
		"""ensure_default_payment_terms crea exactamente los 5 Payment Terms FM."""
		ensure_default_payment_terms()
		for name in _PT_NAMES:
			self.assertTrue(
				frappe.db.exists("Payment Term", name),
				f"Payment Term no creado: {name}",
			)

	def test_crea_cinco_payment_terms_templates(self):
		"""ensure_default_payment_terms crea exactamente los 5 Payment Terms Templates FM."""
		ensure_default_payment_terms()
		for name in _PT_NAMES:
			self.assertTrue(
				frappe.db.exists("Payment Terms Template", name),
				f"Payment Terms Template no creado: {name}",
			)

	def test_credit_days_correctos(self):
		"""Cada Payment Term tiene los credit_days correctos según la definición."""
		ensure_default_payment_terms()
		expected = {pt["name"]: pt["credit_days"] for pt in _PAYMENT_TERMS}
		for name, days in expected.items():
			actual = frappe.db.get_value("Payment Term", name, "credit_days")
			self.assertEqual(actual, days, f"{name}: credit_days esperado {days}, obtenido {actual}")

	def test_idempotente_no_duplica(self):
		"""Ejecutar dos veces no duplica Payment Terms ni Templates."""
		ensure_default_payment_terms()
		ensure_default_payment_terms()
		for name in _PT_NAMES:
			count_pt = frappe.db.count("Payment Term", {"payment_term_name": name})
			count_ptt = frappe.db.count("Payment Terms Template", {"template_name": name})
			self.assertEqual(count_pt, 1, f"Payment Term duplicado: {name}")
			self.assertEqual(count_ptt, 1, f"Payment Terms Template duplicado: {name}")
