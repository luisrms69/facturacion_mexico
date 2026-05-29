"""
Tests de endpoints API CFDI Recibidos — Fase 3d.

Prueba build_purchase_invoice y suggest_supplier_from_cfdi
directamente como funciones Python (equivalente a llamada HTTP autenticada).
"""

import json
import unittest

import frappe

from facturacion_mexico.cfdi_recibidos.api import (
	build_purchase_invoice,
	suggest_supplier_from_cfdi,
)

TEST_COMPANY = "_Test Company"
TEST_SAT_KEY = "43231500"
_H = frappe.generate_hash()[:6]
_UUID_PREFIX = f"API{_H}0001"
TEST_SUPPLIER_RFC = f"BAPI{_H}"[:13]


# --------------------------------------------------------------------------- #
# Helpers de fixtures                                                           #
# --------------------------------------------------------------------------- #


def _get_or_create_tax_account(account_name: str, company: str) -> str:
	existing = frappe.db.get_value("Account", {"account_name": account_name, "company": company}, "name")
	if existing:
		return existing
	parent = frappe.db.get_value(
		"Account", {"account_type": "Tax", "is_group": 1, "company": company}, "name"
	) or frappe.db.get_value("Account", {"root_type": "Liability", "is_group": 1, "company": company}, "name")
	if not parent:
		frappe.throw(f"No hay cuenta padre para crear cuentas de prueba en {company}")
	acc = frappe.new_doc("Account")
	acc.account_name = account_name
	acc.company = company
	acc.parent_account = parent
	acc.account_type = "Tax"
	acc.insert(ignore_permissions=True)
	frappe.db.commit()
	return acc.name


def _get_expense_account() -> str:
	for filters in [
		{"account_type": "Expense Account", "company": TEST_COMPANY, "is_group": 0},
		{"root_type": "Expense", "company": TEST_COMPANY, "is_group": 0},
	]:
		account = frappe.db.get_value("Account", filters, "name")
		if account:
			return account
	frappe.throw("No se encontró cuenta de tipo Expense en el site de pruebas")


def _get_or_create_uom(uom_name: str):
	if not frappe.db.exists("UOM", uom_name):
		frappe.get_doc({"doctype": "UOM", "uom_name": uom_name}).insert(ignore_permissions=True)
		frappe.db.commit()


def _get_or_create_supplier_group() -> str:
	group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
	if group:
		return group
	parent = frappe.db.get_value("Supplier Group", {"is_group": 1}, "name")
	if not parent:
		root = frappe.new_doc("Supplier Group")
		root.supplier_group_name = "All Supplier Groups"
		root.is_group = 1
		root.insert(ignore_permissions=True)
		frappe.db.commit()
		parent = root.name
	leaf = frappe.new_doc("Supplier Group")
	leaf.supplier_group_name = f"_APIT {_H}"
	leaf.is_group = 0
	leaf.parent_supplier_group = parent
	leaf.insert(ignore_permissions=True)
	frappe.db.commit()
	return leaf.name


def _create_supplier(supplier_name: str, tax_id: str) -> str:
	if frappe.db.exists("Supplier", supplier_name):
		return supplier_name
	sup = frappe.new_doc("Supplier")
	sup.supplier_name = supplier_name
	sup.supplier_group = _get_or_create_supplier_group()
	sup.tax_id = tax_id
	sup.insert(ignore_permissions=True)
	frappe.db.commit()
	return sup.name


def _regla(impuesto_sat, tasa_cuota, descripcion, cuenta, *, es_retencion=False, tipo_factor="Tasa"):
	return {
		"impuesto_sat": impuesto_sat,
		"tipo_factor": tipo_factor,
		"tasa_cuota": tasa_cuota,
		"descripcion": descripcion,
		"es_retencion": 1 if es_retencion else 0,
		"cuenta_impuesto": cuenta,
		"activo": 1,
	}


def _make_config(company: str, reglas: list, *, wizard_completado: bool = True) -> str:
	config_name = f"CFDI-REC-CFG-{company}"
	if frappe.db.exists("Configuracion CFDI Recibidos", config_name):
		frappe.delete_doc("Configuracion CFDI Recibidos", config_name, force=True)
	config = frappe.new_doc("Configuracion CFDI Recibidos")
	config.company = company
	config.wizard_completado = 1 if wizard_completado else 0
	for regla in reglas:
		config.append("reglas_impuesto", regla)
	config.insert(ignore_permissions=True, ignore_links=True)
	frappe.db.commit()
	return config_name


