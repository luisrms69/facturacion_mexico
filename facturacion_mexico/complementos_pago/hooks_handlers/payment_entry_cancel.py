"""
Payment Entry before_cancel / on_cancel — Complemento Pago MX.

Bloquea la cancelación del PE si tiene un Complemento Pago MX activo
(cualquier estado distinto de "Cancelado").
"""

import frappe
from frappe import _


def block_cancel_if_complemento_activo(doc, method=None):
	"""Hook before_cancel — bloquear si complemento no está cancelado."""
	comp_name = doc.get("fm_complemento_pago")
	if not comp_name:
		return

	status = frappe.db.get_value("Complemento Pago MX", comp_name, "complement_status")
	if not status:
		return

	if status != "Cancelado":
		frappe.throw(
			_(
				"No se puede cancelar el Payment Entry {0} porque tiene un "
				"Complemento de Pago fiscal activo ({1}) en estado '{2}'. "
				"Cancele primero el Complemento de Pago."
			).format(doc.name, comp_name, status),
			title=_("Complemento de Pago activo"),
		)


def cancel_related_complement(doc, method=None):
	"""Hook on_cancel — por ahora no-op. El complemento se cancela manualmente."""
	pass
