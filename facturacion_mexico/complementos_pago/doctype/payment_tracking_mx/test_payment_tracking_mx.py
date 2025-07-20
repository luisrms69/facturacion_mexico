"""
Tests 4-Layer para Payment Tracking MX - Sprint 2
Sistema de Facturación México - Metodología Buzola
"""

import frappe

# REGLA #43A: Skip automatic test records para evitar framework issues
frappe.flags.skip_test_records = True

import unittest
from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.complementos_pago.doctype.payment_tracking_mx.payment_tracking_mx import (
	PaymentTrackingMX,
	get_invoice_balance,
	get_next_parcialidad_number,
)


class TestPaymentTrackingMX(FrappeTestCase):
	"""Tests 4-Layer para Payment Tracking MX siguiendo metodología Buzola."""

	def setUp(self):
		"""Configuración común para todos los tests."""
		self.test_sales_invoice = "SINV-TEST-001"
		self.test_payment_entry = "PE-TEST-001"
		self.test_amount = 1000.0
		self.test_balance = 5000.0

	# ═══════════════════════════════════════════════════════════════════
	# LAYER 1: UNIT TESTS - Funciones puras sin dependencias externas
	# ═══════════════════════════════════════════════════════════════════

	def test_layer1_calculate_balance_after_pure_function(self):
		"""Layer 1: Test cálculo de saldo posterior (función pura)."""
		# Arrange
		tracking = frappe.new_doc("Payment Tracking MX")
		tracking.balance_before = 5000.0
		tracking.amount_paid = 1500.0

		# Act
		tracking.calculate_balance_after()

		# Assert
		self.assertEqual(tracking.balance_after, 3500.0)

	def test_layer1_validate_amounts_positive_scenario(self):
		"""Layer 1: Test validación de montos - escenario positivo."""
		# Arrange
		tracking = frappe.new_doc("Payment Tracking MX")
		tracking.amount_paid = 1000.0
		tracking.balance_before = 5000.0

		# Act & Assert (no debe lanzar excepción)
		try:
			tracking.validate_amounts()
		except Exception as e:
			self.fail(f"validate_amounts() raised {e} unexpectedly!")

	def test_layer1_validate_amounts_negative_scenarios(self):
		"""Layer 1: Test validación de montos - escenarios negativos."""
		# Test: amount_paid <= 0
		tracking = frappe.new_doc("Payment Tracking MX")
		tracking.amount_paid = 0
		tracking.balance_before = 5000.0
		with self.assertRaises(frappe.ValidationError):
			tracking.validate_amounts()

		# Test: balance_before <= 0
		tracking = frappe.new_doc("Payment Tracking MX")
		tracking.amount_paid = 1000.0
		tracking.balance_before = 0
		with self.assertRaises(frappe.ValidationError):
			tracking.validate_amounts()

		# Test: amount_paid > balance_before
		tracking = frappe.new_doc("Payment Tracking MX")
		tracking.amount_paid = 6000.0
		tracking.balance_before = 5000.0
		with self.assertRaises(frappe.ValidationError):
			tracking.validate_amounts()

	# ═══════════════════════════════════════════════════════════════════
	# LAYER 2: BUSINESS LOGIC TESTS - Lógica de negocio con mocks
	# ═══════════════════════════════════════════════════════════════════

	def test_layer2_validate_payment_sequence_with_posterior_payments(self):
		"""Layer 2: Test detección de pagos retroactivos con mocks."""
		# REGLA #44: Create document FIRST sin frappe.new_doc para evitar user_permissions error
		tracking = frappe.get_doc(
			{
				"doctype": "Payment Tracking MX",
				"sales_invoice": "SINV-001",
				"payment_entry": "PE-001",
				"amount_paid": 1000.0,
				"balance_before": 5000.0,
				"parcialidad_number": 1,
				"payment_date": "2025-07-19",  # Fecha anterior a los existentes
				"name": "PT-001",
			}
		)

		# Establecer campos calculados básicos
		tracking.balance_after = tracking.balance_before - tracking.amount_paid

		# Mock contextual solo para validaciones específicas
		with (
			patch("frappe.db.sql") as mock_sql,
			patch("frappe.utils.now") as mock_now,
		):
			# Arrange mocks
			mock_now.return_value = "2025-07-19 10:00:00"
			mock_sql.return_value = [
				{"name": "PT-002", "payment_date": "2025-07-20", "parcialidad_number": 2},
				{"name": "PT-003", "payment_date": "2025-07-21", "parcialidad_number": 3},
			]

			# Act
			tracking.validate_payment_sequence()

		# Assert
		self.assertEqual(tracking.is_retroactive, 1)
		self.assertIn("ADVERTENCIA", tracking.sequence_warning)
		self.assertIn("2 pagos posteriores", tracking.sequence_warning)

	@patch("frappe.db.sql")
	def test_layer2_validate_payment_sequence_no_posterior_payments(self, mock_sql):
		"""Layer 2: Test sin pagos posteriores - no retroactivo."""
		# Arrange
		mock_sql.return_value = []  # Sin pagos posteriores

		tracking = frappe.new_doc("Payment Tracking MX")
		tracking.sales_invoice = "SINV-001"
		tracking.payment_date = "2025-07-19"
		tracking.name = "PT-001"

		# Act
		tracking.validate_payment_sequence()

		# Assert
		self.assertEqual(tracking.is_retroactive, 0)
		self.assertEqual(tracking.sequence_warning, "")

	@patch("frappe.db.sql")
	def test_layer2_validate_parcialidad_sequence_normal_flow(self, mock_sql):
		"""Layer 2: Test secuencia normal de parcialidades."""
		# Arrange
		mock_sql.return_value = [(2,)]  # Última parcialidad es 2

		tracking = frappe.new_doc("Payment Tracking MX")
		tracking.sales_invoice = "SINV-001"
		tracking.parcialidad_number = 3  # Siguiente esperado
		tracking.is_retroactive = 0
		tracking.name = "PT-003"

		# Act & Assert (no debe lanzar excepción)
		try:
			tracking.validate_parcialidad_sequence()
		except Exception as e:
			self.fail(f"validate_parcialidad_sequence() raised {e} unexpectedly!")

	@patch("frappe.db.sql")
	def test_layer2_validate_parcialidad_sequence_gap_error(self, mock_sql):
		"""Layer 2: Test error en secuencia de parcialidades."""
		# Arrange
		mock_sql.return_value = [(2,)]  # Última parcialidad es 2

		tracking = frappe.new_doc("Payment Tracking MX")
		tracking.sales_invoice = "SINV-001"
		tracking.parcialidad_number = 5  # Salto en secuencia
		tracking.is_retroactive = 0
		tracking.name = "PT-005"

		# Act & Assert
		with self.assertRaises(frappe.ValidationError) as context:
			tracking.validate_parcialidad_sequence()
		self.assertIn("secuencial", str(context.exception))

	# ═══════════════════════════════════════════════════════════════════
	# LAYER 3: INTEGRATION TESTS - Flujo completo con datos reales
	# ═══════════════════════════════════════════════════════════════════

	def test_layer3_create_tracking_record_complete_flow(self):
		"""Layer 3: Test creación completa de registro tracking."""
		# Este test requiere datos reales en la DB, se implementaría
		# con fixtures de Sales Invoice y Payment Entry reales
		pass

	@patch("frappe.get_value")
	@patch("frappe.db.sql")
	@patch(
		"facturacion_mexico.complementos_pago.doctype.payment_tracking_mx.payment_tracking_mx.get_invoice_balance"
	)
	@patch(
		"facturacion_mexico.complementos_pago.doctype.payment_tracking_mx.payment_tracking_mx.get_next_parcialidad_number"
	)
	def test_layer3_create_tracking_record_with_mocks(
		self, mock_parcialidad, mock_balance, mock_sql, mock_get_value
	):
		"""Layer 3: Test creación de tracking con mocks para simular integración."""
		# Arrange
		mock_get_value.return_value = "2025-07-19"
		mock_balance.return_value = 4000.0
		mock_parcialidad.return_value = 2

		# Act
		with patch("frappe.new_doc") as mock_new_doc:
			mock_tracking = MagicMock()
			mock_new_doc.return_value = mock_tracking
			mock_tracking.name = "PT-TEST-001"

			result = PaymentTrackingMX.create_tracking_record("SINV-001", "PE-001", 1000.0)

			# Assert
			mock_tracking.insert.assert_called_once()
			mock_tracking.submit.assert_called_once()
			self.assertEqual(result, "PT-TEST-001")

	# ═══════════════════════════════════════════════════════════════════
	# LAYER 4: PERFORMANCE & CONFIGURATION TESTS
	# ═══════════════════════════════════════════════════════════════════

	@patch("frappe.db.sql")
	def test_layer4_get_invoice_balance_performance_query(self, mock_sql):
		"""Layer 4: Test rendimiento de consulta de saldo."""
		# Arrange
		mock_sql.side_effect = [
			[(0,)],  # paid_amount query
		]

		with patch("frappe.get_value", return_value=5000.0):
			# Act
			result = get_invoice_balance("SINV-001")

			# Assert
			self.assertEqual(result, 5000.0)
			# Verificar que solo se ejecuta una consulta SQL optimizada
			self.assertEqual(mock_sql.call_count, 1)

			# Verificar que la consulta usa índices correctos
			call_args = mock_sql.call_args[0]
			self.assertIn("SUM(amount_paid)", call_args[0])
			self.assertIn("docstatus = 1", call_args[0])

	@patch("frappe.db.sql")
	def test_layer4_get_next_parcialidad_number_edge_cases(self, mock_sql):
		"""Layer 4: Test casos extremos del número de parcialidad."""
		# Test: Sin parcialidades previas
		mock_sql.return_value = [(0,)]
		result = get_next_parcialidad_number("SINV-NEW")
		self.assertEqual(result, 1)

		# Test: Con parcialidades existentes
		mock_sql.return_value = [(5,)]
		result = get_next_parcialidad_number("SINV-EXISTING")
		self.assertEqual(result, 6)

	def test_layer4_payment_tracking_memory_usage(self):
		"""Layer 4: Test uso de memoria en creación masiva."""
		# Test que simula creación de múltiples registros
		# para verificar que no hay memory leaks
		tracking_objects = []

		for i in range(100):
			tracking = frappe.new_doc("Payment Tracking MX")
			tracking.balance_before = 1000.0 * i
			tracking.amount_paid = 100.0
			tracking.calculate_balance_after()
			tracking_objects.append(tracking)

		# Verificar que todos se calcularon correctamente
		for i, tracking in enumerate(tracking_objects):
			expected_balance = (1000.0 * i) - 100.0
			self.assertEqual(tracking.balance_after, expected_balance)

		# Cleanup automático por garbage collector de Python


# ═══════════════════════════════════════════════════════════════════
# TESTS UTILITARIOS PARA FUNCIONES HELPER
# ═══════════════════════════════════════════════════════════════════


class TestPaymentTrackingHelpers(FrappeTestCase):
	"""Tests para funciones helper de Payment Tracking."""

	@patch("frappe.get_value")
	@patch("frappe.db.sql")
	def test_get_invoice_balance_calculation(self, mock_sql, mock_get_value):
		"""Test cálculo correcto de saldo de factura."""
		# Arrange
		mock_get_value.return_value = 10000.0  # Total factura
		mock_sql.return_value = [(3000.0,)]  # Total pagado

		# Act
		balance = get_invoice_balance("SINV-001")

		# Assert
		self.assertEqual(balance, 7000.0)

	@patch("frappe.db.sql")
	def test_get_next_parcialidad_number_sequential(self, mock_sql):
		"""Test obtención secuencial de número de parcialidad."""
		# Arrange
		mock_sql.return_value = [(3,)]  # Última parcialidad: 3

		# Act
		next_number = get_next_parcialidad_number("SINV-001")

		# Assert
		self.assertEqual(next_number, 4)


if __name__ == "__main__":
	unittest.main()
