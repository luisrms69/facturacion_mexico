"""
fiscal_state/complemento_state.py

Calcula el estado fiscal de un Complemento Pago MX de forma centralizada.
Read-only — no modifica ningún documento ni comportamiento existente.

Propósito inicial: auditoría y comparación contra la lógica actual de UI.
"""

import frappe
from frappe import _

_TIMBRADO = "Timbrado"
_CANCELADO = "Cancelado"
_PENDIENTE = "Pendiente"
_ERROR = "Error"
_PENDIENTE_CANCELACION = "Pendiente Cancelación"

_TIMBRABLE_STATUSES = {_PENDIENTE, _ERROR}


def get_complemento_fiscal_state(comp_name: str) -> dict:
	"""
	Retorna el estado fiscal completo de un Complemento Pago MX.

	Returns:
		dict con facts, actions y messages.
	"""
	comp = frappe.get_doc("Complemento Pago MX", comp_name)

	facts = _compute_facts(comp)
	actions = _compute_actions(facts)
	messages = _compute_messages(facts)

	return {
		"doctype": "Complemento Pago MX",
		"name": comp_name,
		"facts": facts,
		"actions": actions,
		"messages": messages,
	}


# ── Facts ──────────────────────────────────────────────────────────────────


def _compute_facts(comp) -> dict:
	"""Observa el estado real del documento y sus vínculos. Solo lee."""

	status = comp.get("status") or _PENDIENTE

	facts = {
		# ── Estado documental ──────────────────────────────────────────────
		"is_draft": comp.docstatus == 0,
		"is_submitted": comp.docstatus == 1,
		"is_cancelled": comp.docstatus == 2,
		# ── Estado fiscal ─────────────────────────────────────────────────
		"status": status,
		"is_timbrado": status == _TIMBRADO,
		"is_cancelado": status == _CANCELADO,
		"is_pendiente": status == _PENDIENTE,
		"is_error": status == _ERROR,
		"is_pendiente_cancelacion": status == _PENDIENTE_CANCELACION,
		# ── UUID y archivos ───────────────────────────────────────────────
		"has_uuid": bool(comp.get("uuid_sat")),
		"has_facturapi_id": bool(comp.get("facturapi_id")),
		"has_xml": bool(comp.get("xml_file")),
		"has_pdf": bool(comp.get("pdf_file")),
		# ── Vínculo con Payment Entry ─────────────────────────────────────
		"has_payment_entry": bool(comp.get("payment_entry")),
		"payment_entry": comp.get("payment_entry") or "",
		# ── Datos del pago ────────────────────────────────────────────────
		"monto_p": float(comp.get("monto_p") or 0),
		"moneda_p": comp.get("moneda_p") or "",
		"forma_pago_p": comp.get("forma_pago_p") or "",
		# ── Documentos relacionados ───────────────────────────────────────
		"has_documentos_relacionados": bool(comp.get("documentos_relacionados")),
	}

	# ── PE activo o cancelado (para contexto) ────────────────────────────
	pe_submitted = False
	pe_cancelled = False

	if facts["has_payment_entry"]:
		pe_data = frappe.get_all(
			"Payment Entry",
			filters={"name": facts["payment_entry"]},
			fields=["docstatus"],
			limit=1,
		)
		if pe_data:
			ds = pe_data[0].get("docstatus")
			pe_submitted = ds == 1
			pe_cancelled = ds == 2

	facts["pe_submitted"] = pe_submitted
	facts["pe_cancelled"] = pe_cancelled

	return facts


# ── Actions ────────────────────────────────────────────────────────────────


def _compute_actions(facts: dict) -> dict:
	"""Deriva acciones posibles desde facts. No consulta BD."""

	can_stamp = facts["is_draft"] and facts["status"] in _TIMBRABLE_STATUSES

	can_cancel = facts["is_submitted"] and facts["is_timbrado"] and facts["has_uuid"]

	can_retry_cancel = facts["is_submitted"] and facts["is_pendiente_cancelacion"]

	return {
		"can_stamp": can_stamp,
		"can_cancel": can_cancel,
		"can_retry_cancel": can_retry_cancel,
		# has_facturapi_id requerido: descargar_archivos_complemento lanza si falta
		"can_download_xml": facts["has_uuid"] and facts["has_facturapi_id"],
		"can_download_pdf": facts["has_uuid"] and facts["has_facturapi_id"],
		"can_view_payment_entry": facts["has_payment_entry"],
	}


# ── Messages ───────────────────────────────────────────────────────────────


def _compute_messages(facts: dict) -> list:
	"""Genera mensajes para la UI basados en facts."""
	msgs = []

	if facts["is_error"]:
		msgs.append(
			{
				"code": "STAMP_ERROR",
				"level": "error",
				"text": _("Error al timbrar el complemento. Revisa los datos y reintenta."),
			}
		)
		return msgs

	if facts["is_pendiente"]:
		if not facts["has_documentos_relacionados"]:
			msgs.append(
				{
					"code": "MISSING_RELATED_DOCS",
					"level": "warning",
					"text": _("Faltan documentos relacionados — completa la configuración antes de timbrar."),
				}
			)
		else:
			msgs.append(
				{
					"code": "PENDING_STAMP",
					"level": "warning",
					"text": _("Complemento pendiente de timbrar."),
				}
			)
		return msgs

	if facts["is_timbrado"]:
		msgs.append(
			{
				"code": "CFDI_STAMPED",
				"level": "success",
				"text": _("Complemento de pago timbrado correctamente."),
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
		if facts["pe_cancelled"]:
			msgs.append(
				{
					"code": "PE_CANCELLED",
					"level": "warning",
					"text": _("El Payment Entry origen fue cancelado."),
				}
			)
		return msgs

	if facts["is_pendiente_cancelacion"]:
		msgs.append(
			{
				"code": "CANCELLATION_PENDING",
				"level": "warning",
				"text": _("Cancelación pendiente de confirmación del SAT."),
			}
		)
		return msgs

	if facts["is_cancelado"]:
		msgs.append(
			{
				"code": "CFDI_CANCELLED",
				"level": "warning",
				"text": _("Complemento de pago cancelado ante el SAT."),
			}
		)

	return msgs