def _make_mapping(supplier_rfc: str, sat_key: str, expense_account: str) -> str:
	existing = frappe.db.get_value(
		"CFDI Concepto Mapping",
		{"supplier_rfc": supplier_rfc, "sat_product_key": sat_key, "company": ["in", ["", None]]},
		"name",
	)
	if existing:
		frappe.delete_doc("CFDI Concepto Mapping", existing, force=True)
	doc = frappe.new_doc("CFDI Concepto Mapping")
	doc.supplier_rfc = supplier_rfc
	doc.sat_product_key = sat_key
	doc.target_type = "ExpenseAccount"
	doc.target_account = expense_account
	doc.is_active = 1
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _get_or_create_expense_item() -> str:
	"""Crea un Item de gasto válido (SAT UOM, bajo Gastos) para pruebas de PI."""
	item_code = f"_GASTO-API-{_H}"
	if frappe.db.exists("Item", item_code):
		return item_code
	ig_name = f"_API Gastos {_H}"
	if not frappe.db.exists("Item Group", ig_name):
		gastos = frappe.db.get_value("Item Group", "Gastos", "name")
		if not gastos:
			root = frappe.db.get_value("Item Group", {"parent_item_group": ""}, "name") or "All Item Groups"
			g = frappe.new_doc("Item Group")
			g.item_group_name = "Gastos"
			g.parent_item_group = root
			g.insert(ignore_permissions=True)
		ig = frappe.new_doc("Item Group")
		ig.item_group_name = ig_name
		ig.parent_item_group = "Gastos"
		ig.insert(ignore_permissions=True)
	item = frappe.new_doc("Item")
	item.item_code = item_code
	item.item_name = f"Item gasto API test {_H}"
	item.item_group = ig_name
	item.is_stock_item = 0
	item.is_purchase_item = 1
	item.is_sales_item = 0
	item.stock_uom = "H87 - Pieza"
	item.insert(ignore_permissions=True)
	frappe.db.commit()
	return item_code


def _delete_if_exists(doctype: str, name: str):
	if name and frappe.db.exists(doctype, name):
		frappe.delete_doc(doctype, name, force=True)
		frappe.db.commit()


def _make_cfdi(
	uuid: str,
	status: str = "Clasificado",
	supplier: str | None = None,
	impuestos: dict | None = None,
	supplier_rfc: str = TEST_SUPPLIER_RFC,
	item_code: str | None = None,
) -> str:
	"""Crea CFDI Recibido mínimo con un concepto para pruebas."""
	if impuestos is None:
		impuestos = {
			"traslados": [
				{"impuesto": "002", "tipo_factor": "Tasa", "tasa_cuota": "0.160000", "importe": 16.0}
			],
			"retenciones": [],
		}
	cfdi = frappe.new_doc("CFDI Recibido")
	cfdi.uuid = uuid
	cfdi.company = TEST_COMPANY
	cfdi.status = status
	cfdi.supplier = supplier
	cfdi.supplier_rfc = supplier_rfc
	cfdi.supplier_name = f"_API Prov {_H}"
	cfdi.currency = frappe.db.get_value("Company", TEST_COMPANY, "default_currency") or "MXN"
	cfdi.exchange_rate = 1.0
	cfdi.issue_date = frappe.utils.today()
	cfdi.subtotal = 100.0
	cfdi.total_impuestos_trasladados = 16.0
	cfdi.total = 116.0
	cfdi.impuestos_json = json.dumps(impuestos)
	concepto = {
		"sat_product_key": TEST_SAT_KEY,
		"description": "Servicio API test",
		"quantity": 1.0,
		"unit_price": 100.0,
		"subtotal": 100.0,
		"discount": 0.0,
		"total": 116.0,
	}
	if item_code:
		concepto["item_code"] = item_code
	cfdi.append("conceptos", concepto)
	cfdi.insert(ignore_permissions=True)
	frappe.db.set_value("CFDI Recibido", cfdi.name, "status", status)
	frappe.db.commit()
	return cfdi.name


