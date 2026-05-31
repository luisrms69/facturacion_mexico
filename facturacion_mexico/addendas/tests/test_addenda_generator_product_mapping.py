"""
Tests para AddendaGenerator._prepare_template_context — product_mapping.

Cubre:
  1. product_mapping está presente en el contexto
  2. item con mapping activo expone customer_item_code, customer_item_description,
     customer_uom y additional_data
  3. sin customer → product_mapping = {}
  4. sin items → product_mapping = {}
  5. sin mappings en BD → product_mapping = {}
  6. template puede usar product_mapping sin fallar cuando está vacío
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
        with patch("frappe.get_all", return_value=[]):
            ctx = self.gen._prepare_template_context(invoice_data, {})
        self.assertIn("product_mapping", ctx)

    # ── item con mapping activo ───────────────────────────────────────────────

    def test_mapping_fields_accessible_by_item_code(self):
        invoice_data = {
            "customer": "C-001",
            "items": [{"item_code": "ITEM-001"}],
        }
        mock_row = {
            "item_code": "ITEM-001",
            "customer_item_code": "LC-9999",
            "customer_item_description": "Producto La Comer",
            "customer_uom": "PZA",
            "additional_data": '{"ean": "7501234567890"}',
        }
        with patch("frappe.get_all", return_value=[mock_row]):
            ctx = self.gen._prepare_template_context(invoice_data, {})

        mapping = ctx["product_mapping"]
        self.assertIn("ITEM-001", mapping)
        self.assertEqual(mapping["ITEM-001"]["customer_item_code"], "LC-9999")
        self.assertEqual(mapping["ITEM-001"]["customer_item_description"], "Producto La Comer")
        self.assertEqual(mapping["ITEM-001"]["customer_uom"], "PZA")
        self.assertEqual(mapping["ITEM-001"]["additional_data"], '{"ean": "7501234567890"}')

    # ── fallbacks seguros ────────────────────────────────────────────────────

    def test_empty_mapping_when_no_customer(self):
        invoice_data = {"items": [{"item_code": "ITEM-001"}]}
        ctx = self.gen._prepare_template_context(invoice_data, {})
        self.assertEqual(ctx["product_mapping"], {})

    def test_empty_mapping_when_no_items(self):
        invoice_data = {"customer": "C-001", "items": []}
        with patch("frappe.get_all", return_value=[]):
            ctx = self.gen._prepare_template_context(invoice_data, {})
        self.assertEqual(ctx["product_mapping"], {})

    def test_empty_mapping_when_no_mappings_in_db(self):
        invoice_data = {
            "customer": "C-001",
            "items": [{"item_code": "ITEM-SIN-MAPPING"}],
        }
        with patch("frappe.get_all", return_value=[]):
            ctx = self.gen._prepare_template_context(invoice_data, {})
        self.assertEqual(ctx["product_mapping"], {})

    def test_empty_mapping_when_frappe_get_all_raises(self):
        invoice_data = {
            "customer": "C-001",
            "items": [{"item_code": "ITEM-001"}],
        }
        with patch("frappe.get_all", side_effect=Exception("DB error")):
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
        with patch("frappe.get_all", return_value=[]):
            result = gen.generate(invoice_data, {})

        self.assertTrue(result["success"])
        self.assertIn("<items>", result["xml_content"])

    # ── múltiples items, solo los mapeados aparecen ───────────────────────────

    def test_only_mapped_items_appear_in_product_mapping(self):
        invoice_data = {
            "customer": "C-001",
            "items": [
                {"item_code": "ITEM-A"},
                {"item_code": "ITEM-B"},
                {"item_code": "ITEM-C"},
            ],
        }
        mock_rows = [
            {
                "item_code": "ITEM-A",
                "customer_item_code": "CA-1",
                "customer_item_description": "Desc A",
                "customer_uom": "PZA",
                "additional_data": None,
            },
        ]
        with patch("frappe.get_all", return_value=mock_rows):
            ctx = self.gen._prepare_template_context(invoice_data, {})

        self.assertIn("ITEM-A", ctx["product_mapping"])
        self.assertNotIn("ITEM-B", ctx["product_mapping"])
        self.assertNotIn("ITEM-C", ctx["product_mapping"])
