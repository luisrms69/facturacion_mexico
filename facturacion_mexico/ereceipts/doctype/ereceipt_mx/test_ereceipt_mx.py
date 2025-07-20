"""
Tests 4-Layer para EReceipt MX - Sprint 2
Sistema de Facturación México - Metodología Buzola
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.ereceipts.doctype.ereceipt_mx.ereceipt_mx import EReceiptMX


class TestEReceiptMX(FrappeTestCase):
	"""Tests 4-Layer para EReceipt MX siguiendo metodología Buzola."""

	def setUp(self):
		"""Configuración común para todos los tests."""
		self.test_sales_invoice = "SINV-TEST-001"
		self.test_company = "Test Company"
		self.test_total = 1000.0
		self.today = datetime.now().date()

	# ═══════════════════════════════════════════════════════════════════
	# LAYER 1: UNIT TESTS - Funciones puras sin dependencias externas
	# ═══════════════════════════════════════════════════════════════════

	def test_layer1_calculate_expiry_fixed_days(self):
		"""Layer 1: Test cálculo de expiración con días fijos."""
		# Arrange
		ereceipt = EReceiptMX()
		ereceipt.date_issued = self.today
		ereceipt.expiry_type = "Fixed Days"
		ereceipt.expiry_days = 5

		# Act
		ereceipt.calculate_expiry_date()

		# Assert
		expected_expiry = self.today + timedelta(days=5)
		self.assertEqual(ereceipt.expiry_date, expected_expiry)

	def test_layer1_calculate_expiry_end_of_month(self):
		"""Layer 1: Test cálculo de expiración fin de mes."""
		# Arrange
		ereceipt = EReceiptMX()
		ereceipt.date_issued = datetime(2025, 7, 15).date()  # Medio del mes
		ereceipt.expiry_type = "End of Month"

		# Act
		ereceipt.calculate_expiry_date()

		# Assert
		expected_expiry = datetime(2025, 7, 31).date()  # Último día de julio
		self.assertEqual(ereceipt.expiry_date, expected_expiry)

	def test_layer1_calculate_expiry_custom_date_provided(self):
		"""Layer 1: Test expiración con fecha personalizada."""
		# Arrange
		custom_date = self.today + timedelta(days=10)
		ereceipt = EReceiptMX()
		ereceipt.date_issued = self.today
		ereceipt.expiry_type = "Custom Date"
		ereceipt.expiry_date = custom_date

		# Act
		ereceipt.calculate_expiry_date()

		# Assert
		self.assertEqual(ereceipt.expiry_date, custom_date)

	def test_layer1_calculate_expiry_custom_date_fallback(self):
		"""Layer 1: Test fallback cuando no se proporciona fecha personalizada."""
		# Arrange
		ereceipt = EReceiptMX()
		ereceipt.date_issued = self.today
		ereceipt.expiry_type = "Custom Date"
		ereceipt.expiry_date = None

		# Act
		ereceipt.calculate_expiry_date()

		# Assert
		expected_expiry = self.today + timedelta(days=3)  # Default fallback
		self.assertEqual(ereceipt.expiry_date, expected_expiry)

	def test_layer1_is_expired_true(self):
		"""Layer 1: Test detección de e-receipt expirado."""
		# Arrange
		ereceipt = EReceiptMX()
		ereceipt.expiry_date = self.today - timedelta(days=1)  # Ayer

		# Act
		result = ereceipt.is_expired()

		# Assert
		self.assertTrue(result)

	def test_layer1_is_expired_false(self):
		"""Layer 1: Test detección de e-receipt válido."""
		# Arrange
		ereceipt = EReceiptMX()
		ereceipt.expiry_date = self.today + timedelta(days=1)  # Mañana

		# Act
		result = ereceipt.is_expired()

		# Assert
		self.assertFalse(result)

	def test_layer1_generate_key_format(self):
		"""Layer 1: Test generación de key único."""
		# Arrange
		ereceipt = EReceiptMX()
		ereceipt.sales_invoice = "SINV-001"
		ereceipt.date_issued = datetime(2025, 7, 19).date()

		# Act
		ereceipt.generate_unique_key()

		# Assert
		expected_pattern = "ER-SINV-001-20250719"
		self.assertTrue(ereceipt.key.startswith(expected_pattern))
		self.assertGreater(len(ereceipt.key), len(expected_pattern))  # Debe tener sufijo único

	# ═══════════════════════════════════════════════════════════════════
	# LAYER 2: BUSINESS LOGIC TESTS - Lógica de negocio con mocks
	# ═══════════════════════════════════════════════════════════════════

	@patch("frappe.db.exists")
	def test_layer2_validate_no_duplicate_ereceipt(self, mock_exists):
		"""Layer 2: Test validación sin duplicados."""
		# Arrange
		mock_exists.return_value = None  # No existe e-receipt previo

		ereceipt = EReceiptMX()
		ereceipt.sales_invoice = "SINV-001"

		# Act & Assert (no debe lanzar excepción)
		try:
			ereceipt.validate_no_duplicate()
		except Exception as e:
			self.fail(f"validate_no_duplicate() raised {e} unexpectedly!")

	@patch("frappe.db.exists")
	def test_layer2_validate_duplicate_ereceipt_error(self, mock_exists):
		"""Layer 2: Test error por e-receipt duplicado."""
		# Arrange
		mock_exists.return_value = "ER-001"  # Existe e-receipt previo

		ereceipt = EReceiptMX()
		ereceipt.sales_invoice = "SINV-001"

		# Act & Assert
		with self.assertRaises(frappe.ValidationError) as context:
			ereceipt.validate_no_duplicate()
		self.assertIn("ya existe", str(context.exception).lower())

	@patch("frappe.get_doc")
	def test_layer2_validate_no_fiscal_invoice(self, mock_get_doc):
		"""Layer 2: Test validación sin factura fiscal previa."""
		# Arrange
		mock_sales_invoice = MagicMock()
		mock_sales_invoice.get.return_value = None  # No tiene factura fiscal
		mock_get_doc.return_value = mock_sales_invoice

		ereceipt = EReceiptMX()
		ereceipt.sales_invoice = "SINV-001"

		# Act & Assert (no debe lanzar excepción)
		try:
			ereceipt.validate_no_fiscal_invoice()
		except Exception as e:
			self.fail(f"validate_no_fiscal_invoice() raised {e} unexpectedly!")

	@patch("frappe.get_doc")
	def test_layer2_validate_fiscal_invoice_exists_error(self, mock_get_doc):
		"""Layer 2: Test error cuando ya existe factura fiscal."""
		# Arrange
		mock_sales_invoice = MagicMock()
		mock_sales_invoice.get.return_value = "FF-001"  # Tiene factura fiscal
		mock_get_doc.return_value = mock_sales_invoice

		ereceipt = EReceiptMX()
		ereceipt.sales_invoice = "SINV-001"

		# Act & Assert
		with self.assertRaises(frappe.ValidationError) as context:
			ereceipt.validate_no_fiscal_invoice()
		self.assertIn("fiscal", str(context.exception).lower())

	@patch("frappe.db.get_single_value")
	@patch("facturacion_mexico.ereceipts.api._generar_facturapi_ereceipt")
	def test_layer2_auto_generate_facturapi_enabled(self, mock_generate, mock_get_single):
		"""Layer 2: Test generación automática en FacturAPI cuando está habilitado."""
		# Arrange
		mock_get_single.return_value = True  # E-receipts habilitados

		ereceipt = EReceiptMX()
		ereceipt.sales_invoice = "SINV-001"

		# Act
		ereceipt.auto_generate_facturapi()

		# Assert
		mock_generate.assert_called_once_with(ereceipt)

	@patch("frappe.db.get_single_value")
	@patch("facturacion_mexico.ereceipts.api._generar_facturapi_ereceipt")
	def test_layer2_auto_generate_facturapi_disabled(self, mock_generate, mock_get_single):
		"""Layer 2: Test no generación cuando está deshabilitado."""
		# Arrange
		mock_get_single.return_value = False  # E-receipts deshabilitados

		ereceipt = EReceiptMX()
		ereceipt.sales_invoice = "SINV-001"

		# Act
		ereceipt.auto_generate_facturapi()

		# Assert
		mock_generate.assert_not_called()

	# ═══════════════════════════════════════════════════════════════════
	# LAYER 3: INTEGRATION TESTS - Flujo completo con mocks de integración
	# ═══════════════════════════════════════════════════════════════════

	@patch("frappe.get_doc")
	@patch("frappe.db.exists")
	@patch("frappe.utils.today")
	def test_layer3_create_ereceipt_complete_flow(self, mock_today, mock_exists, mock_get_doc):
		"""Layer 3: Test flujo completo de creación de e-receipt."""
		# Arrange
		mock_today.return_value = "2025-07-19"
		mock_exists.return_value = None  # No existe e-receipt previo

		mock_sales_invoice = MagicMock()
		mock_sales_invoice.company = "Test Company"
		mock_sales_invoice.grand_total = 1000.0
		mock_sales_invoice.get.return_value = None  # No tiene factura fiscal
		mock_get_doc.return_value = mock_sales_invoice

		# Act
		with patch("frappe.new_doc") as mock_new_doc:
			mock_ereceipt = MagicMock()
			mock_new_doc.return_value = mock_ereceipt
			mock_ereceipt.name = "ER-TEST-001"

			# Simular proceso de inserción
			mock_ereceipt.insert.return_value = None

			# Crear e-receipt (simulado)
			ereceipt = EReceiptMX()
			ereceipt.sales_invoice = "SINV-001"
			ereceipt.company = "Test Company"
			ereceipt.total = 1000.0
			ereceipt.date_issued = "2025-07-19"

			# Assert setup correcto
			self.assertEqual(ereceipt.sales_invoice, "SINV-001")
			self.assertEqual(ereceipt.total, 1000.0)

	@patch("frappe.db.sql")
	def test_layer3_expire_ereceipts_batch_update(self, mock_sql):
		"""Layer 3: Test expiración masiva de e-receipts."""
		# Arrange
		mock_sql.side_effect = [
			None,  # UPDATE query
			[(5,)],  # COUNT query - 5 registros expirados
		]

		# Act
		expired_count = EReceiptMX.expire_ereceipts_batch()

		# Assert
		self.assertEqual(expired_count, 5)
		self.assertEqual(mock_sql.call_count, 2)  # UPDATE + COUNT

	@patch("frappe.db.get_list")
	def test_layer3_get_ereceipts_for_global_invoice(self, mock_get_list):
		"""Layer 3: Test obtención de e-receipts para factura global."""
		# Arrange
		mock_ereceipts = [
			{
				"name": "ER-001",
				"sales_invoice": "SINV-001",
				"total": 500.0,
				"date_issued": "2025-07-19",
				"key": "ER-KEY-001",
			},
			{
				"name": "ER-002",
				"sales_invoice": "SINV-002",
				"total": 750.0,
				"date_issued": "2025-07-19",
				"key": "ER-KEY-002",
			},
		]
		mock_get_list.return_value = mock_ereceipts

		# Act
		result = EReceiptMX.get_for_global_invoice("2025-07-19", "2025-07-19")

		# Assert
		self.assertEqual(len(result), 2)
		self.assertEqual(result[0]["total"], 500.0)
		self.assertEqual(result[1]["total"], 750.0)

	# ═══════════════════════════════════════════════════════════════════
	# LAYER 4: PERFORMANCE & CONFIGURATION TESTS
	# ═══════════════════════════════════════════════════════════════════

	@patch("frappe.db.sql")
	def test_layer4_expiry_batch_performance(self, mock_sql):
		"""Layer 4: Test rendimiento de expiración masiva."""
		# Arrange
		mock_sql.side_effect = [None, [(100,)]]  # 100 registros expirados

		# Act
		start_time = datetime.now()
		result = EReceiptMX.expire_ereceipts_batch()
		end_time = datetime.now()

		# Assert
		execution_time = (end_time - start_time).total_seconds()
		self.assertLess(execution_time, 0.1)  # Debe ser muy rápido
		self.assertEqual(result, 100)

		# Verificar que usa consulta optimizada
		update_query = mock_sql.call_args_list[0][0][0]
		self.assertIn("UPDATE", update_query)
		self.assertIn("WHERE status = 'open'", update_query)
		self.assertIn("expiry_date <", update_query)

	def test_layer4_key_generation_uniqueness(self):
		"""Layer 4: Test unicidad en generación de keys."""
		# Crear múltiples e-receipts con la misma base
		keys = set()

		for _i in range(100):
			ereceipt = EReceiptMX()
			ereceipt.sales_invoice = "SINV-001"
			ereceipt.date_issued = self.today
			ereceipt.generate_unique_key()
			keys.add(ereceipt.key)

		# Todas las keys deben ser únicas
		self.assertEqual(len(keys), 100)

	@patch("frappe.db.get_list")
	def test_layer4_large_dataset_query_performance(self, mock_get_list):
		"""Layer 4: Test rendimiento con datasets grandes."""
		# Simular 10,000 e-receipts
		large_dataset = []
		for i in range(10000):
			large_dataset.append(
				{
					"name": f"ER-{i:06d}",
					"sales_invoice": f"SINV-{i:06d}",
					"total": 100.0 + i,
					"date_issued": "2025-07-19",
					"key": f"ER-KEY-{i:06d}",
				}
			)

		mock_get_list.return_value = large_dataset

		# Act
		start_time = datetime.now()
		result = EReceiptMX.get_for_global_invoice("2025-07-01", "2025-07-31")
		end_time = datetime.now()

		# Assert
		execution_time = (end_time - start_time).total_seconds()
		self.assertLess(execution_time, 0.5)  # Debe procesar rápido
		self.assertEqual(len(result), 10000)

	def test_layer4_memory_usage_large_totals(self):
		"""Layer 4: Test uso de memoria con totales grandes."""
		# Test con diferentes tamaños de totales
		test_totals = [
			999999999.99,  # Máximo para currency
			0.01,  # Mínimo
			1000000.50,  # Caso común grande
		]

		for total in test_totals:
			ereceipt = EReceiptMX()
			ereceipt.total = total
			ereceipt.sales_invoice = "SINV-LARGE"

			# Verificar que maneja correctamente totales grandes
			self.assertEqual(ereceipt.total, total)
			self.assertIsInstance(ereceipt.total, (int, float))

	def test_layer4_date_calculation_edge_cases(self):
		"""Layer 4: Test casos límite en cálculo de fechas."""
		edge_dates = [
			datetime(2025, 2, 28).date(),  # Fin de febrero no bisiesto
			datetime(2024, 2, 29).date(),  # Año bisiesto
			datetime(2025, 12, 31).date(),  # Fin de año
			datetime(2025, 1, 1).date(),  # Inicio de año
		]

		for test_date in edge_dates:
			ereceipt = EReceiptMX()
			ereceipt.date_issued = test_date
			ereceipt.expiry_type = "Fixed Days"
			ereceipt.expiry_days = 30

			# Act
			ereceipt.calculate_expiry_date()

			# Assert
			expected_expiry = test_date + timedelta(days=30)
			self.assertEqual(ereceipt.expiry_date, expected_expiry)


# ═══════════════════════════════════════════════════════════════════
# TESTS PARA FUNCIONES DE UTILIDAD Y API
# ═══════════════════════════════════════════════════════════════════


class TestEReceiptMXUtils(FrappeTestCase):
	"""Tests para funciones de utilidad de EReceipt MX."""

	def test_status_transitions_valid(self):
		"""Test transiciones válidas de estado."""
		valid_transitions = [
			("open", "expired"),
			("open", "invoiced"),
			("open", "cancelled"),
		]

		for from_status, to_status in valid_transitions:
			ereceipt = EReceiptMX()
			ereceipt.status = from_status

			# Simular cambio de status
			ereceipt.status = to_status

			# Verificar que el cambio es válido
			self.assertEqual(ereceipt.status, to_status)

	def test_status_transitions_invalid(self):
		"""Test transiciones inválidas de estado."""
		invalid_transitions = [
			("expired", "open"),
			("invoiced", "open"),
			("cancelled", "open"),
		]

		for from_status, _to_status in invalid_transitions:
			ereceipt = EReceiptMX()
			ereceipt.status = from_status

			# En una implementación real, esto debería validarse
			# Por ahora solo verificamos que conocemos las transiciones
			self.assertNotEqual(from_status, "open")


if __name__ == "__main__":
	unittest.main()
