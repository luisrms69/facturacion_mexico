# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 1 Installation Tests
Tests básicos para verificar que la instalación de la app funciona correctamente
"""

import unittest

import frappe


class TestLayer1Installation(unittest.TestCase):
    """Tests de instalación básica - Layer 1"""

    @classmethod
    def setUpClass(cls):
        """Setup inicial para todos los tests"""
        frappe.clear_cache()

    def test_app_is_installed(self):
        """Test: La app facturacion_mexico está instalada"""
        installed_apps = frappe.get_installed_apps()
        self.assertIn("facturacion_mexico", installed_apps)

    def test_hooks_are_loaded(self):
        """Test: Hooks de la app están cargados"""
        # Verificar que podemos importar hooks
        try:
            from facturacion_mexico import hooks
            self.assertIsNotNone(hooks)
        except ImportError:
            self.fail("No se pueden importar hooks de facturacion_mexico")

    def test_install_functions_available(self):
        """Test: Funciones de instalación están disponibles"""
        try:
            from facturacion_mexico.install import after_install, before_tests
            self.assertIsNotNone(after_install)
            self.assertIsNotNone(before_tests)
        except ImportError as e:
            self.fail(f"No se pueden importar funciones de install: {e}")

    def test_basic_modules_importable(self):
        """Test: Módulos básicos se pueden importar"""
        basic_modules = [
            "facturacion_mexico.utils",
            "facturacion_mexico.install",
        ]

        for module in basic_modules:
            try:
                __import__(module)
            except ImportError as e:
                self.fail(f"No se puede importar módulo {module}: {e}")

    def test_database_tables_created(self):
        """Test: Tablas de base de datos fueron creadas"""
        # Verificar algunas tablas básicas que deben existir
        basic_tables = [
            "tabUso CFDI SAT",
            "tabRegimen Fiscal SAT",
        ]

        for table in basic_tables:
            # Verificar que la tabla existe
            try:
                result = frappe.db.sql(f"SHOW TABLES LIKE '{table}'")
                self.assertGreater(len(result), 0, f"Tabla {table} debe existir")
            except Exception as e:
                self.fail(f"Error verificando tabla {table}: {e}")

        # Verificar Single DocType especialmente
        try:
            # Para Single DocTypes, verificar de forma diferente
            singles_table = frappe.db.sql("SHOW TABLES LIKE 'tabSingles'")
            self.assertGreater(len(singles_table), 0, "Tabla tabSingles debe existir")
        except Exception as e:
            self.fail(f"Error verificando tabla Singles: {e}")

    def test_custom_field_tables_accessible(self):
        """Test: Tablas de custom fields son accesibles"""
        try:
            # Verificar que podemos consultar custom fields
            custom_fields = frappe.db.sql("""
                SELECT COUNT(*) as count
                FROM `tabCustom Field`
                WHERE fieldname LIKE 'fm_%'
            """, as_dict=True)

            # Solo verificamos que la consulta funciona
            self.assertIsInstance(custom_fields, list)
            self.assertIn("count", custom_fields[0])

        except Exception as e:
            self.fail(f"Error accediendo a tablas de custom fields: {e}")

    def test_single_doctype_records_created(self):
        """Test: Registros de DocTypes Single fueron creados"""
        # Verificar Facturacion Mexico Settings
        try:
            settings_exists = frappe.db.exists("Facturacion Mexico Settings",
                                              "Facturacion Mexico Settings")
            self.assertTrue(settings_exists,
                           "Registro de Facturacion Mexico Settings debe existir")
        except Exception as e:
            self.fail(f"Error verificando Single DocTypes: {e}")

    def test_catalog_data_populated(self):
        """Test: Datos de catálogos fueron poblados"""
        # Verificar que hay datos básicos en catálogos SAT
        uso_cfdi_count = frappe.db.count("Uso CFDI SAT")
        regimen_count = frappe.db.count("Regimen Fiscal SAT")

        self.assertGreater(uso_cfdi_count, 0, "Debe haber registros en Uso CFDI SAT")
        self.assertGreater(regimen_count, 0, "Debe haber registros en Regimen Fiscal SAT")

    def test_warehouse_types_created(self):
        """Test: Warehouse Types básicos fueron creados"""
        basic_types = ["Stores", "Work In Progress", "Finished Goods", "Transit"]

        for wh_type in basic_types:
            exists = frappe.db.exists("Warehouse Type", wh_type)
            self.assertTrue(exists, f"Warehouse Type {wh_type} debe existir")

    def test_basic_uoms_created(self):
        """Test: UOMs básicos fueron creados"""
        basic_uoms = ["Nos", "Unit", "Piece"]

        for uom in basic_uoms:
            exists = frappe.db.exists("UOM", uom)
            self.assertTrue(exists, f"UOM {uom} debe existir")

    def test_frappe_core_intact(self):
        """Test: Core de Frappe sigue funcionando después de instalación"""
        # Verificar funciones básicas de Frappe
        self.assertIsNotNone(frappe.session.user)
        self.assertTrue(frappe.flags.in_test)

        # Verificar que podemos hacer queries básicas
        result = frappe.db.sql("SELECT 1 as test", as_dict=True)
        self.assertEqual(result[0].test, 1)

    def test_erpnext_integration_not_broken(self):
        """Test: Integración con ERPNext no está rota si está instalado"""
        erpnext_installed = "erpnext" in frappe.get_installed_apps()

        if erpnext_installed:
            # Verificar que DocTypes básicos de ERPNext siguen funcionando
            try:
                companies = frappe.get_all("Company", limit=1)
                customers = frappe.get_all("Customer", limit=1)

                # Solo verificar que las consultas funcionan
                self.assertIsInstance(companies, list)
                self.assertIsInstance(customers, list)

            except Exception as e:
                self.fail(f"Integración con ERPNext rota: {e}")

    def test_permissions_setup_basic(self):
        """Test: Setup básico de permisos funciona"""
        try:
            # Verificar que el usuario Administrator puede acceder a funciones básicas
            user_roles = frappe.get_roles()
            self.assertIsInstance(user_roles, list)

            # En testing, debe tener System Manager
            if frappe.session.user == "Administrator":
                self.assertIn("System Manager", user_roles)

        except Exception as e:
            self.fail(f"Error en setup de permisos: {e}")


if __name__ == "__main__":
    unittest.main()
