# Copyright (c) 2026, Buzola and contributors
# For license information, please see license.txt
"""Operación autoritativa única para aplicar el estado de cancelación de una FFM.

Centraliza la transición de cancelación (PENDIENTE_CANCELACION / CANCELADO / TIMBRADO) para que
TODOS los caminos (síncrono, revisión manual, motor de reconciliación y cascada de sustitución)
dejen consistentes: FFM.status, fm_motivo_cancelacion, cancellation_reason, cancellation_date,
fm_sync_status y SI.fm_fiscal_status.

No crea Response Log, no llama al PAC, no cancela DocTypes, no agrega campos ni DocTypes.
"""

from datetime import datetime, timezone

import frappe
from frappe.utils import convert_utc_to_system_timezone, now_datetime

from facturacion_mexico.config.fiscal_states_config import FiscalStates, SyncStates


def extract_canceled_at(response):
	"""Devuelve el timestamp REAL de cancelación del PAC (`canceled_at`) normalizado a la zona horaria
	del sitio, o None si no hay un timestamp válido.

	FacturAPI entrega el instante en UTC ISO-8601 (con sufijo 'Z'), p. ej. `2026-06-23T15:51:42.045Z`.
	Se interpreta como UTC (no se descarta la zona) y se convierte al MISMO instante en la zona del
	sitio, devolviendo un datetime naive apto para el campo Datetime.
	"""
	if not isinstance(response, dict):
		return None
	raw = response.get("raw_response")
	raw = raw if isinstance(raw, dict) else response
	cancellation = raw.get("cancellation")
	ts = cancellation.get("canceled_at") if isinstance(cancellation, dict) else None
	ts = ts or raw.get("canceled_at")
	if not ts or not isinstance(ts, str):
		return None
	try:
		# 'Z' -> offset explícito (+00:00): se interpreta como UTC, no se elimina la zona.
		parsed = datetime.fromisoformat(ts.strip().replace("Z", "+00:00"))
	except (ValueError, TypeError):
		return None
	# Llevar a UTC naive y convertir al mismo instante en la zona del sitio.
	if parsed.tzinfo is not None:
		parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
	local = convert_utc_to_system_timezone(parsed)
	return local.replace(tzinfo=None) if getattr(local, "tzinfo", None) else local


def derive_cancellation_reconciliation(remote_status, cancellation_status):
	"""Criterio ACOTADO y fail-closed para cancelación (no modifica `derive_pac_reconciliation`).

	A diferencia del helper global, `accepted` AISLADO (sin `status=canceled`) NO es terminal:
	el HTTP/aceptación del receptor no confirma la cancelación fiscal ante el SAT.

	Returns:
	    tuple (fiscal_status | None, fm_sync_status):
	    - canceled                          -> (CANCELADO, synced)          # único terminal
	    - valid + pending/verifying/accepted-> (PENDIENTE_CANCELACION, synced)
	    - valid + rejected/expired          -> (TIMBRADO, synced)           # cancelación no procedió
	    - valid + none/""                   -> (TIMBRADO, synced)
	    - pending                           -> (None, pending)
	    - desconocido/incoherente           -> (None, error)  # nunca CANCELADO
	"""
	rs = (remote_status or "").strip().lower()
	cs = (cancellation_status or "").strip().lower()

	if rs == "canceled":
		return FiscalStates.CANCELADO, SyncStates.SYNCED

	if rs == "valid":
		if cs in ("pending", "verifying", "accepted"):
			return FiscalStates.PENDIENTE_CANCELACION, SyncStates.SYNCED
		if cs in ("rejected", "expired"):
			return FiscalStates.TIMBRADO, SyncStates.SYNCED
		if cs in ("", "none"):
			return FiscalStates.TIMBRADO, SyncStates.SYNCED
		return None, SyncStates.ERROR

	if rs == "pending":
		return None, SyncStates.PENDING

	return None, SyncStates.ERROR


