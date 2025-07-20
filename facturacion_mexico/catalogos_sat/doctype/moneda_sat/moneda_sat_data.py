"""
Datos de referencia para Moneda SAT
Catálogo SAT c_Moneda
"""

import frappe


def create_default_monedas_sat():
	"""Crear monedas SAT por defecto para testing."""

	# Monedas SAT más comunes según catálogo oficial
	monedas_data = [
		{"code": "MXN", "description": "Peso Mexicano", "decimales": 2, "vigencia_desde": "2010-01-01"},
		{
			"code": "USD",
			"description": "Dólar de los Estados Unidos de América",
			"decimales": 2,
			"vigencia_desde": "2010-01-01",
		},
		{"code": "EUR", "description": "Euro", "decimales": 2, "vigencia_desde": "2010-01-01"},
	]

	for moneda_data in monedas_data:
		# Verificar si ya existe
		existing = frappe.db.exists("Moneda SAT", moneda_data["code"])
		if existing:
			continue

		# Crear nueva moneda
		moneda = frappe.new_doc("Moneda SAT")
		moneda.update(moneda_data)
		moneda.insert(ignore_permissions=True)

	frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to persist catalog data during system initialization


if __name__ == "__main__":
	create_default_monedas_sat()
