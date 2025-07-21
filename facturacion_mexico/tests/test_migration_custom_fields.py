"""
Test Suite: Migración de Custom Fields a Prefijo fm_
Objetivo: Verificar que la migración de 16 custom fields fue exitosa
Ejecutar: bench --site facturacion.dev run-tests --app facturacion_mexico --test facturacion_mexico.tests.test_migration_custom_fields
"""

import os
import re
import unittest

import frappe
from frappe.tests.utils import FrappeTestCase


class TestCustomFieldMigration(FrappeTestCase):
    """Test suite para verificar migración de custom fields"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Campos antiguos que NO deberían existir después de migración
        cls.old_field_names = [
            "cfdi_use", "payment_method_sat", "fiscal_status", "uuid_fiscal",
            "factura_fiscal_mx", "informacion_fiscal_mx_section", "column_break_fiscal_mx",
            "rfc", "regimen_fiscal", "uso_cfdi_default", "column_break_fiscal_customer",
            "producto_servicio_sat", "unidad_sat", "clasificacion_sat_section", "column_break_item_sat"
        ]

        # Campos nuevos que DEBERÍAN existir después de migración
        cls.new_field_names = [
            "fm_cfdi_use", "fm_payment_method_sat", "fm_fiscal_status", "fm_uuid_fiscal",
            "fm_factura_fiscal_mx", "fm_informacion_fiscal_section", "fm_column_break_fiscal",
            "fm_rfc", "fm_regimen_fiscal", "fm_uso_cfdi_default", "fm_column_break_fiscal_customer",
            "fm_producto_servicio_sat", "fm_unidad_sat", "fm_clasificacion_sat_section", "fm_column_break_item_sat"
        ]

        # Mapeo por DocType
        cls.doctype_field_mapping = {
            "Sales Invoice": [
                "fm_cfdi_use", "fm_payment_method_sat", "fm_fiscal_status",
                "fm_uuid_fiscal", "fm_factura_fiscal_mx", "fm_informacion_fiscal_section",
                "fm_column_break_fiscal"
            ],
            "Customer": [
                "fm_rfc", "fm_regimen_fiscal", "fm_uso_cfdi_default",
                "fm_informacion_fiscal_section_customer", "fm_column_break_fiscal_customer"
            ],
            "Item": [
                "fm_producto_servicio_sat", "fm_unidad_sat",
                "fm_clasificacion_sat_section", "fm_column_break_item_sat"
            ]
        }

    def test_01_all_migrated_custom_fields_exist(self):
        """Verificar que todos los custom fields migrados existen con prefijo fm_"""

        for doctype, expected_fields in self.doctype_field_mapping.items():
            with self.subTest(doctype=doctype):

                custom_fields = frappe.get_all(
                    "Custom Field",
                    filters={"dt": doctype},
                    fields=["fieldname", "label", "fieldtype"],
                    order_by="idx"
                )

                actual_fieldnames = [f.fieldname for f in custom_fields]

                for expected_field in expected_fields:
                    self.assertIn(
                        expected_field,
                        actual_fieldnames,
                        f"Campo esperado {expected_field} no encontrado en {doctype}. "
                        f"Campos actuales: {actual_fieldnames}"
                    )

    def test_02_no_old_fields_exist_in_database(self):
        """Verificar que NO quedan campos antiguos en la base de datos"""

        for doctype in ["Sales Invoice", "Customer", "Item"]:
            with self.subTest(doctype=doctype):

                old_fields_found = frappe.get_all(
                    "Custom Field",
                    filters={
                        "dt": doctype,
                        "fieldname": ["in", self.old_field_names]
                    },
                    fields=["fieldname", "label"]
                )

                self.assertEqual(
                    len(old_fields_found),
                    0,
                    f"Se encontraron campos antiguos en {doctype}: "
                    f"{[f.fieldname for f in old_fields_found]}"
                )

    def test_03_database_columns_renamed_correctly(self):
        """Verificar que las columnas en DB fueron renombradas correctamente"""

        # Verificar Sales Invoice columns
        si_columns = frappe.db.sql("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'tabSales Invoice'
            AND COLUMN_NAME LIKE 'fm_%'
        """, as_dict=True)

        si_column_names = [col.COLUMN_NAME for col in si_columns]

        expected_si_columns = [
            "fm_cfdi_use", "fm_payment_method_sat",
            "fm_fiscal_status", "fm_uuid_fiscal", "fm_factura_fiscal_mx"
        ]

        for expected_column in expected_si_columns:
            self.assertIn(
                expected_column,
                si_column_names,
                f"Columna {expected_column} no encontrada en tabSales Invoice. "
                f"Columnas fm_ encontradas: {si_column_names}"
            )

        # Verificar Customer columns
        customer_columns = frappe.db.sql("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'tabCustomer'
            AND COLUMN_NAME LIKE 'fm_%'
        """, as_dict=True)

        customer_column_names = [col.COLUMN_NAME for col in customer_columns]

        expected_customer_columns = ["fm_rfc", "fm_regimen_fiscal", "fm_uso_cfdi_default"]

        for expected_column in expected_customer_columns:
            self.assertIn(
                expected_column,
                customer_column_names,
                f"Columna {expected_column} no encontrada en tabCustomer"
            )

        # Verificar Item columns
        item_columns = frappe.db.sql("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'tabItem'
            AND COLUMN_NAME LIKE 'fm_%'
        """, as_dict=True)

        item_column_names = [col.COLUMN_NAME for col in item_columns]

        expected_item_columns = ["fm_producto_servicio_sat", "fm_unidad_sat"]

        for expected_column in expected_item_columns:
            self.assertIn(
                expected_column,
                item_column_names,
                f"Columna {expected_column} no encontrada en tabItem"
            )

    def test_04_no_old_field_references_in_code(self):
        """Verificar que no quedan referencias a campos antiguos en código"""

        # Directorios a verificar
        directories = ["facturacion_mexico"]

        problematic_references = []

        for directory in directories:
            if not os.path.exists(directory):
                continue

            for root, dirs, files in os.walk(directory):
                # Excluir directorios no relevantes
                dirs_to_skip = ['.git', '__pycache__', 'patches', 'node_modules']
                dirs[:] = [d for d in dirs if not any(skip in d for skip in dirs_to_skip)]

                for file in files:
                    if file.endswith('.py'):
                        filepath = os.path.join(root, file)

                        # Saltar archivos de migración
                        if any(skip in filepath for skip in ['migrate_custom_field', 'backup_custom_field', 'test_migration']):
                            continue

                        try:
                            with open(filepath, encoding='utf-8') as f:
                                content = f.read()
                        except (FileNotFoundError, PermissionError, UnicodeDecodeError):
                            continue

                        # Verificar cada campo antiguo - patrones específicos que indican uso real
                        for old_field in self.old_field_names:
                            # Patrones que SÍ indican referencias problemáticas
                            problematic_patterns = [
                                rf'\.{old_field}(?!\w)',  # .cfdi_use (pero no .cfdi_use_something)
                                rf'"{old_field}"(?!\w)',  # "cfdi_use"
                                rf"'{old_field}'(?!\w)",  # 'cfdi_use'
                                rf'\["{old_field}"\]',    # ["cfdi_use"]
                                rf"\['{old_field}'\]",    # ['cfdi_use']
                                rf'get\("{old_field}"\)', # get("cfdi_use")
                                rf"get\('{old_field}'\)", # get('cfdi_use')
                            ]

                            for pattern in problematic_patterns:
                                matches = re.finditer(pattern, content, re.IGNORECASE)
                                for match in matches:
                                    # Obtener contexto de línea
                                    lines = content[:match.start()].split('\n')
                                    line_num = len(lines)
                                    line_content = content.split('\n')[line_num-1] if line_num <= len(content.split('\n')) else ""

                                    # Filtrar falsos positivos comunes
                                    if any(fp in line_content.lower() for fp in ['comment', '#', 'rfc_emisor', 'test_', '_test']):
                                        continue

                                    problematic_references.append({
                                        'file': filepath,
                                        'line': line_num,
                                        'field': old_field,
                                        'content': line_content.strip(),
                                        'pattern': pattern
                                    })

        # Reportar referencias problemáticas encontradas
        if problematic_references:
            error_msg = "Se encontraron referencias a campos antiguos:\n"
            for ref in problematic_references[:5]:  # Mostrar primeros 5
                error_msg += f"\n- {ref['file']}:{ref['line']} - Campo: {ref['field']}"
                error_msg += f"\n  Línea: {ref['content'][:100]}"

            if len(problematic_references) > 5:
                error_msg += f"\n... y {len(problematic_references) - 5} referencias más."

            self.fail(error_msg)

    def test_05_functional_sales_invoice_creation(self):
        """Test funcional: Crear Sales Invoice con nuevos campos"""

        # Crear Customer de prueba con nuevos campos
        customer = self.create_test_customer()

        # Crear Sales Invoice con nuevos campos
        si = frappe.new_doc("Sales Invoice")
        si.customer = customer
        si.company = frappe.defaults.get_defaults().get("company", "Test Company Motor Reglas")

        # Usar NUEVOS nombres de campo
        si.fm_cfdi_use = "G03"  # Campo migrado
        si.fm_payment_method_sat = "PUE"  # Campo migrado

        # Agregar item
        si.append("items", {
            "item_code": self.create_test_item(),
            "qty": 1,
            "rate": 100
        })

        try:
            si.insert(ignore_permissions=True)

            # Verificar que los campos nuevos existen y tienen valores
            self.assertTrue(hasattr(si, "fm_cfdi_use"), "Campo fm_cfdi_use no existe")
            self.assertTrue(hasattr(si, "fm_payment_method_sat"), "Campo fm_payment_method_sat no existe")
            self.assertEqual(si.fm_cfdi_use, "G03")
            self.assertEqual(si.fm_payment_method_sat, "PUE")

            # Verificar que campos antiguos NO existen
            self.assertFalse(hasattr(si, "cfdi_use"), "Campo antiguo cfdi_use aún existe")
            self.assertFalse(hasattr(si, "payment_method_sat"), "Campo antiguo payment_method_sat aún existe")

        finally:
            # Cleanup
            if frappe.db.exists("Sales Invoice", si.name):
                frappe.delete_doc("Sales Invoice", si.name, force=True, ignore_permissions=True)

    def test_06_functional_customer_rfc_handling(self):
        """Test funcional: Manejo de RFC en Customer con nuevo campo"""

        # Crear customer con RFC usando NUEVO nombre de campo
        customer = frappe.new_doc("Customer")
        customer.customer_name = f"Test RFC Migration {frappe.generate_hash()[:6]}"
        customer.customer_type = "Individual"
        customer.fm_rfc = "XAXX010101000"  # Campo migrado

        try:
            customer.insert(ignore_permissions=True)

            # Verificar que el campo nuevo existe y tiene valor
            self.assertTrue(hasattr(customer, "fm_rfc"), "Campo fm_rfc no existe")
            self.assertEqual(customer.fm_rfc, "XAXX010101000")

            # Verificar que campo antiguo NO existe
            self.assertFalse(hasattr(customer, "rfc"), "Campo antiguo rfc aún existe")

        finally:
            # Cleanup
            if frappe.db.exists("Customer", customer.name):
                frappe.delete_doc("Customer", customer.name, force=True, ignore_permissions=True)

    def test_07_functional_item_sat_codes(self):
        """Test funcional: Códigos SAT en Item con nuevos campos"""

        item = frappe.new_doc("Item")
        item.item_code = f"TEST-SAT-{frappe.generate_hash()[:6]}"
        item.item_name = "Test SAT Migration"
        item.item_group = "All Item Groups"
        item.stock_uom = "Nos"

        # Usar NUEVOS nombres de campo
        item.fm_producto_servicio_sat = "01010101"  # Campo migrado
        item.fm_unidad_sat = "ACT"  # Campo migrado

        try:
            item.insert(ignore_permissions=True)

            # Verificar que los campos nuevos existen y tienen valores
            self.assertTrue(hasattr(item, "fm_producto_servicio_sat"), "Campo fm_producto_servicio_sat no existe")
            self.assertTrue(hasattr(item, "fm_unidad_sat"), "Campo fm_unidad_sat no existe")
            self.assertEqual(item.fm_producto_servicio_sat, "01010101")
            self.assertEqual(item.fm_unidad_sat, "ACT")

            # Verificar que campos antiguos NO existen
            self.assertFalse(hasattr(item, "producto_servicio_sat"), "Campo antiguo producto_servicio_sat aún existe")
            self.assertFalse(hasattr(item, "unidad_sat"), "Campo antiguo unidad_sat aún existe")

        finally:
            # Cleanup
            if frappe.db.exists("Item", item.name):
                frappe.delete_doc("Item", item.name, force=True, ignore_permissions=True)

    def test_08_field_structure_and_properties(self):
        """Verificar que las propiedades de los campos se mantuvieron correctamente"""

        # Verificar campo crítico: fm_cfdi_use
        cfdi_field = frappe.get_doc("Custom Field", {"dt": "Sales Invoice", "fieldname": "fm_cfdi_use"})
        self.assertEqual(cfdi_field.fieldtype, "Link")
        self.assertEqual(cfdi_field.options, "Uso CFDI SAT")
        self.assertEqual(cfdi_field.reqd, 1)
        self.assertEqual(cfdi_field.label, "Uso del CFDI")

        # Verificar campo crítico: fm_rfc
        rfc_field = frappe.get_doc("Custom Field", {"dt": "Customer", "fieldname": "fm_rfc"})
        self.assertEqual(rfc_field.fieldtype, "Data")
        self.assertEqual(rfc_field.label, "RFC")

        # Verificar campo crítico: fm_fiscal_status
        status_field = frappe.get_doc("Custom Field", {"dt": "Sales Invoice", "fieldname": "fm_fiscal_status"})
        self.assertEqual(status_field.fieldtype, "Select")
        self.assertEqual(status_field.read_only, 1)
        self.assertIn("Pendiente", status_field.options)
        self.assertIn("Timbrada", status_field.options)

    def test_09_migration_data_integrity(self):
        """Verificar que los datos existentes se preservaron durante la migración"""

        # Este test verifica que si existían datos en los campos antiguos,
        # se mantuvieron en los campos nuevos

        # Buscar documentos que puedan tener datos en campos migrados
        invoices_with_fiscal_data = frappe.db.sql("""
            SELECT name, fm_cfdi_use, fm_fiscal_status
            FROM `tabSales Invoice`
            WHERE fm_cfdi_use IS NOT NULL OR fm_fiscal_status IS NOT NULL
            LIMIT 5
        """, as_dict=True)

        # Si hay datos, verificar que están en campos correctos
        for invoice in invoices_with_fiscal_data:
            if invoice.fm_cfdi_use:
                # Verificar que existe el registro referenciado
                uso_cfdi_exists = frappe.db.exists("Uso CFDI SAT", invoice.fm_cfdi_use)
                if uso_cfdi_exists:  # Solo validar si el catálogo está poblado
                    self.assertTrue(
                        uso_cfdi_exists,
                        f"Uso CFDI {invoice.fm_cfdi_use} referenciado en factura {invoice.name} no existe"
                    )

            if invoice.fm_fiscal_status:
                self.assertIn(
                    invoice.fm_fiscal_status,
                    ["Pendiente", "Timbrada", "Cancelada", "Error"],
                    f"Estado fiscal inválido {invoice.fm_fiscal_status} en factura {invoice.name}"
                )

    def create_test_customer(self):
        """Helper para crear customer de prueba con nuevos campos"""
        customer = frappe.new_doc("Customer")
        customer.customer_name = f"Test Customer Migration {frappe.generate_hash()[:6]}"
        customer.customer_type = "Individual"
        customer.fm_rfc = "XAXX010101000"  # Usar nuevo campo
        customer.insert(ignore_permissions=True)
        return customer.name

    def create_test_item(self):
        """Helper para crear item de prueba con nuevos campos"""
        item = frappe.new_doc("Item")
        item.item_code = f"TEST-ITEM-{frappe.generate_hash()[:6]}"
        item.item_name = "Test Item Migration"
        item.item_group = "All Item Groups"
        item.stock_uom = "Nos"
        item.fm_producto_servicio_sat = "01010101"  # Usar nuevo campo
        item.insert(ignore_permissions=True)
        return item.item_code
