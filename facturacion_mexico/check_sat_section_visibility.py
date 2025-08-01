import frappe


def run():
	"""Verificar visibilidad de sección SAT en Item"""

	print("🔍 VERIFICANDO VISIBILIDAD SECCIÓN SAT EN ITEM")
	print("=" * 50)

	try:
		# 1. Buscar sección SAT
		sat_section = frappe.get_doc("Custom Field", "Item-fm_clasificacion_sat_section")

		print("📋 Sección SAT (fm_clasificacion_sat_section):")
		print(f"   Label: {sat_section.label}")
		print(f"   Hidden: {sat_section.hidden}")
		print(f"   Collapsible: {sat_section.collapsible}")
		print(f"   Depends On: {sat_section.depends_on}")

		# 2. Verificar si hay depends_on que la oculte
		if sat_section.depends_on:
			print(f"⚠️  PROBLEMA: Sección tiene depends_on: {sat_section.depends_on}")
			print("   Esto puede estar ocultando toda la sección")

			# Remover depends_on si existe
			sat_section.depends_on = None
			sat_section.save()
			print("✅ Removido depends_on de la sección SAT")

		# 3. Verificar campos en la sección
		meta = frappe.get_meta("Item")
		in_sat_section = False
		sat_section_fields = []

		for field in meta.fields:
			if field.fieldname == "fm_clasificacion_sat_section":
				in_sat_section = True
				continue
			elif field.fieldtype == "Section Break" and in_sat_section:
				break
			elif in_sat_section:
				sat_section_fields.append(
					{
						"fieldname": field.fieldname,
						"label": field.label,
						"fieldtype": field.fieldtype,
						"hidden": field.hidden,
					}
				)

		print(f"\n📊 Campos en sección SAT ({len(sat_section_fields)}):")
		for field in sat_section_fields:
			visibility = "🔍 Visible" if not field["hidden"] else "👁️ Oculto"
			print(f'   - {field["fieldname"]}: {field["label"]} ({field["fieldtype"]}) {visibility}')

		# 4. Verificar si fm_producto_servicio_sat está en la lista
		producto_field = next(
			(f for f in sat_section_fields if f["fieldname"] == "fm_producto_servicio_sat"), None
		)

		if producto_field:
			print("\n✅ Campo fm_producto_servicio_sat encontrado en sección SAT")
			print(f'   Estado: {"Visible" if not producto_field["hidden"] else "Oculto"}')
		else:
			print("\n❌ Campo fm_producto_servicio_sat NO encontrado en sección SAT")

		# 5. Limpiar cache
		frappe.clear_cache()
		print("\n🔄 Cache limpiado")

		return {
			"success": True,
			"section_visible": not sat_section.hidden,
			"section_depends_on": sat_section.depends_on,
			"fields_in_section": len(sat_section_fields),
			"producto_field_found": bool(producto_field),
		}

	except Exception as e:
		print(f"💥 Error: {e!s}")
		return {"success": False, "error": str(e)}
