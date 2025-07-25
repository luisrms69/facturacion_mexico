"""
Tests para Draft Management System - Issue #27
Layer 1 (Unit), Layer 2 (Integration), Layer 3 (End-to-End)
"""

import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.test_runner import FrappeTestCase
from frappe.utils import add_days, now

from facturacion_mexico.draft_management.api import (
    approve_and_invoice_draft,
    cancel_draft,
    create_draft_invoice,
    get_draft_preview,
)


class TestDraftManagement(FrappeTestCase):
    """Tests Layer 1 - Unit Tests para Draft Management"""

    def setUp(self):
        """Configuración inicial para tests"""

        # Crear Sales Invoice de prueba simplificado
        self.test_invoice_name = "TEST-DRAFT-001"

        # Simular que existe el documento
        frappe.db.sql("""
            INSERT INTO `tabSales Invoice`
            (name, customer, grand_total, fm_create_as_draft, docstatus, creation, modified)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE modified = %s
        """, (
            self.test_invoice_name, "Test Customer", 1000, 1, 0, now(), now(), now()
        ))
        frappe.db.commit()

        # Crear objeto mock para self.test_invoice
        self.test_invoice = frappe._dict()
        self.test_invoice.name = self.test_invoice_name

    def test_create_draft_invoice_success(self):
        """Test Layer 1: Crear borrador exitoso"""
        with patch('facturacion_mexico.draft_management.api.send_to_factorapi') as mock_api:
            # Mock respuesta exitosa de FacturAPI
            mock_api.return_value = {
                "success": True,
                "draft_id": "draft_test123",
                "preview_url": "https://test.factorapi.io/preview/draft_test123"
            }

            # Ejecutar creación de borrador
            result = create_draft_invoice(self.test_invoice.name)

            # Verificar resultado
            self.assertTrue(result["success"])
            self.assertEqual(result["draft_id"], "draft_test123")
            self.assertIn("preview_url", result)

            # Verificar campos actualizados en BD
            updated_invoice = frappe.get_doc("Sales Invoice", self.test_invoice.name)
            self.assertEqual(updated_invoice.fm_draft_status, "Borrador")
            self.assertEqual(updated_invoice.fm_factorapi_draft_id, "draft_test123")
            self.assertIsNotNone(updated_invoice.fm_draft_created_date)

    def test_create_draft_invoice_not_marked_as_draft(self):
        """Test Layer 1: Error cuando factura no está marcada como borrador"""
        # Remover marca de borrador
        frappe.db.set_value("Sales Invoice", self.test_invoice.name, {
            "fm_create_as_draft": 0
        })

        result = create_draft_invoice(self.test_invoice.name)

        self.assertFalse(result["success"])
        self.assertIn("no está marcada para crear como borrador", result["message"])

    def test_create_draft_invoice_already_exists(self):
        """Test Layer 1: Error cuando borrador ya existe"""
        # Marcar como borrador existente
        frappe.db.set_value("Sales Invoice", self.test_invoice.name, {
            "fm_draft_status": "Borrador",
            "fm_factorapi_draft_id": "existing_draft_123"
        })

        result = create_draft_invoice(self.test_invoice.name)

        self.assertFalse(result["success"])
        self.assertIn("ya existe como borrador", result["message"])
        self.assertEqual(result["draft_id"], "existing_draft_123")

    def test_approve_and_invoice_draft_success(self):
        """Test Layer 1: Aprobar borrador exitoso"""
        # Configurar borrador existente
        frappe.db.set_value("Sales Invoice", self.test_invoice.name, {
            "fm_draft_status": "Borrador",
            "fm_factorapi_draft_id": "draft_test123"
        })

        with patch('facturacion_mexico.draft_management.api.convert_draft_to_invoice') as mock_convert:
            # Mock conversión exitosa
            mock_convert.return_value = {
                "success": True,
                "cfdi_uuid": "12345678-1234-1234-1234-123456789abc",
                "cfdi_xml": "<cfdi:Comprobante>...</cfdi:Comprobante>",
                "pdf_url": "https://test.factorapi.io/pdf/12345.pdf"
            }

            result = approve_and_invoice_draft(self.test_invoice.name, "test@user.com")

            self.assertTrue(result["success"])
            self.assertIn("cfdi_uuid", result)
            self.assertIn("pdf_url", result)

            # Verificar estado final
            updated_invoice = frappe.get_doc("Sales Invoice", self.test_invoice.name)
            self.assertEqual(updated_invoice.fm_draft_status, "Timbrado")
            self.assertEqual(updated_invoice.fm_draft_approved_by, "test@user.com")

    def test_approve_draft_not_in_draft_status(self):
        """Test Layer 1: Error aprobando factura que no está en borrador"""
        # Configurar en estado no-borrador
        frappe.db.set_value("Sales Invoice", self.test_invoice.name, {
            "fm_draft_status": "Timbrado"
        })

        result = approve_and_invoice_draft(self.test_invoice.name)

        self.assertFalse(result["success"])
        self.assertIn("no está en estado borrador", result["message"])

    def test_cancel_draft_success(self):
        """Test Layer 1: Cancelar borrador exitoso"""
        # Configurar borrador existente
        frappe.db.set_value("Sales Invoice", self.test_invoice.name, {
            "fm_draft_status": "Borrador",
            "fm_factorapi_draft_id": "draft_test123",
            "fm_draft_created_date": now()
        })

        with patch('facturacion_mexico.draft_management.api.cancel_draft_in_factorapi') as mock_cancel:
            mock_cancel.return_value = {"success": True}

            result = cancel_draft(self.test_invoice.name)

            self.assertTrue(result["success"])

            # Verificar campos limpiados
            updated_invoice = frappe.get_doc("Sales Invoice", self.test_invoice.name)
            self.assertEqual(updated_invoice.fm_draft_status, "")
            self.assertEqual(updated_invoice.fm_factorapi_draft_id, "")
            self.assertEqual(updated_invoice.fm_create_as_draft, 0)

    def test_get_draft_preview_success(self):
        """Test Layer 1: Obtener preview de borrador"""
        # Configurar borrador existente
        frappe.db.set_value("Sales Invoice", self.test_invoice.name, {
            "fm_draft_status": "Borrador",
            "fm_factorapi_draft_id": "draft_test123",
            "fm_draft_created_date": now()
        })

        with patch('facturacion_mexico.draft_management.api.get_draft_preview_from_factorapi') as mock_preview:
            mock_preview.return_value = {
                "success": True,
                "xml": "<cfdi:Comprobante>preview</cfdi:Comprobante>",
                "pdf_url": "https://test.factorapi.io/preview/draft_test123.pdf"
            }

            result = get_draft_preview(self.test_invoice.name)

            self.assertTrue(result["success"])
            self.assertIn("preview_xml", result)
            self.assertIn("preview_pdf_url", result)
            self.assertIn("draft_data", result)
            self.assertEqual(result["draft_data"]["draft_id"], "draft_test123")


