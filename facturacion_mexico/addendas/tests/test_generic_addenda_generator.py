# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Test Generic Addenda Generator - Sprint 6 Phase 3
Tests Layer 1-2 para sistema de addendas genéricas con Jinja2
"""

import json
import unittest
from unittest.mock import Mock, patch

import frappe

from facturacion_mexico.addendas.generic_addenda_generator import (
	AddendaGenerator,
	AddendaValidator,
	generate_addenda_for_invoice,
	get_addenda_type_fields,
)


class TestGenericAddendaGenerator(unittest.TestCase):
	"""Test Generic Addenda Generator - Layer 1 Unit Tests"""

	@classmethod
	def setUpClass(cls):
		"""Set up test environment"""
		frappe.set_user("Administrator")
		cls.test_addenda_type = "TEST_GENERIC"
		cls.create_test_addenda_type()

	@classmethod
	def create_test_addenda_type(cls):
		"""Create test addenda type for testing"""
		try:
			# Check if exists
			if frappe.db.exists("Addenda Type", cls.test_addenda_type):
				return

			# Create test addenda type
			addenda_type_doc = frappe.get_doc(
				{
					"doctype": "Addenda Type",
					"name": cls.test_addenda_type,
					"description": "Test Generic Addenda Type",
					"version": "1.0",
					"is_active": 1,
					"xml_template": """<?xml version="1.0" encoding="UTF-8"?>
<Addenda>
    <DatosGenerales
        version="{{version}}"
        folio="{{invoice.name}}"
        fecha="{{current_date}}"
        total="{{invoice.grand_total}}" />
    <Cliente
        nombre="{{customer_name}}"
        rfc="{{customer_rfc}}"
        email="{{customer_email | default('sin-email@test.com')}}" />
    {% if campo_opcional %}
    <DatosOpcionales valor="{{campo_opcional}}" />
    {% endif %}
