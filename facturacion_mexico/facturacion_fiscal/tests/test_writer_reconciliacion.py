"""Soporte del writer para operation_type='reconciliacion' (Paso 2 del motor).

Ante una respuesta PAC exitosa, el writer delega EXCLUSIVAMENTE en derive_pac_reconciliation
(no duplica la matriz) y aplica (estado_fiscal, fm_sync_status). Estado fiscal solo si no es None.
Errores HTTP/timeout y contradicciones de identidad conservan su semántica (no se reinterpretan).

Todo con respuestas SIMULADAS contra el writer (PACResponseWriter). Cero PAC real.
"""

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.facturacion_fiscal.api import FiscalCorrelationError, PACResponseWriter


def _seed_si(*, fiscal_status="", ffm=None):
	si = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": "_Test Company",
			"customer": "_Test Customer",
			"net_total": 100,
			"grand_total": 116,
			"posting_date": frappe.utils.today(),
			"docstatus": 1,
			"fm_fiscal_status": fiscal_status or None,
			"fm_factura_fiscal_mx": ffm,
		}
	)
	si.flags.ignore_validate = True
	si.flags.ignore_mandatory = True
	si.flags.ignore_links = True
	si.db_insert()
	frappe.db.commit()
	return si.name


def _seed_ffm(sales_invoice, status, *, facturapi_id="FA-1", uuid="U-1", sync="pending"):
	ffm = frappe.get_doc(
		{
			"doctype": "Factura Fiscal Mexico",
			"naming_series": "FFM-TEST-.YYYY.-",
			"sales_invoice": sales_invoice,
			"status": status,
			"fm_tipo_comprobante": "I",
			"company": "_Test Company",
			"customer": "_Test Customer",
			"facturapi_id": facturapi_id or None,
			"fm_uuid": uuid or None,
			"fm_sync_status": sync,
			"docstatus": 1,
		}
	)
	ffm.flags.ignore_validate = True
	ffm.flags.ignore_mandatory = True
	ffm.flags.ignore_links = True
	ffm.db_insert()
	frappe.db.commit()
	return ffm.name


class TestWriterReconciliacion(IntegrationTestCase):
	def setUp(self):
		self.si_names = []
		self.ffm_names = []
		self.writer = PACResponseWriter()
		self.addCleanup(frappe.set_user, "Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		for ffm in self.ffm_names:
			frappe.db.delete("FacturAPI Response Log", {"factura_fiscal_mexico": ffm})
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

	def _reconciliar(self, si, ffm, raw, *, status_code=200, success=True):
		"""Ejecuta el writer con operation_type='reconciliacion'. raw = cuerpo del invoice del PAC."""
		# get_invoice siempre trae id/uuid para que la correlación estricta pase (salvo en los
		# tests de contradicción, que los sobreescriben).
		raw_full = {"id": "FA-1", "uuid": "U-1", **raw}
		self.writer.write_pac_response(
			si,
			{"action": "reconciliacion", "facturapi_id": "FA-1"},
			{"success": success, "status_code": status_code, "raw_response": raw_full},
			"reconciliacion",
			factura_fiscal_name=ffm,
		)

	def _status(self, ffm):
		return frappe.db.get_value("Factura Fiscal Mexico", ffm, "status")

	def _sync(self, ffm):
		return frappe.db.get_value("Factura Fiscal Mexico", ffm, "fm_sync_status")

	# --- estados que delegan en el helper (respuesta exitosa) ---

	def test_valid_none_timbrado_synced(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO")
		self._reconciliar(si, ffm, {"status": "valid"})
		self.assertEqual(self._status(ffm), "TIMBRADO")
		self.assertEqual(self._sync(ffm), "synced")

	def test_valid_pending_pendiente_synced(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO")
		self._reconciliar(si, ffm, {"status": "valid", "cancellation_status": "pending"})
		self.assertEqual(self._status(ffm), "PENDIENTE_CANCELACION")
		self.assertEqual(self._sync(ffm), "synced")

	def test_valid_verifying_pendiente_synced(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO")
		self._reconciliar(si, ffm, {"status": "valid", "cancellation_status": "verifying"})
		self.assertEqual(self._status(ffm), "PENDIENTE_CANCELACION")
		self.assertEqual(self._sync(ffm), "synced")

	def test_canceled_cancelado_synced(self):
		si = self._si()
		ffm = self._ffm(si, "PENDIENTE_CANCELACION")
		self._reconciliar(si, ffm, {"status": "canceled"})
		self.assertEqual(self._status(ffm), "CANCELADO")
		self.assertEqual(self._sync(ffm), "synced")

	def test_accepted_sin_status_cancelado_synced(self):
		si = self._si()
		ffm = self._ffm(si, "PENDIENTE_CANCELACION")
		self._reconciliar(si, ffm, {"cancellation_status": "accepted"})
		self.assertEqual(self._status(ffm), "CANCELADO")
		self.assertEqual(self._sync(ffm), "synced")

	def test_valid_rejected_timbrado_synced(self):
		si = self._si()
		ffm = self._ffm(si, "PENDIENTE_CANCELACION")
		self._reconciliar(si, ffm, {"status": "valid", "cancellation_status": "rejected"})
		self.assertEqual(self._status(ffm), "TIMBRADO")
		self.assertEqual(self._sync(ffm), "synced")

	def test_valid_expired_timbrado_synced(self):
		si = self._si()
		ffm = self._ffm(si, "PENDIENTE_CANCELACION")
		self._reconciliar(si, ffm, {"status": "valid", "cancellation_status": "expired"})
		self.assertEqual(self._status(ffm), "TIMBRADO")
		self.assertEqual(self._sync(ffm), "synced")

	# --- sin transición fiscal (helper devuelve None) ---

	def test_remoto_pending_conserva_estado_y_pending(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO")
		self._reconciliar(si, ffm, {"status": "pending"})
		self.assertEqual(self._status(ffm), "TIMBRADO")  # sin cambio fiscal
		self.assertEqual(self._sync(ffm), "pending")

	def test_estado_desconocido_conserva_estado_y_error(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO")
		self._reconciliar(si, ffm, {"status": "draft"})
		self.assertEqual(self._status(ffm), "TIMBRADO")  # sin cambio fiscal
		self.assertEqual(self._sync(ffm), "error")

	# --- contradicción de identidad: conserva la semántica de FiscalCorrelationError ---

	def test_contradiccion_facturapi_id_propaga(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", facturapi_id="FA-1", uuid="U-1")
		with self.assertRaises(FiscalCorrelationError):
			self.writer.write_pac_response(
				si,
				{"action": "reconciliacion"},
				{"success": True, "status_code": 200, "raw_response": {"id": "FA-OTRO", "status": "valid"}},
				"reconciliacion",
				factura_fiscal_name=ffm,
			)

	def test_contradiccion_uuid_propaga(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", facturapi_id="FA-1", uuid="U-1")
		with self.assertRaises(FiscalCorrelationError):
			self.writer.write_pac_response(
				si,
				{"action": "reconciliacion"},
				{
					"success": True,
					"status_code": 200,
					"raw_response": {"id": "FA-1", "uuid": "U-OTRO", "status": "valid"},
				},
				"reconciliacion",
				factura_fiscal_name=ffm,
			)

	# cero referencias al cliente PAC en el módulo
	def test_cero_trafico_pac(self):
		g = globals()
		for simbolo in ("FacturapiClient", "create_invoice", "cancel_invoice", "requests", "get_invoice"):
			self.assertNotIn(simbolo, g, f"La prueba no debe importar {simbolo}")
