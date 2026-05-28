"""
Tests de PurchaseInvoiceBuilder — F.3.

Crea y limpia fixtures reales en BD: CFDI Recibido, supplier, Configuracion CFDI Recibidos,
cuentas de impuesto, Items con item_defaults.

Arquitectura F.3:
- PIBuilder lee item_code desde CFDI Recibido Concepto.
- No consulta CFDI Concepto Mapping para construir la PI.
- Bloquea si algún concepto no tiene item_code.
"""

import json
import unittest

import frappe
from frappe.utils import flt, today

from facturacion_mexico.cfdi_recibidos.services.purchase_invoice_builder import (
	build_purchase_invoice,
)

TEST_COMPANY = "_Test Company"
TEST_SAT_KEY = "43231500"
_H = frappe.generate_hash()[:6]
_UUID_PREFIX = f"PIB{_H}0001000100"
TEST_SUPPLIER_RFC = f"BPIB{_H}"[:13]


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------


def _get_or_create_tax_account(account_name: str, company: str) -> str:
	existing = frappe.db.get_value("Account", {"account_name": account_name, "company": company}, "name")
	if existing:
		return existing

	parent = frappe.db.get_value(
		"Account", {"account_type": "Tax", "is_group": 1, "company": company}, "name"
	) or frappe.db.get_value("Account", {"root_type": "Liability", "is_group": 1, "company": company}, "name")

	if not parent:
		frappe.throw(f"No hay cuenta padre disponible para crear cuentas de prueba en {company}")

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
		{"root_type": "Expense", "is_group": 0},
	]:
		account = frappe.db.get_value("Account", filters, "name")
		if account:
			return account
	frappe.throw("No se encontró ninguna cuenta de tipo Expense en el site de pruebas")


def _get_or_create_supplier_group() -> str:
	group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
	if group:
		return group
	group = frappe.db.get_value("Supplier Group", {"is_group": 1}, "name")
	if not group:
		root = frappe.new_doc("Supplier Group")
		root.supplier_group_name = "All Supplier Groups"
		root.is_group = 1
		root.insert(ignore_permissions=True)
		frappe.db.commit()
		group = root.name
	leaf = frappe.new_doc("Supplier Group")
	leaf.supplier_group_name = "Services"
	leaf.is_group = 0
	leaf.parent_supplier_group = group
	leaf.insert(ignore_permissions=True)
	frappe.db.commit()
	return leaf.name


def _create_supplier(supplier_name: str) -> str:
	if frappe.db.exists("Supplier", supplier_name):
		return supplier_name
	sup_group = _get_or_create_supplier_group()
	sup = frappe.new_doc("Supplier")
	sup.supplier_name = supplier_name
	sup.supplier_group = sup_group
	sup.tax_id = TEST_SUPPLIER_RFC
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


def _get_or_create_test_item(item_code: str, expense_account: str) -> str:
	"""
	Crea un item de compra (no stock, no ventas) con expense_account en item_defaults.
	ERPNext derivará expense_account en la PI desde estos defaults.
	"""
	if frappe.db.exists("Item", item_code):
		return item_code

	if not frappe.db.exists("Item Group", "Gastos"):
		root = frappe.db.get_value("Item Group", {"parent_item_group": ""}, "name") or "All Item Groups"
		g = frappe.new_doc("Item Group")
		g.item_group_name = "Gastos"
		g.parent_item_group = root
		g.insert(ignore_permissions=True)
		frappe.db.commit()

	if not frappe.db.exists("Item Group", "_PIB TestIG"):
		ig = frappe.new_doc("Item Group")
		ig.item_group_name = "_PIB TestIG"
		ig.parent_item_group = "Gastos"
		ig.insert(ignore_permissions=True)
		frappe.db.commit()

	doc = frappe.new_doc("Item")
	doc.item_code = item_code
	doc.item_name = item_code
	doc.item_group = "_PIB TestIG"
	doc.is_stock_item = 0
	doc.is_purchase_item = 1
	doc.is_sales_item = 0
	doc.stock_uom = "H87 - Pieza"
	doc.append("uoms", {"uom": "H87 - Pieza", "conversion_factor": 1})
	doc.append(
		"item_defaults",
		{
			"company": TEST_COMPANY,
			"expense_account": expense_account,
			"default_warehouse": "",
		},
	)
	doc.flags.ignore_validate = True
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return item_code


