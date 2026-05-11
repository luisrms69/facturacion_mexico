"""
Tests para check_ppd_requirement() en payment_entry_validate.py

Casos cubiertos (unitarios):
  1. PE Receive con SI PPD timbrada → fm_require_complement = 1
  2. PE Receive con SI PUE timbrada → fm_require_complement = 0
  3. PE Receive con SI PPD no timbrada → fm_require_complement = 0
  4. PE no Receive (Payment) → fm_require_complement = 0
  5. PE cancelado (docstatus=2) → fm_require_complement = 0

Casos cubiertos (integración):
  6. Hook corre al guardar PE real con SI PPD timbrada → fm_require_complement = 1
  7. Hook corre al guardar PE real con SI PUE → fm_require_complement = 0
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.complementos_pago.hooks_handlers.payment_entry_validate import (
	check_ppd_requirement,
)


def _make_pe(payment_type="Receive", docstatus=1, references=None):
	"""Crea un doc mock de Payment Entry con los campos mínimos."""
	doc = frappe._dict(
		payment_type=payment_type,
		docstatus=docstatus,
		fm_require_complement=0,
		references=references or [],
	)
	doc.get = lambda key, default=None: (
		doc.get(key, default) if isinstance(doc, dict) else getattr(doc, key, default)
	)
	return doc


def _si_ref(si_name, allocated=1000):
	return frappe._dict(
		reference_doctype="Sales Invoice",
		reference_name=si_name,
		allocated_amount=allocated,
	)


class TestCheckPPDRequirement(FrappeTestCase):
	# ── Caso 1 ────────────────────────────────────────────────────────────
	def test_receive_ppd_timbrada_requiere_complemento(self):
		"""Receive + SI PPD timbrada → fm_require_complement = 1."""
		doc = _make_pe(references=[_si_ref("SINV-PPD-001")])
		with patch("frappe.get_all", return_value=[{"name": "SINV-PPD-001"}]):
			check_ppd_requirement(doc)
		self.assertEqual(doc.fm_require_complement, 1)

	# ── Caso 2 ────────────────────────────────────────────────────────────
	def test_receive_pue_no_requiere_complemento(self):
		"""Receive + SI PUE → fm_require_complement = 0 (frappe.get_all retorna vacío)."""
		doc = _make_pe(references=[_si_ref("SINV-PUE-001")])
		with patch("frappe.get_all", return_value=[]):
			check_ppd_requirement(doc)
		self.assertEqual(doc.fm_require_complement, 0)

	# ── Caso 3 ────────────────────────────────────────────────────────────
	def test_receive_ppd_no_timbrada_no_requiere(self):
		"""Receive + SI PPD pero NO timbrada → fm_require_complement = 0."""
		doc = _make_pe(references=[_si_ref("SINV-PPD-DRAFT")])
		with patch("frappe.get_all", return_value=[]):
			check_ppd_requirement(doc)
		self.assertEqual(doc.fm_require_complement, 0)

	# ── Caso 4 ────────────────────────────────────────────────────────────
	def test_payment_no_receive(self):
		"""Payment type != Receive → fm_require_complement = 0 sin consultar BD."""
		doc = _make_pe(payment_type="Pay", references=[_si_ref("SINV-001")])
		with patch("frappe.get_all") as mock_get_all:
			check_ppd_requirement(doc)
			mock_get_all.assert_not_called()
		self.assertEqual(doc.fm_require_complement, 0)

	# ── Caso 5 ────────────────────────────────────────────────────────────
	def test_pe_cancelado(self):
		"""PE cancelado (docstatus=2) → fm_require_complement = 0."""
		doc = _make_pe(docstatus=2, references=[_si_ref("SINV-PPD-001")])
		with patch("frappe.get_all") as mock_get_all:
			check_ppd_requirement(doc)
			mock_get_all.assert_not_called()
		self.assertEqual(doc.fm_require_complement, 0)

	# ── Caso extra: sin referencias ───────────────────────────────────────
	def test_sin_referencias(self):
		"""Sin referencias → fm_require_complement = 0."""
		doc = _make_pe(references=[])
		with patch("frappe.get_all") as mock_get_all:
			check_ppd_requirement(doc)
			mock_get_all.assert_not_called()
		self.assertEqual(doc.fm_require_complement, 0)

	# ── Caso extra: allocated_amount = 0 ─────────────────────────────────
	def test_allocated_amount_cero_ignorado(self):
		"""Referencia con allocated_amount=0 se ignora."""
		doc = _make_pe(references=[_si_ref("SINV-PPD-001", allocated=0)])
		with patch("frappe.get_all") as mock_get_all:
			check_ppd_requirement(doc)
			mock_get_all.assert_not_called()
		self.assertEqual(doc.fm_require_complement, 0)


class TestCheckPPDRequirementIntegracion(FrappeTestCase):
	"""Tests de integración: confirma que el hook corre al guardar PE real en BD."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from frappe.utils import getdate

		cls._suffix = frappe.generate_hash(length=6)

		# --- Company (patrón documentado en test-guard) ---
		default_co = frappe.defaults.get_global_default("company")
		if default_co and frappe.db.exists("Company", default_co):
			cls.company = default_co
		else:
			cls.company = frappe.db.get_value("Company", {}, "name")
			if not cls.company:
				company = frappe.new_doc("Company")
				company.company_name = "_Test Company"
				company.abbr = "_TC"
				company.default_currency = "MXN"
				company.country = "Mexico"
				company.insert(ignore_permissions=True)
				cls.company = company.name
				frappe.db.set_default("company", cls.company)

		cls.currency = frappe.db.get_value("Company", cls.company, "default_currency") or "MXN"

		# --- UOM ---
		if not frappe.db.exists("UOM", "Nos"):
			frappe.get_doc({"doctype": "UOM", "uom_name": "Nos"}).insert(ignore_permissions=True)

		# --- Customer Group + Territory ---
		if not frappe.db.exists("Customer Group", "All Customer Groups"):
			frappe.get_doc(
				{"doctype": "Customer Group", "customer_group_name": "All Customer Groups", "is_group": 1}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Customer Group", "Individual"):
			frappe.get_doc(
				{
					"doctype": "Customer Group",
					"customer_group_name": "Individual",
					"is_group": 0,
					"parent_customer_group": "All Customer Groups",
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Territory", "All Territories"):
			frappe.get_doc(
				{"doctype": "Territory", "territory_name": "All Territories", "is_group": 1}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Territory", "Rest Of The World"):
			frappe.get_doc(
				{
					"doctype": "Territory",
					"territory_name": "Rest Of The World",
					"is_group": 0,
					"parent_territory": "All Territories",
				}
			).insert(ignore_permissions=True)

		# --- Customer ---
		cls.customer = "_Test Customer"
		if not frappe.db.exists("Customer", cls.customer):
			customer = frappe.new_doc("Customer")
			customer.customer_name = "_Test Customer"
			customer.customer_type = "Individual"
			customer.customer_group = "Individual"
			customer.territory = "Rest Of The World"
			customer.insert(ignore_permissions=True)

		# --- SAT Producto Servicio (requerido por hook validate de SI) ---
		sat_code = "84111506"
		if not frappe.db.exists("SAT Producto Servicio", sat_code):
			sat = frappe.new_doc("SAT Producto Servicio")
			sat.codigo = sat_code
			sat.descripcion = "Servicios de consultoria - Test"
			sat.insert(ignore_permissions=True)

		# --- Item ---
		item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
		cls.item_code = f"FM-TEST-PPD-{cls._suffix}"
		if not frappe.db.exists("Item", cls.item_code):
			item = frappe.new_doc("Item")
			item.item_code = cls.item_code
			item.item_name = "Item test PPD"
			item.item_group = item_group
			item.stock_uom = "Nos"
			item.is_stock_item = 0
			item.fm_producto_servicio_sat = sat_code
			item.insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Item", cls.item_code, "fm_producto_servicio_sat", sat_code)

		# --- Cost Center ---
		cls.cost_center = frappe.db.get_value("Cost Center", {"is_group": 0, "company": cls.company}, "name")
		if not cls.cost_center:
			parent_cc = frappe.db.get_value("Cost Center", {"company": cls.company}, "name")
			if parent_cc:
				cc = frappe.new_doc("Cost Center")
				cc.cost_center_name = f"FM Test PPD {cls._suffix}"
				cc.company = cls.company
				cc.parent_cost_center = parent_cc
				cc.insert(ignore_permissions=True)
				cls.cost_center = cc.name

		# --- Fiscal Year ---
		today = getdate()
		fy_name = str(today.year)
		if not frappe.db.exists("Fiscal Year", fy_name):
			fy = frappe.new_doc("Fiscal Year")
			fy.year = fy_name
			fy.year_start_date = f"{today.year}-01-01"
			fy.year_end_date = f"{today.year}-12-31"
			fy.append("companies", {"company": cls.company})
			fy.insert(ignore_permissions=True)
		else:
			fy = frappe.get_doc("Fiscal Year", fy_name)
			if cls.company not in [c.company for c in fy.companies]:
				fy.append("companies", {"company": cls.company})
				fy.save(ignore_permissions=True)

		# --- Cuentas para PE ---
		cls.receivable_account = frappe.db.get_value(
			"Account", {"account_type": "Receivable", "company": cls.company, "is_group": 0}, "name"
		)
		cls.bank_account = frappe.db.get_value(
			"Account",
			{"account_type": ["in", ["Bank", "Cash"]], "company": cls.company, "is_group": 0},
			"name",
		)

		frappe.db.commit()

	def _make_real_si(self, is_ppd=True, fiscal_status="TIMBRADO"):
		"""Crea SI real submitted con campos fiscales seteados vía db_set."""
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = self.customer
		si.cost_center = self.cost_center
		si.currency = self.currency
		si.conversion_rate = 1.0
		si.append("items", {"item_code": self.item_code, "qty": 1, "rate": 500})
		si.insert(ignore_permissions=True)
		si.submit()
		frappe.db.set_value(
			"Sales Invoice",
			si.name,
			{"fm_es_ppd": 1 if is_ppd else 0, "fm_fiscal_status": fiscal_status},
		)
		frappe.db.commit()
		return si.name

	def _make_real_pe(self, si_name, allocated=500):
		"""Crea PE real tipo Receive con referencia a la SI."""
		if not self.receivable_account or not self.bank_account:
			self.skipTest("No hay cuentas contables disponibles para PE en este site")

		pe = frappe.new_doc("Payment Entry")
		pe.payment_type = "Receive"
		pe.company = self.company
		pe.party_type = "Customer"
		pe.party = self.customer
		pe.paid_from = self.receivable_account
		pe.paid_to = self.bank_account
		pe.paid_amount = allocated
		pe.received_amount = allocated
		pe.target_exchange_rate = 1.0
		pe.source_exchange_rate = 1.0
		pe.append(
			"references",
			{"reference_doctype": "Sales Invoice", "reference_name": si_name, "allocated_amount": allocated},
		)
		pe.insert(ignore_permissions=True)
		return pe

	# ── Caso 6: integración PPD timbrada ─────────────────────────────────
	def test_integracion_ppd_timbrada_activa_campo(self):
		"""Hook corre al guardar PE real: SI PPD timbrada → fm_require_complement = 1."""
		si_name = self._make_real_si(is_ppd=True, fiscal_status="TIMBRADO")
		pe = self._make_real_pe(si_name)
		# El hook ya corrió en insert() → verificar el campo en el doc en memoria
		self.assertEqual(pe.fm_require_complement, 1)

	# ── Caso 7: integración PUE no activa campo ───────────────────────────
	def test_integracion_pue_no_activa_campo(self):
		"""Hook corre al guardar PE real: SI PUE → fm_require_complement = 0."""
		si_name = self._make_real_si(is_ppd=False, fiscal_status="TIMBRADO")
		pe = self._make_real_pe(si_name)
		self.assertEqual(pe.fm_require_complement, 0)
