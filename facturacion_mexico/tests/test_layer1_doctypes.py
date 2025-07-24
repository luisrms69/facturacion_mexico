# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 1 DocTypes Tests
Tests básicos para verificar que DocTypes principales funcionan
"""

import frappe
import unittest


class TestLayer1DocTypes(unittest.TestCase):
    """Tests de DocTypes básicos - Layer 1"""

    @classmethod
    def setUpClass(cls):
        """Setup inicial para todos los tests"""
        frappe.clear_cache()

    def test_facturacion_mexico_settings_doctype(self):
        """Test: DocType Facturacion Mexico Settings"""
        # Verificar que el DocType existe
        self.assertTrue(frappe.db.exists("DocType", "Facturacion Mexico Settings"))

        # Verificar que podemos obtener el documento
        settings = frappe.get_single("Facturacion Mexico Settings")
        self.assertIsNotNone(settings)

        # Verificar campos básicos existen
        self.assertTrue(hasattr(settings, "sandbox_mode"))
        self.assertTrue(hasattr(settings, "timeout"))

    def test_uso_cfdi_sat_doctype(self):
        """Test: DocType Uso CFDI SAT"""
        # Verificar que el DocType existe
        self.assertTrue(frappe.db.exists("DocType", "Uso CFDI SAT"))

        # Verificar que hay registros
        uso_cfdi_count = frappe.db.count("Uso CFDI SAT")
        self.assertGreater(uso_cfdi_count, 0, "Debe haber registros de Uso CFDI SAT")

        # Verificar estructura de un registro
        uso_cfdi = frappe.db.get_value("Uso CFDI SAT", {"code": "G01"},
                                      ["code", "description"], as_dict=True)
        if uso_cfdi:
            self.assertEqual(uso_cfdi.code, "G01")
            self.assertIsNotNone(uso_cfdi.description)

    def test_regimen_fiscal_sat_doctype(self):
        """Test: DocType Regimen Fiscal SAT"""
        # Verificar que el DocType existe
        self.assertTrue(frappe.db.exists("DocType", "Regimen Fiscal SAT"))

        # Verificar que hay registros
        regimen_count = frappe.db.count("Regimen Fiscal SAT")
        self.assertGreater(regimen_count, 0, "Debe haber registros de Regimen Fiscal SAT")

        # Verificar estructura de un registro
        regimen = frappe.db.get_value("Regimen Fiscal SAT", {"code": "601"},
                                     ["code", "description"], as_dict=True)
        if regimen:
            self.assertEqual(regimen.code, "601")
            self.assertIsNotNone(regimen.description)

    def test_addenda_type_doctype_exists(self):
        """Test: DocType Addenda Type existe"""
        addenda_type_exists = frappe.db.exists("DocType", "Addenda Type")

        if addenda_type_exists:
            # Si existe, verificar estructura básica
            meta = frappe.get_meta("Addenda Type")
            self.assertIsNotNone(meta)

            # Verificar campos principales
            field_names = [f.fieldname for f in meta.fields]
            expected_fields = ["description", "version", "is_active"]

            for field in expected_fields:
                self.assertIn(field, field_names,
                             f"Addenda Type debe tener campo {field}")

    def test_multi_sucursal_doctypes_exist_if_enabled(self):
        """Test: DocTypes multi-sucursal si están habilitados"""
        # Verificar Branch si existe
        branch_exists = frappe.db.exists("DocType", "Branch")
        if branch_exists:
            meta = frappe.get_meta("Branch")
            self.assertIsNotNone(meta)

        # Verificar Configuracion Fiscal Sucursal si existe
        config_fiscal_exists = frappe.db.exists("DocType", "Configuracion Fiscal Sucursal")
        if config_fiscal_exists:
            meta = frappe.get_meta("Configuracion Fiscal Sucursal")
            self.assertIsNotNone(meta)

    def test_doctype_permissions_basic(self):
        """Test: Permisos básicos de DocTypes funcionan"""
        # Verificar que podemos leer DocTypes básicos
        try:
            # Esto no debe fallar con permisos
            uso_cfdi_list = frappe.get_all("Uso CFDI SAT", limit=1)
            regimen_list = frappe.get_all("Regimen Fiscal SAT", limit=1)

            # Solo verificar que no falló con errores de permisos
            self.assertIsInstance(uso_cfdi_list, list)
            self.assertIsInstance(regimen_list, list)

        except frappe.PermissionError:
            self.fail("No debe haber errores de permisos para DocTypes básicos")

    def test_doctype_meta_loading(self):
        """Test: Carga de metadatos de DocTypes funciona"""
        basic_doctypes = [
            "Facturacion Mexico Settings",
            "Uso CFDI SAT",
            "Regimen Fiscal SAT"
        ]

        for doctype in basic_doctypes:
            if frappe.db.exists("DocType", doctype):
                try:
                    meta = frappe.get_meta(doctype)
                    self.assertIsNotNone(meta)
                    self.assertEqual(meta.name, doctype)
                    self.assertIsInstance(meta.fields, list)
                except Exception as e:
                    self.fail(f"Error cargando metadatos de {doctype}: {e}")

    def test_doctype_creation_basic(self):
        """Test: Creación básica de documentos funciona"""
        # Probar crear un documento simple de test si es posible
        try:
            # Verificar que podemos crear settings
            settings = frappe.get_single("Facturacion Mexico Settings")
            # Si llegamos aquí, la creación/obtención funciona
            self.assertIsNotNone(settings)

        except Exception as e:
            self.fail(f"Error en creación básica de documentos: {e}")

    def test_standard_frappe_doctypes_available(self):
        """Test: DocTypes estándar de Frappe están disponibles"""
        standard_doctypes = ["User", "Role", "DocType", "Custom Field"]

        for doctype in standard_doctypes:
            exists = frappe.db.exists("DocType", doctype)
            self.assertTrue(exists, f"DocType estándar {doctype} debe existir")

    def test_erpnext_doctypes_available_if_installed(self):
        """Test: DocTypes de ERPNext si está instalado"""
        erpnext_installed = "erpnext" in frappe.get_installed_apps()

        if erpnext_installed:
            erpnext_doctypes = ["Customer", "Sales Invoice", "Item", "Company"]

            for doctype in erpnext_doctypes:
                exists = frappe.db.exists("DocType", doctype)
                self.assertTrue(exists, f"DocType ERPNext {doctype} debe existir")


if __name__ == "__main__":
    unittest.main()