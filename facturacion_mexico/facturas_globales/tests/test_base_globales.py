"""
Base Test Class para Facturas Globales - Sprint 4 Semana 1
Framework de testing 4-Layer siguiendo REGLA #33 progresivo
"""

import time
from typing import Any

import frappe
from frappe.test_runner import make_test_records
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today


class FacturasGlobalesTestBase(FrappeTestCase):
	"""Clase base para tests del módulo de facturas globales."""

	@classmethod
	def setUpClass(cls):
		"""Configuración inicial para todos los tests."""
		super().setUpClass()
		cls.setup_test_data()

	@classmethod
	def setup_test_data(cls):
		"""Configurar datos de prueba necesarios."""
		cls.setup_test_dependencies()
		cls.create_test_company()
		cls.create_test_ereceipts()
		cls.setup_facturacion_settings()

	@classmethod
	def setup_test_dependencies(cls):
		"""Configurar dependencias necesarias para los tests."""
		try:
			# Crear registros de prueba estándar de ERPNext
			make_test_records("Territory")
			make_test_records("Customer Group")
			make_test_records("Item Group")
			make_test_records("UOM")
			make_test_records("Account")
			make_test_records("Company")
		except Exception:
			# Si falla make_test_records, crear manualmente los registros mínimos
			cls.create_minimal_test_fixtures()

	@classmethod
	def create_minimal_test_fixtures(cls):
		"""Crear fixtures mínimos necesarios."""
		# Crear Company de prueba
		if not frappe.db.exists("Company", "Test Global Company"):
			company = frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": "Test Global Company",
					"abbr": "TGC",
					"default_currency": "MXN",
					"country": "Mexico",
				}
			)
			company.insert(ignore_permissions=True)

		# Crear Territory de prueba
		if not frappe.db.exists("Territory", "_Test Territory Global"):
			territory = frappe.get_doc(
				{
					"doctype": "Territory",
					"territory_name": "_Test Territory Global",
					"is_group": 0,
					"parent_territory": "All Territories",
				}
			)
			territory.insert(ignore_permissions=True)

	@classmethod
	def create_test_company(cls):
		"""Crear empresa de prueba."""
		company_name = "Test Global Company"
		if not frappe.db.exists("Company", company_name):
			company = frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": company_name,
					"abbr": "TGC",
					"default_currency": "MXN",
					"country": "Mexico",
					"tax_id": "TGC123456789",
				}
			)
			company.insert(ignore_permissions=True)

		cls.test_company = company_name

	@classmethod
	def create_test_ereceipts(cls):
		"""Crear E-Receipts de prueba."""
		cls.test_ereceipts = []

		# Crear 10 receipts de prueba para diferentes escenarios
		for i in range(10):
			receipt_data = {
				"doctype": "EReceipt MX",
				"company": cls.test_company,
				"folio": f"ER-GLOBAL-{i:03d}",
				"receipt_date": add_days(today(), -i),
				"total_amount": 100.00 + (i * 10),
				"tax_amount": 16.00 + (i * 1.6),
				"base_amount": 84.00 + (i * 8.4),
				"tax_rate": 16.0,
				"currency": "MXN",
				"customer_name": f"Cliente Test {i}" if i % 3 == 0 else "Público General",
				"status": "Paid",
				"payment_method": "Efectivo",
				"usage_cfdi": "G01",
				"available_for_global": 1,
				"included_in_global": 0,
			}

			try:
				if not frappe.db.exists("EReceipt MX", receipt_data["folio"]):
					receipt_doc = frappe.get_doc(receipt_data)
					receipt_doc.insert(ignore_permissions=True)
					receipt_doc.submit()
					cls.test_ereceipts.append(receipt_doc.name)
			except Exception:
				# Si falla la creación, crear mock data
				cls.test_ereceipts.append(f"MOCK-ER-{i:03d}")

	@classmethod
	def setup_facturacion_settings(cls):
		"""Configurar settings de facturación."""
		try:
			settings = frappe.get_single("Facturacion Mexico Settings")
			settings.enable_global_invoices = 1
			settings.global_invoice_serie = "FG-TEST"
			settings.global_invoice_periodicidad = "Mensual"
			settings.auto_generate_global = 0
			settings.notify_global_generation = 0
			settings.save(ignore_permissions=True)
		except Exception:
			# Si el DocType no existe, crear configuración mock
			pass

	def create_test_factura_global(self, **kwargs) -> str:
		"""Crear factura global de prueba."""
		from unittest.mock import MagicMock, patch

		default_data = {
			"doctype": "Factura Global MX",
			"company": self.test_company,
			"periodo_inicio": add_days(today(), -6),  # 7 days total (0-6 inclusive)
			"periodo_fin": today(),
			"periodicidad": "Semanal",
			"status": "Draft",
		}

		# Actualizar con datos personalizados
		default_data.update(kwargs)

		# Mock settings para evitar errores de validación
		with patch("frappe.get_single") as mock_settings:
			settings_mock = MagicMock()
			settings_mock.enable_global_invoices = 1
			settings_mock.global_invoice_serie = "FG-TEST"
			mock_settings.return_value = settings_mock

			global_doc = frappe.get_doc(default_data)

			# Agregar receipts si no se especificaron
			if not global_doc.get("receipts_detail") and self.test_ereceipts:
				for i, ereceipt_name in enumerate(self.test_ereceipts[:5]):  # Primeros 5
					if not ereceipt_name.startswith("MOCK-"):
						from facturacion_mexico.facturas_globales.doctype.factura_global_detail.factura_global_detail import (
							FacturaGlobalDetail,
						)

						try:
							detail_data = FacturaGlobalDetail.create_from_receipt(ereceipt_name)
							global_doc.append("receipts_detail", detail_data)
						except Exception:
							# Si falla, agregar datos básicos
							global_doc.append(
								"receipts_detail",
								{
									"ereceipt": ereceipt_name,
									"folio_receipt": f"ER-{i:03d}",
									"fecha_receipt": add_days(today(), -i),
									"monto": 100.00 + (i * 10),
									"customer_name": "Test Customer",
									"included_in_cfdi": 1,
								},
							)

			global_doc.insert(ignore_permissions=True)
			return global_doc.name

	def create_mock_ereceipt_data(self, count: int = 5) -> list[dict[str, Any]]:
		"""Crear datos mock de E-Receipts para testing."""
		mock_receipts = []

		for i in range(count):
			receipt = {
				"name": f"MOCK-ER-{i:03d}",
				"folio": f"ER-MOCK-{i:03d}",
				"receipt_date": add_days(today(), -i),
				"total_amount": 100.00 + (i * 10),
				"tax_amount": 16.00 + (i * 1.6),
				"base_amount": 84.00 + (i * 8.4),
				"tax_rate": 16.0,
				"customer_name": f"Mock Customer {i}",
				"currency": "MXN",
				"status": "Paid",
				"available_for_global": 1,
				"included_in_global": 0,
			}
			mock_receipts.append(receipt)

		return mock_receipts

	def measure_execution_time(self, func, *args, **kwargs) -> tuple[Any, float]:
		"""Medir tiempo de ejecución de una función."""
		start_time = time.time()
		result = func(*args, **kwargs)
		execution_time = time.time() - start_time
		return result, execution_time

	def assert_factura_global_valid(self, factura_name: str, message: str = "Factura Global should be valid"):
		"""Validar que una factura global sea válida."""
		if not frappe.db.exists("Factura Global MX", factura_name):
			self.fail(f"{message}: Factura no encontrada")

		doc = frappe.get_doc("Factura Global MX", factura_name)

		# Validaciones básicas
		self.assertIsNotNone(doc.company, f"{message}: Company es requerido")
		self.assertIsNotNone(doc.periodo_inicio, f"{message}: Período inicio requerido")
		self.assertIsNotNone(doc.periodo_fin, f"{message}: Período fin requerido")
		self.assertGreaterEqual(doc.periodo_fin, doc.periodo_inicio, f"{message}: Período inválido")

	def assert_api_response_valid(
		self, response: dict[str, Any], message: str = "API response should be valid"
	):
		"""Validar que una respuesta de API sea válida."""
		self.assertIsInstance(response, dict, f"{message}: Response debe ser dict")
		self.assertIn("success", response, f"{message}: Response debe tener campo 'success'")

		if not response.get("success"):
			error_msg = response.get("message", "Error desconocido")
			self.fail(f"{message}: API falló - {error_msg}")

	def tearDown(self):
		"""Limpieza después de cada test."""
		super().tearDown()
		self.cleanup_test_data()

	def cleanup_test_data(self):
		"""Limpiar datos de prueba."""
		try:
			# Limpiar facturas globales de prueba
			test_globals = frappe.get_all(
				"Factura Global MX", filters={"company": self.test_company}, pluck="name"
			)

			for global_name in test_globals:
				try:
					frappe.delete_doc("Factura Global MX", global_name, force=True, ignore_permissions=True)
				except Exception:
					# Ignorar si el documento ya fue eliminado o no existe
					pass

			# Limpiar E-Receipts de prueba si son mock
			for receipt_name in getattr(self, "test_ereceipts", []):
				if receipt_name.startswith("MOCK-"):
					continue

				try:
					# Solo limpiar si no está en uso
					receipt_doc = frappe.get_doc("EReceipt MX", receipt_name)
					if not receipt_doc.get("global_invoice"):
						frappe.delete_doc("EReceipt MX", receipt_name, force=True, ignore_permissions=True)
				except Exception:
					# Ignorar errores de cleanup - documento puede no existir o estar en uso
					pass

		except Exception as e:
			frappe.log_error(f"Error en cleanup de tests: {e}")

	@classmethod
	def tearDownClass(cls):
		"""Limpieza final de la clase."""
		super().tearDownClass()

		# Limpiar datos de la clase
		try:
			# Limpiar company de prueba si no está en uso
			if hasattr(cls, "test_company"):
				companies_in_use = frappe.db.count("Factura Global MX", {"company": cls.test_company})
				if companies_in_use == 0:
					frappe.delete_doc("Company", cls.test_company, force=True, ignore_permissions=True)
		except Exception:
			# Ignorar errores al limpiar empresa de test - puede estar en uso por otros tests
			pass
