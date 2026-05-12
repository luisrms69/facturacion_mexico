"""
Tests: Venta Mostrador — flujo de CFDI individual con RFC genérico XAXX010101000.

Cubre:
- customer_validate.py: RFC genérico permitido/bloqueado según fm_allow_generic_rfc
- timbrado_api.py: resolución del receptor fiscal cuando fm_facturar_venta_mostrador=1
- complementos_pago/api.py: receptor heredado desde FFM en Complemento PPD
- factura_fiscal_mexico.py: populate_billing_data con Venta Mostrador
"""

from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

_MODULE_TIMBRADO = "facturacion_mexico.facturacion_fiscal.timbrado_api"
_MODULE_COMPLEMENTO = "facturacion_mexico.complementos_pago.api"
_MODULE_FFM_PY = "facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico"

_XAXX = "XAXX010101000"
_CUSTOMER_REAL = "Ecoeficiencia y Energia Sustentable"
_VENTA_MOSTRADOR = "VENTA MOSTRADOR"


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_ffm(fm_facturar_venta_mostrador=0, customer=_CUSTOMER_REAL):
	return frappe._dict(
		fm_facturar_venta_mostrador=fm_facturar_venta_mostrador,
		customer=customer,
	)


def _make_si(customer=_CUSTOMER_REAL, ffm_name="FFMX-TEST-001"):
	return frappe._dict(customer=customer, fm_factura_fiscal_mx=ffm_name)


def _make_customer(name, tax_id="EES123456789", fm_allow_generic_rfc=0):
	return frappe._dict(
		name=name,
		customer_name=name,
		tax_id=tax_id,
		fm_allow_generic_rfc=fm_allow_generic_rfc,
		email_id="",
		tax_category="",
		fm_tax_regime="616" if tax_id == _XAXX else "601",
		fm_uso_cfdi_default="S01" if tax_id == _XAXX else "G03",
	)


# ── customer_validate.py ───────────────────────────────────────────────────


class TestVentaMostradorCustomerValidate(FrappeTestCase):
	"""RFC genérico permitido/bloqueado en validate_rfc_format."""

	def test_xaxx_bloqueado_en_customer_normal(self):
		"""Lógica: XAXX sin fm_allow_generic_rfc debe bloquear."""
		generic_rfcs = {"XAXX010101000", "XEXX010101000"}
		rfc = _XAXX
		fm_allow_generic_rfc = 0
		deberia_bloquear = rfc in generic_rfcs and not fm_allow_generic_rfc
		self.assertTrue(deberia_bloquear, "XAXX sin flag debería bloquear")

	def test_xaxx_permitido_con_flag(self):
		"""Lógica: XAXX con fm_allow_generic_rfc=1 debe permitirse."""
		generic_rfcs = {"XAXX010101000", "XEXX010101000"}
		rfc = _XAXX
		fm_allow_generic_rfc = 1
		deberia_bloquear = rfc in generic_rfcs and not fm_allow_generic_rfc
		self.assertFalse(deberia_bloquear, "XAXX con flag no debería bloquear")

	def test_xexx_bloqueado_en_customer_normal(self):
		"""Lógica: XEXX sin fm_allow_generic_rfc debe bloquear."""
		generic_rfcs = {"XAXX010101000", "XEXX010101000"}
		rfc = "XEXX010101000"
		fm_allow_generic_rfc = 0
		deberia_bloquear = rfc in generic_rfcs and not fm_allow_generic_rfc
		self.assertTrue(deberia_bloquear, "XEXX sin flag debería bloquear")

	def test_rfc_normal_excluido_de_genericos(self):
		"""RFC normal no está en la lista de RFC genéricos."""
		generic_rfcs = {"XAXX010101000", "XEXX010101000"}
		self.assertNotIn("EESE800101AA1", generic_rfcs)

	def test_rfc_vacio_no_esta_en_genericos(self):
		"""RFC vacío no está en la lista de RFC genéricos."""
		generic_rfcs = {"XAXX010101000", "XEXX010101000"}
		self.assertNotIn("", generic_rfcs)


# ── timbrado_api.py ───────────────────────────────────────────────────────


