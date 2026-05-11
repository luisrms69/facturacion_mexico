"""
Payment Entry validate hook — Complemento Pago MX.

Detecta si el PE referencia Sales Invoices PPD timbradas y actualiza
fm_require_complement como fuente única de verdad en BD.
"""

import frappe


def check_ppd_requirement(doc, method=None):
	"""Actualiza fm_require_complement según SIs PPD timbradas referenciadas.

	Regla:
	  fm_require_complement = 1  si existe al menos una SI referenciada con
	                              fm_es_ppd=1 Y con FFM en status TIMBRADO.
	  fm_require_complement = 0  en cualquier otro caso.

	Solo aplica a Payment Entry de tipo Receive (cobros).
	"""
	if doc.payment_type != "Receive":
		doc.fm_require_complement = 0
		return

	if doc.docstatus == 2:
		doc.fm_require_complement = 0
		return

	si_names = [
		ref.reference_name
		for ref in doc.get("references", [])
		if ref.reference_doctype == "Sales Invoice" and ref.allocated_amount > 0
	]

	if not si_names:
		doc.fm_require_complement = 0
		return

	# Buscar SIs PPD con FFM timbrada
	ppd_timbradas = frappe.get_all(
		"Sales Invoice",
		filters={
			"name": ["in", si_names],
			"fm_es_ppd": 1,
			"fm_fiscal_status": "TIMBRADO",
		},
		fields=["name"],
		limit=1,
	)

	doc.fm_require_complement = 1 if ppd_timbradas else 0
