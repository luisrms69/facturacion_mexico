import frappe


def execute():
	"""Migra datos de complement_status → status en Complemento Pago MX."""
	if not frappe.db.has_column("Complemento Pago MX", "complement_status"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabComplemento Pago MX`
		SET status = complement_status
		WHERE complement_status IS NOT NULL AND complement_status != ''
		"""
	)
	frappe.db.commit()
