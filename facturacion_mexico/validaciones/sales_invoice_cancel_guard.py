import frappe
from frappe import _

# Ajusta a los nombres reales de tu DocType y campos
FFM_DOCTYPE = "Factura Fiscal Mexico"
# Campo link en Sales Invoice:
FFM_LINK_FIELD = "fm_factura_fiscal_mx"
# Campo de estado fiscal en FFM (ajusta si tu campo se llama distinto)
FFM_STATUS_FIELD = "fm_fiscal_status"

# Estados que PERMITEN cancelar la SI (cancela solo si FFM está totalmente cancelada)
ALLOWED_FFM_CANCELLED_STATES = {"CANCELADO", "CANCELADA", "CANCELLED", "CANCELLED_OK", "CANCELED"}


def _get_linked_ffm(si_name: str):
	"""Devuelve (name, status) de la FFM vinculada a la SI."""
	# 1) por campo link directo
	ffm = frappe.db.get_value(
		FFM_DOCTYPE,
		{"sales_invoice": si_name},  # si tu FFM guarda la SI
		["name", FFM_STATUS_FIELD],
		as_dict=True,
	)
	if ffm:
		return ffm

	# 2) por campo link en la propia SI (más común)
	ffm_name = frappe.db.get_value("Sales Invoice", si_name, FFM_LINK_FIELD)
	if ffm_name:
		vals = frappe.db.get_value(FFM_DOCTYPE, ffm_name, ["name", FFM_STATUS_FIELD], as_dict=True)
		return vals
	return None


def _ffm_allows_cancellation(ffm: dict) -> (bool, str):
	"""Regresa (allowed, reason). allowed=True solo si FFM está 100% cancelada."""
	if not ffm:
		return True, ""
	status = (ffm.get(FFM_STATUS_FIELD) or "").upper().strip()
	if status in ALLOWED_FFM_CANCELLED_STATES:
		return True, ""

	if status:
		return False, _("La Factura Fiscal vinculada no está cancelada (estado: {0}).").format(status)
	return False, _("Existe una Factura Fiscal vinculada y no está cancelada.")


def before_cancel(doc, method=None):
	"""Hook de Sales Invoice: bloquear cancelación si la FFM no está 100% cancelada."""
	ffm = _get_linked_ffm(doc.name)
	allowed, reason = _ffm_allows_cancellation(ffm)
	if not allowed:
		raise frappe.ValidationError(_("No se puede cancelar esta Sales Invoice: {0}").format(reason))


@frappe.whitelist()
def can_cancel_sales_invoice(si_name: str) -> dict:
	"""Para el cliente: responde si se puede cancelar y por qué."""
	ffm = _get_linked_ffm(si_name)
	allowed, reason = _ffm_allows_cancellation(ffm)
	return {"allowed": bool(allowed), "reason": reason, "ffm": (ffm or {}).get("name")}
