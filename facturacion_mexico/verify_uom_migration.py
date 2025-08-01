import os

import frappe


def run():
	"""Verificar estado final de migración UOM-SAT"""

	print("📊 ESTADO FINAL MIGRACIÓN UOM-SAT")
	print("=" * 40)

	# Contar UOMs SAT creadas
	sat_uoms = frappe.db.count("UOM", {"uom_name": ["like", "% - %"], "enabled": 1})
	print(f"✅ UOMs SAT activas: {sat_uoms}")

	# Contar UOMs genéricas aún activas
	generic_uoms = frappe.db.count("UOM", {"uom_name": ["not like", "% - %"], "enabled": 1})
	print(f"⚠️  UOMs genéricas activas: {generic_uoms}")

	# Verificar fixtures generados
	fixtures_path = "/home/erpnext/frappe-bench/apps/facturacion_mexico/facturacion_mexico/fixtures/uom.json"
	if os.path.exists(fixtures_path):
		print(f"✅ Fixtures UOM generados: uom.json")
		# Contar líneas del archivo
		with open(fixtures_path, "r") as f:
			lines = len(f.readlines())
		print(f"📄 Tamaño fixtures: {lines} líneas")
	else:
		print("❌ Fixtures UOM no encontrados")

	# Listar algunas UOMs SAT creadas
	sample_uoms = frappe.get_all(
		"UOM", filters={"uom_name": ["like", "% - %"], "enabled": 1}, fields=["uom_name"], limit=5
	)

	print("\n📋 Ejemplos UOMs SAT creadas:")
	for uom in sample_uoms:
		print(f"   - {uom.uom_name}")

	# Estado final
	migration_success = sat_uoms >= 18
	print("")
	print("🎯 MIGRACIÓN UOM-SAT:", "✅ EXITOSA" if migration_success else "❌ INCOMPLETA")

	return {
		"success": migration_success,
		"sat_uoms_active": sat_uoms,
		"generic_uoms_active": generic_uoms,
		"fixtures_generated": os.path.exists(fixtures_path),
	}
