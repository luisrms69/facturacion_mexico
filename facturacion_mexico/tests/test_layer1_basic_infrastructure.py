# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 1 Basic Infrastructure Tests
Tests básicos para verificar infraestructura core de facturación México
"""

import frappe
import unittest
from frappe.test_runner import make_test_records


class TestLayer1BasicInfrastructure(unittest.TestCase):
    """Tests de infraestructura básica - Layer 1"""

    @classmethod
    def setUpClass(cls):
        """Setup inicial para todos los tests"""
        frappe.clear_cache()

    def test_facturacion_mexico_app_installed(self):
        """Test: Verificar que la app facturacion_mexico está instalada"""
        installed_apps = frappe.get_installed_apps()
        self.assertIn("facturacion_mexico", installed_apps)

    def test_basic_doctypes_exist(self):
        """Test: Verificar que DocTypes básicos existen"""
        basic_doctypes = [
            "Facturacion Mexico Settings",
            "Uso CFDI SAT",
            "Regimen Fiscal SAT",
        ]

        for doctype in basic_doctypes:
            exists = frappe.db.exists("DocType", doctype)
            self.assertTrue(exists, f"DocType {doctype} debe existir")

    def test_facturacion_mexico_settings_created(self):
        """Test: Verificar que configuración básica existe"""
        settings = frappe.get_single("Facturacion Mexico Settings")
        self.assertIsNotNone(settings)
        self.assertIsNotNone(settings.name)

    def test_basic_sat_catalogs_exist(self):
        """Test: Verificar que catálogos SAT básicos existen"""
        # Verificar algunos códigos básicos de Uso CFDI
        basic_uso_cfdi = ["G01", "G03", "P01"]
        for codigo in basic_uso_cfdi:
            exists = frappe.db.exists("Uso CFDI SAT", codigo)
            self.assertTrue(exists, f"Uso CFDI SAT {codigo} debe existir")

        # Verificar algunos códigos básicos de Régimen Fiscal
        basic_regimen = ["601", "603"]
        for codigo in basic_regimen:
            exists = frappe.db.exists("Regimen Fiscal SAT", codigo)
            self.assertTrue(exists, f"Regimen Fiscal SAT {codigo} debe existir")

    def test_custom_fields_basic_existence(self):
        """Test: Verificar que algunos custom fields básicos existen"""
        # Verificar que Customer tiene campos fiscales básicos
        customer_fields = frappe.db.sql("""
            SELECT fieldname FROM `tabCustom Field`
            WHERE dt = 'Customer' AND fieldname LIKE 'fm_%'
        """, as_dict=True)

        customer_field_names = [f.fieldname for f in customer_fields]
        expected_customer_fields = ["fm_rfc"]

        for field in expected_customer_fields:
            self.assertIn(field, customer_field_names,
                         f"Customer debe tener custom field {field}")

    def test_company_setup_works(self):
        """Test: Verificar que setup básico de Company funciona"""
        # Buscar si existe alguna company
        companies = frappe.get_all("Company", limit=1)
        if companies:
            company = frappe.get_doc("Company", companies[0].name)
            self.assertIsNotNone(company.name)
            self.assertTrue(len(company.name) > 0)

    def test_warehouse_types_exist(self):
        """Test: Verificar que tipos de warehouse básicos existen"""
        basic_warehouse_types = ["Stores", "Work In Progress", "Finished Goods", "Transit"]

        for wh_type in basic_warehouse_types:
            exists = frappe.db.exists("Warehouse Type", wh_type)
            self.assertTrue(exists, f"Warehouse Type {wh_type} debe existir")

    def test_basic_uoms_exist(self):
        """Test: Verificar que UOMs básicos existen"""
        basic_uoms = ["Nos", "Unit", "Piece"]

        for uom in basic_uoms:
            exists = frappe.db.exists("UOM", uom)
            self.assertTrue(exists, f"UOM {uom} debe existir")

    def test_database_connection_works(self):
        """Test: Verificar que conexión a base de datos funciona"""
        result = frappe.db.sql("SELECT 1 as test_value", as_dict=True)
        self.assertEqual(result[0].test_value, 1)

    def test_frappe_context_available(self):
        """Test: Verificar que contexto de Frappe está disponible"""
        self.assertIsNotNone(frappe.session.user)
        self.assertIsNotNone(frappe.local)
        self.assertTrue(frappe.flags.in_test)


def make_test_records_basic():
    """Crear registros básicos de test si no existen"""
    # Este método se puede usar para setup adicional si es necesario
    pass


if __name__ == "__main__":
    unittest.main()