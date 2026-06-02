"""
Tests para AddendaGenerator._load_product_mappings — nueva arquitectura.

Lee desde Item Customer Detail (tabItem Customer Detail) via frappe.db.sql.
La descripción y UOM vienen del invoice item, no de la BD.

Cubre:
  1. product_mapping está presente en el contexto
  2. item con mapping expone customer_item_code (ref_code), customer_item_description
     (del invoice item) y customer_uom (del invoice item)
  3. sin customer → product_mapping = {}
  4. sin items → product_mapping = {}
  5. sin mappings en BD → product_mapping = {}
  6. error de BD → product_mapping = {}
  7. template puede usar product_mapping vacío sin fallar
  8. solo los items mapeados aparecen en product_mapping
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


def _make_generator(addenda_type="TEST_TYPE"):
	"""Construye AddendaGenerator mockeando la carga del Addenda Type."""
	mock_type_doc = MagicMock()
	mock_type_doc.is_active = 1
	mock_type_doc.xml_template = "<test/>"
	mock_type_doc.field_definitions = []

	with patch("frappe.get_cached_doc", return_value=mock_type_doc):
		from facturacion_mexico.addendas.generic_addenda_generator import AddendaGenerator

		return AddendaGenerator(addenda_type)


class TestAddendaGeneratorProductMapping(FrappeTestCase):
	def setUp(self):
		self.gen = _make_generator()

	# ── product_mapping presente en contexto ─────────────────────────────────

	def test_product_mapping_key_present_in_context(self):
		invoice_data = {"customer": "C-001", "items": []}
		with patch("frappe.db.sql", return_value=[]):
			ctx = self.gen._prepare_template_context(invoice_data, {})
		self.assertIn("product_mapping", ctx)

	# ── item con mapping activo ───────────────────────────────────────────────

	def test_mapping_fields_accessible_by_item_code(self):
		invoice_data = {
			"customer": "C-001",
			"items": [{"item_code": "ITEM-001", "item_name": "Producto Uno", "uom": "H87 - Pieza"}],
		}
		mock_row = frappe._dict(
			{
				"item_code": "ITEM-001",
				"customer_item_code": "LC-9999",
				"fm_customer_uom": "EA",
				"fm_customer_description": "PRODUCTO UNO CLIENTE",
			}
		)
		with patch("frappe.db.sql", return_value=[mock_row]):
			ctx = self.gen._prepare_template_context(invoice_data, {})

		mapping = ctx["product_mapping"]
		self.assertIn("ITEM-001", mapping)
		self.assertEqual(mapping["ITEM-001"]["customer_item_code"], "LC-9999")
		self.assertEqual(mapping["ITEM-001"]["customer_item_description"], "PRODUCTO UNO CLIENTE")
		self.assertEqual(mapping["ITEM-001"]["customer_uom"], "EA")

	def test_fallback_uom_uses_sat_code(self):
		"""Sin fm_customer_uom usa el código SAT extraído del UOM de ERPNext."""
		invoice_data = {
			"customer": "C-001",
			"items": [{"item_code": "ITEM-001", "item_name": "Acelga", "uom": "H87 - Pieza"}],
		}
		mock_row = frappe._dict(
			{
				"item_code": "ITEM-001",
				"customer_item_code": "45865",
				"fm_customer_uom": None,
				"fm_customer_description": None,
			}
		)
		with patch("frappe.db.sql", return_value=[mock_row]):
			ctx = self.gen._prepare_template_context(invoice_data, {})

		mapping = ctx["product_mapping"]
		self.assertEqual(mapping["ITEM-001"]["customer_uom"], "H87")
		self.assertEqual(mapping["ITEM-001"]["customer_item_description"], "Acelga")

	# ── fallbacks seguros ────────────────────────────────────────────────────

	def test_empty_mapping_when_no_customer(self):
		invoice_data = {"items": [{"item_code": "ITEM-001"}]}
		ctx = self.gen._prepare_template_context(invoice_data, {})
		self.assertEqual(ctx["product_mapping"], {})

	def test_empty_mapping_when_no_items(self):
		invoice_data = {"customer": "C-001", "items": []}
		with patch("frappe.db.sql", return_value=[]):
			ctx = self.gen._prepare_template_context(invoice_data, {})
		self.assertEqual(ctx["product_mapping"], {})

	def test_empty_mapping_when_no_mappings_in_db(self):
		invoice_data = {
			"customer": "C-001",
			"items": [{"item_code": "ITEM-SIN-MAPPING", "item_name": "Sin Mapping", "uom": "EA"}],
		}
		with patch("frappe.db.sql", return_value=[]):
			ctx = self.gen._prepare_template_context(invoice_data, {})
		self.assertEqual(ctx["product_mapping"], {})

	def test_empty_mapping_when_db_raises(self):
		invoice_data = {
			"customer": "C-001",
			"items": [{"item_code": "ITEM-001", "item_name": "Item", "uom": "EA"}],
		}
		with patch("frappe.db.sql", side_effect=Exception("DB error")):
			ctx = self.gen._prepare_template_context(invoice_data, {})
		self.assertEqual(ctx["product_mapping"], {})

	# ── template puede usar product_mapping vacío sin fallar ─────────────────

	def test_render_does_not_fail_with_empty_product_mapping(self):
		"""Un template que itera product_mapping no debe romper si está vacío."""
		mock_type_doc = MagicMock()
		mock_type_doc.is_active = 1
		mock_type_doc.xml_template = (
			"<items>"
			"{% for code, m in product_mapping.items() %}"
			"<item>{{ m.customer_item_code }}</item>"
			"{% endfor %}"
			"</items>"
		)
		mock_type_doc.field_definitions = []
		mock_type_doc.xsd_schema = None

		with patch("frappe.get_cached_doc", return_value=mock_type_doc):
			from facturacion_mexico.addendas.generic_addenda_generator import AddendaGenerator

			gen = AddendaGenerator("TEST_TYPE")

		invoice_data = {"customer": "C-001", "items": [], "company": None}
		with patch("frappe.db.sql", return_value=[]):
			result = gen.generate(invoice_data, {})

		self.assertTrue(result["success"])
		self.assertIn("<items>", result["xml_content"])

	# ── múltiples items, solo los mapeados aparecen ───────────────────────────

	def test_only_mapped_items_appear_in_product_mapping(self):
		invoice_data = {
			"customer": "C-001",
			"items": [
				{"item_code": "ITEM-A", "item_name": "Item A", "uom": "PZA"},
				{"item_code": "ITEM-B", "item_name": "Item B", "uom": "KGM"},
				{"item_code": "ITEM-C", "item_name": "Item C", "uom": "EA"},
			],
		}
		mock_rows = [frappe._dict({"item_code": "ITEM-A", "customer_item_code": "CA-1"})]
		with patch("frappe.db.sql", return_value=mock_rows):
			ctx = self.gen._prepare_template_context(invoice_data, {})

		self.assertIn("ITEM-A", ctx["product_mapping"])
		self.assertNotIn("ITEM-B", ctx["product_mapping"])
		self.assertNotIn("ITEM-C", ctx["product_mapping"])
