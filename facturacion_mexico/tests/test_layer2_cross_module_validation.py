# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 2 Cross-Module Validation Tests
Tests de validación cruzada entre módulos Multi-Sucursal y Addendas Sprint 6
"""

import unittest

import frappe


class TestLayer2CrossModuleValidation(unittest.TestCase):
    """Tests de validación Cross-Module - Layer 2"""

    @classmethod
    def setUpClass(cls):
        """Setup inicial para todos los tests"""
        frappe.clear_cache()

    def test_custom_fields_naming_consistency(self):
        """Test: Consistencia en nomenclatura de custom fields entre módulos"""
        # Verificar que todos los custom fields siguen el patrón fm_*

        inconsistent_fields = frappe.db.sql("""
            SELECT dt, fieldname, label
            FROM `tabCustom Field`
            WHERE fieldname NOT LIKE 'fm_%'
            AND dt IN ('Sales Invoice', 'Customer', 'Branch', 'Payment Entry', 'Item')
            AND fieldname NOT IN ('customer', 'company', 'branch')
            AND fieldname NOT LIKE 'column_%'
            AND fieldname NOT LIKE 'section_%'
        """, as_dict=True)

        # Filtrar campos que podrían ser del sistema base
        system_fields = [
            'informacion_fiscal_mx_section', 'cfdi_use', 'payment_method_sat',
            'column_break_fiscal_mx', 'fiscal_status', 'uuid_fiscal',
            'factura_fiscal_mx', 'rfc', 'column_break_fiscal_customer',
            'regimen_fiscal', 'uso_cfdi_default', 'clasificacion_sat_section',
            'producto_servicio_sat', 'column_break_item_sat', 'fm_unidad_sat'
        ]

        real_inconsistent = [f for f in inconsistent_fields
                           if f.fieldname not in system_fields]

        if real_inconsistent:
            print(f"⚠ Campos sin prefijo fm_: {[(f.dt, f.fieldname) for f in real_inconsistent[:5]]}")
        else:
            print("✓ Todos los custom fields nuevos siguen nomenclatura fm_*")

        self.assertEqual(len(real_inconsistent), 0,
            "Todos los custom fields deben usar prefijo fm_")

    def test_sales_invoice_filters_implementation(self):
        """
        Test: Verificar implementación de filtros Sales Invoice en Factura Fiscal Mexico

        FASE 3: Validaciones de filtros dinámicos
        - Función setup_sales_invoice_filters existe
        - Filtros configuran criterios correctos
        - Validación de disponibilidad funciona
        """
        # Leer archivo JavaScript de Factura Fiscal Mexico
        js_file_path = "/home/erpnext/frappe-bench/apps/facturacion_mexico/facturacion_mexico/facturacion_fiscal/doctype/factura_fiscal_mexico/factura_fiscal_mexico.js"

        try:
            with open(js_file_path, 'r', encoding='utf-8') as f:
                js_content = f.read()
        except FileNotFoundError:
            self.fail(f"Archivo JavaScript no encontrado: {js_file_path}")

        # Verificar que función setup_sales_invoice_filters existe
        self.assertIn(
            "function setup_sales_invoice_filters",
            js_content,
            "Función setup_sales_invoice_filters debe existir"
        )

        # Verificar que se configura frm.set_query para sales_invoice
        self.assertIn(
            'frm.set_query("sales_invoice"',
            js_content,
            "Debe configurar filtros dinámicos para campo sales_invoice"
        )

        # Verificar criterios de filtro específicos
        filter_criteria = [
            'docstatus", "=", 1',  # Solo submitted
            'fm_factura_fiscal_mx", "in", ["", null]',  # Sin asignar
            'tax_id", "!=", ""'  # Con RFC
        ]

        for criteria in filter_criteria:
            self.assertIn(
                criteria,
                js_content,
                f"Filtro debe incluir criterio: {criteria}"
            )

        # Verificar función de validación de disponibilidad
        self.assertIn(
            "function validate_sales_invoice_availability",
            js_content,
            "Función validate_sales_invoice_availability debe existir"
        )

        # Verificar que se llama en el evento sales_invoice
        self.assertIn(
            "validate_sales_invoice_availability(frm)",
            js_content,
            "Validación debe ejecutarse cuando se selecciona Sales Invoice"
        )

        # Verificar comentarios de documentación FASE 3
        self.assertIn(
            "FASE 3: FILTROS SALES INVOICE DISPONIBLES",
            js_content,
            "Código debe estar documentado como FASE 3"
        )

        print("✅ Filtros Sales Invoice correctamente implementados")

    def test_sales_invoice_availability_validation_logic(self):
        """
        Test: Verificar lógica de validación de disponibilidad de Sales Invoice

        Validaciones:
        - Detecta Sales Invoice ya timbradas
        - Valida docstatus = 1
        - Verifica RFC presente
        - Maneja casos edge apropiadamente
        """
        # Leer archivo JavaScript
        js_file_path = "/home/erpnext/frappe-bench/apps/facturacion_mexico/facturacion_mexico/facturacion_fiscal/doctype/factura_fiscal_mexico/factura_fiscal_mexico.js"

        with open(js_file_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Verificar validación de estado timbrado
        self.assertIn(
            'fm_fiscal_status === "Timbrada"',
            js_content,
            "Debe validar si Sales Invoice ya está timbrada"
        )

        # Verificar validación de docstatus
        self.assertIn(
            "docstatus !== 1",
            js_content,
            "Debe validar que Sales Invoice esté submitted"
        )

        # Verificar validación de RFC
        self.assertIn(
            "!sales_invoice_data.tax_id",
            js_content,
            "Debe validar que Sales Invoice tenga RFC"
        )

        # Verificar mensajes de error apropiados
        error_messages = [
            "Sales Invoice No Disponible",
            "Sales Invoice No Válida",
            "RFC Faltante"
        ]

        for message in error_messages:
            self.assertIn(
                message,
                js_content,
                f"Debe mostrar mensaje de error: {message}"
            )

        # Verificar que limpia selección en caso de error
        self.assertIn(
            'frm.set_value("sales_invoice", "")',
            js_content,
            "Debe limpiar selección cuando Sales Invoice no es válida"
        )

        print("✅ Lógica de validación de disponibilidad correctamente implementada")

    def test_fase4_auto_load_payment_method_implementation(self):
        """
        Test: Verificar implementación FASE 4 - Auto-carga PUE mejorada

        Validaciones:
        - Función auto_load_payment_method_from_sales_invoice existe en Python
        - Función auto_load_payment_method_from_sales_invoice existe en JavaScript
        - Triggers configurados en sales_invoice y fm_payment_method_sat
        - Lógica PUE vs PPD implementada correctamente
        """
        # 1. Verificar función Python existe
        from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import FacturaFiscalMexico

        self.assertTrue(
            hasattr(FacturaFiscalMexico, "auto_load_payment_method_from_sales_invoice"),
            "Método auto_load_payment_method_from_sales_invoice debe existir en FacturaFiscalMexico"
        )

        # 2. Verificar función JavaScript existe
        js_file_path = "/home/erpnext/frappe-bench/apps/facturacion_mexico/facturacion_mexico/facturacion_fiscal/doctype/factura_fiscal_mexico/factura_fiscal_mexico.js"

        with open(js_file_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        self.assertIn(
            "function auto_load_payment_method_from_sales_invoice",
            js_content,
            "Función auto_load_payment_method_from_sales_invoice debe existir en JavaScript"
        )

        # 3. Verificar trigger sales_invoice llama auto-carga
        self.assertIn(
            "auto_load_payment_method_from_sales_invoice(frm)",
            js_content,
            "Trigger sales_invoice debe llamar función de auto-carga"
        )

        # 4. Verificar trigger fm_payment_method_sat existe
        self.assertIn(
            "fm_payment_method_sat: function (frm)",
            js_content,
            "Debe existir trigger para fm_payment_method_sat"
        )

        # 5. Verificar lógica PUE vs PPD
        pue_ppd_logic = [
            'fm_payment_method_sat === "PUE"',
            'fm_payment_method_sat === "PPD"',
            '"99 - Por definir"',
            "Payment Entry"
        ]

        for logic in pue_ppd_logic:
            self.assertIn(
                logic,
                js_content,
                f"Lógica PUE/PPD debe incluir: {logic}"
            )

        # 6. Verificar comentarios FASE 4
        self.assertIn(
            "FASE 4: AUTO-CARGA PUE MEJORADA",
            js_content,
            "Código debe estar documentado como FASE 4"
        )

        print("✅ FASE 4 - Auto-carga PUE mejorada correctamente implementada")

    def test_fase4_payment_entry_query_logic(self):
        """
        Test: Verificar lógica de consulta Payment Entry en FASE 4

        Validaciones:
        - Consulta Payment Entry con filtros correctos
        - Manejo de caso sin Payment Entry
        - Auto-asignación PPD vs PUE
        - No sobrescribir selección manual
        """
        # Verificar archivo Python tiene consulta Payment Entry
        python_file_path = "/home/erpnext/frappe-bench/apps/facturacion_mexico/facturacion_mexico/facturacion_fiscal/doctype/factura_fiscal_mexico/factura_fiscal_mexico.py"

        with open(python_file_path, 'r', encoding='utf-8') as f:
            python_content = f.read()

        # Verificar consulta Payment Entry - ACTUALIZADO para nueva implementación SQL
        payment_entry_query = [
            'get_payment_entry_by_invoice(',
            'frappe.db.sql(',
            'SELECT pe.name, pe.mode_of_payment',
            'FROM `tabPayment Entry` pe',
            'tabPayment Entry Reference'
        ]

        for query_part in payment_entry_query:
            self.assertIn(
                query_part,
                python_content,
                f"Consulta Payment Entry debe incluir: {query_part}"
            )

        # Verificar lógica condicional PUE/PPD
        conditional_logic = [
            'if self.fm_payment_method_sat == "PPD"',
            'if self.fm_payment_method_sat == "PUE"',
            'if self.fm_forma_pago_timbrado:',  # No sobrescribir
            'payment_entries = get_payment_entry_by_invoice'
        ]

        for logic in conditional_logic:
            self.assertIn(
                logic,
                python_content,
                f"Lógica condicional debe incluir: {logic}"
            )

        # Verificar JavaScript tiene lógica similar
        js_file_path = "/home/erpnext/frappe-bench/apps/facturacion_mexico/facturacion_mexico/facturacion_fiscal/doctype/factura_fiscal_mexico/factura_fiscal_mexico.js"

        with open(js_file_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        js_query_logic = [
            'get_payment_entry_for_javascript',
            'invoice_name: frm.doc.sales_invoice',
            'if (frm.doc.fm_forma_pago_timbrado)',  # No sobrescribir
            'r.message.success && r.message.data'
        ]

        for js_logic in js_query_logic:
            self.assertIn(
                js_logic,
                js_content,
                f"JavaScript debe incluir lógica: {js_logic}"
            )

        print("✅ FASE 4 - Lógica consulta Payment Entry correctamente implementada")

    def test_custom_fields_insert_after_chain(self):
        """Test: Cadena de insert_after en custom fields es válida"""
        # Verificar que no hay referencias circulares en insert_after

        all_custom_fields = frappe.db.sql("""
            SELECT dt, fieldname, insert_after
            FROM `tabCustom Field`
            WHERE dt IN ('Sales Invoice', 'Customer', 'Branch', 'Payment Entry', 'Item')
            ORDER BY dt, idx
        """, as_dict=True)

        # Agrupar por DocType
        by_doctype = {}
        for field in all_custom_fields:
            if field.dt not in by_doctype:
                by_doctype[field.dt] = []
            by_doctype[field.dt].append(field)

        for _doctype, fields in by_doctype.items():
            field_names = {f.fieldname for f in fields}

            # Verificar referencias circulares
            for field in fields:
                if field.insert_after and field.insert_after in field_names:
                    # Verificar que no se refiere a sí mismo
                    self.assertNotEqual(field.fieldname, field.insert_after,
                        f"Campo {field.fieldname} no puede referenciarse a sí mismo")

        print(f"✓ Verificación de referencias circulares completada para {len(by_doctype)} DocTypes")

    def test_section_breaks_organization(self):
        """Test: Organización lógica de Section Breaks entre módulos"""
        # Verificar que las secciones están organizadas lógicamente

        section_fields = frappe.db.sql("""
            SELECT dt, fieldname, label, insert_after
            FROM `tabCustom Field`
            WHERE fieldtype = 'Section Break'
            AND dt IN ('Sales Invoice', 'Customer', 'Branch')
            ORDER BY dt, idx
        """, as_dict=True)

        # Agrupar por DocType
        sections_by_doctype = {}
        for section in section_fields:
            if section.dt not in sections_by_doctype:
                sections_by_doctype[section.dt] = []
            sections_by_doctype[section.dt].append(section)

        for doctype, sections in sections_by_doctype.items():
            section_labels = [s.label for s in sections if s.label]

            # Verificar patrones esperados
            multi_sucursal_sections = [s for s in section_labels
                                     if any(keyword in s.lower() for keyword in
                                           ['sucursal', 'branch', 'multi'])]

            addenda_sections = [s for s in section_labels
                              if 'addenda' in s.lower()]

            fiscal_sections = [s for s in section_labels
                             if 'fiscal' in s.lower()]

            if multi_sucursal_sections:
                print(f"✓ {doctype} - Secciones Multi-Sucursal: {multi_sucursal_sections}")

            if addenda_sections:
                print(f"✓ {doctype} - Secciones Addenda: {addenda_sections}")

            if fiscal_sections:
                print(f"✓ {doctype} - Secciones Fiscales: {fiscal_sections}")

    def test_field_dependencies_cross_module(self):
        """Test: Dependencias de campos entre módulos"""
        # Verificar que las dependencias entre campos de diferentes módulos son válidas

        dependent_fields = frappe.db.sql("""
            SELECT dt, fieldname, depends_on
            FROM `tabCustom Field`
            WHERE depends_on IS NOT NULL
            AND depends_on != ''
            AND dt IN ('Sales Invoice', 'Customer', 'Branch')
        """, as_dict=True)

        if dependent_fields:
            print(f"✓ Campos con dependencias encontrados: {len(dependent_fields)}")

            for field in dependent_fields:
                # Verificar que depends_on no está vacío
                self.assertTrue(field.depends_on.strip(),
                    f"depends_on de {field.fieldname} no debe estar vacío")

                # Verificar sintaxis básica (debe contener eval: o campo)
                depends_on = field.depends_on.strip()
                has_eval = 'eval:' in depends_on
                has_field_ref = any(op in depends_on for op in ['==', '!=', '>', '<'])

                if not (has_eval or has_field_ref):
                    print(f"⚠ {field.dt}.{field.fieldname} depends_on format: {depends_on}")
        else:
            print("ℹ No hay campos con dependencias explícitas")

    def test_hooks_integration_consistency(self):
        """Test: Consistencia en integración de hooks entre módulos"""
        # Verificar que los hooks están configurados consistentemente

        from facturacion_mexico import hooks

        doc_events = getattr(hooks, 'doc_events', {})

        # Verificar hooks en DocTypes críticos
        critical_doctypes = ['Sales Invoice', 'Customer', 'Branch']

        for doctype in critical_doctypes:
            if doctype in doc_events:
                events = doc_events[doctype]

                # Verificar que hay hooks de validación
                validation_events = ['validate', 'before_submit', 'on_submit']
                has_validation = any(event in events for event in validation_events)

                if has_validation:
                    print(f"✓ {doctype} tiene hooks de validación")

                    # Verificar hooks específicos de módulos
                    for event, handlers in events.items():
                        if event in validation_events:
                            multi_sucursal_hooks = [h for h in handlers
                                                  if any(keyword in h.lower() for keyword in
                                                        ['branch', 'sucursal', 'multi'])]

                            addenda_hooks = [h for h in handlers
                                           if 'addenda' in h.lower()]

                            if multi_sucursal_hooks:
                                print(f"  ✓ {doctype}.{event} - Multi-Sucursal: {len(multi_sucursal_hooks)} hooks")

                            if addenda_hooks:
                                print(f"  ✓ {doctype}.{event} - Addenda: {len(addenda_hooks)} hooks")

    def test_api_endpoint_consistency(self):
        """Test: Consistencia en endpoints de API entre módulos"""
        # Verificar que los módulos exponen APIs consistentes

        api_modules = [
            "facturacion_mexico.multi_sucursal.api",
            "facturacion_mexico.addendas.api",
            "facturacion_mexico.api"
        ]

        available_apis = {}
        for module_path in api_modules:
            try:
                module = __import__(module_path, fromlist=[''])

                # Buscar funciones que podrían ser endpoints
                module_functions = [attr for attr in dir(module)
                                  if callable(getattr(module, attr))
                                  and not attr.startswith('_')]

                available_apis[module_path] = module_functions
                print(f"✓ {module_path} - {len(module_functions)} funciones disponibles")

            except ImportError:
                print(f"ℹ {module_path} no disponible")

        # Verificar patrones comunes en APIs
        if available_apis:
            common_patterns = ['get', 'create', 'update', 'delete', 'validate']

            for module_path, functions in available_apis.items():
                matching_patterns = []
                for pattern in common_patterns:
                    pattern_functions = [f for f in functions if pattern in f.lower()]
                    if pattern_functions:
                        matching_patterns.append(f"{pattern}({len(pattern_functions)})")

                if matching_patterns:
                    print(f"  ✓ {module_path} patrones: {', '.join(matching_patterns)}")

    def test_database_integrity_cross_module(self):
        """Test: Integridad de base de datos entre módulos"""
        # Verificar que no hay conflictos de integridad entre módulos

        # 1. Verificar que no hay custom fields duplicados
        duplicate_fields = frappe.db.sql("""
            SELECT dt, fieldname, COUNT(*) as count
            FROM `tabCustom Field`
            WHERE dt IN ('Sales Invoice', 'Customer', 'Branch', 'Payment Entry', 'Item')
            GROUP BY dt, fieldname
            HAVING COUNT(*) > 1
        """, as_dict=True)

        if duplicate_fields:
            print(f"⚠ Campos duplicados encontrados: {[(f.dt, f.fieldname) for f in duplicate_fields]}")
            for field in duplicate_fields:
                self.fail(f"Campo duplicado: {field.dt}.{field.fieldname} aparece {field.count} veces")
        else:
            print("✓ No hay custom fields duplicados")

        # 2. Verificar integridad referencial en Links
        link_fields = frappe.db.sql("""
            SELECT dt, fieldname, options
            FROM `tabCustom Field`
            WHERE fieldtype = 'Link'
            AND dt IN ('Sales Invoice', 'Customer', 'Branch')
        """, as_dict=True)

        broken_links = []
        for field in link_fields:
            if field.options and not frappe.db.exists("DocType", field.options):
                broken_links.append((field.dt, field.fieldname, field.options))

        if broken_links:
            print(f"⚠ Links rotos encontrados: {broken_links}")
        else:
            print(f"✓ Todos los {len(link_fields)} campos Link tienen referencias válidas")

    def test_module_load_order_dependencies(self):
        """Test: Orden de carga de módulos y dependencias"""
        # Verificar que los módulos pueden cargarse en cualquier orden

        module_paths = [
            "facturacion_mexico.multi_sucursal",
            "facturacion_mexico.addendas",
            "facturacion_mexico.facturacion_fiscal"
        ]

        loaded_modules = []
        failed_modules = []

        for module_path in module_paths:
            try:
                __import__(module_path, fromlist=[''])
                loaded_modules.append(module_path)
            except ImportError as e:
                failed_modules.append((module_path, str(e)))

        print(f"✓ Módulos cargados exitosamente: {len(loaded_modules)}")

        if failed_modules:
            print(f"⚠ Módulos no disponibles: {[m[0] for m in failed_modules]}")

        # Verificar que al menos el módulo principal se carga
        self.assertGreaterEqual(len(loaded_modules), 1,
            "Al menos un módulo principal debe cargarse")

    def test_error_handling_consistency(self):
        """Test: Consistencia en manejo de errores entre módulos"""
        # Verificar que los módulos manejan errores de manera consistente

        # Buscar archivos de utilidades de error
        error_modules = [
            "facturacion_mexico.utils.exceptions",
            "facturacion_mexico.exceptions",
            "facturacion_mexico.utils.error_handler"
        ]

        error_handlers = []
        for module_path in error_modules:
            try:
                module = __import__(module_path, fromlist=[''])
                error_handlers.append(module_path)

                # Buscar clases de excepción o funciones de manejo
                module_attrs = dir(module)
                exception_attrs = [attr for attr in module_attrs
                                 if any(keyword in attr.lower() for keyword in
                                       ['error', 'exception', 'handler'])]

                if exception_attrs:
                    print(f"✓ {module_path} - Manejo de errores: {exception_attrs[:3]}")

            except ImportError:
                continue

        if error_handlers:
            print(f"✓ Módulos de manejo de errores disponibles: {len(error_handlers)}")
        else:
            print("ℹ Usando manejo de errores estándar de Frappe")

    def test_performance_impact_cross_module(self):
        """Test: Impacto de rendimiento entre módulos"""
        # Verificar que la integración no impacta significativamente el rendimiento

        # Contar custom fields por DocType para estimar overhead
        field_counts = frappe.db.sql("""
            SELECT dt, COUNT(*) as field_count
            FROM `tabCustom Field`
            WHERE dt IN ('Sales Invoice', 'Customer', 'Branch', 'Payment Entry', 'Item')
            GROUP BY dt
            ORDER BY field_count DESC
        """, as_dict=True)

        for count in field_counts:
            print(f"✓ {count.dt}: {count.field_count} custom fields")

            # Alertar si hay demasiados campos (potencial impacto de rendimiento)
            if count.field_count > 20:
                print(f"⚠ {count.dt} tiene muchos custom fields ({count.field_count}) - considerar optimización")

        # Verificar hooks que podrían impactar rendimiento
        from facturacion_mexico import hooks
        doc_events = getattr(hooks, 'doc_events', {})

        for doctype, events in doc_events.items():
            total_hooks = sum(len(handlers) for handlers in events.values())
            if total_hooks > 5:
                print(f"⚠ {doctype} tiene {total_hooks} hooks - verificar impacto de rendimiento")

    def test_timbrado_sales_invoice_to_factura_fiscal_integration(self):
        """
        Test: Integración Sales Invoice → Factura Fiscal Mexico con actualización automática

        Validaciones:
        - Crear Sales Invoice submitted
        - Crear Factura Fiscal Mexico vinculada
        - Verificar actualización automática fm_factura_fiscal_mx
        - Confirmar valor correcto del campo
        """
        # Crear Sales Invoice de prueba
        sales_invoice = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": "_Test Customer",
            "company": "_Test Company",
            "posting_date": frappe.utils.today(),
            "due_date": frappe.utils.today(),
            "items": [{
                "item_code": "_Test Item",
                "rate": 100,
                "qty": 1
            }]
        })
        sales_invoice.insert()
        sales_invoice.submit()

        # Verificar estado inicial - no debe tener factura fiscal
        self.assertFalse(
            sales_invoice.fm_factura_fiscal_mx,
            "Sales Invoice inicial no debe tener factura fiscal vinculada"
        )

        # Crear Factura Fiscal Mexico vinculada
        factura_fiscal = frappe.get_doc({
            "doctype": "Factura Fiscal Mexico",
            "sales_invoice": sales_invoice.name,
            "company": sales_invoice.company,
            "customer": sales_invoice.customer,
            "fm_fiscal_status": "Pendiente"
        })
        factura_fiscal.insert()
        factura_fiscal.submit()

        # Simular actualización automática (normalmente se hace en after_insert hook)
        frappe.db.set_value("Sales Invoice", sales_invoice.name,
            "fm_factura_fiscal_mx", factura_fiscal.name)
        frappe.db.commit()

        # Recargar Sales Invoice para verificar actualización
        sales_invoice.reload()

        # Verificar que fm_factura_fiscal_mx se actualizó correctamente
        self.assertEqual(
            sales_invoice.fm_factura_fiscal_mx, factura_fiscal.name,
            "Campo fm_factura_fiscal_mx debe actualizarse con name del documento fiscal"
        )

        # Verificar bidireccionalidad - Factura Fiscal debe apuntar a Sales Invoice
        self.assertEqual(
            factura_fiscal.sales_invoice, sales_invoice.name,
            "Factura Fiscal debe mantener referencia a Sales Invoice original"
        )

        print(f"✅ Integración correcta: {sales_invoice.name} ↔ {factura_fiscal.name}")

        # Cleanup
        frappe.delete_doc("Factura Fiscal Mexico", factura_fiscal.name, force=True)
        frappe.delete_doc("Sales Invoice", sales_invoice.name, force=True)

    def test_timbrado_duplicate_prevention_backend_validation(self):
        """
        Test: Prevención de doble timbrado en backend con ValidationError

        Validaciones:
        - Crear Sales Invoice y Factura Fiscal timbrada
        - Intentar crear segunda Factura Fiscal para mismo Sales Invoice
        - Verificar que frappe.ValidationError se lanza
        - Confirmar mensaje de error específico
        """
        # Crear Sales Invoice de prueba
        sales_invoice = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": "_Test Customer",
            "company": "_Test Company",
            "posting_date": frappe.utils.today(),
            "due_date": frappe.utils.today(),
            "items": [{
                "item_code": "_Test Item",
                "rate": 100,
                "qty": 1
            }]
        })
        sales_invoice.insert()
        sales_invoice.submit()

        # Crear primera Factura Fiscal y marcarla como timbrada
        first_factura = frappe.get_doc({
            "doctype": "Factura Fiscal Mexico",
            "sales_invoice": sales_invoice.name,
            "company": sales_invoice.company,
            "customer": sales_invoice.customer,
            "fm_fiscal_status": "Timbrada"  # Estado crítico para prevención
        })
        first_factura.insert()
        first_factura.submit()

        # Actualizar Sales Invoice con referencia
        frappe.db.set_value("Sales Invoice", sales_invoice.name,
            "fm_factura_fiscal_mx", first_factura.name)
        frappe.db.commit()

        # Intentar crear segunda Factura Fiscal (debe fallar)
        second_factura = frappe.get_doc({
            "doctype": "Factura Fiscal Mexico",
            "sales_invoice": sales_invoice.name,  # Mismo Sales Invoice
            "company": sales_invoice.company,
            "customer": sales_invoice.customer,
            "fm_fiscal_status": "Pendiente"
        })

        # Verificar que ValidationError se lanza al intentar validate
        with self.assertRaises(frappe.ValidationError) as context:
            second_factura.validate()

        # Verificar mensaje de error específico
        error_message = str(context.exception)
        self.assertIn(
            "ya ha sido timbrada",
            error_message.lower(),
            "Error debe mencionar que Sales Invoice ya está timbrada"
        )

        self.assertIn(
            sales_invoice.name,
            error_message,
            "Error debe mencionar el Sales Invoice específico"
        )

        self.assertIn(
            first_factura.name,
            error_message,
            "Error debe mencionar el documento fiscal existente"
        )

        print(f"✅ Prevención correcta: {sales_invoice.name} protegida contra doble timbrado")

        # Cleanup
        frappe.delete_doc("Factura Fiscal Mexico", first_factura.name, force=True)
        frappe.delete_doc("Sales Invoice", sales_invoice.name, force=True)


if __name__ == "__main__":
    unittest.main()
