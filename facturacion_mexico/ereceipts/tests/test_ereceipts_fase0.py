"""
Tests Fase 0 — E-Receipts: payload fiscal correcto + trazabilidad SI ↔ EReceipt MX.

Cubre:
- Payload enviado a FacturAPI no usa product_key "01010101" si el Item tiene fm_producto_servicio_sat.
- RFC enviado a FacturAPI usa Customer.tax_id (no campo 'rfc' inexistente).
- Email falso nunca se envía a FacturAPI.
- Impuestos IVA incluidos en items del receipt si tax_rate está definido.
- Sin impuestos si tax_rate es None.
- get_ereceipt_summary devuelve datos correctos por estado.
- get_ereceipt_summary no copia UUID a Sales Invoice.
- Al crear EReceipt exitoso, SI.fm_ereceipt_mx y SI.fm_fiscal_status=E-RECEIPT se actualizan.
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase


class TestEReceiptPayload(IntegrationTestCase):
	"""Tests para el payload enviado a FacturAPI al crear E-Receipt."""

	def _db_get_with_product_key(self, doctype, name, field, *args, **kwargs):
		"""Helper: devuelve clave SAT válida para Items; None para todo lo demás."""
		if doctype == "Item" and field == "fm_producto_servicio_sat":
			return "01010101"
		return None

	def _make_mock_si_item(self, item_code, qty=1, rate=100, uom="H87 - Pieza"):
		item = MagicMock()
		item.item_code = item_code
		item.item_name = "Producto Test"
		item.qty = qty
		item.rate = rate
		item.uom = uom
		return item

	def _make_mock_si(self, customer="CUST-001", grand_total=116):
		si = MagicMock()
		si.name = "SINV-TEST-001"
		si.customer = customer
		si.customer_name = "Cliente Test"
		si.company = "Test Company"
		si.grand_total = grand_total
		si.contact_email = None
		return si

	def _make_mock_customer(self, tax_id=None):
		c = MagicMock()
		c.tax_id = tax_id
		c.get = lambda k, default=None: getattr(c, k, default)
		return c

	def _make_ereceipt(self, tax_rate=16.0, has_ieps=0, si_name="SINV-TEST-001"):
		er = MagicMock()
		er.name = "ER-TEST-001"
		er.company = "Test Company"
		er.sales_invoice = si_name
		er.tax_rate = tax_rate
		er.has_ieps = has_ieps
		er.expiry_date = None
		er.get = lambda k, default=None: getattr(er, k, default)
		return er

	@patch("facturacion_mexico.ereceipts.api.frappe.get_doc")
	@patch("facturacion_mexico.ereceipts.api.frappe.db.get_value")
	@patch("facturacion_mexico.ereceipts.api.frappe.db.set_value")
	@patch("facturacion_mexico.ereceipts.api.get_facturapi_client")
	def test_product_key_from_item_not_hardcoded(
		self, mock_client, mock_set_value, mock_db_get, mock_get_doc
	):
		"""product_key debe venir de Item.fm_producto_servicio_sat, no "01010101"."""
		from facturacion_mexico.ereceipts.api import _generar_facturapi_ereceipt

		ereceipt = self._make_ereceipt()
		si = self._make_mock_si()
		si.items = [self._make_mock_si_item("ITEM-001")]
		customer = self._make_mock_customer(tax_id="RFC123456789")

		def get_doc_side(doctype, name):
			if doctype == "Sales Invoice":
				return si
			if doctype == "Customer":
				return customer
			raise frappe.DoesNotExistError(doctype, name)

		mock_get_doc.side_effect = get_doc_side
		# Item.fm_producto_servicio_sat = "84111506" (servicios de software)
		mock_db_get.side_effect = lambda doctype, name, field, *args, **kwargs: (
			"84111506" if doctype == "Item" and field == "fm_producto_servicio_sat" else None
		)

		mock_api = MagicMock()
		mock_api.create_receipt.return_value = {
			"id": "fp-id-123",
			"key": "receipt-key",
			"self_invoice_url": "https://factura.space/test/receipt-key",
		}
		mock_client.return_value = mock_api

		_generar_facturapi_ereceipt(ereceipt)

		call_args = mock_api.create_receipt.call_args[0][0]
		item_product_key = call_args["items"][0]["product"]["product_key"]
		self.assertEqual(item_product_key, "84111506")
		self.assertNotEqual(item_product_key, "01010101")

	@patch("facturacion_mexico.ereceipts.api.frappe.log_error")
	@patch("facturacion_mexico.ereceipts.api.frappe.throw")
	@patch("facturacion_mexico.ereceipts.api.frappe.get_doc")
	@patch("facturacion_mexico.ereceipts.api.frappe.db.get_value")
	@patch("facturacion_mexico.ereceipts.api.frappe.db.set_value")
	@patch("facturacion_mexico.ereceipts.api.get_facturapi_client")
	def test_missing_product_key_raises_validation_error(
		self, mock_client, mock_set_value, mock_db_get, mock_get_doc, mock_throw, mock_log_error
	):
		"""Si Item no tiene fm_producto_servicio_sat, se lanza ValidationError — no se crea EReceipt."""
		from facturacion_mexico.ereceipts.api import _generar_facturapi_ereceipt

		ereceipt = self._make_ereceipt()
		si = self._make_mock_si()
		si.items = [self._make_mock_si_item("ITEM-NO-KEY")]
		customer = self._make_mock_customer()

		mock_get_doc.side_effect = lambda dt, name: si if dt == "Sales Invoice" else customer
		mock_db_get.return_value = None  # No SAT key en Item
		mock_throw.side_effect = Exception("ValidationError")  # simular frappe.throw
		mock_api = MagicMock()
		mock_client.return_value = mock_api

		result = _generar_facturapi_ereceipt(ereceipt)

		# FacturAPI NO debe ser llamado cuando falta la clave SAT
		mock_api.create_receipt.assert_not_called()
		# El resultado debe indicar fallo
		self.assertFalse(result.get("success", True))

	@patch("facturacion_mexico.ereceipts.api.frappe.get_doc")
	@patch("facturacion_mexico.ereceipts.api.frappe.db.get_value")
	@patch("facturacion_mexico.ereceipts.api.frappe.db.set_value")
	@patch("facturacion_mexico.ereceipts.api.get_facturapi_client")
	def test_rfc_from_tax_id_not_rfc_field(self, mock_client, mock_set_value, mock_db_get, mock_get_doc):
		"""RFC enviado a FacturAPI debe venir de Customer.tax_id."""
		from facturacion_mexico.ereceipts.api import _generar_facturapi_ereceipt

		ereceipt = self._make_ereceipt()
		si = self._make_mock_si()
		si.items = [self._make_mock_si_item("ITEM-001")]
		customer = self._make_mock_customer(tax_id="XEXX010101000")

		mock_get_doc.side_effect = lambda dt, name: si if dt == "Sales Invoice" else customer
		mock_db_get.side_effect = self._db_get_with_product_key
		mock_api = MagicMock()
		mock_api.create_receipt.return_value = {"id": "fp-id", "key": "k", "self_invoice_url": "u"}
		mock_client.return_value = mock_api

		_generar_facturapi_ereceipt(ereceipt)

		call_args = mock_api.create_receipt.call_args[0][0]
		self.assertEqual(call_args["customer"].get("tax_id"), "XEXX010101000")

	@patch("facturacion_mexico.ereceipts.api.frappe.get_doc")
	@patch("facturacion_mexico.ereceipts.api.frappe.db.get_value")
	@patch("facturacion_mexico.ereceipts.api.frappe.db.set_value")
	@patch("facturacion_mexico.ereceipts.api.get_facturapi_client")
	def test_no_fake_email_in_payload(self, mock_client, mock_set_value, mock_db_get, mock_get_doc):
		"""Si no hay email real, NO se envía 'noreply@example.com' a FacturAPI."""
		from facturacion_mexico.ereceipts.api import _generar_facturapi_ereceipt

		ereceipt = self._make_ereceipt()
		si = self._make_mock_si()
		si.items = [self._make_mock_si_item("ITEM-001")]
		si.contact_email = None
		customer = self._make_mock_customer()
		customer.customer_primary_contact = None

		mock_get_doc.side_effect = lambda dt, name: si if dt == "Sales Invoice" else customer
		mock_db_get.side_effect = self._db_get_with_product_key
		mock_api = MagicMock()
		mock_api.create_receipt.return_value = {"id": "fp-id", "key": "k", "self_invoice_url": "u"}
		mock_client.return_value = mock_api

		_generar_facturapi_ereceipt(ereceipt)

		call_args = mock_api.create_receipt.call_args[0][0]
		self.assertNotIn("email", call_args["customer"])
		email = call_args["customer"].get("email", "")
		self.assertNotIn("noreply", email)
		self.assertNotIn("example.com", email)

	@patch("facturacion_mexico.ereceipts.api.frappe.get_doc")
	@patch("facturacion_mexico.ereceipts.api.frappe.db.get_value")
	@patch("facturacion_mexico.ereceipts.api.frappe.db.set_value")
	@patch("facturacion_mexico.ereceipts.api.get_facturapi_client")
	def test_iva_taxes_in_items_when_tax_rate_known(
		self, mock_client, mock_set_value, mock_db_get, mock_get_doc
	):
		"""Si tax_rate está definido, cada item tiene taxes=[{IVA}] con la tasa correcta."""
		from facturacion_mexico.ereceipts.api import _generar_facturapi_ereceipt

		ereceipt = self._make_ereceipt(tax_rate=16.0)
		si = self._make_mock_si()
		si.items = [self._make_mock_si_item("ITEM-001")]
		customer = self._make_mock_customer()

		mock_get_doc.side_effect = lambda dt, name: si if dt == "Sales Invoice" else customer
		mock_db_get.side_effect = self._db_get_with_product_key
		mock_api = MagicMock()
		mock_api.create_receipt.return_value = {"id": "fp-id", "key": "k", "self_invoice_url": "u"}
		mock_client.return_value = mock_api

		_generar_facturapi_ereceipt(ereceipt)

		call_args = mock_api.create_receipt.call_args[0][0]
		item_taxes = call_args["items"][0]["product"].get("taxes", [])
		self.assertEqual(len(item_taxes), 1)
		self.assertEqual(item_taxes[0]["type"], "IVA")
		self.assertAlmostEqual(item_taxes[0]["rate"], 0.16)

	@patch("facturacion_mexico.ereceipts.api.frappe.get_doc")
	@patch("facturacion_mexico.ereceipts.api.frappe.db.get_value")
	@patch("facturacion_mexico.ereceipts.api.frappe.db.set_value")
	@patch("facturacion_mexico.ereceipts.api.get_facturapi_client")
	def test_no_taxes_when_tax_rate_none(self, mock_client, mock_set_value, mock_db_get, mock_get_doc):
		"""Si tax_rate es None (no determinable), no se envían taxes en los items."""
		from facturacion_mexico.ereceipts.api import _generar_facturapi_ereceipt

		ereceipt = self._make_ereceipt(tax_rate=None)
		si = self._make_mock_si()
		si.items = [self._make_mock_si_item("ITEM-001")]
		customer = self._make_mock_customer()

		mock_get_doc.side_effect = lambda dt, name: si if dt == "Sales Invoice" else customer
		mock_db_get.side_effect = self._db_get_with_product_key
		mock_api = MagicMock()
		mock_api.create_receipt.return_value = {"id": "fp-id", "key": "k", "self_invoice_url": "u"}
		mock_client.return_value = mock_api

		_generar_facturapi_ereceipt(ereceipt)

		call_args = mock_api.create_receipt.call_args[0][0]
		item_taxes = call_args["items"][0]["product"].get("taxes", [])
		self.assertEqual(item_taxes, [])

	@patch("facturacion_mexico.ereceipts.api.frappe.get_doc")
	@patch("facturacion_mexico.ereceipts.api.frappe.db.get_value")
	@patch("facturacion_mexico.ereceipts.api.frappe.db.set_value")
	@patch("facturacion_mexico.ereceipts.api.get_facturapi_client")
	def test_si_updated_on_success(self, mock_client, mock_set_value, mock_db_get, mock_get_doc):
		"""Al crear receipt exitosamente, SI.fm_ereceipt_mx y fm_fiscal_status se actualizan."""
		from facturacion_mexico.ereceipts.api import _generar_facturapi_ereceipt

		ereceipt = self._make_ereceipt()
		si = self._make_mock_si()
		si.items = [self._make_mock_si_item("ITEM-001")]
		customer = self._make_mock_customer()

		mock_get_doc.side_effect = lambda dt, name: si if dt == "Sales Invoice" else customer
		mock_db_get.side_effect = self._db_get_with_product_key
		mock_api = MagicMock()
		mock_api.create_receipt.return_value = {
			"id": "fp-id-123",
			"key": "receipt-key",
			"self_invoice_url": "https://factura.space/test/k",
		}
		mock_client.return_value = mock_api

		_generar_facturapi_ereceipt(ereceipt)

		mock_set_value.assert_called_once()
		call_args = mock_set_value.call_args
		self.assertEqual(call_args[0][0], "Sales Invoice")
		self.assertEqual(call_args[0][1], "SINV-TEST-001")
		update_dict = call_args[0][2]
		self.assertEqual(update_dict.get("fm_ereceipt_mx"), "ER-TEST-001")
		self.assertEqual(update_dict.get("fm_fiscal_status"), "E-RECEIPT")

	@patch("facturacion_mexico.ereceipts.api.frappe.log_error")
	@patch("facturacion_mexico.ereceipts.api.frappe.get_doc")
	@patch("facturacion_mexico.ereceipts.api.frappe.db.get_value")
	@patch("facturacion_mexico.ereceipts.api.frappe.db.set_value")
	@patch("facturacion_mexico.ereceipts.api.get_facturapi_client")
	def test_si_not_updated_on_failure(
		self, mock_client, mock_set_value, mock_db_get, mock_get_doc, mock_log_error
	):
		"""Si FacturAPI falla, NO se actualiza Sales Invoice."""
		from facturacion_mexico.ereceipts.api import _generar_facturapi_ereceipt

		ereceipt = self._make_ereceipt()
		si = self._make_mock_si()
		si.items = [self._make_mock_si_item("ITEM-001")]
		customer = self._make_mock_customer()

		mock_get_doc.side_effect = lambda dt, name: si if dt == "Sales Invoice" else customer
		mock_db_get.side_effect = self._db_get_with_product_key
		mock_api = MagicMock()
		mock_api.create_receipt.return_value = {}  # Respuesta inválida
		mock_client.return_value = mock_api

		_generar_facturapi_ereceipt(ereceipt)

		mock_set_value.assert_not_called()


class TestEReceiptSummaryAPI(IntegrationTestCase):
	"""Tests para get_ereceipt_summary — no copia UUID a Sales Invoice."""

	@patch("facturacion_mexico.api.ereceipt_summary.frappe.get_doc")
	@patch("facturacion_mexico.api.ereceipt_summary.frappe.db.get_value")
	def test_summary_open_status(self, mock_db_get, mock_get_doc):
		"""Estado open devuelve self_invoice_url y expires_at, sin UUID."""
		from facturacion_mexico.api.ereceipt_summary import get_ereceipt_summary

		er = MagicMock()
		er.as_dict.return_value = {
			"name": "ER-001",
			"status": "open",
			"self_invoice_url": "https://factura.space/test/key123",
			"expiry_date": "2026-07-01",
			"invoice_uuid": None,
			"invoice_folio": None,
			"invoiced_at": None,
			"factura_global_mx": None,
		}
		mock_get_doc.return_value = er

		result = get_ereceipt_summary("ER-001")

		self.assertEqual(result["status"], "open")
		self.assertEqual(result["self_invoice_url"], "https://factura.space/test/key123")
		self.assertIsNone(result["invoice_uuid"])

	@patch("facturacion_mexico.api.ereceipt_summary.frappe.get_doc")
	@patch("facturacion_mexico.api.ereceipt_summary.frappe.db.get_value")
	def test_summary_invoiced_to_customer(self, mock_db_get, mock_get_doc):
		"""Estado invoiced_to_customer devuelve UUID e invoice_folio."""
		from facturacion_mexico.api.ereceipt_summary import get_ereceipt_summary

		er = MagicMock()
		er.as_dict.return_value = {
			"name": "ER-002",
			"status": "invoiced_to_customer",
			"self_invoice_url": "https://factura.space/test/key",
			"expiry_date": "2026-07-01",
			"invoice_uuid": "550e8400-e29b-41d4-a716-446655440000",
			"invoice_folio": "A-0001",
			"invoiced_at": "2026-06-15 10:00:00",
			"factura_global_mx": None,
		}
		mock_get_doc.return_value = er

		result = get_ereceipt_summary("ER-002")

		self.assertEqual(result["status"], "invoiced_to_customer")
		self.assertEqual(result["invoice_uuid"], "550e8400-e29b-41d4-a716-446655440000")
		self.assertEqual(result["invoice_folio"], "A-0001")
		self.assertIsNone(result["factura_global_uuid"])

	@patch("facturacion_mexico.api.ereceipt_summary.frappe.get_doc")
	@patch("facturacion_mexico.api.ereceipt_summary.frappe.db.get_value")
	def test_summary_invoiced_globally_reads_fg_uuid(self, mock_db_get, mock_get_doc):
		"""Estado invoiced_globally lee UUID desde Factura Global MX, no desde SI."""
		from facturacion_mexico.api.ereceipt_summary import get_ereceipt_summary

		er = MagicMock()
		er.as_dict.return_value = {
			"name": "ER-003",
			"status": "invoiced_globally",
			"self_invoice_url": None,
			"expiry_date": None,
			"invoice_uuid": None,
			"invoice_folio": None,
			"invoiced_at": None,
			"factura_global_mx": "FG-2026-001",
		}
		mock_get_doc.return_value = er
		mock_db_get.return_value = "GLOBAL-UUID-001"

		result = get_ereceipt_summary("ER-003")

		self.assertEqual(result["factura_global_mx"], "FG-2026-001")
		self.assertEqual(result["factura_global_uuid"], "GLOBAL-UUID-001")
		# UUID individual es None — no es CFDI propio de la SI
		self.assertIsNone(result["invoice_uuid"])

	@patch("facturacion_mexico.api.ereceipt_summary.frappe.get_doc")
	@patch("facturacion_mexico.api.ereceipt_summary.frappe.db.get_value")
	def test_summary_does_not_write_to_si(self, mock_db_get, mock_get_doc):
		"""get_ereceipt_summary solo lee — nunca escribe en Sales Invoice."""
		from facturacion_mexico.api.ereceipt_summary import get_ereceipt_summary

		er = MagicMock()
		er.as_dict.return_value = {
			"name": "ER-004",
			"status": "invoiced_to_customer",
			"self_invoice_url": None,
			"expiry_date": None,
			"invoice_uuid": "some-uuid",
			"invoice_folio": "B-0002",
			"invoiced_at": None,
			"factura_global_mx": None,
		}
		mock_get_doc.return_value = er

		with patch("facturacion_mexico.api.ereceipt_summary.frappe.db.set_value") as mock_set:
			get_ereceipt_summary("ER-004")
			mock_set.assert_not_called()


class TestBuildItemTaxes(IntegrationTestCase):
	"""Tests para _build_item_taxes_for_receipt."""

	def test_iva_16(self):
		from facturacion_mexico.ereceipts.api import _build_item_taxes_for_receipt

		taxes = _build_item_taxes_for_receipt(16.0)
		self.assertEqual(len(taxes), 1)
		self.assertEqual(taxes[0]["type"], "IVA")
		self.assertAlmostEqual(taxes[0]["rate"], 0.16)
		self.assertEqual(taxes[0]["factor"], "Tasa")

	def test_iva_8(self):
		from facturacion_mexico.ereceipts.api import _build_item_taxes_for_receipt

		taxes = _build_item_taxes_for_receipt(8.0)
		self.assertAlmostEqual(taxes[0]["rate"], 0.08)

	def test_iva_0_explicit_exento(self):
		from facturacion_mexico.ereceipts.api import _build_item_taxes_for_receipt

		taxes = _build_item_taxes_for_receipt(0.0)
		self.assertEqual(len(taxes), 1)
		self.assertAlmostEqual(taxes[0]["rate"], 0.0)

	def test_none_returns_empty(self):
		from facturacion_mexico.ereceipts.api import _build_item_taxes_for_receipt

		taxes = _build_item_taxes_for_receipt(None)
		self.assertEqual(taxes, [])