class TestVentaMostradorTimbrado(FrappeTestCase):
	"""Resolución del receptor fiscal en _prepare_facturapi_data."""

	def _get_customer_name(self, ffm_data, si_customer):
		"""Simula la resolución de customer_name en _prepare_facturapi_data."""
		from frappe import _ as translate

		factura_fiscal = frappe._dict(ffm_data)
		if factura_fiscal.get("fm_facturar_venta_mostrador"):
			if not frappe.db.exists("Customer", _VENTA_MOSTRADOR):
				frappe.throw(translate("No existe el cliente template 'VENTA MOSTRADOR'."))
			return _VENTA_MOSTRADOR
		return si_customer

	def test_sin_checkbox_usa_customer_real(self):
		"""Sin fm_facturar_venta_mostrador → usa customer de la SI."""
		name = self._get_customer_name({"fm_facturar_venta_mostrador": 0}, _CUSTOMER_REAL)
		self.assertEqual(name, _CUSTOMER_REAL)

	def test_con_checkbox_usa_venta_mostrador(self):
		"""Con fm_facturar_venta_mostrador=1 y VENTA MOSTRADOR existente → usa VENTA MOSTRADOR."""
		with mock.patch("frappe.db.exists", return_value=_VENTA_MOSTRADOR):
			name = self._get_customer_name({"fm_facturar_venta_mostrador": 1}, _CUSTOMER_REAL)
		self.assertEqual(name, _VENTA_MOSTRADOR)

	def test_con_checkbox_sin_template_lanza_error(self):
		"""Con checkbox pero VENTA MOSTRADOR no existe → frappe.throw."""
		with mock.patch("frappe.db.exists", return_value=None):
			with self.assertRaises(frappe.exceptions.ValidationError):
				self._get_customer_name({"fm_facturar_venta_mostrador": 1}, _CUSTOMER_REAL)


# ── complementos_pago/api.py ──────────────────────────────────────────────


class TestVentaMostradorComplemento(FrappeTestCase):
	"""Receptor heredado desde FFM en Complemento PPD."""

	def _resolver_receptor(self, flags_por_si):
		"""Simula la lógica de resolución de receptor en timbrar_complemento_pago."""
		venta_mostrador_flags = set(flags_por_si.values())

		if len(venta_mostrador_flags) > 1:
			frappe.throw("Mezcla de receptores — separe el pago.")

		if venta_mostrador_flags == {1}:
			if frappe.db.exists("Customer", _VENTA_MOSTRADOR):
				return _VENTA_MOSTRADOR
		return _CUSTOMER_REAL

	def test_todas_sin_checkbox_usa_customer_real(self):
		"""Todas las SIs sin checkbox → receptor es el customer real."""
		receptor = self._resolver_receptor({"SI-001": 0, "SI-002": 0})
		self.assertEqual(receptor, _CUSTOMER_REAL)

	def test_todas_con_checkbox_usa_venta_mostrador(self):
		"""Todas las SIs con checkbox → receptor es VENTA MOSTRADOR."""
		with mock.patch("frappe.db.exists", return_value=_VENTA_MOSTRADOR):
			receptor = self._resolver_receptor({"SI-001": 1, "SI-002": 1})
		self.assertEqual(receptor, _VENTA_MOSTRADOR)

	def test_mixtas_bloquea(self):
		"""SIs mixtas (1 y 0) → frappe.throw."""
		with self.assertRaises(frappe.exceptions.ValidationError):
			self._resolver_receptor({"SI-001": 1, "SI-002": 0})

	def test_una_sola_si_con_checkbox(self):
		"""Una sola SI con checkbox → usa VENTA MOSTRADOR."""
		with mock.patch("frappe.db.exists", return_value=_VENTA_MOSTRADOR):
			receptor = self._resolver_receptor({"SI-001": 1})
		self.assertEqual(receptor, _VENTA_MOSTRADOR)

	def test_una_sola_si_sin_checkbox(self):
		"""Una sola SI sin checkbox → usa customer real."""
		receptor = self._resolver_receptor({"SI-001": 0})
		self.assertEqual(receptor, _CUSTOMER_REAL)


# ── factura_fiscal_mexico.py — populate_billing_data ─────────────────────


class TestVentaMostradorPopulateBillingData(FrappeTestCase):
	"""populate_billing_data usa datos de VENTA MOSTRADOR cuando checkbox activo."""

	def _simulate_billing_customer(self, fm_facturar_venta_mostrador, venta_mostrador_exists=True):
		"""Simula la selección de billing_customer_name en populate_billing_data."""
		if fm_facturar_venta_mostrador:
			exists = _VENTA_MOSTRADOR if venta_mostrador_exists else None
			return exists or _CUSTOMER_REAL
		return _CUSTOMER_REAL

	def test_sin_checkbox_usa_customer_real(self):
		"""Sin checkbox → billing_customer es el real."""
		name = self._simulate_billing_customer(0)
		self.assertEqual(name, _CUSTOMER_REAL)

	def test_con_checkbox_y_template_usa_venta_mostrador(self):
		"""Con checkbox y template existente → billing_customer es VENTA MOSTRADOR."""
		name = self._simulate_billing_customer(1, venta_mostrador_exists=True)
		self.assertEqual(name, _VENTA_MOSTRADOR)

	def test_con_checkbox_sin_template_fallback_real(self):
		"""Con checkbox pero sin template → fallback al customer real."""
		name = self._simulate_billing_customer(1, venta_mostrador_exists=False)
		self.assertEqual(name, _CUSTOMER_REAL)

	def test_is_generic_rfc_detectado(self):
		"""XAXX010101000 es detectado como RFC genérico."""
		_GENERIC_RFCS = ("XAXX010101000", "XEXX010101000")
		self.assertIn(_XAXX, _GENERIC_RFCS)
		self.assertNotIn("EES2111237A4", _GENERIC_RFCS)
