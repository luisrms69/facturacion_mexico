"""
Datos de referencia para Impuesto SAT
Catálogo SAT c_Impuesto
"""

import frappe


def create_default_impuestos_sat():
	"""Crear impuestos SAT por defecto para testing."""

	# Impuestos SAT más comunes según catálogo oficial
	impuestos_data = [
		{"code": "002", "description": "IVA", "vigencia_desde": "2010-01-01"},
		{"code": "001", "description": "ISR", "vigencia_desde": "2010-01-01"},
		{"code": "003", "description": "IEPS", "vigencia_desde": "2010-01-01"},
	]

	for impuesto_data in impuestos_data:
		# Verificar si ya existe
		existing = frappe.db.exists("Impuesto SAT", impuesto_data["code"])
		if existing:
			continue

		# Crear nuevo impuesto
		impuesto = frappe.new_doc("Impuesto SAT")
		impuesto.update(impuesto_data)
		impuesto.insert(ignore_permissions=True)

	frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to persist catalog data during system initialization


if __name__ == "__main__":
	create_default_impuestos_sat()
