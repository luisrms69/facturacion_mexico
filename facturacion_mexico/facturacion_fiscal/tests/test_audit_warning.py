"""Manejo NO bloqueante de auditoría incompleta tras respuesta PAC (Corrección 6B1).

Cuando `write_pac_response` reporta `audit_log_failed` o `audit_log_ref_failed`, la operación
fiscal YA se procesó: el flujo continúa (FASE 3), conserva `success=True`, no re-llama al PAC,
no crea Recovery Task ni reintenta, y agrega una advertencia visible no bloqueante. Una
`FiscalCorrelationError` sigue deteniendo el flujo (6A); un error real del PAC o un fallo de
la FASE 3 conservan su comportamiento existente.

Todo con mocks de boundary. Cero llamadas reales al PAC.
"""

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


def _set_value_si_noop_factory():
	"""Neutraliza efectos colaterales de entorno de test en las escrituras de FASE 3.

	- Sales Invoice: no-op (la SI mínima no pasa validación mandatory).
	- Factura Fiscal Mexico: escribe con frappe.db.set_value (sin disparar on_update →
	  create_fiscal_event → Response Log colateral, ajeno a 6B1). El estado fiscal sí se
	  persiste para poder verificarlo.
	"""
	orig = frappe.set_value

	def _fake(dt, dn, *args, **kwargs):
		if dt == "Sales Invoice":
			return None
		if dt == "Factura Fiscal Mexico":
			return frappe.db.set_value(dt, dn, *args, **kwargs)
		return orig(dt, dn, *args, **kwargs)

	return _fake


