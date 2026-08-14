"""Tests de la guarda central de ambiente fiscal — issue #215.

Verifican que las operaciones MUTANTES al PAC se bloqueen (sin contactar a FacturAPI)
cuando el ambiente del sitio es inseguro, y que producción/sandbox legítimos y los GET
sigan funcionando. Nunca se contacta a FacturAPI real: `requests.request` está mockeado.
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

_REQUESTS_TARGET = "facturacion_mexico.facturacion_fiscal.api_client.requests.request"


def _fake_ok_response():
	resp = MagicMock()
	resp.ok = True
	resp.status_code = 201
	resp.headers = {"Content-Type": "application/json"}
	resp.json.return_value = {"id": "inv_test", "livemode": False}
	return resp


class TestPacEnvironmentGuard(FrappeTestCase):
	def _client(self, environment, api_key="", test_api_key=""):
		"""Construye un FacturAPIClient con ambiente y credenciales controlados."""
		from facturacion_mexico.facturacion_fiscal.api_client import FacturAPIClient

		settings = frappe._dict(
			{"name": "FMCS-Test", "sandbox_mode": 1, "api_key": api_key, "test_api_key": test_api_key}
		)

		def mock_pwd(doctype, name, fieldname, raise_exception=True):
			return settings.get(fieldname) or ""

		with (
			patch(
				"frappe.db.get_value",
				side_effect=lambda doctype, filters, fields, **kw: (
					settings if doctype == "Facturacion Mexico Company Settings" else None
				),
			),
			patch("frappe.utils.password.get_decrypted_password", side_effect=mock_pwd),
			patch(
				"facturacion_mexico.facturacion_fiscal.pac_environment.get_fm_environment",
				return_value=environment,
			),
		):
			return FacturAPIClient(company="Test Company")

	# 1. production + api_key válida + POST → permitido
	def test_production_post_allowed(self):
		client = self._client("production", api_key="prod-key")
		with patch(_REQUESTS_TARGET, return_value=_fake_ok_response()) as req:
			result = client.create_invoice({"type": "I"})
		req.assert_called_once()
		self.assertTrue(result["success"])

	# 2. sandbox + test_api_key válida + POST → permitido
	def test_sandbox_post_allowed(self):
		client = self._client("sandbox", test_api_key="sk_test_ok")
		with patch(_REQUESTS_TARGET, return_value=_fake_ok_response()) as req:
			result = client.create_invoice({"type": "I"})
		req.assert_called_once()
		self.assertTrue(result["success"])

	# 3. falta fm_environment + POST → bloqueado y requests.request NO llamado
	def test_missing_environment_post_blocked(self):
		client = self._client("", api_key="prod-key")
		with patch(_REQUESTS_TARGET) as req:
			with self.assertRaises(frappe.ValidationError):
				client.create_invoice({"type": "I"})
		req.assert_not_called()

	# 4. valor inválido + POST → bloqueado
	def test_invalid_environment_post_blocked(self):
		client = self._client("staging", api_key="prod-key")
		with patch(_REQUESTS_TARGET) as req:
			with self.assertRaises(frappe.ValidationError):
				client.create_invoice({"type": "I"})
		req.assert_not_called()

	# 5. production sin api_key → bloqueado
	def test_production_without_api_key_blocked(self):
		client = self._client("production", api_key="")
		with patch(_REQUESTS_TARGET) as req:
			with self.assertRaises(frappe.ValidationError):
				client.create_invoice({"type": "I"})
		req.assert_not_called()

	# 6. sandbox sin test_api_key → bloqueado
	def test_sandbox_without_test_api_key_blocked(self):
		client = self._client("sandbox", test_api_key="")
		with patch(_REQUESTS_TARGET) as req:
			with self.assertRaises(frappe.ValidationError):
				client.create_invoice({"type": "I"})
		req.assert_not_called()

	# 7. sandbox + test_api_key que contiene sk_live_ → bloqueado
	def test_sandbox_with_live_key_blocked(self):
		client = self._client("sandbox", test_api_key="sk_live_leaked")
		with patch(_REQUESTS_TARGET) as req:
			with self.assertRaises(frappe.ValidationError):
				client.create_invoice({"type": "I"})
		req.assert_not_called()

	# 8. GET continúa permitido (incluso con ambiente ausente)
	def test_get_allowed_even_without_environment(self):
		client = self._client("", api_key="")
		with patch(_REQUESTS_TARGET, return_value=_fake_ok_response()) as req:
			client.get_invoice("inv_1")
		req.assert_called_once()

	# 9. payload/endpoint de una operación permitida NO cambia
	def test_allowed_payload_and_endpoint_unchanged(self):
		client = self._client("production", api_key="prod-key")
		data = {"type": "E", "related_documents": [{"relationship": "03", "documents": ["UUID-1"]}]}
		with patch(_REQUESTS_TARGET, return_value=_fake_ok_response()) as req:
			client.create_invoice(data)
		_, kwargs = req.call_args
		self.assertEqual(kwargs["method"], "POST")
		self.assertTrue(kwargs["url"].endswith("/invoices"))
		self.assertEqual(kwargs["json"], data)
