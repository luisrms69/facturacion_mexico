"""Tests de selección de credencial de FacturAPIClient — modelo `fm_environment` (issue #215).

La credencial se elige por el ambiente del sitio (`fm_environment` en site_config.json),
NO por `sandbox_mode` de BD:
  1. Sin Company Settings → throw
  2. Sin company → throw
  3. `sandbox_mode` derivado de `fm_environment`
  4. production → api_key
  5. sandbox → test_api_key (nunca api_key)
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


def _mock_company_settings(api_key="cs-prod-key", test_api_key="cs-test-key"):
	"""Dict que simula Facturacion Mexico Company Settings (sandbox_mode ya no decide)."""
	return frappe._dict(
		{"name": "FMCS-Test", "sandbox_mode": 1, "api_key": api_key, "test_api_key": test_api_key}
	)


class TestCompanySettingsClient(FrappeTestCase):
	def _make_client(self, company="Test Company", company_settings=None, environment="sandbox"):
		"""Construye FacturAPIClient mockeando BD, desencriptación y ambiente del sitio."""
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
			patch(
				"facturacion_mexico.facturacion_fiscal.pac_environment.get_fm_environment",
				return_value=environment,
			),
		):
			return FacturAPIClient(company=company)

	# ── Sin Company Settings / sin company → throw ───────────────────────────

	def test_throws_when_no_company_settings(self):
		"""Ambiente válido pero sin Company Settings → frappe.throw."""
		with self.assertRaises(frappe.ValidationError):
			self._make_client(company="Sin Configurar", company_settings=None, environment="production")

	def test_throws_when_no_company(self):
		"""Ambiente válido pero sin company → frappe.throw."""
		with self.assertRaises(frappe.ValidationError):
			self._make_client(company=None, company_settings=None, environment="production")

	# ── sandbox_mode derivado de fm_environment ──────────────────────────────

	def test_sandbox_mode_derived_true(self):
		client = self._make_client(company_settings=_mock_company_settings(), environment="sandbox")
		self.assertTrue(client.sandbox_mode)

	def test_sandbox_mode_derived_false(self):
		client = self._make_client(company_settings=_mock_company_settings(), environment="production")
		self.assertFalse(client.sandbox_mode)

	# ── production → api_key ─────────────────────────────────────────────────

	def test_production_uses_api_key(self):
		client = self._make_client(
			company_settings=_mock_company_settings(api_key="mi-prod-key"), environment="production"
		)
		self.assertEqual(client.api_key, "mi-prod-key")

	def test_production_empty_api_key_returns_empty(self):
		client = self._make_client(
			company_settings=_mock_company_settings(api_key=""), environment="production"
		)
		self.assertEqual(client.api_key, "")

	# ── sandbox → test_api_key ───────────────────────────────────────────────

	def test_sandbox_uses_test_api_key(self):
		client = self._make_client(
			company_settings=_mock_company_settings(test_api_key="mi-test-key"), environment="sandbox"
		)
		self.assertEqual(client.api_key, "mi-test-key")

	def test_sandbox_empty_test_api_key_returns_empty(self):
		client = self._make_client(
			company_settings=_mock_company_settings(test_api_key=""), environment="sandbox"
		)
		self.assertEqual(client.api_key, "")

	def test_sandbox_does_not_use_prod_key(self):
		"""sandbox → usa test_api_key aunque api_key esté configurada."""
		client = self._make_client(
			company_settings=_mock_company_settings(api_key="prod-key", test_api_key="test-key"),
			environment="sandbox",
		)
		self.assertEqual(client.api_key, "test-key")
		self.assertNotEqual(client.api_key, "prod-key")
