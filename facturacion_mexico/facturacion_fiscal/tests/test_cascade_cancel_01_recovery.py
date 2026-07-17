"""Regresión del fix (SIMPLIFICADO) de recuperación de la cascada de sustitución motivo 01.

Cronología del fix: intento inmediato → +0.5s → +1.0s (solo errores transitorios) dentro del
request; si se agota, A queda PENDIENTE_CANCELACION + fm_sync_status='pending' SIN falsear el
timbrado de B; un scheduler (cada 1 min) la retoma con GET-first.

Cubre:
  (1) cancelación inmediata OK;
  (2) transitorio recuperado por reintento inmediato;
  (3) reintentos inmediatos agotados → PENDIENTE (sin falso error de timbrado);
  (4) cancelación fiscal ya ocurrida → reconciliar documentos;
  (5) idempotencia;
  (6) scheduler: A 'valid' → reenvía 1 DELETE y cancela;
  (7) scheduler: A ya 'canceled' → no reenvía, reconcilia;
  (8) scheduler: error definitivo → sale del ciclo automático (fm_sync_status='error');
  (9) unidad: clasificación de errores transitorios.

Único boundary mockeado: el PAC (`TimbradoAPI` y sus métodos, que en producción llaman a
FacturAPI). Todo lo demás usa el código real. `time.sleep` se neutraliza para no ralentizar.
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.config.fiscal_states_config import FiscalStates
from facturacion_mexico.facturacion_fiscal import timbrado_api as T


def _codigo(v):
	return str(v).split(" - ")[0].split(" ")[0].strip()


class _FakeCancelClient:
	"""Cliente FacturAPI falso SOLO en el boundary HTTP: deja correr el código real de
	cancelar_factura (incluido su guard de estado). GET->valid, DELETE->canceled/accepted."""

	def __init__(self):
		self.cancel_calls = []

	def get_invoice(self, fid):
		return {"raw_response": {"status": "valid"}}

	def cancel_invoice(self, fid, motivo, uuid):
		self.cancel_calls.append((fid, motivo, uuid))
		return {"raw_response": {"status": "canceled", "cancellation_status": "accepted"}}

	# El acuse se descarga best-effort (try/except en el código); no es parte de la aserción.
	def download_cancellation_receipt_pdf(self, fid):
		raise Exception("no-op en test")

	def download_cancellation_receipt_xml(self, fid):
		raise Exception("no-op en test")


class TestCascadeCancel01Recovery(FrappeTestCase):
	def setUp(self):
		self.h = frappe.generate_hash()[:6]
		# Company con cuenta por cobrar configurada (para poder crear/submit SI).
		self.debit_to = frappe.db.get_value(
			"Account", {"account_type": "Receivable", "is_group": 0}, ["name", "company"], as_dict=True
		)
		self.company = self.debit_to.company
		self.debit_to = self.debit_to.name
		# Moneda del documento = moneda de la cuenta por cobrar (o la de la empresa). Evita el
		# mismatch "currency (MXN) vs document currency (INR)" en CI, donde la SI defaultea a INR.
		self.si_currency = frappe.db.get_value(
			"Account", self.debit_to, "account_currency"
		) or frappe.db.get_value("Company", self.company, "default_currency")
		self.income_acc = frappe.db.get_value(
			"Account", {"company": self.company, "root_type": "Income", "is_group": 0}, "name"
		)
		self.cg = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
		self.terr = frappe.db.get_value("Territory", {"is_group": 0}, "name")
		self.cc = frappe.db.get_value("Cost Center", {"is_group": 0, "company": self.company}, "name")
		# Ítem determinista: grupo garantizado por el seed ("Products") + clave SAT válida.
		# Evita ítems basura de otras suites que referencian Item Groups inexistentes.
		self.item = f"FM-CASCADE-{self.h}"
		if not frappe.db.exists("Item", self.item):
			ig = frappe.db.get_value("Item Group", "Products", "name") or frappe.db.get_value(
				"Item Group", {"is_group": 0}, "name"
			)
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": self.item,
					"item_name": self.item,
					"item_group": ig,
					"stock_uom": "Nos",
					"is_stock_item": 0,
					"is_sales_item": 1,
					"fm_producto_servicio_sat": "84111506",
				}
			).insert(ignore_permissions=True)
		# Catálogos SAT reales del site (fm_cfdi_use=Link Uso CFDI SAT; fm_forma_pago_timbrado=Link Mode of Payment).
		self.uso_cfdi = frappe.db.get_value("Uso CFDI SAT", "G03", "name") or frappe.db.get_value(
			"Uso CFDI SAT", {}, "name"
		)
		self.forma_pago = frappe.db.get_value("Mode of Payment", {}, "name")

		self.customer = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": f"CLI-{self.h}",
				"customer_type": "Company",
				"customer_group": self.cg,
				"territory": self.terr,
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value(
			"Customer",
			self.customer.name,
			{
				"tax_id": "XAXX010101000",
				"fm_rfc_validated": 1,
				"fm_uso_cfdi_default": "G03",
				"fm_tax_regime": "601",
			},
		)

		self.A_uuid = f"AAAA{self.h}-0000-0000-0000-000000000001".lower()
		self.B_uuid = f"BBBB{self.h}-0000-0000-0000-000000000002".lower()

	def tearDown(self):
		# Limpieza dura: estos tests hacen commit (helpers + código productivo bajo prueba), así que
		# las filas sobreviven al rollback de FrappeTestCase. Sin esto, las FFM que quedan en
		# PENDIENTE_CANCELACION/pending contaminarían la suite de reconciliación.
		super().tearDown()
		for ffm in [getattr(self, "A_ffm", None), getattr(self, "B_ffm", None)]:
			if ffm:
				frappe.db.delete("Factura Fiscal Mexico", {"name": ffm})
		for si in [getattr(self, "A_si", None), getattr(self, "B_si", None)]:
			if si:
				frappe.db.delete("Sales Invoice Item", {"parent": si})
				frappe.db.delete("Sales Invoice", {"name": si})
		frappe.db.commit()  # nosemgrep: frappe-manual-commit

	# ---------------- helpers ----------------

	def _mk_si(self, src_uuid=None):
		si = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": self.company,
				"customer": self.customer.name,
				"currency": self.si_currency,
				"cost_center": self.cc,
				"debit_to": self.debit_to,
				"items": [
					{
						"item_code": self.item,
						"qty": 1,
						"rate": 100,
						"cost_center": self.cc,
						"income_account": self.income_acc,
					}
				],
			}
		)
		if src_uuid:
			si.set("ffm_substitution_source_uuid", src_uuid)
		si.insert(ignore_permissions=True)
		si.submit()
		return si.name

	def _mk_ffm_timbrado(self, si_name, uuid):
		"""FFM submitted en estado TIMBRADO con UUID/facturapi_id (sin llamar al PAC)."""
		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
			get_or_create_active_ffm,
		)

		ffm_name = get_or_create_active_ffm(si_name)
		ffm = frappe.get_doc("Factura Fiscal Mexico", ffm_name)
		if not ffm.get("fm_cfdi_use") and self.uso_cfdi:
			ffm.fm_cfdi_use = self.uso_cfdi
		if not ffm.get("fm_tax_system"):
			ffm.fm_tax_system = "601"
		if not ffm.get("fm_forma_pago_timbrado") and self.forma_pago:
			ffm.fm_forma_pago_timbrado = self.forma_pago
		ffm.fm_payment_method_sat = "PPD"
		ffm.save(ignore_permissions=True)
		if ffm.docstatus == 0:
			ffm.submit()
		frappe.db.set_value(
			"Factura Fiscal Mexico",
			ffm_name,
			{
				"status": FiscalStates.TIMBRADO,
				"fm_uuid": uuid,
				"facturapi_id": f"fapi_{uuid[:12]}",
				"fecha_timbrado": frappe.utils.now_datetime(),
			},
		)
		frappe.db.commit()
		return ffm_name

	def _build_A_B(self):
		self.A_si = self._mk_si()
		self.A_ffm = self._mk_ffm_timbrado(self.A_si, self.A_uuid)
		self.B_si = self._mk_si(src_uuid=self.A_uuid)
		self.B_ffm = self._mk_ffm_timbrado(self.B_si, self.B_uuid)

	def _pac_ok(self, *a, **k):
		"""Mock: PAC acepta → deja A en CANCELADO (como haría apply_cancellation_state).
		Sin commit: en la misma transacción el set_value ya es visible para la cascada."""
		frappe.db.set_value("Factura Fiscal Mexico", self.A_ffm, "status", FiscalStates.CANCELADO)
		return {"status": "accepted"}

	def _pac_404(self, *a, **k):
		raise frappe.ValidationError("Error FacturAPI 404: invoice_not_found - No se encontró la factura.")

	def _ds(self, doctype, name):
		return frappe.db.get_value(doctype, name, "docstatus")

	# ---------------- TESTS ----------------

	def test_1_cancelacion_inmediata_ok(self):
		self._build_A_B()
		with patch.object(T, "TimbradoAPI") as MockAPI:
			MockAPI.return_value.cancelar_factura.side_effect = self._pac_ok
			res = T._cascade_cancel_previous_after_substitute(self.B_ffm)
		self.assertEqual(res.get("cascade"), "completed")
		self.assertEqual(self._ds("Sales Invoice", self.A_si), 2, "SI A debe quedar docstatus=2")
		self.assertEqual(self._ds("Factura Fiscal Mexico", self.A_ffm), 2, "FFM A debe quedar docstatus=2")

	def test_2_404_transitorio_reintento_ok(self):
		self._build_A_B()
		seq = [self._pac_404, self._pac_ok]

		def side(*a, **k):
			return seq.pop(0)(*a, **k)

		with (
			patch("facturacion_mexico.facturacion_fiscal.timbrado_api.time.sleep"),
			patch.object(T, "TimbradoAPI") as MockAPI,
		):
			MockAPI.return_value.cancelar_factura.side_effect = side
			res = T._cascade_cancel_previous_after_substitute(self.B_ffm)
		self.assertEqual(res.get("cascade"), "completed")
		self.assertEqual(self._ds("Sales Invoice", self.A_si), 2)
		self.assertEqual(self._ds("Factura Fiscal Mexico", self.A_ffm), 2)

	def test_3_reintentos_inmediatos_agotados_deja_pendiente(self):
		"""404 transitorio persistente en la ventana inmediata: NO se falsea el timbrado de B.
		A queda PENDIENTE_CANCELACION + fm_sync_status='pending' (para el scheduler), docstatus intactos."""
		self._build_A_B()
		with (
			patch("facturacion_mexico.facturacion_fiscal.timbrado_api.time.sleep"),
			patch.object(T, "TimbradoAPI") as MockAPI,
		):
			MockAPI.return_value.cancelar_factura.side_effect = self._pac_404
			res = T._cascade_cancel_previous_after_substitute(self.B_ffm)
		self.assertEqual(res.get("cascade"), "pending_cancellation")
		self.assertEqual(self._ds("Sales Invoice", self.A_si), 1, "SI A NO debe cancelarse")
		self.assertEqual(self._ds("Factura Fiscal Mexico", self.A_ffm), 1, "FFM A NO debe cancelarse")
		a = frappe.db.get_value(
			"Factura Fiscal Mexico", self.A_ffm, ["status", "fm_sync_status", "fm_sync_error"], as_dict=True
		)
		self.assertEqual(a.status, FiscalStates.PENDIENTE_CANCELACION)
		self.assertEqual(a.fm_sync_status, "pending", "debe quedar en la cola del scheduler")
		self.assertTrue(a.fm_sync_error, "debe explicar por qué quedó pendiente")

	def test_4_cancelacion_fiscal_ya_ocurrida_reconcilia_documentos(self):
		self._build_A_B()
		# Fiscal ya CANCELADO (por reconcile/reintento previo) pero documentos aún docstatus=1.
		frappe.db.set_value("Factura Fiscal Mexico", self.A_ffm, "status", FiscalStates.CANCELADO)
		frappe.db.commit()
		called = {"n": 0}

		def spy(*a, **k):
			called["n"] += 1
			return {"status": "accepted"}

		with patch.object(T.TimbradoAPI, "cancelar_factura", side_effect=spy):
			res = T._cascade_cancel_previous_after_substitute(self.B_ffm)
		self.assertEqual(res.get("cascade"), "documental_completed")
		self.assertEqual(called["n"], 0, "no debe re-llamar al PAC si ya está CANCELADO")
		self.assertEqual(self._ds("Sales Invoice", self.A_si), 2)
		self.assertEqual(self._ds("Factura Fiscal Mexico", self.A_ffm), 2)

	def test_5_idempotencia_ya_todo_cancelado(self):
		self._build_A_B()
		frappe.db.set_value("Factura Fiscal Mexico", self.A_ffm, "status", FiscalStates.CANCELADO)
		frappe.db.commit()
		with patch.object(T.TimbradoAPI, "cancelar_factura", side_effect=self._pac_ok):
			T._cascade_cancel_previous_after_substitute(self.B_ffm)  # 1ª: baja a docstatus=2
			res2 = T._cascade_cancel_previous_after_substitute(self.B_ffm)  # 2ª: no-op
		self.assertEqual(res2.get("skipped"), "already_cancelled")
		self.assertEqual(self._ds("Sales Invoice", self.A_si), 2)
		self.assertEqual(self._ds("Factura Fiscal Mexico", self.A_ffm), 2)

	# ---------------- SCHEDULER: retry_pending_substitution_cancellations ----------------

	def _set_A_pending(self):
		"""Simula el estado dejado por la cascada tras agotar los reintentos inmediatos.
		Incluye el snapshot fm_fiscal_status en la SI (es lo que evalúa el guard de cancelar_factura)."""
		frappe.db.set_value(
			"Factura Fiscal Mexico",
			self.A_ffm,
			{"status": FiscalStates.PENDIENTE_CANCELACION, "fm_sync_status": "pending"},
		)
		frappe.db.set_value(
			"Sales Invoice", self.A_si, "fm_fiscal_status", FiscalStates.PENDIENTE_CANCELACION
		)
		frappe.db.commit()

	def test_6_scheduler_A_valida_reenvia_delete_y_cancela(self):
		"""A sigue 'valid' en el PAC: el scheduler reenvía UN DELETE motivo 01 y completa documental."""
		self._build_A_B()
		self._set_A_pending()
		with patch.object(T, "TimbradoAPI") as MockAPI:
			MockAPI.return_value.client.get_invoice.return_value = {"raw_response": {"status": "valid"}}
			MockAPI.return_value.cancelar_factura.side_effect = self._pac_ok
			T.retry_pending_substitution_cancellations()
		self.assertEqual(MockAPI.return_value.cancelar_factura.call_count, 1, "debe reenviar 1 DELETE")
		self.assertEqual(self._ds("Sales Invoice", self.A_si), 2)
		self.assertEqual(self._ds("Factura Fiscal Mexico", self.A_ffm), 2)

	def test_7_scheduler_A_ya_cancelada_no_reenvia_delete(self):
		"""A ya 'canceled' en el PAC: NO se reenvía DELETE; solo reconcilia + completa documental."""
		self._build_A_B()
		self._set_A_pending()
		with patch.object(T, "TimbradoAPI") as MockAPI:
			MockAPI.return_value.client.get_invoice.return_value = {"raw_response": {"status": "canceled"}}
			T.retry_pending_substitution_cancellations()
		self.assertEqual(
			MockAPI.return_value.cancelar_factura.call_count, 0, "no reenviar si ya está cancelada"
		)
		self.assertEqual(
			frappe.db.get_value("Factura Fiscal Mexico", self.A_ffm, "status"), FiscalStates.CANCELADO
		)
		self.assertEqual(self._ds("Sales Invoice", self.A_si), 2)
		self.assertEqual(self._ds("Factura Fiscal Mexico", self.A_ffm), 2)

	def test_8_scheduler_error_definitivo_sale_del_ciclo(self):
		"""Error NO transitorio al reenviar: A sale del ciclo automático (fm_sync_status='error')."""
		self._build_A_B()
		self._set_A_pending()

		def _pac_definitivo(*a, **k):
			raise frappe.ValidationError("Error FacturAPI 422: unprocessable - motivo inválido")

		with patch.object(T, "TimbradoAPI") as MockAPI:
			MockAPI.return_value.client.get_invoice.return_value = {"raw_response": {"status": "valid"}}
			MockAPI.return_value.cancelar_factura.side_effect = _pac_definitivo
			T.retry_pending_substitution_cancellations()
		a = frappe.db.get_value(
			"Factura Fiscal Mexico", self.A_ffm, ["fm_sync_status", "status"], as_dict=True
		)
		self.assertEqual(a.fm_sync_status, "error", "debe salir del ciclo automático")
		self.assertEqual(self._ds("Factura Fiscal Mexico", self.A_ffm), 1, "documentos intactos")

	def _age_B(self, minutes):
		"""Envejece el ancla real (fecha_timbrado de B) `minutes` minutos hacia atrás."""
		from frappe.utils import add_to_date

		frappe.db.set_value(
			"Factura Fiscal Mexico",
			self.B_ffm,
			"fecha_timbrado",
			add_to_date(frappe.utils.now_datetime(), minutes=-minutes),
			update_modified=False,
		)
		frappe.db.commit()

	def test_10_scheduler_abandona_tras_ventana_maxima(self):
		"""Cota anti-bloqueo: pasada la ventana máxima (desde fecha_timbrado de B), el scheduler
		abandona el caso SIN llamar al PAC (ni GET ni DELETE) y lo deja como error accionable."""
		self._build_A_B()
		self._set_A_pending()
		self._age_B(T._SUBSTITUTION_CANCEL_MAX_AGE_MIN + 5)
		with patch.object(T, "TimbradoAPI") as MockAPI:
			T.retry_pending_substitution_cancellations()
			MockAPI.return_value.client.get_invoice.assert_not_called()
			MockAPI.return_value.cancelar_factura.assert_not_called()
		self.assertEqual(
			frappe.db.get_value("Factura Fiscal Mexico", self.A_ffm, "fm_sync_status"),
			"error",
			"debe salir del ciclo automático",
		)

	def test_11_scheduler_throttle_fuera_de_ventana_rapida(self):
		"""Throttle escalonado: pasada la ventana rápida, si el último contacto con el PAC
		(fm_last_pac_sync) es reciente (<5 min), el tick se salta SIN llamar al PAC."""
		from frappe.utils import add_to_date

		self._build_A_B()
		self._set_A_pending()
		self._age_B(10)  # fuera de la ventana rápida (>5 min)
		# Contacto reciente con el PAC → debe enfriar.
		frappe.db.set_value(
			"Factura Fiscal Mexico",
			self.A_ffm,
			"fm_last_pac_sync",
			add_to_date(frappe.utils.now_datetime(), minutes=-1),
			update_modified=False,
		)
		frappe.db.commit()
		with patch.object(T, "TimbradoAPI") as MockAPI:
			T.retry_pending_substitution_cancellations()
			MockAPI.return_value.client.get_invoice.assert_not_called()
			MockAPI.return_value.cancelar_factura.assert_not_called()
		self.assertEqual(
			frappe.db.get_value("Factura Fiscal Mexico", self.A_ffm, "status"),
			FiscalStates.PENDIENTE_CANCELACION,
			"sigue pendiente para el próximo tick elegible",
		)

	def test_12_scheduler_cancela_con_guard_real(self):
		"""Integración SIN mockear cancelar_factura: el flujo REAL (incluido el guard de estado)
		permite el retry interno sobre A en PENDIENTE_CANCELACION y converge a CANCELADO.
		Este test es el que faltaba: los mocks previos ocultaban el guard que rompía la recuperación."""
		self._build_A_B()
		self._set_A_pending()
		fake = _FakeCancelClient()
		with patch.object(T, "get_facturapi_client", return_value=fake):
			T.retry_pending_substitution_cancellations()
		self.assertEqual(len(fake.cancel_calls), 1, "debe enviar exactamente 1 DELETE (sin duplicados)")
		self.assertEqual(fake.cancel_calls[0][1], "01", "motivo 01")
		self.assertEqual(fake.cancel_calls[0][2], self.B_uuid, "folio sustitución = UUID_B")
		self.assertEqual(
			frappe.db.get_value("Factura Fiscal Mexico", self.A_ffm, "status"), FiscalStates.CANCELADO
		)
		self.assertEqual(self._ds("Sales Invoice", self.A_si), 2, "SI A documental cancelada")
		self.assertEqual(self._ds("Factura Fiscal Mexico", self.A_ffm), 2, "FFM A documental cancelada")
		self.assertEqual(self._ds("Factura Fiscal Mexico", self.B_ffm), 1, "B permanece timbrada")

	def test_13_scheduler_success_false_transitorio_conserva(self):
		"""cancelar_factura devuelve {success:False} con error transitorio → conservar PENDIENTE."""
		self._build_A_B()
		self._set_A_pending()
		with patch.object(T, "TimbradoAPI") as MockAPI:
			MockAPI.return_value.client.get_invoice.return_value = {"raw_response": {"status": "valid"}}
			MockAPI.return_value.cancelar_factura.return_value = {
				"success": False,
				"error": "Error FacturAPI 404: invoice_not_found",
			}
			T.retry_pending_substitution_cancellations()
		a = frappe.db.get_value(
			"Factura Fiscal Mexico", self.A_ffm, ["status", "fm_sync_status"], as_dict=True
		)
		self.assertEqual(a.status, FiscalStates.PENDIENTE_CANCELACION, "transitorio → sigue pendiente")
		self.assertEqual(a.fm_sync_status, "pending", "no sale del ciclo por un transitorio")

	def test_14_scheduler_success_false_definitivo_sale(self):
		"""cancelar_factura devuelve {success:False} con error definitivo → sale del ciclo (error)."""
		self._build_A_B()
		self._set_A_pending()
		with patch.object(T, "TimbradoAPI") as MockAPI:
			MockAPI.return_value.client.get_invoice.return_value = {"raw_response": {"status": "valid"}}
			MockAPI.return_value.cancelar_factura.return_value = {
				"success": False,
				"error": "Error 422 unprocessable: motivo inválido",
			}
			T.retry_pending_substitution_cancellations()
		self.assertEqual(
			frappe.db.get_value("Factura Fiscal Mexico", self.A_ffm, "fm_sync_status"),
			"error",
			"un {success:False} definitivo NO se interpreta como éxito",
		)

	def test_15_gap3_reconcile_completa_documental_cancelado(self):
		"""Gap 3: A ya CANCELADO fiscal pero docstatus=1 (documental incompleto), origen de sustitución.
		La reconciliación NO reenvía DELETE y completa el documental (SI y FFM → docstatus=2). Idempotente."""
		from facturacion_mexico.facturacion_fiscal.services import ffm_reconciliation as R

		self._build_A_B()
		frappe.db.set_value(
			"Factura Fiscal Mexico",
			self.A_ffm,
			{"status": FiscalStates.CANCELADO, "fm_sync_status": "synced"},
		)
		frappe.db.commit()
		a_fapi = frappe.db.get_value("Factura Fiscal Mexico", self.A_ffm, "facturapi_id")
		client = MagicMock()
		client.get_invoice.return_value = {
			"success": True,
			"status_code": 200,
			"raw_response": {
				"id": a_fapi,
				"uuid": self.A_uuid,
				"status": "canceled",
				"cancellation_status": "accepted",
			},
		}
		mod = "facturacion_mexico.facturacion_fiscal.services.ffm_reconciliation.get_facturapi_client"
		with patch(mod, return_value=client):
			R._reconcile_ffm(self.A_ffm)
		client.cancel_invoice.assert_not_called()
		self.assertEqual(self._ds("Sales Invoice", self.A_si), 2, "SI A documental cancelada")
		self.assertEqual(self._ds("Factura Fiscal Mexico", self.A_ffm), 2, "FFM A documental cancelada")
		# Idempotencia: una segunda reconciliación no cambia nada ni falla.
		with patch(mod, return_value=client):
			R._reconcile_ffm(self.A_ffm)
		self.assertEqual(self._ds("Factura Fiscal Mexico", self.A_ffm), 2)

	def test_9_clasificacion_error_transitorio(self):
		"""Unidad pura: qué errores se consideran transitorios."""
		for msg in [
			"Error FacturAPI 404: invoice_not_found",
			"HTTP 429",
			"500 server",
			"502 bad gateway",
			"Timeout al conectar",
			"Error de conexión con FacturAPI",
		]:
			self.assertTrue(T._is_transient_pac_error(Exception(msg)), msg)
		for msg in ["Error FacturAPI 422: unprocessable", "RFC inválido", "400 bad request"]:
			self.assertFalse(T._is_transient_pac_error(Exception(msg)), msg)
