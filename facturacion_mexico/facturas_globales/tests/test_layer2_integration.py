"""
Layer 2: Integration Tests - Facturas Globales
Tests de integración entre componentes y con base de datos
REGLA #33: Testing progresivo - Layer 2 debe pasar después de Layer 1
"""

import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import add_days, flt, today

from facturacion_mexico.facturas_globales.tests.test_base_globales import FacturasGlobalesTestBase


class TestFacturasGlobalesIntegration(FacturasGlobalesTestBase):
	"""Tests de integración para el sistema de facturas globales."""

	def test_complete_doctype_workflow(self):
		"""Test: Flujo completo de DocType desde creación hasta submit."""
		# Mock settings para evitar errores
		with patch("frappe.get_single") as mock_settings:
			settings_mock = MagicMock()
			settings_mock.enable_global_invoices = 1
			settings_mock.global_invoice_serie = "FG-TEST"
			mock_settings.return_value = settings_mock

			# Crear factura global con datos reales
			global_name = self.create_test_factura_global(
				periodo_inicio=add_days(today(), -6), periodo_fin=today(), periodicidad="Semanal"
			)

		# Verificar que se creó correctamente
		self.assertTrue(frappe.db.exists("Factura Global MX", global_name))

		global_doc = frappe.get_doc("Factura Global MX", global_name)

		# Test validaciones automáticas
		self.assertEqual(global_doc.docstatus, 0)  # Draft

		# Si no hay receipts, agregar algunos manualmente para testing
		if len(global_doc.receipts_detail) == 0:
			# Create actual EReceipt documents to avoid link validation errors
			with patch("frappe.db.get_single_value") as mock_single_value:
				mock_single_value.return_value = 0  # Disable ereceipts settings check

				for i in range(3):
					receipt_doc = frappe.get_doc(
						{
							"doctype": "EReceipt MX",
							"naming_series": "E-REC-.YYYY.-",
							"company": self.test_company,
							"date_issued": add_days(today(), -i),
							"total": 100.00 + (i * 10),
							"customer_name": f"Test Customer {i}",
							"status": "open",
							"expiry_type": "Custom Date",
							"expiry_date": add_days(today(), 30),
							"included_in_global": 0,
						}
					)
					receipt_doc.insert(ignore_permissions=True)

				global_doc.append(
					"receipts_detail",
					{
						"ereceipt": receipt_doc.name,
						"folio_receipt": receipt_doc.name,
						"fecha_receipt": add_days(today(), -i),
						"monto": 100.00 + (i * 10),
						"customer_name": f"Test Customer {i}",
						"included_in_cfdi": 1,
					},
				)
			with patch("frappe.get_single") as mock_settings_save:
				settings_mock_save = MagicMock()
				settings_mock_save.enable_global_invoices = 1
				settings_mock_save.global_invoice_serie = "FG-TEST"
				mock_settings_save.return_value = settings_mock_save
				global_doc.save()

		self.assertGreater(len(global_doc.receipts_detail), 0)
		self.assertGreater(global_doc.total_periodo, 0)
		self.assertEqual(global_doc.cantidad_receipts, len(global_doc.receipts_detail))

		# Test cálculos automáticos
		manual_total = sum(flt(detail.monto) for detail in global_doc.receipts_detail)
		self.assertEqual(flt(global_doc.total_periodo), manual_total)

		# Test autonaming pattern
		self.assertTrue(global_doc.name.startswith("FG-"))
		self.assertIn(self.test_company, global_doc.name)

	def test_ereceipt_integration(self):
		"""Test: Integración real con E-Receipts."""
		# Create real EReceipts for testing with simplified approach
		test_receipts = []
		with patch("frappe.db.get_single_value") as mock_single_value:
			mock_single_value.return_value = 0  # Disable ereceipts settings check

			for i in range(3):
				receipt_doc = frappe.get_doc(
					{
						"doctype": "EReceipt MX",
						"naming_series": "E-REC-.YYYY.-",
						"company": self.test_company,
						"date_issued": add_days(today(), -i),
						"total": 100.00 + (i * 25),
						"customer_name": f"Cliente Integración {i}",
						"status": "open",
						"expiry_type": "Custom Date",
						"expiry_date": add_days(today(), 30),
						"included_in_global": 0,
					}
				)
				receipt_doc.insert(ignore_permissions=True)
				test_receipts.append(receipt_doc.name)

		# Crear factura global usando estos receipts
		with patch("frappe.get_single") as mock_settings:
			settings_mock = MagicMock()
			settings_mock.enable_global_invoices = 1
			settings_mock.global_invoice_serie = "FG-TEST"
			mock_settings.return_value = settings_mock

			global_doc = frappe.get_doc(
				{
					"doctype": "Factura Global MX",
					"company": self.test_company,
					"periodo_inicio": add_days(today(), -6),  # 7 days total (0-6 inclusive)
					"periodo_fin": today(),
					"periodicidad": "Semanal",
					"status": "Draft",
				}
			)

			# Agregar receipts reales
			for i, receipt_name in enumerate(test_receipts):
				global_doc.append(
					"receipts_detail",
					{
						"ereceipt": receipt_name,
						"folio_receipt": receipt_name,
						"fecha_receipt": add_days(today(), -i),
						"monto": 100.00 + (i * 25),
						"customer_name": f"Cliente Integración {i}",
						"included_in_cfdi": 1,
					},
				)

			global_doc.insert(ignore_permissions=True)

		# Verificar integración correcta
		self.assertEqual(len(global_doc.receipts_detail), 3)

		# Verificar datos poblados correctamente
		for i, detail in enumerate(global_doc.receipts_detail):
			self.assertEqual(detail.ereceipt, test_receipts[i])
			self.assertEqual(detail.folio_receipt, test_receipts[i])
			self.assertEqual(detail.monto, 100.00 + (i * 25))
			self.assertEqual(detail.customer_name, f"Cliente Integración {i}")
			self.assertEqual(detail.included_in_cfdi, 1)

		# Cleanup
		for receipt_name in test_receipts:
			frappe.delete_doc("EReceipt MX", receipt_name, force=True, ignore_permissions=True)

	def test_api_database_integration(self):
		"""Test: Integración de APIs con base de datos real."""
		from facturacion_mexico.facturas_globales.api import create_global_invoice, get_available_ereceipts

		# Test get_available_ereceipts con datos reales
		result = get_available_ereceipts(
			periodo_inicio=add_days(today(), -7), periodo_fin=today(), company=self.test_company
		)

		self.assertTrue(result["success"])
		self.assertIn("data", result)
		self.assertIn("summary", result)

		# Verificar estructura de datos
		if result["data"]:
			receipt = result["data"][0]
			required_fields = ["ereceipt", "folio", "fecha_receipt", "monto", "customer_name"]
			for field in required_fields:
				self.assertIn(field, receipt)

		# Test create_global_invoice con integración real
		if result["data"] and len(result["data"]) > 0:
			create_result = create_global_invoice(
				periodo_inicio=add_days(today(), -7),
				periodo_fin=today(),
				periodicidad="Semanal",
				company=self.test_company,
			)

			if create_result["success"]:
				# Verificar que se creó en la base de datos
				invoice_name = create_result["name"]
				self.assertTrue(frappe.db.exists("Factura Global MX", invoice_name))

				# Verificar datos de la factura creada
				created_doc = frappe.get_doc("Factura Global MX", invoice_name)
				self.assertEqual(created_doc.company, self.test_company)
				self.assertGreater(len(created_doc.receipts_detail), 0)

				# Cleanup
				frappe.delete_doc("Factura Global MX", invoice_name, force=True, ignore_permissions=True)

	def test_aggregator_database_integration(self):
		"""Test: Integración de agregador con base de datos."""
		from facturacion_mexico.facturas_globales.processors.ereceipt_aggregator import EReceiptAggregator

		# Crear agregador con período real
		aggregator = EReceiptAggregator(
			periodo_inicio=add_days(today(), -7), periodo_fin=today(), company=self.test_company
		)

		# Test obtención de receipts desde base de datos
		receipts = aggregator.get_available_receipts()
		self.assertIsInstance(receipts, list)

		if receipts:
			# Test agrupaciones con datos reales
			tax_groups = aggregator.group_by_tax_rate()
			self.assertIsInstance(tax_groups, dict)

			daily_groups = aggregator.group_by_day()
			self.assertIsInstance(daily_groups, dict)

			customer_groups = aggregator.group_by_customer()
			self.assertIsInstance(customer_groups, dict)

			# Test cálculos con datos reales
			totals = aggregator.calculate_totals()
			self.assertIn("count", totals)
			self.assertIn("total_amount", totals)
			self.assertEqual(totals["count"], len(receipts))

			# Test validaciones con datos reales
			folio_validation = aggregator.validate_continuous_folios()
			self.assertIn("is_continuous", folio_validation)
			self.assertIn("missing_folios", folio_validation)

	def test_cfdi_builder_integration(self):
		"""Test: Integración de constructor CFDI."""
		from facturacion_mexico.facturas_globales.processors.cfdi_global_builder import CFDIGlobalBuilder

		# Crear factura global con datos reales
		global_name = self.create_test_factura_global()
		global_doc = frappe.get_doc("Factura Global MX", global_name)

		# Mock de settings para evitar errores
		with patch("frappe.get_single") as mock_settings:
			settings_mock = MagicMock()
			settings_mock.enable_global_invoices = 1
			settings_mock.global_invoice_serie = "FG-TEST"
			settings_mock.facturapi_test_mode = True
			settings_mock.get.return_value = "01000"
			mock_settings.return_value = settings_mock

			# Mock company data
			with patch("frappe.get_doc") as mock_get_doc:
				mock_company = MagicMock()
				mock_company.tax_id = "TEST123456789"
				mock_get_doc.return_value = mock_company

				# Test construcción de datos CFDI
				builder = CFDIGlobalBuilder(global_doc)

				# Test validación de datos
				validation = builder.validate_cfdi_data()
				self.assertIn("is_valid", validation)
				self.assertIn("errors", validation)
				self.assertIn("warnings", validation)

				# Test construcción de datos completos
				if validation["is_valid"]:
					cfdi_data = builder.build_global_invoice_data()

					# Verificar estructura requerida
					required_keys = ["type", "customer", "items", "payment_form", "payment_method"]
					for key in required_keys:
						self.assertIn(key, cfdi_data)

					# Verificar datos del cliente
					customer = cfdi_data["customer"]
					self.assertIn("legal_name", customer)
					self.assertIn("tax_id", customer)

					# Verificar items
					items = cfdi_data["items"]
					self.assertIsInstance(items, list)
					self.assertGreater(len(items), 0)

					# Verificar estructura de items
					item = items[0]
					item_required = ["quantity", "product", "unit_price", "taxes"]
					for key in item_required:
						self.assertIn(key, item)

	def test_complete_integration_workflow(self):
		"""Test: Flujo completo de integración end-to-end."""
		from facturacion_mexico.facturas_globales.api import get_available_ereceipts, preview_global_invoice

		# 1. Obtener receipts disponibles
		receipts_result = get_available_ereceipts(
			periodo_inicio=add_days(today(), -6), periodo_fin=today(), company=self.test_company
		)

		self.assertTrue(receipts_result["success"])

		# 2. Preview de factura global
		preview_result = preview_global_invoice(
			periodo_inicio=add_days(today(), -6), periodo_fin=today(), company=self.test_company
		)

		self.assertTrue(preview_result["success"])
		self.assertIn("preview", preview_result)

		# 3. Crear factura global usando workflow completo
		global_name = self.create_test_factura_global(
			periodo_inicio=add_days(today(), -6), periodo_fin=today()
		)

		global_doc = frappe.get_doc("Factura Global MX", global_name)

		# Si no hay receipts, agregar algunos manualmente para testing
		if len(global_doc.receipts_detail) == 0:
			# Create actual EReceipts to avoid link validation errors
			with patch("frappe.db.get_single_value") as mock_single_value:
				mock_single_value.return_value = 0  # Disable ereceipts settings check

				for i in range(2):
					receipt_doc = frappe.get_doc(
						{
							"doctype": "EReceipt MX",
							"naming_series": "E-REC-.YYYY.-",
							"company": self.test_company,
							"date_issued": add_days(today(), -i),
							"total": 150.00 + (i * 25),
							"customer_name": f"Workflow Customer {i}",
							"status": "open",
							"expiry_type": "Custom Date",
							"expiry_date": add_days(today(), 30),
							"included_in_global": 0,
						}
					)
					receipt_doc.insert(ignore_permissions=True)

				global_doc.append(
					"receipts_detail",
					{
						"ereceipt": receipt_doc.name,
						"folio_receipt": receipt_doc.name,
						"fecha_receipt": add_days(today(), -i),
						"monto": 150.00 + (i * 25),
						"customer_name": f"Workflow Customer {i}",
						"included_in_cfdi": 1,
					},
				)
			with patch("frappe.get_single") as mock_settings_save:
				settings_mock_save = MagicMock()
				settings_mock_save.enable_global_invoices = 1
				settings_mock_save.global_invoice_serie = "FG-TEST"
				mock_settings_save.return_value = settings_mock_save
				global_doc.save()

		# 4. Validar datos del workflow
		self.assertGreater(len(global_doc.receipts_detail), 0)
		self.assertGreater(global_doc.total_periodo, 0)

		# 5. Test configuración
		config_test = global_doc.test_configuration(dry_run=True)
		self.assertIn("success", config_test)
		self.assertIn("validations", config_test)

	def test_error_handling_integration(self):
		"""Test: Manejo de errores en integración."""
		# Test con company inexistente
		with self.assertRaises(Exception):
			frappe.get_doc(
				{
					"doctype": "Factura Global MX",
					"company": "Empresa Inexistente",
					"periodo_inicio": today(),
					"periodo_fin": add_days(today(), 7),
					"periodicidad": "Semanal",
				}
			).insert()

		# Test con período inválido
		with self.assertRaises(frappe.ValidationError):
			doc = frappe.get_doc(
				{
					"doctype": "Factura Global MX",
					"company": self.test_company,
					"periodo_inicio": add_days(today(), 7),  # Futuro
					"periodo_fin": add_days(today(), 14),
					"periodicidad": "Semanal",
				}
			)
			doc.validate_period_dates()

		# Test con receipts duplicados
		global_doc = frappe.get_doc(
			{
				"doctype": "Factura Global MX",
				"company": self.test_company,
				"periodo_inicio": add_days(today(), -7),
				"periodo_fin": today(),
				"periodicidad": "Semanal",
			}
		)

		# Agregar mismo receipt dos veces
		if self.test_ereceipts:
			receipt_name = self.test_ereceipts[0]
			if not receipt_name.startswith("MOCK-"):
				detail_data = {
					"ereceipt": receipt_name,
					"folio_receipt": "TEST-001",
					"fecha_receipt": today(),
					"monto": 100.00,
					"customer_name": "Test Customer",
					"included_in_cfdi": 1,
				}
				global_doc.append("receipts_detail", detail_data)
				global_doc.append("receipts_detail", detail_data)  # Duplicado

				global_doc.insert(ignore_permissions=True)

				# Verificar que la validación detecta el problema
				with self.assertRaises(frappe.ValidationError):
					global_doc.submit()

	def test_performance_integration(self):
		"""Test: Rendimiento en integración con datos grandes."""
		import time

		# Test con agregador y muchos receipts mock
		from facturacion_mexico.facturas_globales.processors.ereceipt_aggregator import EReceiptAggregator

		aggregator = EReceiptAggregator(
			periodo_inicio=add_days(today(), -30), periodo_fin=today(), company=self.test_company
		)

		# Simular muchos receipts
		mock_receipts = []
		for i in range(100):
			mock_receipts.append(
				{
					"name": f"PERF-{i:04d}",
					"folio": f"PERF-{i:04d}",
					"receipt_date": add_days(today(), -i % 30),
					"total_amount": 100.00 + i,
					"tax_amount": 16.00,
					"tax_rate": 16.0,
					"customer_name": f"Customer {i % 10}",
					"payment_method": "Efectivo" if i % 2 == 0 else "Transferencia",
				}
			)

		aggregator.receipts = mock_receipts

		# Test performance de agrupaciones
		start_time = time.time()
		aggregator.group_by_tax_rate()  # We don't need to store the result, just test performance
		tax_time = time.time() - start_time

		start_time = time.time()
		daily_groups = aggregator.group_by_day()
		daily_time = time.time() - start_time

		start_time = time.time()
		customer_groups = aggregator.group_by_customer()
		customer_time = time.time() - start_time

		start_time = time.time()
		totals = aggregator.calculate_totals()
		totals_time = time.time() - start_time

		# Verificar que las operaciones sean eficientes (< 1 segundo cada una)
		self.assertLess(tax_time, 1.0, f"Tax grouping took too long: {tax_time:.3f}s")
		self.assertLess(daily_time, 1.0, f"Daily grouping took too long: {daily_time:.3f}s")
		self.assertLess(customer_time, 1.0, f"Customer grouping took too long: {customer_time:.3f}s")
		self.assertLess(totals_time, 1.0, f"Totals calculation took too long: {totals_time:.3f}s")

		# Verificar resultados correctos
		self.assertEqual(len(mock_receipts), 100)
		self.assertEqual(totals["count"], 100)
		self.assertGreater(len(daily_groups), 0)
		self.assertEqual(len(customer_groups), 10)  # 10 clientes únicos


if __name__ == "__main__":
	unittest.main()
