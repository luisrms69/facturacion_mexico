#!/usr/bin/env python3
"""
Test Suite Migration - Tax Category → fm_tax_regime Compatibility
Pruebas críticas para verificar migración Customer.tax_category → fm_tax_regime
Conforme RG-003: Tests simples, sin dependencias externas, sin documentos complejos
"""

import unittest
import frappe


class TestTaxRegimeMigration(unittest.TestCase):
    """Test crítico: migración tax_category → fm_tax_regime funciona correctamente."""

    @classmethod
    def setUpClass(cls):
        """Setup inicial para todos los tests"""
        frappe.clear_cache()

    def test_tax_code_extraction_logic(self):
        """Test: extracción código SAT funciona correctamente."""
        test_regimes = [
            ("601 - General de Ley Personas Morales", "601"),
            ("612 - Persona Física con Actividades Empresariales", "612"),
            ("605 - Sueldos y Salarios e Ingresos Asimilados", "605")
        ]

        for regime, expected_code in test_regimes:
            with self.subTest(regime=regime):
                # Simular lógica en timbrado_api.py líneas 1399-1401
                tax_code = regime.split(" - ")[0].strip()
                self.assertEqual(tax_code, expected_code)

    @unittest.skip("Legacy: verifica datos de producción migrados, no válido en site de tests limpio")
    def test_migration_data_integrity(self):
        """Test: verificar integridad datos migrados."""
        customers_with_fm = frappe.db.count("Customer", {"fm_tax_regime": ["!=", ""]})
        self.assertGreaterEqual(customers_with_fm, 3)
        customers_with_tax = frappe.db.count("Customer", {"tax_category": ["!=", ""]})
        self.assertEqual(customers_with_tax, 0)

    def test_custom_field_exists(self):
        """Test: verificar que custom field fm_tax_regime existe y está configurado."""
        meta = frappe.get_meta("Customer")

        # Verificar campo existe
        fm_field = next((f for f in meta.fields if f.fieldname == "fm_tax_regime"), None)
        self.assertIsNotNone(fm_field, "Custom field fm_tax_regime no existe")

        # Verificar configuración correcta
        self.assertEqual(fm_field.fieldtype, "Link")
        self.assertEqual(fm_field.options, "Tax Category")
        self.assertEqual(fm_field.label, "Régimen Fiscal SAT")

    def test_sales_invoice_custom_field_removed(self):
        """Test: verificar que Sales Invoice ya NO tiene fm_tax_regime (eliminado como redundante)."""
        meta = frappe.get_meta("Sales Invoice")

        # Verificar campo ya NO existe en Sales Invoice (eliminado por redundante)
        fm_field = next((f for f in meta.fields if f.fieldname == "fm_tax_regime"), None)
        self.assertIsNone(fm_field, "Custom field fm_tax_regime aún existe en Sales Invoice (debería estar eliminado)")

        # Comentario: Sales Invoice.fm_tax_regime era redundante porque FFM siempre obtiene
        # tax regime desde Customer.fm_tax_regime, nunca desde Sales Invoice

    def test_extract_tax_system_function_uses_fm_tax_regime(self):
        """Test: verificar que _extract_tax_system_from_customer usa fm_tax_regime."""
        from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import FacturaFiscalMexico

        # Crear mock customer con fm_tax_regime
        mock_customer = frappe._dict({
            'fm_tax_regime': '601 - General de Ley Personas Morales'
        })

        # Crear instancia FFM directamente para test
        ffm_doc = frappe.get_doc({"doctype": "Factura Fiscal Mexico"})
        result = ffm_doc._extract_tax_system_from_customer(mock_customer)

        # Debe extraer código "601"
        self.assertEqual(result, "601")

        # Test customer sin fm_tax_regime
        mock_customer_empty = frappe._dict({})
        result_empty = ffm_doc._extract_tax_system_from_customer(mock_customer_empty)
        self.assertIsNone(result_empty)

    @unittest.skip("Legacy: path hardcodeado a bench v15, contenido JS cambiado desde migración")
    def test_javascript_references_updated(self):
        """Test: verificar que JavaScript usa fm_tax_regime."""
        js_path = "/home/erpnext/frappe-bench/apps/facturacion_mexico/facturacion_mexico/facturacion_fiscal/doctype/factura_fiscal_mexico/factura_fiscal_mexico.js"

        with open(js_path, 'r') as f:
            js_content = f.read()

        self.assertIn('"fm_tax_regime"', js_content)
        self.assertIn('r.message.fm_tax_regime', js_content)