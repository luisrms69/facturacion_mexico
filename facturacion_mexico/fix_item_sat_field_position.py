import frappe


def run():
	"""Mover campo fm_producto_servicio_sat a la sección SAT correcta"""

	print("🔧 MOVIENDO CAMPO SAT PRODUCTO/SERVICIO A SECCIÓN CORRECTA")
	print("=" * 60)

	try:
		# 1. Obtener el campo actual
		field_doc = frappe.get_doc("Custom Field", "Item-fm_producto_servicio_sat")

		print("📋 Estado actual:")
		print(f"   Insert After: {field_doc.insert_after}")
		print(f"   Hidden: {field_doc.hidden}")

		# 2. Buscar un campo SAT existente para posicionarlo correctamente
		meta = frappe.get_meta("Item")
		sat_fields = [
			f for f in meta.fields if f.fieldname.startswith("fm_") and "sat" in f.fieldname.lower()
		]

		print("\n📊 Campos SAT encontrados en Item:")
		for i, field in enumerate(sat_fields[:5]):
			print(f"   {i+1}. {field.fieldname}: {field.label}")

		# 3. Encontrar la sección SAT correcta
		# Buscar sección que contenga campos fm_
		target_insert_after = None
		current_section = None

		for field in meta.fields:
			if field.fieldtype == "Section Break" and (
				"sat" in field.fieldname.lower() or "fiscal" in field.fieldname.lower()
			):
				current_section = field.fieldname
				print(f"   📍 Sección SAT encontrada: {current_section}")
			elif current_section and field.fieldname.startswith("fm_") and "sat" not in field.fieldname:
				target_insert_after = field.fieldname
				break

		# Si no encontramos una sección específica, usar un campo SAT conocido
		if not target_insert_after:
			# Buscar campos fiscales conocidos
			known_sat_fields = ["fm_cfdi_use", "fm_uso_cfdi_default", "fm_enable_fiscal"]

			for known_field in known_sat_fields:
				if frappe.db.exists("Custom Field", f"Item-{known_field}"):
					target_insert_after = known_field
					break

		if target_insert_after:
			print(f"\n🎯 Moviendo campo después de: {target_insert_after}")

			# Actualizar posición del campo
			field_doc.insert_after = target_insert_after
			field_doc.save()

			# Limpiar cache para que se vea el cambio
			frappe.clear_cache()

			print("✅ Campo movido exitosamente")
			print("🔄 Cache limpiado - los cambios deberían ser visibles")

		else:
			print("⚠️  No se encontró ubicación SAT adecuada")
			print("    El campo permanece en su ubicación actual")

		# 4. Verificar estado final
		print("\n📊 Estado final:")
		updated_field = frappe.get_doc("Custom Field", "Item-fm_producto_servicio_sat")
		print(f"   Insert After: {updated_field.insert_after}")
		print(f"   Label: {updated_field.label}")
		print(f"   Hidden: {updated_field.hidden}")

		return {
			"success": True,
			"moved": bool(target_insert_after),
			"new_position": target_insert_after,
			"message": f"Campo {'movido' if target_insert_after else 'permanece en posición actual'}",
		}

	except Exception as e:
		print(f"💥 Error: {e!s}")
		return {"success": False, "error": str(e)}
