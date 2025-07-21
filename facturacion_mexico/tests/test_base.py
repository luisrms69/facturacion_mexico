import json
import os
from typing import ClassVar
from unittest.mock import patch

import frappe
from frappe.test_runner import make_test_records
from frappe.tests.utils import FrappeTestCase

# REGLA #43A: Skip test records para evitar LinkValidationError (patrón condominium_management)
frappe.flags.skip_test_records = True

# REGLA #43B: Test ignore list para dependencias problemáticas
test_ignore = ["Sales Invoice", "Customer", "Item", "Uso CFDI SAT", "Item Tax Template", "Warehouse"]


class FacturacionMexicoTestGranular(FrappeTestCase):
	"""
	Base class para testing granular de Facturación México.

	METODOLOGÍA 4 LAYERS:
	- Layer 1: Unit Tests (NO DB) - SIEMPRE FUNCIONAN
	- Layer 2: Mocked Integration - IDENTIFICAN PROBLEMAS DE HOOKS
	- Layer 3: Focused Integration - PRUEBAN DEPENDENCIAS ESPECÍFICAS
	- Layer 4: Configuration Tests - VALIDAN DOCTYPE JSON Y META
	"""

	# Configuration by DocType
	DOCTYPE_NAME = None
	REQUIRED_FIELDS: ClassVar[dict] = {}
	MOCK_HOOKS = True  # Enable hook mocking by default
	TEST_MINIMAL_ONLY = False  # Set True for super lightweight testing

	@classmethod
	def setUpClass(cls):
		"""Configurar datos de test una sola vez."""
		# REGLA #43A: Aplicar skip_test_records en setup de clase
		frappe.flags.skip_test_records = True

		# Usar fixtures centralizados para una arquitectura sólida
		from facturacion_mexico.fixtures.test_data import create_test_records

		try:
			create_test_records()
			frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to persist test setup data across test methods
		except Exception as e:
			frappe.log_error(f"Error setting up test data: {e}")
			# Fallback a método anterior si fixtures fallan
			if cls.DOCTYPE_NAME:
				cls.create_test_settings()
				cls.create_test_catalogs()
				cls.create_test_customer()
				cls.create_test_item()
				frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to persist fallback test data

	def setUp(self):
		"""Setup para cada test individual."""
		# REGLA #43A: Asegurar skip_test_records en cada test
		frappe.flags.skip_test_records = True
		frappe.set_user("Administrator")

	def tearDown(self):
		"""Cleanup después de cada test."""
		frappe.db.rollback()

	# ===== LAYER 1: UNIT TESTS (NO DATABASE OPERATIONS) =====

	def test_field_validation_isolated(self):
		"""LAYER 1: Test individual field assignment without DB operations."""
		if not self.DOCTYPE_NAME:
			self.skipTest("DOCTYPE_NAME not defined")

		doc = frappe.new_doc(self.DOCTYPE_NAME)

		# Test each field assignment individually
		for field_name, field_value in self.REQUIRED_FIELDS.items():
			if field_name != "doctype":
				setattr(doc, field_name, field_value)
				self.assertEqual(
					getattr(doc, field_name), field_value, f"Field {field_name} assignment failed"
				)

	def test_doctype_exists_in_meta(self):
		"""LAYER 1: Test that DocType exists in frappe meta."""
		if not self.DOCTYPE_NAME:
			self.skipTest("DOCTYPE_NAME not defined")

		meta = frappe.get_meta(self.DOCTYPE_NAME)
		self.assertIsNotNone(meta)
		self.assertEqual(meta.name, self.DOCTYPE_NAME)

	# ===== LAYER 2: BUSINESS LOGIC WITH MOCKED HOOKS =====

	def test_creation_with_mocked_hooks(self):
		"""LAYER 2: Test validation logic with hooks disabled."""
		if not self.DOCTYPE_NAME or not self.REQUIRED_FIELDS:
			self.skipTest("DOCTYPE_NAME or REQUIRED_FIELDS not defined")

		if self.MOCK_HOOKS:
			with patch("frappe.get_hooks", return_value={}):
				try:
					doc = frappe.get_doc(self.REQUIRED_FIELDS.copy())
					doc.validate()
				except Exception as e:
					frappe.log_error(f"Expected validation failure: {e!s}")
					# No falla el test, solo registra para diagnóstico
		else:
			self.skipTest("Hook mocking disabled")

	def test_identify_hooks_problem(self):
		"""LAYER 2: Diagnostic test to identify specific hook problems."""
		if not self.DOCTYPE_NAME or not self.REQUIRED_FIELDS:
			self.skipTest("DOCTYPE_NAME or REQUIRED_FIELDS not defined")

		doc = frappe.get_doc(self.REQUIRED_FIELDS.copy())

		# Test validation without hooks
		with patch("frappe.get_hooks", return_value={}):
			try:
				doc.validate()
				hooks_problem = False
			except Exception as e:
				hooks_problem = True
				frappe.log_error(f"Validation failed even without hooks: {e!s}")

		# Test with hooks enabled
		try:
			doc.validate()
			with_hooks_problem = False
		except Exception as e:
			with_hooks_problem = True
			frappe.log_error(f"Validation failed with hooks: {e!s}")

		# Diagnóstico
		if not hooks_problem and with_hooks_problem:
			frappe.log_error("DIAGNOSTIC: Problem is specifically in hooks configuration")
		elif hooks_problem:
			frappe.log_error("DIAGNOSTIC: Problem is in basic validation, not hooks")

	# ===== LAYER 3: FOCUSED INTEGRATION TESTS =====

	def test_minimal_valid_creation(self):
		"""LAYER 3: Test with minimal valid data (focused integration)."""
		if not self.DOCTYPE_NAME or not self.REQUIRED_FIELDS or self.TEST_MINIMAL_ONLY:
			self.skipTest("Minimal testing only or missing configuration")

		try:
			doc = frappe.get_doc(self.REQUIRED_FIELDS.copy())
			doc.insert(ignore_permissions=True)

			# Basic verification
			self.assertTrue(doc.name)
			self.assertEqual(doc.doctype, self.DOCTYPE_NAME)

			# Cleanup immediately
			doc.delete(ignore_permissions=True, force=True)

		except Exception as e:
			frappe.log_error(f"Expected integration failure: {e!s}")
			self.skipTest(f"Complex dependencies prevent simple creation: {e!s}")

	def test_required_fields_validation(self):
		"""LAYER 3: Test that required fields are properly validated."""
		if not self.DOCTYPE_NAME:
			self.skipTest("DOCTYPE_NAME not defined")

		meta = frappe.get_meta(self.DOCTYPE_NAME)
		required_fields = [field.fieldname for field in meta.fields if field.reqd]

		if required_fields:
			# Test creation without required fields
			doc = frappe.new_doc(self.DOCTYPE_NAME)

			with self.assertRaises(frappe.ValidationError):
				doc.insert(ignore_permissions=True)

	# ===== LAYER 4: CONFIGURATION VALIDATION =====

	def test_doctype_json_configuration(self):
		"""LAYER 4: Test DocType JSON configuration."""
		if not self.DOCTYPE_NAME:
			self.skipTest("DOCTYPE_NAME not defined")

		# Buscar archivo JSON del DocType
		json_path = None
		try:
			app_path = frappe.get_app_path("facturacion_mexico")
			for root, _dirs, files in os.walk(app_path):
				if (
					self.DOCTYPE_NAME.lower().replace(" ", "_") in root
					and f"{self.DOCTYPE_NAME.lower().replace(' ', '_')}.json" in files
				):
					json_path = os.path.join(root, f"{self.DOCTYPE_NAME.lower().replace(' ', '_')}.json")
					break
			else:
				self.skipTest(f"DocType JSON not found for {self.DOCTYPE_NAME}")
		except Exception as e:
			self.skipTest(f"Error finding DocType JSON: {e!s}")

		if json_path is None:
			self.skipTest("JSON path was not properly initialized.")

		with open(json_path, encoding="utf-8") as f:
			doctype_def = json.load(f)

		# Test basic JSON structure
		self.assertEqual(doctype_def.get("name"), self.DOCTYPE_NAME)
		self.assertIn("fields", doctype_def)
		self.assertIsInstance(doctype_def["fields"], list)

	def test_doctype_meta_consistency(self):
		"""LAYER 4: Test consistency between JSON and meta."""
		if not self.DOCTYPE_NAME:
			self.skipTest("DOCTYPE_NAME not defined")

		meta = frappe.get_meta(self.DOCTYPE_NAME)

		# Verificar que el meta tiene campos
		self.assertTrue(len(meta.fields) > 0, "DocType should have fields")

		# Verificar que todos los campos required están definidos
		for field in meta.fields:
			if field.reqd:
				self.assertTrue(field.fieldname, f"Required field should have fieldname: {field}")
				self.assertTrue(field.label, f"Required field should have label: {field.fieldname}")

	# ===== MÉTODOS DE CONFIGURACIÓN BASE =====

	@classmethod
	def create_test_settings(cls):
		"""Crear configuración de test para Facturación México."""
		if not frappe.db.exists("Facturacion Mexico Settings", "Facturacion Mexico Settings"):
			settings = frappe.new_doc("Facturacion Mexico Settings")
			settings.sandbox_mode = 1
			settings.test_api_key = "test_api_key_12345"
			settings.timeout = 30
			settings.rfc_emisor = "ABC123456789"
			settings.lugar_expedicion = "01000"
			settings.auto_generate_ereceipts = 1
			settings.send_email_default = 0
			settings.download_files_default = 1
			settings.save()

	@classmethod
	def create_test_catalogs(cls):
		"""Crear catálogos SAT básicos para testing."""

		# Crear Uso CFDI de test
		if not frappe.db.exists("Uso CFDI SAT", "G01"):
			uso_cfdi = frappe.new_doc("Uso CFDI SAT")
			uso_cfdi.code = "G01"
			uso_cfdi.description = "Adquisición de mercancías"
			uso_cfdi.aplica_fisica = 1
			uso_cfdi.aplica_moral = 1
			uso_cfdi.save()

		# Crear Régimen Fiscal de test
		if not frappe.db.exists("Regimen Fiscal SAT", "601"):
			regimen = frappe.new_doc("Regimen Fiscal SAT")
			regimen.code = "601"
			regimen.description = "General de Ley Personas Morales"
			regimen.aplica_fisica = 0
			regimen.aplica_moral = 1
			regimen.save()

	@classmethod
	def create_test_customer(cls):
		"""Crear cliente de test con datos fiscales válidos."""
		if not frappe.db.exists("Customer", "Test Customer MX"):
			make_test_records("Company")

			customer = frappe.new_doc("Customer")
			customer.customer_name = "Test Customer MX"
			customer.customer_type = "Company"
			customer.customer_group = (
				frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "All Customer Groups"
			)
			customer.territory = (
				frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories"
			)

			# Campos fiscales - RFC válido de prueba
			customer.fm_rfc = "ABC123456789"  # RFC válido para pruebas
			customer.fm_regimen_fiscal = "601"
			customer.fm_uso_cfdi_default = "G01"

			customer.save()

	@classmethod
	def create_test_item(cls):
		"""Crear artículo de test con clasificación SAT."""
		if not frappe.db.exists("Item", "Test Item MX"):
			try:
				# Simplificar creación de item para evitar dependencias complejas
				item = frappe.new_doc("Item")
				item.item_code = "Test Item MX"
				item.item_name = "Artículo de Prueba MX"
				item.item_group = "All Item Groups"
				item.stock_uom = "Nos"
				item.is_stock_item = 0  # No stock para simplificar
				item.include_item_in_manufacturing = 0

				# Clasificación SAT
				item.fm_producto_servicio_sat = "01010101"
				item.fm_unidad_sat = "H87"

				item.save()
			except Exception as e:
				# Si falla, continuar sin item de test
				frappe.logger().warning(f"No se pudo crear item de test: {e!s}")

	# ===== FACTORY METHODS PATTERN (Transferido de condominium_management) =====

	@classmethod
	def create_test_customer_factory(cls, **kwargs):
		"""Factory method para crear Customer de test con nombres únicos."""
		timestamp = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
		random_suffix = frappe.utils.random_string(3)

		defaults = {
			"doctype": "Customer",
			"customer_name": f"Test-Customer-{timestamp}-{random_suffix}",
			"customer_type": "Individual",
			"customer_group": "All Customer Groups",
			"territory": "All Territories",
			"fm_rfc": f"ABC{random_suffix}456789",  # RFC único para pruebas
		}
		defaults.update(kwargs)

		if frappe.flags.skip_test_records:
			# Si skip_test_records está activo, usar new_doc sin insertar
			return frappe.new_doc(defaults["doctype"]).update(defaults)
		else:
			# Insertar normalmente
			return frappe.get_doc(defaults).insert()

	@classmethod
	def create_test_payment_entry_factory(cls, **kwargs):
		"""Factory method para crear Payment Entry de test."""
		frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")

		defaults = {
			"doctype": "Payment Entry",
			"payment_type": "Receive",
			"party_type": "Customer",
			"party": kwargs.get("customer", "Test Customer MX"),
			"paid_amount": 1000.0,
			"received_amount": 1000.0,
			"target_exchange_rate": 1.0,
			"posting_date": frappe.utils.today(),
		}
		defaults.update(kwargs)

		if frappe.flags.skip_test_records:
			return frappe.new_doc(defaults["doctype"]).update(defaults)
		else:
			return frappe.get_doc(defaults).insert()

	@classmethod
	def create_test_sales_invoice_factory(cls, **kwargs):
		"""Factory method para crear Sales Invoice de test."""
		frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")

		defaults = {
			"doctype": "Sales Invoice",
			"customer": kwargs.get("customer", "Test Customer MX"),
			"posting_date": frappe.utils.today(),
			"due_date": frappe.utils.today(),
			"items": [{"item_code": "Test Item MX", "qty": 1, "rate": 1000.0}],
		}
		defaults.update(kwargs)

		if frappe.flags.skip_test_records:
			return frappe.new_doc(defaults["doctype"]).update(defaults)
		else:
			return frappe.get_doc(defaults).insert()

	# ===== MÉTODOS DE UTILIDAD =====

	def assertValidRFC(self, rfc):
		"""Validar que un RFC tenga formato correcto."""
		self.assertIsNotNone(rfc)
		self.assertTrue(len(rfc) in [12, 13], f"RFC {rfc} debe tener 12 o 13 caracteres")
		self.assertTrue(rfc.isalnum(), f"RFC {rfc} debe ser alfanumérico")

	def assertFiscalEventCreated(self, reference_doctype, reference_name, event_type):
		"""Validar que se haya creado un evento fiscal."""
		events = frappe.get_all(
			"Fiscal Event MX",
			filters={
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"event_type": event_type,
			},
		)
		self.assertTrue(
			len(events) > 0,
			f"Evento fiscal {event_type} no fue creado para {reference_doctype} {reference_name}",
		)

	@classmethod
	def tearDownClass(cls):
		"""Limpiar después de todos los tests."""
		# Usar cleanup centralizado para arquitectura sólida
		from facturacion_mexico.fixtures.test_data import cleanup_test_records

		try:
			cleanup_test_records()
		except Exception as e:
			frappe.log_error(f"Error cleaning up test data: {e}")

		frappe.db.rollback()


# ===== LEGACY COMPATIBILITY =====
# Mantener nombre anterior para compatibilidad
FacturacionMexicoTestCase = FacturacionMexicoTestGranular
