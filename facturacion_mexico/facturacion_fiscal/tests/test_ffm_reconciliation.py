"""Motor de reconciliación FFM ↔ FacturAPI (Paso 3).

Selector, estados (vía helper único), persistencia (cambio/no-op), errores HTTP, locks y permisos.
El boundary del PAC (get_invoice) se mockea por completo. Cero PAC real.
"""

import types
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.facturacion_fiscal.services import ffm_reconciliation as mod

MOD = "facturacion_mexico.facturacion_fiscal.services.ffm_reconciliation"


def _seed_si():
	si = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": "_Test Company",
			"customer": "_Test Customer",
			"net_total": 100,
			"grand_total": 116,
			"posting_date": frappe.utils.today(),
			"docstatus": 1,
		}
	)
	si.flags.ignore_validate = True
	si.flags.ignore_mandatory = True
	si.flags.ignore_links = True
	si.db_insert()
	frappe.db.commit()
	return si.name


def _seed_ffm(sales_invoice, status, *, facturapi_id="FA-1", uuid="U-1", sync="pending", last_sync=None):
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
			"fm_last_pac_sync": last_sync,
			"docstatus": 1,
		}
	)
	ffm.flags.ignore_validate = True
	ffm.flags.ignore_mandatory = True
	ffm.flags.ignore_links = True
	ffm.db_insert()
	frappe.db.commit()
	return ffm.name


def _ok(raw, status_code=200):
	return {"success": True, "status_code": status_code, "raw_response": {"id": "FA-1", "uuid": "U-1", **raw}}


def _http_error(code):
	exc = frappe.ValidationError(f"Error FacturAPI {code}")
	exc.response = types.SimpleNamespace(status_code=code)
	return exc


