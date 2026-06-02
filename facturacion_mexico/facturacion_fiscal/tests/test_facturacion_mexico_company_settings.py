"""
Tests para Facturacion Mexico Company Settings — sandbox_mode, api_key, test_api_key.

Cubre:
  1. Sin Company Settings → throw
  2. Sin company → throw
  3. sandbox_mode desde Company Settings
  4. api_key (producción) desde Company Settings
  5. test_api_key (sandbox) desde Company Settings
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


def _mock_company_settings(sandbox_mode=1, api_key="cs-prod-key", test_api_key="cs-test-key"):
	"""Dict que simula Facturacion Mexico Company Settings."""
	return frappe._dict(
		{"name": "FMCS-Test", "sandbox_mode": sandbox_mode, "api_key": api_key, "test_api_key": test_api_key}
	)


class TestCompanySettingsClient(FrappeTestCase):
	def _make_client(self, company="Test Company", company_settings=None):
		"""Construye FacturAPIClient mockeando acceso a BD y desencriptación de passwords."""
		from facturacion_mexico.facturacion_fiscal.api_client import FacturAPIClient

		def mock_get_decrypted_password(doctype, name, fieldname, raise_exception=True):
			if company_settings is None:
				return ""
			return company_settings.get(fieldname) or ""

		with (
			patch(
				"frappe.db.get_value",
				side_effect=lambda doctype, filters, fields, **kw: (
					company_settings if doctype == "Facturacion Mexico Company Settings" else None
				),
			),
			patch(
				"frappe.utils.password.get_decrypted_password",
				side_effect=mock_get_decrypted_password,
			),
		):
			return FacturAPIClient(company=company)

	# ── Sin Company Settings → throw ─────────────────────────────────────────

	def test_throws_when_no_company_settings(self):
		"""Sin Company Settings → frappe.throw."""
		with self.assertRaises(frappe.ValidationError):
			self._make_client(company="Sin Configurar", company_settings=None)

	def test_throws_when_no_company(self):
		"""Sin company → frappe.throw."""
		from facturacion_mexico.facturacion_fiscal.api_client import FacturAPIClient

		with self.assertRaises(frappe.ValidationError):
			FacturAPIClient(company=None)

	# ── sandbox_mode ──────────────────────────────────────────────────────────

	def test_sandbox_mode_true(self):
		client = self._make_client(company_settings=_mock_company_settings(sandbox_mode=1))
		self.assertTrue(client.sandbox_mode)

	def test_sandbox_mode_false(self):
		client = self._make_client(company_settings=_mock_company_settings(sandbox_mode=0))
		self.assertFalse(client.sandbox_mode)

	# ── api_key (producción) ──────────────────────────────────────────────────

	def test_prod_uses_api_key(self):
		"""sandbox=0 → api_key de Company Settings."""
		client = self._make_client(
			company_settings=_mock_company_settings(sandbox_mode=0, api_key="mi-prod-key")
		)
		self.assertEqual(client.api_key, "mi-prod-key")

	def test_prod_empty_api_key_returns_empty(self):
		"""sandbox=0 sin api_key → cadena vacía."""
		client = self._make_client(company_settings=_mock_company_settings(sandbox_mode=0, api_key=""))
		self.assertEqual(client.api_key, "")

	# ── test_api_key (sandbox) ────────────────────────────────────────────────

	def test_sandbox_uses_test_api_key(self):
		"""sandbox=1 → test_api_key de Company Settings."""
		client = self._make_client(
			company_settings=_mock_company_settings(sandbox_mode=1, test_api_key="mi-test-key")
		)
		self.assertEqual(client.api_key, "mi-test-key")

	def test_sandbox_empty_test_api_key_returns_empty(self):
		"""sandbox=1 sin test_api_key → cadena vacía."""
		client = self._make_client(company_settings=_mock_company_settings(sandbox_mode=1, test_api_key=""))
		self.assertEqual(client.api_key, "")

	def test_sandbox_does_not_use_prod_key(self):
		"""sandbox=1 → NO usa api_key aunque esté configurada."""
		client = self._make_client(
			company_settings=_mock_company_settings(
				sandbox_mode=1, api_key="prod-key", test_api_key="test-key"
			)
		)
		self.assertEqual(client.api_key, "test-key")
		self.assertNotEqual(client.api_key, "prod-key")