def _delete_if_exists(doctype: str, name: str):
	if name and frappe.db.exists(doctype, name):
		frappe.delete_doc(doctype, name, force=True)
		frappe.db.commit()


# ---------------------------------------------------------------------------
# Clase de prueba
# ---------------------------------------------------------------------------


class TestPurchaseInvoiceBuilder(unittest.TestCase):
	"""Tests del PurchaseInvoiceBuilder — conversión CFDI Recibido → Purchase Invoice (F.3)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		cls.expense_account = _get_expense_account()

		cls.acc_iva_nac = _get_or_create_tax_account(f"_PIB IVA Nac {_H}", TEST_COMPANY)
		cls.acc_ret_isr = _get_or_create_tax_account(f"_PIB Ret ISR {_H}", TEST_COMPANY)
		cls.acc_ret_iva = _get_or_create_tax_account(f"_PIB Ret IVA {_H}", TEST_COMPANY)
		cls.all_tax_accounts = [cls.acc_iva_nac, cls.acc_ret_isr, cls.acc_ret_iva]

		cls.config_name = _make_config(
			TEST_COMPANY,
			[
				_regla("002", 0.16, "IVA Acreditable (Nacional)", cls.acc_iva_nac),
				_regla("001", 0.00, "ISR Retenido", cls.acc_ret_isr, es_retencion=True),
				_regla("002", 0.00, "IVA Retenido", cls.acc_ret_iva, es_retencion=True),
			],
		)

		cls.supplier_name = _create_supplier(f"_PIB Proveedor {_H}")

		# Item de prueba con expense_account configurado — PIBuilder lo usará vía concepto.item_code
		cls.test_item = _get_or_create_test_item(f"_PIB-ITEM-{_H}", cls.expense_account)

	@classmethod
	def tearDownClass(cls):
		_delete_if_exists("Configuracion CFDI Recibidos", cls.config_name)
		_delete_if_exists("Item", cls.test_item)
		for acc in getattr(cls, "all_tax_accounts", []):
			try:
				_delete_if_exists("Account", acc)
			except Exception:
				pass
		try:
			_delete_if_exists("Supplier", cls.supplier_name)
		except Exception:
			pass
		super().tearDownClass()

	# ------------------------------------------------------------------ #
	# Helpers de instancia                                                 #
	# ------------------------------------------------------------------ #

	def setUp(self):
		self._cleanup_uuids = []

	def tearDown(self):
		for uuid in self._cleanup_uuids:
			pi_name = frappe.db.get_value("Purchase Invoice", {"fm_cfdi_uuid": uuid}, "name")
			if pi_name:
				try:
					frappe.delete_doc("Purchase Invoice", pi_name, force=True)
				except Exception:
					pass
			cfdi_name = frappe.db.get_value("CFDI Recibido", {"uuid": uuid}, "name")
			if cfdi_name:
				try:
					frappe.delete_doc("CFDI Recibido", cfdi_name, force=True)
				except Exception:
					pass
		if self._cleanup_uuids:
			frappe.db.commit()

	def _uuid(self, suffix: str) -> str:
		return f"{_UUID_PREFIX}{suffix}"

	def _concepto(
		self, item_code=None, sat_key=None, description="Servicio de prueba", unit_price=100.0, quantity=1
	) -> dict:
		"""Crea un concepto con item_code pre-asignado."""
		return {
			"sat_product_key": sat_key or TEST_SAT_KEY,
			"description": description,
			"quantity": quantity,
			"unit_key": "E48",
			"unit": "Servicio",
			"unit_price": unit_price,
			"amount": unit_price * quantity,
			"discount": 0,
			"tax_object": "02",
			"taxes_json": "{}",
			"item_code": item_code or self.test_item,
		}

	def _make_cfdi(
		self,
		suffix: str,
		total: float = 116.0,
		impuestos_json: dict | None = None,
		conceptos: list | None = None,
		issue_date: str | None = None,
	) -> str:
		uuid = self._uuid(suffix)
		self._cleanup_uuids.append(uuid)

		if impuestos_json is None:
			impuestos_json = {
				"traslados": [
					{
						"impuesto": "002",
						"tipo_factor": "Tasa",
						"tasa_cuota": "0.160000",
						"importe": 16.0,
					}
				],
				"retenciones": [],
			}

		if conceptos is None:
			conceptos = [self._concepto()]

		doc = frappe.new_doc("CFDI Recibido")
		doc.company = TEST_COMPANY
		doc.uuid = uuid
		doc.supplier_rfc = TEST_SUPPLIER_RFC
		doc.supplier_name = f"_PIB Proveedor {_H}"
		doc.receiver_rfc = frappe.db.get_value("Company", TEST_COMPANY, "tax_id") or "RFC000000000"
		doc.status = "Clasificado"
		doc.cfdi_type = "I"
		doc.xml_hash = frappe.generate_hash()[:64]
		doc.supplier = self.supplier_name
		doc.issue_date = issue_date or today()
		doc.total = total
		doc.subtotal = total - 16.0
		doc.currency = frappe.db.get_value("Company", TEST_COMPANY, "default_currency") or "MXN"
		doc.exchange_rate = 1.0
		doc.impuestos_json = json.dumps(impuestos_json)
		for c in conceptos:
			doc.append("conceptos", c)
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return doc.name

	# ------------------------------------------------------------------ #
	# Tests básicos — creación y vínculo                                   #
	# ------------------------------------------------------------------ #

	def test_crea_pi_en_draft(self):
		cfdi = self._make_cfdi("001")
		result = build_purchase_invoice(cfdi)
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])
		self.assertEqual(pi.docstatus, 0)

	def test_pi_vinculado_a_cfdi(self):
		cfdi = self._make_cfdi("002")
		result = build_purchase_invoice(cfdi)
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])
		self.assertEqual(pi.fm_cfdi_recibido, cfdi)

	def test_pi_uuid_en_fm_cfdi_uuid(self):
		cfdi = self._make_cfdi("003")
		result = build_purchase_invoice(cfdi)
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])
		self.assertEqual(pi.fm_cfdi_uuid, self._uuid("003"))

	def test_posting_date_es_hoy(self):
		cfdi = self._make_cfdi("004")
		result = build_purchase_invoice(cfdi)
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])
		self.assertEqual(str(pi.posting_date), today())

	def test_bill_date_es_fecha_emision(self):
		issue = "2024-03-15"
		cfdi = self._make_cfdi("005", issue_date=issue)
		result = build_purchase_invoice(cfdi)
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])
		self.assertEqual(str(pi.bill_date), issue)

	def test_cfdi_status_convertido(self):
		cfdi = self._make_cfdi("006")
		build_purchase_invoice(cfdi)
		status = frappe.db.get_value("CFDI Recibido", cfdi, "status")
		self.assertEqual(status, "Convertido a PI")

	def test_cfdi_purchase_invoice_link(self):
		cfdi = self._make_cfdi("007")
		result = build_purchase_invoice(cfdi)
		pi_link = frappe.db.get_value("CFDI Recibido", cfdi, "purchase_invoice")
		self.assertEqual(pi_link, result["purchase_invoice"])

	# ------------------------------------------------------------------ #
	# Tests F.3 — item_code desde concepto                                 #
	# ------------------------------------------------------------------ #

	def test_pi_usa_item_code_del_concepto(self):
		"""PI line usa el item_code del concepto, no de CFDI Concepto Mapping."""
		cfdi = self._make_cfdi("F01")
		result = build_purchase_invoice(cfdi)
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])
		self.assertGreater(len(pi.items), 0)
		self.assertEqual(pi.items[0].item_code, self.test_item)

	def test_bloquea_si_falta_item_code(self):
		"""PIBuilder lanza ValidationError si algún concepto no tiene item_code."""
		concepto_sin_item = {
			"sat_product_key": TEST_SAT_KEY,
			"description": "Sin clasificar",
			"quantity": 1,
			"unit_key": "E48",
			"unit": "Servicio",
			"unit_price": 100.0,
			"amount": 100.0,
			"discount": 0,
			"tax_object": "02",
			"taxes_json": "{}",
			# item_code ausente a propósito
		}
		cfdi = self._make_cfdi("F02", conceptos=[concepto_sin_item])
		with self.assertRaises(frappe.ValidationError) as ctx:
			build_purchase_invoice(cfdi)
		self.assertIn("item_code", str(ctx.exception))

	def test_bloquea_si_un_concepto_sin_item_code_entre_varios(self):
		"""Bloquea si hay mezcla de conceptos con y sin item_code."""
		conceptos = [
			self._concepto(),  # tiene item_code
			{  # sin item_code
				"sat_product_key": TEST_SAT_KEY,
				"description": "Sin clasificar",
				"quantity": 1,
				"unit_key": "E48",
				"unit": "Servicio",
				"unit_price": 50.0,
				"amount": 50.0,
				"discount": 0,
				"tax_object": "02",
				"taxes_json": "{}",
			},
		]
		cfdi = self._make_cfdi("F03", total=174.0, conceptos=conceptos)
		with self.assertRaises(frappe.ValidationError):
			build_purchase_invoice(cfdi)

	def test_mapping_no_consultado_para_construir_pi(self):
		"""PIBuilder NO consulta CFDI Concepto Mapping — usa concepto.item_code directamente."""
		from unittest.mock import patch

		import facturacion_mexico.cfdi_recibidos.services.purchase_invoice_builder as pib_module

		cfdi = self._make_cfdi("F04")
		# Si PIBuilder aún consultara CFDI Concepto Mapping, este patch lo detectaría
		with patch.object(frappe.db, "get_value", wraps=frappe.db.get_value) as mock_gv:
			result = build_purchase_invoice(cfdi)
			calls_mapping = [c for c in mock_gv.call_args_list if c[0] and c[0][0] == "CFDI Concepto Mapping"]
		self.assertEqual(len(calls_mapping), 0, "PIBuilder no debe consultar CFDI Concepto Mapping")
		self.assertIsNotNone(result["purchase_invoice"])

	# ------------------------------------------------------------------ #
	# Tests de items y taxes                                               #
	# ------------------------------------------------------------------ #

	def test_expense_account_derivada_del_item(self):
		"""expense_account en PI viene de item_defaults del item, no del mapping."""
		cfdi = self._make_cfdi("008")
		result = build_purchase_invoice(cfdi)
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])
		self.assertGreater(len(pi.items), 0)
		self.assertEqual(pi.items[0].expense_account, self.expense_account)

	def test_iva_traslado_es_add(self):
		cfdi = self._make_cfdi("009")
		result = build_purchase_invoice(cfdi)
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])
		iva_rows = [t for t in pi.taxes if t.account_head == self.acc_iva_nac]
		self.assertEqual(len(iva_rows), 1)
		self.assertEqual(iva_rows[0].add_deduct_tax, "Add")

	def test_grand_total_dentro_tolerancia(self):
		cfdi = self._make_cfdi("010", total=116.0)
		result = build_purchase_invoice(cfdi)
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])
		diff = abs(flt(pi.grand_total) - 116.0)
		self.assertLessEqual(diff, 0.02)

	def test_item_uom_derivado_del_item(self):
		"""UOM del PI item viene del stock_uom del item (H87 - Pieza)."""
		cfdi = self._make_cfdi("U01")
		result = build_purchase_invoice(cfdi)
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])
		self.assertGreater(len(pi.items), 0)
		item_uom = frappe.db.get_value("Item", self.test_item, "stock_uom")
		self.assertEqual(pi.items[0].uom, item_uom)
		self.assertNotEqual(pi.items[0].uom, "Nos")

	# ------------------------------------------------------------------ #
	# Idempotencia                                                         #
	# ------------------------------------------------------------------ #

	def test_idempotencia_caso_a_reparacion(self):
		"""PI válido existe pero CFDI sin vínculo → repara y devuelve recovered=True."""
		cfdi = self._make_cfdi("A01")
		result1 = build_purchase_invoice(cfdi)
		pi_name = result1["purchase_invoice"]

		frappe.db.set_value("CFDI Recibido", cfdi, {"purchase_invoice": None, "status": "Clasificado"})
		frappe.db.commit()

		result2 = build_purchase_invoice(cfdi)
		self.assertEqual(result2["status"], "ok")
		self.assertEqual(result2["purchase_invoice"], pi_name)
		self.assertTrue(result2["recovered"])

		status = frappe.db.get_value("CFDI Recibido", cfdi, "status")
		self.assertEqual(status, "Convertido a PI")

	def test_idempotencia_caso_b_bloquea_grand_total_mismatch(self):
		"""PI existe pero grand_total difiere del XML > tolerancia → ValidationError."""
		cfdi = self._make_cfdi("B01", total=116.0)
		build_purchase_invoice(cfdi)

		frappe.db.set_value("CFDI Recibido", cfdi, "total", 120.0)
		frappe.db.commit()

		with self.assertRaises(frappe.ValidationError):
			build_purchase_invoice(cfdi)

	def test_idempotencia_caso_c_bloquea_cfdi_diferente(self):
		"""PI con mismo UUID pero fm_cfdi_recibido de otro CFDI → ValidationError."""
		cfdi = self._make_cfdi("C01")
		result = build_purchase_invoice(cfdi)
		pi_name = result["purchase_invoice"]

		frappe.db.set_value("Purchase Invoice", pi_name, "fm_cfdi_recibido", "CFDI-RECIBIDO-OTRO")
		frappe.db.commit()

		with self.assertRaises(frappe.ValidationError):
			build_purchase_invoice(cfdi)

		frappe.db.set_value("Purchase Invoice", pi_name, "fm_cfdi_recibido", cfdi)
		frappe.db.commit()

	# ------------------------------------------------------------------ #
	# Retenciones y grand_total                                            #
	# ------------------------------------------------------------------ #

	def test_retencion_add_deduct_tax_deduct(self):
		"""Retención ISR → fila con add_deduct_tax='Deduct' y tax_amount positivo."""
		impuestos = {
			"traslados": [
				{"impuesto": "002", "tipo_factor": "Tasa", "tasa_cuota": "0.160000", "importe": 16.0}
			],
			"retenciones": [{"impuesto": "001", "importe": 10.0}],
		}
		cfdi = self._make_cfdi("B11", total=106.0, impuestos_json=impuestos)
		result = build_purchase_invoice(cfdi)
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])

		ret_rows = [t for t in pi.taxes if t.account_head == self.acc_ret_isr]
		self.assertEqual(len(ret_rows), 1)
		self.assertEqual(ret_rows[0].add_deduct_tax, "Deduct")
		self.assertGreater(flt(ret_rows[0].tax_amount), 0)

		diff = abs(flt(pi.grand_total) - 106.0)
		self.assertLessEqual(diff, 0.02, f"grand_total={pi.grand_total}, esperado≈106")

	def test_multiples_conceptos_procesados(self):
		"""Múltiples conceptos: todos los items tienen item_code y grand_total correcto."""
		conceptos = [
			self._concepto(description="Servicio A", unit_price=60.0),
			self._concepto(description="Servicio B", unit_price=40.0),
		]
		impuestos = {
			"traslados": [
				{"impuesto": "002", "tipo_factor": "Tasa", "tasa_cuota": "0.160000", "importe": 16.0}
			],
			"retenciones": [],
		}
		cfdi = self._make_cfdi("B12", total=116.0, impuestos_json=impuestos, conceptos=conceptos)
		result = build_purchase_invoice(cfdi)
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])

		self.assertEqual(len(pi.items), 2)
		for item in pi.items:
			self.assertEqual(item.item_code, self.test_item)

		diff = abs(flt(pi.grand_total) - 116.0)
		self.assertLessEqual(diff, 0.02, f"grand_total={pi.grand_total}, esperado≈116")

	# ------------------------------------------------------------------ #
	# Recuperación tras fallo simulado                                     #
	# ------------------------------------------------------------------ #

	def test_recovery_after_failed_cfdi_save(self):
		"""PI insertado OK pero cfdi_doc.save() falló → segundo intento recupera idempotente."""
		cfdi = self._make_cfdi("B21")
		result1 = build_purchase_invoice(cfdi)
		pi_name = result1["purchase_invoice"]
		self.assertFalse(result1["recovered"])

		frappe.db.set_value("CFDI Recibido", cfdi, {"purchase_invoice": None, "status": "Clasificado"})
		frappe.db.commit()

		result2 = build_purchase_invoice(cfdi)
		self.assertEqual(result2["status"], "ok")
		self.assertEqual(result2["purchase_invoice"], pi_name)
		self.assertTrue(result2["recovered"])

		cfdi_doc = frappe.get_doc("CFDI Recibido", cfdi)
		self.assertEqual(cfdi_doc.purchase_invoice, pi_name)
		self.assertEqual(cfdi_doc.status, "Convertido a PI")
