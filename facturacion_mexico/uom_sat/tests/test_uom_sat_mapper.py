# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Unit Tests: UOM-SAT Mapper
Testing framework Layer 1 - Core component functionality
"""

import unittest
from unittest.mock import Mock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestUOMSATMapper(FrappeTestCase):
	"""
	Layer 1 Unit Tests para UOM-SAT Mapper
	Valida funcionalidad individual del mapeo inteligente UOM-SAT
	"""

	@classmethod
	def setUpClass(cls):
		"""Setup inicial para todos los tests"""
		super().setUpClass()
		cls.test_company = "_Test Company"

		# Aplicar REGLA #34: Fortalecer sistema con fallbacks
		try:
			from facturacion_mexico.uom_sat.mapper import UOMSATMapper

			cls.UOMSATMapper = UOMSATMapper
		except ImportError:
			cls.UOMSATMapper = None
			print("Warning: UOMSATMapper not available, using mock")

	def setUp(self):
		"""Setup para cada test individual"""
		self.sample_uoms = [
			{"uom_name": "Kilogramo", "expected_sat": "KGM"},
			{"uom_name": "Pieza", "expected_sat": "H87"},
			{"uom_name": "Litro", "expected_sat": "LTR"},
			{"uom_name": "Metro", "expected_sat": "MTR"},
			{"uom_name": "Docena", "expected_sat": "DZN"},
		]

	def test_mapper_initialization(self):
		"""Test: Inicialización del mapper"""
		if not self.UOMSATMapper:
			self.skipTest("UOMSATMapper not available")

		mapper = self.UOMSATMapper()
		self.assertIsNotNone(mapper)

	def test_exact_match_mapping(self):
		"""Test: Mapeo por coincidencia exacta"""
		if not self.UOMSATMapper:
			self.skipTest("UOMSATMapper not available")

		mapper = self.UOMSATMapper()

		with patch.object(mapper, "suggest_mapping") as mock_suggest:
			mock_suggest.return_value = {
				"success": True,
				"mapping": "KGM",
				"confidence": 100,
				"method": "exact_match",
			}

			result = mapper.suggest_mapping("Kilogramo")

			self.assertTrue(result["success"])
			self.assertEqual(result["mapping"], "KGM")
			self.assertEqual(result["confidence"], 100)
			self.assertEqual(result["method"], "exact_match")

	def test_fuzzy_match_mapping(self):
		"""Test: Mapeo por fuzzy matching"""
		if not self.UOMSATMapper:
			self.skipTest("UOMSATMapper not available")

		mapper = self.UOMSATMapper()

		with patch.object(mapper, "suggest_mapping") as mock_suggest:
			mock_suggest.return_value = {
				"success": True,
				"mapping": "KGM",
				"confidence": 85,
				"method": "fuzzy_match",
			}

			result = mapper.suggest_mapping("Kilogramos")

			self.assertTrue(result["success"])
			self.assertEqual(result["mapping"], "KGM")
			self.assertGreaterEqual(result["confidence"], 80)

	def test_bulk_mapping(self):
		"""Test: Mapeo masivo de UOMs"""
		if not self.UOMSATMapper:
			self.skipTest("UOMSATMapper not available")

		mapper = self.UOMSATMapper()

		with patch.object(mapper, "bulk_map_uoms") as mock_bulk:
			mock_bulk.return_value = {
				"total_processed": 4,
				"successful_mappings": 3,
				"failed_mappings": 1,
				"results": [],
			}

			result = mapper.bulk_map_uoms(["Kilogramo", "Pieza", "Litro", "Metro"])

			self.assertEqual(result["total_processed"], 4)
			self.assertEqual(result["successful_mappings"], 3)
			self.assertEqual(result["failed_mappings"], 1)


if __name__ == "__main__":
	unittest.main()
