# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Test UOM SAT Validation - Sprint 6 Phase 4
Tests Layer 1-2 para validación UOM-SAT en facturación
"""

import unittest
from unittest.mock import MagicMock, patch

import frappe

from facturacion_mexico.uom_sat.validation import UOMSATValidator


class TestUOMSATValidation(unittest.TestCase):
	"""Test UOM SAT Validation - Layer 1 Unit Tests"""

	@classmethod
	def setUpClass(cls):
		"""Set up test environment"""
		frappe.set_user("Administrator")

	def setUp(self):
		"""Set up each test"""
		self.validator = UOMSATValidator()

		# Mock invoice document
		self.mock_invoice = MagicMock()
		self.mock_invoice.items = [
			MagicMock(item_code="ITEM001", item_name="Test Item 1", uom="Kg", qty=10),
			MagicMock(item_code="ITEM002", item_name="Test Item 2", uom="Pza", qty=5),
			MagicMock(item_code="ITEM003", item_name="Test Item 3", uom="Unmapped", qty=2),
		]

	def test_validator_initialization(self):
		"""Test validator initialization"""
		self.assertIsNotNone(self.validator)
		self.assertIsInstance(self.validator.validation_enabled, bool)

	@patch.object(UOMSATValidator, "_get_uom_mapping")
	def test_validate_invoice_all_mapped(self, mock_get_mapping):
		"""Test validation with all UOMs mapped"""
		# Mock all UOMs as mapped
		mock_get_mapping.side_effect = [
			{"sat_clave": "KGM", "confidence": 100, "source": "Manual"},
			{"sat_clave": "H87", "confidence": 95, "source": "Auto"},
			{"sat_clave": "LTR", "confidence": 85, "source": "Auto"},
		]

		result = self.validator.validate_invoice_uom_mappings(self.mock_invoice)

		self.assertTrue(result["is_valid"])
		self.assertEqual(len(result["errors"]), 0)
		self.assertEqual(len(result["unmapped_items"]), 0)

	@patch.object(UOMSATValidator, "_get_uom_mapping")
	def test_validate_invoice_with_unmapped_uoms(self, mock_get_mapping):
		"""Test validation with unmapped UOMs"""
		# Mock some UOMs as unmapped
		mock_get_mapping.side_effect = [
			{"sat_clave": "KGM", "confidence": 100, "source": "Manual"},
			{"sat_clave": "H87", "confidence": 95, "source": "Auto"},
			None,  # Unmapped UOM
		]

		result = self.validator.validate_invoice_uom_mappings(self.mock_invoice)

		self.assertFalse(result["is_valid"])
		self.assertGreater(len(result["errors"]), 0)
		self.assertEqual(len(result["unmapped_items"]), 1)
		self.assertEqual(result["unmapped_items"][0]["item_code"], "ITEM003")

	@patch.object(UOMSATValidator, "_get_uom_mapping")
	def test_validate_invoice_with_low_confidence(self, mock_get_mapping):
		"""Test validation with low confidence mappings"""
		# Mock UOMs with low confidence
		mock_get_mapping.side_effect = [
			{"sat_clave": "KGM", "confidence": 100, "source": "Manual"},
			{"sat_clave": "H87", "confidence": 75, "source": "Auto"},  # Low confidence
			{"sat_clave": "LTR", "confidence": 60, "source": "Auto"},  # Very low confidence
		]

		result = self.validator.validate_invoice_uom_mappings(self.mock_invoice)

		self.assertTrue(result["is_valid"])  # Still valid but with warnings
		self.assertGreater(len(result["warnings"]), 0)
		self.assertIn("baja confianza", result["warnings"][0])

	def test_validate_invoice_disabled_validation(self):
		"""Test validation when disabled"""
		self.validator.validation_enabled = False

		result = self.validator.validate_invoice_uom_mappings(self.mock_invoice)

		self.assertTrue(result["is_valid"])
		self.assertEqual(len(result["errors"]), 0)

	@patch.object(UOMSATValidator, "_generate_mapping_suggestions")
	@patch.object(UOMSATValidator, "_get_uom_mapping")
	def test_validate_and_suggest_corrections(self, mock_get_mapping, mock_suggestions):
		"""Test validation with correction suggestions"""
		# Mock unmapped UOM
		mock_get_mapping.side_effect = [
			{"sat_clave": "KGM", "confidence": 100, "source": "Manual"},
			{"sat_clave": "H87", "confidence": 95, "source": "Auto"},
			None,  # Unmapped
		]

		# Mock suggestions
		mock_suggestions.return_value = [
			{
				"item_code": "ITEM003",
				"uom": "Unmapped",
				"suggested_mapping": "MTR",
				"confidence": 85,
				"reason": "Pattern match",
			}
		]

		result = self.validator.validate_and_suggest_corrections(self.mock_invoice)

		self.assertFalse(result["is_valid"])
		self.assertIn("auto_corrections", result)
		mock_suggestions.assert_called_once()

	def test_get_uom_mapping_exists(self):
		"""Test getting UOM mapping when exists"""
		with patch("frappe.get_cached_doc") as mock_get_doc:
			mock_uom_doc = MagicMock()
			mock_uom_doc.fm_clave_sat = "KGM"
			mock_uom_doc.get.side_effect = lambda x: {
				"fm_mapping_confidence": 95,
				"fm_mapping_source": "Auto",
				"fm_mapping_verified": 1,
			}.get(x, None)
			mock_get_doc.return_value = mock_uom_doc

			mapping = self.validator._get_uom_mapping("Kg")

			self.assertIsNotNone(mapping)
			self.assertEqual(mapping["sat_clave"], "KGM")
			self.assertEqual(mapping["confidence"], 95)

	def test_get_uom_mapping_not_exists(self):
		"""Test getting UOM mapping when doesn't exist"""
		with patch("frappe.get_cached_doc") as mock_get_doc:
			mock_uom_doc = MagicMock()
			mock_uom_doc.get.return_value = None  # No SAT mapping
			mock_get_doc.return_value = mock_uom_doc

			mapping = self.validator._get_uom_mapping("Unmapped")

			self.assertIsNone(mapping)

	@patch("frappe.get_cached_doc", side_effect=Exception("UOM not found"))
	def test_get_uom_mapping_error(self, mock_get_doc):
		"""Test error handling in get_uom_mapping"""
		mapping = self.validator._get_uom_mapping("Invalid")
		self.assertIsNone(mapping)

	def test_get_recommendation_high_confidence(self):
		"""Test recommendation for high confidence"""
		recommendation = self.validator._get_recommendation(95)
		self.assertIn("Alta confianza", recommendation)

	def test_get_recommendation_medium_confidence(self):
		"""Test recommendation for medium confidence"""
		recommendation = self.validator._get_recommendation(85)
		self.assertIn("Confianza media", recommendation)

	def test_get_recommendation_low_confidence(self):
		"""Test recommendation for low confidence"""
		recommendation = self.validator._get_recommendation(75)
		self.assertIn("Baja confianza", recommendation)

	def test_get_recommendation_very_low_confidence(self):
		"""Test recommendation for very low confidence"""
		recommendation = self.validator._get_recommendation(50)
		self.assertIn("No recomendado", recommendation)

	@patch("frappe.get_single")
	def test_is_validation_enabled_from_settings(self, mock_get_single):
		"""Test checking validation enabled from settings"""
		mock_settings = MagicMock()
		mock_settings.validate_uom_mappings = True
		mock_get_single.return_value = mock_settings

		validator = UOMSATValidator()
		self.assertTrue(validator._is_validation_enabled())

	@patch("frappe.get_single", side_effect=Exception("Settings not found"))
	def test_is_validation_enabled_default(self, mock_get_single):
		"""Test default validation enabled when settings fail"""
		validator = UOMSATValidator()
		self.assertTrue(validator._is_validation_enabled())  # Default True


