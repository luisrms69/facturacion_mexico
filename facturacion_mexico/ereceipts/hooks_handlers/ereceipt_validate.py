"""
EReceipt Validation Hooks
"""

import frappe
from frappe.utils import add_days, getdate


def calculate_expiry_date(doc, method):
	"""Calculate expiry date for EReceipt MX."""
	if doc.expiry_type == "Fixed Days" and doc.expiry_days:
		doc.expiry_date = add_days(doc.date_issued, doc.expiry_days)
	elif doc.expiry_type == "End of Month":
		from frappe.utils import get_last_day

		doc.expiry_date = get_last_day(doc.date_issued)
	# Custom Date is already set by user
