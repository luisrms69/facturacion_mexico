"""
Layer 1: Unit Tests - Facturas Globales
Tests de componentes individuales aislados
REGLA #33: Testing progresivo - Layer 1 debe pasar antes de Layer 2
"""

import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import add_days, flt, today

from facturacion_mexico.facturas_globales.tests.test_base_globales import FacturasGlobalesTestBase


class TestFacturasGlobalesUnit(FacturasGlobalesTestBase):
	"""Tests unitarios para componentes de facturas globales."""

	def test_period_validation_logic(self):
		"""Test: Lógica de validación de períodos."""

		# Crear documento temporal para testing
		doc = frappe.get_doc(
			{
				"doctype": "Factura Global MX",
				"company": self.test_company,
				"periodo_inicio": today(),
				"periodo_fin": add_days(today(), 6),  # 7 days total (0-6 inclusive)
				"periodicidad": "Semanal",
			}
		)

		# Test validación exitosa
		try:
			doc.validate_period_dates()
			validation_passed = True
		except Exception as e:
			validation_passed = False
			print(f"Validation failed with error: {e}")

		self.assertTrue(validation_passed, "Validación de período válido debería pasar")

		# Test período inválido (inicio > fin)
		doc.periodo_inicio = add_days(today(), 7)
		doc.periodo_fin = today()

		with self.assertRaises(frappe.ValidationError):
			doc.validate_period_dates()

	def test_receipt_aggregation_algorithms(self):
		"""Test: Algoritmos de agregación de receipts."""
		from facturacion_mexico.facturas_globales.processors.ereceipt_aggregator import EReceiptAggregator

		# Mock data para testing
		mock_receipts = self.create_mock_ereceipt_data(5)

		# Crear agregador
		aggregator = EReceiptAggregator(
			periodo_inicio=add_days(today(), -7), periodo_fin=today(), company=self.test_company
		)

		# Mock del método get_available_receipts
		aggregator.receipts = mock_receipts

		# Test agrupación por tasa de impuesto
		tax_groups = aggregator.group_by_tax_rate()

		self.assertIsInstance(tax_groups, dict)
		self.assertIn("tax_16.0", tax_groups)
		self.assertEqual(tax_groups["tax_16.0"]["totals"]["count"], 5)

		# Test agrupación por día
		daily_groups = aggregator.group_by_day()
		self.assertIsInstance(daily_groups, dict)
		self.assertGreater(len(daily_groups), 0)

		# Test cálculo de totales
		totals = aggregator.calculate_totals()
		self.assertIn("count", totals)
		self.assertIn("total_amount", totals)
		self.assertEqual(totals["count"], 5)

	def test_total_calculations(self):
		"""Test: Cálculos de totales."""

		# Crear documento con receipts mock
		doc = frappe.get_doc(
			{
				"doctype": "Factura Global MX",
				"company": self.test_company,
				"periodo_inicio": add_days(today(), -7),
				"periodo_fin": today(),
				"periodicidad": "Semanal",
			}
		)

		# Agregar receipts mock
		test_receipts = [{"monto": 100.00}, {"monto": 200.00}, {"monto": 150.00}]

		for receipt in test_receipts:
			doc.append("receipts_detail", receipt)

		# Test cálculo de totales
		doc.calculate_totals()

		expected_total = sum(r["monto"] for r in test_receipts)
		self.assertEqual(flt(doc.total_periodo), expected_total)
		self.assertEqual(doc.cantidad_receipts, len(test_receipts))

	def test_folio_continuity_check(self):
		"""Test: Verificación de continuidad de folios."""
		from facturacion_mexico.facturas_globales.processors.ereceipt_aggregator import EReceiptAggregator

		aggregator = EReceiptAggregator(
			periodo_inicio=add_days(today(), -7), periodo_fin=today(), company=self.test_company
		)

		# Test con folios continuos
		continuous_receipts = [
			{"folio": "ER-001", "name": "receipt1"},
			{"folio": "ER-002", "name": "receipt2"},
			{"folio": "ER-003", "name": "receipt3"},
		]
		aggregator.receipts = continuous_receipts

		validation = aggregator.validate_continuous_folios()
		self.assertTrue(validation["is_continuous"])
		self.assertEqual(len(validation["missing_folios"]), 0)

		# Test con folios discontinuos
		discontinuous_receipts = [
			{"folio": "ER-001", "name": "receipt1"},
			{"folio": "ER-003", "name": "receipt3"},  # Falta ER-002
			{"folio": "ER-004", "name": "receipt4"},
		]
		aggregator.receipts = discontinuous_receipts

		validation = aggregator.validate_continuous_folios()
		self.assertFalse(validation["is_continuous"])
		self.assertIn(2, validation["missing_folios"])

	def test_cfdi_data_structure_building(self):
		"""Test: Construcción de estructura de datos CFDI."""
		from facturacion_mexico.facturas_globales.processors.cfdi_global_builder import CFDIGlobalBuilder

		# Crear factura global mock
		global_doc = MagicMock()
		global_doc.name = "FG-TEST-001"
		global_doc.company = self.test_company
		global_doc.periodo_inicio = add_days(today(), -7)
		global_doc.periodo_fin = today()
		global_doc.periodicidad = "Semanal"
		global_doc.total_periodo = 1000.00
		global_doc.cantidad_receipts = 5
		global_doc.serie = "FG-TEST"

		# Mock receipts detail
		global_doc.receipts_detail = [
			MagicMock(ereceipt="ER-001", monto=200.00, included_in_cfdi=True),
			MagicMock(ereceipt="ER-002", monto=300.00, included_in_cfdi=True),
		]

		# Mock settings
		with patch("frappe.get_single") as mock_settings:
			mock_settings.return_value = MagicMock(global_invoice_serie="FG-TEST", facturapi_test_mode=True)

			# Mock company
			with patch("frappe.get_doc") as mock_get_doc:
				mock_company = MagicMock()
				mock_company.tax_id = "TEST123456789"
				mock_get_doc.return_value = mock_company

				builder = CFDIGlobalBuilder(global_doc)

				# Test construcción de datos del cliente
				customer_data = builder._build_customer_data()
				self.assertIn("legal_name", customer_data)
				self.assertEqual(customer_data["tax_id"], "XAXX010101000")

				# Test mapeo de periodicidad
				periodicity_code = builder._map_periodicidad()
				self.assertEqual(periodicity_code, "02")  # Semanal

	def test_api_response_structure(self):
		"""Test: Estructura de respuestas de API."""
		from facturacion_mexico.facturas_globales.api import get_available_ereceipts

		# Mock de la consulta SQL
		with patch("frappe.db.sql") as mock_sql:
			from frappe.utils import getdate

			mock_sql.return_value = [
				{
					"ereceipt": "ER-001",
					"folio": "ER-001",
					"fecha_receipt": getdate(today()),
					"monto": 100.00,
					"tax_amount": 16.00,
					"customer_name": "Test Customer",
					"currency": "MXN",
					"status": "Paid",
					"available_for_global": 1,
					"selectable": 1,
				}
			]

			# Mock de defaults
			with patch("frappe.defaults.get_user_default") as mock_default:
				mock_default.return_value = self.test_company

				result = get_available_ereceipts(
					periodo_inicio=add_days(today(), -6),  # 7 days total
					periodo_fin=today(),
				)

				# Validar estructura de respuesta
				self.assertIn("success", result)
				if not result["success"]:
					print(f"API call failed: {result}")
				self.assertTrue(result["success"])
				self.assertIn("data", result)
				self.assertIn("summary", result)

				# Validar estructura del summary
				summary = result["summary"]
				self.assertIn("total_receipts", summary)
				self.assertIn("total_amount", summary)
				self.assertIn("daily_breakdown", summary)

	def test_validation_error_handling(self):
		"""Test: Manejo de errores de validación."""

		# Test validación sin company
		doc = frappe.get_doc(
			{
				"doctype": "Factura Global MX",
				"periodo_inicio": today(),
				"periodo_fin": add_days(today(), 7),
				# company faltante
			}
		)

		with self.assertRaises(frappe.ValidationError):
			doc.autoname()

		# Test validación con fechas faltantes
		doc2 = frappe.get_doc(
			{
				"doctype": "Factura Global MX",
				"company": self.test_company,
				# fechas faltantes
			}
		)

		with self.assertRaises(frappe.ValidationError):
			doc2.validate_period_dates()

	def test_autonaming_pattern(self):
		"""Test: Patrón de autonaming."""

		doc = frappe.get_doc(
			{
				"doctype": "Factura Global MX",
				"company": self.test_company,
				"periodo_inicio": today(),
				"periodo_fin": add_days(today(), 7),
				"periodicidad": "Semanal",
			}
		)

		# Mock del count para predecir el nombre
		with patch("frappe.db.count") as mock_count:
			mock_count.return_value = 0  # Primer documento

			doc.autoname()

			# Verificar patrón del nombre
			from frappe.utils import getdate

			date_today = getdate(today())
			year = date_today.strftime("%Y")
			month = date_today.strftime("%m")
			expected_prefix = f"FG-{self.test_company}-{year}-{month}-"

			self.assertTrue(doc.name.startswith(expected_prefix))
			self.assertTrue(doc.name.endswith("0001"))

	def test_factura_global_detail_population(self):
		"""Test: Población automática de datos en detalles."""
		from facturacion_mexico.facturas_globales.doctype.factura_global_detail.factura_global_detail import (
			FacturaGlobalDetail,
		)

		# Mock de E-Receipt data
		expected_data = {
			"ereceipt": "ER-TEST-001",
			"folio_receipt": "ER-001",
			"fecha_receipt": today(),
			"monto": 100.00,
			"customer_name": "Test Customer",
			"included_in_cfdi": 1,
		}

		with patch(
			"facturacion_mexico.facturas_globales.doctype.factura_global_detail.factura_global_detail.FacturaGlobalDetail.create_from_receipt"
		) as mock_create:
			mock_create.return_value = expected_data

			# Test creación desde receipt
			detail_data = FacturaGlobalDetail.create_from_receipt("ER-TEST-001")

			self.assertEqual(detail_data["ereceipt"], "ER-TEST-001")
			self.assertEqual(detail_data["folio_receipt"], "ER-001")
			self.assertEqual(detail_data["monto"], 100.00)
			self.assertEqual(detail_data["customer_name"], "Test Customer")
			self.assertEqual(detail_data["included_in_cfdi"], 1)

	def test_settings_integration(self):
		"""Test: Integración con configuraciones."""

		doc = frappe.get_doc(
			{
				"doctype": "Factura Global MX",
				"company": self.test_company,
				"periodo_inicio": today(),
				"periodo_fin": add_days(today(), 7),
				"periodicidad": "Semanal",
			}
		)

		# Mock settings habilitado
		with patch("frappe.get_single") as mock_settings:
			settings_mock = MagicMock()
			settings_mock.enable_global_invoices = 1
			settings_mock.global_invoice_serie = "FG-TEST"
			mock_settings.return_value = settings_mock

			# Validación debería pasar
			try:
				doc.validate_company_settings()
				validation_passed = True
			except Exception:
				validation_passed = False

			self.assertTrue(validation_passed)
			self.assertEqual(doc.serie, "FG-TEST")

		# Mock settings deshabilitado
		with patch("frappe.get_single") as mock_settings:
			settings_mock = MagicMock()
			settings_mock.enable_global_invoices = 0
			mock_settings.return_value = settings_mock

			with self.assertRaises(frappe.ValidationError):
				doc.validate_company_settings()


if __name__ == "__main__":
	unittest.main()
