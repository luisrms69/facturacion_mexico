# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Test UOM SAT API - Sprint 6 Phase 4
Tests Layer 1-2 para APIs del sistema UOM-SAT
"""

import json
import unittest
from unittest.mock import MagicMock, patch

import frappe

from facturacion_mexico.uom_sat import api


class TestUOMSATAPI(unittest.TestCase):
	"""Test UOM SAT APIs - Layer 1 Unit Tests"""

	@classmethod
	def setUpClass(cls):
		"""Set up test environment"""
		frappe.set_user("Administrator")

	def setUp(self):
		"""Set up each test"""
		pass

	@patch("frappe.db.count")
	@patch("frappe.db.sql")
	def test_get_uom_mapping_dashboard(self, mock_sql, mock_count):
		"""Test UOM mapping dashboard API"""
		# Mock database counts
		mock_count.side_effect = [100, 80, 30, 25, 5]  # total, mapped, auto, verified, low_confidence

		# Mock SQL queries
		mock_sql.side_effect = [
			[{"name": "UOM1", "uom_name": "Kilogramo", "usage_count": 50}],  # unmapped_popular
			[{"source": "Auto", "count": 30}, {"source": "Manual", "count": 50}],  # mapping_sources
			[{"date": "2025-07-22", "mappings": 10}],  # mapping_trend
		]

		result = api.get_uom_mapping_dashboard()

		self.assertTrue(result["success"])
		self.assertIn("dashboard", result)

		dashboard = result["dashboard"]
		self.assertEqual(dashboard["summary"]["total_uoms"], 100)
		self.assertEqual(dashboard["summary"]["mapped_uoms"], 80)
		self.assertEqual(dashboard["summary"]["mapping_percentage"], 80.0)

	@patch("frappe.db.sql")
	def test_get_unmapped_uoms_popular(self, mock_sql):
		"""Test get unmapped UOMs API with popular filter"""
		mock_sql.return_value = [
			{"name": "UOM1", "uom_name": "Kilogramo", "usage_count": 50},
			{"name": "UOM2", "uom_name": "Pieza", "usage_count": 30},
		]

		result = api.get_unmapped_uoms(limit=10, popular_only=True)

		self.assertTrue(result["success"])
		self.assertEqual(len(result["unmapped_uoms"]), 2)
		self.assertEqual(result["unmapped_uoms"][0]["usage_count"], 50)

	@patch("frappe.get_all")
	def test_get_unmapped_uoms_all(self, mock_get_all):
		"""Test get unmapped UOMs API without filter"""
		mock_get_all.return_value = [
			{"name": "UOM1", "uom_name": "Test UOM 1"},
			{"name": "UOM2", "uom_name": "Test UOM 2"},
		]

		result = api.get_unmapped_uoms(limit=50, popular_only=False)

		self.assertTrue(result["success"])
		self.assertEqual(len(result["unmapped_uoms"]), 2)
		mock_get_all.assert_called_once()

	@patch("facturacion_mexico.uom_sat.api.UOMSATMapper")
	@patch("frappe.get_all")
	def test_bulk_suggest_mappings(self, mock_get_all, mock_mapper_class):
		"""Test bulk suggest mappings API"""
		# Mock unmapped UOMs
		mock_get_all.return_value = [
			{"name": "UOM1", "uom_name": "Kilogramo"},
			{"name": "UOM2", "uom_name": "Pieza"},
		]

		# Mock mapper
		mock_mapper = MagicMock()
		mock_mapper.suggest_mapping.side_effect = [
			{
				"suggested_mapping": "KGM",
				"confidence": 95,
				"reason": "Exact match",
				"sat_description": "Kilogramo",
			},
			{
				"suggested_mapping": "H87",
				"confidence": 85,
				"reason": "Pattern match",
				"sat_description": "Pieza",
			},
		]
		mock_mapper_class.return_value = mock_mapper

		result = api.bulk_suggest_mappings(confidence_threshold=80, limit=50)

		self.assertTrue(result["success"])
		self.assertEqual(result["total_processed"], 2)
		self.assertEqual(result["suggestions_generated"], 2)
		self.assertEqual(len(result["suggestions"]), 2)

	@patch("frappe.db.set_value")
	@patch("frappe.db.commit")
	def test_apply_bulk_mappings_high_confidence(self, mock_commit, mock_set_value):
		"""Test apply bulk mappings with high confidence mode"""
		mappings_data = [
			{"uom": "UOM1", "suggested_mapping": "KGM", "confidence": 95},
			{"uom": "UOM2", "suggested_mapping": "H87", "confidence": 75},  # Below threshold
		]

		result = api.apply_bulk_mappings(json.dumps(mappings_data), "high_confidence")

		self.assertTrue(result["success"])
		self.assertEqual(result["applied"], 1)  # Only high confidence
		self.assertEqual(result["skipped"], 1)
		mock_set_value.assert_called_once()
		mock_commit.assert_called_once()

	@patch("frappe.db.set_value")
	@patch("frappe.db.commit")
	def test_apply_bulk_mappings_all_mode(self, mock_commit, mock_set_value):
		"""Test apply bulk mappings with all mode"""
		mappings_data = [
			{"uom": "UOM1", "suggested_mapping": "KGM", "confidence": 95},
			{"uom": "UOM2", "suggested_mapping": "H87", "confidence": 75},
		]

		result = api.apply_bulk_mappings(json.dumps(mappings_data), "all")

		self.assertTrue(result["success"])
		self.assertEqual(result["applied"], 2)  # Both applied
		self.assertEqual(result["skipped"], 0)
		self.assertEqual(mock_set_value.call_count, 2)

	@patch("facturacion_mexico.uom_sat.api.UOMSATValidator")
	@patch("frappe.get_all")
	@patch("frappe.get_doc")
	def test_validate_all_pending_invoices(self, mock_get_doc, mock_get_all, mock_validator_class):
		"""Test validate all pending invoices API"""
		# Mock pending invoices
		mock_get_all.return_value = [
			{"name": "SINV-001", "customer": "Customer 1", "grand_total": 1000},
			{"name": "SINV-002", "customer": "Customer 2", "grand_total": 2000},
		]

		# Mock invoice documents
		mock_get_doc.side_effect = [MagicMock(), MagicMock()]

		# Mock validator
		mock_validator = MagicMock()
		mock_validator.validate_invoice_uom_mappings.side_effect = [
			{"is_valid": True, "errors": [], "warnings": []},
			{"is_valid": False, "errors": ["UOM error"], "warnings": ["UOM warning"]},
		]
		mock_validator_class.return_value = mock_validator

		result = api.validate_all_pending_invoices()

		self.assertTrue(result["success"])
		self.assertEqual(result["summary"]["total_invoices"], 2)
		self.assertEqual(result["summary"]["valid_invoices"], 1)
		self.assertEqual(result["summary"]["invalid_invoices"], 1)

	@patch("frappe.get_all")
	@patch("frappe.db.exists")
	def test_get_sat_catalog_from_doctype(self, mock_exists, mock_get_all):
		"""Test get SAT catalog from DocType"""
		mock_exists.return_value = True
		mock_get_all.return_value = [
			{"clave": "KGM", "descripcion": "Kilogramo", "simbolo": "kg", "disabled": 0},
			{"clave": "H87", "descripcion": "Pieza", "simbolo": "Pza", "disabled": 0},
		]

		result = api.get_sat_catalog()

		self.assertTrue(result["success"])
		self.assertEqual(len(result["catalog"]), 2)
		self.assertEqual(result["catalog"][0]["clave"], "KGM")

	@patch("frappe.db.exists")
	def test_get_sat_catalog_fallback(self, mock_exists):
		"""Test get SAT catalog fallback when DocType doesn't exist"""
		mock_exists.return_value = False

		result = api.get_sat_catalog()

		self.assertTrue(result["success"])
		self.assertGreater(len(result["catalog"]), 0)  # Should have fallback catalog

	@patch("frappe.db.count")
	@patch("frappe.db.exists")
	def test_sync_sat_catalog(self, mock_exists, mock_count):
		"""Test sync SAT catalog API"""
		mock_exists.return_value = True
		mock_count.return_value = 150

		result = api.sync_sat_catalog()

		self.assertTrue(result["success"])
		self.assertEqual(result["catalog_entries"], 150)
		self.assertIn("last_sync", result)

	@patch("frappe.get_all")
	def test_export_uom_mappings_json(self, mock_get_all):
		"""Test export UOM mappings in JSON format"""
		mock_get_all.return_value = [
			{"name": "UOM1", "uom_name": "Kg", "fm_clave_sat": "KGM", "fm_mapping_confidence": 100},
			{"name": "UOM2", "uom_name": "Pza", "fm_clave_sat": "H87", "fm_mapping_confidence": 95},
		]

		result = api.export_uom_mappings("json")

		self.assertTrue(result["success"])
		self.assertEqual(result["format"], "json")
		self.assertEqual(len(result["mappings"]), 2)

	@patch("frappe.get_all")
	def test_export_uom_mappings_csv(self, mock_get_all):
		"""Test export UOM mappings in CSV format"""
		mock_get_all.return_value = [
			{"name": "UOM1", "uom_name": "Kg", "fm_clave_sat": "KGM", "fm_mapping_confidence": 100},
		]

		result = api.export_uom_mappings("csv")

		self.assertTrue(result["success"])
		self.assertEqual(result["format"], "csv")
		self.assertIn("content", result)
		self.assertIn("name,uom_name", result["content"])  # CSV headers

	@patch("frappe.db.set_value")
	@patch("frappe.db.commit")
	@patch("frappe.db.exists")
	@patch("frappe.db.get_value")
	def test_import_uom_mappings(self, mock_get_value, mock_exists, mock_commit, mock_set_value):
		"""Test import UOM mappings API"""
		mappings_data = [
			{"name": "UOM1", "fm_clave_sat": "KGM", "fm_mapping_confidence": 100},
			{"name": "UOM2", "fm_clave_sat": "H87", "fm_mapping_confidence": 95},
		]

		# Mock UOMs exist
		mock_exists.side_effect = [True, True]
		# Mock no existing mappings
		mock_get_value.side_effect = [None, None]

		result = api.import_uom_mappings(json.dumps(mappings_data), update_existing=False)

		self.assertTrue(result["success"])
		self.assertEqual(result["imported"], 2)
		self.assertEqual(result["updated"], 0)
		self.assertEqual(mock_set_value.call_count, 2)

	@patch("facturacion_mexico.uom_sat.api.create_uom_sat_fields")
	@patch("facturacion_mexico.uom_sat.api.UOMSATMapper")
	def test_install_uom_sat_system(self, mock_mapper_class, mock_create_fields):
		"""Test install UOM SAT system API"""
		# Mock field creation
		mock_create_fields.return_value = {"success": True, "message": "Fields created"}

		# Mock mapper bulk operation
		mock_mapper = MagicMock()
		mock_mapper.bulk_map_uoms.return_value = {"processed": 50, "mapped": 30}
		mock_mapper_class.return_value = mock_mapper

		result = api.install_uom_sat_system()

		self.assertTrue(result["success"])
		self.assertTrue(result["fields_installed"])
		self.assertIn("initial_mappings", result)


