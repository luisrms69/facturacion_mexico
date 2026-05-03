"""
Tests E4 - Puente Read-Only Sales Invoice → PAC

ARQUITECTURA E4-RO:
Sistema de facturación que lee directamente desde Sales Invoice sin cálculos,
validando integridad estructural del payload antes de envío al PAC.

FUNCIONES TESTEADAS:
- E4.1: _read_taxes_from_sales_invoice_item()
- E4.2: _get_tax_amount_for_item_robust()
- E4.3: _resolve_objeto_impuesto()
- E4.4: _map_tax_account_to_sat()
- E4.6: _validate_objeto_imp_consistency()
- E4.7: _validate_currency_consistency()
- E4.8: _validate_payload_completeness_ro()

PRINCIPIOS TESTING (RG-003):
- ✅ Simplicidad: Prueba reglas negocio, no UI
- ✅ Determinismo: Sin red, mock gateway FacturAPI
- ✅ Aislamiento: Cada test crea sus datos
- ✅ Unit (prioridad) + 1 smoke integración

EJECUCIÓN:
bench --site facturacion.dev run-tests --app facturacion_mexico --module facturacion_mexico.tests.test_e4_puente_si_pac
"""

import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.facturacion_fiscal.timbrado_api import TimbradoAPI

# Constantes testing (RG-003.6)
TIMEZONE = "America/Mexico_City"
CURRENCY = "MXN"
TEST_ACCOUNT_IVA = "2117001 - IVA 16% - _TC"
TEST_ACCOUNT_ISR_RET = "2118001 - ISR Ret 10% - _TC"


