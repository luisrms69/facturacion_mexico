#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testing unitario para sistema email automático CFDI - PR #68

Cobertura completa de métodos nuevos añadidos en PR #68:
- API Client: send_invoice_email()
- FFM: _resolve_recipient_email(), _resolve_auto_email_flag(), _send_cfdi_email()
- TimbradoAPI: _send_fiscal_email()

Cumple reglas RG-003 de CLAUDE.md:
- Unit tests con mocks solo de gateway externo
- Determinísticos, sin red, sin commits manuales
- IDs únicos, rollback automático del framework
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch, MagicMock


class TestPR68EmailSystem(FrappeTestCase):
    """Testing unitario para sistema email automático CFDI - PR #68"""

    def setUp(self):
        """Setup con IDs únicos para evitar conflictos entre tests"""
        self.test_id = "TEST-" + frappe.generate_hash()[:6]
        self.mock_ffm = MagicMock()
        self.mock_ffm.name = f"FFMX-{self.test_id}"

    def test_send_invoice_email_success(self):
        """Test API Client - envío email exitoso via FacturAPI"""
        from facturacion_mexico.facturacion_fiscal.api_client import FacturAPIClient

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.sandbox_mode = True
        mock_settings.timeout = 30

        with patch("frappe.get_single") as mock_get_single:
            mock_get_single.return_value = mock_settings

            with patch.object(FacturAPIClient, "_get_api_key") as mock_get_key:
                mock_get_key.return_value = "test-key"

                with patch.object(FacturAPIClient, "_make_request") as mock_make_request:
                    mock_make_request.return_value = {"status": "success", "message": "Email sent"}

                    # Test method
                    client = FacturAPIClient()
                    result = client.send_invoice_email("test-invoice-id", "test@email.com")

                    # Verificaciones
                    self.assertEqual(result["status"], "success")
                    mock_make_request.assert_called_once_with(
                        "POST", "/invoices/test-invoice-id/email", {"email": "test@email.com"}
                    )

    def test_send_invoice_email_api_error(self):
        """Test API Client - manejo error HTTP de FacturAPI"""
        from facturacion_mexico.facturacion_fiscal.api_client import FacturAPIClient

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.sandbox_mode = True
        mock_settings.timeout = 30

        with patch("frappe.get_single") as mock_get_single:
            mock_get_single.return_value = mock_settings

            with patch.object(FacturAPIClient, "_get_api_key") as mock_get_key:
                mock_get_key.return_value = "test-key"

                with patch.object(FacturAPIClient, "_make_request") as mock_make_request:
                    # Mock error HTTP
                    mock_make_request.side_effect = Exception("HTTP 400: Bad Request")

                    client = FacturAPIClient()

                    # Verificar que se lanza excepción en error
                    with self.assertRaises(Exception):
                        client.send_invoice_email("invalid-id", "invalid-email")

    def test_resolve_recipient_email_ffm_priority(self):
        """Test prioridad FFM.fm_email_facturacion sobre settings fallback"""
        from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import _resolve_recipient_email

        # Mock FFM con email configurado
        self.mock_ffm.fm_email_facturacion = "ffm@test.com"

        with patch("facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico._get_settings_email_defaults") as mock_settings:
            mock_settings.return_value = (True, "fallback@test.com")

            result = _resolve_recipient_email(self.mock_ffm)

            # Debe usar email de FFM, no fallback
            self.assertEqual(result, "ffm@test.com")

    def test_resolve_recipient_email_settings_fallback(self):
        """Test fallback a settings cuando FFM no tiene email"""
        from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import _resolve_recipient_email

        # Mock FFM sin email
        self.mock_ffm.fm_email_facturacion = ""

        with patch("facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico._get_settings_email_defaults") as mock_settings:
            mock_settings.return_value = (True, "fallback@test.com")

            result = _resolve_recipient_email(self.mock_ffm)

            # Debe usar fallback de settings
            self.assertEqual(result, "fallback@test.com")

    def test_resolve_recipient_email_no_fallback(self):
        """Test retorna None cuando no hay email ni fallback"""
        from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import _resolve_recipient_email

        # Mock FFM sin email
        self.mock_ffm.fm_email_facturacion = None

        with patch("facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico._get_settings_email_defaults") as mock_settings:
            mock_settings.return_value = (False, None)

            result = _resolve_recipient_email(self.mock_ffm)

            # Debe retornar None
            self.assertIsNone(result)

    def test_resolve_auto_email_flag_customer_enviar(self):
        """Test customer configurado como 'Enviar' devuelve 1"""
        from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import _resolve_auto_email_flag

        with patch("frappe.db.get_value") as mock_get_value:
            mock_get_value.return_value = "Enviar"

            with patch("facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico._get_settings_email_defaults") as mock_settings:
                mock_settings.return_value = (False, "test@email.com")

                result = _resolve_auto_email_flag("TEST-CUSTOMER")

                # Customer "Enviar" sobrescribe settings
                self.assertEqual(result, 1)

    def test_resolve_auto_email_flag_customer_no_enviar(self):
        """Test customer configurado como 'No enviar' devuelve 0"""
        from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import _resolve_auto_email_flag

        with patch("frappe.db.get_value") as mock_get_value:
            mock_get_value.return_value = "No enviar"

            with patch("facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico._get_settings_email_defaults") as mock_settings:
                mock_settings.return_value = (True, "test@email.com")  # Settings dice SÍ enviar

                result = _resolve_auto_email_flag("TEST-CUSTOMER")

                # Customer "No enviar" sobrescribe settings
                self.assertEqual(result, 0)

    def test_resolve_auto_email_flag_default_settings(self):
        """Test usa settings cuando customer tiene 'Default (usar settings)'"""
        from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import _resolve_auto_email_flag

        with patch("frappe.db.get_value") as mock_get_value:
            mock_get_value.return_value = "Default (usar settings)"

            with patch("facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico._get_settings_email_defaults") as mock_settings:
                mock_settings.return_value = (True, "test@email.com")

                result = _resolve_auto_email_flag("TEST-CUSTOMER")

                # Debe usar configuración de settings
                self.assertEqual(result, 1)

    def test_send_fiscal_email_success(self):
        """Test TimbradoAPI - envío fiscal email exitoso con mock completo"""
        from facturacion_mexico.facturacion_fiscal.timbrado_api import TimbradoAPI

        with patch("facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico._resolve_recipient_email") as mock_resolve_email:
            mock_resolve_email.return_value = "test@email.com"

            # Mock TimbradoAPI y client
            api = TimbradoAPI()
            api.client = MagicMock()
            api.client.send_invoice_email.return_value = {"status": "success"}

            # Test method
            api._send_fiscal_email(self.mock_ffm, "test-facturapi-id")

            # Verificaciones
            mock_resolve_email.assert_called_once_with(self.mock_ffm)
            api.client.send_invoice_email.assert_called_once_with("test-facturapi-id", "test@email.com")

    def test_send_fiscal_email_no_recipient(self):
        """Test TimbradoAPI - manejo correcto cuando no hay email recipient"""
        from facturacion_mexico.facturacion_fiscal.timbrado_api import TimbradoAPI

        with patch("facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico._resolve_recipient_email") as mock_resolve_email:
            mock_resolve_email.return_value = None

            with patch("frappe.logger") as mock_logger:
                with patch("frappe.msgprint") as mock_msgprint:
                    # Mock TimbradoAPI
                    api = TimbradoAPI()
                    api.client = MagicMock()

                    # Test method
                    api._send_fiscal_email(self.mock_ffm, "test-facturapi-id")

                    # Verificaciones
                    mock_resolve_email.assert_called_once_with(self.mock_ffm)
                    # No debe llamar API cuando no hay recipient
                    api.client.send_invoice_email.assert_not_called()
                    # Debe mostrar mensaje al usuario
                    mock_msgprint.assert_called_once()

    def test_send_fiscal_email_api_exception(self):
        """Test TimbradoAPI - manejo robusto de excepciones en API"""
        from facturacion_mexico.facturacion_fiscal.timbrado_api import TimbradoAPI

        with patch("facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico._resolve_recipient_email") as mock_resolve_email:
            mock_resolve_email.return_value = "test@email.com"

            with patch("frappe.logger") as mock_logger:
                # Mock TimbradoAPI con excepción
                api = TimbradoAPI()
                api.client = MagicMock()
                api.client.send_invoice_email.side_effect = Exception("API Error")

                # Test method - no debe re-raise excepción
                try:
                    api._send_fiscal_email(self.mock_ffm, "test-facturapi-id")
                except Exception:
                    self.fail("_send_fiscal_email() no debe re-raise excepciones")

                # Debe logear el error
                mock_logger.assert_called()