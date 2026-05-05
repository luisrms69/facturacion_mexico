import frappe


def sync_ffm_summary_to_sales_invoice(ffm_doc, method=None):
	# Eliminado: los campos fm_ffm_* fueron removidos de Sales Invoice (siempre NULL).
	# El resumen fiscal se muestra vía fm_ffm_summary_html que lee FFM en tiempo real.
	pass
