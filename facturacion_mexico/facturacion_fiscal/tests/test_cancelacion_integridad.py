"""Integridad del flujo de cancelación CFDI (síncrono + asíncrono).

Valida el criterio acotado de cancelación, la operación autoritativa única
`apply_cancellation_state`, la consistencia de FFM/SI en todas las transiciones, la guarda de la
cascada y la protección contra el crash 1406. Todo con respuestas SIMULADAS — cero PAC real.
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.config.fiscal_states_config import FiscalStates, SyncStates
from facturacion_mexico.facturacion_fiscal.api import PACResponseWriter
from facturacion_mexico.facturacion_fiscal.cancellation_state import (
	apply_cancellation_state,
	derive_cancellation_reconciliation,
)

_FA = "FA-" + frappe.generate_hash()[:10]
_UUID = "U-" + frappe.generate_hash()[:10]


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


def _seed_ffm(
	sales_invoice,
	status,
	*,
	motivo=None,
	reason=None,
	date=None,
	facturapi_id=None,
	uuid=None,
	sync="pending",
):
	# IDs fiscales únicos por fixture cuando el caller no los suministra (aislamiento de pruebas,
	# RG-003). Los tests de correlación que necesitan emparejar seed↔respuesta pasan ids explícitos.
	facturapi_id = facturapi_id or "FA-" + frappe.generate_hash()[:10]
	uuid = uuid or "U-" + frappe.generate_hash()[:10]
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
			"fm_motivo_cancelacion": motivo,
			"cancellation_reason": reason,
			"cancellation_date": date,
			"docstatus": 1,
		}
	)
	ffm.flags.ignore_validate = True
	ffm.flags.ignore_mandatory = True
	ffm.flags.ignore_links = True
	ffm.db_insert()
	frappe.db.commit()
	return ffm.name


class TestCancelacionIntegridad(IntegrationTestCase):
	def setUp(self):
		self._si = []
		self._ffm = []
		self.addCleanup(frappe.set_user, "Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		for ffm in self._ffm:
			frappe.db.delete("FacturAPI Response Log", {"factura_fiscal_mexico": ffm})
			frappe.db.delete("Factura Fiscal Mexico", {"name": ffm})
		for si in self._si:
			frappe.db.delete("Sales Invoice", {"name": si})
		frappe.db.commit()

	def si(self, **kw):
		n = _seed_si(**kw)
		self._si.append(n)
		return n

	def ffm(self, *a, **kw):
		n = _seed_ffm(*a, **kw)
		self._ffm.append(n)
		return n

	def _status(self, ffm):
		return frappe.db.get_value("Factura Fiscal Mexico", ffm, "status")

	def _field(self, ffm, f):
		return frappe.db.get_value("Factura Fiscal Mexico", ffm, f)

	def _si_status(self, si):
		return frappe.db.get_value("Sales Invoice", si, "fm_fiscal_status")

	def _derive_writer(self, raw, success=True, code=200):
		resp = {"success": success, "status_code": code, "raw_response": raw}
		return PACResponseWriter()._derive_status_from_response(resp, "Solicitud Cancelación")[0]

	# ---------- Clasificación (criterio acotado + writer) ----------

	def test_01_verifying_pendiente_ffm_y_si(self):
		ffm = self.ffm(None, FiscalStates.TIMBRADO, motivo="02")
		si = self.si(fiscal_status=FiscalStates.TIMBRADO, ffm=ffm)
		frappe.db.set_value("Factura Fiscal Mexico", ffm, "sales_invoice", si)
		st, sync = derive_cancellation_reconciliation("valid", "verifying")
		apply_cancellation_state(ffm, st, sync_status=sync)
		self.assertEqual(self._status(ffm), FiscalStates.PENDIENTE_CANCELACION)
		self.assertEqual(self._si_status(si), FiscalStates.PENDIENTE_CANCELACION)
		self.assertEqual(
			self._derive_writer({"status": "valid", "cancellation_status": "verifying"}),
			FiscalStates.PENDIENTE_CANCELACION,
		)

	def test_03_canceled_es_cancelado(self):
		self.assertEqual(
			self._derive_writer({"status": "canceled", "cancellation_status": "accepted"}),
			FiscalStates.CANCELADO,
		)

	def test_09_desconocido_nunca_cancelado(self):
		for raw in (
			{},
			{"status": "valid"},
			{"status": "weird", "cancellation_status": "??"},
			{"status": "valid", "cancellation_status": None},
		):
			self.assertNotEqual(self._derive_writer(raw), FiscalStates.CANCELADO)
		self.assertIsNone(self._derive_writer({}, success=False, code=500))

	def test_18_accepted_aislado_no_cancela(self):
		# valid + accepted SIN status=canceled NO es terminal.
		st, _ = derive_cancellation_reconciliation("valid", "accepted")
		self.assertEqual(st, FiscalStates.PENDIENTE_CANCELACION)
		self.assertEqual(
			self._derive_writer({"status": "valid", "cancellation_status": "accepted"}),
			FiscalStates.PENDIENTE_CANCELACION,
		)

	# ---------- apply_cancellation_state ----------

	def test_02_motivo_persiste_en_verifying(self):
		ffm = self.ffm(None, FiscalStates.TIMBRADO, motivo="02")
		apply_cancellation_state(ffm, FiscalStates.PENDIENTE_CANCELACION, sync_status=SyncStates.SYNCED)
		self.assertEqual(self._field(ffm, "fm_motivo_cancelacion"), "02")

	def test_03b_reason_es_02_no_residual_01(self):
		ffm = self.ffm(
			None,
			FiscalStates.TIMBRADO,
			motivo="02",
			reason="01 - Comprobantes emitidos con errores con relación",
		)
		apply_cancellation_state(ffm, FiscalStates.PENDIENTE_CANCELACION, sync_status=SyncStates.SYNCED)
		self.assertEqual((self._field(ffm, "cancellation_reason") or "")[:2], "02")

	def test_04_date_vacia_en_pendiente(self):
		ffm = self.ffm(None, FiscalStates.TIMBRADO, motivo="02")
		apply_cancellation_state(ffm, FiscalStates.PENDIENTE_CANCELACION, sync_status=SyncStates.SYNCED)
		self.assertIsNone(self._field(ffm, "cancellation_date"))

	def test_05_terminal_completa_ffm_y_si(self):
		ffm = self.ffm(None, FiscalStates.PENDIENTE_CANCELACION, motivo="02")
		si = self.si(fiscal_status=FiscalStates.PENDIENTE_CANCELACION, ffm=ffm)
		frappe.db.set_value("Factura Fiscal Mexico", ffm, "sales_invoice", si)
		apply_cancellation_state(ffm, FiscalStates.CANCELADO, sync_status=SyncStates.SYNCED)
		self.assertEqual(self._status(ffm), FiscalStates.CANCELADO)
		self.assertEqual((self._field(ffm, "cancellation_reason") or "")[:2], "02")
		self.assertIsNotNone(self._field(ffm, "cancellation_date"))
		self.assertEqual(self._si_status(si), FiscalStates.CANCELADO)

	def test_08_no_toca_si_de_otra_ffm(self):
		ffm_act = self.ffm(None, FiscalStates.TIMBRADO, motivo="02")
		ffm_otra = self.ffm(
			None, FiscalStates.PENDIENTE_CANCELACION, motivo="02", facturapi_id="FA-X", uuid="U-X"
		)
		si = self.si(fiscal_status=FiscalStates.TIMBRADO, ffm=ffm_act)  # SI apunta a ffm_act
		frappe.db.set_value("Factura Fiscal Mexico", ffm_otra, "sales_invoice", si)
		# Aplicar CANCELADO a ffm_otra: como la SI NO apunta a ella, el snapshot SI no cambia.
		apply_cancellation_state(ffm_otra, FiscalStates.CANCELADO, sync_status=SyncStates.SYNCED)
		self.assertEqual(self._status(ffm_otra), FiscalStates.CANCELADO)
		self.assertEqual(self._si_status(si), FiscalStates.TIMBRADO)  # intacto

	def test_15_idempotente(self):
		ffm = self.ffm(None, FiscalStates.PENDIENTE_CANCELACION, motivo="02")
		apply_cancellation_state(ffm, FiscalStates.CANCELADO, sync_status=SyncStates.SYNCED)
		snap = frappe.db.get_value(
			"Factura Fiscal Mexico",
			ffm,
			["status", "cancellation_reason", "cancellation_date", "fm_sync_status"],
			as_dict=True,
		)
		apply_cancellation_state(ffm, FiscalStates.CANCELADO, sync_status=SyncStates.SYNCED)
		snap2 = frappe.db.get_value(
			"Factura Fiscal Mexico",
			ffm,
			["status", "cancellation_reason", "cancellation_date", "fm_sync_status"],
			as_dict=True,
		)
		self.assertEqual(snap, snap2)

	def test_16_rejected_expired_a_timbrado(self):
		ffm = self.ffm(None, FiscalStates.PENDIENTE_CANCELACION, motivo="02")
		si = self.si(fiscal_status=FiscalStates.PENDIENTE_CANCELACION, ffm=ffm)
		frappe.db.set_value("Factura Fiscal Mexico", ffm, "sales_invoice", si)
		st, sync = derive_cancellation_reconciliation("valid", "rejected")
		self.assertEqual(st, FiscalStates.TIMBRADO)
		apply_cancellation_state(ffm, st, sync_status=sync)
		self.assertEqual(self._status(ffm), FiscalStates.TIMBRADO)
		self.assertIsNone(self._field(ffm, "cancellation_date"))
		self.assertEqual(self._si_status(si), FiscalStates.TIMBRADO)

	def test_17_cancelado_no_regresa(self):
		ffm = self.ffm(None, FiscalStates.CANCELADO, motivo="02", date=frappe.utils.now_datetime())
		apply_cancellation_state(ffm, FiscalStates.PENDIENTE_CANCELACION, sync_status=SyncStates.SYNCED)
		self.assertEqual(self._status(ffm), FiscalStates.CANCELADO)  # no degrada

	def test_20_sync_status_derivado(self):
		ffm = self.ffm(None, FiscalStates.TIMBRADO, motivo="02", sync="pending")
		apply_cancellation_state(ffm, FiscalStates.PENDIENTE_CANCELACION, sync_status=SyncStates.SYNCED)
		val = self._field(ffm, "fm_sync_status")
		self.assertEqual(val, SyncStates.SYNCED)
		opts = frappe.get_meta("Factura Fiscal Mexico").get_field("fm_sync_status").options or ""
		self.assertIn(val, [o.strip() for o in opts.split("\n") if o.strip()])

	def test_23_objeto_stale_usa_motivo_actual(self):
		ffm_name = self.ffm(None, FiscalStates.TIMBRADO, motivo="03")
		ffm_doc = frappe.get_doc("Factura Fiscal Mexico", ffm_name)  # objeto en memoria con motivo=03
		frappe.db.set_value("Factura Fiscal Mexico", ffm_name, "fm_motivo_cancelacion", "02")  # cambia en BD
		apply_cancellation_state(ffm_doc, FiscalStates.PENDIENTE_CANCELACION, sync_status=SyncStates.SYNCED)
		self.assertEqual((self._field(ffm_name, "cancellation_reason") or "")[:2], "02")  # usa el actual

	def test_24_fecha_no_se_sobrescribe(self):
		ffm = self.ffm(None, FiscalStates.PENDIENTE_CANCELACION, motivo="02")
		apply_cancellation_state(ffm, FiscalStates.CANCELADO, sync_status=SyncStates.SYNCED)
		fecha1 = self._field(ffm, "cancellation_date")
		# Segunda ejecución sin fecha y una "observación posterior" no reemplazan la fecha existente.
		apply_cancellation_state(ffm, FiscalStates.CANCELADO, sync_status=SyncStates.SYNCED)
		apply_cancellation_state(
			ffm,
			FiscalStates.CANCELADO,
			sync_status=SyncStates.SYNCED,
			cancellation_date=frappe.utils.add_to_date(fecha1, days=1),
		)
		self.assertEqual(self._field(ffm, "cancellation_date"), fecha1)

	def test_25_repara_cancelado_incompleto(self):
		# CANCELADO con motivo correcto pero reason/fecha/SI incompletos -> se completan sin tocar fecha.
		ffm = self.ffm(None, FiscalStates.CANCELADO, motivo="02", reason="", date=None)
		si = self.si(fiscal_status=FiscalStates.PENDIENTE_CANCELACION, ffm=ffm)
		frappe.db.set_value("Factura Fiscal Mexico", ffm, "sales_invoice", si)
		apply_cancellation_state(ffm, FiscalStates.CANCELADO, sync_status=SyncStates.SYNCED)
		self.assertEqual((self._field(ffm, "cancellation_reason") or "")[:2], "02")
		self.assertIsNotNone(self._field(ffm, "cancellation_date"))
		self.assertEqual(self._si_status(si), FiscalStates.CANCELADO)

	def test_13_guard_usa_estado_real_de_ffm_no_snapshot(self):
		"""El guard de cancelar_si_post_fiscal valida el estado REAL de la FFM activa, NO el snapshot
		SI.fm_fiscal_status (que puede quedar stale). Documentos reales; sin mock de frappe.get_doc ni
		de funciones internas (RG-003). Se detiene de forma determinista en la validación 'todas
		canceladas', antes del cancel() real de la SI, y falla ante errores no esperados."""
		from facturacion_mexico.api.fiscal_operations import cancelar_si_post_fiscal

		# FFM activa REALMENTE cancelada ante el SAT, pero snapshot SI desactualizado (PENDIENTE).
		ffm_cancelado = self.ffm(None, FiscalStates.CANCELADO, motivo="02")
		si = self.si(fiscal_status=FiscalStates.PENDIENTE_CANCELACION, ffm=ffm_cancelado)
		frappe.db.set_value("Factura Fiscal Mexico", ffm_cancelado, "sales_invoice", si)
		# 2ª FFM ligada a la misma SI AÚN activa: el flujo pasa el guard SAT (la FFM activa SÍ está
		# CANCELADO) y se detiene en la validación determinista "todas canceladas", sin llegar al
		# cancel() real de la SI.
		ffm_activa = self.ffm(None, FiscalStates.PENDIENTE_CANCELACION, motivo="02")
		frappe.db.set_value("Factura Fiscal Mexico", ffm_activa, "sales_invoice", si)
		frappe.db.commit()

		with self.assertRaises(frappe.ValidationError) as ctx:
			cancelar_si_post_fiscal(si)
		msg = str(ctx.exception)
		# El guard SAT PASÓ: leyó el estado real de la FFM activa, no el snapshot stale de la SI.
		self.assertNotIn("cancelada ante el SAT", msg)
		# Se detuvo, de forma determinista, en la validación de FFMs aún activas (no en el cancel()).
		self.assertIn(ffm_activa, msg)

	def test_13b_guard_rechaza_cuando_ffm_activa_no_esta_cancelada(self):
		"""Caso negativo del guard: si la FFM activa NO está CANCELADO, se rechaza con el error SAT."""
		from facturacion_mexico.api.fiscal_operations import cancelar_si_post_fiscal

		ffm = self.ffm(None, FiscalStates.PENDIENTE_CANCELACION, motivo="02")
		si = self.si(fiscal_status=FiscalStates.PENDIENTE_CANCELACION, ffm=ffm)
		frappe.db.set_value("Factura Fiscal Mexico", ffm, "sales_invoice", si)
		frappe.db.commit()

		with self.assertRaisesRegex(frappe.ValidationError, "cancelada ante el SAT"):
			cancelar_si_post_fiscal(si)

	def test_13c_endpoint_publico_no_controla_skip_state_persist(self):
		"""Seguridad (#13): la frontera pública @frappe.whitelist() NO expone skip_state_persist; un
		caller no puede saltarse la persistencia del estado fiscal por el wire. El skip se deriva
		server-side de operation_type ('Solicitud Cancelación') dentro del writer."""
		import inspect

		from facturacion_mexico.facturacion_fiscal.api import write_pac_response

		# 1. La firma pública no incluye el parámetro.
		self.assertNotIn("skip_state_persist", inspect.signature(write_pac_response).parameters)

		# 2. Enviar el flag desde el caller falla por argumento inesperado (TypeError en el binding,
		#    antes de tocar BD): no es controlable desde el request.
		with self.assertRaises(TypeError):
			write_pac_response(
				"SI-INEXISTENTE",
				"{}",
				"{}",
				"timbrado",
				factura_fiscal_name="FFM-INEXISTENTE",
				skip_state_persist=True,
			)

	# ---------- Motor asíncrono ----------

	def _fake_client(self, raw):
		c = MagicMock()
		c.get_invoice.return_value = {"success": True, "status_code": 200, "raw_response": raw}
		return c

	def test_06_motor_pendiente_a_cancelado_completo(self):
		from facturacion_mexico.facturacion_fiscal.services import ffm_reconciliation as mod

		ffm = self.ffm(
			None,
			FiscalStates.PENDIENTE_CANCELACION,
			motivo="02",
			sync="pending",
			facturapi_id=_FA,
			uuid=_UUID,
		)
		si = self.si(fiscal_status=FiscalStates.PENDIENTE_CANCELACION, ffm=ffm)
		frappe.db.set_value("Factura Fiscal Mexico", ffm, "sales_invoice", si)
		raw = {"status": "canceled", "cancellation_status": "accepted", "id": _FA, "uuid": _UUID}
		with patch.object(mod, "get_facturapi_client", return_value=self._fake_client(raw)):
			mod._reconcile_ffm(ffm)
		self.assertEqual(self._status(ffm), FiscalStates.CANCELADO)
		self.assertEqual((self._field(ffm, "cancellation_reason") or "")[:2], "02")
		self.assertIsNotNone(self._field(ffm, "cancellation_date"))
		self.assertEqual(self._field(ffm, "fm_sync_status"), SyncStates.SYNCED)
		self.assertEqual(self._si_status(si), FiscalStates.CANCELADO)

	def test_22_reconciliacion_no_cancelacion_intacta(self):
		from facturacion_mexico.facturacion_fiscal.services import ffm_reconciliation as mod

		# FFM TIMBRADO con sync pending; respuesta valid sin cancelación -> NO es cancelación.
		ffm = self.ffm(None, FiscalStates.TIMBRADO, sync="pending", facturapi_id=_FA, uuid=_UUID)
		raw = {"status": "valid", "cancellation_status": "none", "id": _FA, "uuid": _UUID}
		with (
			patch.object(mod, "get_facturapi_client", return_value=self._fake_client(raw)),
			patch.object(mod, "apply_cancellation_state") as apply_mock,
		):
			mod._reconcile_ffm(ffm)
			apply_mock.assert_not_called()  # no usa el helper de cancelación
		self.assertEqual(self._status(ffm), FiscalStates.TIMBRADO)

	# ---------- Consolidación: un solo flujo (motor) + revisar como wrapper ----------

	def test_07_revisar_delega_en_motor(self):
		# revisar_estatus_cancelacion NO tiene lógica propia: delega en reconcile_ffm y NO hace
		# una segunda consulta al PAC (no llama query_pac_status).
		from facturacion_mexico.facturacion_fiscal import timbrado_api as tmod

		ffm = self.ffm(None, FiscalStates.PENDIENTE_CANCELACION, motivo="02")
		with (
			patch(
				"facturacion_mexico.facturacion_fiscal.services.ffm_reconciliation.reconcile_ffm",
				return_value={"ffm": ffm, "outcome": "changed"},
			) as rec,
			patch("facturacion_mexico.facturacion_fiscal.api_client.query_pac_status") as qps,
		):
			out = tmod.revisar_estatus_cancelacion(ffm)
		rec.assert_called_once_with(ffm)  # delega en el motor
		qps.assert_not_called()  # sin segunda llamada al PAC
		self.assertEqual(out, {"ffm": ffm, "outcome": "changed"})

	def test_07b_motor_repara_cancelado_incompleto(self):
		# Flujo A (motor) repara una FFM CANCELADO+synced con reason/fecha/SI incompletos,
		# aunque status y sync no cambien. Y crea Response Log porque reparó.
		from facturacion_mexico.facturacion_fiscal.services import ffm_reconciliation as mod

		ffm = self.ffm(
			None,
			FiscalStates.CANCELADO,
			motivo="02",
			reason="01 - Comprobantes emitidos con errores con relación",
			date=None,
			sync="synced",
			facturapi_id=_FA,
			uuid=_UUID,
		)
		si = self.si(fiscal_status=FiscalStates.PENDIENTE_CANCELACION, ffm=ffm)  # snapshot viejo
		frappe.db.set_value("Factura Fiscal Mexico", ffm, "sales_invoice", si)
		n0 = frappe.db.count("FacturAPI Response Log", {"factura_fiscal_mexico": ffm})
		raw = {"status": "canceled", "cancellation_status": "accepted", "id": _FA, "uuid": _UUID}
		with patch.object(mod, "get_facturapi_client", return_value=self._fake_client(raw)):
			out = mod._reconcile_ffm(ffm)
		self.assertEqual(self._status(ffm), FiscalStates.CANCELADO)  # no degrada
		self.assertEqual((self._field(ffm, "cancellation_reason") or "")[:2], "02")  # reparado
		self.assertIsNotNone(self._field(ffm, "cancellation_date"))  # reparado
		self.assertEqual(self._si_status(si), FiscalStates.CANCELADO)  # snapshot reparado
		self.assertEqual(out.get("outcome"), "changed")
		self.assertEqual(  # reparar SÍ deja Response Log
			frappe.db.count("FacturAPI Response Log", {"factura_fiscal_mexico": ffm}), n0 + 1
		)

	def test_07c_motor_consistente_no_reescribe_ni_loguea(self):
		# FFM CANCELADO ya completa y consistente: el motor no reescribe ni crea Response Log.
		from facturacion_mexico.facturacion_fiscal.services import ffm_reconciliation as mod

		ffm = self.ffm(
			None,
			FiscalStates.CANCELADO,
			motivo="02",
			reason="02 - Comprobantes emitidos con errores sin relación",
			date=frappe.utils.now_datetime(),
			sync="synced",
			facturapi_id=_FA,
			uuid=_UUID,
		)
		si = self.si(fiscal_status=FiscalStates.CANCELADO, ffm=ffm)
		frappe.db.set_value("Factura Fiscal Mexico", ffm, "sales_invoice", si)
		before = frappe.db.get_value(
			"Factura Fiscal Mexico",
			ffm,
			["cancellation_reason", "cancellation_date", "fm_sync_status", "status"],
			as_dict=True,
		)
		n0 = frappe.db.count("FacturAPI Response Log", {"factura_fiscal_mexico": ffm})
		raw = {"status": "canceled", "cancellation_status": "accepted", "id": _FA, "uuid": _UUID}
		with patch.object(mod, "get_facturapi_client", return_value=self._fake_client(raw)):
			out = mod._reconcile_ffm(ffm)
		after = frappe.db.get_value(
			"Factura Fiscal Mexico",
			ffm,
			["cancellation_reason", "cancellation_date", "fm_sync_status", "status"],
			as_dict=True,
		)
		self.assertEqual(out.get("outcome"), "unchanged")
		self.assertEqual(before, after)  # no reescribe
		self.assertEqual(  # sin log automático
			frappe.db.count("FacturAPI Response Log", {"factura_fiscal_mexico": ffm}), n0
		)

	def test_07e_correlacion_invalida_no_aplica(self):
		# Respuesta con identidad que NO corresponde a la FFM: no se aplica, no se modifica FFM/SI.
		from facturacion_mexico.facturacion_fiscal.services import ffm_reconciliation as mod

		ffm = self.ffm(None, FiscalStates.PENDIENTE_CANCELACION, motivo="02", sync="pending")
		si = self.si(fiscal_status=FiscalStates.PENDIENTE_CANCELACION, ffm=ffm)
		frappe.db.set_value("Factura Fiscal Mexico", ffm, "sales_invoice", si)
		raw = {
			"status": "canceled",
			"cancellation_status": "accepted",
			"id": "FA-OTRO",
			"uuid": "U-OTRO",
		}  # identidad contradictoria
		with patch.object(mod, "get_facturapi_client", return_value=self._fake_client(raw)):
			out = mod._reconcile_ffm(ffm)
		self.assertEqual(out.get("outcome"), "error")
		self.assertEqual(self._status(ffm), FiscalStates.PENDIENTE_CANCELACION)  # sin cambio
		self.assertEqual(self._si_status(si), FiscalStates.PENDIENTE_CANCELACION)

	def test_07f_solo_un_boton_consulta_en_gui(self):
		import os

		js = os.path.join(
			frappe.get_app_path("facturacion_mexico"),
			"facturacion_fiscal",
			"doctype",
			"factura_fiscal_mexico",
			"factura_fiscal_mexico.js",
		)
		with open(js, encoding="utf-8") as f:
			content = f.read()
		self.assertNotIn("Revisar Estatus Cancelación", content)  # botón duplicado eliminado
		self.assertIn("Verificar estado en FacturAPI", content)  # único botón de consulta

	# ---------- canceled_at del PAC (timestamp real + zona horaria) ----------

	def test_canceledat_extrae_y_normaliza_tz(self):
		# UTC con 'Z' -> MISMO instante en la zona del sitio (no se descarta la zona).
		import datetime as dt

		from facturacion_mexico.facturacion_fiscal.cancellation_state import extract_canceled_at

		resp = {"raw_response": {"cancellation": {"canceled_at": "2026-06-23T15:51:42.045Z"}}}
		got = extract_canceled_at(resp)
		self.assertIsNotNone(got)
		expected = frappe.utils.convert_utc_to_system_timezone(dt.datetime(2026, 6, 23, 15, 51, 42))
		expected = expected.replace(tzinfo=None) if getattr(expected, "tzinfo", None) else expected
		self.assertEqual(got.replace(microsecond=0), expected.replace(microsecond=0))  # mismo instante

	def test_canceledat_ausente_devuelve_none(self):
		from facturacion_mexico.facturacion_fiscal.cancellation_state import extract_canceled_at

		self.assertIsNone(extract_canceled_at({"raw_response": {"status": "canceled"}}))
		self.assertIsNone(extract_canceled_at({"raw_response": {"cancellation": {"status": "none"}}}))

	def test_motor_usa_canceledat_del_pac(self):
		# canceled + canceled_at -> la fecha persistida es el timestamp REAL del PAC (no now()).
		from facturacion_mexico.facturacion_fiscal.cancellation_state import extract_canceled_at
		from facturacion_mexico.facturacion_fiscal.services import ffm_reconciliation as mod

		ffm = self.ffm(
			None,
			FiscalStates.PENDIENTE_CANCELACION,
			motivo="02",
			sync="pending",
			facturapi_id=_FA,
			uuid=_UUID,
		)
		si = self.si(fiscal_status=FiscalStates.PENDIENTE_CANCELACION, ffm=ffm)
		frappe.db.set_value("Factura Fiscal Mexico", ffm, "sales_invoice", si)
		raw = {
			"status": "canceled",
			"cancellation_status": "none",
			"id": _FA,
			"uuid": _UUID,
			"cancellation": {"canceled_at": "2026-06-23T15:51:42.045Z"},
		}
		with patch.object(mod, "get_facturapi_client", return_value=self._fake_client(raw)):
			mod._reconcile_ffm(ffm)
		got = self._field(ffm, "cancellation_date")
		expected = extract_canceled_at({"raw_response": raw})
		self.assertEqual(got.replace(microsecond=0), expected.replace(microsecond=0))

	def test_motor_sin_canceledat_usa_observacion(self):
		# canceled SIN canceled_at -> hora de observación (no None).
		from facturacion_mexico.facturacion_fiscal.services import ffm_reconciliation as mod

		ffm = self.ffm(
			None,
			FiscalStates.PENDIENTE_CANCELACION,
			motivo="02",
			sync="pending",
			facturapi_id=_FA,
			uuid=_UUID,
		)
		raw = {"status": "canceled", "cancellation_status": "none", "id": _FA, "uuid": _UUID}
		with patch.object(mod, "get_facturapi_client", return_value=self._fake_client(raw)):
			mod._reconcile_ffm(ffm)
		self.assertIsNotNone(self._field(ffm, "cancellation_date"))

	def test_motor_pasa_canceledat_al_helper(self):
		from facturacion_mexico.facturacion_fiscal.cancellation_state import extract_canceled_at
		from facturacion_mexico.facturacion_fiscal.services import ffm_reconciliation as mod

		ffm = self.ffm(
			None,
			FiscalStates.PENDIENTE_CANCELACION,
			motivo="02",
			sync="pending",
			facturapi_id=_FA,
			uuid=_UUID,
		)
		raw = {
			"status": "canceled",
			"cancellation_status": "none",
			"id": _FA,
			"uuid": _UUID,
			"cancellation": {"canceled_at": "2026-06-23T15:51:42.045Z"},
		}
		exp = extract_canceled_at({"raw_response": raw})
		with (
			patch.object(mod, "get_facturapi_client", return_value=self._fake_client(raw)),
			patch.object(mod, "apply_cancellation_state", return_value=True) as ap,
		):
			mod._reconcile_ffm(ffm)
		_, kwargs = ap.call_args
		self.assertEqual(kwargs.get("cancellation_date").replace(microsecond=0), exp.replace(microsecond=0))

	def test_motor_no_terminal_sin_fecha(self):
		# verifying / pending / rejected / desconocido -> NO se fija cancellation_date.
		from facturacion_mexico.facturacion_fiscal.services import ffm_reconciliation as mod

		for cs in ("verifying", "pending", "rejected", "zzz-desconocido"):
			ffm = self.ffm(
				None,
				FiscalStates.PENDIENTE_CANCELACION,
				motivo="02",
				sync="pending",
				facturapi_id=_FA,
				uuid=_UUID,
			)
			raw = {"status": "valid", "cancellation_status": cs, "id": _FA, "uuid": _UUID}
			with patch.object(mod, "get_facturapi_client", return_value=self._fake_client(raw)):
				mod._reconcile_ffm(ffm)
			self.assertIsNone(self._field(ffm, "cancellation_date"), f"cs={cs}")

	# ---------- Cascada ----------

	def test_10_21_cascada_no_terminal_no_cancela(self):
		from facturacion_mexico.facturacion_fiscal import timbrado_api as tmod

		src_uuid = "U-SRC-" + frappe.generate_hash()[:8]
		new_uuid = "U-NEW-" + frappe.generate_hash()[:8]
		orig_ffm = self.ffm(None, FiscalStates.TIMBRADO, motivo="02", facturapi_id="FA-ORIG", uuid=src_uuid)
		orig_si = self.si(fiscal_status=FiscalStates.TIMBRADO, ffm=orig_ffm)
		frappe.db.set_value("Factura Fiscal Mexico", orig_ffm, "sales_invoice", orig_si)
		new_ffm = self.ffm(None, FiscalStates.TIMBRADO, facturapi_id="FA-NEW", uuid=new_uuid)
		new_si = self.si(fiscal_status=FiscalStates.TIMBRADO, ffm=new_ffm)
		frappe.db.set_value("Factura Fiscal Mexico", new_ffm, "sales_invoice", new_si)
		frappe.db.set_value("Sales Invoice", new_si, "ffm_substitution_source_uuid", src_uuid)
		frappe.db.commit()

		# PAC deja la cancelación NO terminal (no marca CANCELADO la FFM previa).
		with patch.object(
			tmod.TimbradoAPI, "cancelar_factura", return_value={"status_ffm": "PENDIENTE_CANCELACION"}
		):
			res = tmod._cascade_cancel_previous_after_substitute(new_ffm)
		self.assertEqual(res.get("cascade"), "halted_not_terminal")
		self.assertNotEqual(self._status(orig_ffm), FiscalStates.CANCELADO)
		self.assertEqual(frappe.db.get_value("Sales Invoice", orig_si, "docstatus"), 1)  # SI NO cancelada

	# ---------- FFM nueva / endpoint / 1406 / logger ----------

	def test_12_ffm_nueva_reason_vacio(self):
		from frappe.model.create_new import get_new_doc

		nuevo = get_new_doc("Factura Fiscal Mexico")
		self.assertIn((nuevo.get("cancellation_reason") or ""), ("", None))

	def test_14_endpoint_usa_ffm_enlazada(self):
		from facturacion_mexico.facturacion_fiscal import timbrado_api as tmod

		ffm_link = self.ffm(None, FiscalStates.TIMBRADO, facturapi_id="FA-L", uuid="U-L")
		ffm_otra = self.ffm(None, FiscalStates.TIMBRADO, facturapi_id="FA-O", uuid="U-O")
		si = self.si(fiscal_status=FiscalStates.TIMBRADO, ffm=ffm_link)
		# Ambas FFM apuntan a la misma SI; la activa es ffm_link (SI.fm_factura_fiscal_mx).
		frappe.db.set_value("Factura Fiscal Mexico", ffm_link, "sales_invoice", si)
		frappe.db.set_value("Factura Fiscal Mexico", ffm_otra, "sales_invoice", si)
		frappe.db.commit()
		with patch.object(tmod, "TimbradoAPI") as TApi:
			TApi.return_value.cancelar_factura.return_value = {"ok": True}
			tmod.cancelar_factura(sales_invoice=si, motivo="02")
		self.assertEqual(self._field(ffm_link, "fm_motivo_cancelacion"), "02")  # se escribió en la enlazada
		self.assertIsNone(self._field(ffm_otra, "fm_motivo_cancelacion"))  # NO en la otra (no limit=1)

	def test_11_log_error_nombrado_sin_1406(self):
		# El fix usa args nombrados: un mensaje largo va a 'error' (Long Text), no a 'method' (140).
		try:
			frappe.log_error(title="PAC Cancelación Error", message="X" * 500)
		except Exception as e:
			self.fail(f"log_error con args nombrados no debe fallar (1406): {e}")

	def test_26_logger_no_enmascara_original(self):
		# Flujo SÍNCRONO de cancelación: si el logger falla, NO reemplaza el error original.
		from facturacion_mexico.facturacion_fiscal import timbrado_api as tmod

		ffm = self.ffm(None, FiscalStates.TIMBRADO, motivo="02", facturapi_id="FA-1", uuid="U-1")
		si = self.si(fiscal_status=FiscalStates.TIMBRADO, ffm=ffm)
		frappe.db.set_value("Factura Fiscal Mexico", ffm, "sales_invoice", si)
		frappe.db.commit()
		client = MagicMock()
		client.cancel_invoice.return_value = {
			"success": True,
			"status_code": 200,
			"raw_response": {"status": "canceled", "id": "FA-1", "uuid": "U-1"},
		}
		with patch.object(tmod, "get_facturapi_client", return_value=client):
			api = tmod.TimbradoAPI(company="_Test Company")
			with (
				patch.object(tmod, "apply_cancellation_state", side_effect=ValueError("ORIGINAL")),
				patch.object(tmod, "write_pac_response", return_value={"success": True}),
				patch.object(tmod.TimbradoAPI, "_download_cancellation_receipt_files", return_value=None),
				patch("frappe.log_error", side_effect=Exception("LOGGER-1406")),
			):
				result = api.cancelar_factura(si, "02")
		# El fallo del logger se tragó; el resultado refleja el error ORIGINAL, no el del logger.
		self.assertIn("ORIGINAL", str(result.get("error", "")))
		self.assertNotIn("LOGGER-1406", str(result))
		self.assertEqual(self._status(ffm), FiscalStates.TIMBRADO)  # apply falló -> FFM sin cambio