class TestUOMSATAPIErrors(unittest.TestCase):
	"""Test UOM SAT API Error Handling"""

	def setUp(self):
		"""Set up error tests"""
		pass

	@patch("frappe.log_error")
	@patch("frappe.db.count", side_effect=Exception("Database error"))
	def test_get_uom_mapping_dashboard_error(self, mock_count, mock_log_error):
		"""Test dashboard API error handling"""
		result = api.get_uom_mapping_dashboard()

		self.assertFalse(result["success"])
		self.assertIn("Error", result["message"])
		mock_log_error.assert_called()

	@patch("frappe.log_error")
	@patch("frappe.get_all", side_effect=Exception("Database error"))
	def test_get_unmapped_uoms_error(self, mock_get_all, mock_log_error):
		"""Test get unmapped UOMs error handling"""
		result = api.get_unmapped_uoms()

		self.assertFalse(result["success"])
		self.assertIn("Error", result["message"])
		mock_log_error.assert_called()

	@patch("frappe.log_error")
	def test_bulk_suggest_mappings_error(self, mock_log_error):
		"""Test bulk suggest mappings error handling"""
		with patch("frappe.get_all", side_effect=Exception("Error")):
			result = api.bulk_suggest_mappings()

		self.assertFalse(result["success"])
		mock_log_error.assert_called()

	@patch("frappe.log_error")
	def test_apply_bulk_mappings_invalid_json(self, mock_log_error):
		"""Test apply bulk mappings with invalid JSON"""
		result = api.apply_bulk_mappings("invalid json", "all")

		self.assertFalse(result["success"])
		mock_log_error.assert_called()

	@patch("frappe.log_error")
	def test_validate_all_pending_invoices_error(self, mock_log_error):
		"""Test validate pending invoices error handling"""
		with patch("frappe.get_all", side_effect=Exception("Error")):
			result = api.validate_all_pending_invoices()

		self.assertFalse(result["success"])
		mock_log_error.assert_called()

	@patch("frappe.log_error")
	def test_export_uom_mappings_error(self, mock_log_error):
		"""Test export UOM mappings error handling"""
		with patch("frappe.get_all", side_effect=Exception("Error")):
			result = api.export_uom_mappings()

		self.assertFalse(result["success"])
		mock_log_error.assert_called()

	@patch("frappe.log_error")
	def test_import_uom_mappings_error(self, mock_log_error):
		"""Test import UOM mappings error handling"""
		result = api.import_uom_mappings("invalid json")

		self.assertFalse(result["success"])
		mock_log_error.assert_called()


