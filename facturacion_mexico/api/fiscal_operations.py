import frappe
from frappe import _


@frappe.whitelist()
def refacturar_misma_si(si_name: str):
	"""
	Re-facturación con la MISMA Sales Invoice para motivos 02/03/04:
	- Verifica que la última FFM ligada al SI esté CANCELADA con motivo 02/03/04
	- Desvincula el SI (limpia fm_factura_fiscal_mx y estado fiscal local)
	- NO timbra ni crea FFM aquí. Solo prepara el SI para usar el flujo original.
	"""
	si = frappe.get_doc("Sales Invoice", si_name)

	# Precondiciones básicas
	if si.docstatus != 1:
		frappe.throw(_("La Sales Invoice debe estar enviada (docstatus=1)."))

	ffm_name = si.get("fm_factura_fiscal_mx")
	if ffm_name:
		ffm = frappe.get_doc("Factura Fiscal Mexico", ffm_name)
		if ffm.fm_fiscal_status != "CANCELADO":
			frappe.throw(
				_(
					"Este botón solo aplica cuando la última Factura Fiscal ligada está CANCELADA (motivo 02/03/04)."
				)
			)

		# M4-02/03/04: Guard contextual - verificar motivo cancelación 02/03/04
		motivo_code = _extract_motive_code_from_reason(ffm.get("cancellation_reason") or "")
		if motivo_code not in ["02", "03", "04"]:
			frappe.throw(
				_(
					"Esta re-facturación aplica únicamente para motivos 02/03/04. "
					f"Motivo actual: {motivo_code or 'N/A'}"
				)
			)

		# Guard avanzado: verificar que no hay operaciones pendientes
		if ffm.get("fm_sync_status") == "pending":
			frappe.throw(_("Operación pendiente en FFM. Espera a que complete antes de re-facturar."))

	# IDEMPOTENCIA: Si ya está desvinculado, respuesta elegante
	if not si.get("fm_factura_fiscal_mx"):
		return {
			"ok": True,
			"already_unlinked": True,
			"message": _("Sales Invoice ya está listo. Use 'Generar Factura Fiscal' (flujo normal)."),
		}

	# DESVINCULACIÓN: Limpiar links y flags residuales para volver al flujo nativo
	ffm_anterior = si.get("fm_factura_fiscal_mx")  # Para trazabilidad

	# Limpiar vinculación principal
	si.db_set("fm_factura_fiscal_mx", "")

	# Limpiar estado fiscal local para UI limpia
	if hasattr(si, "fm_fiscal_status"):
		si.db_set("fm_fiscal_status", "")
	if hasattr(si, "fm_sync_status"):
		si.db_set("fm_sync_status", "idle")

	# Limpiar flags residuales de sustitución (si existieran)
	if hasattr(si, "ffm_substitution_source_uuid"):
		si.db_set("ffm_substitution_source_uuid", "")

	# TRAZABILIDAD MÍNIMA: Comment simple sin sobrecarga
	si.add_comment(
		"Info", _("Re-facturación 02/03/04: SI desvinculada de FFM {0}.").format(ffm_anterior or "N/A")
	)

	# M4-FIX-03: Refuerzo estado limpio para evitar validaciones residuales
	si.reload()
	frappe.db.commit()
	frappe.clear_cache()

	return {
		"ok": True,
		"message": _("Sales Invoice lista para re-facturar. Use 'Generar Factura Fiscal' (flujo normal)."),
	}


def _extract_motive_code_from_reason(cancellation_reason: str) -> str:
	"""Extrae código motivo de 'cancellation_reason' formato '02 - Descripción'."""
	if not cancellation_reason:
		return ""

	# Buscar patrón "NN - " al inicio
	import re

	match = re.match(r"^(\d{2})\s*-", cancellation_reason.strip())
	return match.group(1) if match else ""
