import unittest

import frappe

from facturacion_mexico.tests.test_base import FacturacionMexicoTestCase

# Evitar errores de dependencias durante make_test_records siguiendo patrón condominium_management
test_ignore = ["Sales Invoice", "Customer", "Item", "Uso CFDI SAT"]


class TestFacturacionMexicoSettings(FacturacionMexicoTestCase):
	"""Tests para Facturacion Mexico Settings."""

	def test_settings_creation(self):
		"""Test creación de configuración básica."""
		settings = frappe.get_doc("Facturacion Mexico Settings", "Facturacion Mexico Settings")
		self.assertIsNotNone(settings)
		self.assertTrue(settings.sandbox_mode)
		self.assertEqual(settings.timeout, 30)

	def test_required_fields_validation(self):
		"""Test validación de campos requeridos."""
		settings = frappe.new_doc("Facturacion Mexico Settings")

		# Test sin RFC emisor (debe fallar por falta de API key)
		with self.assertRaises(frappe.ValidationError):
			settings.save()

		# Test con RFC emisor pero sin lugar expedición (debe fallar por falta de API key)
		settings.rfc_emisor = "ABC123456789"
		with self.assertRaises(frappe.ValidationError):
			settings.save()

		# Test con RFC emisor y lugar expedición pero sin API key (debe fallar)
		settings.lugar_expedicion = "01000"
		with self.assertRaises(frappe.ValidationError):
			settings.save()

		# Test con todos los campos requeridos incluyendo API key
		settings.test_api_key = "test_api_key_dummy_for_testing"
		settings.save()  # No debe fallar

	def test_api_key_fields_exist(self):
		"""Test que existen campos para API keys."""
		settings = frappe.get_doc("Facturacion Mexico Settings", "Facturacion Mexico Settings")

		# Verificar que los campos existen en el meta
		field_names = [field.fieldname for field in settings.meta.fields]
		self.assertIn("api_key", field_names)
		self.assertIn("test_api_key", field_names)
		self.assertIn("sandbox_mode", field_names)

	def test_default_values(self):
		"""Test valores por defecto de configuración."""
		settings = frappe.get_doc("Facturacion Mexico Settings", "Facturacion Mexico Settings")
		self.assertTrue(settings.auto_generate_ereceipts)
		self.assertFalse(settings.send_email_default)
		self.assertTrue(settings.download_files_default)


if __name__ == "__main__":
	unittest.main()
