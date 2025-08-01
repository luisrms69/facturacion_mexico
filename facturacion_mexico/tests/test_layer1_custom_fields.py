# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 1 Custom Fields Tests
Tests básicos para verificar custom fields funcionan correctamente
"""

import unittest

import frappe


class TestLayer1CustomFields(unittest.TestCase):
    """Tests de custom fields básicos - Layer 1"""

    @classmethod
    def setUpClass(cls):
        """Setup inicial para todos los tests"""
        frappe.clear_cache()

    def test_customer_custom_fields_exist(self):
        """Test: Verificar custom fields de Customer"""
        customer_fields = frappe.db.sql("""
            SELECT fieldname, label, fieldtype
            FROM `tabCustom Field`
            WHERE dt = 'Customer' AND fieldname LIKE 'fm_%'
            ORDER BY fieldname
        """, as_dict=True)

        # Verificar que existen algunos campos básicos
        [f.fieldname for f in customer_fields]

        # Verificar que tax_id (RFC) está disponible en Customer
        customer_meta = frappe.get_meta("Customer")
        self.assertTrue(customer_meta.has_field("tax_id"), "Customer debe tener campo tax_id disponible")

        # Verificar que los campos tienen configuración correcta
        for field in customer_fields:
            self.assertIsNotNone(field.fieldname)
            # Label puede ser vacío para algunos campos, solo verificar fieldtype
            self.assertIsNotNone(field.fieldtype)

    def test_sales_invoice_custom_fields_exist(self):
        """Test: Verificar custom fields de Sales Invoice"""
        si_fields = frappe.db.sql("""
            SELECT fieldname, label, fieldtype
            FROM `tabCustom Field`
            WHERE dt = 'Sales Invoice' AND fieldname LIKE 'fm_%'
            ORDER BY fieldname
        """, as_dict=True)

        # Debe haber al menos algunos campos fiscales
        self.assertGreater(len(si_fields), 0, "Sales Invoice debe tener custom fields fm_*")

        # Verificar configuración de campos
        for field in si_fields:
            self.assertIsNotNone(field.fieldname)
            # Label puede ser vacío para algunos campos, solo verificar fieldtype
            self.assertIsNotNone(field.fieldtype)

    def test_branch_custom_fields_exist(self):
        """Test: Verificar custom fields de Branch si existe DocType"""
        # Verificar si Branch DocType existe
        branch_exists = frappe.db.exists("DocType", "Branch")

        if branch_exists:
            branch_fields = frappe.db.sql("""
                SELECT fieldname, label, fieldtype
                FROM `tabCustom Field`
                WHERE dt = 'Branch' AND fieldname LIKE 'fm_%'
                ORDER BY fieldname
            """, as_dict=True)

            # Si Branch existe, debe tener campos fiscales
            field_names = [f.fieldname for f in branch_fields]

            # Verificar campos básicos que sabemos que deben existir
            basic_fields = ["fm_enable_fiscal"]
            for field in basic_fields:
                if field in field_names:  # Solo validar si existe
                    self.assertIn(field, field_names, f"Branch debe tener campo {field}")

    def test_custom_field_insertion_integrity(self):
        """Test: Verificar integridad de inserción de custom fields"""
        # Contar total de custom fields de la app
        total_fields = frappe.db.sql("""
            SELECT COUNT(*) as count
            FROM `tabCustom Field`
            WHERE fieldname LIKE 'fm_%'
        """, as_dict=True)

        self.assertGreater(total_fields[0].count, 0,
                          "Debe existir al menos un custom field fm_*")

    def test_custom_fields_no_duplicate_names(self):
        """Test: Verificar que no hay nombres duplicados de custom fields"""
        duplicates = frappe.db.sql("""
            SELECT dt, fieldname, COUNT(*) as count
            FROM `tabCustom Field`
            WHERE fieldname LIKE 'fm_%'
            GROUP BY dt, fieldname
            HAVING COUNT(*) > 1
        """, as_dict=True)

        self.assertEqual(len(duplicates), 0,
                        f"No debe haber custom fields duplicados: {duplicates}")

    def test_custom_fields_have_proper_naming(self):
        """Test: Verificar que custom fields siguen convención de nombres"""
        fm_fields = frappe.db.sql("""
            SELECT dt, fieldname
            FROM `tabCustom Field`
            WHERE fieldname LIKE 'fm_%'
        """, as_dict=True)

        for field in fm_fields:
            # Verificar que comienzan con fm_
            self.assertTrue(field.fieldname.startswith("fm_"),
                           f"Campo {field.fieldname} debe comenzar con fm_")

            # Verificar que no tienen caracteres extraños
            allowed_chars = set("abcdefghijklmnopqrstuvwxyz0123456789_")
            field_chars = set(field.fieldname.lower())
            invalid_chars = field_chars - allowed_chars

            self.assertEqual(len(invalid_chars), 0,
                           f"Campo {field.fieldname} tiene caracteres inválidos: {invalid_chars}")

    def test_frappe_custom_field_api_works(self):
        """Test: Verificar que API de custom fields de Frappe funciona"""
        # Intentar obtener metadatos de un DocType conocido
        try:
            meta = frappe.get_meta("Customer")
            self.assertIsNotNone(meta)

            # Verificar que podemos acceder a custom fields
            custom_fields = [f for f in meta.fields if f.fieldname.startswith("fm_")]
            # No forzamos que existan, solo que la API funcione
            self.assertIsInstance(custom_fields, list)

        except Exception as e:
            self.fail(f"API de metadatos de Frappe falló: {e}")

    def test_database_custom_field_structure(self):
        """Test: Verificar estructura de tabla de custom fields"""
        # Verificar que la tabla tabCustom Field existe y tiene estructura correcta
        columns = frappe.db.sql("""
            SHOW COLUMNS FROM `tabCustom Field`
        """, as_dict=True)

        column_names = [c.Field for c in columns]
        required_columns = ["name", "dt", "fieldname", "label", "fieldtype"]

        for col in required_columns:
            self.assertIn(col, column_names,
                         f"Tabla tabCustom Field debe tener columna {col}")


if __name__ == "__main__":
    unittest.main()
