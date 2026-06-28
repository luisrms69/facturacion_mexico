"""Resolución canónica del correo destinatario fiscal (FFM y Complemento de Pago).

Cubre el defecto reportado: el Complemento de Pago no usaba la misma fuente que la Factura
Fiscal (dirección principal del Customer), y la FFM tenía dos defectos latentes:
- guardaba un placeholder de aviso en `fm_email_facturacion` que mataba el fallback;
- consultaba el fallback con la company default global, no la del documento (multi-company).

Estas pruebas usan registros REALES (Customer / Address / Company Settings) — sin sobre-mockear,
que fue justo lo que impidió detectar el bug antes. El único boundary que se simula es FacturAPI.
"""

import inspect

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.facturacion_fiscal.email_recipient import (
	_is_valid_email,
	get_company_fallback_email,
	get_customer_primary_address_email,
	resolve_fiscal_recipient_email,
)


def _make_customer(suffix: str) -> str:
	c = frappe.get_doc(
		{"doctype": "Customer", "customer_name": f"TEST-EMAIL-{suffix}", "customer_type": "Company"}
	).insert(ignore_permissions=True)
	return c.name


def _ensure_default_address_template():
	"""CI no trae Address Template por defecto; insertar una Address dispara su render
	(`on_update` -> `get_address_display`), que falla sin un template default."""
	if frappe.db.exists("Address Template", {"is_default": 1}):
		return
	country = frappe.get_all("Country", limit=1, pluck="name")
	frappe.get_doc(
		{
			"doctype": "Address Template",
			"country": country[0] if country else "Mexico",
			"is_default": 1,
			"template": "{{ address_line1 or '' }}",
		}
	).insert(ignore_permissions=True)


def _first_company() -> str | None:
	"""Company existente de forma robusta (evita `get_value` con filtro vacío `{}`)."""
	default = frappe.defaults.get_global_default("company")
	if default:
		return default
	names = frappe.get_all("Company", limit=1, pluck="name")
	return names[0] if names else None


def _make_address(customer: str, suffix: str, email: str | None, primary: bool = True) -> str:
	_ensure_default_address_template()
	addr = frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": f"TEST-ADDR-{suffix}",
			"address_type": "Billing",
			"address_line1": "Calle Falsa 123",
			"city": "CDMX",
			"country": "Mexico",
			"pincode": "06000",
			"email_id": email,
			"is_primary_address": 1 if primary else 0,
			"links": [{"link_doctype": "Customer", "link_name": customer}],
		}
	).insert(ignore_permissions=True)
	if primary:
		frappe.db.set_value("Customer", customer, "customer_primary_address", addr.name)
	return addr.name


def _set_company_fallback(company: str, email: str | None):
	"""get_or_create Company Settings y fija customer_email_fallback (rollback por la suite)."""
	name = frappe.db.get_value("Facturacion Mexico Company Settings", {"company": company}, "name")
	if name:
		frappe.db.set_value("Facturacion Mexico Company Settings", name, "customer_email_fallback", email)
		return
	doc = frappe.get_doc(
		{
			"doctype": "Facturacion Mexico Company Settings",
			"company": company,
			"customer_email_fallback": email,
		}
	)
	doc.flags.ignore_validate = True
	doc.insert(ignore_permissions=True, ignore_mandatory=True)


class TestIsValidEmail(IntegrationTestCase):
	def test_accepts_real_emails(self):
		for good in [
			"cliente@example.com",
			"cliente@sub.example.com",
			"cliente.test@example.com.mx",
			"a@b.co",
		]:
			self.assertTrue(_is_valid_email(good), f"debió aceptar: {good!r}")

	def test_rejects_placeholder_and_invalid(self):
		for bad in [
			"",
			None,
			"   ",
			"⚠️ FALTA EMAIL EN DIRECCIÓN",
			"⚠️ SELECCIONA UN CLIENTE",
			"❌ ERROR AL OBTENER EMAIL",
			"no-arroba",
			"dos@@arrobas.com",
			"sin dominio@",
			"con espacio @x.com",
			# Dominios malformados (endurecimiento CodeRabbit #2)
			"cliente@.mx",
			"cliente@example..com",
			"cliente@mx",
			"cliente@example.com.",
			"cliente@.example.com",
			"@example.com",
			"cliente@",
		]:
			self.assertFalse(_is_valid_email(bad), f"debió rechazar: {bad!r}")


