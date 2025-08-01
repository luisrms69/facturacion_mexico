# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 2 Customer Addenda Branch Integration Tests
Tests de integración para configuración de addendas específicas por sucursal y customer
"""

import unittest

import frappe


class TestLayer2CustomerAddendaBranch(unittest.TestCase):
    """Tests de integración Customer-Addenda-Branch - Layer 2"""

    @classmethod
    def setUpClass(cls):
        """Setup inicial para todos los tests"""
        frappe.clear_cache()

    def test_customer_default_addenda_configuration(self):
        """Test: Configuración por defecto de addenda en Customer"""
        if not frappe.db.exists("DocType", "Customer"):
            self.skipTest("Customer DocType no disponible")

        # Verificar campos de configuración de addenda en Customer
        customer_addenda_fields = frappe.db.sql("""
            SELECT fieldname, fieldtype, label, options
            FROM `tabCustom Field`
            WHERE dt = 'Customer' AND (
                fieldname LIKE '%addenda%' OR
                label LIKE '%Addenda%'
            )
        """, as_dict=True)

        self.assertGreater(len(customer_addenda_fields), 0,
            "Customer debe tener campos de configuración de addenda")

        # Verificar campos críticos
        field_names = [f.fieldname for f in customer_addenda_fields]

        # Campo para indicar si requiere addenda
        requires_addenda_fields = [f for f in field_names if 'require' in f and 'addenda' in f]

        # Campo para tipo de addenda por defecto
        default_type_fields = [f for f in field_names if 'default' in f and 'addenda' in f]

        if requires_addenda_fields:
            print(f"✓ Customer tiene campo 'requiere addenda': {requires_addenda_fields}")

        if default_type_fields:
            print(f"✓ Customer tiene campo 'tipo addenda por defecto': {default_type_fields}")

        # Al menos uno de estos patrones debería existir
        has_addenda_config = len(requires_addenda_fields) > 0 or len(default_type_fields) > 0
        self.assertTrue(has_addenda_config,
            "Customer debe tener configuración básica de addenda")

    def test_branch_specific_addenda_settings(self):
        """Test: Configuración específica de addenda por sucursal"""
        if not frappe.db.exists("DocType", "Branch"):
            self.skipTest("Branch DocType no disponible")

        # Verificar si Branch tiene configuraciones específicas de addenda
        branch_addenda_fields = frappe.db.sql("""
            SELECT fieldname, fieldtype, label, options
            FROM `tabCustom Field`
            WHERE dt = 'Branch' AND (
                fieldname LIKE '%addenda%' OR
                label LIKE '%Addenda%'
            )
        """, as_dict=True)

        if len(branch_addenda_fields) > 0:
            print(f"✓ Branch tiene configuración específica de addenda: {[f.fieldname for f in branch_addenda_fields]}")

            # Verificar tipos de campos
            for field in branch_addenda_fields:
                self.assertIsNotNone(field.fieldtype,
                    f"Campo {field.fieldname} debe tener tipo definido")
        else:
            print("ℹ Branch no tiene configuración específica de addenda")

    def test_sales_invoice_addenda_branch_inheritance(self):
        """Test: Herencia de configuración de addenda Customer->Branch->Sales Invoice"""
        if not frappe.db.exists("DocType", "Sales Invoice"):
            self.skipTest("Sales Invoice DocType no disponible")

        # Verificar campos en Sales Invoice que permitan herencia de configuración
        si_fields = frappe.db.sql("""
            SELECT fieldname, fieldtype, label, options, fetch_from
            FROM `tabCustom Field`
            WHERE dt = 'Sales Invoice' AND (
                fieldname LIKE '%addenda%' OR
                fieldname LIKE '%branch%' OR
                fieldname = 'customer'
            )
        """, as_dict=True)

        field_names = [f.fieldname for f in si_fields]

        # Verificar relaciones necesarias para herencia
        has_customer_relation = 'customer' in field_names or any('customer' in f for f in field_names)
        has_branch_relation = any('branch' in f for f in field_names)
        has_addenda_fields = any('addenda' in f for f in field_names)

        # Customer es un campo estándar de Sales Invoice
        try:
            si_meta = frappe.get_meta("Sales Invoice")
            standard_fields = [f.fieldname for f in si_meta.fields]
            has_customer_standard = 'customer' in standard_fields

            self.assertTrue(has_customer_standard or has_customer_relation,
                "Sales Invoice debe relacionar con Customer")
        except Exception:
            if not has_customer_relation:
                print("⚠ No se pudo verificar relación con Customer")

        if has_branch_relation and has_addenda_fields:
            print("✓ Sales Invoice puede heredar configuración Customer->Branch->Addenda")

            # Verificar campos con fetch_from para herencia automática
            fetch_fields = [f for f in si_fields if f.fetch_from]
            if fetch_fields:
                print(f"✓ Campos con herencia automática: {[f.fieldname for f in fetch_fields]}")

    def test_addenda_type_branch_compatibility(self):
        """Test: Compatibilidad de tipos de addenda con sucursales"""
        if not frappe.db.exists("DocType", "Addenda Type"):
            self.skipTest("Addenda Type DocType no disponible")

        # Verificar estructura de Addenda Type
        addenda_type_meta = frappe.get_meta("Addenda Type")
        addenda_fields = [f.fieldname for f in addenda_type_meta.fields]

        # Verificar campos que podrían indicar compatibilidad con sucursales
        branch_compatibility_fields = [f for f in addenda_fields
                                     if 'branch' in f.lower() or 'sucursal' in f.lower()]

        if branch_compatibility_fields:
            print(f"✓ Addenda Type tiene campos de compatibilidad con sucursales: {branch_compatibility_fields}")
        else:
            print("ℹ Addenda Type es genérico (compatible con todas las sucursales)")

        # Verificar que existe al menos un tipo de addenda para testing
        test_addenda_types = frappe.db.sql("""
            SELECT name FROM `tabAddenda Type`
            WHERE name LIKE 'TEST_%'
            LIMIT 3
        """, as_dict=True)

        if test_addenda_types:
            print(f"✓ Tipos de addenda de test disponibles: {[t.name for t in test_addenda_types]}")

    def test_customer_branch_addenda_validation_chain(self):
        """Test: Cadena de validación Customer->Branch->Addenda"""
        # Verificar que existe lógica de validación para la cadena de configuración

        # 1. Verificar módulos de validación
        validation_modules = [
            "facturacion_mexico.hooks_handlers.sales_invoice_validate",
            "facturacion_mexico.validaciones.hooks_handlers.sales_invoice_validate"
        ]

        available_validators = []
        for module_path in validation_modules:
            try:
                __import__(module_path, fromlist=[''])
                available_validators.append(module_path)
            except ImportError:
                continue

        if available_validators:
            print(f"✓ Módulos de validación disponibles: {available_validators}")

        # 2. Verificar hooks de validación en Sales Invoice
        from facturacion_mexico import hooks

        doc_events = getattr(hooks, 'doc_events', {})
        si_events = doc_events.get('Sales Invoice', {})

        validation_hooks = []
        for event in ['validate', 'before_submit', 'on_submit']:
            if event in si_events:
                validation_hooks.extend(si_events[event])

        addenda_validation_hooks = [h for h in validation_hooks
                                  if 'addenda' in h.lower() or 'branch' in h.lower()]

        if addenda_validation_hooks:
            print(f"✓ Hooks de validación Customer-Branch-Addenda: {addenda_validation_hooks}")

    def test_addenda_configuration_inheritance_priority(self):
        """Test: Prioridad de herencia en configuración de addenda"""
        # Verificar orden de prioridad: Sales Invoice > Customer > Branch > Default

        # 1. Verificar campos en Sales Invoice para override manual
        si_override_fields = frappe.db.sql("""
            SELECT fieldname, label, depends_on
            FROM `tabCustom Field`
            WHERE dt = 'Sales Invoice' AND fieldname LIKE '%addenda%'
            AND fieldtype IN ('Link', 'Select', 'Check')
        """, as_dict=True)

        # 2. Verificar campos en Customer para configuración por defecto
        customer_default_fields = frappe.db.sql("""
            SELECT fieldname, label, depends_on
            FROM `tabCustom Field`
            WHERE dt = 'Customer' AND fieldname LIKE '%addenda%'
            AND fieldtype IN ('Link', 'Select', 'Check')
        """, as_dict=True)

        # 3. Verificar configuración a nivel Branch si existe
        branch_config_fields = frappe.db.sql("""
            SELECT fieldname, label, depends_on
            FROM `tabCustom Field`
            WHERE dt = 'Branch' AND fieldname LIKE '%addenda%'
            AND fieldtype IN ('Link', 'Select', 'Check')
        """, as_dict=True)

        # Verificar jerarquía de configuración
        hierarchy_levels = 0

        if si_override_fields:
            hierarchy_levels += 1
            print(f"✓ Nivel 1 - Sales Invoice override: {[f.fieldname for f in si_override_fields]}")

        if customer_default_fields:
            hierarchy_levels += 1
            print(f"✓ Nivel 2 - Customer default: {[f.fieldname for f in customer_default_fields]}")

        if branch_config_fields:
            hierarchy_levels += 1
            print(f"✓ Nivel 3 - Branch config: {[f.fieldname for f in branch_config_fields]}")

        self.assertGreaterEqual(hierarchy_levels, 2,
            "Debe existir al menos configuración en Sales Invoice y Customer")

    def test_addenda_generation_context_passing(self):
        """Test: Paso de contexto Customer-Branch en generación de addenda"""
        # Verificar que el sistema puede pasar contexto de customer y branch al generar addendas

        try:
            # Verificar módulo de generación de addendas
            from facturacion_mexico.addendas import generic_addenda_generator

            # Buscar métodos que acepten contexto de customer y branch
            generator_methods = dir(generic_addenda_generator)

            # Métodos que podrían aceptar contexto
            context_methods = [m for m in generator_methods
                             if any(keyword in m.lower() for keyword in
                                   ['generate', 'create', 'build', 'process'])]

            if context_methods:
                print(f"✓ Métodos de generación disponibles: {context_methods}")

                # Verificar si algún método puede manejar customer y branch
                for method_name in context_methods[:3]:  # Verificar primeros 3 métodos
                    try:
                        method = getattr(generic_addenda_generator, method_name)
                        if callable(method):
                            print(f"✓ Método {method_name} es callable")
                    except AttributeError:
                        continue

        except ImportError:
            print("ℹ Módulo de generación de addendas no disponible para testing")

    def test_customer_addenda_configuration_ui_integration(self):
        """Test: Integración de UI para configuración de addenda en Customer"""
        if not frappe.db.exists("DocType", "Customer"):
            self.skipTest("Customer DocType no disponible")

        # Verificar organización de campos de addenda en Customer
        customer_addenda_fields = frappe.db.sql("""
            SELECT fieldname, fieldtype, label, insert_after, depends_on, collapsible
            FROM `tabCustom Field`
            WHERE dt = 'Customer' AND (
                fieldname LIKE '%addenda%' OR
                label LIKE '%Addenda%'
            )
            ORDER BY idx
        """, as_dict=True)

        if customer_addenda_fields:
            # Verificar que hay una sección para addendas
            sections = [f for f in customer_addenda_fields if f.fieldtype == 'Section Break']

            if sections:
                print(f"✓ Customer tiene sección de addendas: {[s.label for s in sections]}")

                # Verificar que la sección es colapsible para mejor UX
                collapsible_sections = [s for s in sections if s.collapsible]
                if collapsible_sections:
                    print("✓ Sección de addendas es colapsible")

            # Verificar campos de configuración
            config_fields = [f for f in customer_addenda_fields
                           if f.fieldtype in ['Check', 'Link', 'Select']]

            self.assertGreater(len(config_fields), 0,
                "Customer debe tener campos de configuración de addenda")


if __name__ == "__main__":
    unittest.main()
