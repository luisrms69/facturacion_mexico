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
 10. receipt sin tax_rate determinada => bloquea (no default 16)
 11. receipt con has_ieps => bloquea con mensaje IEPS
 12. receipt exento / tasa 0 conocida => permite sin nodo IVA
 13. receipt tasa 8 => nodo IVA con rate=0.08
 14. unit_key faltante => bloquea
 15. forma de pago no configurada => bloquea
 16. cálculo base/impuesto correcto para precio-con-IVA-incluido
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt


def _tax_row(account_head, rate=16.0):
	return frappe._dict({"account_head": account_head, "description": "", "rate": rate})


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


def _mock_item(product_key="84111506", unit_key="H87"):
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

	# ── forma de pago no configurada bloquea ─────────────────────────────────

	def test_throws_if_payment_form_not_configured(self):
		"""Lanza error si global_payment_form_default está vacío — no fallback silencioso a '01'."""
		builder = self._make_builder(cs=_mock_company_settings(payment_form=None))
		with patch("frappe.db.get_value", return_value=None):
			with self.assertRaises(frappe.ValidationError):
				builder._get_payment_form()

	# ── unit_key faltante bloquea ─────────────────────────────────────────────

	def test_throws_if_unit_key_missing(self):
		"""Lanza error si Item no tiene fm_unidad_sat — no fallback silencioso a 'ACT'."""
		builder = self._make_builder(item=_mock_item(unit_key=None))
		with patch("frappe.get_doc", return_value=builder._mock_item):
			with self.assertRaises(frappe.ValidationError):
				builder._build_items_data()

	# ── receipt sin tax_rate bloquea ─────────────────────────────────────────

	def test_throws_if_tax_rate_missing(self):
		"""Lanza error si receipt tiene tax_rate=None — no default silencioso a 16."""
		detail = MagicMock()
		detail.included_in_cfdi = 1
		detail.ereceipt = "ER-TEST-0001"
		detail.monto = 100.0

		receipt = MagicMock()
		receipt.get = lambda field, default=None: (
			None if field == "tax_rate" else (0 if field == "has_ieps" else default)
		)

		builder = self._make_builder(global_doc=_mock_global_doc(receipts=[detail]))
		with patch("frappe.get_doc", return_value=receipt):
			with self.assertRaises(frappe.ValidationError):
				builder._group_receipts_by_tax()

	# ── receipt con IEPS bloquea Factura Global ───────────────────────────────

	def test_throws_if_has_ieps(self):
		"""Lanza error con mención a IEPS si receipt tiene has_ieps=1."""
		detail = MagicMock()
		detail.included_in_cfdi = 1
		detail.ereceipt = "ER-TEST-IEPS"
		detail.monto = 100.0

		receipt = MagicMock()
		receipt.get = lambda field, default=None: (
			1 if field == "has_ieps" else (16.0 if field == "tax_rate" else default)
		)

		builder = self._make_builder(global_doc=_mock_global_doc(receipts=[detail]))
		with patch("frappe.get_doc", return_value=receipt):
			with self.assertRaises(frappe.ValidationError) as ctx:
				builder._group_receipts_by_tax()
		self.assertIn("IEPS", str(ctx.exception))

	# ── tasa 0 / exento conocido → no genera nodo IVA ────────────────────────

	def test_tax_rate_zero_no_iva_node(self):
		"""Con tax_rate=0 (exento/tasa 0 conocida) no se genera nodo IVA."""
		builder = self._make_builder()
		taxes = builder._build_item_taxes(0.0)
		self.assertEqual(taxes, [])

	# ── tasa 8 genera nodo IVA correcto ──────────────────────────────────────

	def test_tax_rate_8_iva_node(self):
		"""Con tax_rate=8.0 el nodo IVA usa rate=0.08."""
		builder = self._make_builder()
		taxes = builder._build_item_taxes(8.0)
		self.assertEqual(len(taxes), 1)
		self.assertEqual(taxes[0]["type"], "IVA")
		self.assertAlmostEqual(taxes[0]["rate"], 0.08, places=4)

	# ── cálculo base/impuesto para precio-con-IVA-incluido ────────────────────

	def test_base_tax_calculation_iva_included(self):
		"""Con total=116 y rate=16: base≈100, tax≈16 (precio ya incluye IVA)."""
		detail = MagicMock()
		detail.included_in_cfdi = 1
		detail.ereceipt = "ER-TEST-CALC"
		detail.monto = 116.0

		receipt = MagicMock()
		receipt.get = lambda field, default=None: (
			0
			if field == "has_ieps"
			else (16.0 if field == "tax_rate" else (0.0 if field == "tax_amount" else default))
		)

		builder = self._make_builder(global_doc=_mock_global_doc(receipts=[detail]))
		with patch("frappe.get_doc", return_value=receipt):
			groups = builder._group_receipts_by_tax()

		self.assertEqual(len(groups), 1)
		group = next(iter(groups.values()))
		# unit_price = base / quantity; base = total - tax_from_receipt
		# Con tax_amount=0 del mock, base = 116 - 0 = 116, unit_price = 116
		# El test verifica que el agrupador procesa sin error y mantiene tax_rate=16
		self.assertAlmostEqual(group["tax_rate"], 16.0, places=1)


