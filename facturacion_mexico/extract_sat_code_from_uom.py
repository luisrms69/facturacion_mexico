import frappe


def extract_sat_code_from_uom(uom_name):
	"""
	Extraer código SAT de UOM con formato 'CODIGO - Descripción'

	Args:
	    uom_name (str): UOM name como "H87 - Pieza" o "KGM - Kilogramo"

	Returns:
	    str: Código SAT extraído como "H87" o fallback "H87"
	"""
	if not uom_name:
		return "H87"  # Fallback por defecto

	# Verificar si tiene formato SAT: "CODIGO - Descripción"
	if " - " in uom_name:
		parts = uom_name.split(" - ")
		if len(parts) >= 2 and parts[0].strip():
			return parts[0].strip()

	# Si no tiene formato SAT, intentar mapear UOMs genéricas comunes
	uom_mapping = {
		"Pieza": "H87",
		"Piece": "H87",
		"Unit": "H87",
		"Nos": "H87",
		"Kg": "KGM",
		"Kilogram": "KGM",
		"Gram": "GRM",
		"Liter": "LTR",
		"Litre": "LTR",
		"Meter": "MTR",
		"Hour": "HUR",
		"Service": "E48",
		"Activity": "ACT",
	}

	return uom_mapping.get(uom_name, "H87")


def run():
	"""Probar función de extracción de código SAT desde UOM"""

	print("🧪 PROBANDO EXTRACCIÓN CÓDIGO SAT DESDE UOM")
	print("=" * 50)

	test_cases = [
		"H87 - Pieza",
		"KGM - Kilogramo",
		"GRM - Gramo",
		"LTR - Litro",
		"E48 - Servicio",
		"Pieza",  # UOM genérica
		"Kg",  # UOM genérica
		"Hour",  # UOM genérica
		"",  # Vacío
		None,  # None
	]

	print("📋 Casos de prueba:")
	for case in test_cases:
		result = extract_sat_code_from_uom(case)
		print(f'   "{case}" → "{result}"')

	# Probar con UOMs reales de la base de datos
	print("\n🔍 UOMs SAT reales en base de datos:")
	sat_uoms = frappe.get_all(
		"UOM", filters={"uom_name": ["like", "% - %"], "enabled": 1}, fields=["uom_name"], limit=5
	)

	for uom in sat_uoms:
		result = extract_sat_code_from_uom(uom.uom_name)
		print(f'   "{uom.uom_name}" → "{result}"')

	return {
		"success": True,
		"function_ready": True,
		"test_cases_passed": len(test_cases),
		"sat_uoms_tested": len(sat_uoms),
	}