class TestDraftManagementIntegration(FrappeTestCase):
    """Tests Layer 2 - Integration Tests"""

    def setUp(self):
        """Configuración para integration tests"""

        # Crear factura de prueba simplificada
        self.test_invoice_name = "TEST-INTEGRATION-001"
        frappe.db.sql("""
            INSERT INTO `tabSales Invoice`
            (name, customer, grand_total, fm_create_as_draft, docstatus, creation, modified)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE modified = %s
        """, (
            self.test_invoice_name, "Integration Customer", 2000, 1, 0, now(), now(), now()
        ))
        frappe.db.commit()

        self.test_invoice = frappe._dict()
        self.test_invoice.name = self.test_invoice_name

    def test_draft_workflow_complete_integration(self):
        """Test Layer 2: Flujo completo borrador -> aprobación -> timbrado"""
        # Paso 1: Marcar como borrador y crear
        frappe.db.set_value("Sales Invoice", self.test_invoice.name, {
            "fm_create_as_draft": 1
        })

        with patch('facturacion_mexico.draft_management.api.send_to_factorapi') as mock_create:
            mock_create.return_value = {
                "success": True,
                "draft_id": "integration_draft_123",
                "preview_url": "https://test.factorapi.io/preview/integration_draft_123"
            }

            # Crear borrador
            create_result = create_draft_invoice(self.test_invoice.name)
            self.assertTrue(create_result["success"])

        # Paso 2: Obtener preview
        with patch('facturacion_mexico.draft_management.api.get_draft_preview_from_factorapi') as mock_preview:
            mock_preview.return_value = {
                "success": True,
                "xml": "<cfdi:Comprobante>integration test</cfdi:Comprobante>",
                "pdf_url": "https://test.factorapi.io/preview/integration_draft_123.pdf"
            }

            preview_result = get_draft_preview(self.test_invoice.name)
            self.assertTrue(preview_result["success"])

        # Paso 3: Aprobar y timbrar
        with patch('facturacion_mexico.draft_management.api.convert_draft_to_invoice') as mock_approve:
            mock_approve.return_value = {
                "success": True,
                "cfdi_uuid": "integration-uuid-12345",
                "cfdi_xml": "<cfdi:Comprobante>final invoice</cfdi:Comprobante>",
                "pdf_url": "https://test.factorapi.io/pdf/integration_final.pdf"
            }

            approve_result = approve_and_invoice_draft(self.test_invoice.name, "integration@test.com")
            self.assertTrue(approve_result["success"])

        # Verificar estado final completo
        final_invoice = frappe.get_doc("Sales Invoice", self.test_invoice.name)
        self.assertEqual(final_invoice.fm_draft_status, "Timbrado")
        self.assertEqual(final_invoice.fm_draft_approved_by, "integration@test.com")
        self.assertEqual(final_invoice.fm_cfdi_uuid, "integration-uuid-12345")

    def test_error_handling_and_rollback(self):
        """Test Layer 2: Manejo de errores y rollback"""
        # Configurar borrador
        frappe.db.set_value("Sales Invoice", self.test_invoice.name, {
            "fm_create_as_draft": 1,
            "fm_draft_status": "Borrador",
            "fm_factorapi_draft_id": "error_test_draft"
        })

        # Simular error en aprobación
        with patch('facturacion_mexico.draft_management.api.convert_draft_to_invoice') as mock_convert:
            mock_convert.return_value = {
                "success": False,
                "message": "Error simulado de FacturAPI"
            }

            result = approve_and_invoice_draft(self.test_invoice.name)
            self.assertFalse(result["success"])
            self.assertIn("Error simulado de FacturAPI", result["message"])

            # Verificar rollback - debe volver a estado borrador
            rolled_back_invoice = frappe.get_doc("Sales Invoice", self.test_invoice.name)
            self.assertEqual(rolled_back_invoice.fm_draft_status, "Borrador")


