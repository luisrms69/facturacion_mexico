"""
fiscal_state/sales_invoice_state.py

Calcula el estado fiscal de una Sales Invoice de forma centralizada.
Read-only — no modifica ningún documento ni comportamiento existente.

Propósito inicial: auditoría y comparación contra la lógica actual de UI.
"""

import frappe
from frappe import _

_TIMBRABLE_STATUSES = {"", "BORRADOR", "ERROR"}
_CANCELADO = "CANCELADO"
_TIMBRADO = "TIMBRADO"
_PENDIENTE_CANCELACION = "PENDIENTE_CANCELACION"


def get_sales_invoice_fiscal_state(si_name: str) -> dict:
	"""
	Retorna el estado fiscal completo de una Sales Invoice.

	Returns:
		dict con facts, actions y messages.
	"""
	si = frappe.get_doc("Sales Invoice", si_name)

	facts = _compute_facts(si)
	actions = _compute_actions(facts)
	messages = _compute_messages(facts)

	return {
		"doctype": "Sales Invoice",
		"name": si_name,
		"facts": facts,
		"actions": actions,
		"messages": messages,
	}


# ── Facts ──────────────────────────────────────────────────────────────────


def _compute_facts(si) -> dict:
	"""Observa el estado real del documento y sus vínculos. Solo lee."""

	fiscal_status = (si.get("fm_fiscal_status") or "").upper()

	facts = {
		# ── Estado documental ──────────────────────────────────────────────
		"is_draft": si.docstatus == 0,
		"is_submitted": si.docstatus == 1,
		"is_cancelled": si.docstatus == 2,
		"is_return": bool(si.get("is_return")),
		# ── Método de pago ────────────────────────────────────────────────
		"is_ppd": bool(si.get("fm_es_ppd")),
		"is_pue": not bool(si.get("fm_es_ppd")),
		# ── Estado fiscal ────────────────────────────────────────────────
		"fiscal_status": fiscal_status,
	}

	# ── FFM vinculada ─────────────────────────────────────────────────────
	ffm_name = si.get("fm_factura_fiscal_mx") or ""
	facts["has_ffm"] = bool(ffm_name)

	has_active_ffm = False
	has_cancelled_ffm = False
	has_stamped_ffm = False
	has_uuid = False
	has_xml = False
	has_pdf = False
	ffm_motivo = None

	if ffm_name:
		ffm_data = frappe.get_all(
			"Factura Fiscal Mexico",
			filters={"name": ffm_name},
			fields=["name", "status", "fm_uuid", "fm_motivo_cancelacion", "docstatus"],
			limit=1,
		)
		if ffm_data:
			ffm = ffm_data[0]
			ffm_status = (ffm.get("status") or "").upper()
			has_uuid = bool(ffm.get("fm_uuid"))
			ffm_motivo = ffm.get("fm_motivo_cancelacion")

			if ffm_status == _CANCELADO:
				has_cancelled_ffm = True
			elif ffm.get("docstatus") == 1:
				has_active_ffm = True

			has_stamped_ffm = has_uuid

			# Archivos: verificar adjuntos con extensión xml/pdf en la FFM
			if has_uuid:
				attachments = frappe.get_all(
					"File",
					filters={"attached_to_doctype": "Factura Fiscal Mexico", "attached_to_name": ffm_name},
					fields=["file_name"],
				)
				for att in attachments:
					name = (att.get("file_name") or "").lower()
					if name.endswith(".xml"):
						has_xml = True
					if name.endswith(".pdf"):
						has_pdf = True

	facts.update(
		{
			"has_active_ffm": has_active_ffm,
			"has_cancelled_ffm": has_cancelled_ffm,
			"has_stamped_ffm": has_stamped_ffm,
			"has_uuid": has_uuid,
			"has_xml": has_xml,
			"has_pdf": has_pdf,
			"ffm_motivo_cancelacion": ffm_motivo,
		}
	)

	# ── Estado de pago ────────────────────────────────────────────────────
	outstanding = float(si.get("outstanding_amount") or 0)
	grand_total = float(si.get("grand_total") or 0)

	facts["outstanding_amount"] = outstanding
	facts["is_paid"] = si.docstatus == 1 and outstanding == 0
	facts["is_partially_paid"] = si.docstatus == 1 and 0 < outstanding < grand_total

	# ── Payment Entries ───────────────────────────────────────────────────
	pe_refs = frappe.get_all(
		"Payment Entry Reference",
		filters={"reference_doctype": "Sales Invoice", "reference_name": si.name},
		fields=["parent"],
	)
	pe_names = [r.get("parent") for r in pe_refs if r.get("parent")]

	has_pe = bool(pe_names)
	has_submitted_pe = False

	if pe_names:
		submitted = frappe.get_all(
			"Payment Entry",
			filters={"name": ["in", pe_names], "docstatus": 1},
			fields=["name"],
			limit=1,
		)
		has_submitted_pe = bool(submitted)

	facts["has_payment_entries"] = has_pe
	facts["has_submitted_payment_entries"] = has_submitted_pe

	# ── Estado de complemento ─────────────────────────────────────────────
	requires_complement = facts["is_ppd"] and has_stamped_ffm and has_submitted_pe
	facts["requires_complement"] = requires_complement

	has_complement = False
	has_active_complement = False

	if has_submitted_pe:
		submitted_pe_names = [
			r["name"]
			for r in frappe.get_all(
				"Payment Entry",
				filters={"name": ["in", pe_names], "docstatus": 1},
				fields=["name"],
			)
		]
		if submitted_pe_names:
			comps = frappe.get_all(
				"Complemento Pago MX",
				filters={"payment_entry": ["in", submitted_pe_names]},
				fields=["name", "status"],
			)
			if comps:
				has_complement = True
				active = [c for c in comps if c.get("status") not in ("Cancelado", "Error")]
				has_active_complement = bool(active)

	facts["has_complement"] = has_complement
	facts["has_active_complement"] = has_active_complement

	return facts


