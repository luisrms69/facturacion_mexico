"""Guard de refacturación 02/03/04 tras eliminar el bloqueo por fm_sync_status (Corrección 7A2).

refacturar_misma_si DESVINCULA el FFM CANCELADO de la Sales Invoice (no timbra ni crea FFM).
Tras 7A2, fm_sync_status='pending' ya NO bloquea: los controles vigentes son docstatus==1,
FFM en CANCELADO y motivo 02/03/04, más la idempotencia cuando la SI ya está desvinculada.

Sin stock, sin PAC. Solo test-facturacion.localhost.
"""

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.api.fiscal_operations import refacturar_misma_si


def _seed_si(*, docstatus: int = 1, ffm: str | None = None) -> str:
	si = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": "_Test Company",
			"customer": "_Test Customer",
			"net_total": 100,
			"grand_total": 116,
			"posting_date": frappe.utils.today(),
			"docstatus": docstatus,
			"fm_factura_fiscal_mx": ffm,
		}
	)
	si.flags.ignore_validate = True
	si.flags.ignore_mandatory = True
	si.flags.ignore_links = True
	si.db_insert()
	frappe.db.commit()
	return si.name


def _seed_ffm(sales_invoice, status: str, *, sync: str = "pending", motivo: str = "") -> str:
	ffm = frappe.get_doc(
		{
			"doctype": "Factura Fiscal Mexico",
			"naming_series": "FFM-TEST-.YYYY.-",
			"sales_invoice": sales_invoice,
			"status": status,
			"fm_tipo_comprobante": "I",
			"company": "_Test Company",
			"customer": "_Test Customer",
			"fm_sync_status": sync,
			"fm_motivo_cancelacion": motivo or None,
			"docstatus": 1,
		}
	)
	ffm.flags.ignore_validate = True
	ffm.flags.ignore_mandatory = True
	ffm.flags.ignore_links = True
	ffm.db_insert()
	frappe.db.commit()
	return ffm.name


class TestRefacturarGuard(IntegrationTestCase):
	def setUp(self):
		self.si_names = []
		self.ffm_names = []
		self.addCleanup(frappe.set_user, "Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		for ffm in self.ffm_names:
			frappe.db.delete("Factura Fiscal Mexico", {"name": ffm})
		for si in self.si_names:
			frappe.db.delete("Sales Invoice", {"name": si})
		frappe.db.commit()

	def _si(self, **kwargs):
		name = _seed_si(**kwargs)
		self.si_names.append(name)
		return name

	def _ffm(self, *args, **kwargs):
		name = _seed_ffm(*args, **kwargs)
		self.ffm_names.append(name)
		return name

	# 1 — CANCELADO + pending + motivo 02 → permite desvincular (ya no bloquea por pending)
	def test_01_cancelado_pending_motivo02_permite(self):
		si = self._si()
		ffm = self._ffm(si, "CANCELADO", sync="pending", motivo="02")
		frappe.db.set_value("Sales Invoice", si, "fm_factura_fiscal_mx", ffm)
		frappe.db.commit()
		result = refacturar_misma_si(si)
		self.assertTrue(result.get("ok"))
		self.assertFalse(frappe.db.get_value("Sales Invoice", si, "fm_factura_fiscal_mx"))

	# 2 — CANCELADO + synced + motivo 03 → sigue permitiendo
	def test_02_cancelado_synced_motivo03_permite(self):
		si = self._si()
		ffm = self._ffm(si, "CANCELADO", sync="synced", motivo="03")
		frappe.db.set_value("Sales Invoice", si, "fm_factura_fiscal_mx", ffm)
		frappe.db.commit()
		result = refacturar_misma_si(si)
		self.assertTrue(result.get("ok"))

	# 3 — TIMBRADO + pending → sigue bloqueado por estado (no por pending)
	def test_03_timbrado_pending_bloqueado_por_estado(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="pending", motivo="02")
		frappe.db.set_value("Sales Invoice", si, "fm_factura_fiscal_mx", ffm)
		frappe.db.commit()
		with self.assertRaises(frappe.ValidationError) as ctx:
			refacturar_misma_si(si)
		self.assertIn("CANCELADA", str(ctx.exception))

	# 4 — PENDIENTE_CANCELACION + synced → bloqueado por estado
	def test_04_pendiente_cancelacion_bloqueado(self):
		si = self._si()
		ffm = self._ffm(si, "PENDIENTE_CANCELACION", sync="synced", motivo="02")
		frappe.db.set_value("Sales Invoice", si, "fm_factura_fiscal_mx", ffm)
		frappe.db.commit()
		with self.assertRaises(frappe.ValidationError):
			refacturar_misma_si(si)

	# 5 — motivo 01 → bloqueado por motivo
	def test_05_motivo_01_bloqueado(self):
		si = self._si()
		ffm = self._ffm(si, "CANCELADO", sync="synced", motivo="01")
		frappe.db.set_value("Sales Invoice", si, "fm_factura_fiscal_mx", ffm)
		frappe.db.commit()
		with self.assertRaises(frappe.ValidationError) as ctx:
			refacturar_misma_si(si)
		self.assertIn("02/03/04", str(ctx.exception))

	# 6 — Sales Invoice no enviada (docstatus=0) → bloqueada por precondición
	def test_06_si_no_enviada_bloqueada(self):
		si = self._si(docstatus=0)
		with self.assertRaises(frappe.ValidationError) as ctx:
			refacturar_misma_si(si)
		self.assertIn("enviada", str(ctx.exception))

	# 7 — SI ya desvinculada → respuesta idempotente
	def test_07_ya_desvinculada_idempotente(self):
		si = self._si()  # sin fm_factura_fiscal_mx
		result = refacturar_misma_si(si)
		self.assertTrue(result.get("ok"))
		self.assertTrue(result.get("already_unlinked"))

	# 10 — cero referencias al cliente del PAC en este módulo
	def test_10_cero_trafico_pac(self):
		g = globals()
		for simbolo in ("FacturapiClient", "create_invoice", "cancel_invoice", "requests"):
			self.assertNotIn(simbolo, g, f"La prueba no debe importar {simbolo}")
