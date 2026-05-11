"""
fiscal_state/payment_entry_state.py

Calcula el estado fiscal de un Payment Entry de forma centralizada.
Read-only — no modifica ningún documento.

Propósito inicial: auditoría y comparación contra la lógica actual de UI.
No reemplaza todavía los botones/mensajes existentes.
"""

import frappe
from frappe import _


def get_payment_entry_fiscal_state(pe_name: str) -> dict:
	"""
	Retorna el estado fiscal completo de un Payment Entry.

	Returns:
		dict con:
		  facts   — hechos observables del documento y sus vínculos
		  actions — acciones que el usuario puede ejecutar (derivadas de facts)
		  messages — mensajes que la UI debería mostrar (derivados de facts)
	"""
	pe = frappe.get_doc("Payment Entry", pe_name)

	facts = _compute_facts(pe)
	actions = _compute_actions(facts)
	messages = _compute_messages(facts)

	return {
		"doctype": "Payment Entry",
		"name": pe_name,
		"facts": facts,
		"actions": actions,
		"messages": messages,
	}


# ── Facts ──────────────────────────────────────────────────────────────────


def _compute_facts(pe) -> dict:
	"""Observa el estado real del documento y sus vínculos. Solo lee, no decide."""

	# ── Estado documental ──────────────────────────────────────────────────
	facts = {
		"is_draft": pe.docstatus == 0,
		"is_submitted": pe.docstatus == 1,
		"is_cancelled": pe.docstatus == 2,
		"payment_type": pe.payment_type,
		"party_type": pe.party_type,
	}

	# ── Referencias a Sales Invoice ────────────────────────────────────────
	si_refs = [ref for ref in pe.get("references", []) if ref.reference_doctype == "Sales Invoice"]
	allocated_si_refs = [ref for ref in si_refs if ref.allocated_amount > 0]
	si_names = [ref.reference_name for ref in allocated_si_refs]

	facts["has_sales_invoice_references"] = bool(si_refs)
	facts["has_allocated_sales_invoice_references"] = bool(allocated_si_refs)

	# ── Estado PPD de las SIs referenciadas ───────────────────────────────
	has_ppd = False
	has_ppd_stamped = False

	if si_names:
		si_data = frappe.get_all(
			"Sales Invoice",
			filters={"name": ["in", si_names]},
			fields=["name", "fm_es_ppd", "fm_fiscal_status"],
		)
		for si in si_data:
			if si.get("fm_es_ppd"):
				has_ppd = True
				if si.get("fm_fiscal_status") == "TIMBRADO":
					has_ppd_stamped = True

	facts["has_ppd_invoice"] = has_ppd
	facts["has_ppd_stamped_invoice"] = has_ppd_stamped

	# ── Estado del complemento ─────────────────────────────────────────────
	# fm_require_complement es ahora confiable gracias al hook implementado
	facts["requires_complement"] = bool(pe.get("fm_require_complement"))
	facts["has_complement"] = bool(pe.get("fm_complemento_pago"))

	has_active = False
	has_cancelled = False
	has_error = False
	complement_status = None
	complement_has_uuid = False
	complement_has_file = False

	if pe.get("fm_complemento_pago"):
		comp = frappe.get_all(
			"Complemento Pago MX",
			filters={"name": pe.fm_complemento_pago},
			fields=["name", "status", "uuid_sat", "facturapi_id"],
			limit=1,
		)
		if comp:
			c = comp[0]
			complement_status = c.get("status")
			complement_has_uuid = bool(c.get("uuid_sat"))
			complement_has_file = bool(c.get("facturapi_id"))

			if complement_status == "Cancelado":
				has_cancelled = True
			elif complement_status == "Error":
				has_error = True
			else:
				has_active = True

	facts["has_active_complement"] = has_active
	facts["has_cancelled_complement"] = has_cancelled
	facts["has_complement_error"] = has_error
	facts["complement_status"] = complement_status
	facts["complement_has_uuid"] = complement_has_uuid
	facts["complement_has_file"] = complement_has_file

	return facts


# ── Actions ────────────────────────────────────────────────────────────────


def _compute_actions(facts: dict) -> dict:
	"""Deriva las acciones posibles a partir de los hechos. No consulta BD."""
	return {
		"can_create_complement": (
			facts["is_submitted"]
			and facts["payment_type"] == "Receive"
			and facts["requires_complement"]
			and not facts["has_active_complement"]
			and not facts["has_cancelled_complement"]
		),
		"can_view_complement": facts["has_complement"],
		"can_cancel_complement": (
			facts["has_active_complement"] and facts["complement_status"] == "Timbrado"
		),
		"can_download_complement_xml": (facts["has_active_complement"] and facts["complement_has_file"]),
		"can_download_complement_pdf": (facts["has_active_complement"] and facts["complement_has_file"]),
		"can_retry_complement": facts["has_complement_error"],
	}


# ── Messages ───────────────────────────────────────────────────────────────


def _compute_messages(facts: dict) -> list:
	"""
	Genera los mensajes que la UI debería mostrar.
	Retorna lista de {code, level, text} para que el JS los consuma.
	"""
	msgs = []

	if not facts["is_submitted"]:
		return msgs

	if facts["payment_type"] != "Receive":
		return msgs

	# Bloqueo: tiene SIs PPD pero ninguna está timbrada
	if facts["has_ppd_invoice"] and not facts["has_ppd_stamped_invoice"]:
		msgs.append(
			{
				"code": "COMPLEMENT_BLOCKED_NO_STAMPED_SI",
				"level": "warning",
				"text": _("No se puede generar complemento: ninguna factura PPD referenciada está timbrada."),
			}
		)
		return msgs

	# Sin facturas PPD → no requiere complemento
	if not facts["requires_complement"]:
		msgs.append(
			{
				"code": "COMPLEMENT_NOT_REQUIRED",
				"level": "info",
				"text": _(
					"Este pago no requiere Complemento de Pago (no referencia facturas PPD timbradas)."
				),
			}
		)
		return msgs

	# Requiere complemento y tiene uno activo
	if facts["has_active_complement"]:
		msgs.append(
			{
				"code": "COMPLEMENT_EXISTS",
				"level": "success",
				"text": _("Complemento de Pago generado y vigente."),
			}
		)
		return msgs

	# Requiere complemento y el que tenía fue cancelado
	if facts["has_cancelled_complement"]:
		msgs.append(
			{
				"code": "COMPLEMENT_CANCELLED",
				"level": "warning",
				"text": _("El Complemento de Pago anterior fue cancelado. Puedes generar uno nuevo."),
			}
		)
		return msgs

	# Error en el complemento
	if facts["has_complement_error"]:
		msgs.append(
			{
				"code": "COMPLEMENT_ERROR",
				"level": "error",
				"text": _("El Complemento de Pago tiene un error. Usa 'Reintentar' para timbrar de nuevo."),
			}
		)
		return msgs

	# Requiere complemento y no tiene ninguno
	if facts["requires_complement"]:
		msgs.append(
			{
				"code": "COMPLEMENT_REQUIRED",
				"level": "warning",
				"text": _("Este pago requiere un Complemento de Pago (REP). Usa 'Crear Complemento'."),
			}
		)

	return msgs
