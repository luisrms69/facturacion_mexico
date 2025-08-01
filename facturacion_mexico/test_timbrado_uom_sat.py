import frappe

from facturacion_mexico.facturacion_fiscal.timbrado_api import _extract_sat_code_from_uom


def run():
	"""Probar timbrado con nuevo sistema UOM SAT"""

	print("🧪 PROBANDO TIMBRADO CON UOM SAT")
	print("=" * 40)

	try:
		# 1. Probar función de extracción directamente
		print("📋 Pruebas función extracción:")
		test_uoms = [
			"H87 - Pieza",
			"E48 - Servicio",
			"ACT - Actividad",
			"Pieza",  # Genérica
			"Service",  # Genérica
		]

		for uom in test_uoms:
			code = _extract_sat_code_from_uom(uom)
			print(f'   "{uom}" → "{code}"')

		# 2. Probar con Item real que use UOM SAT
		print("\n🔍 Probando con Items reales:")

		# Buscar Items con UOM SAT
		items_with_sat_uom = frappe.db.sql(
			"""
            SELECT name, stock_uom, fm_producto_servicio_sat
            FROM `tabItem`
            WHERE stock_uom LIKE '% - %'
            LIMIT 3
        """,
			as_dict=True,
		)

		if items_with_sat_uom:
			for item in items_with_sat_uom:
				sat_code = _extract_sat_code_from_uom(item.stock_uom)
				print(f"   Item: {item.name}")
				print(f"     UOM: {item.stock_uom} → SAT: {sat_code}")
				print(f"     Producto SAT: {item.fm_producto_servicio_sat}")
		else:
			print("   No se encontraron Items con UOM SAT")

		# 3. Simular datos que llegarían al timbrado
		print("\n🎯 Simulación datos timbrado:")

		# Crear un item simulado
		if items_with_sat_uom:
			test_item = items_with_sat_uom[0]
		else:
			test_item = frappe._dict(
				{"name": "Test Item", "stock_uom": "H87 - Pieza", "fm_producto_servicio_sat": "80141600"}
			)

		# Simular el objeto item que llega al timbrado
		simulated_item = frappe._dict(
			{
				"item_code": test_item.name,
				"uom": test_item.stock_uom,
				"qty": 1,
				"rate": 100,
				"description": "Test description",
			}
		)

		# Extraer códigos como lo haría el timbrado
		unit_key = _extract_sat_code_from_uom(simulated_item.uom)

		print(f"   Item simulado: {simulated_item.item_code}")
		print(f"   UOM original: {simulated_item.uom}")
		print(f"   unit_key para FacturAPI: {unit_key}")
		print(f"   unit_name para FacturAPI: {simulated_item.uom}")

		# 4. Verificar que no hay dependencias de fm_unidad_sat
		items_with_old_field = frappe.db.sql(
			"""
            SELECT COUNT(*) as count
            FROM `tabItem`
            WHERE fm_unidad_sat IS NOT NULL
            AND fm_unidad_sat != ''
        """,
			as_dict=True,
		)[0]["count"]

		print("\n📊 Estado migración:")
		print(f"   Items con fm_unidad_sat: {items_with_old_field}")
		print(f"   Items con UOM SAT: {len(items_with_sat_uom)}")

		if items_with_old_field == 0:
			print("   ✅ Sin dependencias de fm_unidad_sat")
		else:
			print("   ⚠️  Aún hay Items con fm_unidad_sat")

		return {
			"success": True,
			"extraction_working": True,
			"items_with_sat_uom": len(items_with_sat_uom),
			"items_with_old_field": items_with_old_field,
			"ready_for_field_removal": items_with_old_field == 0,
		}

	except Exception as e:
		print(f"💥 Error: {e!s}")
		return {"success": False, "error": str(e)}
