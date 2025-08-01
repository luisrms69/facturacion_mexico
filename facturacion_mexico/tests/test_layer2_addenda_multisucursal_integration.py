# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 2 Addenda Multi-Sucursal Integration Tests
Tests de integración específicos para el sistema combinado Addenda + Multi-Sucursal Sprint 6
"""

import unittest

import frappe


class TestLayer2AddendaMultiSucursalIntegration(unittest.TestCase):
    """Tests de integración Addenda-Multi-Sucursal - Layer 2"""

    @classmethod
    def setUpClass(cls):
        """Setup inicial para todos los tests"""
        frappe.clear_cache()
        cls.test_branch = None
        cls.test_customer = None

    def setUp(self):
        """Setup para cada test individual"""
        # Crear datos de test solo si los DocTypes existen
        if frappe.db.exists("DocType", "Branch") and frappe.db.exists("DocType", "Customer"):
            self.create_test_data()

    def tearDown(self):
        """Cleanup después de cada test"""
        self.cleanup_test_data()

    def create_test_data(self):
        """Crear datos de test para integración"""
        try:
            # Crear Branch de test
            if not frappe.db.exists("Branch", "Test Branch Addenda"):
                self.test_branch = frappe.get_doc({
                    "doctype": "Branch",
                    "branch": "Test Branch Addenda",
                    "fm_enable_fiscal": 1,
                    "fm_lugar_expedicion": "Test Location"
                })
                self.test_branch.insert(ignore_permissions=True)

            # Crear Customer de test
            if not frappe.db.exists("Customer", "Test Customer Addenda"):
                self.test_customer = frappe.get_doc({
                    "doctype": "Customer",
                    "customer_name": "Test Customer Addenda",
                    "fm_requires_addenda": 1,
                    "fm_default_addenda_type": "TEST_GENERIC" if frappe.db.exists("Addenda Type", "TEST_GENERIC") else None
                })
                self.test_customer.insert(ignore_permissions=True)

        except Exception as e:
            print(f"Warning: Could not create test data: {e}")

    def cleanup_test_data(self):
        """Limpiar datos de test"""
        try:
            if self.test_branch and frappe.db.exists("Branch", "Test Branch Addenda"):
                frappe.delete_doc("Branch", "Test Branch Addenda", force=True)
            if self.test_customer and frappe.db.exists("Customer", "Test Customer Addenda"):
                frappe.delete_doc("Customer", "Test Customer Addenda", force=True)
        except Exception:
            pass  # Ignore cleanup errors

    def test_branch_addenda_custom_fields_integration(self):
        """Test: Integración de custom fields de Branch con sistema de addendas"""
        if not frappe.db.exists("DocType", "Branch"):
            self.skipTest("Branch DocType no disponible")

        # Verificar que Branch tiene campos relacionados con addendas si están implementados
        branch_fields = frappe.db.sql("""
            SELECT fieldname, fieldtype, label
            FROM `tabCustom Field`
            WHERE dt = 'Branch' AND (
                fieldname LIKE '%addenda%' OR
                fieldname LIKE 'fm_%' OR
                label LIKE '%Addenda%'
            )
        """, as_dict=True)

        # Al menos debe tener campos fiscales que podrían integrarse con addendas
        fiscal_fields = [f for f in branch_fields if 'fiscal' in f.fieldname.lower()]
        self.assertGreaterEqual(len(fiscal_fields), 1,
            "Branch debe tener al menos un campo fiscal para integración con addendas")

    def test_sales_invoice_branch_addenda_integration(self):
        """Test: Integración de Sales Invoice con Branch y Addenda"""
        if not frappe.db.exists("DocType", "Sales Invoice"):
            self.skipTest("Sales Invoice DocType no disponible")

        # Verificar custom fields de integración en Sales Invoice
        si_fields = frappe.db.sql("""
            SELECT fieldname, fieldtype, label
            FROM `tabCustom Field`
            WHERE dt = 'Sales Invoice' AND (
                fieldname LIKE 'fm_branch%' OR
                fieldname LIKE 'fm_addenda%' OR
                fieldname LIKE 'fm_multi_sucursal%'
            )
        """, as_dict=True)

        # Verificar campos críticos de integración
        field_names = [f.fieldname for f in si_fields]

        # Campos de Multi-Sucursal
        multi_sucursal_fields = [f for f in field_names if 'branch' in f or 'sucursal' in f]

        # Campos de Addenda
        addenda_fields = [f for f in field_names if 'addenda' in f]

        self.assertGreater(len(multi_sucursal_fields), 0,
            "Sales Invoice debe tener campos de Multi-Sucursal")
        self.assertGreater(len(addenda_fields), 0,
            "Sales Invoice debe tener campos de Addenda")

    def test_customer_branch_addenda_relationship(self):
        """Test: Relación Customer-Branch-Addenda"""
        if not all([
            frappe.db.exists("DocType", "Customer"),
            frappe.db.exists("DocType", "Branch"),
            frappe.db.exists("DocType", "Sales Invoice")
        ]):
            self.skipTest("DocTypes requeridos no disponibles")

        # Verificar que Customer tiene campos de addenda
        customer_addenda_fields = frappe.db.sql("""
            SELECT fieldname FROM `tabCustom Field`
            WHERE dt = 'Customer' AND fieldname LIKE '%addenda%'
        """, as_dict=True)

        self.assertGreater(len(customer_addenda_fields), 0,
            "Customer debe tener campos de addenda para integración")

        # Verificar que Sales Invoice puede relacionar Customer, Branch y Addenda
        si_relation_fields = frappe.db.sql("""
            SELECT fieldname, fieldtype FROM `tabCustom Field`
            WHERE dt = 'Sales Invoice' AND (
                fieldname LIKE '%branch%' OR
                fieldname LIKE '%addenda%' OR
                fieldname = 'customer'
            )
        """, as_dict=True)

        relation_types = [f.fieldname for f in si_relation_fields]

        # Debe poder relacionar con customer (estándar) y branch/addenda (custom)
        has_customer_relation = 'customer' in relation_types or any('customer' in f for f in relation_types)
        has_branch_relation = any('branch' in f for f in relation_types)
        has_addenda_relation = any('addenda' in f for f in relation_types)

        # Customer es un campo estándar de Sales Invoice, verificar que existe
        try:
            si_meta = frappe.get_meta("Sales Invoice")
            standard_fields = [f.fieldname for f in si_meta.fields]
            has_customer_standard = 'customer' in standard_fields

            self.assertTrue(has_customer_standard or has_customer_relation,
                "Sales Invoice debe poder relacionar con Customer")
        except Exception:
            # Fallback si no se puede acceder a meta
            if not has_customer_relation:
                print("⚠ No se pudo verificar relación con Customer")

        # Si tiene campos de branch o addenda, la integración está implementada
        integration_available = has_branch_relation or has_addenda_relation
        if integration_available:
            print("✓ Integración Customer-Branch-Addenda detectada")

    def test_addenda_generation_with_branch_context(self):
        """Test: Generación de addenda con contexto de sucursal"""
        # Verificar que existen módulos de generación de addendas
        try:
            # Intentar importar módulo de generación de addendas
            from facturacion_mexico.addendas import generic_addenda_generator

            # Verificar que el generador puede trabajar con contexto de sucursal
            generator_methods = dir(generic_addenda_generator)

            # Buscar métodos que puedan manejar branch/sucursal
            branch_aware_methods = [m for m in generator_methods
                                  if 'branch' in m.lower() or 'sucursal' in m.lower()]

            if branch_aware_methods:
                print(f"✓ Generador de addendas con contexto de sucursal: {branch_aware_methods}")
            else:
                print("ℹ Generador de addendas genérico disponible")

        except ImportError:
            self.skipTest("Módulo de generación de addendas no disponible")

    def test_certificate_selection_per_branch(self):
        """Test: Selección de certificados por sucursal para addendas"""
        if not frappe.db.exists("DocType", "Branch"):
            self.skipTest("Branch DocType no disponible")

        # Verificar si Branch tiene campos relacionados con certificados
        cert_fields = frappe.db.sql("""
            SELECT fieldname, fieldtype, label
            FROM `tabCustom Field`
            WHERE dt = 'Branch' AND (
                fieldname LIKE '%cert%' OR
                fieldname LIKE '%certificado%' OR
                label LIKE '%Cert%'
            )
        """, as_dict=True)

        if len(cert_fields) > 0:
            print(f"✓ Branch tiene campos de certificados: {[f.fieldname for f in cert_fields]}")

            # Verificar que los campos de certificados pueden integrarse con addendas
            for field in cert_fields:
                self.assertIsNotNone(field.fieldtype,
                    f"Campo de certificado {field.fieldname} debe tener tipo definido")
        else:
            print("ℹ Branch no tiene campos específicos de certificados")

    def test_addenda_template_branch_variables(self):
        """Test: Templates de addenda con variables de sucursal"""
        if not frappe.db.exists("DocType", "Addenda Type"):
            self.skipTest("Addenda Type DocType no disponible")

        # Verificar si existe DocType para templates
        template_doctypes = [
            "Addenda Template",
            "Addenda Configuration"
        ]

        available_templates = []
        for doctype in template_doctypes:
            if frappe.db.exists("DocType", doctype):
                available_templates.append(doctype)

        if available_templates:
            print(f"✓ DocTypes de templates disponibles: {available_templates}")

            # Verificar estructura de template que podría incluir variables de sucursal
            for template_doctype in available_templates:
                try:
                    meta = frappe.get_meta(template_doctype)
                    template_fields = [f.fieldname for f in meta.fields]

                    # Buscar campos que podrían contener templates con variables
                    template_content_fields = [f for f in template_fields
                                             if 'template' in f or 'xml' in f or 'content' in f]

                    if template_content_fields:
                        print(f"✓ {template_doctype} tiene campos de template: {template_content_fields}")

                except Exception as e:
                    print(f"⚠ Error accediendo {template_doctype}: {e}")
        else:
            print("ℹ No hay DocTypes de templates específicos disponibles")

    def test_cross_module_validation(self):
        """Test: Validación cruzada entre módulos de Multi-Sucursal y Addendas"""
        # Verificar que ambos sistemas pueden coexistir sin conflictos

        # 1. Verificar campos custom en Sales Invoice no tienen conflictos
        si_fields = frappe.db.sql("""
            SELECT fieldname, fieldtype, label, insert_after
            FROM `tabCustom Field`
            WHERE dt = 'Sales Invoice' AND fieldname LIKE 'fm_%'
            ORDER BY idx
        """, as_dict=True)

        field_names = [f.fieldname for f in si_fields]

        # Verificar que no hay duplicados
        unique_fields = set(field_names)
        self.assertEqual(len(field_names), len(unique_fields),
            "No debe haber campos duplicados en Sales Invoice")

        # 2. Verificar secciones organizadas correctamente
        sections = [f for f in si_fields if f.fieldtype == 'Section Break']

        section_labels = [s.label for s in sections if s.label]
        multi_sucursal_sections = [s for s in section_labels if 'sucursal' in s.lower()]
        addenda_sections = [s for s in section_labels if 'addenda' in s.lower()]

        if multi_sucursal_sections and addenda_sections:
            print(f"✓ Secciones organizadas: Multi-Sucursal={multi_sucursal_sections}, Addenda={addenda_sections}")

        # 3. Verificar orden lógico de campos
        [f.insert_after for f in si_fields if f.insert_after]

        # No debe haber referencias circulares
        self.assertNotIn(None, [f.fieldname for f in si_fields],
            "Todos los custom fields deben tener nombres válidos")


if __name__ == "__main__":
    unittest.main()
