"""
Tests del workflow de re-facturación: refacturar_misma_si()

Cubre el flujo:
  SI PPD submitted + timbrada → FFM cancelada (motivo 02/03/04)
  → refacturar_misma_si() → SI desvinculada → lista para re-timbrar

Ejecutar:
  bench --site test-facturacion.localhost execute facturacion_mexico.tests.ci_pre_tests.run
  bench --site test-facturacion.localhost run-tests --app facturacion_mexico \
    --module facturacion_mexico.tests.test_refacturar_workflow --lightmode
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.api.fiscal_operations import refacturar_misma_si
from facturacion_mexico.tests.fm_si_builder import TEST_COMPANY, make_submitted_si

TEST_SAT_CODE = "84111506"  # Servicios de consultoría — genérico para testing
TEST_ITEM_CODE = "FM-TEST-REFACTURA-ITEM"


class TestRefacturarWorkflow(FrappeTestCase):
	"""Tests unitarios para refacturar_misma_si()."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		# --- Company ---
		# `_Test Company` es la company canónica de ERPNext con plan de cuentas completo:
		# necesaria para que la SI real haga insert()+submit() sin fallar por income_account/
		# debit_to sin resolver. El default global del site puede ser una company mínima sin
		# plan de cuentas (p. ej. "Test PCV Company"), que no permite emitir una SI real.
		if frappe.db.exists("Company", TEST_COMPANY):
			cls.company = TEST_COMPANY
		else:
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

		# --- UOM ---
		if not frappe.db.exists("UOM", "Nos"):
			frappe.get_doc({"doctype": "UOM", "uom_name": "Nos"}).insert(ignore_permissions=True)

		# --- SAT Producto Servicio ---
		if not frappe.db.exists("SAT Producto Servicio", TEST_SAT_CODE):
			sat = frappe.new_doc("SAT Producto Servicio")
			sat.codigo = TEST_SAT_CODE
			sat.descripcion = "Servicios de consultoria - Test"
			sat.insert(ignore_permissions=True)

		# --- Item Group (cualquiera que exista) ---
		item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"

		# --- Item de prueba ---
		if not frappe.db.exists("Item", TEST_ITEM_CODE):
			item = frappe.new_doc("Item")
			item.item_code = TEST_ITEM_CODE
			item.item_name = "Item de prueba re-facturación"
			item.item_group = item_group
			item.stock_uom = "Nos"
			item.is_stock_item = 0
			item.fm_producto_servicio_sat = TEST_SAT_CODE
			item.insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Item", TEST_ITEM_CODE, "fm_producto_servicio_sat", TEST_SAT_CODE)

		# --- Customer Group + Territory (prerequisitos de Customer) ---
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

		# --- Cost Center (hoja) para la company ---
		cls.cost_center = frappe.db.get_value("Cost Center", {"is_group": 0, "company": cls.company}, "name")
		if not cls.cost_center:
			parent_cc = frappe.db.get_value("Cost Center", {"company": cls.company}, "name")
			if parent_cc:
				cc = frappe.new_doc("Cost Center")
				cc.cost_center_name = "FM Test"
				cc.company = cls.company
				cc.parent_cost_center = parent_cc
				cc.insert(ignore_permissions=True)
				cls.cost_center = cc.name

		# --- Fiscal Year — requerido por ERPNext para GL entries en si.submit() ---
		# bench new-site en CI no crea Fiscal Year automáticamente.
		from frappe.utils import getdate

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

		frappe.db.commit()

	def _make_si(self, docstatus=1):
		"""Crea una SI fiscalmente válida (cost_center + SAT code) para testing.

		Cablea income_account/debit_to/cost_center a cuentas reales de la company vía el
		builder de tests compartido, de modo que insert()+submit() no fallen.
		"""
		return make_submitted_si(
			company=self.company,
			customer=self.customer,
			item_code=TEST_ITEM_CODE,
			cost_center=self.cost_center,
			rate=1000,
			do_submit=(docstatus == 1),
		)

	def _make_ffm(self, si_name, status="TIMBRADO", motivo=None):
		"""Crea una FFM mínima vinculada a la SI."""
		ffm = frappe.new_doc("Factura Fiscal Mexico")
		ffm.sales_invoice = si_name
		ffm.company = self.company
		ffm.customer = self.customer
		ffm.fm_cfdi_use = "G03"  # Gastos en general — disponible en fixtures SAT
		ffm.insert(ignore_permissions=True)
		ffm.submit()

		# Setear status y motivo DESPUÉS de submit — on_submit puede resetear el status
		_motivo_labels = {
			"01": "01 - Comprobantes emitidos con errores con relación",
			"02": "02 - Comprobantes emitidos con errores sin relación",
			"03": "03 - No se llevó a cabo la operación",
			"04": "04 - Operación nominativa relacionada en la factura global",
		}
		update = {"status": status, "fm_sync_status": "idle"}
		if motivo:
			update["fm_motivo_cancelacion"] = motivo
			update["cancellation_reason"] = _motivo_labels.get(motivo, motivo)
		frappe.db.set_value("Factura Fiscal Mexico", ffm.name, update)

		# Vincular desde SI
		frappe.db.set_value("Sales Invoice", si_name, "fm_factura_fiscal_mx", ffm.name)
		frappe.db.set_value("Sales Invoice", si_name, "fm_fiscal_status", status)
		frappe.db.commit()
		return frappe.get_doc("Factura Fiscal Mexico", ffm.name)

	# ── Test 1: Happy path motivo 02 ────────────────────────────────────────
	def test_refacturar_motivo_02(self):
		"""SI submitted + FFM CANCELADA motivo 02 → desvincula correctamente."""
		si = self._make_si()
		self._make_ffm(si.name, status="CANCELADO", motivo="02")

		refacturar_misma_si(si.name)

		si.reload()
		self.assertEqual(si.fm_factura_fiscal_mx, "", "FFM debe desvincularse")
		self.assertIn(si.fm_fiscal_status, ("", None, "BORRADOR"), "Estado fiscal debe limpiarse")
		self.assertEqual(si.docstatus, 1, "SI debe seguir submitted")

	# ── Test 2: Happy path motivo 03 ────────────────────────────────────────
	def test_refacturar_motivo_03(self):
		"""Motivo 03 también permite re-facturar."""
		si = self._make_si()
		self._make_ffm(si.name, status="CANCELADO", motivo="03")
		refacturar_misma_si(si.name)
		si.reload()
		self.assertEqual(si.fm_factura_fiscal_mx, "")

	# ── Test 3: Happy path motivo 04 ────────────────────────────────────────
	def test_refacturar_motivo_04(self):
		"""Motivo 04 (operación nominativa) también permite re-facturar."""
		si = self._make_si()
		self._make_ffm(si.name, status="CANCELADO", motivo="04")
		refacturar_misma_si(si.name)
		si.reload()
		self.assertEqual(si.fm_factura_fiscal_mx, "")

	# ── Test 4: Bloqueo — FFM no cancelada (TIMBRADO) ───────────────────────
	def test_bloqueo_ffm_timbrada(self):
		"""FFM en TIMBRADO → throw, no se puede re-facturar."""
		si = self._make_si()
		self._make_ffm(si.name, status="TIMBRADO")
		with self.assertRaises(frappe.ValidationError):
			refacturar_misma_si(si.name)

	# ── Test 5: Bloqueo — SI no submitted ───────────────────────────────────
	def test_bloqueo_si_draft(self):
		"""SI en borrador → throw."""
		si = self._make_si(docstatus=0)
		with self.assertRaises(frappe.ValidationError):
			refacturar_misma_si(si.name)

	# ── Test 6: Bloqueo — motivo 01 (sustitución) ───────────────────────────
	def test_bloqueo_motivo_01(self):
		"""Motivo 01 no permite refacturar_misma_si (requiere CFDI sustituto)."""
		si = self._make_si()
		self._make_ffm(si.name, status="CANCELADO", motivo="01")
		with self.assertRaises(frappe.ValidationError):
			refacturar_misma_si(si.name)

	# ── Test 7: Sin FFM vinculada ────────────────────────────────────────────
	def test_sin_ffm_vinculada(self):
		"""SI sin FFM → no falla, simplemente no hay nada que desvincular."""
		si = self._make_si()
		try:
			refacturar_misma_si(si.name)
		except Exception as e:
			self.fail(f"No debería fallar sin FFM vinculada: {e}")

	# ── Test 8: Idempotencia ─────────────────────────────────────────────────
	def test_idempotencia(self):
		"""Llamar dos veces no falla — segunda llamada ve SI ya desvinculada."""
		si = self._make_si()
		self._make_ffm(si.name, status="CANCELADO", motivo="02")
		refacturar_misma_si(si.name)
		try:
			refacturar_misma_si(si.name)
		except Exception as e:
			self.fail(f"Segunda llamada no debe fallar: {e}")