class TestUOMSATValidationIntegration(unittest.TestCase):
	"""Test UOM SAT Validation - Layer 2 Integration Tests"""

	@classmethod
	def setUpClass(cls):
		"""Set up test environment"""
		frappe.set_user("Administrator")

	def setUp(self):
		"""Set up each test"""
		self.validator = UOMSATValidator()

	@patch("frappe.db.set_value")
	@patch("frappe.db.commit")
	def test_apply_auto_corrections_high_confidence(self, mock_commit, mock_set_value):
		"""Test applying auto corrections with high confidence"""
		corrections = [
			{
				"uom": "Kg",
				"suggested_mapping": "KGM",
				"confidence": 95,
				"reason": "Pattern match",
			},
			{
				"uom": "Pza",
				"suggested_mapping": "H87",
				"confidence": 75,  # Lower confidence
				"reason": "Rule match",
			},
		]

		result = self.validator.apply_auto_corrections(corrections, "apply_high_confidence")

		self.assertTrue(result["success"])
		self.assertEqual(result["applied"], 1)  # Only high confidence
		self.assertEqual(result["skipped"], 1)
		mock_set_value.assert_called_once()
		mock_commit.assert_called_once()

	@patch("frappe.db.set_value")
	@patch("frappe.db.commit")
	def test_apply_auto_corrections_all(self, mock_commit, mock_set_value):
		"""Test applying all auto corrections"""
		corrections = [
			{
				"uom": "Kg",
				"suggested_mapping": "KGM",
				"confidence": 95,
				"reason": "Pattern match",
			},
			{
				"uom": "Pza",
				"suggested_mapping": "H87",
				"confidence": 75,
				"reason": "Rule match",
			},
		]

		result = self.validator.apply_auto_corrections(corrections, "apply_all")

		self.assertTrue(result["success"])
		self.assertEqual(result["applied"], 2)  # Both applied
		self.assertEqual(result["skipped"], 0)
		self.assertEqual(mock_set_value.call_count, 2)

	@patch("facturacion_mexico.uom_sat.mapper.UOMSATMapper")
	def test_generate_mapping_suggestions_with_mapper(self, mock_mapper_class):
		"""Test generating suggestions using mapper"""
		mock_mapper = MagicMock()
		mock_mapper.suggest_mapping.return_value = {
			"suggested_mapping": "KGM",
			"confidence": 85,
			"reason": "Fuzzy match",
			"sat_description": "Kilogramo",
		}
		mock_mapper_class.return_value = mock_mapper

		unmapped_items = [{"item_code": "ITEM001", "uom": "Kg"}]

		suggestions = self.validator._generate_mapping_suggestions(unmapped_items)

		self.assertEqual(len(suggestions), 1)
		self.assertEqual(suggestions[0]["suggested_mapping"], "KGM")
		mock_mapper.suggest_mapping.assert_called_once_with("Kg")

	@patch("facturacion_mexico.uom_sat.mapper.UOMSATMapper", side_effect=Exception("Mapper error"))
	@patch("frappe.log_error")
	def test_generate_suggestions_error_handling(self, mock_log_error, mock_mapper):
		"""Test error handling in suggestion generation"""
		unmapped_items = [{"item_code": "ITEM001", "uom": "Kg"}]

		suggestions = self.validator._generate_mapping_suggestions(unmapped_items)

		self.assertEqual(len(suggestions), 0)
		mock_log_error.assert_called()