class TestAuditWarning(IntegrationTestCase):
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

	def _run_timbrado(self, si, ffm, *, writer_return=None, writer_side_effect=None, create_side_effect=None):
		"""Ejecuta timbrar_factura con FASE 1 neutralizada y boundaries mockeados."""
		ffm_doc = frappe.get_doc("Factura Fiscal Mexico", ffm)
		client = MagicMock()
		if create_side_effect is not None:
			client.create_invoice.side_effect = create_side_effect
		else:
			client.create_invoice.return_value = {"uuid": "U-1", "id": "FA-1", "total": 116}

		wpr = patch(f"{_TIMBRADO_API}.write_pac_response")
		with patch(f"{_TIMBRADO_API}.get_facturapi_client", return_value=client):
			api = TimbradoAPI(company="_Test Company")
			with (
				patch.object(TimbradoAPI, "_validate_invoice_for_timbrado"),
				patch.object(TimbradoAPI, "_prepare_facturapi_data", return_value={}),
				patch.object(TimbradoAPI, "_get_factura_fiscal", return_value=ffm_doc),
				patch.object(TimbradoAPI, "_validate_amount_discrepancies"),
				patch.object(TimbradoAPI, "_download_fiscal_files"),
				patch.object(TimbradoAPI, "_send_fiscal_email"),
				patch("frappe.set_value", side_effect=_set_value_si_noop_factory()),
				wpr as mock_wpr,
			):
				if writer_side_effect is not None:
					mock_wpr.side_effect = writer_side_effect
				else:
					mock_wpr.return_value = writer_return
				result = api.timbrar_factura(si)
		return result, client

	# 1 — timbrado exitoso + audit_log_failed: no bloqueante, FFM TIMBRADO, advertencia
	def test_01_timbrado_audit_log_failed_no_bloquea(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		result, client = self._run_timbrado(
			si, ffm, writer_return={"success": True, "fiscal_updated": True, "audit_log_failed": True}
		)
		self.assertTrue(result["success"])
		self.assertTrue(result.get("audit_warning"))
		self.assertEqual(result.get("audit_status"), "incomplete")
		self.assertEqual(result.get("audit_detail"), "audit_log_failed")
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "TIMBRADO")
		client.create_invoice.assert_called_once()

	# 2 — timbrado exitoso + audit_log_ref_failed: mismo no-bloqueo, diferencia técnica
	def test_02_timbrado_audit_log_ref_failed(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		result, _ = self._run_timbrado(
			si, ffm, writer_return={"success": True, "fiscal_updated": True, "audit_log_ref_failed": True}
		)
		self.assertTrue(result["success"])
		self.assertTrue(result.get("audit_warning"))
		self.assertEqual(result.get("audit_detail"), "audit_log_ref_failed")

	# 5 — writer sin problemas de auditoría: sin advertencia, comportamiento previo
	def test_05_sin_problema_auditoria_no_advertencia(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		result, _ = self._run_timbrado(
			si, ffm, writer_return={"success": True, "fiscal_updated": True, "response_log_name": "LOG-1"}
		)
		self.assertTrue(result["success"])
		self.assertNotIn("audit_warning", result)

	# 6 — error real del PAC: comportamiento existente (el except externo devuelve dict de
	#     error), sin advertencia de auditoría ni mensaje de éxito.
	def test_06_error_real_pac_conserva_comportamiento(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		result, client = self._run_timbrado(
			si, ffm, writer_return={"success": True}, create_side_effect=RuntimeError("PAC 500")
		)
		self.assertNotIn("audit_warning", result)
		self.assertNotEqual(result.get("message"), "Factura timbrada exitosamente")
		client.create_invoice.assert_called_once()

	# 7 — FiscalCorrelationError sigue deteniendo el flujo (6A), no se degrada a advertencia
	def test_07_correlacion_sigue_deteniendo(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		with self.assertRaises(FiscalCorrelationError):
			self._run_timbrado(si, ffm, writer_side_effect=FiscalCorrelationError("x"))

	# 8 — fallo de la FASE 3: 6B1 no lo oculta ni lo transforma en éxito con advertencia
	def test_08_fallo_fase3_no_se_oculta(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		with patch.object(TimbradoAPI, "_process_timbrado_success", side_effect=RuntimeError("frappe down")):
			# El except frappe_error maneja: success=False, sin audit_warning.
			ffm_doc = frappe.get_doc("Factura Fiscal Mexico", ffm)
			client = MagicMock()
			client.create_invoice.return_value = {"uuid": "U-1", "id": "FA-1"}
			with patch(f"{_TIMBRADO_API}.get_facturapi_client", return_value=client):
				api = TimbradoAPI(company="_Test Company")
				with (
					patch.object(TimbradoAPI, "_validate_invoice_for_timbrado"),
					patch.object(TimbradoAPI, "_prepare_facturapi_data", return_value={}),
					patch.object(TimbradoAPI, "_get_factura_fiscal", return_value=ffm_doc),
					patch("frappe.set_value", side_effect=_set_value_si_noop_factory()),
					patch(f"{_TIMBRADO_API}.write_pac_response", return_value={"success": True}),
				):
					result = api.timbrar_factura(si)
		self.assertFalse(result["success"])
		self.assertNotIn("audit_warning", result)

	# 3 — cancelación exitosa + auditoría incompleta: no bloqueante, sin Recovery, sin 2ª cancelación
	def test_03_cancelacion_audit_incompleta(self):
		ffm = self._ffm(None, "TIMBRADO", facturapi_id="FA-1", uuid="U-1")
		si = self._si(fiscal_status="TIMBRADO", ffm=ffm)
		frappe.db.set_value("Factura Fiscal Mexico", ffm, "sales_invoice", si)
		frappe.db.commit()

		recovery_dt = frappe.db.exists("DocType", "Fiscal Recovery Task")
		recovery_before = (
			frappe.db.count("Fiscal Recovery Task", {"reference_name": ffm}) if recovery_dt else 0
		)

		client = MagicMock()
		client.cancel_invoice.return_value = {"success": True, "raw_response": {"status": "canceled"}}

		with patch(f"{_TIMBRADO_API}.get_facturapi_client", return_value=client):
			api = TimbradoAPI(company="_Test Company")
			with (
				patch("frappe.set_value", side_effect=_set_value_si_noop_factory()),
				patch(
					f"{_TIMBRADO_API}.write_pac_response",
					return_value={"success": True, "fiscal_updated": True, "audit_log_failed": True},
				),
			):
				result = api.cancelar_factura(si, "02")

		self.assertTrue(result["success"])
		self.assertTrue(result.get("audit_warning"))
		client.cancel_invoice.assert_called_once()  # sin segunda cancelación
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "CANCELADO")
		if recovery_dt:
			self.assertEqual(
				frappe.db.count("Fiscal Recovery Task", {"reference_name": ffm}), recovery_before
			)

	# 4 — consulta exitosa + auditoría incompleta: estado conservado, advertencia, sin repetir PAC
	def test_04_revisar_delega_en_motor(self):
		# Consolidación: revisar_estatus_cancelacion ya no tiene lógica/consulta propia; delega en el
		# motor (reconcile_ffm) y NO realiza una segunda llamada al PAC (query_pac_status). El manejo
		# de auditoría incompleta queda en el camino único del motor/writer (probado en sus suites).
		si = self._si()
		ffm = self._ffm(si, "PENDIENTE_CANCELACION", facturapi_id="FA-1", uuid="U-1")
		with (
			patch(
				"facturacion_mexico.facturacion_fiscal.services.ffm_reconciliation.reconcile_ffm",
				return_value={"ffm": ffm, "outcome": "changed"},
			) as rec,
			patch("facturacion_mexico.facturacion_fiscal.api_client.query_pac_status") as qps,
		):
			result = revisar_estatus_cancelacion(ffm)
		rec.assert_called_once_with(ffm)
		qps.assert_not_called()
		self.assertEqual(result, {"ffm": ffm, "outcome": "changed"})

	# 10 — cero referencias al cliente del PAC en este módulo
	def test_10_cero_trafico_pac(self):
		g = globals()
		for simbolo in ("FacturapiClient", "create_invoice", "requests", "get_facturapi_client"):
			self.assertNotIn(simbolo, g, f"La prueba no debe importar {simbolo}")