class TestFFMReconciliation(IntegrationTestCase):
	def setUp(self):
		self.si_names = []
		self.ffm_names = []
		self.addCleanup(frappe.set_user, "Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		for ffm in self.ffm_names:
			frappe.db.delete("FacturAPI Response Log", {"factura_fiscal_mexico": ffm})
			frappe.db.delete("Factura Fiscal Mexico", {"name": ffm})
		for si in self.si_names:
			frappe.db.delete("Sales Invoice", {"name": si})
		for u in getattr(self, "user_ids", []):
			frappe.db.delete("User", {"name": u})
		frappe.db.commit()

	def _si(self):
		name = _seed_si()
		self.si_names.append(name)
		return name

	def _ffm(self, *args, **kwargs):
		name = _seed_ffm(*args, **kwargs)
		self.ffm_names.append(name)
		return name

	def _client(self, *, get_return=None, get_side_effect=None):
		client = MagicMock()
		if get_side_effect is not None:
			client.get_invoice.side_effect = get_side_effect
		else:
			client.get_invoice.return_value = get_return
		return client

	def _reconciliar(self, ffm_name, *, get_return=None, get_side_effect=None):
		client = self._client(get_return=get_return, get_side_effect=get_side_effect)
		with patch(f"{MOD}.get_facturapi_client", return_value=client) as gfc:
			res = mod._reconcile_ffm(ffm_name)
		return res, client, gfc

	def _status(self, ffm):
		return frappe.db.get_value("Factura Fiscal Mexico", ffm, "status")

	def _sync(self, ffm):
		return frappe.db.get_value("Factura Fiscal Mexico", ffm, "fm_sync_status")

	def _last_sync(self, ffm):
		return frappe.db.get_value("Factura Fiscal Mexico", ffm, "fm_last_pac_sync")

	# ─────────────────────────── Selector ───────────────────────────

	def test_selector_incluye_timbrado_pending(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="pending", facturapi_id="FA-A")
		self.assertIn(ffm, mod._select_candidates())

	def test_selector_incluye_pendiente_cancelacion_synced(self):
		si = self._si()
		ffm = self._ffm(si, "PENDIENTE_CANCELACION", sync="synced", facturapi_id="FA-B")
		self.assertIn(ffm, mod._select_candidates())  # entra aunque esté synced

	def test_selector_excluye_sin_facturapi_id(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="pending", facturapi_id="")
		self.assertNotIn(ffm, mod._select_candidates())

	def test_selector_excluye_timbrado_synced(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="synced", facturapi_id="FA-C")
		self.assertNotIn(ffm, mod._select_candidates())

	def test_selector_prioriza_cancelaciones(self):
		si = self._si()
		pend = self._ffm(si, "TIMBRADO", sync="pending", facturapi_id="FA-A")
		cancel = self._ffm(si, "PENDIENTE_CANCELACION", sync="pending", facturapi_id="FA-B")
		sel = mod._select_candidates()
		self.assertLess(sel.index(cancel), sel.index(pend))

	def test_selector_respeta_limit(self):
		si = self._si()
		for i in range(3):
			self._ffm(si, "TIMBRADO", sync="pending", facturapi_id=f"FA-{i}")
		self.assertEqual(len(mod._select_candidates(limit=2)), 2)

	# ─────────────────────────── Estados ───────────────────────────

	def test_vigente_pending_a_synced(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="pending")
		res, _, _ = self._reconciliar(ffm, get_return=_ok({"status": "valid"}))
		self.assertEqual(res["outcome"], "changed")
		self.assertEqual(self._status(ffm), "TIMBRADO")
		self.assertEqual(self._sync(ffm), "synced")

	def test_cancelacion_pendiente(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="pending")
		self._reconciliar(ffm, get_return=_ok({"status": "valid", "cancellation_status": "pending"}))
		self.assertEqual(self._status(ffm), "PENDIENTE_CANCELACION")

	def test_verifying(self):
		si = self._si()
		ffm = self._ffm(si, "PENDIENTE_CANCELACION", sync="synced")
		self._reconciliar(ffm, get_return=_ok({"status": "valid", "cancellation_status": "verifying"}))
		self.assertEqual(self._status(ffm), "PENDIENTE_CANCELACION")

	def test_canceled(self):
		si = self._si()
		ffm = self._ffm(si, "PENDIENTE_CANCELACION", sync="synced")
		self._reconciliar(ffm, get_return=_ok({"status": "canceled"}))
		self.assertEqual(self._status(ffm), "CANCELADO")

	def test_accepted(self):
		si = self._si()
		ffm = self._ffm(si, "PENDIENTE_CANCELACION", sync="synced")
		self._reconciliar(ffm, get_return=_ok({"cancellation_status": "accepted"}))
		self.assertEqual(self._status(ffm), "CANCELADO")

	def test_rejected(self):
		si = self._si()
		ffm = self._ffm(si, "PENDIENTE_CANCELACION", sync="synced")
		self._reconciliar(ffm, get_return=_ok({"status": "valid", "cancellation_status": "rejected"}))
		self.assertEqual(self._status(ffm), "TIMBRADO")

	def test_expired(self):
		si = self._si()
		ffm = self._ffm(si, "PENDIENTE_CANCELACION", sync="synced")
		self._reconciliar(ffm, get_return=_ok({"status": "valid", "cancellation_status": "expired"}))
		self.assertEqual(self._status(ffm), "TIMBRADO")

	def test_remoto_pending_conserva_estado_y_pending(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="synced")
		res, _, _ = self._reconciliar(ffm, get_return=_ok({"status": "pending"}))
		self.assertEqual(self._status(ffm), "TIMBRADO")  # sin cambio fiscal
		self.assertEqual(self._sync(ffm), "pending")
		self.assertEqual(res["outcome"], "changed")  # synced -> pending sí es cambio

	def test_estado_desconocido_conserva_estado_y_error(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="synced")
		self._reconciliar(ffm, get_return=_ok({"status": "draft"}))
		self.assertEqual(self._status(ffm), "TIMBRADO")  # sin cambio fiscal
		self.assertEqual(self._sync(ffm), "error")

	# ─────────────────────────── Persistencia ───────────────────────────

	def test_cambio_llama_al_writer(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="pending")
		with patch(f"{MOD}._write_pac_response") as wpr:
			self._reconciliar(ffm, get_return=_ok({"status": "valid"}))
		wpr.assert_called_once()

	def test_noop_no_llama_al_writer_y_actualiza_timestamp(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="synced", last_sync=None)
		with patch(f"{MOD}._write_pac_response") as wpr:
			res, _, _ = self._reconciliar(ffm, get_return=_ok({"status": "valid"}))
		wpr.assert_not_called()
		self.assertEqual(res["outcome"], "unchanged")
		self.assertIsNotNone(frappe.db.get_value("Factura Fiscal Mexico", ffm, "fm_last_pac_sync"))

	def test_noop_no_crea_log(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="synced")
		self._reconciliar(ffm, get_return=_ok({"status": "valid"}))
		self.assertEqual(frappe.db.count("FacturAPI Response Log", {"factura_fiscal_mexico": ffm}), 0)

	def test_cambio_solo_sync_llama_al_writer(self):
		# valid -> TIMBRADO (sin cambio fiscal) pero sync pending->synced sí es cambio.
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="pending")
		with patch(f"{MOD}._write_pac_response") as wpr:
			self._reconciliar(ffm, get_return=_ok({"status": "valid"}))
		wpr.assert_called_once()

	def test_noop_valida_identidad_antes_de_timestamp(self):
		# Respuesta que sería no-op (valid) pero con facturapi_id contradictorio: NO debe actualizar
		# timestamp ni quedar unchanged; valida identidad primero -> error.
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="synced", last_sync=None)
		bad = {"success": True, "status_code": 200, "raw_response": {"id": "FA-OTRO", "status": "valid"}}
		res, _, _ = self._reconciliar(ffm, get_return=bad)
		self.assertEqual(res["outcome"], "error")
		self.assertEqual(res.get("error_type"), "correlacion")
		self.assertIsNone(frappe.db.get_value("Factura Fiscal Mexico", ffm, "fm_last_pac_sync"))

	# ─────────── fm_last_pac_sync: solo en GET exitoso y correlacionado ───────────

	_VIEJO = "2020-01-01 00:00:00"

	def _ffm_con_last_sync(self, sync="pending"):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync=sync, last_sync=self._VIEJO)
		return ffm, self._last_sync(ffm)

	def test_last_sync_timeout_no_modifica(self):
		ffm, antes = self._ffm_con_last_sync()
		self._reconciliar(ffm, get_return={"success": False, "status_code": 500})
		self.assertEqual(self._last_sync(ffm), antes)

	def test_last_sync_429_no_modifica(self):
		ffm, antes = self._ffm_con_last_sync()
		self._reconciliar(ffm, get_side_effect=_http_error(429))
		self.assertEqual(self._last_sync(ffm), antes)

	def test_last_sync_5xx_no_modifica(self):
		ffm, antes = self._ffm_con_last_sync()
		self._reconciliar(ffm, get_side_effect=_http_error(503))
		self.assertEqual(self._last_sync(ffm), antes)

	def test_last_sync_404_no_modifica(self):
		ffm, antes = self._ffm_con_last_sync()
		self._reconciliar(ffm, get_side_effect=_http_error(404))
		self.assertEqual(self._last_sync(ffm), antes)

	def test_last_sync_contradiccion_no_modifica(self):
		ffm, antes = self._ffm_con_last_sync()
		bad = {"success": True, "status_code": 200, "raw_response": {"id": "FA-OTRO", "status": "valid"}}
		self._reconciliar(ffm, get_return=bad)
		self.assertEqual(self._last_sync(ffm), antes)

	def test_last_sync_get_exitoso_con_cambio_si_modifica(self):
		# FFM pending + valid -> cambio (pending->synced): fm_last_pac_sync se actualiza.
		ffm, antes = self._ffm_con_last_sync(sync="pending")
		self._reconciliar(ffm, get_return=_ok({"status": "valid"}))
		self.assertNotEqual(self._last_sync(ffm), antes)

	def test_last_sync_get_exitoso_sin_cambio_si_modifica(self):
		# FFM synced + valid -> no-op: igual se actualiza fm_last_pac_sync (consulta exitosa).
		ffm, antes = self._ffm_con_last_sync(sync="synced")
		self._reconciliar(ffm, get_return=_ok({"status": "valid"}))
		self.assertNotEqual(self._last_sync(ffm), antes)

	# ─────────── Persistencia transaccional (commit explícito en ramas sin writer) ───────────
	# Estas pruebas simulan el cierre de la request (botón vía frappe.call, sin auto-commit) con
	# un frappe.db.rollback() posterior: si la rama NO commitea, el rollback revierte la escritura
	# y la aserción falla. Un set_value en la misma transacción es invisible a este defecto.

	def test_noop_persiste_last_sync_tras_rollback(self):
		ffm, antes = self._ffm_con_last_sync(sync="synced")
		res, _, _ = self._reconciliar(ffm, get_return=_ok({"status": "valid"}))
		self.assertEqual(res["outcome"], "unchanged")
		frappe.db.rollback()  # simula fin de request sin auto-commit
		self.assertNotEqual(self._last_sync(ffm), antes)  # sobrevive al rollback => hubo commit

	def test_noop_dos_consultas_consecutivas_avanzan_timestamp(self):
		ffm, antes = self._ffm_con_last_sync(sync="synced")
		self._reconciliar(ffm, get_return=_ok({"status": "valid"}))
		frappe.db.rollback()
		t1 = self._last_sync(ffm)
		self.assertNotEqual(t1, antes)  # primera consulta selló y persistió
		# Segunda consulta, también no-op: vuelve a sellar y persistir.
		self._reconciliar(ffm, get_return=_ok({"status": "valid"}))
		frappe.db.rollback()
		t2 = self._last_sync(ffm)
		self.assertGreaterEqual(t2, t1)

	def test_error_persiste_sync_y_conserva_last_sync_tras_rollback(self):
		# 404 -> error: el override final de _log_and_set_sync (sync=error + last_sync restaurado)
		# corre DESPUÉS del commit del writer y debe commitearse para sobrevivir al fin de request.
		ffm, antes = self._ffm_con_last_sync(sync="pending")
		res, _, _ = self._reconciliar(ffm, get_side_effect=_http_error(404))
		self.assertEqual(res["outcome"], "error")
		frappe.db.rollback()  # simula fin de request sin auto-commit
		self.assertEqual(self._sync(ffm), "error")  # override persistido
		self.assertEqual(self._last_sync(ffm), antes)  # se conservó el valor previo

	def test_noop_no_modifica_sales_invoice(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="synced")
		ds_antes = frappe.db.get_value("Sales Invoice", si, "docstatus")
		self._reconciliar(ffm, get_return=_ok({"status": "valid"}))
		self.assertEqual(frappe.db.get_value("Sales Invoice", si, "docstatus"), ds_antes)

	# ─────────────────────────── Errores y seguridad ───────────────────────────

	def test_timeout_pending(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="pending")
		res, _, _ = self._reconciliar(ffm, get_return={"success": False, "status_code": 500})
		self.assertEqual(res["outcome"], "pending")
		self.assertEqual(self._sync(ffm), "pending")
		self.assertEqual(self._status(ffm), "TIMBRADO")

	def test_429_pending(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="pending")
		res, _, _ = self._reconciliar(ffm, get_side_effect=_http_error(429))
		self.assertEqual(res["outcome"], "pending")
		self.assertEqual(self._sync(ffm), "pending")

	def test_5xx_pending(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="pending")
		res, _, _ = self._reconciliar(ffm, get_side_effect=_http_error(503))
		self.assertEqual(res["outcome"], "pending")
		self.assertEqual(self._sync(ffm), "pending")

	def test_404_error(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="pending")
		res, _, _ = self._reconciliar(ffm, get_side_effect=_http_error(404))
		self.assertEqual(res["outcome"], "error")
		self.assertEqual(self._sync(ffm), "error")
		self.assertEqual(self._status(ffm), "TIMBRADO")

	def test_401_403_error(self):
		si = self._si()
		for code in (401, 403):
			ffm = self._ffm(si, "TIMBRADO", sync="pending", facturapi_id=f"FA-{code}")
			res, _, _ = self._reconciliar(ffm, get_side_effect=_http_error(code))
			self.assertEqual(res["outcome"], "error")
			self.assertEqual(self._sync(ffm), "error")

	def test_contradiccion_id_error_correlacion(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="pending")
		bad = {"success": True, "status_code": 200, "raw_response": {"id": "FA-OTRO", "status": "valid"}}
		res, _, _ = self._reconciliar(ffm, get_return=bad)
		self.assertEqual(res["outcome"], "error")
		self.assertEqual(res.get("error_type"), "correlacion")
		self.assertEqual(self._sync(ffm), "error")
		self.assertEqual(self._status(ffm), "TIMBRADO")  # nunca cambia el estado fiscal

	def test_contradiccion_uuid_error_correlacion(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="pending")
		bad = {
			"success": True,
			"status_code": 200,
			"raw_response": {"id": "FA-1", "uuid": "U-OTRO", "status": "valid"},
		}
		res, _, _ = self._reconciliar(ffm, get_return=bad)
		self.assertEqual(res.get("error_type"), "correlacion")

	def test_cliente_recibe_company(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="pending")
		_, _, gfc = self._reconciliar(ffm, get_return=_ok({"status": "valid"}))
		gfc.assert_called_once_with(company="_Test Company")

	def test_nunca_create_ni_cancel_invoice(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="pending")
		_, client, _ = self._reconciliar(ffm, get_return=_ok({"status": "valid"}))
		client.create_invoice.assert_not_called()
		client.cancel_invoice.assert_not_called()

	def test_lote_un_fallo_no_detiene(self):
		si = self._si()
		a = self._ffm(si, "TIMBRADO", sync="pending", facturapi_id="FA-A")
		self._ffm(si, "TIMBRADO", sync="pending", facturapi_id="FA-B")

		def _side(name):
			if name == a:
				raise RuntimeError("boom")
			return {"ffm": name, "outcome": "unchanged"}

		with (
			patch(f"{MOD}._reconcile_ffm", side_effect=_side),
			patch(f"{MOD}._acquire_lock", return_value=True),
			patch(f"{MOD}._release_lock"),
		):
			summary = mod.run_auto_reconciliation()
		self.assertEqual(summary["processed"], 2)
		self.assertGreaterEqual(summary["errors"], 1)

	def test_lock_global_ocupado_sale_sin_error(self):
		frappe.cache().delete(mod._lock_key(mod.LOCK_BATCH))
		token = mod._acquire_lock(mod.LOCK_BATCH, 60)
		self.assertTrue(token)
		try:
			summary = mod.run_auto_reconciliation()
			self.assertTrue(summary.get("batch_locked"))
			self.assertEqual(summary["selected"], 0)
		finally:
			mod._release_lock(mod.LOCK_BATCH, token)

	# ─────────────────────────── Propiedad del lock ───────────────────────────

	def test_lock_propietario_libera(self):
		key = "test:own:" + frappe.generate_hash()[:8]
		token = mod._acquire_lock(key, 60)
		self.assertTrue(token)
		mod._release_lock(key, token)
		# Liberado: se puede re-adquirir.
		token2 = mod._acquire_lock(key, 60)
		self.assertTrue(token2)
		mod._release_lock(key, token2)

	def test_lock_token_distinto_no_libera(self):
		key = "test:own:" + frappe.generate_hash()[:8]
		token = mod._acquire_lock(key, 60)
		mod._release_lock(key, "token-ajeno")  # NO debe borrar
		self.assertIsNone(mod._acquire_lock(key, 60))  # sigue ocupado por el dueño
		mod._release_lock(key, token)

	def test_lock_expirado_no_borra_el_nuevo(self):
		key = "test:own:" + frappe.generate_hash()[:8]
		token_viejo = mod._acquire_lock(key, 60)
		# Simular: el lock del viejo expiró y OTRO proceso adquirió uno nuevo (mismo key, otro valor).
		frappe.cache().set(mod._lock_key(key), "dueno-nuevo", ex=60)
		# El proceso viejo intenta liberar con su token: NO debe borrar el lock del nuevo.
		mod._release_lock(key, token_viejo)
		valor = frappe.cache().get(mod._lock_key(key))
		valor = valor.decode() if isinstance(valor, bytes) else valor
		self.assertEqual(valor, "dueno-nuevo")
		frappe.cache().delete(mod._lock_key(key))

	def test_lock_liberado_en_finally_con_excepcion(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="pending")
		key = mod.LOCK_FFM_PREFIX + ffm
		frappe.cache().delete(mod._lock_key(key))
		with patch(f"{MOD}.get_facturapi_client", side_effect=RuntimeError("boom")):
			with self.assertRaises(RuntimeError):
				mod._reconcile_ffm(ffm)
		# El finally liberó el lock: se puede re-adquirir.
		token = mod._acquire_lock(key, 60)
		self.assertTrue(token)
		mod._release_lock(key, token)

	def test_lock_ffm_ocupado_devuelve_locked(self):
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="pending")
		key = mod.LOCK_FFM_PREFIX + ffm
		frappe.cache().delete(mod._lock_key(key))
		token = mod._acquire_lock(key, 60)
		self.assertTrue(token)
		try:
			res, _, _ = self._reconciliar(ffm, get_return=_ok({"status": "valid"}))
			self.assertEqual(res["outcome"], "locked")
		finally:
			mod._release_lock(key, token)

	def test_permiso_servidor_aplicado(self):
		self.user_ids = []
		si = self._si()
		ffm = self._ffm(si, "TIMBRADO", sync="pending")
		uid = "recon-noperm-" + frappe.generate_hash()[:8] + "@test.com"
		user = frappe.get_doc(
			{"doctype": "User", "email": uid, "first_name": "NoPerm", "roles": [{"role": "Sales User"}]}
		)
		user.flags.ignore_permissions = True
		user.insert(ignore_permissions=True)
		self.user_ids.append(uid)
		frappe.db.commit()
		frappe.set_user(uid)
		with self.assertRaises(frappe.PermissionError):
			mod.reconcile_ffm(ffm)

	def test_cero_trafico_pac(self):
		g = globals()
		for simbolo in ("FacturapiClient", "create_invoice", "cancel_invoice", "requests"):
			self.assertNotIn(simbolo, g, f"La prueba no debe importar {simbolo}")