class TestUOMSATAPIIntegration(unittest.TestCase):
	"""Test UOM SAT API - Layer 2 Integration Tests"""

	@classmethod
	def setUpClass(cls):
		"""Set up integration test environment"""
		frappe.set_user("Administrator")

	def setUp(self):
		"""Set up each integration test"""
		pass

	@patch("frappe.db.sql")
	@patch("frappe.db.count")
	def test_dashboard_data_consistency(self, mock_count, mock_sql):
		"""Test dashboard data consistency"""
		# Mock consistent data
		mock_count.side_effect = [100, 80, 30, 25, 5]
		mock_sql.side_effect = [[], [], []]

		result = api.get_uom_mapping_dashboard()

		self.assertTrue(result["success"])

		summary = result["dashboard"]["summary"]
		self.assertEqual(summary["unmapped_uoms"], summary["total_uoms"] - summary["mapped_uoms"])
		self.assertEqual(summary["unmapped_uoms"], 20)

	@patch("frappe.get_all")
	def test_unmapped_uoms_filter_consistency(self, mock_get_all):
		"""Test unmapped UOMs filter consistency"""
		mock_get_all.return_value = [
			{"name": "UOM1", "uom_name": "Test1"},
			{"name": "UOM2", "uom_name": "Test2"},
		]

		result = api.get_unmapped_uoms(limit=10)

		self.assertTrue(result["success"])
		self.assertEqual(result["count"], len(result["unmapped_uoms"]))

	@patch("facturacion_mexico.uom_sat.api.UOMSATMapper")
	@patch("frappe.get_all")
	def test_bulk_operations_consistency(self, mock_get_all, mock_mapper_class):
		"""Test consistency between bulk suggest and apply"""
		# Mock UOMs
		mock_get_all.return_value = [{"name": "UOM1", "uom_name": "Kg"}]

		# Mock mapper suggestions
		mock_mapper = MagicMock()
		mock_mapper.suggest_mapping.return_value = {
			"suggested_mapping": "KGM",
			"confidence": 95,
			"reason": "Test",
			"sat_description": "Kilogramo",
		}
		mock_mapper_class.return_value = mock_mapper

		# Get suggestions
		suggest_result = api.bulk_suggest_mappings()
		self.assertTrue(suggest_result["success"])

		# Apply same suggestions
		with patch("frappe.db.set_value"), patch("frappe.db.commit"):
			apply_result = api.apply_bulk_mappings(
				json.dumps(suggest_result["suggestions"]), "high_confidence"
			)

		self.assertTrue(apply_result["success"])
		self.assertEqual(apply_result["applied"], 1)


if __name__ == "__main__":
	unittest.main()
