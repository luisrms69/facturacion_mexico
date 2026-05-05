"""
Payment Entry cancel handler — Complemento Pago MX.
Cancela el complemento vinculado si existe.
"""

import frappe


def cancel_related_complement(doc, method=None):
	"""Cancelar Complemento Pago MX vinculado al Payment Entry."""
	complement_name = doc.get("fm_complemento_pago")
	if not complement_name:
		return

	if not frappe.db.exists("Complemento Pago MX", complement_name):
		return

	complement = frappe.get_doc("Complemento Pago MX", complement_name)
	if complement.docstatus == 1:
		complement.cancel()
		frappe.logger().info(f"Complemento {complement_name} cancelado por PE {doc.name}")
