import frappe


def run():
	"""Mover campo fm_producto_servicio_sat después de Default Unit of Measure"""

	print("🔧 MOVIENDO CAMPO SAT PRODUCTO/SERVICIO DESPUÉS DE DEFAULT UOM")
	print("=" * 65)

	try:
		# 1. Obtener el campo actual
		field_doc = frappe.get_doc("Custom Field", "Item-fm_producto_servicio_sat")

		print("📋 Estado actual:")
		print(f"   Insert After: {field_doc.insert_after}")

		# 2. Mover después de stock_uom (Default Unit of Measure)
		field_doc.insert_after = "stock_uom"
		field_doc.save()

		print("✅ Campo movido después de: stock_uom (Default Unit of Measure)")

		# 3. Limpiar cache para que se vea el cambio
		frappe.clear_cache()

		print("🔄 Cache limpiado")

		# 4. Verificar la nueva posición
		meta = frappe.get_meta("Item")
		found_uom = False
		found_field = False
		position = None

		for i, field in enumerate(meta.fields):
			if field.fieldname == "stock_uom":
				found_uom = True
				print(f"📍 Default Unit of Measure encontrado en posición {i}")
			elif found_uom and field.fieldname == "fm_producto_servicio_sat":
				found_field = True
				position = i
				print(f"✅ Campo fm_producto_servicio_sat encontrado en posición {i} (después de UOM)")
				break

		# 5. Verificar campos alrededor para contexto
		if position:
			print("\n📊 Contexto posición:")
			start = max(0, position - 2)
			end = min(len(meta.fields), position + 3)

			for i in range(start, end):
				field = meta.fields[i]
				marker = " ➤ " if i == position else "   "
				print(f"{marker}{i}: {field.fieldname} ({field.label}) - {field.fieldtype}")

		return {
			"success": True,
			"moved": True,
			"new_position": position,
			"after_uom": found_uom and found_field,
			"message": "Campo movido después de Default Unit of Measure",
		}

	except Exception as e:
		print(f"💥 Error: {e!s}")
		return {"success": False, "error": str(e)}
