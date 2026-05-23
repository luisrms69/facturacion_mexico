"""
Tests de PurchaseInvoiceBuilder — Fase 3c.

Crea y limpia fixtures reales en BD: CFDI Recibido, supplier, CFM, template, cuentas de impuesto.
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


def _get_or_create_uom(uom_name: str) -> str:
	if not frappe.db.exists("UOM", uom_name):
		uom = frappe.new_doc("UOM")
		uom.uom_name = uom_name
		uom.insert(ignore_permissions=True)
		frappe.db.commit()
	return uom_name


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


def _make_template(title: str, accounts: list) -> str:
	if frappe.db.exists("Purchase Taxes and Charges Template", title):
		frappe.delete_doc("Purchase Taxes and Charges Template", title, force=True)
	tmpl = frappe.new_doc("Purchase Taxes and Charges Template")
	tmpl.title = title
	tmpl.company = TEST_COMPANY
	for account in accounts:
		tmpl.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": account,
				"description": account,
				"tax_amount": 0,
			},
		)
	tmpl.insert(ignore_permissions=True)
	frappe.db.commit()
	return tmpl.name


def _make_cfm(company: str, template: str, mapeos: list) -> str:
	cfm_name = f"CFM-{company}"
	if frappe.db.exists("Configuracion Fiscal Mexico", cfm_name):
		frappe.delete_doc("Configuracion Fiscal Mexico", cfm_name, force=True)
	cfm = frappe.new_doc("Configuracion Fiscal Mexico")
	cfm.company = company
	cfm.cfdi_recibidos_tax_template = template
	for rol, cuenta in mapeos:
		cfm.append("mapeo_cuentas", {"rol_fiscal": rol, "cuenta_impuesto": cuenta})
	cfm.insert(ignore_permissions=True, ignore_mandatory=not mapeos)
	frappe.db.commit()
	return cfm_name


def _make_mapping(
	supplier_rfc: str,
	sat_key: str,
	expense_account: str,
	retencion_isr_rol: str = "",
	retencion_iva_rol: str = "",
) -> str:
	doc = frappe.new_doc("CFDI Concepto Mapping")
	doc.supplier_rfc = supplier_rfc
	doc.sat_product_key = sat_key
	doc.target_type = "ExpenseAccount"
	doc.target_account = expense_account
	doc.is_active = 1
	if retencion_isr_rol:
		doc.retencion_isr_rol_fiscal = retencion_isr_rol
	if retencion_iva_rol:
		doc.retencion_iva_rol_fiscal = retencion_iva_rol
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _delete_if_exists(doctype: str, name: str):
	if name and frappe.db.exists(doctype, name):
		frappe.delete_doc(doctype, name, force=True)
		frappe.db.commit()


# ---------------------------------------------------------------------------
# Clase de prueba
# ---------------------------------------------------------------------------


class TestPurchaseInvoiceBuilder(unittest.TestCase):
	"""Tests del PurchaseInvoiceBuilder — conversión CFDI Recibido → Purchase Invoice."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		_get_or_create_uom("Nos")

		cls.expense_account = _get_expense_account()

		cls.acc_iva_nac = _get_or_create_tax_account(f"_PIB IVA Nac {_H}", TEST_COMPANY)
		cls.acc_ret_isr = _get_or_create_tax_account(f"_PIB Ret ISR {_H}", TEST_COMPANY)
		cls.acc_ret_iva = _get_or_create_tax_account(f"_PIB Ret IVA {_H}", TEST_COMPANY)
		cls.all_tax_accounts = [cls.acc_iva_nac, cls.acc_ret_isr, cls.acc_ret_iva]

		cls.template_name = _make_template(f"_PIB Tpl {_H}", cls.all_tax_accounts)

		cls.cfm_name = _make_cfm(
			TEST_COMPANY,
			cls.template_name,
			[
				("IVA Acreditable (Nacional)", cls.acc_iva_nac),
				("ISR Retenido (Honorarios)", cls.acc_ret_isr),
				("IVA Retenido (Honorarios)", cls.acc_ret_iva),
			],
		)

		cls.supplier_name = _create_supplier(f"_PIB Proveedor {_H}")

		cls.mapping_name = _make_mapping(
			supplier_rfc=TEST_SUPPLIER_RFC,
			sat_key=TEST_SAT_KEY,
			expense_account=cls.expense_account,
			retencion_isr_rol="ISR Retenido (Honorarios)",
			retencion_iva_rol="IVA Retenido (Honorarios)",
		)

	@classmethod
	def tearDownClass(cls):
		_delete_if_exists("CFDI Concepto Mapping", cls.mapping_name)
		_delete_if_exists("Configuracion Fiscal Mexico", cls.cfm_name)
		_delete_if_exists("Purchase Taxes and Charges Template", cls.template_name)
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
			conceptos = [
				{
					"sat_product_key": TEST_SAT_KEY,
					"description": "Servicio de prueba",
					"quantity": 1,
					"unit_key": "E48",
					"unit": "Servicio",
					"unit_price": 100.0,
					"amount": 100.0,
					"discount": 0,
					"tax_object": "02",
					"taxes_json": "{}",
				}
			]

		doc = frappe.new_doc("CFDI Recibido")
		doc.company = TEST_COMPANY
		doc.uuid = uuid
		doc.supplier_rfc = TEST_SUPPLIER_RFC
		doc.supplier_name = f"_PIB Proveedor {_H}"
		doc.receiver_rfc = frappe.db.get_value("Company", TEST_COMPANY, "tax_id") or "RFC000000000"
		doc.status = "Listo"
		doc.cfdi_type = "I"
		doc.xml_hash = frappe.generate_hash()[:64]
		doc.supplier = self.supplier_name
		doc.issue_date = issue_date or today()
		doc.total = total
		doc.subtotal = total - 16.0
		# Usar la moneda real de la empresa para evitar mismatch con Creditors account
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
	# Tests de items y taxes                                               #
	# ------------------------------------------------------------------ #

	def test_expense_account_en_item(self):
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

	# ------------------------------------------------------------------ #
	# Idempotencia                                                         #
	# ------------------------------------------------------------------ #

	def test_idempotencia_caso_a_reparacion(self):
		"""PI válido existe pero CFDI sin vínculo → repara y devuelve recovered=True."""
		cfdi = self._make_cfdi("A01")
		result1 = build_purchase_invoice(cfdi)
		pi_name = result1["purchase_invoice"]

		# Simular que cfdi_doc.save() falló: desvinculamos el CFDI
		frappe.db.set_value("CFDI Recibido", cfdi, {"purchase_invoice": None, "status": "Listo"})
		frappe.db.commit()

		result2 = build_purchase_invoice(cfdi)
		self.assertEqual(result2["status"], "ok")
		self.assertEqual(result2["purchase_invoice"], pi_name)
		self.assertTrue(result2["recovered"])

		# Verificar que el CFDI quedó reparado
		status = frappe.db.get_value("CFDI Recibido", cfdi, "status")
		self.assertEqual(status, "Convertido a PI")

	def test_idempotencia_caso_b_bloquea_grand_total_mismatch(self):
		"""PI existe pero grand_total difiere del XML > tolerancia → ValidationError."""
		cfdi = self._make_cfdi("B01", total=116.0)
		build_purchase_invoice(cfdi)

		# Cambiar total del CFDI para provocar mismatch (diff=4 MXN > 0.02)
		frappe.db.set_value("CFDI Recibido", cfdi, "total", 120.0)
		frappe.db.commit()

		with self.assertRaises(frappe.ValidationError):
			build_purchase_invoice(cfdi)

	def test_idempotencia_caso_c_bloquea_cfdi_diferente(self):
		"""PI con mismo UUID pero fm_cfdi_recibido de otro CFDI → ValidationError."""
		cfdi = self._make_cfdi("C01")
		result = build_purchase_invoice(cfdi)
		pi_name = result["purchase_invoice"]

		# Simular que el PI pertenece a un CFDI diferente
		frappe.db.set_value("Purchase Invoice", pi_name, "fm_cfdi_recibido", "CFDI-RECIBIDO-OTRO")
		frappe.db.commit()

		with self.assertRaises(frappe.ValidationError):
			build_purchase_invoice(cfdi)

		# Restaurar para cleanup correcto
		frappe.db.set_value("Purchase Invoice", pi_name, "fm_cfdi_recibido", cfdi)
		frappe.db.commit()

	# ------------------------------------------------------------------ #
	# Bloqueante B1 — retenciones y grand_total                            #
	# ------------------------------------------------------------------ #

	def test_b1_retencion_add_deduct_tax_deduct(self):
		"""Retención ISR → fila con add_deduct_tax='Deduct' y tax_amount positivo."""
		impuestos = {
			"traslados": [
				{
					"impuesto": "002",
					"tipo_factor": "Tasa",
					"tasa_cuota": "0.160000",
					"importe": 16.0,
				}
			],
			"retenciones": [{"impuesto": "001", "importe": 10.0}],
		}
		# total = 100 + 16 - 10 = 106
		cfdi = self._make_cfdi("B11", total=106.0, impuestos_json=impuestos)
		result = build_purchase_invoice(cfdi)
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])

		ret_rows = [t for t in pi.taxes if t.account_head == self.acc_ret_isr]
		self.assertEqual(len(ret_rows), 1)
		self.assertEqual(ret_rows[0].add_deduct_tax, "Deduct")
		self.assertGreater(flt(ret_rows[0].tax_amount), 0)

		# grand_total debe ser 106 ± tolerancia
		diff = abs(flt(pi.grand_total) - 106.0)
		self.assertLessEqual(diff, 0.02, f"grand_total={pi.grand_total}, esperado≈106")

	# ------------------------------------------------------------------ #
	# Bloqueante B1b — múltiples conceptos procesados correctamente        #
	# (item_wise_tax_detail fue removido en ERPNext v16; se verifica        #
	#  que todos los items tienen expense_account y el grand_total es OK)  #
	# ------------------------------------------------------------------ #

	def test_b1b_multiples_conceptos_procesados(self):
		"""Múltiples conceptos: todos los items tienen expense_account y grand_total correcto."""
		conceptos = [
			{
				"sat_product_key": TEST_SAT_KEY,
				"description": "Servicio A",
				"quantity": 1,
				"unit_key": "E48",
				"unit": "Servicio",
				"unit_price": 60.0,
				"amount": 60.0,
				"discount": 0,
				"tax_object": "02",
				"taxes_json": "{}",
			},
			{
				"sat_product_key": TEST_SAT_KEY,
				"description": "Servicio B",
				"quantity": 1,
				"unit_key": "E48",
				"unit": "Servicio",
				"unit_price": 40.0,
				"amount": 40.0,
				"discount": 0,
				"tax_object": "02",
				"taxes_json": "{}",
			},
		]
		impuestos = {
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
		cfdi = self._make_cfdi("B12", total=116.0, impuestos_json=impuestos, conceptos=conceptos)
		result = build_purchase_invoice(cfdi)
		pi = frappe.get_doc("Purchase Invoice", result["purchase_invoice"])

		# Dos conceptos → dos items en la PI
		self.assertEqual(len(pi.items), 2)

		# Cada item tiene expense_account asignada por el mapping
		for item in pi.items:
			self.assertIsNotNone(
				item.expense_account,
				f"expense_account es None en item '{item.description}'",
			)

		# grand_total correcto con 2 items (60+40=100 base, IVA 16 → 116)
		diff = abs(flt(pi.grand_total) - 116.0)
		self.assertLessEqual(diff, 0.02, f"grand_total={pi.grand_total}, esperado≈116")

	# ------------------------------------------------------------------ #
	# Bloqueante B2 — recuperación tras fallo simulado en cfdi_doc.save()  #
	# ------------------------------------------------------------------ #

	def test_b2_recovery_after_failed_cfdi_save(self):
		"""PI insertado OK pero cfdi_doc.save() falló → segundo intento recupera idempotente."""
		cfdi = self._make_cfdi("B21")
		result1 = build_purchase_invoice(cfdi)
		pi_name = result1["purchase_invoice"]
		self.assertFalse(result1["recovered"])

		# Simular fallo de cfdi_doc.save(): el CFDI no quedó vinculado
		frappe.db.set_value("CFDI Recibido", cfdi, {"purchase_invoice": None, "status": "Listo"})
		frappe.db.commit()

		# Reintento debe reconocer el PI existente (Caso A) y reparar vínculo
		result2 = build_purchase_invoice(cfdi)
		self.assertEqual(result2["status"], "ok")
		self.assertEqual(result2["purchase_invoice"], pi_name)
		self.assertTrue(result2["recovered"])

		# El CFDI debe quedar correctamente vinculado
		cfdi_doc = frappe.get_doc("CFDI Recibido", cfdi)
		self.assertEqual(cfdi_doc.purchase_invoice, pi_name)
		self.assertEqual(cfdi_doc.status, "Convertido a PI")
