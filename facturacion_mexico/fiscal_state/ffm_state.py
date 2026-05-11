"""
fiscal_state/ffm_state.py

Calcula el estado fiscal de una Factura Fiscal Mexico (FFM) de forma centralizada.
Read-only — no modifica ningún documento ni comportamiento existente.

Propósito inicial: auditoría y comparación contra la lógica actual de UI.
"""

import frappe
from frappe import _

_TIMBRADO = "TIMBRADO"
_CANCELADO = "CANCELADO"
_PENDIENTE_CANCELACION = "PENDIENTE_CANCELACION"
_BORRADOR = "BORRADOR"
_ERROR = "ERROR"

_TIMBRABLE_STATUSES = {_BORRADOR, _ERROR, ""}
_CANCELABLE_STATUSES = {_TIMBRADO}
_FINAL_STATUSES = {_CANCELADO}


def get_ffm_fiscal_state(ffm_name: str) -> dict:
	"""
	Retorna el estado fiscal completo de una Factura Fiscal Mexico.

	Returns:
		dict con facts, actions y messages.
	"""
	ffm = frappe.get_doc("Factura Fiscal Mexico", ffm_name)

	facts = _compute_facts(ffm)
	actions = _compute_actions(facts)
	messages = _compute_messages(facts)

	return {
		"doctype": "Factura Fiscal Mexico",
		"name": ffm_name,
		"facts": facts,
		"actions": actions,
		"messages": messages,
	}


# ── Facts ──────────────────────────────────────────────────────────────────


def _compute_facts(ffm) -> dict:
	"""Observa el estado real del documento y sus vínculos. Solo lee."""

	status = (ffm.get("status") or "").upper()
	sync_status = (ffm.get("fm_sync_status") or "").lower()
	tipo_comprobante = ffm.get("fm_tipo_comprobante") or ""
	payment_method = ffm.get("fm_payment_method_sat") or ""

	facts = {
		# ── Estado documental ──────────────────────────────────────────────
		"is_draft": ffm.docstatus == 0,
		"is_submitted": ffm.docstatus == 1,
		"is_cancelled": ffm.docstatus == 2,
		# ── Estado fiscal ─────────────────────────────────────────────────
		"status": status,
		"is_timbrado": status == _TIMBRADO,
		"is_cancelado": status == _CANCELADO,
		"is_pendiente_cancelacion": status == _PENDIENTE_CANCELACION,
		"is_borrador": status in (_BORRADOR, ""),
		"is_error": status == _ERROR,
		"sync_pending": sync_status == "pending",
		# ── CFDI ──────────────────────────────────────────────────────────
		"has_uuid": bool(ffm.get("fm_uuid")),
		"has_facturapi_id": bool(ffm.get("facturapi_id")),
		"tipo_comprobante": tipo_comprobante,
		"is_ingreso": tipo_comprobante.startswith("I"),
		"is_egreso": tipo_comprobante.startswith("E"),
		"payment_method": payment_method,
		"is_ppd": payment_method == "PPD",
		"is_pue": payment_method == "PUE",
		# ── Archivos ──────────────────────────────────────────────────────
		"has_xml": bool(ffm.get("fm_xml_url")),
		"has_pdf": bool(ffm.get("fm_pdf_url")),
		# ── Cancelación ───────────────────────────────────────────────────
		"motivo_cancelacion": ffm.get("fm_motivo_cancelacion") or "",
		"cancellation_reason": ffm.get("cancellation_reason") or "",
		# ── Sales Invoice vinculada ───────────────────────────────────────
		"has_sales_invoice": bool(ffm.get("sales_invoice")),
		"sales_invoice": ffm.get("sales_invoice") or "",
	}

	# ── Payment Entry activo que bloquea cancelación ─────────────────────
	has_active_pe = False
	if facts["has_sales_invoice"]:
		pe_refs = frappe.get_all(
			"Payment Entry Reference",
			filters={"reference_doctype": "Sales Invoice", "reference_name": facts["sales_invoice"]},
			fields=["parent"],
		)
		if pe_refs:
			pe_names = [r.get("parent") for r in pe_refs if r.get("parent")]
			if pe_names:
				submitted_pe = frappe.get_all(
					"Payment Entry",
					filters={"name": ["in", pe_names], "docstatus": 1},
					fields=["name"],
					limit=1,
				)
				has_active_pe = bool(submitted_pe)

	facts["has_active_payment_entry"] = has_active_pe

	# ── Tax system (para validar si puede timbrar) ────────────────────────
	tax_system = ffm.get("fm_tax_system") or ""
	facts["tax_system_valid"] = bool(tax_system) and not (tax_system.startswith(("⚠️", "❌")))

	return facts


