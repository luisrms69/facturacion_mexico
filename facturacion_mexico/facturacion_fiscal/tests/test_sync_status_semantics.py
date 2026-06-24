"""Semántica y escritura coherente de fm_sync_status (Corrección 7A1).

fm_sync_status indica si el FFM local refleja de forma verificable la última respuesta
conocida del PAC. NO se confunde con el estado fiscal: una cancelación aceptada pero
fiscalmente PENDIENTE_CANCELACION es 'synced' (la respuesta ya se reflejó localmente).

- synced: hubo respuesta concluyente del PAC (éxito, rechazo conocido o estado de cancelación).
- pending: respuesta realmente inconclusa (timeout / sin información).
- error: la persistencia/verificación no se pudo confirmar (unresolved de 6B2).
- el fallback no-PAC (fiscal_event_*) NO altera fm_sync_status.

Todo con mocks de boundary. Cero llamadas reales al PAC. Solo test-facturacion.localhost.
"""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.config.fiscal_states_config import FiscalStates, SyncStates
from facturacion_mexico.facturacion_fiscal.api import PACResponseWriter
from facturacion_mexico.facturacion_fiscal.cancellation_state import apply_cancellation_state
from facturacion_mexico.facturacion_fiscal.timbrado_api import TimbradoAPI, revisar_estatus_cancelacion

_TIMBRADO_API = "facturacion_mexico.facturacion_fiscal.timbrado_api"


def _seed_si(*, fiscal_status: str = "", ffm: str | None = None) -> str:
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


def _seed_ffm(
	sales_invoice, status: str, *, facturapi_id: str = "", uuid: str = "", sync: str = "pending"
) -> str:
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


def _set_value_factory(*, ffm_raises=False):
	orig = frappe.set_value

	def _fake(dt, dn, *args, **kwargs):
		if dt == "Sales Invoice":
			return None
		if dt == "Factura Fiscal Mexico":
			if ffm_raises:
				raise RuntimeError("frappe down (FASE 3)")
			return frappe.db.set_value(dt, dn, *args, **kwargs)
		return orig(dt, dn, *args, **kwargs)

	return _fake