class _E4TestBase(FrappeTestCase):
	"""Base para todos los tests E4 — parchea get_facturapi_client para que
	TimbradoAPI() no intente conectar a FacturAPI durante los tests."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._patcher = patch(
			"facturacion_mexico.facturacion_fiscal.timbrado_api.get_facturapi_client",
			return_value=MagicMock(),
		)
		cls._patcher.start()

	@classmethod
	def tearDownClass(cls):
		cls._patcher.stop()
		super().tearDownClass()


class TestE4ReadTaxesFromSI(_E4TestBase):
	"""
	Test E4.1: _read_taxes_from_sales_invoice_item()

	Validar lectura de impuestos desde item_tax_rate sin cálculos.
	"""

	def setUp(self):
		"""Setup test data - ID único por test."""
		self.test_id = "TEST-E4-" + frappe.generate_hash()[:6]

	def test_read_taxes_empty_item_tax_rate(self):
		"""Test: item sin item_tax_rate retorna lista vacía."""


		service = TimbradoAPI()

		# Mock item sin item_tax_rate
		item = frappe._dict({"item_tax_rate": ""})
		sales_invoice = frappe._dict({"name": self.test_id, "taxes": []})

		result = service._read_taxes_from_sales_invoice_item(item, sales_invoice)

		self.assertEqual(result, [])

	def test_read_taxes_with_single_tax(self):
		"""Test: item con 1 impuesto retorna lista con 1 elemento."""


		service = TimbradoAPI()

		# Mock item con IVA 16%
		item = frappe._dict(
			{
				"item_tax_rate": json.dumps({TEST_ACCOUNT_IVA: 16.0}),
				"item_code": "ITEM-001",
				"item_name": "Test Item",
				"name": "TEST-ROW-001",
			}
		)

		# Mock sales invoice con taxes
		sales_invoice = frappe._dict(
			{
				"name": self.test_id,
				"taxes": [
					frappe._dict(
						{
							"account_head": TEST_ACCOUNT_IVA,
							"item_wise_tax_detail": json.dumps({"TEST-ROW-001": [16.0, 160.0]}),
						}
					)
				],
			}
		)

		result = service._read_taxes_from_sales_invoice_item(item, sales_invoice)

		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["account_head"], TEST_ACCOUNT_IVA)
		self.assertEqual(result[0]["rate"], 16.0)
		self.assertEqual(result[0]["amount"], 160.0)


class TestE4TaxAmountRobust(_E4TestBase):
	"""
	Test E4.2: _get_tax_amount_for_item_robust()

	Validar fallback de llaves: row.name → item_code → item_name.
	"""

	def setUp(self):
		"""Setup test data."""
		self.test_id = "TEST-E4-" + frappe.generate_hash()[:6]

	def test_fallback_row_name_priority(self):
		"""Test: prioridad 1 = row.name encontrado."""


		service = TimbradoAPI()

		sales_invoice = frappe._dict(
			{
				"taxes": [
					frappe._dict(
						{
							"account_head": TEST_ACCOUNT_IVA,
							"item_wise_tax_detail": json.dumps(
								{
									"ROW-001": [16.0, 160.0],
									"ITEM-CODE-001": [16.0, 999.0],  # No debe usar este
								}
							),
						}
					)
				]
			}
		)

		result = service._get_tax_amount_for_item_robust(
			sales_invoice, TEST_ACCOUNT_IVA, "ITEM-CODE-001", "Item Name", "ROW-001"
		)

		self.assertEqual(result, 160.0)  # Usa ROW-001, no ITEM-CODE-001

	def test_fallback_item_code_when_row_missing(self):
		"""Test: fallback a item_code si row.name no existe."""


		service = TimbradoAPI()

		sales_invoice = frappe._dict(
			{
				"taxes": [
					frappe._dict(
						{
							"account_head": TEST_ACCOUNT_IVA,
							"item_wise_tax_detail": json.dumps({"ITEM-CODE-001": [16.0, 160.0]}),
						}
					)
				]
			}
		)

		result = service._get_tax_amount_for_item_robust(
			sales_invoice, TEST_ACCOUNT_IVA, "ITEM-CODE-001", "Item Name", "ROW-999"
		)

		self.assertEqual(result, 160.0)  # Usa item_code cuando row.name falta

	def test_return_zero_when_no_keys_match(self):
		"""Test: retorna 0.0 cuando ninguna llave coincide."""


		service = TimbradoAPI()

		sales_invoice = frappe._dict(
			{
				"taxes": [
					frappe._dict(
						{
							"account_head": TEST_ACCOUNT_IVA,
							"item_wise_tax_detail": json.dumps({"OTHER-KEY": [16.0, 160.0]}),
						}
					)
				]
			}
		)

		result = service._get_tax_amount_for_item_robust(
			sales_invoice, TEST_ACCOUNT_IVA, "ITEM-CODE-001", "Item Name", "ROW-001"
		)

		self.assertEqual(result, 0.0)


class TestE4ResolveObjetoImp(_E4TestBase):
	"""
	Test E4.3: _resolve_objeto_impuesto()

	Validar resolución ObjetoImp desde catálogo SAT.
	"""

	def test_throw_when_clave_prod_serv_missing(self):
		"""Test: lanza error si item no tiene ClaveProdServ."""


		service = TimbradoAPI()

		item_doc = frappe._dict({"name": "TEST-ITEM", "fm_producto_servicio_sat": None})

		with self.assertRaises(frappe.ValidationError) as context:
			service._resolve_objeto_impuesto(item_doc)

		self.assertIn("no tiene ClaveProdServ", str(context.exception))


class TestE4MapTaxToSAT(_E4TestBase):
	"""
	Test E4.4: _map_tax_account_to_sat()

	Validar mapeo cuenta ERPNext → metadata SAT.
	"""

	def test_throw_when_account_not_mapped(self):
		"""Test: lanza error si cuenta no tiene mapeo SAT."""


		service = TimbradoAPI()

		# Mock Facturacion Mexico Settings con company
		mock_settings = frappe._dict({"company": "Test Company"})

		# Mock Configuracion Fiscal Mexico sin mapeos
		mock_config = frappe._dict({"mapeos_cuentas_fiscales": []})

		def get_single_side_effect(doctype):
			if doctype == "Facturacion Mexico Settings":
				return mock_settings
			return frappe._dict({})

		def get_doc_side_effect(doctype, name):
			if doctype == "Configuracion Fiscal Mexico":
				return mock_config
			return frappe._dict({})

		with patch("frappe.get_single", side_effect=get_single_side_effect):
			with patch("frappe.db.get_value", return_value="Test Config"):
				with patch("frappe.get_doc", side_effect=get_doc_side_effect):
					with self.assertRaises(frappe.ValidationError) as context:
						service._map_tax_account_to_sat("Cuenta Sin Mapeo - _TC")

					error_msg = str(context.exception)
					# Verificar que el error menciona la cuenta
					self.assertIn("Cuenta Sin Mapeo", error_msg)


class TestE4ValidateObjetoImp(_E4TestBase):
	"""
	Test E4.6: _validate_objeto_imp_consistency()

	Validar consistencia ObjetoImp vs presencia de impuestos.
	"""

	def test_throw_when_objeto_imp_01_but_has_taxes(self):
		"""Test: error si ObjetoImp 01 (no objeto) pero tiene impuestos."""


		service = TimbradoAPI()

		item = frappe._dict({"item_code": "ITEM-001"})
		taxes_payload = [{"type": "002", "rate": 0.16}]  # IVA presente

		with self.assertRaises(frappe.ValidationError) as context:
			service._validate_objeto_imp_consistency("01", taxes_payload, item)

		error_msg = str(context.exception)
		# Verificar que contiene información clave (puede incluir HTML)
		self.assertIn("ITEM-001", error_msg)
		self.assertIn("No objeto de impuesto", error_msg)

	def test_throw_when_objeto_imp_02_but_no_taxes(self):
		"""Test: error si ObjetoImp 02 (sí objeto) pero sin impuestos."""


		service = TimbradoAPI()

		item = frappe._dict({"item_code": "ITEM-001"})
		taxes_payload = []  # Sin impuestos

		with self.assertRaises(frappe.ValidationError) as context:
			service._validate_objeto_imp_consistency("02", taxes_payload, item)

		error_msg = str(context.exception)
		# Verificar que contiene información clave (puede incluir HTML)
		self.assertIn("ITEM-001", error_msg)
		self.assertIn("objeto de impuesto", error_msg)

	def test_pass_when_objeto_imp_02_with_taxes(self):
		"""Test: pasa validación si ObjetoImp 02 y tiene impuestos."""


		service = TimbradoAPI()

		item = frappe._dict({"item_code": "ITEM-001"})
		taxes_payload = [{"type": "002", "rate": 0.16}]

		# No debe lanzar excepción
		try:
			service._validate_objeto_imp_consistency("02", taxes_payload, item)
		except frappe.ValidationError:
			self.fail("No debería lanzar error con ObjetoImp 02 y taxes")


class TestE4ValidateCurrency(_E4TestBase):
	"""
	Test E4.7: _validate_currency_consistency()

	Validar consistencia moneda payload vs Sales Invoice.
	"""

	def test_throw_when_currencies_mismatch(self):
		"""Test: error si moneda payload ≠ moneda SI."""


		service = TimbradoAPI()

		invoice_data = {"currency": "USD"}
		sales_invoice = frappe._dict({"currency": "MXN"})

		with self.assertRaises(frappe.ValidationError) as context:
			service._validate_currency_consistency(invoice_data, sales_invoice)

		self.assertIn("Moneda inconsistente", str(context.exception))

	def test_pass_when_currencies_match(self):
		"""Test: pasa validación si monedas coinciden."""


		service = TimbradoAPI()

		invoice_data = {"currency": "MXN"}
		sales_invoice = frappe._dict({"currency": "MXN", "conversion_rate": 1.0})

		# No debe lanzar excepción
		try:
			service._validate_currency_consistency(invoice_data, sales_invoice)
		except frappe.ValidationError:
			self.fail("No debería lanzar error con monedas iguales")


class TestE4ValidatePayloadCompleteness(_E4TestBase):
	"""
	Test E4.8: _validate_payload_completeness_ro()

	Validar completitud estructural payload antes de envío PAC.
	"""

	def test_throw_when_customer_data_incomplete(self):
		"""Test: error si faltan campos customer requeridos."""


		service = TimbradoAPI()

		invoice_data = {
			"customer": {"legal_name": "Test Customer"},  # Falta tax_id, tax_system
			"payment_form": "01",
			"use": "G03",
			"items": [{"product": {"product_key": "01010101", "unit_key": "E48", "description": "Test"}}],
		}
		sales_invoice = frappe._dict({"name": "SI-TEST-001"})

		with self.assertRaises(frappe.ValidationError) as context:
			service._validate_payload_completeness_ro(invoice_data, sales_invoice)

		error_msg = str(context.exception)
		self.assertIn("No se puede timbrar", error_msg)
		self.assertIn("RFC del Cliente faltante", error_msg)
		self.assertIn("Régimen Fiscal del Cliente faltante", error_msg)

	def test_throw_when_items_empty(self):
		"""Test: error si items[] vacío."""


		service = TimbradoAPI()

		invoice_data = {
			"customer": {"legal_name": "Test", "tax_id": "XAXX010101000", "tax_system": "601"},
			"payment_form": "01",
			"use": "G03",
			"items": [],  # Vacío
		}
		sales_invoice = frappe._dict({"name": "SI-TEST-001"})

		with self.assertRaises(frappe.ValidationError) as context:
			service._validate_payload_completeness_ro(invoice_data, sales_invoice)

		self.assertIn("La factura no tiene productos/conceptos para timbrar", str(context.exception))

	def test_throw_when_tax_fields_incomplete(self):
		"""Test: error si faltan campos en taxes del item."""


		service = TimbradoAPI()

		invoice_data = {
			"customer": {"legal_name": "Test", "tax_id": "XAXX010101000", "tax_system": "601"},
			"payment_form": "01",
			"use": "G03",
			"items": [
				{
					"product": {
						"product_key": "01010101",
						"unit_key": "E48",
						"description": "Test",
						"taxability": "02",
						"taxes": [
							{
								"type": "002",
								# Falta: factor, rate, withholding
							}
						],
					}
				}
			],
		}
		sales_invoice = frappe._dict({"name": "SI-TEST-001"})

		with self.assertRaises(frappe.ValidationError) as context:
			service._validate_payload_completeness_ro(invoice_data, sales_invoice)

		error_msg = str(context.exception)
		self.assertIn("factor faltante", error_msg)
		# rate solo se valida cuando factor está presente (condicional en validar_rate_por_tipo)
		self.assertIn("withholding faltante", error_msg)

	def test_pass_when_payload_complete(self):
		"""Test: pasa validación con payload completo."""


		service = TimbradoAPI()

		invoice_data = {
			"customer": {"legal_name": "Test Customer", "tax_id": "XAXX010101000", "tax_system": "601"},
			"payment_form": "01",
			"use": "G03",
			"items": [
				{
					"product": {
						"product_key": "01010101",
						"unit_key": "E48",
						"description": "Test Item",
						"taxability": "02",
						"taxes": [{"type": "IVA", "factor": "Tasa", "rate": 0.16, "withholding": False}],
					}
				}
			],
		}
		sales_invoice = frappe._dict({"name": "SI-TEST-001"})

		# No debe lanzar excepción
		try:
			result = service._validate_payload_completeness_ro(invoice_data, sales_invoice)
			self.assertTrue(result)
		except frappe.ValidationError:
			self.fail("No debería lanzar error con payload completo")


class TestE4IntegrationSmoke(_E4TestBase):
	"""
	Test E4 Integración Smoke: Validaciones E4

	Test smoke de validaciones E4.7 y E4.8 con payload simulado.
	NO mock de métodos internos (RG-003.7).
	"""

	def test_integration_validate_currency_and_completeness(self):
		"""Test: validaciones E4.7 + E4.8 con payload completo."""


		service = TimbradoAPI()

		# Sales Invoice mínimo
		sales_invoice = frappe._dict({"name": "SI-TEST-001", "currency": "MXN"})

		# Payload completo válido
		invoice_data = {
			"currency": "MXN",
			"payment_form": "01",
			"use": "G03",
			"customer": {"legal_name": "Test Customer SA de CV", "tax_id": "XAXX010101000", "tax_system": "601"},
			"items": [
				{
					"product": {
						"product_key": "01010101",
						"unit_key": "E48",
						"description": "Test Item",
						"taxability": "02",
						"taxes": [{"type": "IVA", "factor": "Tasa", "rate": 0.16, "withholding": False}],
					},
					"quantity": 1,
					"unit_price": 1000.0,
				}
			],
		}

		# Ejecutar validaciones E4.7 y E4.8 (no deben lanzar error)
		try:
			service._validate_currency_consistency(invoice_data, sales_invoice)
			result = service._validate_payload_completeness_ro(invoice_data, sales_invoice)

			self.assertTrue(result)

		except frappe.ValidationError as e:
			self.fail(f"Validaciones E4.7/E4.8 fallaron con payload válido: {str(e)}")
