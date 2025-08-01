import frappe


def run():
	"""Probar validaciones UOM SAT en Sales Invoice"""

	print("🧪 PROBANDO VALIDACIONES UOM SAT")
	print("=" * 40)

	try:
		# 1. Verificar que tenemos UOMs SAT disponibles
		sat_uoms = frappe.get_all(
			"UOM", filters={"uom_name": ["like", "% - %"], "enabled": 1}, fields=["name", "uom_name"], limit=3
		)

		print(f"✅ UOMs SAT disponibles para testing: {len(sat_uoms)}")
		for uom in sat_uoms:
			print(f"   - {uom.uom_name}")

		if not sat_uoms:
			return {"error": "No hay UOMs SAT disponibles"}

		# 2. Probar validación formato SAT
		from facturacion_mexico.facturacion_fiscal.hooks_handlers.sales_invoice_validate import (
			_validate_uom_sat_format,
		)

		# Test item simulado con UOM SAT válida
		test_item_valid = frappe._dict({"item_code": "TEST-ITEM", "uom": "H87 - Pieza"})

		print(f"\n🔍 Probando UOM válida: '{test_item_valid.uom}'")
		try:
			_validate_uom_sat_format(test_item_valid)
			print("✅ Validación exitosa - UOM SAT válida")
		except Exception as e:
			print(f"❌ Error inesperado: {e!s}")
			return {"error": f"Validación falló para UOM válida: {e!s}"}

		# 3. Probar validación con UOM inválida
		test_item_invalid = frappe._dict({"item_code": "TEST-ITEM-2", "uom": "InvalidUOM"})

		print(f"\n🔍 Probando UOM inválida: '{test_item_invalid.uom}'")
		try:
			_validate_uom_sat_format(test_item_invalid)
			print("❌ ERROR - Validación debería haber fallado")
			return {"error": "Validación no detectó UOM inválida"}
		except Exception as e:
			print(f"✅ Validación correcta - Error esperado: {str(e)[:100]}...")

		# 4. Verificar que Item puede usar UOMs SAT
		print("\n📦 Verificando Items con UOMs SAT...")

		# Buscar items existentes con UOMs SAT
		items_with_sat = frappe.get_all(
			"Item", filters={"stock_uom": ["like", "% - %"]}, fields=["item_code", "stock_uom"], limit=3
		)

		print(f"   Items con UOM SAT: {len(items_with_sat)}")
		for item in items_with_sat:
			print(f"   - {item.item_code}: {item.stock_uom}")

		# 5. Estado final
		print("\n📊 RESUMEN TESTING:")
		print(f"   ✅ UOMs SAT activas: {len(sat_uoms)}")
		print("   ✅ Validación formato: Funcionando")
		print("   ✅ Detección errores: Funcionando")
		print(f"   ✅ Items compatibles: {len(items_with_sat)}")

		return {
			"success": True,
			"sat_uoms_available": len(sat_uoms),
			"validation_working": True,
			"items_with_sat": len(items_with_sat),
		}

	except Exception as e:
		print(f"💥 Error en testing: {e!s}")
		return {"success": False, "error": str(e)}
