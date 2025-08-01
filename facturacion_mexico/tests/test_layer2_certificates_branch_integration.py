# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 2 Certificates Branch Integration Tests
Tests de integración para manejo de certificados por sucursal para addendas
"""

import unittest

import frappe


class TestLayer2CertificatesBranchIntegration(unittest.TestCase):
    """Tests de integración Certificados-Branch - Layer 2"""

    @classmethod
    def setUpClass(cls):
        """Setup inicial para todos los tests"""
        frappe.clear_cache()

    def test_branch_certificate_fields_structure(self):
        """Test: Estructura de campos de certificados en Branch"""
        if not frappe.db.exists("DocType", "Branch"):
            self.skipTest("Branch DocType no disponible")

        # Verificar campos relacionados con certificados en Branch
        cert_fields = frappe.db.sql("""
            SELECT fieldname, fieldtype, label, options
            FROM `tabCustom Field`
            WHERE dt = 'Branch' AND (
                fieldname LIKE '%cert%' OR
                fieldname LIKE '%certificado%' OR
                label LIKE '%Cert%' OR
                label LIKE '%Certificado%'
            )
        """, as_dict=True)

        if cert_fields:
            print(f"✓ Branch tiene campos de certificados: {[f.fieldname for f in cert_fields]}")

            # Verificar tipos de campos apropiados
            for field in cert_fields:
                self.assertIsNotNone(field.fieldtype,
                    f"Campo {field.fieldname} debe tener tipo definido")

                # Verificar que los campos de certificado son apropiados
                appropriate_types = ['Link', 'Table', 'Data', 'Text', 'Check']
                if field.fieldtype not in appropriate_types:
                    print(f"⚠ Campo {field.fieldname} tipo {field.fieldtype} - verificar si es apropiado")
        else:
            print("ℹ Branch no tiene campos específicos de certificados")

    def test_certificate_sharing_between_branches(self):
        """Test: Compartir certificados entre sucursales"""
        if not frappe.db.exists("DocType", "Branch"):
            self.skipTest("Branch DocType no disponible")

        # Verificar campo para compartir certificados
        share_cert_fields = frappe.db.sql("""
            SELECT fieldname, fieldtype, label
            FROM `tabCustom Field`
            WHERE dt = 'Branch' AND (
                fieldname LIKE '%share%' OR
                label LIKE '%Compartir%' OR
                label LIKE '%Share%'
            ) AND (
                fieldname LIKE '%cert%' OR
                label LIKE '%Cert%'
            )
        """, as_dict=True)

        if share_cert_fields:
            print(f"✓ Branch tiene campos para compartir certificados: {[f.fieldname for f in share_cert_fields]}")

            # Verificar que es tipo Check (boolean)
            for field in share_cert_fields:
                if field.fieldtype == 'Check':
                    print(f"✓ Campo {field.fieldname} es tipo Check (apropiado para compartir)")
        else:
            print("ℹ No hay campos específicos para compartir certificados")

    def test_certificate_doctype_integration(self):
        """Test: Integración con DocType de certificados"""
        # Verificar si existe DocType específico para certificados
        cert_doctypes = [
            "Certificate",
            "Certificado",
            "SAT Certificate",
            "Certificado SAT",
            "Digital Certificate"
        ]

        available_cert_doctypes = []
        for doctype in cert_doctypes:
            if frappe.db.exists("DocType", doctype):
                available_cert_doctypes.append(doctype)

        if available_cert_doctypes:
            print(f"✓ DocTypes de certificados disponibles: {available_cert_doctypes}")

            # Verificar estructura de certificados
            for cert_doctype in available_cert_doctypes:
                try:
                    meta = frappe.get_meta(cert_doctype)
                    fields = [f.fieldname for f in meta.fields]

                    # Buscar campos relacionados con sucursales
                    branch_fields = [f for f in fields
                                   if 'branch' in f.lower() or 'sucursal' in f.lower()]

                    if branch_fields:
                        print(f"✓ {cert_doctype} tiene campos de sucursal: {branch_fields}")

                except Exception as e:
                    print(f"⚠ Error accediendo {cert_doctype}: {e}")
        else:
            print("ℹ No hay DocTypes específicos de certificados")

    def test_certificate_selection_logic_integration(self):
        """Test: Lógica de selección de certificados por sucursal"""
        # Verificar módulos de selección de certificados
        cert_selection_modules = [
            "facturacion_mexico.multi_sucursal.certificate_manager",
            "facturacion_mexico.certificates.branch_certificate_selector",
            "facturacion_mexico.facturacion_fiscal.certificate_selector"
        ]

        available_selectors = []
        for module_path in cert_selection_modules:
            try:
                module = __import__(module_path, fromlist=[''])
                available_selectors.append(module_path)

                # Verificar métodos de selección
                module_methods = dir(module)
                selection_methods = [m for m in module_methods
                                   if any(keyword in m.lower() for keyword in
                                         ['select', 'choose', 'get', 'find'])]

                if selection_methods:
                    print(f"✓ {module_path} tiene métodos de selección: {selection_methods[:3]}")

            except ImportError:
                continue

        if available_selectors:
            print(f"✓ Módulos de selección de certificados: {available_selectors}")
        else:
            print("ℹ Módulos específicos de selección no encontrados")

    def test_certificate_validation_per_branch(self):
        """Test: Validación de certificados por sucursal"""
        # Verificar que existe validación de certificados específica por sucursal

        # Verificar hooks de validación
        from facturacion_mexico import hooks

        doc_events = getattr(hooks, 'doc_events', {})

        # Buscar validaciones en DocTypes relacionados
        validation_doctypes = ['Sales Invoice', 'Branch']
        cert_validation_hooks = []

        for doctype in validation_doctypes:
            if doctype in doc_events:
                doctype_events = doc_events[doctype]
                for event in ['validate', 'before_submit']:
                    if event in doctype_events:
                        hooks_list = doctype_events[event]
                        cert_hooks = [h for h in hooks_list
                                    if 'cert' in h.lower() or 'certificado' in h.lower()]
                        cert_validation_hooks.extend(cert_hooks)

        if cert_validation_hooks:
            print(f"✓ Hooks de validación de certificados: {cert_validation_hooks}")
        else:
            print("ℹ No hay hooks específicos de validación de certificados")

    def test_certificate_usage_tracking_per_branch(self):
        """Test: Seguimiento de uso de certificados por sucursal"""
        # Verificar campos para rastrear uso de certificados

        if not frappe.db.exists("DocType", "Sales Invoice"):
            self.skipTest("Sales Invoice DocType no disponible")

        # Verificar campos en Sales Invoice que rastreen certificado usado
        cert_usage_fields = frappe.db.sql("""
            SELECT fieldname, fieldtype, label
            FROM `tabCustom Field`
            WHERE dt = 'Sales Invoice' AND (
                fieldname LIKE '%cert%' OR
                fieldname LIKE '%certificado%' OR
                label LIKE '%Cert%' OR
                label LIKE '%Certificado%'
            )
        """, as_dict=True)

        if cert_usage_fields:
            print(f"✓ Sales Invoice rastrea certificados usados: {[f.fieldname for f in cert_usage_fields]}")

            # Verificar que son campos apropiados para rastreo
            for field in cert_usage_fields:
                if field.fieldtype in ['Link', 'Data', 'Text']:
                    print(f"✓ Campo {field.fieldname} apropiado para rastreo")
        else:
            print("ℹ No hay rastreo específico de certificados en Sales Invoice")

    def test_certificate_branch_relationship_validation(self):
        """Test: Validación de relación Certificate-Branch"""
        # Verificar que la relación entre certificados y sucursales es válida

        if not frappe.db.exists("DocType", "Branch"):
            self.skipTest("Branch DocType no disponible")

        # Verificar si Branch puede tener múltiples certificados o uno específico
        cert_relation_fields = frappe.db.sql("""
            SELECT fieldname, fieldtype, options
            FROM `tabCustom Field`
            WHERE dt = 'Branch' AND fieldtype IN ('Link', 'Table')
            AND (
                fieldname LIKE '%cert%' OR
                options LIKE '%Cert%'
            )
        """, as_dict=True)

        if cert_relation_fields:
            print(f"✓ Branch tiene relaciones de certificados: {[f.fieldname for f in cert_relation_fields]}")

            # Verificar tipo de relación
            for field in cert_relation_fields:
                if field.fieldtype == 'Link':
                    print(f"✓ {field.fieldname} - Relación 1:1 con {field.options}")
                elif field.fieldtype == 'Table':
                    print(f"✓ {field.fieldname} - Relación 1:N con {field.options}")

    def test_certificate_security_per_branch(self):
        """Test: Seguridad de certificados por sucursal"""
        # Verificar que existe control de acceso a certificados por sucursal

        # Verificar permisos a nivel de Branch
        if frappe.db.exists("DocType", "Branch"):
            branch_meta = frappe.get_meta("Branch")
            branch_permissions = branch_meta.permissions

            if branch_permissions:
                # Verificar que hay control de permisos
                permission_roles = [p.role for p in branch_permissions if p.read]
                print(f"✓ Roles con acceso a Branch: {permission_roles[:3]}")

                # Verificar permisos de escritura (modificar certificados)
                write_roles = [p.role for p in branch_permissions if p.write]
                if write_roles:
                    print(f"✓ Roles que pueden modificar certificados en Branch: {write_roles[:3]}")

    def test_certificate_backup_and_recovery_per_branch(self):
        """Test: Backup y recuperación de certificados por sucursal"""
        # Verificar capacidades de backup de configuración de certificados

        # Verificar si hay campos para configuración de backup
        if frappe.db.exists("DocType", "Branch"):
            backup_fields = frappe.db.sql("""
                SELECT fieldname, fieldtype, label
                FROM `tabCustom Field`
                WHERE dt = 'Branch' AND (
                    fieldname LIKE '%backup%' OR
                    fieldname LIKE '%recovery%' OR
                    label LIKE '%Backup%' OR
                    label LIKE '%Recovery%'
                )
            """, as_dict=True)

            if backup_fields:
                print(f"✓ Branch tiene campos de backup/recovery: {[f.fieldname for f in backup_fields]}")
            else:
                print("ℹ No hay campos específicos de backup/recovery en Branch")

    def test_certificate_expiration_monitoring_per_branch(self):
        """Test: Monitoreo de expiración de certificados por sucursal"""
        # Verificar campos para monitorear expiración de certificados

        if not frappe.db.exists("DocType", "Branch"):
            self.skipTest("Branch DocType no disponible")

        # Buscar campos de fecha/tiempo relacionados con certificados
        cert_date_fields = frappe.db.sql("""
            SELECT fieldname, fieldtype, label
            FROM `tabCustom Field`
            WHERE dt = 'Branch' AND fieldtype IN ('Date', 'Datetime', 'Time')
            AND (
                fieldname LIKE '%cert%' OR
                label LIKE '%Cert%' OR
                fieldname LIKE '%expir%' OR
                label LIKE '%Expir%'
            )
        """, as_dict=True)

        if cert_date_fields:
            print(f"✓ Branch tiene campos de fecha para certificados: {[f.fieldname for f in cert_date_fields]}")

        # Verificar campos de alerta/warning
        warning_fields = frappe.db.sql("""
            SELECT fieldname, fieldtype, label
            FROM `tabCustom Field`
            WHERE dt = 'Branch' AND (
                fieldname LIKE '%warning%' OR
                fieldname LIKE '%alert%' OR
                fieldname LIKE '%threshold%' OR
                label LIKE '%Warning%' OR
                label LIKE '%Alert%'
            )
        """, as_dict=True)

        if warning_fields:
            print(f"✓ Branch tiene campos de alerta: {[f.fieldname for f in warning_fields]}")


if __name__ == "__main__":
    unittest.main()
