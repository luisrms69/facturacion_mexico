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


def _make_config(
	company: str,
	reglas: list,
	*,
	wizard_completado: bool = True,
	tol_abs: "float | None" = None,
	tol_pct: "float | None" = None,
) -> str:
	config_name = f"CFDI-REC-CFG-{company}"
	if frappe.db.exists("Configuracion CFDI Recibidos", config_name):
		frappe.delete_doc("Configuracion CFDI Recibidos", config_name, force=True)
	config = frappe.new_doc("Configuracion CFDI Recibidos")
	config.company = company
	config.wizard_completado = 1 if wizard_completado else 0
	if tol_abs is not None:
		config.tolerancia_total_absoluta = tol_abs
	if tol_pct is not None:
		config.tolerancia_total_porcentual = tol_pct
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
		self,
		item_code=None,
		sat_key=None,
		description="Servicio de prueba",
		unit_price=100.0,
		quantity=1,
		expense_account=None,
	) -> dict:
		"""Crea un concepto con item_code y expense_account pre-asignados."""
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
			"expense_account": expense_account or self.expense_account,
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

	def test_posting_date_igual_a_fecha_xml(self):
		"""posting_date de la PI = fecha de emisión del XML, no la fecha de hoy."""
		cfdi = self._make_cfdi("004")
		result = build_purchase_invoice(cfdi)
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])
		cfdi_issue_date = frappe.db.get_value("CFDI Recibido", cfdi, "issue_date")
		self.assertEqual(str(pi.posting_date), str(cfdi_issue_date))

	def test_fechas_con_xml_antiguo(self):
		"""CFDI con fecha antigua: posting_date, bill_date y due_date = fecha del XML."""
		issue = "2024-03-15"
		cfdi = self._make_cfdi("005", issue_date=issue)
		result = build_purchase_invoice(cfdi)
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])
		self.assertEqual(str(pi.posting_date), issue)
		self.assertEqual(str(pi.bill_date), issue)
		self.assertEqual(str(pi.due_date), issue)

	def test_falla_si_issue_date_vacio(self):
		"""CFDI sin fecha de emisión debe fallar con ValidationError — no usar today() como fallback."""
		cfdi = self._make_cfdi("005B", issue_date="2024-03-15")
		# Vaciar issue_date directamente en BD para simular XML sin fecha
		frappe.db.set_value("CFDI Recibido", cfdi, "issue_date", None)
		frappe.db.commit()
		with self.assertRaises(frappe.ValidationError) as ctx:
			build_purchase_invoice(cfdi)
		self.assertIn("fecha de emisión", str(ctx.exception))
		# No debe existir PI vinculada
		self.assertIsNone(frappe.db.get_value("CFDI Recibido", cfdi, "purchase_invoice"))

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
		"""expense_account en PI viene de concepto.expense_account (asignado en el concepto)."""
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
			self._concepto(description="Servicio A", unit_price=60.0, expense_account=self.expense_account),
			self._concepto(description="Servicio B", unit_price=40.0, expense_account=self.expense_account),
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


# ---------------------------------------------------------------------------
# Tests de lógica pura — _within_tolerance (sin BD, sin frappe)
# ---------------------------------------------------------------------------


class TestWithinTolerance(unittest.TestCase):
	"""Tests de _within_tolerance como función pura."""

	def _call(self, diff, total_xml, tol_abs, tol_pct):
		from facturacion_mexico.cfdi_recibidos.services.purchase_invoice_builder import (
			_within_tolerance,
		)

		return _within_tolerance(diff, total_xml, tol_abs, tol_pct)

	def test_pasa_por_tolerancia_absoluta(self):
		self.assertTrue(self._call(0.5, 100.0, 1.0, 0.0))

	def test_falla_absoluta_porcentual_desactivada(self):
		self.assertFalse(self._call(2.0, 100.0, 1.0, 0.0))

	def test_pasa_por_tolerancia_porcentual(self):
		# diff=1.5, tol_abs=1.0 → abs falla; tol_pct=2.0% de 100=2.0 ≥ 1.5 → pasa
		self.assertTrue(self._call(1.5, 100.0, 1.0, 2.0))

	def test_falla_excede_ambas_tolerancias(self):
		# diff=3.0, tol_abs=1.0 → abs falla; 2% de 100=2.0 < 3.0 → pct falla
		self.assertFalse(self._call(3.0, 100.0, 1.0, 2.0))

	def test_porcentual_cero_desactiva_porcentual(self):
		# tol_pct=0 → pct desactivado; abs falla también → False
		self.assertFalse(self._call(2.0, 100.0, 0.5, 0.0))

	def test_diff_cero_siempre_pasa(self):
		self.assertTrue(self._call(0.0, 100.0, 0.0, 0.0))

	def test_total_cero_no_activa_porcentual(self):
		# total=0 → división bloqueada; solo importa abs
		self.assertFalse(self._call(2.0, 0.0, 1.0, 5.0))

	def test_diff_exactamente_igual_a_absoluta_pasa(self):
		self.assertTrue(self._call(1.0, 100.0, 1.0, 0.0))

	def test_diff_exactamente_igual_a_porcentual_pasa(self):
		# diff=2.0, 2% de 100=2.0 → pasa (<=)
		self.assertTrue(self._call(2.0, 100.0, 0.5, 2.0))


