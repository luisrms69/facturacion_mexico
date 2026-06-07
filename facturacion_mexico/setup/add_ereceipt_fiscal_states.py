"""
Agrega estados E-RECEIPT y E-RECEIPT-FACTURADO al Custom Field fm_fiscal_status
de Sales Invoice. Ejecutado por after_migrate.

Los fixtures de Custom Field en Frappe v16 no siempre actualizan el campo `options`
de campos Select existentes cuando el registro en BD tiene modified más reciente.
Este módulo garantiza que las opciones estén presentes sin importar el orden de sync.
"""

import frappe


def ensure_ereceipt_fiscal_states():
	"""Garantiza que fm_fiscal_status incluye las opciones de E-Receipt."""
	cf_name = "Sales Invoice-fm_fiscal_status"

	if not frappe.db.exists("Custom Field", cf_name):
		return

	current_options = frappe.db.get_value("Custom Field", cf_name, "options") or ""
	required_states = ["E-RECEIPT", "E-RECEIPT-FACTURADO"]

	missing = [s for s in required_states if s not in current_options]
	if not missing:
		return

	new_options = current_options.rstrip("\n") + "\n" + "\n".join(missing)
	frappe.db.set_value(
		"Custom Field",
		cf_name,
		"options",
		new_options,
		update_modified=False,
	)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required after_migrate setup operation
	frappe.logger().info(f"fm_fiscal_status: estados E-Receipt agregados: {missing}")