class TestResolveHelperRealRecords(IntegrationTestCase):
	def setUp(self):
		self.sfx = frappe.generate_hash()[:6]
		self.company = _first_company()

	def test_address_email_used(self):
		cust = _make_customer(self.sfx)
		_make_address(cust, self.sfx, "addr@example.com")
		self.assertEqual(
			resolve_fiscal_recipient_email(customer=cust, company=self.company), "addr@example.com"
		)

	def test_ignores_customer_email_id_uses_address(self):
		"""El helper NO usa Customer.email_id; prioriza la dirección principal."""
		cust = _make_customer(self.sfx)
		frappe.db.set_value("Customer", cust, "email_id", "customer-directo@example.com")
		_make_address(cust, self.sfx, "addr@example.com")
		out = resolve_fiscal_recipient_email(customer=cust, company=self.company)
		self.assertEqual(out, "addr@example.com")
		self.assertNotEqual(out, "customer-directo@example.com")

	def test_fallback_when_address_has_no_email(self):
		if not self.company:
			self.skipTest("entorno de pruebas sin Company")
		cust = _make_customer(self.sfx)
		_make_address(cust, self.sfx, None)  # dirección sin correo
		_set_company_fallback(self.company, "fallback@empresa.com")
		self.assertEqual(
			resolve_fiscal_recipient_email(customer=cust, company=self.company), "fallback@empresa.com"
		)

	def test_none_when_no_address_no_fallback(self):
		cust = _make_customer(self.sfx)
		_make_address(cust, self.sfx, None)
		_set_company_fallback(self.company, None)
		self.assertIsNone(resolve_fiscal_recipient_email(customer=cust, company=self.company))

	def test_to_override_wins(self):
		cust = _make_customer(self.sfx)
		_make_address(cust, self.sfx, "addr@example.com")
		self.assertEqual(
			resolve_fiscal_recipient_email(customer=cust, company=self.company, to="override@example.com"),
			"override@example.com",
		)

	def test_to_override_invalid_falls_through(self):
		cust = _make_customer(self.sfx)
		_make_address(cust, self.sfx, "addr@example.com")
		self.assertEqual(
			resolve_fiscal_recipient_email(customer=cust, company=self.company, to="⚠️ no-email"),
			"addr@example.com",
		)

	def test_stored_email_real_used(self):
		cust = _make_customer(self.sfx)
		_make_address(cust, self.sfx, "addr@example.com")
		self.assertEqual(
			resolve_fiscal_recipient_email(
				customer=cust, company=self.company, stored_email="ffm-real@example.com"
			),
			"ffm-real@example.com",
		)

	def test_stored_placeholder_ignored(self):
		cust = _make_customer(self.sfx)
		_make_address(cust, self.sfx, "addr@example.com")
		out = resolve_fiscal_recipient_email(
			customer=cust, company=self.company, stored_email="⚠️ FALTA EMAIL EN DIRECCIÓN"
		)
		self.assertEqual(out, "addr@example.com")


class TestCompanyFallbackScoping(IntegrationTestCase):
	"""Multi-company: el fallback se lee por la company del documento, nunca por la global."""

	def setUp(self):
		self.company = _first_company()
		if not self.company:
			self.skipTest("entorno de pruebas sin Company")

	def test_fallback_scoped_to_company(self):
		_set_company_fallback(self.company, "scoped@empresa.com")
		self.assertEqual(get_company_fallback_email(self.company), "scoped@empresa.com")

	def test_other_company_does_not_get_this_fallback(self):
		_set_company_fallback(self.company, "scoped@empresa.com")
		# Una company distinta (inexistente) no debe heredar el fallback de otra.
		self.assertIsNone(get_company_fallback_email("Compania Inexistente ZZZ"))

	def test_no_company_returns_none_not_global_default(self):
		# Sin company, NO se usa frappe.defaults global: simplemente no hay fallback.
		self.assertIsNone(get_company_fallback_email(None))