# ---------------------------------------------------------------------------
# Tests de tolerancia configurable — integración con Configuracion CFDI
# ---------------------------------------------------------------------------


class TestToleranciaConfigurable(unittest.TestCase):
	"""Tests de tolerancia leída desde Configuracion CFDI Recibidos."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.expense_account = _get_expense_account()
		cls.acc_iva = _get_or_create_tax_account(f"_TOLA IVA {_H}", TEST_COMPANY)
		cls.supplier_name = _create_supplier(f"_TOLA Prov {_H}")
		cls.test_item = _get_or_create_test_item(f"_TOLA-ITEM-{_H}", cls.expense_account)

	@classmethod
	def tearDownClass(cls):
		config_name = f"CFDI-REC-CFG-{TEST_COMPANY}"
		if frappe.db.exists("Configuracion CFDI Recibidos", config_name):
			frappe.delete_doc("Configuracion CFDI Recibidos", config_name, force=True)
		_delete_if_exists("Item", cls.test_item)
		try:
			_delete_if_exists("Account", cls.acc_iva)
		except Exception:
			pass
		try:
			_delete_if_exists("Supplier", cls.supplier_name)
		except Exception:
			pass
		super().tearDownClass()

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
		return f"{_UUID_PREFIX}TC{suffix}"

	def _make_cfdi_tola(self, suffix: str, total: float = 116.0) -> str:
		uuid = self._uuid(suffix)
		self._cleanup_uuids.append(uuid)
		doc = frappe.new_doc("CFDI Recibido")
		doc.company = TEST_COMPANY
		doc.uuid = uuid
		doc.supplier_rfc = TEST_SUPPLIER_RFC
		doc.supplier_name = f"_TOLA Prov {_H}"
		doc.receiver_rfc = frappe.db.get_value("Company", TEST_COMPANY, "tax_id") or "RFC000000000"
		doc.status = "Clasificado"
		doc.cfdi_type = "I"
		doc.xml_hash = frappe.generate_hash()[:64]
		doc.supplier = self.supplier_name
		doc.issue_date = "2026-01-15"
		doc.total = total
		doc.subtotal = total - 16.0
		doc.currency = frappe.db.get_value("Company", TEST_COMPANY, "default_currency") or "MXN"
		doc.exchange_rate = 1.0
		doc.impuestos_json = json.dumps(
			{
				"traslados": [
					{"impuesto": "002", "tipo_factor": "Tasa", "tasa_cuota": "0.160000", "importe": 16.0}
				],
				"retenciones": [],
			}
		)
		doc.append(
			"conceptos",
			{
				"sat_product_key": TEST_SAT_KEY,
				"description": "Servicio TOLA",
				"quantity": 1,
				"unit_key": "E48",
				"unit": "Servicio",
				"unit_price": total - 16.0,
				"amount": total - 16.0,
				"discount": 0,
				"tax_object": "02",
				"taxes_json": "{}",
				"item_code": self.test_item,
				"expense_account": self.expense_account,
			},
		)
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return doc.name

	def test_usa_defaults_si_config_sin_campos(self):
		"""Config sin tolerancias explícitas usa defaults: abs=1.0, pct=0.5."""
		_make_config(TEST_COMPANY, [_regla("002", 0.16, "IVA", self.acc_iva)])
		# defaults → tol_abs=1.0; diff=0 al crear PI normal → pasa
		cfdi = self._make_cfdi_tola("D01")
		result = build_purchase_invoice(cfdi)
		self.assertEqual(result["status"], "ok")

	def test_tolerancia_absoluta_estricta_bloquea_diff_pequena(self):
		"""Config con tol_abs=0.10 y tol_pct=0 → diff=0.50 en idempotencia causa error."""
		_make_config(
			TEST_COMPANY,
			[_regla("002", 0.16, "IVA", self.acc_iva)],
			tol_abs=0.10,
			tol_pct=0.0,
		)
		cfdi = self._make_cfdi_tola("E01", total=116.0)
		build_purchase_invoice(cfdi)
		# Simular idempotencia con diff=0.50 (mayor que tol_abs=0.10, pct desactivado)
		frappe.db.set_value(
			"CFDI Recibido", cfdi, {"purchase_invoice": None, "status": "Clasificado", "total": 116.5}
		)
		frappe.db.commit()
		with self.assertRaises(frappe.ValidationError):
			build_purchase_invoice(cfdi)

	def test_tolerancia_porcentual_permite_diff_mayor_que_absoluta(self):
		"""Config tol_abs=0.10, tol_pct=2.0 → diff=0.50 pasa (0.50/116.5 ≈ 0.43% < 2%)."""
		_make_config(
			TEST_COMPANY,
			[_regla("002", 0.16, "IVA", self.acc_iva)],
			tol_abs=0.10,
			tol_pct=2.0,
		)
		cfdi = self._make_cfdi_tola("P01", total=116.0)
		build_purchase_invoice(cfdi)
		frappe.db.set_value(
			"CFDI Recibido", cfdi, {"purchase_invoice": None, "status": "Clasificado", "total": 116.5}
		)
		frappe.db.commit()
		result = build_purchase_invoice(cfdi)
		self.assertEqual(result["status"], "ok")
		self.assertTrue(result["recovered"])

	def test_porcentual_cero_no_salva_diff_mayor_que_absoluta(self):
		"""tol_pct=0 no activa tolerancia porcentual aunque diff sea pequeño en porcentaje."""
		_make_config(
			TEST_COMPANY,
			[_regla("002", 0.16, "IVA", self.acc_iva)],
			tol_abs=0.10,
			tol_pct=0.0,
		)
		cfdi = self._make_cfdi_tola("P02", total=116.0)
		build_purchase_invoice(cfdi)
		# diff=0.30 < 0.5% de 116 pero tol_pct=0 → solo importa abs=0.10 → falla
		frappe.db.set_value(
			"CFDI Recibido", cfdi, {"purchase_invoice": None, "status": "Clasificado", "total": 116.3}
		)
		frappe.db.commit()
		with self.assertRaises(frappe.ValidationError):
			build_purchase_invoice(cfdi)


# ---------------------------------------------------------------------------
# Tests de batch — build_purchase_invoices_pending_batch
# ---------------------------------------------------------------------------

_BATCH_UUID_PREFIX = f"PIB{_H}BTCH"


class TestBatchGenerate(unittest.TestCase):
	"""Tests del endpoint batch build_purchase_invoices_pending_batch."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.expense_account = _get_expense_account()
		cls.acc_iva = _get_or_create_tax_account(f"_BTC IVA {_H}", TEST_COMPANY)
		cls.supplier_name = _create_supplier(f"_BTC Prov {_H}")
		cls.test_item = _get_or_create_test_item(f"_BTC-ITEM-{_H}", cls.expense_account)
		cls.config_name = _make_config(
			TEST_COMPANY,
			[_regla("002", 0.16, "IVA Acreditable", cls.acc_iva)],
		)

	@classmethod
	def tearDownClass(cls):
		_delete_if_exists("Configuracion CFDI Recibidos", cls.config_name)
		_delete_if_exists("Item", cls.test_item)
		try:
			_delete_if_exists("Account", cls.acc_iva)
		except Exception:
			pass
		try:
			_delete_if_exists("Supplier", cls.supplier_name)
		except Exception:
			pass
		super().tearDownClass()

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

	def _uuid(self, suffix):
		return f"{_BATCH_UUID_PREFIX}{suffix}"

	def _impuestos_iva(self):
		return {
			"traslados": [
				{"impuesto": "002", "tipo_factor": "Tasa", "tasa_cuota": "0.160000", "importe": 16.0}
			],
			"retenciones": [],
		}

	def _make_clasificado(self, suffix):
		"""CFDI elegible: todos los conceptos con item_code → status Clasificado."""
		uuid = self._uuid(suffix)
		self._cleanup_uuids.append(uuid)
		doc = frappe.new_doc("CFDI Recibido")
		doc.company = TEST_COMPANY
		doc.uuid = uuid
		doc.supplier_rfc = TEST_SUPPLIER_RFC
		doc.supplier_name = f"_BTC Prov {_H}"
		doc.receiver_rfc = frappe.db.get_value("Company", TEST_COMPANY, "tax_id") or "RFC000000000"
		doc.cfdi_type = "I"
		doc.xml_hash = frappe.generate_hash()[:64]
		doc.supplier = self.supplier_name
		doc.issue_date = "2026-01-20"
		doc.total = 116.0
		doc.subtotal = 100.0
		doc.currency = frappe.db.get_value("Company", TEST_COMPANY, "default_currency") or "MXN"
		doc.exchange_rate = 1.0
		doc.impuestos_json = json.dumps(self._impuestos_iva())
		doc.append(
			"conceptos",
			{
				"sat_product_key": TEST_SAT_KEY,
				"description": "Servicio batch",
				"quantity": 1,
				"unit_key": "E48",
				"unit": "Servicio",
				"unit_price": 100.0,
				"amount": 100.0,
				"discount": 0,
				"tax_object": "02",
				"taxes_json": "{}",
				"item_code": self.test_item,
				"expense_account": self.expense_account,
			},
		)
		doc.insert(ignore_permissions=True)
		# compute_stage requiere department; forzamos status para que el batch lo encuentre
		frappe.db.set_value("CFDI Recibido", doc.name, "status", "Clasificado")
		frappe.db.commit()
		return doc.name

	def _make_sin_item_code(self, suffix):
		"""CFDI que fallará en build: sin item_code, forzado a status 'Error conversión'."""
		uuid = self._uuid(suffix)
		self._cleanup_uuids.append(uuid)
		doc = frappe.new_doc("CFDI Recibido")
		doc.company = TEST_COMPANY
		doc.uuid = uuid
		doc.supplier_rfc = TEST_SUPPLIER_RFC
		doc.supplier_name = f"_BTC Prov {_H}"
		doc.receiver_rfc = frappe.db.get_value("Company", TEST_COMPANY, "tax_id") or "RFC000000000"
		doc.cfdi_type = "I"
		doc.xml_hash = frappe.generate_hash()[:64]
		doc.supplier = self.supplier_name
		doc.issue_date = "2026-01-20"
		doc.total = 116.0
		doc.subtotal = 100.0
		doc.currency = frappe.db.get_value("Company", TEST_COMPANY, "default_currency") or "MXN"
		doc.exchange_rate = 1.0
		doc.impuestos_json = json.dumps({"traslados": [], "retenciones": []})
		doc.append(
			"conceptos",
			{
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
			},
		)
		# "Error conversión" es terminal → validate no llama compute_stage
		doc.status = "Error conversión"
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return doc.name

	def _make_no_procesar(self, suffix):
		"""CFDI con no_procesar=1 → inelegible para batch."""
		uuid = self._uuid(suffix)
		self._cleanup_uuids.append(uuid)
		doc = frappe.new_doc("CFDI Recibido")
		doc.company = TEST_COMPANY
		doc.uuid = uuid
		doc.supplier_rfc = TEST_SUPPLIER_RFC
		doc.supplier_name = f"_BTC Prov {_H}"
		doc.receiver_rfc = frappe.db.get_value("Company", TEST_COMPANY, "tax_id") or "RFC000000000"
		doc.cfdi_type = "I"
		doc.xml_hash = frappe.generate_hash()[:64]
		doc.supplier = self.supplier_name
		doc.issue_date = "2026-01-20"
		doc.total = 116.0
		doc.subtotal = 100.0
		doc.currency = frappe.db.get_value("Company", TEST_COMPANY, "default_currency") or "MXN"
		doc.exchange_rate = 1.0
		doc.impuestos_json = json.dumps(self._impuestos_iva())
		doc.no_procesar = 1
		doc.append(
			"conceptos",
			{
				"sat_product_key": TEST_SAT_KEY,
				"description": "No procesar",
				"quantity": 1,
				"unit_key": "E48",
				"unit": "Servicio",
				"unit_price": 100.0,
				"amount": 100.0,
				"discount": 0,
				"tax_object": "02",
				"taxes_json": "{}",
				"item_code": self.test_item,
				"expense_account": self.expense_account,
			},
		)
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return doc.name

	def _run_batch(self):
		from facturacion_mexico.cfdi_recibidos.api import build_purchase_invoices_pending_batch

		return build_purchase_invoices_pending_batch()

	def _our_results(self, result, *cfdi_names):
		"""Filtra los resultados del batch a los CFDIs de este test."""
		names = set(cfdi_names)
		return [r for r in result["results"] if r["cfdi_recibido"] in names]

	# ------------------------------------------------------------------ #

	def test_procesa_todos_elegibles(self):
		"""Batch procesa múltiples CFDIs Clasificados y genera PI para cada uno."""
		c1 = self._make_clasificado("BT01")
		c2 = self._make_clasificado("BT02")
		result = self._run_batch()
		ours = self._our_results(result, c1, c2)
		self.assertEqual(len(ours), 2)
		self.assertTrue(all(r["status"] == "ok" for r in ours))
		self.assertTrue(all(r["purchase_invoice"] for r in ours))

	def test_omite_no_procesar(self):
		"""CFDIs con no_procesar=1 no aparecen en los resultados del batch."""
		elegible = self._make_clasificado("BT03")
		excluido = self._make_no_procesar("BT04")
		result = self._run_batch()
		cfdi_names_in_results = {r["cfdi_recibido"] for r in result["results"]}
		self.assertIn(elegible, cfdi_names_in_results)
		self.assertNotIn(excluido, cfdi_names_in_results)

	def test_omite_estados_no_elegibles(self):
		"""CFDIs en estados distintos de Clasificado/Error conversión no se procesan."""
		elegible = self._make_clasificado("BT05")
		# Sin item_code → compute_stage devuelve "Falta clasificación" (inelegible)
		uuid_inel = self._uuid("BT06")
		self._cleanup_uuids.append(uuid_inel)
		doc = frappe.new_doc("CFDI Recibido")
		doc.company = TEST_COMPANY
		doc.uuid = uuid_inel
		doc.supplier_rfc = TEST_SUPPLIER_RFC
		doc.supplier_name = f"_BTC Prov {_H}"
		doc.receiver_rfc = frappe.db.get_value("Company", TEST_COMPANY, "tax_id") or "RFC000000000"
		doc.cfdi_type = "I"
		doc.xml_hash = frappe.generate_hash()[:64]
		doc.supplier = self.supplier_name
		doc.issue_date = "2026-01-20"
		doc.total = 116.0
		doc.subtotal = 100.0
		doc.currency = frappe.db.get_value("Company", TEST_COMPANY, "default_currency") or "MXN"
		doc.exchange_rate = 1.0
		doc.impuestos_json = json.dumps({"traslados": [], "retenciones": []})
		doc.append(
			"conceptos",
			{
				"sat_product_key": TEST_SAT_KEY,
				"description": "Sin item",
				"quantity": 1,
				"unit_key": "E48",
				"unit": "Servicio",
				"unit_price": 100.0,
				"amount": 100.0,
				"discount": 0,
				"tax_object": "02",
				"taxes_json": "{}",
				# sin item_code → status Falta clasificación
			},
		)
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		inelegible = doc.name

		result = self._run_batch()
		cfdi_names_in_results = {r["cfdi_recibido"] for r in result["results"]}
		self.assertIn(elegible, cfdi_names_in_results)
		self.assertNotIn(inelegible, cfdi_names_in_results)

	def test_continua_si_cfdi_falla(self):
		"""Un CFDI con error no detiene el lote — el siguiente se procesa."""
		ok_cfdi = self._make_clasificado("BT07")
		err_cfdi = self._make_sin_item_code("BT08")

		result = self._run_batch()
		ours = self._our_results(result, ok_cfdi, err_cfdi)

		ok_results = [r for r in ours if r["cfdi_recibido"] == ok_cfdi]
		err_results = [r for r in ours if r["cfdi_recibido"] == err_cfdi]

		self.assertEqual(len(ok_results), 1)
		self.assertEqual(ok_results[0]["status"], "ok")

		self.assertEqual(len(err_results), 1)
		self.assertEqual(err_results[0]["status"], "error")
		self.assertIsNone(err_results[0]["purchase_invoice"])

	def test_respeta_idempotencia_no_duplica_pi(self):
		"""Segunda ejecución del batch no crea PI duplicada para CFDI ya convertido."""
		cfdi = self._make_clasificado("BT09")

		result1 = self._run_batch()
		ours1 = self._our_results(result1, cfdi)
		self.assertEqual(len(ours1), 1)
		self.assertEqual(ours1[0]["status"], "ok")

		# Segunda ejecución: CFDI ya es "Convertido a PI" → no aparece en batch
		result2 = self._run_batch()
		ours2 = self._our_results(result2, cfdi)
		self.assertEqual(len(ours2), 0, "CFDI convertido no debe aparecer en segundo batch")

		# Solo una PI para este UUID
		pi_count = frappe.db.count("Purchase Invoice", {"fm_cfdi_uuid": self._uuid("BT09")})
		self.assertEqual(pi_count, 1)

	def test_retorna_estructura_correcta(self):
		"""Batch retorna {total, ok, error, skipped, results} con tipos correctos."""
		c1 = self._make_clasificado("BT10")
		c2 = self._make_sin_item_code("BT11")

		result = self._run_batch()
		ours = self._our_results(result, c1, c2)

		self.assertIn("total", result)
		self.assertIn("ok", result)
		self.assertIn("error", result)
		self.assertIn("skipped", result)
		self.assertIn("results", result)
		self.assertIsInstance(result["results"], list)
		self.assertEqual(result["skipped"], 0)

		ok_ours = sum(1 for r in ours if r["status"] == "ok")
		err_ours = sum(1 for r in ours if r["status"] == "error")
		self.assertEqual(ok_ours, 1)
		self.assertEqual(err_ours, 1)


