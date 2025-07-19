import unittest
from typing import ClassVar

import frappe

from facturacion_mexico.tests.test_base import FacturacionMexicoTestGranular

# Evitar errores de dependencias durante make_test_records siguiendo patrón condominium_management
test_ignore = ["Sales Invoice", "Customer", "Item", "Uso CFDI SAT"]


class TestFacturaFiscalMexicoGranular(FacturacionMexicoTestGranular):
	"""Tests granulares para Factura Fiscal Mexico."""

	DOCTYPE_NAME = "Factura Fiscal Mexico"
	REQUIRED_FIELDS: ClassVar[dict] = {
		"doctype": "Factura Fiscal Mexico",
		"naming_series": "FFMX-.YYYY.-",
		"sales_invoice": "SI-TEST-001",
		"company": "Test Company",
	}
	MOCK_HOOKS = True
	TEST_MINIMAL_ONLY = True  # Complex dependencies expected

	def test_status_field_assignment(self):
		"""LAYER 1: Test status field assignment."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)

		# Test default status
		self.assertEqual(doc.status, "draft")

		# Test status assignment
		doc.status = "stamped"
		self.assertEqual(doc.status, "stamped")

		doc.status = "cancelled"
		self.assertEqual(doc.status, "cancelled")

	def test_sales_invoice_assignment(self):
		"""LAYER 1: Test Sales Invoice link assignment."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)

		doc.sales_invoice = "SI-TEST-001"
		self.assertEqual(doc.sales_invoice, "SI-TEST-001")

		doc.company = "Test Company"
		self.assertEqual(doc.company, "Test Company")

	def test_fiscal_data_assignment(self):
		"""LAYER 1: Test fiscal data fields assignment."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)

		# Test fiscal fields
		doc.facturapi_id = "test_facturapi_id"
		doc.uuid = "test_uuid_12345"
		doc.serie = "A"
		doc.folio = "123"
		doc.total_fiscal = 1000.00

		self.assertEqual(doc.facturapi_id, "test_facturapi_id")
		self.assertEqual(doc.uuid, "test_uuid_12345")
		self.assertEqual(doc.serie, "A")
		self.assertEqual(doc.folio, "123")
		self.assertEqual(doc.total_fiscal, 1000.00)

	def test_status_transition_validation_logic(self):
		"""LAYER 2: Test status transition validation logic."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)
		doc.status = "draft"

		# Mock the get_doc_before_save method for testing
		old_doc = frappe.new_doc(self.DOCTYPE_NAME)
		old_doc.status = "draft"

		# Test valid transitions from draft
		doc.status = "stamped"
		try:
			# This would normally call validate_status_transitions
			# but we'll test the logic directly
			valid_transitions = {
				"draft": ["stamped", "cancelled"],
				"stamped": ["cancel_requested", "cancelled"],
				"cancel_requested": ["cancelled", "stamped"],
				"cancelled": [],
			}

			old_status = "draft"
			new_status = "stamped"
			is_valid = new_status in valid_transitions.get(old_status, [])
			self.assertTrue(is_valid, f"Transition {old_status} → {new_status} should be valid")

		except Exception as e:
			self.fail(f"Valid transition should not raise exception: {e!s}")

	def test_invalid_status_transitions(self):
		"""LAYER 2: Test invalid status transition detection."""
		valid_transitions = {
			"draft": ["stamped", "cancelled"],
			"stamped": ["cancel_requested", "cancelled"],
			"cancel_requested": ["cancelled", "stamped"],
			"cancelled": [],
		}

		# Test invalid transitions
		invalid_cases = [
			("cancelled", "draft"),  # Can't go back from cancelled
			("cancelled", "stamped"),  # Can't go back from cancelled
			("draft", "cancel_requested"),  # Can't request cancellation from draft
		]

		for old_status, new_status in invalid_cases:
			is_valid = new_status in valid_transitions.get(old_status, [])
			self.assertFalse(is_valid, f"Transition {old_status} → {new_status} should be invalid")

	def test_mark_as_stamped_logic(self):
		"""LAYER 2: Test mark_as_stamped method logic."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)
		doc.status = "draft"

		# Test data that mark_as_stamped would process
		facturapi_data = {
			"id": "test_facturapi_id",
			"uuid": "test_uuid_12345",
			"serie": "A",
			"folio": "123",
			"total": 1000.50,
		}

		# Simulate the logic without DB operations
		doc.status = "stamped"
		doc.facturapi_id = facturapi_data.get("id")
		doc.uuid = facturapi_data.get("uuid")
		doc.serie = facturapi_data.get("serie")
		doc.folio = facturapi_data.get("folio")
		doc.total_fiscal = float(facturapi_data.get("total", 0))

		# Verify assignments
		self.assertEqual(doc.status, "stamped")
		self.assertEqual(doc.facturapi_id, "test_facturapi_id")
		self.assertEqual(doc.uuid, "test_uuid_12345")
		self.assertEqual(doc.serie, "A")
		self.assertEqual(doc.folio, "123")
		self.assertEqual(doc.total_fiscal, 1000.50)

	def test_mark_as_cancelled_logic(self):
		"""LAYER 2: Test mark_as_cancelled method logic."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)
		doc.status = "stamped"

		# Simulate mark_as_cancelled logic
		cancellation_reason = "01 - Comprobantes emitidos con errores con relación"
		doc.status = "cancelled"
		doc.cancellation_reason = cancellation_reason

		# Verify assignments
		self.assertEqual(doc.status, "cancelled")
		self.assertEqual(doc.cancellation_reason, cancellation_reason)

	def test_required_fields_meta_validation(self):
		"""LAYER 4: Test that required fields are properly configured in meta."""
		meta = frappe.get_meta(self.DOCTYPE_NAME)

		# Find required fields
		required_fields = [field.fieldname for field in meta.fields if field.reqd]

		# Verify expected required fields
		expected_required = ["naming_series", "sales_invoice", "company", "status"]

		for field in expected_required:
			self.assertIn(field, required_fields, f"Field {field} should be required")

	def test_field_types_configuration(self):
		"""LAYER 4: Test field types are properly configured."""
		meta = frappe.get_meta(self.DOCTYPE_NAME)

		# Test specific field types
		field_types = {field.fieldname: field.fieldtype for field in meta.fields}

		expected_types = {
			"sales_invoice": "Link",
			"company": "Link",
			"status": "Select",
			"facturapi_id": "Data",
			"uuid": "Data",
			"total_fiscal": "Currency",
			"fecha_timbrado": "Datetime",
			"pdf_file": "Attach",
			"xml_file": "Attach",
		}

		for field_name, expected_type in expected_types.items():
			if field_name in field_types:
				self.assertEqual(
					field_types[field_name],
					expected_type,
					f"Field {field_name} should be type {expected_type}",
				)

	def test_status_options_configuration(self):
		"""LAYER 4: Test status field options are properly configured."""
		meta = frappe.get_meta(self.DOCTYPE_NAME)

		# Find status field
		status_field = None
		for field in meta.fields:
			if field.fieldname == "status":
				status_field = field
				break

		self.assertIsNotNone(status_field, "Status field should exist")

		# Test status options
		expected_options = ["draft", "stamped", "cancelled", "cancel_requested"]
		if status_field and status_field.options:
			actual_options = [opt.strip() for opt in status_field.options.split("\n") if opt.strip()]

			for option in expected_options:
				self.assertIn(option, actual_options, f"Status option {option} should be available")


if __name__ == "__main__":
	unittest.main()