class TestFFMResolverDelegation(IntegrationTestCase):
	def test_ffm_resolver_passes_document_company(self):
		"""_resolve_recipient_email delega al helper con la company del documento (multi-company)."""
		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico import (
			factura_fiscal_mexico as ffm_mod,
		)

		captured = {}

		def fake_resolver(**kwargs):
			captured.update(kwargs)
			return "x@y.com"

		ffm = frappe.get_doc({"doctype": "Factura Fiscal Mexico"})  # doc en memoria, sin insertar
		ffm.customer = "CUST-A"
		ffm.company = "COMPANY-A"
		ffm.fm_email_facturacion = "stored@y.com"

		with self.patch_resolver(ffm_mod, fake_resolver):
			ffm_mod._resolve_recipient_email(ffm)

		self.assertEqual(captured.get("company"), "COMPANY-A")
		self.assertEqual(captured.get("customer"), "CUST-A")
		self.assertEqual(captured.get("stored_email"), "stored@y.com")

	def patch_resolver(self, _mod, fn):
		import unittest.mock as m

		# _resolve_recipient_email importa el helper localmente desde el módulo fuente,
		# así que se parchea ahí (no en el módulo de la FFM).
		return m.patch(
			"facturacion_mexico.facturacion_fiscal.email_recipient.resolve_fiscal_recipient_email",
			side_effect=fn,
		)

	def test_manual_and_auto_use_same_resolver(self):
		"""Conductual: el envío manual (`_send_cfdi_email`) y el automático (`_send_fiscal_email`)
		llaman al MISMO resolver `_resolve_recipient_email` con el documento (company correcta),
		sin comunicación externa real (FacturAPI mockeado)."""
		import unittest.mock as m
		from types import SimpleNamespace

		from facturacion_mexico.facturacion_fiscal import timbrado_api as t_mod
		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico import (
			factura_fiscal_mexico as ffm_mod,
		)

		captured = []

		def fake_resolver(doc):
			captured.append(doc)
			return "dest@example.com"

		ffm = frappe.get_doc({"doctype": "Factura Fiscal Mexico"})  # doc en memoria, sin insertar
		ffm.customer = "CUST-Z"
		ffm.company = "COMPANY-Z"
		ffm.fm_uuid = "UUID-123"
		ffm.facturapi_id = "fapi-123"
		ffm.add_comment = lambda *a, **k: None  # doc sin guardar: no insertar Comment

		# Ambos flujos resuelven vía _resolve_recipient_email (el automático lo importa localmente
		# desde el mismo módulo, así que basta parchear ahí).
		with m.patch.object(ffm_mod, "_resolve_recipient_email", side_effect=fake_resolver):
			# MANUAL: FacturAPIClient se importa dentro de _send_cfdi_email desde api_client.
			with m.patch("facturacion_mexico.facturacion_fiscal.api_client.FacturAPIClient") as MockClient:
				result = ffm_mod._send_cfdi_email(ffm)
				self.assertTrue(result.get("sent"))
				self.assertEqual(result.get("to"), "dest@example.com")
				MockClient.return_value.send_invoice_email.assert_called_once_with(
					"fapi-123", "dest@example.com"
				)

			# AUTOMÁTICO post-timbrado: self.client es el boundary externo (mockeado).
			fake_timbrado = SimpleNamespace(client=m.MagicMock())
			t_mod.TimbradoAPI._send_fiscal_email(fake_timbrado, ffm, "fapi-123")
			fake_timbrado.client.send_invoice_email.assert_called_once_with("fapi-123", "dest@example.com")

		# Verificación clave: ambos flujos llamaron al MISMO resolver con el documento (company correcta).
		self.assertEqual(len(captured), 2)
		for doc in captured:
			self.assertIs(doc, ffm)
			self.assertEqual(getattr(doc, "company", None), "COMPANY-Z")


class TestComplementoUsesCanonicalResolver(IntegrationTestCase):
	def test_action_uses_helper_with_doc_customer_and_company(self):
		"""action_send_email_complemento usa comp.customer/comp.company vía el helper,
		ignorando Payment Entry.contact_email y Customer.email_id."""
		src = inspect.getsource(
			frappe.get_attr("facturacion_mexico.complementos_pago.api.action_send_email_complemento")
		)
		# Usa el resolver canónico con el documento como fuente.
		self.assertIn("resolve_fiscal_recipient_email", src)
		self.assertIn("comp.customer", src)
		self.assertIn("comp.company", src)
		# Ya NO consulta las fuentes prohibidas.
		self.assertNotIn("contact_email", src)
		self.assertNotIn('"email_id"', src)


class TestPopulateBillingDataNoPlaceholder(IntegrationTestCase):
	def test_no_placeholder_stored_in_email_field(self):
		"""Con dirección principal sin correo, fm_email_facturacion queda VACÍO (no un aviso)."""
		sfx = frappe.generate_hash()[:6]
		cust = _make_customer(sfx)
		_make_address(cust, sfx, None)  # sin email
		ffm = frappe.get_doc({"doctype": "Factura Fiscal Mexico"})
		ffm.customer = cust
		ffm.populate_billing_data()
		self.assertEqual(ffm.fm_email_facturacion, "")
		self.assertNotIn("⚠", ffm.fm_email_facturacion or "")


class TestNoOperationalGlobalSettingsReference(IntegrationTestCase):
	def test_no_code_reads_legacy_global_settings(self):
		"""Ningún .py operativo debe leer el DocType global removido 'Facturacion Mexico Settings'."""
		import os

		import facturacion_mexico

		root = os.path.dirname(facturacion_mexico.__file__)
		offenders = []
		read_calls = ("get_single(", "get_cached_single(", "get_doc(", "get_value(")
		for dirpath, _dirs, files in os.walk(root):
			if "/tests" in dirpath or "__pycache__" in dirpath:
				continue
			for fn in files:
				if not fn.endswith(".py"):
					continue
				path = os.path.join(dirpath, fn)
				with open(path, encoding="utf-8") as fh:
					content = fh.read()
				if "Facturacion Mexico Settings" not in content:
					continue
				for line in content.splitlines():
					if "Company Settings" in line:
						continue
					if "Facturacion Mexico Settings" in line and any(rc in line for rc in read_calls):
						offenders.append(f"{path}: {line.strip()}")
		self.assertEqual(offenders, [], f"Lecturas operativas del setting global: {offenders}")
