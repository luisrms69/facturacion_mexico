"""Propagación real de FiscalCorrelationError tras respuesta del PAC (Corrección 6A).

Una contradicción de correlación (FFM de otra SI, UUID o facturapi_id contradictorios)
NO debe degradarse a un resultado ordinario `{success:False}` ni ser absorbida por un
`except Exception`. Debe propagarse para detener el flujo: sin ejecutar la FASE 3, sin
re-llamar al PAC, sin reintentos/recovery automáticos, con un mensaje seguro al usuario.

Todo se prueba con respuestas SIMULADAS y mocks de boundary (cliente PAC y el escritor
de persistencia). Cero tráfico real contra FacturAPI.
"""

import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.facturacion_fiscal.api import (
	FiscalCorrelationError,
)
from facturacion_mexico.facturacion_fiscal.api import (
	write_pac_response as public_write_pac_response,
)
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


def _seed_ffm(sales_invoice: str, status: str, *, uuid: str = "", facturapi_id: str = "") -> str:
	ffm = frappe.get_doc(
		{
			"doctype": "Factura Fiscal Mexico",
			"naming_series": "FFM-TEST-.YYYY.-",
			"sales_invoice": sales_invoice,
			"status": status,
			"fm_tipo_comprobante": "I",
			"company": "_Test Company",
			"customer": "_Test Customer",
			"fm_uuid": uuid or None,
			"facturapi_id": facturapi_id or None,
			"docstatus": 1,
		}
	)
	ffm.flags.ignore_validate = True
	ffm.flags.ignore_mandatory = True
	ffm.flags.ignore_links = True
	ffm.db_insert()
	frappe.db.commit()
	return ffm.name