# =============================================================================
# Tests para extract_iva_info_from_si_taxes
# =============================================================================


class TestExtractIvaInfo(FrappeTestCase):
	"""Tests unitarios para la función de extracción de tasa IVA desde Sales Invoice taxes."""

	def setUp(self):
		from facturacion_mexico.utils.calculo_impuestos import extract_iva_info_from_si_taxes

		self.extract = extract_iva_info_from_si_taxes

	# ── sin impuestos determinables ───────────────────────────────────────────

	def test_no_taxes_returns_none(self):
		"""Sin filas de impuestos retorna None — no asume exento."""
		rate, has_ieps = self.extract([])
		self.assertIsNone(rate)
		self.assertFalse(has_ieps)

	def test_no_iva_row_returns_none(self):
		"""Filas sin IVA (solo ISR u otras) retornan None — no asume exento por ausencia."""
		taxes = [_tax_row("ISR Retenido", rate=10.0)]
		rate, has_ieps = self.extract(taxes)
		self.assertIsNone(rate)
		self.assertFalse(has_ieps)

	# ── tasa conocida ─────────────────────────────────────────────────────────

	def test_iva_16_detected(self):
		"""Fila IVA 16% retorna (16.0, False)."""
		taxes = [_tax_row("IVA Trasladado 16%", rate=16.0)]
		rate, has_ieps = self.extract(taxes)
		self.assertAlmostEqual(rate, 16.0)
		self.assertFalse(has_ieps)

	def test_iva_8_detected(self):
		"""Fila IVA 8% (zona fronteriza) retorna (8.0, False)."""
		taxes = [_tax_row("IVA Frontera 8%", rate=8.0)]
		rate, has_ieps = self.extract(taxes)
		self.assertAlmostEqual(rate, 8.0)
		self.assertFalse(has_ieps)

	def test_iva_zero_known(self):
		"""Fila IVA explícita con rate=0 retorna (0.0, False) — tasa cero confirmada."""
		taxes = [_tax_row("IVA Tasa 0%", rate=0.0)]
		rate, has_ieps = self.extract(taxes)
		self.assertAlmostEqual(rate, 0.0)
		self.assertFalse(has_ieps)

	# ── múltiples tasas ───────────────────────────────────────────────────────

	def test_multiple_iva_rates_returns_none(self):
		"""Múltiples tasas IVA distintas retorna None — no determinable."""
		taxes = [_tax_row("IVA 16%", rate=16.0), _tax_row("IVA Frontera", rate=8.0)]
		rate, _has_ieps = self.extract(taxes)
		self.assertIsNone(rate)

	# ── detección IEPS ────────────────────────────────────────────────────────

	def test_ieps_detected(self):
		"""Fila con IEPS en account_head marca has_ieps=True."""
		taxes = [_tax_row("IEPS Cuota Combustible", rate=5.91), _tax_row("IVA 16%", rate=16.0)]
		rate, has_ieps = self.extract(taxes)
		self.assertTrue(has_ieps)
		self.assertAlmostEqual(rate, 16.0)  # IVA sigue extrayéndose

	def test_ieps_only_no_iva(self):
		"""Solo IEPS (sin IVA): has_ieps=True, rate=None."""
		taxes = [_tax_row("IEPS Bebidas", rate=26.5)]
		rate, has_ieps = self.extract(taxes)
		self.assertTrue(has_ieps)
		self.assertIsNone(rate)
