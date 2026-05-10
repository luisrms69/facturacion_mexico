"""
Patch para renombrar campo uuid a fm_uuid
Siguiendo best practices de namespacing en Frappe
"""

import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	"""Renombrar campo uuid a fm_uuid siguiendo namespacing best practices"""
	try:
		# Verificar si el campo existe antes de renombrar
		if frappe.db.has_column("Factura Fiscal Mexico", "uuid"):
			# Renombrar el campo en la BD
			rename_field("Factura Fiscal Mexico", "uuid", "fm_uuid")

			# Commit cambios
			frappe.db.commit()

			print("✅ Campo uuid renombrado exitosamente a fm_uuid")
		else:
			print("⚠️ Campo uuid no existe o ya fue renombrado")

	except Exception as e:
		frappe.log_error(f"Error renombrando campo uuid: {e}", "Patch UUID Rename Error")
		raise
