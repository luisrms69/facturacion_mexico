"""
Payment Entry on_submit hook — Complemento Pago MX.

ESTADO: no-op hasta Bloque 3B.
La creación del complemento será manual (botón en Complemento Pago MX).
"""

import frappe


def create_complement_if_required(doc, method=None):
	"""Hook on_submit — pendiente implementación en Bloque 3B."""
	pass