# ---------------------------------------------------------------------------
# Tests de propagación cost_center y project al Purchase Invoice
# ---------------------------------------------------------------------------


class TestPurchaseInvoiceBuilderCostCenterProject(unittest.TestCase):
	"""Verifica que cost_center y project del CFDI Recibido se propagan al PI y sus líneas."""

	_HCC = frappe.generate_hash()[:6]
	_UUID_PREFIX_CC = f"PICC{_HCC}0001000100"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.expense_account = _get_expense_account()
		cls.config_name = _make_config(
			TEST_COMPANY,
			[
				_regla(
					"002",
					0.16,
					"IVA Test CC",
					_get_or_create_tax_account(f"_CC IVA {cls._HCC}", TEST_COMPANY),
				)
			],
		)
		cls.supplier_name = _create_supplier(f"_CC Prov {cls._HCC}")
		cls.test_item = _get_or_create_test_item(f"_CC-ITEM-{cls._HCC}", cls.expense_account)
		# Cost Center
		parent_cc = frappe.db.get_value("Cost Center", {"is_group": 1, "company": TEST_COMPANY}, "name")
		cls.cost_center = None
		if parent_cc:
			cc_name = f"_Test CC PI {cls._HCC}"
			existing = frappe.db.get_value(
				"Cost Center", {"cost_center_name": cc_name, "company": TEST_COMPANY}, "name"
			)
			if existing:
				cls.cost_center = existing
			else:
				cc = frappe.new_doc("Cost Center")
				cc.cost_center_name = cc_name
				cc.company = TEST_COMPANY
				cc.parent_cost_center = parent_cc
				cc.is_group = 0
				cc.insert(ignore_permissions=True)
				frappe.db.commit()
				cls.cost_center = cc.name
		# Project
		proj_name = f"_Test Proj PI {cls._HCC}"
		cls.project = None
		existing = frappe.db.get_value("Project", {"project_name": proj_name}, "name")
		if existing:
			cls.project = existing
		else:
			try:
				proj = frappe.new_doc("Project")
				proj.project_name = proj_name
				proj.status = "Open"
				proj.insert(ignore_permissions=True)
				frappe.db.commit()
				cls.project = proj.name  # usar el name real asignado por ERPNext
			except Exception:
				pass

	@classmethod
	def tearDownClass(cls):
		_delete_if_exists("Configuracion CFDI Recibidos", cls.config_name)
		_delete_if_exists("Item", cls.test_item)
		if cls.cost_center:
			_delete_if_exists("Cost Center", cls.cost_center)
		_delete_if_exists("Project", cls.project)
		try:
			_delete_if_exists("Supplier", cls.supplier_name)
		except Exception:
			pass
		super().tearDownClass()

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

	def _make_cfdi_with_cc(self, suffix, cost_center=None, project=None):
		uuid = f"{self._UUID_PREFIX_CC}{suffix}"
		self._cleanup_uuids.append(uuid)
		doc = frappe.new_doc("CFDI Recibido")
		doc.company = TEST_COMPANY
		doc.uuid = uuid
		doc.supplier_rfc = f"CC{self._HCC}"[:13]
		doc.supplier_name = f"_CC Prov {self._HCC}"
		doc.receiver_rfc = frappe.db.get_value("Company", TEST_COMPANY, "tax_id") or "RFC000000000"
		doc.cfdi_type = "I"
		doc.xml_hash = frappe.generate_hash()[:64]
		doc.supplier = self.supplier_name
		doc.issue_date = "2026-01-20"
		doc.total = 116.0
		doc.subtotal = 100.0
		doc.currency = frappe.db.get_value("Company", TEST_COMPANY, "default_currency") or "MXN"
		doc.exchange_rate = 1.0
		doc.impuestos_json = json.dumps(
			{
				"traslados": [
					{"impuesto": "002", "tipo_factor": "Tasa", "tasa_cuota": "0.160000", "importe": 16.0}
				],
				"retenciones": [],
			}
		)
		if cost_center:
			doc.cost_center = cost_center
		if project:
			doc.project = project
		doc.append(
			"conceptos",
			{
				"sat_product_key": TEST_SAT_KEY,
				"description": "Servicio CC test",
				"quantity": 1,
				"unit_key": "E48",
				"unit": "Servicio",
				"unit_price": 100.0,
				"amount": 100.0,
				"discount": 0,
				"tax_object": "02",
				"taxes_json": "{}",
				"item_code": self.test_item,
				"expense_account": self.expense_account,
			},
		)
		doc.insert(ignore_permissions=True)
		frappe.db.set_value("CFDI Recibido", doc.name, "status", "Clasificado")
		frappe.db.commit()
		return doc.name

	def test_cost_center_y_project_llegan_al_pi_header_y_lineas(self):
		"""PI hereda cost_center y project del CFDI Recibido en header y en cada línea."""
		if not self.cost_center:
			self.skipTest("No hay Cost Center disponible en el site de pruebas")
		cfdi = self._make_cfdi_with_cc("CC01", cost_center=self.cost_center, project=self.project)
		result = build_purchase_invoice(cfdi)
		self.assertEqual(result["status"], "ok")
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])
		self.assertEqual(pi.cost_center, self.cost_center)
		self.assertEqual(pi.project, self.project)
		for item in pi.items:
			self.assertEqual(item.cost_center, self.cost_center)
			self.assertEqual(item.project, self.project)

	def test_sin_cost_center_ni_project_pi_se_crea_sin_error(self):
		"""CFDI sin cost_center ni project genera PI correctamente — campos vacíos no bloquean."""
		cfdi = self._make_cfdi_with_cc("CC02", cost_center=None, project=None)
		result = build_purchase_invoice(cfdi)
		self.assertEqual(result["status"], "ok")
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])
		# No deben tener valor forzado
		self.assertIn(pi.cost_center or "", ["", None] + ([self.cost_center] if self.cost_center else []))

	def test_solo_cost_center_sin_project(self):
		"""Solo cost_center definido — llega al PI; project queda vacío."""
		if not self.cost_center:
			self.skipTest("No hay Cost Center disponible en el site de pruebas")
		cfdi = self._make_cfdi_with_cc("CC03", cost_center=self.cost_center, project=None)
		result = build_purchase_invoice(cfdi)
		self.assertEqual(result["status"], "ok")
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])
		self.assertEqual(pi.cost_center, self.cost_center)
		for item in pi.items:
			self.assertEqual(item.cost_center, self.cost_center)