class TestDraftManagementEndToEnd(FrappeTestCase):
    """Tests Layer 3 - End-to-End Workflow Tests"""

    def setUp(self):
        """Configuración para E2E tests"""

    def test_complete_draft_approval_workflow(self):
        """Test Layer 3: Flujo completo end-to-end con múltiples facturas"""
        # Crear múltiples facturas de prueba
        invoices = []
        for i in range(3):
            invoice_name = f"TEST-E2E-{i+1:03d}"
            frappe.db.sql("""
                INSERT INTO `tabSales Invoice`
                (name, customer, grand_total, fm_create_as_draft, docstatus, creation, modified)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE modified = %s
            """, (
                invoice_name, f"Draft Customer {i+1}", 1000*(i+1), 1, 0, now(), now(), now()
            ))

            invoice = frappe._dict()
            invoice.name = invoice_name
            invoices.append(invoice)
        frappe.db.commit()

        # Mock todas las integraciones FacturAPI
        with patch('facturacion_mexico.draft_management.api.send_to_factorapi') as mock_create, \
             patch('facturacion_mexico.draft_management.api.convert_draft_to_invoice') as mock_convert, \
             patch('facturacion_mexico.draft_management.api.get_draft_preview_from_factorapi') as mock_preview:

            # Configurar mocks
            mock_create.side_effect = [
                {"success": True, "draft_id": f"e2e_draft_{i}", "preview_url": f"https://test.com/preview/{i}"}
                for i in range(3)
            ]
            mock_convert.side_effect = [
                {"success": True, "cfdi_uuid": f"e2e-uuid-{i}", "cfdi_xml": f"<xml>invoice {i}</xml>"}
                for i in range(3)
            ]
            mock_preview.return_value = {"success": True, "xml": "<preview>", "pdf_url": "https://test.com/preview.pdf"}

            # Ejecutar flujo completo para cada factura
            results = []
            for i, invoice in enumerate(invoices):
                # Crear borrador
                create_result = create_draft_invoice(invoice.name)
                self.assertTrue(create_result["success"], f"Error creando borrador {i}")

                # Preview
                preview_result = get_draft_preview(invoice.name)
                self.assertTrue(preview_result["success"], f"Error obteniendo preview {i}")

                # Aprobar (solo las primeras 2)
                if i < 2:
                    approve_result = approve_and_invoice_draft(invoice.name, f"approver_{i}@test.com")
                    self.assertTrue(approve_result["success"], f"Error aprobando factura {i}")
                    results.append("approved")
                else:
                    # Cancelar la tercera
                    with patch('facturacion_mexico.draft_management.api.cancel_draft_in_factorapi') as mock_cancel:
                        mock_cancel.return_value = {"success": True}
                        cancel_result = cancel_draft(invoice.name)
                        self.assertTrue(cancel_result["success"], f"Error cancelando factura {i}")
                        results.append("cancelled")

            # Verificar estados finales
            for i, invoice in enumerate(invoices):
                final_invoice = frappe.get_doc("Sales Invoice", invoice.name)
                if i < 2:
                    self.assertEqual(final_invoice.fm_draft_status, "Timbrado")
                    self.assertEqual(final_invoice.fm_cfdi_uuid, f"e2e-uuid-{i}")
                else:
                    self.assertEqual(final_invoice.fm_draft_status, "")
                    self.assertEqual(final_invoice.fm_create_as_draft, 0)

            # Verificar métricas del flujo
            self.assertEqual(results.count("approved"), 2)
            self.assertEqual(results.count("cancelled"), 1)

    def test_draft_workflow_with_addendas_integration(self):
        """Test Layer 3: Integración borradores con sistema de addendas"""
        # Crear factura que requiere addenda
        invoice_name = "TEST-ADDENDA-001"
        frappe.db.sql("""
            INSERT INTO `tabSales Invoice`
            (name, customer, grand_total, fm_create_as_draft, fm_addenda_required,
             fm_addenda_type, docstatus, creation, modified)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE modified = %s
        """, (
            invoice_name, "Addenda Customer", 3000, 1, 1, "Test Addenda Type",
            0, now(), now(), now()
        ))
        frappe.db.commit()

        invoice = frappe._dict()
        invoice.name = invoice_name
        invoice.customer = "Addenda Customer"

        with patch('facturacion_mexico.draft_management.api.send_to_factorapi') as mock_create, \
             patch('facturacion_mexico.draft_management.api.convert_draft_to_invoice') as mock_convert:

            mock_create.return_value = {
                "success": True,
                "draft_id": "addenda_draft_123",
                "preview_url": "https://test.com/addenda_preview"
            }
            mock_convert.return_value = {
                "success": True,
                "cfdi_uuid": "addenda-uuid-123",
                "cfdi_xml": "<cfdi:Comprobante><cfdi:Addenda>test addenda</cfdi:Addenda></cfdi:Comprobante>"
            }

            # Flujo completo con addenda
            create_result = create_draft_invoice(invoice.name)
            self.assertTrue(create_result["success"])

            approve_result = approve_and_invoice_draft(invoice.name)
            self.assertTrue(approve_result["success"])

            # Verificar que tanto borrador como addenda funcionaron
            final_invoice = frappe.get_doc("Sales Invoice", invoice.name)
            self.assertEqual(final_invoice.fm_draft_status, "Timbrado")
            self.assertEqual(final_invoice.fm_addenda_required, 1)
            self.assertIn("Addenda", final_invoice.fm_cfdi_xml)


# Utility functions para tests

def create_test_draft_scenarios():
    """Crear escenarios diversos para testing"""
    scenarios = [
        {"name": "Simple Draft", "items": 1, "total": 1000},
        {"name": "Multi-item Draft", "items": 5, "total": 5000},
        {"name": "High Value Draft", "items": 2, "total": 50000},
    ]
    return scenarios


if __name__ == "__main__":
    unittest.main()
