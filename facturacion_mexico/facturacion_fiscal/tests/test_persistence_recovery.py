"""Fallo de la persistencia principal tras PAC exitoso (Corrección 6B2).

Cuando `write_pac_response` devuelve `success=False` (el PASO 1 del writer no persistió el
estado fiscal) pero el PAC SÍ respondió bien, el flujo no trata esto como operación fallida:
ejecuta la FASE 3 una sola vez, verifica con lectura NUEVA de BD el estado persistido y
distingue entre recuperación local (success=True + advertencia crítica) y persistencia aún
no resuelta (success=False + intervención manual, retry_allowed=False). Nunca re-llama al PAC.

Distinto de: auditoría incompleta (6B1), FiscalCorrelationError (6A) y error real del PAC.

Todo con mocks de boundary. Cero llamadas reales al PAC.
"""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.facturacion_fiscal.api import FiscalCorrelationError
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


def _seed_ffm(sales_invoice, status: str, *, facturapi_id: str = "", uuid: str = "") -> str:
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
	"""SI: no-op (mínima). FFM: db.set_value (sin hooks) o lanza si ffm_raises."""
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


class TestPersistenceRecovery(IntegrationTestCase):
	def setUp(self):
		self.si_names = []
		self.ffm_names = []
		self.addCleanup(frappe.set_user, "Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		has_recovery = frappe.db.exists("DocType", "Fiscal Recovery Task")
		for ffm in self.ffm_names:
			if has_recovery:
				frappe.db.delete("Fiscal Recovery Task", {"reference_name": ffm})
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

	def _run_timbrado(self, si, ffm, *, writer_return=None, writer_side_effect=None, fase3="real"):
		ffm_doc = frappe.get_doc("Factura Fiscal Mexico", ffm)
		client = MagicMock()
		client.create_invoice.return_value = {"uuid": "U-1", "id": "FA-1", "total": 116}

		with patch(f"{_TIMBRADO_API}.get_facturapi_client", return_value=client):
			api = TimbradoAPI(company="_Test Company")
			stack = [
				patch.object(TimbradoAPI, "_validate_invoice_for_timbrado"),
				patch.object(TimbradoAPI, "_prepare_facturapi_data", return_value={}),
				patch.object(TimbradoAPI, "_get_factura_fiscal", return_value=ffm_doc),
				patch("frappe.set_value", side_effect=_set_value_factory()),
			]
			wpr = patch(f"{_TIMBRADO_API}.write_pac_response")
			if fase3 == "real":
				stack += [
					patch.object(TimbradoAPI, "_validate_amount_discrepancies"),
					patch.object(TimbradoAPI, "_download_fiscal_files"),
					patch.object(TimbradoAPI, "_send_fiscal_email"),
				]
			elif fase3 == "fail":
				stack.append(
					patch.object(TimbradoAPI, "_process_timbrado_success", side_effect=RuntimeError("down"))
				)
			elif fase3 == "wrong_uuid":

				def _wrong(self_, si_, ffm_, resp_):
					frappe.db.set_value(
						"Factura Fiscal Mexico", ffm_.name, {"status": "TIMBRADO", "fm_uuid": "OTRO-UUID"}
					)

				stack.append(
					patch.object(TimbradoAPI, "_process_timbrado_success", autospec=True, side_effect=_wrong)
				)

			with ExitStack() as es:
				for p in stack:
					es.enter_context(p)
				mock_wpr = es.enter_context(wpr)
				if writer_side_effect is not None:
					mock_wpr.side_effect = writer_side_effect
				else:
					mock_wpr.return_value = writer_return
				result = api.timbrar_factura(si)
		return result, client

	# 1 — timbrado: writer falla, FASE 3 recupera, verificación OK
	def test_01_timbrado_recuperado_por_fase3(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		result, client = self._run_timbrado(si, ffm, writer_return={"success": False, "error": "boom"})
		self.assertTrue(result["success"])
		self.assertEqual(result.get("persistence_status"), "recovered_by_phase3")
		self.assertEqual(result.get("persistence_recovery_source"), "phase3")
		self.assertTrue(result.get("persistence_warning"))
		self.assertFalse(result.get("retry_allowed"))
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "TIMBRADO")
		client.create_invoice.assert_called_once()

	# 2 — timbrado: writer falla y FASE 3 también falla → no resuelto
	def test_02_timbrado_no_resuelto(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		result, client = self._run_timbrado(si, ffm, writer_return={"success": False}, fase3="fail")
		self.assertFalse(result["success"])
		self.assertEqual(result.get("persistence_status"), "unresolved")
		self.assertFalse(result.get("retry_allowed"))
		self.assertTrue(result.get("operation_may_be_processed"))
		self.assertIn("No repita la operación", result.get("message", ""))
		client.create_invoice.assert_called_once()

	# 3 — timbrado: FASE 3 "termina" pero el UUID persistido no coincide → no resuelto
	def test_03_timbrado_uuid_no_coincide_no_resuelto(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		result, _ = self._run_timbrado(si, ffm, writer_return={"success": False}, fase3="wrong_uuid")
		self.assertFalse(result.get("success"))  # nunca éxito limpio
		self.assertEqual(result.get("persistence_status"), "unresolved")

	# 10 — writer exitoso: sin metadata de 6B2
	def test_10_writer_exitoso_sin_metadata(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		result, _ = self._run_timbrado(si, ffm, writer_return={"success": True, "fiscal_updated": True})
		self.assertTrue(result["success"])
		self.assertNotIn("persistence_warning", result)
		self.assertNotIn("persistence_status", result)

	# 8 — audit_log_failed sigue siendo 6B1 (no 6B2)
	def test_08_audit_log_failed_es_6b1(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		result, _ = self._run_timbrado(
			si, ffm, writer_return={"success": True, "fiscal_updated": True, "audit_log_failed": True}
		)
		self.assertTrue(result["success"])
		self.assertTrue(result.get("audit_warning"))
		self.assertNotIn("persistence_warning", result)

	# 9 — FiscalCorrelationError sigue deteniendo (6A)
	def test_09_correlacion_detiene(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		with self.assertRaises(FiscalCorrelationError):
			self._run_timbrado(si, ffm, writer_side_effect=FiscalCorrelationError("x"))

	# 7 — error real del PAC: comportamiento existente, sin advertencia de recuperación
	def test_07_error_real_pac(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		ffm_doc = frappe.get_doc("Factura Fiscal Mexico", ffm)
		client = MagicMock()
		client.create_invoice.side_effect = RuntimeError("PAC 500")
		with patch(f"{_TIMBRADO_API}.get_facturapi_client", return_value=client):
			api = TimbradoAPI(company="_Test Company")
			with (
				patch.object(TimbradoAPI, "_validate_invoice_for_timbrado"),
				patch.object(TimbradoAPI, "_prepare_facturapi_data", return_value={}),
				patch.object(TimbradoAPI, "_get_factura_fiscal", return_value=ffm_doc),
				patch("frappe.set_value", side_effect=_set_value_factory()),
				patch(f"{_TIMBRADO_API}.write_pac_response", return_value={"success": False}),
			):
				result = api.timbrar_factura(si)
		self.assertNotIn("persistence_warning", result)

	# 4 — cancelación: writer falla, FASE 3 recupera a CANCELADO
	def test_04_cancelacion_recuperada(self):
		ffm = self._ffm(None, "TIMBRADO", facturapi_id="FA-1", uuid="U-1")
		si = self._si(fiscal_status="TIMBRADO", ffm=ffm)
		frappe.db.set_value("Factura Fiscal Mexico", ffm, "sales_invoice", si)
		frappe.db.commit()
		client = MagicMock()
		client.cancel_invoice.return_value = {"success": True, "raw_response": {"status": "canceled"}}
		with patch(f"{_TIMBRADO_API}.get_facturapi_client", return_value=client):
			api = TimbradoAPI(company="_Test Company")
			with (
				patch("frappe.set_value", side_effect=_set_value_factory()),
				patch(f"{_TIMBRADO_API}.write_pac_response", return_value={"success": False}),
			):
				result = api.cancelar_factura(si, "02")
		self.assertTrue(result["success"])
		self.assertEqual(result.get("persistence_status"), "recovered_by_phase3")
		self.assertEqual(result.get("persistence_recovery_source"), "phase3")
		client.cancel_invoice.assert_called_once()
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "CANCELADO")

	# 5 — cancelación: writer y FASE 3 fallan → no resuelto, sin Recovery Task, sin 2ª cancelación
	def test_05_cancelacion_no_resuelta_sin_recovery(self):
		ffm = self._ffm(None, "TIMBRADO", facturapi_id="FA-1", uuid="U-1")
		si = self._si(fiscal_status="TIMBRADO", ffm=ffm)
		frappe.db.set_value("Factura Fiscal Mexico", ffm, "sales_invoice", si)
		frappe.db.commit()
		recovery_dt = frappe.db.exists("DocType", "Fiscal Recovery Task")
		client = MagicMock()
		client.cancel_invoice.return_value = {"success": True, "raw_response": {"status": "canceled"}}
		with patch(f"{_TIMBRADO_API}.get_facturapi_client", return_value=client):
			api = TimbradoAPI(company="_Test Company")
			with (
				patch("frappe.set_value", side_effect=_set_value_factory(ffm_raises=True)),
				patch(f"{_TIMBRADO_API}.write_pac_response", return_value={"success": False}),
			):
				result = api.cancelar_factura(si, "02")
		self.assertFalse(result["success"])
		self.assertEqual(result.get("persistence_status"), "unresolved")
		client.cancel_invoice.assert_called_once()  # sin segunda cancelación
		if recovery_dt:
			self.assertEqual(frappe.db.count("Fiscal Recovery Task", {"reference_name": ffm}), 0)

	# 6 — consulta: writer falla, el estado ya persistido queda verificado
	def test_06_consulta_recuperada(self):
		si = self._si()
		ffm = self._ffm(si, "PENDIENTE_CANCELACION", facturapi_id="FA-1", uuid="U-1")
		mock_query = patch(
			"facturacion_mexico.facturacion_fiscal.api_client.query_pac_status",
			return_value={"success": True, "data": {"cancellation_status": "accepted"}},
		)
		with (
			mock_query as mq,
			patch("frappe.set_value", side_effect=_set_value_factory()),
			patch(f"{_TIMBRADO_API}.write_pac_response", return_value={"success": False}),
		):
			result = revisar_estatus_cancelacion(ffm)
		self.assertTrue(result.get("success", True))  # éxito con advertencia
		self.assertEqual(result.get("status"), "CANCELADO")  # estado previamente persistido y verificado
		self.assertNotEqual(result.get("persistence_status"), "recovered_by_phase3")
		self.assertEqual(result.get("persistence_status"), "state_verified_after_writer_failure")
		self.assertEqual(result.get("persistence_recovery_source"), "pre_writer_state_update")
		self.assertTrue(result.get("persistence_warning"))
		mq.assert_called_once()  # consulta al PAC una sola vez

	# --- M3 (CodeRabbit): verificación de persistencia usa el estado derivado (`fiscal_status`) ---

	def _run_cancelacion(self, motivo, raw_response, *, ffm_raises=False):
		"""Cancelación con writer fallido: dispara la verificación de persistencia (6B2/M3)."""
		ffm = self._ffm(None, "TIMBRADO", facturapi_id="FA-1", uuid="U-1")
		si = self._si(fiscal_status="TIMBRADO", ffm=ffm)
		frappe.db.set_value("Factura Fiscal Mexico", ffm, "sales_invoice", si)
		frappe.db.commit()
		client = MagicMock()
		client.cancel_invoice.return_value = {"success": True, "raw_response": raw_response}
		with patch(f"{_TIMBRADO_API}.get_facturapi_client", return_value=client):
			api = TimbradoAPI(company="_Test Company")
			with (
				patch("frappe.set_value", side_effect=_set_value_factory(ffm_raises=ffm_raises)),
				patch(f"{_TIMBRADO_API}.write_pac_response", return_value={"success": False}),
			):
				result = api.cancelar_factura(si, motivo)
		return result, ffm, client

	# 14 — cancelación RECHAZADA: FASE 3 mantiene TIMBRADO → se reconoce como persistido (recuperado)
	def test_14_cancelacion_rejected_recuperada_timbrado(self):
		result, ffm, client = self._run_cancelacion("02", {"cancellation_status": "rejected"})
		self.assertTrue(result["success"])
		self.assertEqual(result.get("persistence_status"), "recovered_by_phase3")
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "TIMBRADO")
		client.cancel_invoice.assert_called_once()

	# 15 — cancelación PENDIENTE: conserva el comportamiento existente (PENDIENTE_CANCELACION recuperado)
	def test_15_cancelacion_pending_recuperada(self):
		result, ffm, _ = self._run_cancelacion("02", {"cancellation_status": "pending"})
		self.assertTrue(result["success"])
		self.assertEqual(result.get("persistence_status"), "recovered_by_phase3")
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "PENDIENTE_CANCELACION")

	# 16 — cancelación ACEPTADA pero FASE 3 no persiste (queda en TIMBRADO) → NO recuperada
	def test_16_cancelacion_accepted_pero_timbrado_no_recuperada(self):
		result, ffm, _ = self._run_cancelacion("02", {"status": "canceled"}, ffm_raises=True)
		self.assertFalse(result["success"])
		self.assertEqual(result.get("persistence_status"), "unresolved")
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "TIMBRADO")

	# 13 — cero referencias al cliente del PAC en este módulo
	def test_13_cero_trafico_pac(self):
		g = globals()
		for simbolo in ("FacturapiClient", "create_invoice", "requests", "get_facturapi_client"):
			self.assertNotIn(simbolo, g, f"La prueba no debe importar {simbolo}")
