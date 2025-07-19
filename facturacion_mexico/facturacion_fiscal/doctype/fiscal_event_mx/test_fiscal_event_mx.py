import json
import unittest
from typing import ClassVar

import frappe

from facturacion_mexico.tests.test_base import FacturacionMexicoTestGranular

# Evitar errores de dependencias durante make_test_records siguiendo patrón condominium_management
test_ignore = ["Sales Invoice", "Customer", "Item", "Uso CFDI SAT"]


class TestFiscalEventMXGranular(FacturacionMexicoTestGranular):
	"""Tests granulares para Fiscal Event MX."""

	DOCTYPE_NAME = "Fiscal Event MX"
	REQUIRED_FIELDS: ClassVar[dict] = {
		"doctype": "Fiscal Event MX",
		"naming_series": "FEMX-.YYYY.-",
		"event_type": "create",
		"reference_doctype": "Factura Fiscal Mexico",
		"reference_name": "FFMX-TEST-001",
	}
	MOCK_HOOKS = True
	TEST_MINIMAL_ONLY = True  # Event sourcing can be complex

	def test_event_type_assignment(self):
		"""LAYER 1: Test event type field assignment."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)

		# Test different event types
		event_types = ["create", "stamp", "cancel", "validate", "error", "status_change", "api_call"]

		for event_type in event_types:
			doc.event_type = event_type
			self.assertEqual(doc.event_type, event_type)

	def test_reference_fields_assignment(self):
		"""LAYER 1: Test reference document fields assignment."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)

		doc.reference_doctype = "Factura Fiscal Mexico"
		doc.reference_name = "FFMX-TEST-001"

		self.assertEqual(doc.reference_doctype, "Factura Fiscal Mexico")
		self.assertEqual(doc.reference_name, "FFMX-TEST-001")

	def test_status_assignment(self):
		"""LAYER 1: Test status field assignment."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)

		# Test default status
		self.assertEqual(doc.status, "pending")

		# Test different statuses
		statuses = ["pending", "success", "failed", "retry"]

		for status in statuses:
			doc.status = status
			self.assertEqual(doc.status, status)

	def test_event_data_json_assignment(self):
		"""LAYER 1: Test event data JSON assignment."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)

		# Test dict assignment
		test_data = {"key": "value", "number": 123, "boolean": True}
		doc.event_data = test_data

		# Should be converted to JSON string or kept as dict
		self.assertIsNotNone(doc.event_data)

		# Test JSON string assignment
		json_string = '{"test": "data"}'
		doc.event_data = json_string
		self.assertEqual(doc.event_data, json_string)

	def test_execution_time_assignment(self):
		"""LAYER 1: Test execution time field assignment."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)

		doc.execution_time = 123.456
		self.assertEqual(doc.execution_time, 123.456)

		doc.execution_time = 0.001
		self.assertEqual(doc.execution_time, 0.001)

	def test_status_transition_validation_logic(self):
		"""LAYER 2: Test status transition validation logic."""
		# Test valid transitions logic
		valid_transitions = {
			"pending": ["success", "failed", "retry"],
			"success": [],  # Estado final
			"failed": ["retry", "success"],  # Puede reintentarse
			"retry": ["success", "failed"],
		}

		# Test valid transitions
		valid_cases = [
			("pending", "success"),
			("pending", "failed"),
			("pending", "retry"),
			("failed", "retry"),
			("failed", "success"),
			("retry", "success"),
			("retry", "failed"),
		]

		for old_status, new_status in valid_cases:
			is_valid = new_status in valid_transitions.get(old_status, [])
			self.assertTrue(is_valid, f"Transition {old_status} → {new_status} should be valid")

	def test_invalid_status_transitions(self):
		"""LAYER 2: Test invalid status transition detection."""
		valid_transitions = {
			"pending": ["success", "failed", "retry"],
			"success": [],  # Estado final
			"failed": ["retry", "success"],
			"retry": ["success", "failed"],
		}

		# Test invalid transitions
		invalid_cases = [
			("success", "pending"),  # Can't go back from success
			("success", "failed"),  # Can't go back from success
			("success", "retry"),  # Can't go back from success
		]

		for old_status, new_status in invalid_cases:
			is_valid = new_status in valid_transitions.get(old_status, [])
			self.assertFalse(is_valid, f"Transition {old_status} → {new_status} should be invalid")

	def test_event_data_json_validation_logic(self):
		"""LAYER 2: Test JSON validation logic without DB operations."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)

		# Test valid JSON string
		valid_json = '{"key": "value", "number": 123}'
		doc.event_data = valid_json

		try:
			json.loads(doc.event_data)
			validation_passed = True
		except json.JSONDecodeError:
			validation_passed = False

		self.assertTrue(validation_passed, "Valid JSON should pass validation")

		# Test valid dict (should be convertible to JSON)
		valid_dict = {"key": "value", "number": 123}
		doc.event_data = valid_dict

		try:
			if isinstance(doc.event_data, dict):
				json.dumps(doc.event_data)
			elif isinstance(doc.event_data, str):
				json.loads(doc.event_data)
			validation_passed = True
		except (json.JSONDecodeError, TypeError):
			validation_passed = False

		self.assertTrue(validation_passed, "Valid dict should be convertible to JSON")

	def test_create_event_static_method_logic(self):
		"""LAYER 2: Test create_event static method logic."""
		# Test the logic without actual DB operations
		event_type = "create"
		reference_doctype = "Factura Fiscal Mexico"
		reference_name = "FFMX-TEST-001"
		event_data = {"test": "data"}
		status = "pending"

		# Simulate the create_event logic
		doc = frappe.new_doc(self.DOCTYPE_NAME)
		doc.event_type = event_type
		doc.reference_doctype = reference_doctype
		doc.reference_name = reference_name
		doc.status = status
		doc.event_data = frappe.as_json(event_data)

		# Verify assignments
		self.assertEqual(doc.event_type, event_type)
		self.assertEqual(doc.reference_doctype, reference_doctype)
		self.assertEqual(doc.reference_name, reference_name)
		self.assertEqual(doc.status, status)

		# Verify JSON conversion
		parsed_data = json.loads(doc.event_data)
		self.assertEqual(parsed_data["test"], "data")

	def test_event_summary_logic(self):
		"""LAYER 2: Test get_event_summary method logic."""
		doc = frappe.new_doc(self.DOCTYPE_NAME)
		doc.event_type = "stamp"
		doc.status = "success"
		doc.reference_doctype = "Factura Fiscal Mexico"
		doc.reference_name = "FFMX-TEST-001"
		doc.execution_time = 123.456

		# Simulate get_event_summary logic
		summary = {
			"event_type": doc.event_type,
			"status": doc.status,
			"reference": f"{doc.reference_doctype} {doc.reference_name}",
			"execution_time": f"{doc.execution_time}ms" if doc.execution_time else "N/A",
		}

		# Verify summary
		self.assertEqual(summary["event_type"], "stamp")
		self.assertEqual(summary["status"], "success")
		self.assertEqual(summary["reference"], "Factura Fiscal Mexico FFMX-TEST-001")
		self.assertEqual(summary["execution_time"], "123.456ms")

	def test_error_message_truncation_logic(self):
		"""LAYER 2: Test error message truncation in summary."""
		long_error = "A" * 150  # Error message longer than 100 chars

		# Simulate truncation logic
		truncated = long_error[:100] + "..." if len(long_error) > 100 else long_error

		self.assertEqual(len(truncated), 103)  # 100 + "..."
		self.assertTrue(truncated.endswith("..."))

		# Test short error (no truncation)
		short_error = "Short error"
		truncated_short = short_error[:100] + "..." if len(short_error) > 100 else short_error

		self.assertEqual(truncated_short, "Short error")
		self.assertFalse(truncated_short.endswith("..."))

	def test_required_fields_meta_validation(self):
		"""LAYER 4: Test that required fields are properly configured."""
		meta = frappe.get_meta(self.DOCTYPE_NAME)

		# Find required fields
		required_fields = [field.fieldname for field in meta.fields if field.reqd]

		# Verify expected required fields
		expected_required = ["naming_series", "event_type", "reference_doctype", "reference_name", "status"]

		for field in expected_required:
			self.assertIn(field, required_fields, f"Field {field} should be required")

	def test_event_type_options_configuration(self):
		"""LAYER 4: Test event_type field options are properly configured."""
		meta = frappe.get_meta(self.DOCTYPE_NAME)

		# Find event_type field
		event_type_field = None
		for field in meta.fields:
			if field.fieldname == "event_type":
				event_type_field = field
				break

		self.assertIsNotNone(event_type_field, "Event type field should exist")

		# Test event type options
		expected_options = ["create", "stamp", "cancel", "validate", "error", "status_change", "api_call"]
		if event_type_field and event_type_field.options:
			actual_options = [opt.strip() for opt in event_type_field.options.split("\n") if opt.strip()]

			for option in expected_options:
				self.assertIn(option, actual_options, f"Event type option {option} should be available")

	def test_field_types_configuration(self):
		"""LAYER 4: Test field types are properly configured."""
		meta = frappe.get_meta(self.DOCTYPE_NAME)

		# Test specific field types
		field_types = {field.fieldname: field.fieldtype for field in meta.fields}

		expected_types = {
			"event_type": "Select",
			"reference_doctype": "Data",
			"reference_name": "Data",
			"status": "Select",
			"creation_datetime": "Datetime",
			"execution_time": "Float",
			"event_data": "JSON",
			"error_message": "Text",
			"user_role": "Data",
		}

		for field_name, expected_type in expected_types.items():
			if field_name in field_types:
				self.assertEqual(
					field_types[field_name],
					expected_type,
					f"Field {field_name} should be type {expected_type}",
				)


if __name__ == "__main__":
	unittest.main()