class TestUOMSATValidationHooks(unittest.TestCase):
	"""Test UOM SAT Validation - Sales Invoice Hooks"""

	def setUp(self):
		"""Set up hook tests"""
		self.mock_invoice = MagicMock()
		self.mock_invoice.get.return_value = True  # fm_factura_electronica = True

	@patch("facturacion_mexico.uom_sat.validation.UOMSATValidator")
	@patch("frappe.msgprint")
	def test_sales_invoice_validation_hook_success(self, mock_msgprint, mock_validator_class):
		"""Test successful validation hook"""
		from facturacion_mexico.uom_sat.validation import sales_invoice_validate_uom_mappings

		mock_validator = MagicMock()
		mock_validator.validate_invoice_uom_mappings.return_value = {
			"is_valid": True,
			"errors": [],
			"warnings": ["Warning message"],
			"suggestions": [],
		}
		mock_validator_class.return_value = mock_validator

		# Should not raise exception
		sales_invoice_validate_uom_mappings(self.mock_invoice, "validate")

		mock_msgprint.assert_called_once()  # Warning message

	@patch("facturacion_mexico.uom_sat.validation.UOMSATValidator")
	@patch("frappe.throw")
	@patch("frappe.msgprint")
	def test_sales_invoice_validation_hook_failure(self, mock_msgprint, mock_throw, mock_validator_class):
		"""Test validation hook failure"""
		from facturacion_mexico.uom_sat.validation import sales_invoice_validate_uom_mappings

		mock_validator = MagicMock()
		mock_validator.validate_invoice_uom_mappings.return_value = {
			"is_valid": False,
			"errors": ["UOM mapping error"],
			"warnings": [],
			"suggestions": [{"uom": "Kg", "suggested_mapping": "KGM"}],
		}
		mock_validator_class.return_value = mock_validator

		sales_invoice_validate_uom_mappings(self.mock_invoice, "validate")

		mock_msgprint.assert_called()  # Suggestions message
		mock_throw.assert_called_once()  # Should throw error

	def test_sales_invoice_validation_hook_skip_non_electronic(self):
		"""Test hook skips non-electronic invoices"""
		from facturacion_mexico.uom_sat.validation import sales_invoice_validate_uom_mappings

		self.mock_invoice.get.return_value = False  # Not electronic invoice

		# Should complete without validation
		sales_invoice_validate_uom_mappings(self.mock_invoice, "validate")

	@patch("frappe.log_error")
	def test_sales_invoice_validation_hook_error_handling(self, mock_log_error):
		"""Test hook error handling"""
		from facturacion_mexico.uom_sat.validation import sales_invoice_validate_uom_mappings

		# Force an error
		with patch(
			"facturacion_mexico.uom_sat.validation.UOMSATValidator", side_effect=Exception("Test error")
		):
			# Should not raise exception
			sales_invoice_validate_uom_mappings(self.mock_invoice, "validate")

		mock_log_error.assert_called()


