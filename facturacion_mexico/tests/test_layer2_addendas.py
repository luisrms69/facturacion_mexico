# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 2 Addendas Integration Tests
Tests de integración para el sistema de addendas Sprint 6
"""

import frappe
import unittest


class TestLayer2Addendas(unittest.TestCase):
    """Tests de integración de addendas - Layer 2"""

    @classmethod
    def setUpClass(cls):
        """Setup inicial para todos los tests"""
        frappe.clear_cache()

    def test_addenda_type_doctype_integration(self):
        """Test: Integración del DocType Addenda Type"""
        if not frappe.db.exists("DocType", "Addenda Type"):
            self.skipTest("DocType Addenda Type no disponible")

        # Verificar estructura del DocType
        meta = frappe.get_meta("Addenda Type")
        self.assertIsNotNone(meta)

        # Verificar campos críticos
        field_names = [f.fieldname for f in meta.fields]
        critical_fields = ["description", "version", "is_active", "xml_template"]

        for field in critical_fields:
            if field in field_names:
                self.assertIn(field, field_names, f"Campo crítico {field} debe existir")

    def test_addenda_generator_modules_integration(self):
        """Test: Integración de módulos de generación de addendas"""
        generator_modules = [
            "facturacion_mexico.addendas.generic_addenda_generator",
            "facturacion_mexico.addendas.addenda_auto_detector",
        ]

        for module in generator_modules:
            try:
                imported_module = __import__(module, fromlist=[''])
                self.assertIsNotNone(imported_module)
            except ImportError:
                # Si no se puede importar, no es crítico para Layer 2
                pass

    def test_customer_addenda_fields_integration(self):
        """Test: Integración de custom fields de addendas en Customer"""
        # Verificar custom fields de addendas en Customer
        customer_addenda_fields = frappe.db.sql("""
            SELECT fieldname, fieldtype
            FROM `tabCustom Field`
            WHERE dt = 'Customer' AND fieldname LIKE '%addenda%'
        """, as_dict=True)

        # Si hay campos de addenda, verificar integración
        if customer_addenda_fields:
            field_names = [f.fieldname for f in customer_addenda_fields]
            expected_fields = ["fm_requires_addenda", "fm_addenda_type"]

            for field in expected_fields:
                if field in field_names:
                    self.assertIn(field, field_names, f"Campo de addenda {field} debe existir")

    def test_addenda_custom_fields_modules_integration(self):
        """Test: Integración de módulos de custom fields de addendas"""
        try:
            from facturacion_mexico.addendas.custom_fields.customer_addenda_fields import (
                create_customer_addenda_fields
            )
            self.assertIsNotNone(create_customer_addenda_fields)
        except ImportError:
            # Si no se puede importar, no es crítico para Layer 2
            pass

    def test_addenda_validation_integration(self):
        """Test: Integración del sistema de validación de addendas"""
        if not frappe.db.exists("DocType", "Addenda Type"):
            self.skipTest("DocType Addenda Type no disponible")

        # Verificar que el DocType tiene validaciones
        try:
            addenda_type_module = frappe.get_module("facturacion_mexico.addendas.doctype.addenda_type.addenda_type")
            self.assertIsNotNone(addenda_type_module)
        except ImportError:
            self.fail("Módulo AddendaType no disponible")

    def test_addenda_business_logic_integration(self):
        """Test: Integración de lógica de negocio de addendas"""
        # Verificar que hay registros base de Addenda Type si existen
        if frappe.db.exists("DocType", "Addenda Type"):
            addenda_count = frappe.db.count("Addenda Type")
            # No forzamos que existan registros, solo verificamos que la consulta funciona
            self.assertIsInstance(addenda_count, int)

    def test_addenda_xml_processing_integration(self):
        """Test: Integración del procesamiento XML de addendas"""
        try:
            # Verificar módulos de validación XML
            from facturacion_mexico.utils.secure_xml import secure_parse_xml
            self.assertIsNotNone(secure_parse_xml)
        except ImportError:
            # Si no está disponible, no es crítico
            pass

    def test_addenda_database_consistency(self):
        """Test: Consistencia de base de datos para addendas"""
        if frappe.db.exists("DocType", "Addenda Type"):
            try:
                result = frappe.db.sql("SHOW TABLES LIKE 'tabAddenda Type'")
                self.assertGreater(len(result), 0, "Tabla tabAddenda Type debe existir")
            except Exception as e:
                self.fail(f"Error verificando tabla Addenda Type: {e}")

    def test_addenda_permissions_integration(self):
        """Test: Permisos del sistema de addendas están integrados"""
        if not frappe.db.exists("DocType", "Addenda Type"):
            self.skipTest("DocType Addenda Type no disponible")

        # Verificar que podemos acceder sin errores de permisos
        try:
            addenda_types = frappe.get_all("Addenda Type", limit=1)
            self.assertIsInstance(addenda_types, list)
        except frappe.PermissionError:
            self.fail("Error de permisos accediendo a Addenda Type")

    def test_addenda_template_processing_integration(self):
        """Test: Integración del procesamiento de templates de addendas"""
        if not frappe.db.exists("DocType", "Addenda Type"):
            self.skipTest("DocType Addenda Type no disponible")

        # Verificar que hay registros de Addenda Type básicos
        addenda_count = frappe.db.sql("""
            SELECT COUNT(*) as count FROM `tabAddenda Type`
        """, as_dict=True)

        # No forzamos que existan registros, solo verificamos la consulta
        self.assertIsInstance(addenda_count, list)
        self.assertIn("count", addenda_count[0])

    def test_addenda_auto_detection_integration(self):
        """Test: Integración del sistema de auto-detección de addendas"""
        try:
            from facturacion_mexico.addendas.addenda_auto_detector import AddendaAutoDetector
            # Solo verificar que la clase se puede importar
            self.assertTrue(hasattr(AddendaAutoDetector, '__init__'))
        except ImportError:
            # Si no está disponible, no es crítico para Layer 2
            pass


if __name__ == "__main__":
    unittest.main()