# ── Actions ────────────────────────────────────────────────────────────────


def _compute_actions(facts: dict) -> dict:
	"""Deriva acciones posibles desde facts. No consulta BD."""
	status = facts["status"]
	is_submitted = facts["is_submitted"]

	can_stamp = (
		is_submitted
		and status in _TIMBRABLE_STATUSES
		and facts["tax_system_valid"]
		and not facts["sync_pending"]
	)

	can_cancel = (
		is_submitted
		and status in _CANCELABLE_STATUSES
		and facts["has_uuid"]
		and not facts["has_active_payment_entry"]
		and not facts["sync_pending"]
	)

	can_retry_cancel = is_submitted and facts["is_pendiente_cancelacion"] and not facts["sync_pending"]

	return {
		"can_stamp": can_stamp,
		"can_cancel": can_cancel,
		"can_retry_cancel": can_retry_cancel,
		# Descargar requiere UUID + facturapi_id — el API obtiene el archivo de FacturAPI.
		# Los archivos adjuntos (fm_xml_url/fm_pdf_url) son opcionales y pueden no estar seteados.
		"can_download_xml": facts["has_uuid"] and facts["has_facturapi_id"],
		"can_download_pdf": facts["has_uuid"] and facts["has_facturapi_id"],
		"can_send_email": facts["has_uuid"] and facts["has_facturapi_id"],
		"can_view_sales_invoice": facts["has_sales_invoice"],
	}


# ── Messages ───────────────────────────────────────────────────────────────


def _compute_messages(facts: dict) -> list:
	"""Genera mensajes para la UI basados en facts."""
	msgs = []

	if not facts["is_submitted"]:
		return msgs

	status = facts["status"]

	if facts["sync_pending"]:
		msgs.append(
			{
				"code": "SYNC_PENDING",
				"level": "info",
				"text": _("Operación en progreso — espera a que complete."),
			}
		)
		return msgs

	# ERROR tiene prioridad — muestra error de timbrado aunque sea "retriable"
	if status == _ERROR:
		msgs.append(
			{
				"code": "STAMP_ERROR",
				"level": "error",
				"text": _("Error en el timbrado. Revisa los datos y reintenta."),
			}
		)

	elif status in (_BORRADOR, ""):
		if not facts["tax_system_valid"]:
			msgs.append(
				{
					"code": "TAX_SYSTEM_INVALID",
					"level": "error",
					"text": _("Configuración fiscal incompleta — no se puede timbrar."),
				}
			)
		else:
			msgs.append(
				{
					"code": "PENDING_STAMP",
					"level": "warning",
					"text": _("CFDI pendiente de timbrar."),
				}
			)

	elif status == _TIMBRADO:
		msgs.append(
			{
				"code": "CFDI_STAMPED",
				"level": "success",
				"text": _("CFDI timbrado correctamente."),
			}
		)
		if facts["has_uuid"] and not (facts["has_xml"] or facts["has_pdf"]):
			msgs.append(
				{
					"code": "FILES_MISSING",
					"level": "info",
					"text": _("XML/PDF pendientes de descargar."),
				}
			)
		if facts["has_active_payment_entry"]:
			msgs.append(
				{
					"code": "CANCEL_BLOCKED_ACTIVE_PE",
					"level": "warning",
					"text": _("No se puede cancelar: existe un pago activo. Cancela primero el pago."),
				}
			)

	elif status == _PENDIENTE_CANCELACION:
		msgs.append(
			{
				"code": "CANCELLATION_PENDING",
				"level": "warning",
				"text": _("Cancelación pendiente de confirmación del SAT."),
			}
		)

	elif status == _CANCELADO:
		msgs.append(
			{
				"code": "CFDI_CANCELLED",
				"level": "warning",
				"text": _("CFDI cancelado ante el SAT."),
			}
		)

	return msgs