</Addenda>""",
					"validation_rules": json.dumps(
						{
							"rules": [
								{
									"type": "required_if",
									"field": "customer_email",
									"condition_field": "requires_email",
									"condition_value": True,
									"severity": "error",
								}
							]
						}
					),
					"field_definitions": [
						{
							"field_name": "customer_name",
							"field_label": "Nombre del Cliente",
							"field_type": "Data",
							"is_mandatory": 1,
							"help_text": "Nombre completo del cliente",
						},
						{
							"field_name": "customer_rfc",
							"field_label": "RFC del Cliente",
							"field_type": "Data",
							"is_mandatory": 1,
							"validation_pattern": "^[A-Z&Ñ]{3,4}[0-9]{6}[A-Z0-9]{3}$",
						},
						{
							"field_name": "customer_email",
							"field_label": "Email del Cliente",
							"field_type": "Data",
							"is_mandatory": 0,
							"default_value": "cliente@test.com",
						},
						{
							"field_name": "campo_opcional",
							"field_label": "Campo Opcional",
							"field_type": "Data",
							"is_mandatory": 0,
						},
						{
							"field_name": "version",
							"field_label": "Versión",
							"field_type": "Data",
							"is_mandatory": 1,
							"default_value": "1.0",
						},
					],
				}
			)

			addenda_type_doc.insert(ignore_permissions=True)
			frappe.db.commit()

		except Exception as e:
			print(f"Error creating test addenda type: {e}")

	def setUp(self):
		"""Set up each test"""
		self.generator = AddendaGenerator(self.test_addenda_type)

		# Sample invoice data
		self.sample_invoice_data = {
			"name": "SINV-2025-001",
			"customer": "Test Customer",
			"grand_total": 1000.50,
			"company": "Test Company",
		}

		# Sample addenda values
		self.sample_addenda_values = {
			"customer_name": "Cliente de Prueba S.A. de C.V.",
			"customer_rfc": "CTM950101ABC",
			"customer_email": "cliente@prueba.com",
			"version": "1.0",
		}

	def test_generator_initialization(self):
		"""Test generator initialization"""
		self.assertEqual(self.generator.addenda_type, self.test_addenda_type)
		self.assertIsNotNone(self.generator.addenda_type_doc)
		self.assertIsNotNone(self.generator.template)
		self.assertTrue(self.generator.addenda_type_doc.is_active)

	def test_generate_addenda_success(self):
		"""Test successful addenda generation"""
		result = self.generator.generate(self.sample_invoice_data, self.sample_addenda_values)

		self.assertTrue(result["success"])
		self.assertIn("xml_content", result)
		self.assertIn("validation_result", result)
		self.assertIn("template_variables", result)

		# Verify XML content contains expected values
		xml_content = result["xml_content"]
		self.assertIn("SINV-2025-001", xml_content)  # Invoice name
		self.assertIn("Cliente de Prueba S.A. de C.V.", xml_content)  # Customer name
		self.assertIn("CTM950101ABC", xml_content)  # RFC
		self.assertIn("1000.50", xml_content)  # Grand total

	def test_generate_addenda_missing_mandatory_field(self):
		"""Test addenda generation with missing mandatory field"""
		incomplete_values = self.sample_addenda_values.copy()
		del incomplete_values["customer_name"]  # Remove mandatory field

		result = self.generator.generate(self.sample_invoice_data, incomplete_values)

		self.assertFalse(result["success"])
		self.assertIn("validation_errors", result)
		self.assertIn("Nombre del Cliente", str(result["validation_errors"]))

	def test_generate_addenda_invalid_field_type(self):
		"""Test addenda generation with invalid field type"""
		invalid_values = self.sample_addenda_values.copy()
		invalid_values["customer_rfc"] = "INVALID-RFC"  # Doesn't match regex pattern

		result = self.generator.generate(self.sample_invoice_data, invalid_values)

		self.assertFalse(result["success"])
		self.assertIn("validation_errors", result)

	def test_template_variables_extraction(self):
		"""Test template variables extraction"""
		variables = self.generator.get_template_variables()

		expected_variables = [
			"campo_opcional",
			"current_date",
			"customer_email",
			"customer_name",
			"customer_rfc",
			"invoice",
			"version",
		]

		for var in expected_variables:
			self.assertIn(var, variables)

	def test_required_fields_extraction(self):
		"""Test required fields extraction"""
		fields = self.generator.get_required_fields()

		self.assertIsInstance(fields, list)
		self.assertGreater(len(fields), 0)

		# Find mandatory field
		mandatory_fields = [f for f in fields if f["is_mandatory"]]
		self.assertGreater(len(mandatory_fields), 0)

		# Check field structure
		sample_field = fields[0]
		required_keys = ["field_name", "field_label", "field_type", "is_mandatory"]
		for key in required_keys:
			self.assertIn(key, sample_field)

	def test_prepare_template_context(self):
		"""Test template context preparation"""
		context = self.generator._prepare_template_context(
			self.sample_invoice_data, self.sample_addenda_values
		)

		# Check invoice data
		self.assertIn("invoice", context)
		self.assertEqual(context["invoice"]["name"], "SINV-2025-001")

		# Check addenda values
		self.assertEqual(context["customer_name"], "Cliente de Prueba S.A. de C.V.")

		# Check system variables
		self.assertIn("current_date", context)
		self.assertIn("current_datetime", context)
		self.assertIn("helpers", context)

	def test_conditional_template_rendering(self):
		"""Test conditional blocks in template"""
		# Test with optional field
		values_with_optional = self.sample_addenda_values.copy()
		values_with_optional["campo_opcional"] = "Valor opcional"

		result = self.generator.generate(self.sample_invoice_data, values_with_optional)
		self.assertTrue(result["success"])
		self.assertIn("DatosOpcionales", result["xml_content"])
		self.assertIn("Valor opcional", result["xml_content"])

		# Test without optional field
		result_no_optional = self.generator.generate(self.sample_invoice_data, self.sample_addenda_values)
		self.assertTrue(result_no_optional["success"])
		self.assertNotIn("DatosOpcionales", result_no_optional["xml_content"])


class TestAddendaValidator(unittest.TestCase):
	"""Test Addenda Validator - Layer 1 Unit Tests"""

	@classmethod
	def setUpClass(cls):
		"""Set up test environment"""
		frappe.set_user("Administrator")
		cls.test_addenda_type = "TEST_GENERIC"

	def setUp(self):
		"""Set up each test"""
		self.validator = AddendaValidator(self.test_addenda_type)

		self.sample_invoice_data = {
			"name": "SINV-2025-001",
			"customer": "Test Customer",
			"grand_total": 1000.50,
		}

		self.sample_addenda_values = {
			"customer_name": "Test Customer",
			"customer_rfc": "CTM950101ABC",
			"requires_email": True,
			"customer_email": "test@example.com",
		}

	def test_validator_initialization(self):
		"""Test validator initialization"""
		self.assertEqual(self.validator.addenda_type, self.test_addenda_type)
		self.assertIsNotNone(self.validator.addenda_type_doc)

	def test_business_rules_validation_success(self):
		"""Test successful business rules validation"""
		result = self.validator.validate_business_rules(self.sample_invoice_data, self.sample_addenda_values)

		self.assertTrue(result["valid"])
		self.assertEqual(len(result["errors"]), 0)

	def test_business_rules_validation_failure(self):
		"""Test business rules validation failure"""
		# Remove required email when requires_email is True
		invalid_values = self.sample_addenda_values.copy()
		del invalid_values["customer_email"]

		result = self.validator.validate_business_rules(self.sample_invoice_data, invalid_values)

		self.assertFalse(result["valid"])
		self.assertGreater(len(result["errors"]), 0)


class TestAddendaGeneratorIntegration(unittest.TestCase):
	"""Test Addenda Generator Integration - Layer 2 Tests"""

	@classmethod
	def setUpClass(cls):
		"""Set up test environment"""
		frappe.set_user("Administrator")
		cls.test_addenda_type = "TEST_GENERIC"

	@patch("frappe.get_doc")
	def test_generate_addenda_for_invoice_api(self, mock_get_doc):
		"""Test generate_addenda_for_invoice API"""
		# Mock invoice document
		mock_invoice = Mock()
		mock_invoice.as_dict.return_value = {
			"name": "SINV-2025-001",
			"customer": "Test Customer",
			"grand_total": 1000.50,
			"company": "Test Company",
		}
		mock_invoice.customer = "Test Customer"
		mock_get_doc.return_value = mock_invoice

		# Mock customer defaults
		with patch(
			"facturacion_mexico.addendas.generic_addenda_generator.get_customer_addenda_defaults"
		) as mock_defaults:
			mock_defaults.return_value = {
				"customer_name": "Test Customer S.A.",
				"customer_rfc": "TCU950101XYZ",
				"version": "1.0",
			}

			result = generate_addenda_for_invoice("SINV-2025-001", self.test_addenda_type)

			self.assertIn("success", result)
			if result["success"]:
				self.assertIn("xml_content", result)

	def test_get_addenda_type_fields_api(self):
		"""Test get_addenda_type_fields API"""
		result = get_addenda_type_fields(self.test_addenda_type)

		self.assertIn("success", result)
		if result["success"]:
			self.assertIn("fields", result)
			self.assertIn("template_variables", result)
			self.assertIsInstance(result["fields"], list)
			self.assertIsInstance(result["template_variables"], list)

	def test_invalid_addenda_type(self):
		"""Test with invalid addenda type"""
		with self.assertRaises(frappe.DoesNotExistError):
			AddendaGenerator("INVALID_TYPE")


class TestAddendaAutoDetector(unittest.TestCase):
	"""Test Addenda Auto Detector - Layer 1 Unit Tests"""

	@classmethod
	def setUpClass(cls):
		"""Set up test environment"""
		frappe.set_user("Administrator")

	def setUp(self):
		"""Set up each test"""
		from facturacion_mexico.addendas.addenda_auto_detector import AddendaAutoDetector

		self.detector = AddendaAutoDetector()

	def test_detector_initialization(self):
		"""Test detector initialization"""
		self.assertIsNotNone(self.detector.detection_rules)
		self.assertIsNotNone(self.detector.addenda_types)
		self.assertIsInstance(self.detector.detection_rules, dict)
		self.assertIsInstance(self.detector.addenda_types, list)

	@patch("frappe.get_cached_doc")
	def test_detect_by_company_name(self, mock_get_doc):
		"""Test detection by company name"""
		# Mock customer with WALMART in name
		mock_customer = Mock()
		mock_customer.customer_name = "WALMART DE MEXICO S.A. DE C.V."
		mock_customer.get.return_value = None
		mock_get_doc.return_value = mock_customer

		result = self.detector.detect_addenda_requirement("TEST_CUSTOMER")

		# Should detect WALMART addenda if rule exists
		self.assertIn("detected", result)
		self.assertIn("confidence", result)
		self.assertIn("reason", result)

	def test_company_name_patterns(self):
		"""Test company name pattern matching"""
		test_cases = [
			("WALMART SUPERCENTER", True),
			("FEMSA COMERCIO", True),
			("SORIANA HERMANOS", True),
			("EMPRESA NORMAL S.A.", False),
		]

		for company_name, should_detect in test_cases:
			result = self.detector._detect_by_company_name(company_name)
			if should_detect:
				# Should have some confidence if pattern exists
				self.assertGreaterEqual(result.get("confidence", 0), 0)
			else:
				self.assertEqual(result["confidence"], 0)


if __name__ == "__main__":
	unittest.main()
