"""
Payment Entry validate hook — Complemento Pago MX.

ESTADO: no-op hasta Bloque 3B.
La detección PPD usa fm_es_ppd (campo en Sales Invoice).
"""

import frappe


def check_ppd_requirement(doc, method=None):
	"""Hook validate — pendiente implementación en Bloque 3B."""
	pass