# ── Actions ────────────────────────────────────────────────────────────────


def _compute_actions(facts: dict) -> dict:
	"""Deriva acciones posibles desde facts. No consulta BD."""
	fiscal_status = facts["fiscal_status"]
	is_submitted = facts["is_submitted"]

	can_stamp = is_submitted and fiscal_status in _TIMBRABLE_STATUSES and not facts["has_active_ffm"]

	can_cancel_cfdi = (
		is_submitted
		and fiscal_status == _TIMBRADO
		and facts["has_stamped_ffm"]
		and not facts["has_active_complement"]
	)

	can_refacturar = (
		is_submitted
		and fiscal_status == _CANCELADO
		and facts["has_cancelled_ffm"]
		and (facts["ffm_motivo_cancelacion"] or "") in ("02", "03", "04")
	)

	can_substitute = is_submitted and fiscal_status == _TIMBRADO and facts["has_stamped_ffm"]

	can_generate_complement = (
		is_submitted
		and facts["is_ppd"]
		and facts["has_stamped_ffm"]
		and facts["has_submitted_payment_entries"]
		and not facts["has_active_complement"]
	)

	# Registrar pagos está permitido solo cuando no hay FFM cancelada ante el SAT.
	# Equivale a la lógica de sales_invoice_block_cancel.js que oculta Create/Payment
	# cuando la SI tiene FFM CANCELADO — gap crítico identificado en auditoría.
	can_register_payment = (
		is_submitted and not facts["is_cancelled"] and (not facts["has_ffm"] or facts["has_active_ffm"])
	)

	return {
		"can_stamp": can_stamp,
		"can_view_ffm": facts["has_ffm"],
		"can_cancel_cfdi": can_cancel_cfdi,
		"can_download_xml": facts["has_uuid"] and facts["has_xml"],
		"can_download_pdf": facts["has_uuid"] and facts["has_pdf"],
		"can_generate_payment_complement": can_generate_complement,
		"can_refacturar": can_refacturar,
		"can_substitute": can_substitute,
		"can_register_payment": can_register_payment,
	}


# ── Messages ───────────────────────────────────────────────────────────────


def _compute_messages(facts: dict) -> list:
	"""Genera mensajes para la UI basados en facts."""
	msgs = []
	fiscal_status = facts["fiscal_status"]

	if facts["is_draft"]:
		msgs.append(
			{
				"code": "BLOCKED_DRAFT",
				"level": "info",
				"text": _("Borrador — envía primero la factura de venta."),
			}
		)
		return msgs

	if facts["is_cancelled"]:
		msgs.append({"code": "BLOCKED_CANCELLED", "level": "info", "text": _("Factura de venta cancelada.")})
		return msgs

	# ── SI submitted ──────────────────────────────────────────────────────
	# CFDI_CANCELLED tiene prioridad: el estado fiscal de la SI es la fuente de
	# verdad cuando el CFDI fue cancelado, incluso si la FFM ya no tiene UUID.
	if fiscal_status == _CANCELADO or facts["has_cancelled_ffm"]:
		msgs.append({"code": "CFDI_CANCELLED", "level": "warning", "text": _("CFDI cancelado ante el SAT.")})
		return msgs

	# Solo mostrar CFDI_NOT_STAMPED cuando no hay cancelación y no hay UUID
	if not facts["has_stamped_ffm"]:
		msgs.append({"code": "CFDI_NOT_STAMPED", "level": "warning", "text": _("CFDI no timbrado.")})
		return msgs

	if fiscal_status == _TIMBRADO:
		msgs.append({"code": "CFDI_STAMPED", "level": "success", "text": _("CFDI timbrado correctamente.")})
		if facts["has_uuid"] and not (facts["has_xml"] or facts["has_pdf"]):
			msgs.append(
				{"code": "CFDI_FILES_MISSING", "level": "info", "text": _("XML/PDF pendientes de descargar.")}
			)

	elif fiscal_status == _CANCELADO:
		msgs.append({"code": "CFDI_CANCELLED", "level": "warning", "text": _("CFDI cancelado ante el SAT.")})

	elif fiscal_status == _PENDIENTE_CANCELACION:
		msgs.append(
			{
				"code": "CFDI_PENDING_CANCELLATION",
				"level": "warning",
				"text": _("Cancelación pendiente de confirmación del SAT."),
			}
		)

	# ── Estado de complemento ─────────────────────────────────────────────
	if facts["requires_complement"]:
		if facts["has_active_complement"]:
			msgs.append(
				{"code": "COMPLEMENT_EXISTS", "level": "success", "text": _("Complemento de pago vigente.")}
			)
		elif facts["has_complement"]:
			msgs.append(
				{
					"code": "COMPLEMENT_PENDING",
					"level": "warning",
					"text": _("Complemento de pago pendiente de timbrar o cancelado."),
				}
			)
		else:
			msgs.append(
				{
					"code": "COMPLEMENT_REQUIRED",
					"level": "warning",
					"text": _("Esta factura PPD requiere un Complemento de Pago."),
				}
			)

	return msgs
