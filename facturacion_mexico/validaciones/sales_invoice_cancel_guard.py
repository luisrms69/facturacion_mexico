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
		{"sales_invoice": si_name, "docstatus": 1},  # ← SOLO SUBMITTED
		["name", FFM_STATUS_FIELD],
		as_dict=True,
	)
	if ffm:
		return ffm

	# 2) por campo link en la propia SI (más común)
	ffm_name = frappe.db.get_value("Sales Invoice", si_name, FFM_LINK_FIELD)
	if not ffm_name:
		return None

	return frappe.db.get_value(
		FFM_DOCTYPE,
		{"name": ffm_name, "docstatus": 1},  # ← SOLO SUBMITTED
		["name", FFM_STATUS_FIELD],
		as_dict=True,
	)


def _ffm_allows_cancellation(ffm: dict) -> (bool, str):
	"""allowed=True si la FFM está cancelada (docstatus=2) o cumple estados PAC permitidos."""
	if not ffm:
		return True, ""

	docstatus = frappe.db.get_value("Factura Fiscal Mexico", ffm["name"], "docstatus")
	if docstatus == 2:
		return True, ""
	if docstatus != 1:  # draft (0) u otros → no bloquean
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