# ---------------------------------------------------------------------------
# Test de integración — falla de cuenta contable no crea PI
# ---------------------------------------------------------------------------

_INT_H = frappe.generate_hash()[:6]
_INT_UUID_PREFIX = f"INT{_INT_H}0000000100"
_INT_SUPPLIER_RFC = f"BINT{_INT_H}"[:13]


class TestExpenseAccountFallaNoCreaPi(unittest.TestCase):
	"""
	Integración end-to-end: modo Automatico CoA SAT sin cuenta imputable
	→ no se crea Purchase Invoice, CFDI queda en 'Error conversión'.

	Flujo completo a través de api.build_purchase_invoice (incluye rollback
	y actualización de status).
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		# Asegurar que existe el grupo "Gastos"
		if not frappe.db.exists("Item Group", "Gastos"):
			root_ig = (
				frappe.db.get_value("Item Group", {"parent_item_group": ""}, "name") or "All Item Groups"
			)
			g = frappe.new_doc("Item Group")
			g.item_group_name = "Gastos"
			g.parent_item_group = root_ig
			g.is_group = 1
			g.insert(ignore_permissions=True)

		# Limpiar residuos de runs anteriores (item groups _INT IG * en cualquier padre)
		stale = frappe.get_all("Item Group", filters={"item_group_name": ["like", "_INT IG %"]}, pluck="name")
		for s in stale:
			try:
				frappe.delete_doc("Item Group", s, force=True)
			except Exception:
				pass
		if stale:
			frappe.db.commit()

		# Item Group con código SAT "99" bajo "Gastos" — ninguna cuenta en CoA empieza con "603-99-"
		cls.ig_name = f"_INT IG {_INT_H}"
		ig = frappe.new_doc("Item Group")
		ig.item_group_name = cls.ig_name
		ig.parent_item_group = "Gastos"
		ig.is_group = 0
		ig.insert(ignore_permissions=True)
		frappe.db.set_value("Item Group", cls.ig_name, "fm_codigo_sufijo_sat", "99")

		# Item de compra bajo ese item_group
		cls.item_code = f"_INT-ITEM-{_INT_H}"
		if not frappe.db.exists("Item", cls.item_code):
			item = frappe.new_doc("Item")
			item.item_code = cls.item_code
			item.item_name = cls.item_code
			item.item_group = cls.ig_name
			item.is_stock_item = 0
			item.is_purchase_item = 1
			item.is_sales_item = 0
			item.stock_uom = "H87 - Pieza"
			item.append("uoms", {"uom": "H87 - Pieza", "conversion_factor": 1})
			item.flags.ignore_validate = True
			item.insert(ignore_permissions=True)

		# Department para el mapeo SAT
		cls.department = f"_Test INT Dept {_INT_H}"
		if not frappe.db.exists("Department", cls.department):
			parent_dept = frappe.db.get_value("Department", {"is_group": 1}, "name") or "All Departments"
			dept = frappe.new_doc("Department")
			dept.department_name = cls.department
			dept.parent_department = parent_dept
			dept.company = TEST_COMPANY
			dept.is_group = 0
			dept.insert(ignore_permissions=True)
			frappe.db.commit()

		# Supplier
		cls.supplier_name = f"_INT Prov {_INT_H}"
		if not frappe.db.exists("Supplier", cls.supplier_name):
			sup_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
			sup = frappe.new_doc("Supplier")
			sup.supplier_name = cls.supplier_name
			sup.supplier_group = sup_group
			sup.tax_id = _INT_SUPPLIER_RFC
			sup.insert(ignore_permissions=True)

		# Cuenta de impuesto (para no fallar en tax_resolver)
		cls.acc_iva = _get_or_create_tax_account(f"_INT IVA {_INT_H}", TEST_COMPANY)

		# Configuracion CFDI Recibidos — modo Automatico CoA SAT, formato ###-##-###
		config_name = f"CFDI-REC-CFG-{TEST_COMPANY}"
		if frappe.db.exists("Configuracion CFDI Recibidos", config_name):
			frappe.delete_doc("Configuracion CFDI Recibidos", config_name, force=True)
		config = frappe.new_doc("Configuracion CFDI Recibidos")
		config.company = TEST_COMPANY
		config.modo_resolucion_contable = "Automatico CoA SAT"
		config.formato_coa = "###-##-###"
		config.append(
			"reglas_impuesto",
			{
				"impuesto_sat": "002",
				"tipo_factor": "Tasa",
				"tasa_cuota": 0.16,
				"descripcion": "IVA Test INT",
				"es_retencion": 0,
				"cuenta_impuesto": cls.acc_iva,
				"activo": 1,
			},
		)
		# Mapeo de departamento → familia SAT 603
		config.append(
			"mapeo_departamentos",
			{
				"department": cls.department,
				"familia_sat": "603 Gastos de administración",
			},
		)
		config.insert(ignore_permissions=True, ignore_links=True)

		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		config_name = f"CFDI-REC-CFG-{TEST_COMPANY}"
		if frappe.db.exists("Configuracion CFDI Recibidos", config_name):
			frappe.delete_doc("Configuracion CFDI Recibidos", config_name, force=True)
		_delete_if_exists("Item", cls.item_code)
		try:
			_delete_if_exists("Account", cls.acc_iva)
		except Exception:
			pass
		try:
			_delete_if_exists("Supplier", cls.supplier_name)
		except Exception:
			pass
		try:
			frappe.delete_doc("Item Group", cls.ig_name, force=True)
		except Exception:
			pass
		try:
			frappe.delete_doc("Department", cls.department, force=True)
		except Exception:
			pass
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		self._cfdi_name = None

	def tearDown(self):
		if self._cfdi_name and frappe.db.exists("CFDI Recibido", self._cfdi_name):
			try:
				frappe.delete_doc("CFDI Recibido", self._cfdi_name, force=True)
				frappe.db.commit()
			except Exception:
				pass

	def _make_cfdi_sin_cuenta(self, suffix: str) -> str:
		uuid = f"{_INT_UUID_PREFIX}{suffix}"
		doc = frappe.new_doc("CFDI Recibido")
		doc.company = TEST_COMPANY
		doc.uuid = uuid
		doc.supplier_rfc = _INT_SUPPLIER_RFC
		doc.supplier_name = self.supplier_name
		doc.receiver_rfc = frappe.db.get_value("Company", TEST_COMPANY, "tax_id") or "RFC000000000"
		doc.status = "Clasificado"
		doc.cfdi_type = "I"
		doc.xml_hash = frappe.generate_hash()[:64]
		doc.supplier = self.supplier_name
		doc.department = self.__class__.department
		doc.issue_date = "2026-01-15"
		doc.total = 116.0
		doc.subtotal = 100.0
		doc.currency = frappe.db.get_value("Company", TEST_COMPANY, "default_currency") or "MXN"
		doc.exchange_rate = 1.0
		doc.impuestos_json = json.dumps(
			{
				"traslados": [
					{"impuesto": "002", "tipo_factor": "Tasa", "tasa_cuota": "0.160000", "importe": 16.0}
				],
				"retenciones": [],
			}
		)
		doc.append(
			"conceptos",
			{
				"sat_product_key": TEST_SAT_KEY,
				"description": "Servicio sin cuenta",
				"quantity": 1,
				"unit_key": "E48",
				"unit": "Servicio",
				"unit_price": 100.0,
				"amount": 100.0,
				"discount": 0,
				"tax_object": "02",
				"taxes_json": "{}",
				"item_code": self.item_code,
				"item_group": self.ig_name,
				# expense_account vacío — debe resolverse automáticamente pero fallará
			},
		)
		doc.insert(ignore_permissions=True, ignore_links=True)
		frappe.db.commit()
		return doc.name

	def test_sin_cuenta_no_crea_pi_y_cfdi_queda_en_error(self):
		"""
		Regla de negocio crítica: si la resolución automática falla por ausencia de cuenta
		compatible en el CoA, NO se crea Purchase Invoice y el CFDI queda en 'Error conversión'.
		"""
		from facturacion_mexico.cfdi_recibidos.api import build_purchase_invoice as api_build

		self._cfdi_name = self._make_cfdi_sin_cuenta("E01")
		uuid = frappe.db.get_value("CFDI Recibido", self._cfdi_name, "uuid")

		# Confirmar que no existe PI previa
		self.assertIsNone(frappe.db.get_value("Purchase Invoice", {"fm_cfdi_uuid": uuid}, "name"))

		# Llamar a través de la api (que hace rollback + set status)
		result = api_build(self._cfdi_name)

		# La api debe retornar error
		self.assertEqual(result["status"], "error", f"Esperado 'error', obtenido: {result}")

		# No debe existir Purchase Invoice vinculada al UUID
		pi_name = frappe.db.get_value("Purchase Invoice", {"fm_cfdi_uuid": uuid}, "name")
		self.assertIsNone(pi_name, f"No debe existir PI para UUID {uuid}, pero existe: {pi_name}")

		# El CFDI debe quedar en 'Error conversión'
		status = frappe.db.get_value("CFDI Recibido", self._cfdi_name, "status")
		self.assertEqual(
			status,
			"Error conversión",
			f"CFDI debe quedar en 'Error conversión', está en: {status}",
		)
