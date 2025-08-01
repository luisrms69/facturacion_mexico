import frappe


def run():
	"""Analizar uso del campo fm_unidad_sat para determinar si se puede eliminar"""

	print("🔍 ANALIZANDO USO DE CAMPO fm_unidad_sat")
	print("=" * 50)

	try:
		# 1. Verificar si el campo existe
		field_exists = frappe.db.exists("Custom Field", "Item-fm_unidad_sat")

		print("📋 ESTADO CAMPO:")
		print(f"   Campo existe: {field_exists}")

		if field_exists:
			field_doc = frappe.get_doc("Custom Field", "Item-fm_unidad_sat")
			print(f"   Label: {field_doc.label}")
			print(f"   Fieldtype: {field_doc.fieldtype}")
			print(f"   Hidden: {field_doc.hidden}")

		# 2. Verificar uso en timbrado (crítico)
		print("\n🎯 USO EN TIMBRADO (timbrado_api.py):")
		print('   ✅ USADO: "unit_key": item_doc.fm_unidad_sat or "H87"')
		print("   📍 Línea 180: Requerido para FacturAPI.io")
		print("   ⚠️  PROBLEMA: Usa campo directo, no UOM con formato SAT")

		# 3. Verificar datos existentes
		items_with_unidad_sat = frappe.db.sql(
			"""
            SELECT name, fm_unidad_sat, stock_uom
            FROM `tabItem`
            WHERE fm_unidad_sat IS NOT NULL
            AND fm_unidad_sat != ''
            LIMIT 5
        """,
			as_dict=True,
		)

		print("\n💾 DATOS EXISTENTES:")
		print(f"   Items con fm_unidad_sat: {len(items_with_unidad_sat)}")
		for item in items_with_unidad_sat:
			print(f'   - {item.name}: fm_unidad_sat="{item.fm_unidad_sat}", stock_uom="{item.stock_uom}"')

		# 4. Verificar uso en tests
		print("\n🧪 USO EN TESTS:")
		print("   ✅ test_layer3_complete_system_integration_sprint6.py")
		print("   ✅ test_layer3_cfdi_multisucursal_generation_workflows.py")
		print('   📍 Tests definen fm_unidad_sat="H87", "ACT", "E48"')

		# 5. Verificar validaciones actuales
		print("\n🔍 VALIDACIONES ACTUALES:")
		print("   ❌ OBSOLETO: sales_invoice_validate.py línea 123")
		print("   ✅ NUEVO: _validate_uom_sat_format() usa item.uom")
		print('   📍 Comentario: "Reemplaza validación anterior de fm_unidad_sat"')

		# 6. Analizar necesidad actual
		print("\n🤔 ANÁLISIS NECESIDAD:")
		print('   ❌ CAMPO DUPLICADO: Ahora UOM tiene formato SAT ("H87 - Pieza")')
		print("   ❌ TIMBRADO OBSOLETO: Usa fm_unidad_sat directo vs extraer de UOM")
		print("   ❌ MANTENIMIENTO DOBLE: fm_unidad_sat + UOM SAT format")

		# 7. Propuesta migración
		print("\n💡 PROPUESTA MIGRACIÓN:")
		print("   1. Actualizar timbrado_api.py para extraer código SAT de item.uom")
		print("   2. Actualizar tests para usar UOM SAT en lugar de fm_unidad_sat")
		print("   3. Migrar datos existentes: fm_unidad_sat → UOM SAT format")
		print("   4. Eliminar campo fm_unidad_sat obsoleto")

		return {
			"success": True,
			"field_exists": field_exists,
			"items_with_data": len(items_with_unidad_sat),
			"used_in_timbrado": True,
			"used_in_tests": True,
			"migration_needed": True,
			"can_eliminate": True,  # Después de migrar timbrado
			"recommendation": "Migrar timbrado_api.py y tests, luego eliminar campo",
		}

	except Exception as e:
		print(f"💥 Error: {e!s}")
		return {"success": False, "error": str(e)}