# --------------------------------------------------------------------------- #
# Clase 1: build_purchase_invoice                                               #
# --------------------------------------------------------------------------- #


class TestBuildPurchaseInvoiceEndpoint(unittest.TestCase):
	"""Tests del endpoint build_purchase_invoice."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_get_or_create_uom("Nos")

		cls.expense_account = _get_expense_account()
		cls.acc_iva = _get_or_create_tax_account(f"_APIT IVA {_H}", TEST_COMPANY)

		cls.config_name = _make_config(
			TEST_COMPANY,
			[_regla("002", 0.16, "IVA Acreditable (Nacional)", cls.acc_iva)],
		)
		cls.supplier_name = _create_supplier(f"_API Prov {_H}", TEST_SUPPLIER_RFC)
		cls.mapping_name = _make_mapping(TEST_SUPPLIER_RFC, TEST_SAT_KEY, cls.expense_account)
		cls.test_item = _get_or_create_expense_item()

	@classmethod
	def tearDownClass(cls):
		_delete_if_exists("Item", cls.test_item)
		_delete_if_exists("CFDI Concepto Mapping", cls.mapping_name)
		_delete_if_exists("Configuracion CFDI Recibidos", cls.config_name)
		_delete_if_exists("Account", cls.acc_iva)
		_delete_if_exists("Supplier", cls.supplier_name)
		super().tearDownClass()

	def setUp(self):
		self._cleanup_cfdis = []
		self._cleanup_pis = []

	def tearDown(self):
		for pi_name in self._cleanup_pis:
			_delete_if_exists("Purchase Invoice", pi_name)
		for cfdi_name in self._cleanup_cfdis:
			_delete_if_exists("CFDI Recibido", cfdi_name)

	def _uuid(self, n: int) -> str:
		return f"{_UUID_PREFIX}BLD{n:04d}"

	def test_crea_pi_draft_correctamente(self):
		cfdi_name = _make_cfdi(self._uuid(1), supplier=self.supplier_name, item_code=self.test_item)
		self._cleanup_cfdis.append(cfdi_name)

		result = build_purchase_invoice(cfdi_name)

		self.assertEqual(result["status"], "ok")
		self.assertIsNotNone(result["purchase_invoice"])
		self.assertFalse(result["recovered"])
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])
		self._cleanup_pis.append(pi.name)
		self.assertEqual(pi.fm_cfdi_uuid, self._uuid(1))
		self.assertEqual(pi.fm_cfdi_recibido, cfdi_name)
		self.assertEqual(len(pi.items), 1)
		self.assertEqual(pi.docstatus, 0)

	def test_bloquea_status_no_listo(self):
		cfdi_name = _make_cfdi(self._uuid(2), status="Cargado", supplier=self.supplier_name)
		self._cleanup_cfdis.append(cfdi_name)

		with self.assertRaises(frappe.ValidationError):
			build_purchase_invoice(cfdi_name)

	def test_maneja_error_tax_resolver(self):
		impuestos_invalidos = {
			"traslados": [
				{"impuesto": "999", "tipo_factor": "Tasa", "tasa_cuota": "0.160000", "importe": 16.0}
			],
			"retenciones": [],
		}
		cfdi_name = _make_cfdi(
			self._uuid(3),
			supplier=self.supplier_name,
			impuestos=impuestos_invalidos,
			item_code=self.test_item,
		)
		self._cleanup_cfdis.append(cfdi_name)

		result = build_purchase_invoice(cfdi_name)

		self.assertEqual(result["status"], "error")
		self.assertIsNone(result["purchase_invoice"])
		self.assertFalse(result["recovered"])
		self.assertIn("999", result["message"])

	def test_idempotencia_devuelve_recovered(self):
		cfdi_name = _make_cfdi(self._uuid(4), supplier=self.supplier_name, item_code=self.test_item)
		self._cleanup_cfdis.append(cfdi_name)

		result1 = build_purchase_invoice(cfdi_name)
		self.assertEqual(result1["status"], "ok")
		self._cleanup_pis.append(result1["purchase_invoice"])

		result2 = build_purchase_invoice(cfdi_name)

		self.assertEqual(result2["status"], "recovered")
		self.assertTrue(result2["recovered"])
		self.assertEqual(result2["purchase_invoice"], result1["purchase_invoice"])

	def test_cfdi_status_error_conversion_al_fallar(self):
		impuestos_invalidos = {
			"traslados": [
				{"impuesto": "999", "tipo_factor": "Tasa", "tasa_cuota": "0.160000", "importe": 16.0}
			],
			"retenciones": [],
		}
		cfdi_name = _make_cfdi(
			self._uuid(5),
			supplier=self.supplier_name,
			impuestos=impuestos_invalidos,
			item_code=self.test_item,
		)
		self._cleanup_cfdis.append(cfdi_name)

		build_purchase_invoice(cfdi_name)

		status = frappe.db.get_value("CFDI Recibido", cfdi_name, "status")
		self.assertEqual(status, "Error conversión")


# --------------------------------------------------------------------------- #
# Clase 2: suggest_supplier_from_cfdi                                           #
# --------------------------------------------------------------------------- #


class TestSuggestSupplierEndpoint(unittest.TestCase):
	"""Tests del endpoint suggest_supplier_from_cfdi."""

	_RFC_EXISTENTE = f"SGTE{_H}"[:13]
	_RFC_INEXISTENTE = f"SGIN{_H}"[:13]

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.supplier_existente = _create_supplier(f"_SGT Prov {_H}", cls._RFC_EXISTENTE)

	@classmethod
	def tearDownClass(cls):
		_delete_if_exists("Supplier", cls.supplier_existente)
		super().tearDownClass()

	def setUp(self):
		self._cleanup_cfdis = []

	def tearDown(self):
		for cfdi_name in self._cleanup_cfdis:
			_delete_if_exists("CFDI Recibido", cfdi_name)

	def _uuid(self, n: int) -> str:
		return f"{_UUID_PREFIX}SGT{n:04d}"

	def _make_cfdi_suggest(self, uuid: str, supplier_rfc: str) -> str:
		cfdi = frappe.new_doc("CFDI Recibido")
		cfdi.uuid = uuid
		cfdi.company = TEST_COMPANY
		cfdi.status = "Falta proveedor"
		cfdi.supplier_rfc = supplier_rfc
		cfdi.supplier_name = f"Proveedor {supplier_rfc}"
		cfdi.currency = frappe.db.get_value("Company", TEST_COMPANY, "default_currency") or "MXN"
		cfdi.exchange_rate = 1.0
		cfdi.issue_date = frappe.utils.today()
		cfdi.total = 100.0
		cfdi.insert(ignore_permissions=True)
		frappe.db.commit()
		return cfdi.name

	def test_encuentra_supplier_existente_por_tax_id(self):
		cfdi_name = self._make_cfdi_suggest(self._uuid(1), self._RFC_EXISTENTE)
		self._cleanup_cfdis.append(cfdi_name)

		result = suggest_supplier_from_cfdi(cfdi_name)

		self.assertEqual(result["status"], "found")
		self.assertTrue(result["supplier_exists"])
		self.assertEqual(result["supplier"], self.supplier_existente)

	def test_sugiere_datos_si_no_existe_supplier(self):
		cfdi_name = self._make_cfdi_suggest(self._uuid(2), self._RFC_INEXISTENTE)
		self._cleanup_cfdis.append(cfdi_name)

		result = suggest_supplier_from_cfdi(cfdi_name)

		self.assertEqual(result["status"], "not_found")
		self.assertFalse(result["supplier_exists"])
		self.assertIsNone(result["supplier"])
		self.assertEqual(result["suggested_data"]["tax_id"], self._RFC_INEXISTENTE)
		self.assertIn("supplier_name", result["suggested_data"])

	def test_no_crea_supplier_automaticamente(self):
		cfdi_name = self._make_cfdi_suggest(self._uuid(3), self._RFC_INEXISTENTE)
		self._cleanup_cfdis.append(cfdi_name)

		count_before = frappe.db.count("Supplier", {"tax_id": self._RFC_INEXISTENTE})
		suggest_supplier_from_cfdi(cfdi_name)
		count_after = frappe.db.count("Supplier", {"tax_id": self._RFC_INEXISTENTE})

		self.assertEqual(count_before, count_after)
