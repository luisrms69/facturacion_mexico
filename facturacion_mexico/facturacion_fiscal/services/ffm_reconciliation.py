"""Motor de reconciliación FFM ↔ FacturAPI (Paso 3).

Consulta FacturAPI por GET (solo lectura) y reconcilia el estado local del FFM con el estado
real del PAC, reutilizando: derive_pac_reconciliation (mapeo único), la correlación estricta del
writer (_resolve_validated_ffm) y write_pac_response (persistencia + Response Log independientes).

Garantías: nunca create_invoice / cancel_invoice; nunca busca otro FFM por Sales Invoice; nunca
cancela ni guarda la Sales Invoice; sin scheduler/hooks/JS/botón en este paso.

Entradas:
    run_auto_reconciliation(limit=None)  -> scheduler / ejecución manual por lote.
    reconcile_ffm(ffm_name)              -> whitelisted (futuro botón), con permiso fiscal.
    _reconcile_ffm(ffm_name)             -> núcleo común (manual y lote ejecutan exactamente esto).
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from facturacion_mexico.config.fiscal_states_config import (
	FiscalStates,
	SyncStates,
	derive_pac_reconciliation,
)
from facturacion_mexico.facturacion_fiscal.api import (
	FiscalCorrelationError,
	PACResponseWriter,
	_extract_reconciliation_states,
)
from facturacion_mexico.facturacion_fiscal.api_client import get_facturapi_client
from facturacion_mexico.facturacion_fiscal.cancellation_state import (
	apply_cancellation_state,
	derive_cancellation_reconciliation,
	extract_canceled_at,
)


def _write_pac_response(
	sales_invoice_name, request_data, response_data, factura_fiscal_name, *, skip_state_persist=False
):
	"""Persistir vía el writer (método, acepta dicts) con operation_type='reconciliacion'.

	Se usa el método del writer y NO la función whitelisted pública (que exige str por type-hints).
	`skip_state_persist=True` cuando se reconcilia una CANCELACIÓN: el writer crea el Response Log
	pero NO persiste el estado fiscal (lo aplica apply_cancellation_state).
	"""
	return PACResponseWriter().write_pac_response(
		sales_invoice_name,
		request_data,
		response_data,
		"reconciliacion",
		factura_fiscal_name=factura_fiscal_name,
		skip_state_persist=skip_state_persist,
	)


BATCH_SIZE = 100

# Locks de cache (Redis), no bloqueantes, con TTL. Liberados siempre en finally.
LOCK_BATCH = "facturacion_mexico:ffm_auto_reconciliation"
LOCK_BATCH_TTL = 2 * 60 * 60  # 2 horas
LOCK_FFM_PREFIX = "facturacion_mexico:ffm_reconciliation:"
LOCK_FFM_TTL = 5 * 60  # 5 minutos

# Roles autorizados a cancelar/reconciliar fiscalmente (idénticos a cancel_ffm_keep_si — PR #197).
FISCAL_ROLES = ("System Manager", "Facturacion Mexico System Manager", "Facturacion Mexico Manager")


def _lock_key(key: str) -> str:
	"""Namespacing por sitio para evitar colisiones en benches multi-sitio."""
	return f"{frappe.local.site}:{key}"


# Compare-and-delete atómico: solo borra la clave si su valor sigue siendo el token del dueño.
# Evita que un proceso cuyo lock expiró borre el lock que otro proceso ya adquirió.
_RELEASE_LUA = (
	"if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"
)


def _acquire_lock(key: str, ttl: int) -> str | None:
	"""Adquisición atómica no bloqueante (Redis SET NX EX). Devuelve el token si se obtuvo el lock,
	o None si ya estaba ocupado. El token identifica al dueño para una liberación segura."""
	token = frappe.generate_hash(length=16)
	# Lock distribuido atómico (SET NX EX): set_value/get_value no soportan NX/TTL. La multitenancia
	# queda cubierta por _lock_key (namespace por frappe.local.site).
	if frappe.cache().set(_lock_key(key), token, nx=True, ex=ttl):  # nosemgrep
		return token
	return None


def _release_lock(key: str, token: str | None) -> None:
	"""Libera el lock SOLO si su valor actual coincide con `token` (compare-and-delete atómico)."""
	if not token:
		return
	frappe.cache().eval(_RELEASE_LUA, 1, _lock_key(key), token)


def _classify_http_error(status_code: int) -> str:
	"""Transitorio (reintentable) -> pending; permanente -> error."""
	if status_code == 429 or status_code >= 500:
		return SyncStates.PENDING
	return SyncStates.ERROR  # 401/403/404 y demás 4xx


def _log_and_set_sync(ffm, response_data: dict, sync_status: str) -> None:
	"""Registra el GET de error (Response Log, vía writer) y fija fm_sync_status, CONSERVANDO
	fm_last_pac_sync.

	Un error de consulta (timeout/4xx/5xx) NO es una consulta exitosa y correlacionada: fm_last_pac_sync
	debe quedar con su valor anterior. Como write_pac_response (por M1) sella fm_last_pac_sync, se
	captura el valor previo y se restaura. El estado fiscal NO cambia (el branch 'reconciliacion'
	del writer devuelve None salvo 2xx).
	"""
	prev_last_sync = ffm.get("fm_last_pac_sync")
	_write_pac_response(
		ffm.sales_invoice or "",
		{"action": "reconciliacion", "facturapi_id": ffm.facturapi_id},
		response_data,
		ffm.name,
	)
	# Se impone la clasificación de reconciliación (p. ej. 404 -> error, no 'synced') y se RESTAURA
	# fm_last_pac_sync al valor previo (el error no cuenta como última consulta exitosa).
	frappe.db.set_value(
		"Factura Fiscal Mexico",
		ffm.name,
		{"fm_sync_status": sync_status, "fm_last_pac_sync": prev_last_sync},
	)
	# Estas escrituras finales corren DESPUÉS del commit del writer; sin un commit propio se
	# descartan al cerrar la request (p. ej. botón vía frappe.call). Un solo commit al final.
	frappe.db.commit()  # nosemgrep


def _reconcile_ffm(ffm_name: str) -> dict:
	"""Núcleo: consulta el PAC para UN FFM y reconcilia. No hace búsquedas alternativas."""
	ffm = frappe.get_doc("Factura Fiscal Mexico", ffm_name)

	lock = LOCK_FFM_PREFIX + ffm_name
	token = _acquire_lock(lock, LOCK_FFM_TTL)
	if not token:
		return {"ffm": ffm_name, "outcome": "locked"}

	try:
		if not ffm.facturapi_id:
			return {"ffm": ffm_name, "outcome": "skipped", "reason": "sin_facturapi_id"}

		# Cliente de la compañía del FFM (puede lanzar si la company no tiene credenciales).
		client = get_facturapi_client(company=ffm.company)

		# Única operación contra el PAC: GET por facturapi_id.
		try:
			response = client.get_invoice(ffm.facturapi_id)
		except frappe.ValidationError as exc:
			# FacturAPIClient adjunta la respuesta HTTP a la excepción (.response.status_code).
			status_code = getattr(getattr(exc, "response", None), "status_code", None) or 500
			sync = _classify_http_error(status_code)
			_log_and_set_sync(
				ffm,
				{"success": False, "status_code": status_code, "error": str(exc), "raw_response": None},
				sync,
			)
			return {"ffm": ffm_name, "outcome": "pending" if sync == SyncStates.PENDING else "error"}

		# Timeout / conexión: el cliente devuelve success=False (transitorio).
		if not (isinstance(response, dict) and response.get("success")):
			status_code = (response or {}).get("status_code", 500) if isinstance(response, dict) else 500
			_log_and_set_sync(
				ffm, response if isinstance(response, dict) else {"success": False}, SyncStates.PENDING
			)
			return {"ffm": ffm_name, "outcome": "pending"}

		# Respuesta exitosa: validar correlación ANTES de decidir si hay cambios (reutiliza la
		# correlación estricta del writer; no se duplican sus reglas).
		try:
			PACResponseWriter()._resolve_validated_ffm(
				ffm.name, ffm.sales_invoice or "", response, "reconciliacion"
			)
		except FiscalCorrelationError:
			# Identidad contradictoria: no se toca el estado fiscal; se marca error. La alerta
			# crítica ya quedó registrada por _resolve_validated_ffm. Se preserva el tipo de error.
			frappe.db.set_value("Factura Fiscal Mexico", ffm.name, "fm_sync_status", SyncStates.ERROR)
			frappe.db.commit()  # nosemgrep
			return {"ffm": ffm_name, "outcome": "error", "error_type": "correlacion"}

		remote_status, cancellation_status = _extract_reconciliation_states(response)

		# CORR-1: decidir EXPLÍCITAMENTE si esta reconciliación corresponde a una cancelación.
		# No se deduce solo del estado derivado: una FFM ya CANCELADO no debe degradarse por una
		# respuesta `valid` sin estado de cancelación.
		_rs = (remote_status or "").strip().lower()
		_cs = (cancellation_status or "").strip().lower()
		is_cancellation = (
			ffm.status in (FiscalStates.PENDIENTE_CANCELACION, FiscalStates.CANCELADO)
			or _rs == "canceled"
			or _cs in ("pending", "verifying", "accepted", "rejected", "expired")
		)

		if is_cancellation:
			fiscal_status, sync_status = derive_cancellation_reconciliation(
				remote_status, cancellation_status
			)
		else:
			fiscal_status, sync_status = derive_pac_reconciliation(remote_status, cancellation_status)

		status_changed = fiscal_status is not None and fiscal_status != ffm.status
		sync_changed = sync_status != ffm.fm_sync_status

		# Cancelación: aplicar SIEMPRE (idempotente) para REPARAR campos incompletos (reason/date/
		# snapshot SI) de una FFM ya terminal, aunque status/sync no cambien. La correlación estricta
		# ya se validó arriba (_resolve_validated_ffm). apply devuelve si escribió algún campo.
		# NO altera la selección de candidatos asíncronos (_select_candidates) — solo cómo se aplica.
		repaired = False
		if is_cancellation and fiscal_status is not None:
			# CANCELADO: usar el `canceled_at` REAL del PAC cuando exista; observación solo si no hay.
			_cdate = (
				(extract_canceled_at(response) or now_datetime())
				if fiscal_status == FiscalStates.CANCELADO
				else None
			)
			repaired = apply_cancellation_state(
				ffm.name, fiscal_status, sync_status=sync_status, cancellation_date=_cdate
			)

		if status_changed or sync_changed or repaired:
			# El writer crea el Response Log correlacionado. En cancelación NO persiste el estado
			# fiscal (skip_state_persist): la escritura autoritativa es apply_cancellation_state.
			_write_pac_response(
				ffm.sales_invoice or "",
				{"action": "reconciliacion", "facturapi_id": ffm.facturapi_id},
				response,
				ffm.name,
				skip_state_persist=is_cancellation,
			)
			if is_cancellation and fiscal_status is None and sync_changed:
				# pending/no concluyente pero el sync cambió (apply no corre con fiscal_status=None).
				frappe.db.set_value("Factura Fiscal Mexico", ffm.name, "fm_sync_status", sync_status)
			return {
				"ffm": ffm_name,
				"outcome": "changed",
				"status": fiscal_status if fiscal_status is not None else ffm.status,
				"sync": sync_status,
			}

		# Sin cambios: NO se crea Response Log; solo se sella la última consulta exitosa.
		# Commit explícito: este write no pasa por el writer (que sí commitea) y se descartaría
		# al cerrar la request (botón vía frappe.call) sin él.
		frappe.db.set_value("Factura Fiscal Mexico", ffm.name, "fm_last_pac_sync", now_datetime())
		frappe.db.commit()  # nosemgrep
		return {"ffm": ffm_name, "outcome": "unchanged"}
	finally:
		_release_lock(lock, token)


@frappe.whitelist()
def reconcile_ffm(ffm_name: str) -> dict:
	"""Reconciliación manual de un FFM (futuro botón). Aplica el permiso fiscal de cancelación."""
	if not frappe.db.exists("Factura Fiscal Mexico", ffm_name):
		frappe.throw(_("El documento fiscal {0} no existe.").format(ffm_name))
	# Mismo permiso que cancel_ffm_keep_si (PR #197): no se inventan roles nuevos.
	frappe.only_for(FISCAL_ROLES)
	return _reconcile_ffm(ffm_name)


def _select_candidates(limit=None) -> list[str]:
	"""FFM con facturapi_id y (pending o PENDIENTE_CANCELACION). Prioridad: cancelación, pending,
	fm_last_pac_sync más antiguo (NULL primero), name.

	Se usa SQL de SOLO LECTURA porque el ORDER BY con CASE (prioridad por estado) no es expresable
	en frappe.get_all (valida nombres de campo). No modifica datos.
	"""
	return frappe.db.sql(
		"""
		SELECT name FROM `tabFactura Fiscal Mexico`
		WHERE facturapi_id IS NOT NULL AND facturapi_id != ''
		  AND (fm_sync_status = 'pending' OR status = 'PENDIENTE_CANCELACION')
		ORDER BY
		  CASE WHEN status = 'PENDIENTE_CANCELACION' THEN 0 ELSE 1 END ASC,
		  CASE WHEN fm_sync_status = 'pending' THEN 0 ELSE 1 END ASC,
		  fm_last_pac_sync ASC, name ASC
		LIMIT %(limit)s
		""",
		{"limit": limit or BATCH_SIZE},
		pluck="name",
	)


def run_auto_reconciliation(limit=None) -> dict:
	"""Lote automático: lock global, selección, procesamiento aislado por FFM, resumen."""
	token = _acquire_lock(LOCK_BATCH, LOCK_BATCH_TTL)
	if not token:
		return {
			"selected": 0,
			"processed": 0,
			"changed": 0,
			"unchanged": 0,
			"pending": 0,
			"errors": 0,
			"locked": 1,
			"batch_locked": True,
		}

	summary = {
		"selected": 0,
		"processed": 0,
		"changed": 0,
		"unchanged": 0,
		"pending": 0,
		"errors": 0,
		"locked": 0,
	}
	try:
		candidates = _select_candidates(limit=limit)
		summary["selected"] = len(candidates)
		for name in candidates:
			try:
				res = _reconcile_ffm(name)
				outcome = res.get("outcome")
			except Exception:
				frappe.log_error(
					f"Reconciliación falló para FFM {name}", "FFM Reconciliation"
				)  # un fallo no detiene el lote
				outcome = "error"
			summary["processed"] += 1
			if outcome == "changed":
				summary["changed"] += 1
			elif outcome == "unchanged":
				summary["unchanged"] += 1
			elif outcome == "pending":
				summary["pending"] += 1
			elif outcome == "locked":
				summary["locked"] += 1
			else:  # error / skipped
				summary["errors"] += 1
	finally:
		_release_lock(LOCK_BATCH, token)

	return summary
