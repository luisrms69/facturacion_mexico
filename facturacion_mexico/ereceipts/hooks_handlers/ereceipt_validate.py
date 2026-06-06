"""
EReceipt Validation Hooks
"""

import frappe
from frappe.utils import add_days


def calculate_expiry_date(doc, method):
	"""Calculate expiry date for EReceipt MX."""
	if doc.expiry_type == "Fixed Days" and doc.expiry_days:
		doc.expiry_date = add_days(doc.date_issued, doc.expiry_days)
	elif doc.expiry_type == "End of Month":
		from frappe.utils import get_last_day

		doc.expiry_date = get_last_day(doc.date_issued)
	# Custom Date is already set by user


def populate_fiscal_info(doc, method):
	"""Rellena tax_rate y has_ieps desde SI si están vacíos (fallback para creación por otras vías).

	Transitorio — issue #182 para modelo line-level definitivo.
	"""
	if not doc.sales_invoice or doc.tax_rate is not None:
		return

	try:
		si = frappe.get_doc("Sales Invoice", doc.sales_invoice)
	except frappe.DoesNotExistError:
		return

	from facturacion_mexico.utils.calculo_impuestos import extract_iva_info_from_si_taxes

	tax_rate, has_ieps = extract_iva_info_from_si_taxes(si.taxes or [])
	doc.tax_rate = tax_rate
	doc.has_ieps = 1 if has_ieps else 0
