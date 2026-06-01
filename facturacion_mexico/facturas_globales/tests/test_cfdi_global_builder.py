"""
Tests para CFDIGlobalBuilder — configuración migrada a Company Settings.

Cubre:
  1. use = "S01" (no "usage" ni "G01")
  2. payload usa "global", no "complemento_global"
  3. customer sale de global_customer configurado
  4. item sale de global_item configurado
  5. falla con mensaje claro si falta Customer/Item
  6. falla si Customer no tiene RFC XAXX010101000
  7. payment_form usa global_payment_form_default
  8. no se requiere serie especial de Factura Global
  9. payment_method = PUE
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


def _mock_company_settings(global_customer="CLI-PUBLICO", global_item="ITEM-GLOBAL", payment_form="01"):
	return frappe._dict(
		{
			"global_customer": global_customer,
			"global_item": global_item,
			"global_payment_form_default": payment_form,
		}
	)


def _mock_customer(rfc="XAXX010101000", regimen="616 - Sin obligaciones fiscales"):
	doc = MagicMock()
	doc.customer_name = "PUBLICO EN GENERAL"
	doc.get = lambda field, default=None: {
		"tax_id": rfc,
		"fm_tax_regime": regimen,
		"email_id": "",
		"customer_primary_address": None,
	}.get(field, default)
	return doc


def _mock_item(product_key="84111506", unit_key="ACT"):
	doc = MagicMock()
	doc.item_code = "ITEM-GLOBAL"
	doc.description = "Ventas periodo"
	doc.get = lambda field, default=None: {
		"fm_producto_servicio_sat": product_key,
		"fm_unidad_sat": unit_key,
	}.get(field, default)
	return doc


def _mock_global_doc(company="Test Company", periodicidad="Mensual", receipts=None):
	doc = MagicMock()
	doc.company = company
	doc.periodicidad = periodicidad
	doc.name = "FG-Test-2026-01-0001"
	doc.receipts_detail = receipts or []
	doc.periodo_inicio = frappe.utils.getdate("2026-01-01")
	doc.periodo_fin = frappe.utils.getdate("2026-01-31")
	doc.cantidad_receipts = len(receipts or [])
	doc.total_periodo = 1000.0
	return doc


class TestCFDIGlobalBuilder(FrappeTestCase):
	def _make_builder(self, global_doc=None, customer=None, item=None, cs=None):
		"""Construye CFDIGlobalBuilder con mocks."""
		from facturacion_mexico.facturas_globales.processors.cfdi_global_builder import CFDIGlobalBuilder

		global_doc = global_doc or _mock_global_doc()
		mock_cs = cs or _mock_company_settings()
		mock_customer = customer or _mock_customer()
		mock_item = item or _mock_item()

		with patch("frappe.db.get_value", return_value=mock_cs):
			with patch("frappe.get_doc") as mock_get_doc:
				mock_get_doc.side_effect = lambda doctype, name: (
					mock_customer if doctype == "Customer" else MagicMock()
				)
				builder = CFDIGlobalBuilder(global_doc)
				builder._mock_customer = mock_customer
				builder._mock_item = mock_item
				return builder

	# ── use = "S01" — no "G01" ───────────────────────────────────────────────

	def test_use_is_s01(self):
		"""Payload usa use='S01', no usage='G01'."""
		builder = self._make_builder()
		with patch(
			"frappe.get_doc",
			side_effect=lambda dt, n: builder._mock_customer if dt == "Customer" else builder._mock_item,
		):
			with patch("frappe.db.get_value", return_value="01"):
				with patch(
					"facturacion_mexico.facturas_globales.processors.cfdi_global_builder.get_facturapi_client"
				):
					data = builder.build_global_invoice_data()
		self.assertEqual(data.get("use"), "S01")
		self.assertNotIn("usage", data)

	# ── objeto "global", no "complemento_global" ─────────────────────────────

	def test_payload_uses_global_not_complemento_global(self):
		"""Payload usa 'global', no 'complemento_global'."""
		builder = self._make_builder()
		with patch(
			"frappe.get_doc",
			side_effect=lambda dt, n: builder._mock_customer if dt == "Customer" else builder._mock_item,
		):
			with patch("frappe.db.get_value", return_value="01"):
				with patch(
					"facturacion_mexico.facturas_globales.processors.cfdi_global_builder.get_facturapi_client"
				):
					data = builder.build_global_invoice_data()
		self.assertIn("global", data)
		self.assertNotIn("complemento_global", data)

	# ── objeto global contiene periodicity, months, year ─────────────────────

	def test_global_object_structure(self):
		"""Objeto global tiene periodicity, months, year."""
		builder = self._make_builder()
		obj = builder._build_global_object()
		self.assertIn("periodicity", obj)
		self.assertIn("months", obj)
		self.assertIn("year", obj)
		self.assertEqual(obj["periodicity"], "04")  # Mensual
		self.assertEqual(obj["months"], "01")  # Enero
		self.assertEqual(obj["year"], 2026)

	# ── payment_method = PUE ──────────────────────────────────────────────────

	def test_payment_method_is_pue(self):
		"""payment_method debe ser 'PUE'."""
		builder = self._make_builder()
		with patch(
			"frappe.get_doc",
			side_effect=lambda dt, n: builder._mock_customer if dt == "Customer" else builder._mock_item,
		):
			with patch("frappe.db.get_value", return_value="01"):
				with patch(
					"facturacion_mexico.facturas_globales.processors.cfdi_global_builder.get_facturapi_client"
				):
					data = builder.build_global_invoice_data()
		self.assertEqual(data.get("payment_method"), "PUE")

	# ── falla si no hay Customer configurado ─────────────────────────────────

	def test_throws_if_no_global_customer(self):
		"""Lanza error si global_customer no está configurado."""
		from facturacion_mexico.facturas_globales.processors.cfdi_global_builder import CFDIGlobalBuilder

		cs_sin_customer = _mock_company_settings(global_customer=None)
		with patch("frappe.db.get_value", return_value=cs_sin_customer):
			with patch("frappe.get_doc"):
				with self.assertRaises(frappe.ValidationError):
					CFDIGlobalBuilder(_mock_global_doc())

	# ── falla si Customer no tiene RFC XAXX010101000 ─────────────────────────

	def test_throws_if_wrong_rfc(self):
		"""Lanza error si Customer tiene RFC distinto a XAXX010101000."""
		builder = self._make_builder(customer=_mock_customer(rfc="RFC-INCORRECTO"))
		with patch("frappe.get_doc", return_value=builder._mock_customer):
			with self.assertRaises(frappe.ValidationError):
				builder._build_customer_data()

	# ── falla si Item no tiene clave SAT ─────────────────────────────────────

	def test_throws_if_item_missing_product_key(self):
		"""Lanza error si Item no tiene clave SAT."""
		builder = self._make_builder(item=_mock_item(product_key=None))
		with patch("frappe.get_doc", return_value=builder._mock_item):
			with self.assertRaises(frappe.ValidationError):
				builder._build_items_data()

	# ── no se usa serie especial ──────────────────────────────────────────────

	def test_no_series_field_in_payload(self):
		"""No hay campo 'series' en el payload (no se requiere serie especial)."""
		builder = self._make_builder()
		with patch(
			"frappe.get_doc",
			side_effect=lambda dt, n: builder._mock_customer if dt == "Customer" else builder._mock_item,
		):
			with patch("frappe.db.get_value", return_value="01"):
				with patch(
					"facturacion_mexico.facturas_globales.processors.cfdi_global_builder.get_facturapi_client"
				):
					data = builder.build_global_invoice_data()
		self.assertNotIn("series", data)

	# ── payment_form desde Company Settings ──────────────────────────────────

	def test_payment_form_from_company_settings(self):
		"""payment_form usa global_payment_form_default cuando no hay forma clara de receipts."""
		builder = self._make_builder(cs=_mock_company_settings(payment_form="03"))
		with patch("frappe.db.get_value", return_value=None):  # Sin Payment Entry
			result = builder._get_payment_form()
		self.assertEqual(result, "03")
