# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Test UOM SAT Mapper - Sprint 6 Phase 4
Tests Layer 1-2 para sistema de mapeo UOM-SAT
"""

import unittest
from unittest.mock import MagicMock, patch

import frappe

from facturacion_mexico.uom_sat.mapper import UOMSATMapper


class TestUOMSATMapper(unittest.TestCase):
	"""Test UOM SAT Mapper - Layer 1 Unit Tests"""

	@classmethod
	def setUpClass(cls):
		"""Set up test environment"""
		frappe.set_user("Administrator")

	def setUp(self):
		"""Set up each test"""
		self.mapper = UOMSATMapper()

		# Mock SAT catalog para testing
		self.mapper.sat_catalog = [
			{"clave": "H87", "descripcion": "Pieza", "simbolo": "Pza"},
			{"clave": "KGM", "descripcion": "Kilogramo", "simbolo": "kg"},
			{"clave": "GRM", "descripcion": "Gramo", "simbolo": "g"},
			{"clave": "MTR", "descripcion": "Metro", "simbolo": "m"},
			{"clave": "CMT", "descripcion": "Centímetro", "simbolo": "cm"},
			{"clave": "LTR", "descripcion": "Litro", "simbolo": "l"},
			{"clave": "MTQ", "descripcion": "Metro cúbico", "simbolo": "m³"},
		]

		# Mock mapping rules
		self.mapper.mapping_rules = [
			{
				"name": "Piezas",
				"type": "contains",
				"pattern": "pieza",
				"target_clave": "H87",
				"confidence": 90,
			},
			{
				"name": "Unidades",
				"type": "contains",
				"pattern": "unidad",
				"target_clave": "H87",
				"confidence": 85,
			},
		]

	def test_mapper_initialization(self):
		"""Test mapper initialization"""
		self.assertIsNotNone(self.mapper.sat_catalog)
		self.assertIsNotNone(self.mapper.mapping_rules)
		self.assertEqual(self.mapper.confidence_threshold, 70)

	def test_exact_match_by_description(self):
		"""Test exact match by SAT description"""
		result = self.mapper.suggest_mapping("Kilogramo")

		self.assertEqual(result["suggested_mapping"], "KGM")
		self.assertEqual(result["confidence"], 100)
		self.assertIn("Coincidencia exacta", result["reason"])

	def test_exact_match_by_clave(self):
		"""Test exact match by SAT clave"""
		result = self.mapper.suggest_mapping("KGM")

		self.assertEqual(result["suggested_mapping"], "KGM")
		self.assertEqual(result["confidence"], 100)
		self.assertIn("Coincidencia exacta", result["reason"])

	def test_fuzzy_match_high_confidence(self):
		"""Test fuzzy match with high confidence"""
		result = self.mapper.suggest_mapping("Kilogram")  # Similar to Kilogramo

		self.assertEqual(result["suggested_mapping"], "KGM")
		self.assertGreater(result["confidence"], 70)
		self.assertIn("Coincidencia difusa", result["reason"])

	def test_rule_based_match(self):
		"""Test rule-based matching"""
		result = self.mapper.suggest_mapping("Pieza grande")

		self.assertEqual(result["suggested_mapping"], "H87")
		self.assertEqual(result["confidence"], 90)
		self.assertIn("Regla aplicada", result["reason"])

	def test_pattern_match_weight(self):
		"""Test pattern matching for weight units"""
		result = self.mapper.suggest_mapping("kg")

		self.assertEqual(result["suggested_mapping"], "KGM")
		self.assertEqual(result["confidence"], 85)
		self.assertIn("Patrón detectado", result["reason"])

	def test_pattern_match_length(self):
		"""Test pattern matching for length units"""
		result = self.mapper.suggest_mapping("metro")

		self.assertEqual(result["suggested_mapping"], "MTR")
		self.assertEqual(result["confidence"], 85)

	def test_pattern_match_volume(self):
		"""Test pattern matching for volume units"""
		result = self.mapper.suggest_mapping("litro")

		self.assertEqual(result["suggested_mapping"], "LTR")
		self.assertEqual(result["confidence"], 85)

	def test_no_match_low_confidence(self):
		"""Test no match when confidence is too low"""
		result = self.mapper.suggest_mapping("XYZ123")

		self.assertIsNone(result["suggested_mapping"])
		self.assertEqual(result["confidence"], 0)
		self.assertIn("No se encontró mapeo", result["reason"])

	def test_normalize_uom_name(self):
		"""Test UOM name normalization"""
		normalized = self.mapper._normalize_uom_name("  Kilo-gramo  @#$  ")
		self.assertEqual(normalized, "Kilo gramo")

	def test_find_sat_by_clave(self):
		"""Test finding SAT unit by clave"""
		sat_unit = self.mapper._find_sat_by_clave("KGM")
		self.assertIsNotNone(sat_unit)
		self.assertEqual(sat_unit["descripcion"], "Kilogramo")

		not_found = self.mapper._find_sat_by_clave("INVALID")
		self.assertIsNone(not_found)

	@patch("frappe.get_all")
	def test_bulk_map_uoms_success(self, mock_get_all):
		"""Test bulk mapping of UOMs"""
		# Mock unmapped UOMs
		mock_get_all.return_value = [
			{"name": "UOM1", "uom_name": "Kilogramo"},
			{"name": "UOM2", "uom_name": "Pieza"},
			{"name": "UOM3", "uom_name": "InvalidUOM"},
		]

		results = self.mapper.bulk_map_uoms(confidence_threshold=80, auto_apply=False)

		self.assertEqual(results["processed"], 3)
		self.assertEqual(results["mapped"], 2)  # Kilogramo y Pieza
		self.assertEqual(len(results["suggestions"]), 2)

	def test_match_rule_contains(self):
		"""Test rule matching with 'contains' type"""
		rule = {"type": "contains", "pattern": "pieza"}
		self.assertTrue(self.mapper._match_rule("Pieza grande", rule))
		self.assertFalse(self.mapper._match_rule("Kilogramo", rule))

	def test_match_rule_starts_with(self):
		"""Test rule matching with 'starts_with' type"""
		rule = {"type": "starts_with", "pattern": "kilo"}
		self.assertTrue(self.mapper._match_rule("Kilogramo", rule))
		self.assertFalse(self.mapper._match_rule("Gramo", rule))

	def test_match_rule_regex(self):
		"""Test rule matching with regex"""
		rule = {"type": "regex", "pattern": r"\b(kg|kilo)\b"}
		self.assertTrue(self.mapper._match_rule("kg", rule))
		self.assertTrue(self.mapper._match_rule("kilogramo", rule))
		self.assertFalse(self.mapper._match_rule("gramo", rule))

	@patch("frappe.db.set_value")
	@patch("frappe.db.commit")
	def test_apply_mapping(self, mock_commit, mock_set_value):
		"""Test applying mapping to UOM"""
		suggestion = {"suggested_mapping": "KGM", "confidence": 95}

		self.mapper._apply_mapping("Test UOM", suggestion)

		mock_set_value.assert_called_once()
		mock_commit.assert_called_once()


class TestUOMSATMapperIntegration(unittest.TestCase):
	"""Test UOM SAT Mapper - Layer 2 Integration Tests"""

	@classmethod
	def setUpClass(cls):
		"""Set up test environment"""
		frappe.set_user("Administrator")

	def setUp(self):
		"""Set up each test"""
		self.mapper = UOMSATMapper()

	@patch("frappe.get_all")
	def test_load_sat_catalog_from_doctype(self, mock_get_all):
		"""Test loading SAT catalog from DocType"""
		mock_get_all.return_value = [
			{"clave": "H87", "descripcion": "Pieza", "simbolo": "Pza"},
			{"clave": "KGM", "descripcion": "Kilogramo", "simbolo": "kg"},
		]

		with patch("frappe.db.exists") as mock_exists:
			mock_exists.return_value = True
			catalog = self.mapper._load_sat_catalog()

		self.assertEqual(len(catalog), 2)
		self.assertEqual(catalog[0]["clave"], "H87")

	@patch("frappe.get_single")
	def test_load_mapping_rules_from_settings(self, mock_get_single):
		"""Test loading mapping rules from settings"""
		mock_settings = MagicMock()
		mock_settings.uom_mapping_rules = '{"rules": [{"name": "test"}]}'
		mock_get_single.return_value = mock_settings

		# Create new mapper to trigger rule loading
		mapper = UOMSATMapper()
		rules = mapper._load_mapping_rules()

		self.assertIn("rules", rules)

	def test_confidence_threshold_application(self):
		"""Test confidence threshold application"""
		# Test with different thresholds
		self.mapper.confidence_threshold = 90

		# Should not suggest low confidence match
		result = self.mapper.suggest_mapping("xyz")
		self.assertIsNone(result["suggested_mapping"])

		# Lower threshold should allow more matches
		self.mapper.confidence_threshold = 50
		# This would need actual fuzzy matches to test properly


class TestUOMSATMapperErrorHandling(unittest.TestCase):
	"""Test UOM SAT Mapper - Error Handling"""

	def setUp(self):
		"""Set up each test"""
		self.mapper = UOMSATMapper()

	@patch("frappe.log_error")
	def test_suggest_mapping_error_handling(self, mock_log_error):
		"""Test error handling in suggest_mapping"""
		# Mock an error in the matching process
		with patch.object(self.mapper, "_exact_match", side_effect=Exception("Test error")):
			result = self.mapper.suggest_mapping("test")

			self.assertFalse(result.get("success", True))
			self.assertEqual(result["confidence"], 0)
			mock_log_error.assert_called()

	@patch("frappe.log_error")
	def test_bulk_map_error_handling(self, mock_log_error):
		"""Test error handling in bulk mapping"""
		with patch("frappe.get_all", side_effect=Exception("Database error")):
			result = self.mapper.bulk_map_uoms()

			self.assertEqual(result["processed"], 0)
			self.assertEqual(result["errors"], 1)
			mock_log_error.assert_called()

	def test_empty_catalog_handling(self):
		"""Test handling of empty SAT catalog"""
		self.mapper.sat_catalog = []

		result = self.mapper.suggest_mapping("test")
		self.assertIsNone(result["suggested_mapping"])

	def test_empty_rules_handling(self):
		"""Test handling of empty mapping rules"""
		self.mapper.mapping_rules = []

		# Should still work with pattern matching
		self.mapper.suggest_mapping("kg")
		# This depends on pattern matching still working


class TestUOMSATMapperPerformance(unittest.TestCase):
	"""Test UOM SAT Mapper - Performance Tests"""

	def setUp(self):
		"""Set up performance test"""
		self.mapper = UOMSATMapper()

		# Create larger mock catalog for performance testing
		self.mapper.sat_catalog = [
			{"clave": f"T{i:03d}", "descripcion": f"Test Unit {i}", "simbolo": f"TU{i}"} for i in range(1000)
		]

	def test_large_catalog_performance(self):
		"""Test performance with large catalog"""
		import time

		start_time = time.time()

		# Test multiple mappings
		for uom in ["Test Unit 1", "Test Unit 500", "Test Unit 999", "Non-existent"]:
			self.mapper.suggest_mapping(uom)

		end_time = time.time()
		execution_time = end_time - start_time

		# Should complete within reasonable time (< 1 second)
		self.assertLess(execution_time, 1.0)

	def test_fuzzy_matching_performance(self):
		"""Test fuzzy matching performance"""
		import time

		start_time = time.time()

		# Test fuzzy matching with variations
		test_uoms = ["Test Unt 1", "Tst Unit 50", "Test Uni 99"]
		for uom in test_uoms:
			self.mapper.suggest_mapping(uom)

		end_time = time.time()
		execution_time = end_time - start_time

		# Fuzzy matching should still be reasonably fast
		self.assertLess(execution_time, 2.0)


if __name__ == "__main__":
	unittest.main()