class TestCorrelacionPropagacion(IntegrationTestCase):
	def setUp(self):
		self.si_names = []
		self.ffm_names = []
		self.addCleanup(frappe.set_user, "Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		has_recovery = frappe.db.exists("DocType", "Fiscal Recovery Task")
		for si in self.si_names:
			frappe.db.delete("Sales Invoice", {"name": si})
		for ffm in self.ffm_names:
			if has_recovery:
				frappe.db.delete("Fiscal Recovery Task", {"reference_name": ffm})
			frappe.db.delete("Factura Fiscal Mexico", {"name": ffm})
		frappe.db.commit()

	def _si(self, **kwargs):
		name = _seed_si(**kwargs)
		self.si_names.append(name)
		return name

	def _ffm(self, *args, **kwargs):
		name = _seed_ffm(*args, **kwargs)
		self.ffm_names.append(name)
		return name

	# ── 1-3: el wrapper público propaga FiscalCorrelationError ───────────────

	def test_01_wrapper_ffm_de_otra_si_propaga(self):
		si_a = self._si()
		si_b = self._si()
		ffm_b = self._ffm(si_b, "TIMBRADO")  # pertenece a si_b
		with self.assertRaises(FiscalCorrelationError):
			public_write_pac_response(
				si_a,  # otra SI
				json.dumps({}),
				json.dumps({"success": True, "uuid": "U-OK"}),
				"timbrado",
				factura_fiscal_name=ffm_b,
			)

	def test_02_wrapper_uuid_contradictorio_propaga(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", uuid="UUID-AAA")
		with self.assertRaises(FiscalCorrelationError):
			public_write_pac_response(
				si,
				json.dumps({}),
				json.dumps({"success": True, "uuid": "UUID-BBB"}),
				"timbrado",
				factura_fiscal_name=ffm,
			)

	def test_03_wrapper_facturapi_id_contradictorio_propaga(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", facturapi_id="FA-AAA")
		with self.assertRaises(FiscalCorrelationError):
			public_write_pac_response(
				si,
				json.dumps({}),
				json.dumps({"success": True, "id": "FA-BBB"}),
				"timbrado",
				factura_fiscal_name=ffm,
			)

	# ── 7: errores ORDINARIOS (no correlación) conservan el comportamiento ───

	def test_07_error_ordinario_no_se_propaga_como_correlacion(self):
		from facturacion_mexico.facturacion_fiscal.api import PACResponseWriter

		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		# Un fallo genérico (no de correlación) sigue devolviéndose como {success:False}.
		with patch.object(PACResponseWriter, "_update_factura_fiscal", side_effect=RuntimeError("boom")):
			result = public_write_pac_response(
				si,
				json.dumps({}),
				json.dumps({"success": True, "uuid": "U-OK"}),
				"timbrado",
				factura_fiscal_name=ffm,
			)
		self.assertFalse(result["success"])
		self.assertIn("boom", result.get("error", ""))

	# ── 4: timbrado — la correlación crítica impide la FASE 3 ────────────────

	def test_04_timbrado_correlacion_detiene_y_no_ejecuta_fase3(self):
		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		ffm_doc = frappe.get_doc("Factura Fiscal Mexico", ffm)

		client = MagicMock()
		client.create_invoice.return_value = {"uuid": "U", "id": "FA"}

		with patch(f"{_TIMBRADO_API}.get_facturapi_client", return_value=client):
			api = TimbradoAPI(company="_Test Company")
			with (
				patch.object(TimbradoAPI, "_validate_invoice_for_timbrado"),
				patch.object(TimbradoAPI, "_prepare_facturapi_data", return_value={}),
				patch.object(TimbradoAPI, "_get_factura_fiscal", return_value=ffm_doc),
				patch.object(TimbradoAPI, "_process_timbrado_success") as spy_fase3,
				patch(f"{_TIMBRADO_API}.write_pac_response", side_effect=FiscalCorrelationError("x")),
			):
				with self.assertRaises(FiscalCorrelationError):
					api.timbrar_factura(si)

			# FASE 3 NO se ejecutó y el PAC se llamó UNA sola vez (sin reintento).
			spy_fase3.assert_not_called()
			client.create_invoice.assert_called_once()

	# ── 5: cancelación — la correlación crítica impide FASE 3 y Recovery ─────

	def test_05_cancelacion_correlacion_detiene_sin_recovery(self):
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
			with patch(f"{_TIMBRADO_API}.write_pac_response", side_effect=FiscalCorrelationError("x")):
				with self.assertRaises(FiscalCorrelationError):
					api.cancelar_factura(si, "02")

			client.cancel_invoice.assert_called_once()

		# La FASE 3 (donde se crearía el Recovery y se marcaría CANCELADO) NO se ejecutó:
		# el FFM sigue TIMBRADO y no se creó Recovery Task que repita la operación.
		self.assertEqual(frappe.db.get_value("Factura Fiscal Mexico", ffm, "status"), "TIMBRADO")
		if recovery_dt:
			self.assertEqual(
				frappe.db.count("Fiscal Recovery Task", {"reference_name": ffm}), recovery_before
			)

	# ── 6: consulta — reporta la inconsistencia y no toca OTRO FFM ───────────

	def test_06_consulta_correlacion_reporta_y_no_toca_otro_ffm(self):
		si = self._si()
		target = self._ffm(si, "PENDIENTE_CANCELACION", facturapi_id="FA-T", uuid="U-T")
		control = self._ffm(si, "TIMBRADO", facturapi_id="FA-C", uuid="U-C")
		control_status_before = frappe.db.get_value("Factura Fiscal Mexico", control, "status")

		with (
			patch(
				"facturacion_mexico.facturacion_fiscal.api_client.query_pac_status",
				return_value={"success": True, "data": {"cancellation_status": "accepted"}},
			),
			patch(f"{_TIMBRADO_API}.write_pac_response", side_effect=FiscalCorrelationError("x")),
		):
			with self.assertRaises(FiscalCorrelationError):
				revisar_estatus_cancelacion(target)

		# El OTRO FFM (control) no fue tocado.
		self.assertEqual(
			frappe.db.get_value("Factura Fiscal Mexico", control, "status"), control_status_before
		)

	# ── M2 (CodeRabbit): write_pac_timeout también propaga la correlación ────

	def test_09_timeout_correlacion_propaga(self):
		from facturacion_mexico.facturacion_fiscal.api import PACResponseWriter, write_pac_timeout

		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		# Una contradicción de correlación dentro del writer NO debe absorberse a {success:False}.
		with patch.object(PACResponseWriter, "write_pac_response", side_effect=FiscalCorrelationError("x")):
			with self.assertRaises(FiscalCorrelationError):
				write_pac_timeout(si, json.dumps({}), 30, factura_fiscal_name=ffm)

	def test_10_timeout_error_ordinario_no_propaga(self):
		from facturacion_mexico.facturacion_fiscal.api import PACResponseWriter, write_pac_timeout

		si = self._si()
		ffm = self._ffm(si, "BORRADOR")
		# Un error genérico sí conserva el comportamiento ordinario {success:False}.
		with patch.object(PACResponseWriter, "write_pac_response", side_effect=RuntimeError("boom")):
			result = write_pac_timeout(si, json.dumps({}), 30, factura_fiscal_name=ffm)
		self.assertFalse(result["success"])

	# ── 8: cero tráfico real al PAC ──────────────────────────────────────────

	def test_08_cero_trafico_pac(self):
		g = globals()
		for simbolo in ("FacturapiClient", "requests", "get_facturapi_client"):
			self.assertNotIn(simbolo, g, f"La prueba no debe importar {simbolo}")
