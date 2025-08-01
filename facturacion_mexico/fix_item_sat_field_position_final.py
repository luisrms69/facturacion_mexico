import frappe


def run():
	"""Mover campo fm_producto_servicio_sat ANTES del Tab Break para que sea visible"""

	print("🔧 MOVIENDO CAMPO SAT PRODUCTO/SERVICIO ANTES DEL TAB")
	print("=" * 55)

	try:
		# 1. Obtener el campo actual
		field_doc = frappe.get_doc("Custom Field", "Item-fm_producto_servicio_sat")

		print("📋 Estado actual:")
		print(f"   Insert After: {field_doc.insert_after}")

		# 2. Necesitamos ponerlo justo después de la sección SAT
		# y antes del purchasing_tab

		# Opción 1: Después de fm_clasificacion_sat_section
		field_doc.insert_after = "fm_clasificacion_sat_section"
		field_doc.save()

		print("✅ Campo movido después de: fm_clasificacion_sat_section")

		# 3. Limpiar cache para que se vea el cambio
		frappe.clear_cache()

		print("🔄 Cache limpiado")

		# 4. Verificar que ahora esté en la posición correcta
		meta = frappe.get_meta("Item")
		found_section = False
		found_field = False
		found_tab = False

		for field in meta.fields:
			if field.fieldname == "fm_clasificacion_sat_section":
				found_section = True
				print("📍 Sección SAT encontrada")
			elif found_section and field.fieldname == "fm_producto_servicio_sat":
				found_field = True
				print("✅ Campo fm_producto_servicio_sat encontrado en sección SAT")
			elif found_section and field.fieldname == "purchasing_tab":
				found_tab = True
				if found_field:
					print("✅ Campo está ANTES del Tab Break (correcto)")
				else:
					print("❌ Campo está DESPUÉS del Tab Break (problema)")
				break

		return {
			"success": True,
			"moved": True,
			"in_sat_section": found_field and not found_tab,
			"message": "Campo movido a sección SAT antes del Tab Break",
		}

	except Exception as e:
		print(f"💥 Error: {e!s}")
		return {"success": False, "error": str(e)}