def _reason_from_motive(motive: str | None) -> str:
	"""Derivar el texto del Select `cancellation_reason` desde el código de motivo solicitado.

	Se deriva por prefijo contra las opciones reales del DocType (evita drift con descripciones).
	Si no hay motivo o no matchea ninguna opción, devuelve "" (fail-soft: no bloquea la transición).
	"""
	motive = (motive or "").strip()
	if not motive:
		return ""
	field = frappe.get_meta("Factura Fiscal Mexico").get_field("cancellation_reason")
	opts = [(o or "").strip() for o in (field.options or "").split("\n") if (o or "").strip()]
	for o in opts:
		if o.startswith((f"{motive} -", f"{motive} ")):
			return o
	return ""


def apply_cancellation_state(ffm, fiscal_status, *, sync_status, cancellation_date=None) -> bool:
	"""Única escritura autoritativa del estado de cancelación. Idempotente y monotónica.

	Returns:
	    bool: True si escribió ALGÚN campo (FFM o snapshot SI); False si no cambió nada
	    (idempotencia / monotonicidad). Lo usa el motor para decidir si crear Response Log.

	Args:
	    ffm: doc o name de Factura Fiscal Mexico.
	    fiscal_status: PENDIENTE_CANCELACION | CANCELADO | TIMBRADO.
	    sync_status: fm_sync_status ya derivado (no se asume "synced").
	    cancellation_date: fecha del PAC (canceled_at) cuando aplique; None en pendiente/timbrado.

	Reglas:
	    - Relee SIEMPRE la FFM desde BD (el objeto en memoria puede estar desactualizado).
	    - Monotonicidad: una FFM CANCELADO no se degrada a PENDIENTE/TIMBRADO por una respuesta vieja.
	      CANCELADO -> CANCELADO SÍ ejecuta la parte reparadora (completa reason/date/sync/SI faltantes).
	    - fm_motivo_cancelacion se CONSERVA (nunca se pone None aquí).
	    - cancellation_date idempotente: una fecha existente nunca se sobrescribe.
	    - SI.fm_fiscal_status solo si SI.fm_factura_fiscal_mx == ffm.name.
	"""
	ffm_name = ffm if isinstance(ffm, str) else ffm.name
	cur = frappe.db.get_value(
		"Factura Fiscal Mexico",
		ffm_name,
		[
			"status",
			"fm_motivo_cancelacion",
			"cancellation_date",
			"cancellation_reason",
			"fm_sync_status",
			"sales_invoice",
		],
		as_dict=True,
	)
	if not cur:
		return False

	# Monotonicidad: no degradar un CANCELADO; pero CANCELADO->CANCELADO repara.
	if cur.status == FiscalStates.CANCELADO and fiscal_status != FiscalStates.CANCELADO:
		return False

	reason = _reason_from_motive(cur.fm_motivo_cancelacion)

	target = {
		"status": fiscal_status,
		"cancellation_reason": reason,
		"fm_sync_status": sync_status,
	}
	if fiscal_status == FiscalStates.CANCELADO:
		# Fecha existente NUNCA se sobrescribe (idempotencia); luego canceled_at; luego observación.
		target["cancellation_date"] = cur.cancellation_date or cancellation_date or now_datetime()
	else:
		target["cancellation_date"] = None

	wrote = False
	changed = {k: v for k, v in target.items() if cur.get(k) != v}
	if changed:
		frappe.db.set_value("Factura Fiscal Mexico", ffm_name, changed)
		wrote = True

	# Snapshot de la SI solo si esta FFM es la activa de esa SI.
	si = cur.sales_invoice
	if si and frappe.db.get_value("Sales Invoice", si, "fm_factura_fiscal_mx") == ffm_name:
		if frappe.db.get_value("Sales Invoice", si, "fm_fiscal_status") != fiscal_status:
			frappe.db.set_value("Sales Invoice", si, "fm_fiscal_status", fiscal_status)
			wrote = True

	return wrote