class TestUOMSATValidationPerformance(unittest.TestCase):
	"""Test UOM SAT Validation - Performance Tests"""

	def setUp(self):
		"""Set up performance tests"""
		self.validator = UOMSATValidator()

		# Create large mock invoice
		self.large_invoice = MagicMock()
		self.large_invoice.items = [
			MagicMock(item_code=f"ITEM{i:03d}", item_name=f"Item {i}", uom=f"UOM{i % 10}", qty=i)
			for i in range(100)
		]

	@patch.object(UOMSATValidator, "_get_uom_mapping")
	def test_large_invoice_validation_performance(self, mock_get_mapping):
		"""Test performance with large invoice"""
		import time

		# Mock all as mapped
		mock_get_mapping.return_value = {"sat_clave": "H87", "confidence": 95, "source": "Auto"}

		start_time = time.time()
		result = self.validator.validate_invoice_uom_mappings(self.large_invoice)
		end_time = time.time()

		execution_time = end_time - start_time

		# Should complete within reasonable time
		self.assertLess(execution_time, 1.0)
		self.assertTrue(result["is_valid"])

	@patch.object(UOMSATValidator, "_get_uom_mapping")
	@patch.object(UOMSATValidator, "_generate_mapping_suggestions")
	def test_suggestion_generation_performance(self, mock_suggestions, mock_get_mapping):
		"""Test performance of suggestion generation"""
		import time

		# Mock some unmapped
		mock_get_mapping.side_effect = (
			lambda uom: None if "UOM1" in uom else {"sat_clave": "H87", "confidence": 95}
		)

		# Mock suggestions
		mock_suggestions.return_value = []

		start_time = time.time()
		self.validator.validate_and_suggest_corrections(self.large_invoice)
		end_time = time.time()

		execution_time = end_time - start_time

		# Should complete within reasonable time even with suggestions
		self.assertLess(execution_time, 2.0)


if __name__ == "__main__":
	unittest.main()
