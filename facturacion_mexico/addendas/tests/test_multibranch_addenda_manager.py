# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Test Multibranch Addenda Manager - Sprint 6 Phase 2
Tests para integración sistema Addendas con Multi-Sucursal
"""

import unittest
from unittest.mock import Mock, patch

import frappe

from facturacion_mexico.addendas.multibranch_addenda_manager import MultibranchAddendaManager


class TestMultibranchAddendaManager(unittest.TestCase):
	"""Test Multibranch Addenda Manager functionality"""

	@classmethod
	def setUpClass(cls):
		"""Set up test environment"""
		frappe.set_user("Administrator")
		cls.company = "Test Company"
		cls.branch = "Test Branch"
		cls.customer = "Test Customer"

	def setUp(self):
		"""Set up each test"""
		self.manager = MultibranchAddendaManager(self.company, self.branch)

	def test_manager_initialization(self):
		"""Test manager initialization"""
		self.assertEqual(self.manager.company, self.company)
		self.assertEqual(self.manager.branch, self.branch)
		self.assertIsNotNone(self.manager.branch_manager)

	@patch("facturacion_mexico.addendas.multibranch_addenda_manager.frappe.get_all")
	def test_get_available_addenda_types_for_branch_no_branch(self, mock_get_all):
		"""Test getting addenda types without specific branch"""
		# Setup mock
		mock_types = [{"name": "Type1", "description": "Test Type 1", "requires_specific_certificate": False}]
		mock_get_all.return_value = mock_types

		# Test without branch
		manager_no_branch = MultibranchAddendaManager(self.company)
		result = manager_no_branch.get_available_addenda_types_for_branch()

		self.assertEqual(result, mock_types)
		mock_get_all.assert_called_once()

	@patch("facturacion_mexico.addendas.multibranch_addenda_manager.frappe.get_all")
	@patch.object(MultibranchAddendaManager, "_get_branch_certificate_status")
	def test_get_available_addenda_types_with_branch(self, mock_cert_status, mock_get_all):
		"""Test getting addenda types for specific branch"""
		# Setup mocks
		mock_types = [{"name": "Type1", "description": "Test Type 1", "requires_specific_certificate": True}]
		mock_get_all.return_value = mock_types
		mock_cert_status.return_value = {"has_valid_certificates": True}

		# Test with branch
		result = self.manager.get_available_addenda_types_for_branch()

		self.assertEqual(len(result), 1)
		self.assertTrue(result[0]["branch_compatible"])
		self.assertTrue(result[0]["certificate_available"])

	@patch.object(MultibranchAddendaManager, "_get_base_addenda_configuration")
	@patch.object(MultibranchAddendaManager, "_get_branch_specific_overrides")
	def test_get_branch_addenda_configuration_success(self, mock_overrides, mock_base):
		"""Test successful branch addenda configuration retrieval"""
		# Setup mocks
		mock_base.return_value = {"configurations": [{"type": "base"}]}
		mock_overrides.return_value = {"configurations": [{"type": "override"}]}

		# Test
		result = self.manager.get_branch_addenda_configuration(self.customer)

		self.assertTrue(result["success"])
		self.assertEqual(result["branch"], self.branch)
		self.assertEqual(result["company"], self.company)
		self.assertEqual(result["customer"], self.customer)

	@patch.object(MultibranchAddendaManager, "_determine_invoice_branch")
	@patch.object(MultibranchAddendaManager, "_get_branch_certificate_status")
	def test_validate_addenda_for_branch_invoice_success(self, mock_cert_status, mock_branch):
		"""Test successful addenda validation for branch invoice"""
		# Setup mocks
		mock_invoice = Mock()
		mock_invoice.customer = self.customer
		mock_branch.return_value = self.branch
		mock_cert_status.return_value = {"has_valid_certificates": True}

		# Mock get_branch_addenda_configuration method
		with patch.object(self.manager, "get_branch_addenda_configuration") as mock_config:
			mock_config.return_value = {"success": True}

			# Test
			is_valid, message = self.manager.validate_addenda_for_branch_invoice(mock_invoice)

			self.assertTrue(is_valid)
			self.assertIn("válida", message)

	@patch.object(MultibranchAddendaManager, "_determine_invoice_branch")
	def test_validate_addenda_for_branch_invoice_no_branch(self, mock_branch):
		"""Test addenda validation when no branch specified"""
		# Setup mock
		mock_invoice = Mock()
		mock_branch.return_value = None

		# Test
		is_valid, message = self.manager.validate_addenda_for_branch_invoice(mock_invoice)

		self.assertTrue(is_valid)
		self.assertIn("No hay restricciones", message)

	def test_merge_configurations(self):
		"""Test configuration merging logic"""
		base_config = {"configurations": [{"type": "base", "value": 1}]}
		overrides = {"configurations": [{"type": "override", "value": 2}]}

		result = self.manager._merge_configurations(base_config, overrides)

		self.assertIn("configurations", result)
		configs = result["configurations"]
		self.assertEqual(len(configs), 2)
		self.assertEqual(configs[0]["type"], "override")  # Overrides first
		self.assertEqual(configs[1]["type"], "base")

	@patch("facturacion_mexico.addendas.multibranch_addenda_manager.frappe.get_cached_doc")
	def test_get_branch_context_for_addenda(self, mock_get_doc):
		"""Test getting branch context for addenda generation"""
		# Setup mock
		mock_branch_doc = Mock()
		mock_branch_doc.branch = "Test Branch Name"
		mock_branch_doc.get.side_effect = lambda key: {
			"fm_lugar_expedicion": "12345",
			"fm_serie_pattern": "A{####}",
		}.get(key)
		mock_get_doc.return_value = mock_branch_doc

		# Test
		mock_invoice = Mock()
		result = self.manager._get_branch_context_for_addenda(mock_invoice)

		self.assertEqual(result["branch_name"], "Test Branch Name")
		self.assertEqual(result["branch_code"], self.branch)
		self.assertEqual(result["lugar_expedicion"], "12345")
		self.assertEqual(result["serie_pattern"], "A{####}")
		self.assertEqual(result["company"], self.company)

	@patch("facturacion_mexico.addendas.multibranch_addenda_manager.frappe.db.get_value")
	def test_get_branch_specific_overrides_with_valid_json(self, mock_db_get):
		"""Test getting branch specific overrides with valid JSON"""
		# Setup mock
		mock_db_get.return_value = {"addenda_overrides": '{"configurations": [{"type": "branch_specific"}]}'}

		# Test
		result = self.manager._get_branch_specific_overrides(self.customer)

		self.assertIsNotNone(result)
		self.assertIn("configurations", result)
		self.assertEqual(result["configurations"][0]["type"], "branch_specific")

	@patch("facturacion_mexico.addendas.multibranch_addenda_manager.frappe.db.get_value")
	def test_get_branch_specific_overrides_with_invalid_json(self, mock_db_get):
		"""Test getting branch specific overrides with invalid JSON"""
		# Setup mock
		mock_db_get.return_value = {"addenda_overrides": "invalid json"}

		# Test
		result = self.manager._get_branch_specific_overrides(self.customer)

		self.assertIsNone(result)

	def test_is_addenda_type_compatible_with_branch(self):
		"""Test addenda type compatibility check"""
		# Test type requiring specific certificate
		addenda_type_req_cert = {"requires_specific_certificate": True}
		branch_certs_valid = {"has_valid_certificates": True}
		branch_certs_invalid = {"has_valid_certificates": False}

		self.assertTrue(
			self.manager._is_addenda_type_compatible_with_branch(addenda_type_req_cert, branch_certs_valid)
		)
		self.assertFalse(
			self.manager._is_addenda_type_compatible_with_branch(addenda_type_req_cert, branch_certs_invalid)
		)

		# Test type not requiring specific certificate
		addenda_type_no_req = {"requires_specific_certificate": False}
		self.assertTrue(
			self.manager._is_addenda_type_compatible_with_branch(addenda_type_no_req, branch_certs_invalid)
		)

	def test_determine_invoice_branch(self):
		"""Test determining invoice branch"""
		# Test with fm_branch attribute
		mock_invoice_with_branch = Mock()
		mock_invoice_with_branch.fm_branch = "Invoice Branch"

		result = self.manager._determine_invoice_branch(mock_invoice_with_branch)
		self.assertEqual(result, "Invoice Branch")

		# Test without fm_branch attribute (fallback)
		mock_invoice_no_branch = Mock()
		mock_invoice_no_branch.fm_branch = None

		result = self.manager._determine_invoice_branch(mock_invoice_no_branch)
		self.assertEqual(result, self.branch)

	@patch("facturacion_mexico.addendas.multibranch_addenda_manager.frappe.log_error")
	def test_error_handling_in_get_branch_addenda_configuration(self, mock_log_error):
		"""Test error handling in get_branch_addenda_configuration"""
		# Force an exception
		with patch.object(self.manager, "_get_base_addenda_configuration") as mock_base:
			mock_base.side_effect = Exception("Test error")

			result = self.manager.get_branch_addenda_configuration(self.customer)

			self.assertFalse(result["success"])
			self.assertIn("Error obteniendo configuración", result["message"])
			mock_log_error.assert_called_once()


class TestMultibranchAddendaManagerAPIs(unittest.TestCase):
	"""Test Multibranch Addenda Manager APIs"""

	@classmethod
	def setUpClass(cls):
		"""Set up test environment"""
		frappe.set_user("Administrator")

	@patch("facturacion_mexico.addendas.multibranch_addenda_manager.MultibranchAddendaManager")
	def test_get_branch_addenda_configuration_api_success(self, mock_manager_class):
		"""Test get_branch_addenda_configuration API success"""
		from facturacion_mexico.addendas.multibranch_addenda_manager import get_branch_addenda_configuration

		# Setup mock
		mock_manager = Mock()
		mock_manager.get_branch_addenda_configuration.return_value = {"success": True, "data": {}}
		mock_manager_class.return_value = mock_manager

		# Test
		result = get_branch_addenda_configuration("Test Company", "Test Branch", "Test Customer")

		self.assertTrue(result["success"])
		mock_manager_class.assert_called_once_with("Test Company", "Test Branch")
		mock_manager.get_branch_addenda_configuration.assert_called_once_with("Test Customer")

	@patch("facturacion_mexico.addendas.multibranch_addenda_manager.MultibranchAddendaManager")
	def test_get_available_addenda_types_for_branch_api_success(self, mock_manager_class):
		"""Test get_available_addenda_types_for_branch API success"""
		from facturacion_mexico.addendas.multibranch_addenda_manager import (
			get_available_addenda_types_for_branch,
		)

		# Setup mock
		mock_manager = Mock()
		mock_manager.get_available_addenda_types_for_branch.return_value = [{"type": "test"}]
		mock_manager_class.return_value = mock_manager

		# Test
		result = get_available_addenda_types_for_branch("Test Company", "Test Branch")

		self.assertTrue(result["success"])
		self.assertEqual(result["count"], 1)
		self.assertEqual(len(result["data"]), 1)

	@patch("facturacion_mexico.addendas.multibranch_addenda_manager.frappe.get_doc")
	@patch("facturacion_mexico.addendas.multibranch_addenda_manager.MultibranchAddendaManager")
	def test_validate_addenda_for_branch_invoice_api_success(self, mock_manager_class, mock_get_doc):
		"""Test validate_addenda_for_branch_invoice API success"""
		from facturacion_mexico.addendas.multibranch_addenda_manager import (
			validate_addenda_for_branch_invoice,
		)

		# Setup mocks
		mock_doc = Mock()
		mock_doc.company = "Test Company"
		mock_doc.get.return_value = "Test Branch"
		mock_get_doc.return_value = mock_doc

		mock_manager = Mock()
		mock_manager.validate_addenda_for_branch_invoice.return_value = (True, "Valid")
		mock_manager_class.return_value = mock_manager

		# Test
		result = validate_addenda_for_branch_invoice("SINV-001", "Test Branch")

		self.assertTrue(result["success"])
		self.assertTrue(result["valid"])
		self.assertEqual(result["message"], "Valid")


if __name__ == "__main__":
	unittest.main()
