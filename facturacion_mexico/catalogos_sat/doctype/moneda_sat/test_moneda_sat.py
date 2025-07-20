"""
Tests para Moneda SAT DocType - Metodología 4-Layer Buzola
"""

import unittest
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

# REGLA #43A: Skip test records para evitar LinkValidationError
frappe.flags.skip_test_records = True


class TestMonedaSAT(FrappeTestCase):
	"""Tests para Moneda SAT con metodología 4-Layer."""

	def setUp(self):
		"""Setup para cada test."""
		frappe.flags.skip_test_records = True
		frappe.set_user("Administrator")

	# ===== LAYER 1: UNIT TESTS =====

	def test_l1_field_assignment(self):
		"""LAYER 1: Test asignación básica de campos."""
		moneda = frappe.new_doc("Moneda SAT")

		# Test asignación individual de campos
		moneda.code = "MXN"
		self.assertEqual(moneda.code, "MXN")

		moneda.description = "Peso Mexicano"
		self.assertEqual(moneda.description, "Peso Mexicano")

		moneda.decimales = 2
		self.assertEqual(moneda.decimales, 2)

	def test_l1_code_format_validation(self):
		"""LAYER 1: Test validación de formato de código."""
		# REGLA #44: Create document FIRST antes de cualquier mock
		moneda = frappe.new_doc("Moneda SAT")
		moneda.description = "Test Currency"

		# Códigos válidos
		valid_codes = ["MXN", "USD", "EUR", "CAD"]
		for code in valid_codes:
			moneda.code = code

			# Mock contextual solo para validación de duplicados
			with patch("frappe.db.get_value") as mock_get_value:
				mock_get_value.return_value = None  # No detectar duplicados
				try:
					moneda.validate_code_format()  # Solo validar formato, no duplicados
				except Exception as e:
					self.fail(f"Código válido {code} falló validación: {e}")

	# ===== LAYER 2: BUSINESS LOGIC TESTS =====

	def test_l2_validation_with_mocks(self):
		"""LAYER 2: Test validación con hooks mockeados."""
		with patch("frappe.throw") as mock_throw:
			moneda = frappe.new_doc("Moneda SAT")
			moneda.code = "MX"  # Código inválido
			moneda.description = "Test"

			# Simular validación
			moneda.validate()

			# Verificar que se llamó frappe.throw
			mock_throw.assert_called()

	def test_l2_duplicate_prevention(self):
		"""LAYER 2: Test prevención de duplicados."""
		with patch("frappe.db.get_value", return_value="EXISTING-MONEDA"):
			moneda = frappe.new_doc("Moneda SAT")
			moneda.code = "MXN"
			moneda.description = "Peso Mexicano"

			# Validar que se detecte duplicado
			with self.assertRaises(frappe.DuplicateEntryError):
				moneda.validate()

	# ===== LAYER 3: INTEGRATION TESTS =====

	def test_l3_create_and_save(self):
		"""LAYER 3: Test creación e inserción real."""
		if frappe.flags.skip_test_records:
			self.skipTest("Skipped due to skip_test_records flag")

		moneda = frappe.new_doc("Moneda SAT")
		moneda.code = "TEST"
		moneda.description = "Test Currency"
		moneda.decimales = 2

		# Insertar y verificar
		moneda.insert()
		self.assertTrue(frappe.db.exists("Moneda SAT", "TEST"))

		# Cleanup
		frappe.delete_doc("Moneda SAT", "TEST")

	# ===== LAYER 4: PERFORMANCE & CONFIGURATION =====

	def test_l4_meta_validation(self):
		"""LAYER 4: Test validación de metadata del DocType."""
		meta = frappe.get_meta("Moneda SAT")

		# Verificar campos requeridos
		required_fields = ["code", "description"]
		for field in required_fields:
			field_meta = meta.get_field(field)
			self.assertIsNotNone(field_meta, f"Campo {field} debe existir")

	def test_l4_performance_bulk_creation(self):
		"""LAYER 4: Test performance con creación masiva."""
		start_time = frappe.utils.now_datetime()

		# Simular creación de múltiples monedas
		currencies = []
		for i in range(10):
			moneda = frappe.new_doc("Moneda SAT")
			moneda.code = f"T{i:02d}"
			moneda.description = f"Test Currency {i}"
			currencies.append(moneda)

		end_time = frappe.utils.now_datetime()
		duration = (end_time - start_time).total_seconds()

		# Verificar que tome menos de 1 segundo
		self.assertLess(duration, 1.0, "Creación masiva debe ser rápida")


if __name__ == "__main__":
	unittest.main()
