# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Test UOM SAT Catalog - Sprint 6 Phase 2
Tests para catálogo de Unidades de Medida SAT
"""

import unittest
from unittest.mock import Mock, patch

import frappe

from facturacion_mexico.uom_sat.uom_sat_catalog import UOMSATCatalog


class TestUOMSATCatalog(unittest.TestCase):
	"""Test UOM SAT Catalog functionality"""

	@classmethod
	def setUpClass(cls):
		"""Set up test environment"""
		frappe.set_user("Administrator")

	def setUp(self):
		"""Set up each test"""
		self.catalog = UOMSATCatalog()

	def test_catalog_initialization(self):
		"""Test catalog initialization"""
		self.assertIsNone(self.catalog._catalog_cache)

	def test_get_sat_catalog_loads_data(self):
		"""Test that get_sat_catalog loads and caches data"""
		# First call should load data
		catalog_data = self.catalog.get_sat_catalog()

		self.assertIsNotNone(catalog_data)
		self.assertIsInstance(catalog_data, list)
		self.assertGreater(len(catalog_data), 0)

		# Verify cache is populated
		self.assertIsNotNone(self.catalog._catalog_cache)

		# Second call should use cache
		catalog_data_2 = self.catalog.get_sat_catalog()
		self.assertEqual(catalog_data, catalog_data_2)

	def test_get_sat_catalog_force_refresh(self):
		"""Test force refresh functionality"""
		# Load initial data
		self.catalog.get_sat_catalog()

		# Force refresh should reload
		refreshed_data = self.catalog.get_sat_catalog(force_refresh=True)

		self.assertIsNotNone(refreshed_data)
		self.assertIsInstance(refreshed_data, list)

	def test_validate_uom_sat_code_valid(self):
		"""Test validation with valid SAT code"""
		# Test with known valid code
		is_valid, message, entry = self.catalog.validate_uom_sat_code("KGM")

		self.assertTrue(is_valid)
		self.assertEqual(message, "Código SAT válido")
		self.assertIsNotNone(entry)
		self.assertEqual(entry["clave"], "KGM")
		self.assertEqual(entry["nombre"], "Kilogramo")

	def test_validate_uom_sat_code_invalid(self):
		"""Test validation with invalid SAT code"""
		is_valid, message, entry = self.catalog.validate_uom_sat_code("INVALID")

		self.assertFalse(is_valid)
		self.assertIn("no encontrado", message)
		self.assertIsNone(entry)

	def test_validate_uom_sat_code_empty(self):
		"""Test validation with empty SAT code"""
		is_valid, message, entry = self.catalog.validate_uom_sat_code("")

		self.assertFalse(is_valid)
		self.assertEqual(message, "Código SAT requerido")
		self.assertIsNone(entry)

	def test_suggest_sat_code_exact_match(self):
		"""Test SAT code suggestions with exact match"""
		suggestions = self.catalog.suggest_sat_code_for_uom("Kilogramo")

		self.assertGreater(len(suggestions), 0)
		self.assertEqual(suggestions[0]["match_type"], "exact")
		self.assertEqual(suggestions[0]["confidence"], 100)
		self.assertEqual(suggestions[0]["clave"], "KGM")

	def test_suggest_sat_code_partial_match(self):
		"""Test SAT code suggestions with partial match"""
		suggestions = self.catalog.suggest_sat_code_for_uom("kilo")

		self.assertGreater(len(suggestions), 0)
		# Should find Kilogramo as partial match
		found_kg = any(s["clave"] == "KGM" for s in suggestions)
		self.assertTrue(found_kg)

	def test_suggest_sat_code_no_match(self):
		"""Test SAT code suggestions with no match"""
		suggestions = self.catalog.suggest_sat_code_for_uom("NONEXISTENT_UNIT")

		self.assertEqual(len(suggestions), 0)

	def test_suggest_sat_code_limits_results(self):
		"""Test that suggestions are limited to top 5"""
		suggestions = self.catalog.suggest_sat_code_for_uom("a")  # Very broad search

		self.assertLessEqual(len(suggestions), 5)

	@patch("facturacion_mexico.uom_sat.uom_sat_catalog.frappe.get_all")
	def test_sync_uom_with_sat_codes_dry_run(self, mock_get_all):
		"""Test UOM synchronization in dry run mode"""
		# Setup mock data
		mock_uoms = [
			{"name": "UOM1", "uom_name": "Kilogramo", "custom_clave_unidad_sat": ""},
			{"name": "UOM2", "uom_name": "Gramo", "custom_clave_unidad_sat": None},
		]
		mock_get_all.return_value = mock_uoms

		# Test dry run
		results = self.catalog.sync_uom_with_sat_codes(dry_run=True)

		self.assertTrue(results["dry_run"])
		self.assertEqual(results["processed"], 2)
		self.assertEqual(results["updated"], 0)  # No actual updates in dry run
		self.assertGreater(len(results["suggestions"]), 0)

	@patch("facturacion_mexico.uom_sat.uom_sat_catalog.frappe.get_all")
	@patch("facturacion_mexico.uom_sat.uom_sat_catalog.frappe.db.set_value")
	@patch("facturacion_mexico.uom_sat.uom_sat_catalog.frappe.db.commit")
	def test_sync_uom_with_sat_codes_real_run(self, mock_commit, mock_set_value, mock_get_all):
		"""Test UOM synchronization in real run mode"""
		# Setup mock data
		mock_uoms = [
			{"name": "UOM1", "uom_name": "Kilogramo", "custom_clave_unidad_sat": ""},
		]
		mock_get_all.return_value = mock_uoms

		# Test real run
		results = self.catalog.sync_uom_with_sat_codes(dry_run=False)

		self.assertFalse(results["dry_run"])
		self.assertEqual(results["processed"], 1)

		# Verify database calls were made for high confidence suggestions
		if results["updated"] > 0:
			mock_set_value.assert_called()
			mock_commit.assert_called_once()

	def test_validate_sales_invoice_uom_codes_valid(self):
		"""Test sales invoice UOM validation with valid codes"""
		# Create mock sales invoice
		mock_invoice = Mock()
		mock_item = Mock()
		mock_item.item_code = "ITEM001"
		mock_item.uom = "Kg"
		mock_invoice.items = [mock_item]

		# Mock frappe.db.get_value to return valid SAT code
		with patch("facturacion_mexico.uom_sat.uom_sat_catalog.frappe.db.get_value") as mock_get_value:
			mock_get_value.return_value = "KGM"

			is_valid, errors = self.catalog.validate_sales_invoice_uom_codes(mock_invoice)

			self.assertTrue(is_valid)
			self.assertEqual(len(errors), 0)

	def test_validate_sales_invoice_uom_codes_missing_sat_code(self):
		"""Test sales invoice UOM validation with missing SAT code"""
		# Create mock sales invoice
		mock_invoice = Mock()
		mock_item = Mock()
		mock_item.item_code = "ITEM001"
		mock_item.uom = "Kg"
		mock_invoice.items = [mock_item]

		# Mock frappe.db.get_value to return None (no SAT code)
		with patch("facturacion_mexico.uom_sat.uom_sat_catalog.frappe.db.get_value") as mock_get_value:
			mock_get_value.return_value = None

			is_valid, errors = self.catalog.validate_sales_invoice_uom_codes(mock_invoice)

			self.assertFalse(is_valid)
			self.assertEqual(len(errors), 1)
			self.assertIn("no tiene código SAT", errors[0])

	def test_validate_sales_invoice_uom_codes_invalid_sat_code(self):
		"""Test sales invoice UOM validation with invalid SAT code"""
		# Create mock sales invoice
		mock_invoice = Mock()
		mock_item = Mock()
		mock_item.item_code = "ITEM001"
		mock_item.uom = "Kg"
		mock_invoice.items = [mock_item]

		# Mock frappe.db.get_value to return invalid SAT code
		with patch("facturacion_mexico.uom_sat.uom_sat_catalog.frappe.db.get_value") as mock_get_value:
			mock_get_value.return_value = "INVALID"

			is_valid, errors = self.catalog.validate_sales_invoice_uom_codes(mock_invoice)

			self.assertFalse(is_valid)
			self.assertEqual(len(errors), 1)
			self.assertIn("no encontrado", errors[0])

	def test_load_sat_catalog_structure(self):
		"""Test that loaded SAT catalog has proper structure"""
		catalog_data = self.catalog._load_sat_catalog()

		self.assertIsInstance(catalog_data, list)
		self.assertGreater(len(catalog_data), 0)

		# Verify structure of catalog entries
		for entry in catalog_data:
			self.assertIn("clave", entry)
			self.assertIn("nombre", entry)
			self.assertIn("descripcion", entry)
			self.assertIn("simbolo", entry)
			self.assertIn("activo", entry)

			# Verify data types
			self.assertIsInstance(entry["clave"], str)
			self.assertIsInstance(entry["nombre"], str)
			self.assertIsInstance(entry["activo"], bool)

	def test_load_sat_catalog_contains_essential_units(self):
		"""Test that catalog contains essential SAT units"""
		catalog_data = self.catalog._load_sat_catalog()

		# Extract all codes
		codes = [entry["clave"] for entry in catalog_data]

		# Verify essential units are present
		essential_codes = ["KGM", "H87", "MTR", "LTR", "SEC", "NA"]
		for code in essential_codes:
			self.assertIn(code, codes, f"Essential SAT code {code} not found in catalog")

	@patch("facturacion_mexico.uom_sat.uom_sat_catalog.frappe.log_error")
	def test_error_handling_in_validate_uom_sat_code(self, mock_log_error):
		"""Test error handling in validate_uom_sat_code"""
		# Force an exception by patching get_sat_catalog
		with patch.object(self.catalog, "get_sat_catalog") as mock_get_catalog:
			mock_get_catalog.side_effect = Exception("Test error")

			is_valid, message, entry = self.catalog.validate_uom_sat_code("KGM")

			self.assertFalse(is_valid)
			self.assertIn("Error de validación", message)
			self.assertIsNone(entry)
			mock_log_error.assert_called_once()

	@patch("facturacion_mexico.uom_sat.uom_sat_catalog.frappe.log_error")
	def test_error_handling_in_suggest_sat_code(self, mock_log_error):
		"""Test error handling in suggest_sat_code_for_uom"""
		# Force an exception
		with patch.object(self.catalog, "get_sat_catalog") as mock_get_catalog:
			mock_get_catalog.side_effect = Exception("Test error")

			suggestions = self.catalog.suggest_sat_code_for_uom("test")

			self.assertEqual(len(suggestions), 0)
			mock_log_error.assert_called_once()


class TestUOMSATCatalogAPIs(unittest.TestCase):
	"""Test UOM SAT Catalog APIs"""

	@classmethod
	def setUpClass(cls):
		"""Set up test environment"""
		frappe.set_user("Administrator")

	@patch("facturacion_mexico.uom_sat.uom_sat_catalog.UOMSATCatalog")
	def test_get_sat_uom_catalog_api_success(self, mock_catalog_class):
		"""Test get_sat_uom_catalog API success"""
		from facturacion_mexico.uom_sat.uom_sat_catalog import get_sat_uom_catalog

		# Setup mock
		mock_catalog = Mock()
		mock_catalog.get_sat_catalog.return_value = [{"clave": "KGM"}]
		mock_catalog_class.return_value = mock_catalog

		# Test
		result = get_sat_uom_catalog()

		self.assertTrue(result["success"])
		self.assertEqual(result["count"], 1)
		self.assertEqual(len(result["data"]), 1)

	@patch("facturacion_mexico.uom_sat.uom_sat_catalog.UOMSATCatalog")
	def test_validate_sat_code_api_success(self, mock_catalog_class):
		"""Test validate_sat_code API success"""
		from facturacion_mexico.uom_sat.uom_sat_catalog import validate_sat_code

		# Setup mock
		mock_catalog = Mock()
		mock_catalog.validate_uom_sat_code.return_value = (True, "Valid", {"clave": "KGM"})
		mock_catalog_class.return_value = mock_catalog

		# Test
		result = validate_sat_code("KGM")

		self.assertTrue(result["success"])
		self.assertTrue(result["valid"])
		self.assertEqual(result["message"], "Valid")
		self.assertIsNotNone(result["entry"])

	@patch("facturacion_mexico.uom_sat.uom_sat_catalog.UOMSATCatalog")
	def test_suggest_sat_codes_api_success(self, mock_catalog_class):
		"""Test suggest_sat_codes API success"""
		from facturacion_mexico.uom_sat.uom_sat_catalog import suggest_sat_codes

		# Setup mock
		mock_catalog = Mock()
		mock_catalog.suggest_sat_code_for_uom.return_value = [{"clave": "KGM", "confidence": 100}]
		mock_catalog_class.return_value = mock_catalog

		# Test
		result = suggest_sat_codes("kilogramo")

		self.assertTrue(result["success"])
		self.assertEqual(result["count"], 1)
		self.assertEqual(len(result["suggestions"]), 1)

	@patch("facturacion_mexico.uom_sat.uom_sat_catalog.UOMSATCatalog")
	def test_sync_uom_sat_codes_api_success(self, mock_catalog_class):
		"""Test sync_uom_sat_codes API success"""
		from facturacion_mexico.uom_sat.uom_sat_catalog import sync_uom_sat_codes

		# Setup mock
		mock_catalog = Mock()
		mock_catalog.sync_uom_with_sat_codes.return_value = {"processed": 5, "updated": 3, "errors": 0}
		mock_catalog_class.return_value = mock_catalog

		# Test
		result = sync_uom_sat_codes(dry_run=True)

		self.assertTrue(result["success"])
		self.assertEqual(result["processed"], 5)
		self.assertEqual(result["updated"], 3)
		self.assertEqual(result["errors"], 0)

	@patch("facturacion_mexico.uom_sat.uom_sat_catalog.UOMSATCatalog")
	def test_validate_invoice_uom_sat_codes_hook_success(self, mock_catalog_class):
		"""Test validate_invoice_uom_sat_codes hook function success"""
		from facturacion_mexico.uom_sat.uom_sat_catalog import validate_invoice_uom_sat_codes

		# Setup mock
		mock_catalog = Mock()
		mock_catalog.validate_sales_invoice_uom_codes.return_value = (True, [])
		mock_catalog_class.return_value = mock_catalog

		# Test
		mock_invoice = Mock()
		is_valid, errors = validate_invoice_uom_sat_codes(mock_invoice)

		self.assertTrue(is_valid)
		self.assertEqual(len(errors), 0)


if __name__ == "__main__":
	unittest.main()