class TestSyncStatusSemantics(IntegrationTestCase):
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

	def _sync(self, ffm):
		return frappe.db.get_value("Factura Fiscal Mexico", ffm, "fm_sync_status")

	def _write(self, si, ffm, response_data, op):
		self.writer.write_pac_response(si, {"req": 1}, response_data, op, factura_fiscal_name=ffm)

	# 1 — FFM recién creado conserva pending (default, sin pasar por el writer)
	def test_01_recien_creado_pending(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR", sync="pending")
		self.assertEqual(self._sync(ffm), "pending")

	# 2 — timbrado exitoso → synced
	def test_02_timbrado_exitoso_synced(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		self._write(
			si,
			ffm,
			{"success": True, "status_code": 200, "raw_response": {"uuid": "U", "id": "FA"}},
			"timbrado",
		)
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "TIMBRADO")
		self.assertEqual(self._sync(ffm), "synced")

	# 3 — timbrado rechazado y registrado como ERROR → synced (rechazo conocido reflejado)
	def test_03_timbrado_rechazado_synced(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		self._write(
			si,
			ffm,
			{"success": False, "status_code": 400, "error": "rechazo PAC", "raw_response": {}},
			"timbrado",
		)
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "ERROR")
		self.assertEqual(self._sync(ffm), "synced")

	# 4 — cancelación inmediata (raw sin 'success', con id) → synced
	# Nuevo contrato (CORR-1): en cancelación el writer crea el Response Log pero NO persiste
	# status/fm_sync_status; eso lo hace apply_cancellation_state. Se verifican ambos por separado.
	def test_04_cancelacion_inmediata_synced(self):
		si = self._si()
		ffm = self._ffm(si, "CANCELADO", facturapi_id="FA-1", sync="pending")
		self._write(si, ffm, {"status": "canceled", "id": "FA-1"}, "cancelacion")
		self.assertEqual(self._sync(ffm), "pending")  # (1) writer no toca sync
		apply_cancellation_state(ffm, FiscalStates.CANCELADO, sync_status=SyncStates.SYNCED)
		self.assertEqual(self._sync(ffm), "synced")  # (2) apply sí

	# 5 — cancelación pendiente de aceptación
	def test_05_cancelacion_pendiente_synced(self):
		si = self._si()
		ffm = self._ffm(si, "PENDIENTE_CANCELACION", facturapi_id="FA-1", sync="pending")
		self._write(si, ffm, {"cancellation_status": "pending", "id": "FA-1"}, "cancelacion")
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "PENDIENTE_CANCELACION")
		self.assertEqual(self._sync(ffm), "pending")  # (1) writer no toca status/sync
		apply_cancellation_state(ffm, FiscalStates.PENDIENTE_CANCELACION, sync_status=SyncStates.SYNCED)
		self.assertEqual(self._sync(ffm), "synced")  # (2) apply sí

	# 6 — cancelación rechazada y registrada
	def test_06_cancelacion_rechazada_synced(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", facturapi_id="FA-1", sync="pending")
		self._write(si, ffm, {"cancellation_status": "rejected", "id": "FA-1"}, "cancelacion")
		self.assertEqual(self._sync(ffm), "pending")  # (1) writer no toca sync
		apply_cancellation_state(ffm, FiscalStates.TIMBRADO, sync_status=SyncStates.SYNCED)
		self.assertEqual(self._sync(ffm), "synced")  # (2) apply sí

	# 7 — consulta con respuesta concluyente → synced
	def test_07_consulta_concluyente_synced(self):
		si = self._si()
		ffm = self._ffm(si, "PENDIENTE_CANCELACION")
		self._write(
			si, ffm, {"success": True, "status_code": 200, "raw_response": {"status": "pending"}}, "consulta"
		)
		self.assertEqual(self._sync(ffm), "synced")

	# 11 — fallo exclusivo de auditoría no cambia sync (estado fiscal correcto)
	def test_11_audit_fail_no_cambia_sync(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		with patch.object(PACResponseWriter, "_write_to_database", side_effect=RuntimeError("log caído")):
			result = self.writer.write_pac_response(
				si,
				{"req": 1},
				{"success": True, "status_code": 200, "raw_response": {"uuid": "U", "id": "FA"}},
				"timbrado",
				factura_fiscal_name=ffm,
			)
		self.assertTrue(result.get("audit_log_failed"))
		self.assertEqual(self._sync(ffm), "synced")

	# 12 — respuesta realmente inconclusa → pending (no se marca falsamente synced)
	def test_12_inconcluso_pending(self):
		si = self._si()
		ffm = self._ffm(si, "PENDIENTE_CANCELACION", sync="pending")
		# Consulta sin información concluyente (timeout). El status no cambia (consulta→None).
		self._write(si, ffm, {"timeout_flag": 1, "status_code": 0}, "consulta")
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "PENDIENTE_CANCELACION")
		self.assertEqual(self._sync(ffm), "pending")

	# 13 — fallback no-PAC (fiscal_event_*) NO altera fm_sync_status
	def test_13_fallback_no_pac_no_altera_sync(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="synced")
		self._write(
			si,
			ffm,
			{"sales_invoice": si, "company": "_Test Company", "status": "TIMBRADO"},
			"fiscal_event_create",
		)
		self.assertEqual(self._sync(ffm), "synced")  # sin cambio

	# --- M1 (CodeRabbit): fm_last_pac_sync solo se refresca con respuesta PAC real ---

	# M1.1 — un evento interno (fiscal_event_*) NO refresca fm_last_pac_sync
	def test_16_fiscal_event_no_actualiza_last_pac_sync(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="synced")  # fm_last_pac_sync nace None
		antes = frappe.db.get_value("Factura Fiscal Mexico", ffm, "fm_last_pac_sync")
		self._write(
			si,
			ffm,
			{"sales_invoice": si, "company": "_Test Company", "status": "TIMBRADO"},
			"fiscal_event_create",
		)
		despues = frappe.db.get_value("Factura Fiscal Mexico", ffm, "fm_last_pac_sync")
		self.assertEqual(antes, despues)  # no se tocó

	# M1.2 — una respuesta PAC real SÍ refresca fm_last_pac_sync
	def test_17_respuesta_pac_real_actualiza_last_pac_sync(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		self.assertIsNone(frappe.db.get_value("Factura Fiscal Mexico", ffm, "fm_last_pac_sync"))
		self._write(
			si,
			ffm,
			{"success": True, "status_code": 200, "raw_response": {"uuid": "U", "id": "FA"}},
			"timbrado",
		)
		self.assertIsNotNone(frappe.db.get_value("Factura Fiscal Mexico", ffm, "fm_last_pac_sync"))

	# ── 6B2: recuperación y no resuelto actualizan sync ──────────────────────

	def _run_timbrado(self, si, ffm, *, writer_return, fase3="real"):
		ffm_doc = frappe.get_doc("Factura Fiscal Mexico", ffm)
		client = MagicMock()
		client.create_invoice.return_value = {"uuid": "U-1", "id": "FA-1", "total": 116}
		with patch(f"{_TIMBRADO_API}.get_facturapi_client", return_value=client):
			api = TimbradoAPI(company="_Test Company")
			stack = [
				patch.object(TimbradoAPI, "_validate_invoice_for_timbrado"),
				patch.object(TimbradoAPI, "_prepare_facturapi_data", return_value={}),
				patch.object(TimbradoAPI, "_get_factura_fiscal", return_value=ffm_doc),
				patch("frappe.set_value", side_effect=_set_value_factory(ffm_raises=(fase3 == "fail"))),
				patch(f"{_TIMBRADO_API}.write_pac_response", return_value=writer_return),
			]
			if fase3 == "real":
				stack += [
					patch.object(TimbradoAPI, "_validate_amount_discrepancies"),
					patch.object(TimbradoAPI, "_download_fiscal_files"),
					patch.object(TimbradoAPI, "_send_fiscal_email"),
				]
			with ExitStack() as es:
				for p in stack:
					es.enter_context(p)
				result = api.timbrar_factura(si)
		return result

	# 8 — writer falla y FASE 3 recupera → synced
	def test_08_recuperado_synced(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR", sync="pending")
		self._run_timbrado(si, ffm, writer_return={"success": False}, fase3="real")
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "TIMBRADO")
		self.assertEqual(self._sync(ffm), "synced")

	# 10 — writer y FASE 3 no resuelven → error
	def test_10_no_resuelto_error(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR", sync="pending")
		result = self._run_timbrado(si, ffm, writer_return={"success": False}, fase3="fail")
		self.assertEqual(result.get("persistence_status"), "unresolved")
		self.assertEqual(self._sync(ffm), "error")

	# 9 — consulta con writer fallido pero estado verificado → synced
	def test_09_consulta_recuperada_synced(self):
		# Consolidación: revisar delega en reconcile_ffm (camino único) y NO hace 2ª consulta al PAC.
		ffm = self._ffm(self._si(), "PENDIENTE_CANCELACION", facturapi_id="FA-1", uuid="U-1", sync="pending")
		with (
			patch(
				"facturacion_mexico.facturacion_fiscal.services.ffm_reconciliation.reconcile_ffm",
				return_value={"ffm": ffm, "outcome": "changed"},
			) as rec,
			patch("facturacion_mexico.facturacion_fiscal.api_client.query_pac_status") as qps,
		):
			out = revisar_estatus_cancelacion(ffm)
		rec.assert_called_once_with(ffm)
		qps.assert_not_called()
		self.assertEqual(out, {"ffm": ffm, "outcome": "changed"})

	# 14 — HTTP 5xx / status_code=0 NO se clasifican como concluyentes solo por el código
	def test_14_http_5xx_no_synced(self):
		si = self._si()
		# 5xx sin otra señal concluyente
		ffm_a = self._ffm(si, "PENDIENTE_CANCELACION", sync="pending")
		self._write(si, ffm_a, {"status_code": 503}, "consulta")
		self.assertEqual(self._sync(ffm_a), "pending")
		# success=False con 5xx (timeout/transporte) tampoco es synced
		ffm_b = self._ffm(si, "PENDIENTE_CANCELACION", sync="pending")
		self._write(si, ffm_b, {"success": False, "status_code": 500}, "consulta")
		self.assertEqual(self._sync(ffm_b), "pending")

	# 15 — cero referencias al cliente del PAC en este módulo
	def test_15_cero_trafico_pac(self):
		g = globals()
		for simbolo in ("FacturapiClient", "create_invoice", "requests", "get_facturapi_client"):
			self.assertNotIn(simbolo, g, f"La prueba no debe importar {simbolo}")
