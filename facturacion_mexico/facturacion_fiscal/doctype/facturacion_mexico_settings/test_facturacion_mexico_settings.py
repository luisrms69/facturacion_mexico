import unittest
from typing import ClassVar

import frappe

from facturacion_mexico.tests.test_base import FacturacionMexicoTestGranular

# Evitar errores de dependencias durante make_test_records siguiendo patrón condominium_management
test_ignore = ["Sales Invoice", "Customer", "Item", "Uso CFDI SAT"]


class TestFacturacionMexicoSettingsGranular(FacturacionMexicoTestGranular):
	"""Tests granulares para Facturacion Mexico Settings."""

	DOCTYPE_NAME = "Facturacion Mexico Settings"
	REQUIRED_FIELDS: ClassVar[dict] = {
		"doctype": "Facturacion Mexico Settings",
		"name": "Facturacion Mexico Settings",
		"rfc_emisor": "ABC123456789",
		"lugar_expedicion": "01000",
	}
	MOCK_HOOKS = True
	TEST_MINIMAL_ONLY = False

	def test_rfc_validation_isolated(self):
		"""LAYER 1: Test RFC validation without DB operations."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)

		# Test valid RFC
		doc.rfc_emisor = "ABC123456789"
		doc.validate_rfc_format()
		self.assertEqual(doc.rfc_emisor, "ABC123456789")

		# Test RFC with lowercase (should convert to uppercase)
		doc.rfc_emisor = "abc123456789"
		doc.validate_rfc_format()
		self.assertEqual(doc.rfc_emisor, "ABC123456789")

	def test_lugar_expedicion_validation_isolated(self):
		"""LAYER 1: Test código postal validation without DB operations."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)

		# Test valid código postal
		doc.lugar_expedicion = "01000"
		doc.validate_lugar_expedicion()
		self.assertEqual(doc.lugar_expedicion, "01000")

		# Test código postal with spaces (should strip)
		doc.lugar_expedicion = " 01000 "
		doc.validate_lugar_expedicion()
		self.assertEqual(doc.lugar_expedicion, "01000")

	def test_api_key_validation_isolated(self):
		"""LAYER 1: Test API key validation logic."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)

		# Test with test_api_key only (should work)
		doc.test_api_key = "test_key"
		doc.sandbox_mode = 1
		try:
			doc.validate_api_keys()
			validation_passed = True
		except frappe.ValidationError:
			validation_passed = False

		self.assertTrue(validation_passed, "Should accept test_api_key in sandbox mode")

	def test_invalid_rfc_validation(self):
		"""LAYER 2: Test invalid RFC validation with expected failures."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)

		# Test RFC too short
		doc.rfc_emisor = "ABC123"
		with self.assertRaises(frappe.ValidationError):
			doc.validate_rfc_format()

		# Test RFC too long
		doc.rfc_emisor = "ABC123456789XYZ"
		with self.assertRaises(frappe.ValidationError):
			doc.validate_rfc_format()

		# Test RFC with special characters
		doc.rfc_emisor = "ABC123456-89"
		with self.assertRaises(frappe.ValidationError):
			doc.validate_rfc_format()

	def test_invalid_lugar_expedicion_validation(self):
		"""LAYER 2: Test invalid código postal validation."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)

		# Test código postal too short
		doc.lugar_expedicion = "123"
		with self.assertRaises(frappe.ValidationError):
			doc.validate_lugar_expedicion()

		# Test código postal too long
		doc.lugar_expedicion = "123456"
		with self.assertRaises(frappe.ValidationError):
			doc.validate_lugar_expedicion()

		# Test código postal with letters
		doc.lugar_expedicion = "0100A"
		with self.assertRaises(frappe.ValidationError):
			doc.validate_lugar_expedicion()

	def test_api_keys_required_validation(self):
		"""LAYER 2: Test that at least one API key is required."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)

		# Test without any API keys
		with self.assertRaises(frappe.ValidationError):
			doc.validate_api_keys()

		# Test sandbox mode without test_api_key
		doc.sandbox_mode = 1
		with self.assertRaises(frappe.ValidationError):
			doc.validate_api_keys()

	def test_settings_singleton_creation(self):
		"""LAYER 3: Test singleton creation and retrieval."""
		# Clean up any existing settings
		if frappe.db.exists("Facturacion Mexico Settings", "Facturacion Mexico Settings"):
			doc = frappe.get_doc("Facturacion Mexico Settings", "Facturacion Mexico Settings")
			doc.delete(ignore_permissions=True, force=True)

		# Test get_settings creates default if not exists
		from facturacion_mexico.facturacion_fiscal.doctype.facturacion_mexico_settings.facturacion_mexico_settings import (
			FacturacionMexicoSettings,
		)

		settings = FacturacionMexicoSettings.get_settings()
		self.assertIsNotNone(settings)
		self.assertEqual(settings.name, "Facturacion Mexico Settings")
		self.assertTrue(settings.sandbox_mode)

		# Cleanup
		settings.delete(ignore_permissions=True, force=True)

	def test_api_url_configuration(self):
		"""LAYER 3: Test API URL configuration logic."""
		doc = frappe.get_doc(self.REQUIRED_FIELDS.copy())

		# Test sandbox URL
		doc.sandbox_mode = 1
		url = doc.get_api_base_url()
		self.assertIn("facturapi.io", url)

		# Test production URL
		doc.sandbox_mode = 0
		url = doc.get_api_base_url()
		self.assertIn("facturapi.io", url)

	def test_default_values_configuration(self):
		"""LAYER 4: Test default values are properly set."""
		meta = frappe.get_meta(self.DOCTYPE_NAME)

		# Find default values in field definitions
		defaults = {}
		for field in meta.fields:
			if field.default:
				defaults[field.fieldname] = field.default

		# Verify expected defaults
		self.assertEqual(defaults.get("sandbox_mode"), "1")
		self.assertEqual(defaults.get("timeout"), "30")
		self.assertEqual(defaults.get("auto_generate_ereceipts"), "1")
		self.assertEqual(defaults.get("send_email_default"), "0")
		self.assertEqual(defaults.get("download_files_default"), "1")


if __name__ == "__main__":
	unittest.main()
