import frappe


def run():
	"""Verificar por qué campo SAT Producto/Servicio no aparece en Item UI"""

	print("🔍 DIAGNÓSTICO CAMPO SAT PRODUCTO/SERVICIO EN ITEM UI")
	print("=" * 60)

	try:
		# 1. Verificar custom field detallado
		field_doc = frappe.get_doc("Custom Field", "Item-fm_producto_servicio_sat")

		print("📋 DETALLES CUSTOM FIELD:")
		print(f"   Fieldname: {field_doc.fieldname}")
		print(f"   Label: {field_doc.label}")
		print(f"   Fieldtype: {field_doc.fieldtype}")
		print(f"   Options: {field_doc.options}")
		print(f"   Hidden: {field_doc.hidden}")
		print(f"   Read Only: {field_doc.read_only}")
		print(f"   Insert After: {field_doc.insert_after}")
		print(f"   Depends On: {field_doc.depends_on}")
		print(f"   Mandatory: {field_doc.reqd}")
		print(f'   Section: {field_doc.fieldname.split("_")[0] if "_" in field_doc.fieldname else "N/A"}')

		# 2. Verificar orden de campos en Item
		meta = frappe.get_meta("Item")
		print("\n📊 POSICIÓN EN ITEM META:")

		# Buscar campos alrededor del fm_producto_servicio_sat
		found_field = False
		for i, field in enumerate(meta.fields):
			if field.fieldname == "fm_producto_servicio_sat":
				found_field = True
				print(f"   Posición: {i}")
				print(f'   Campo anterior: {meta.fields[i-1].fieldname if i > 0 else "N/A"}')
				print(
					f'   Campo siguiente: {meta.fields[i+1].fieldname if i < len(meta.fields)-1 else "N/A"}'
				)
				break

		if not found_field:
			print("   ❌ Campo NO encontrado en Item meta")
		else:
			print("   ✅ Campo encontrado en Item meta")

		# 3. Verificar si hay secciones o tabs que lo oculten
		sections = [f for f in meta.fields if f.fieldtype == "Section Break"]
		tabs = [f for f in meta.fields if f.fieldtype == "Tab Break"]

		print("\n📁 ESTRUCTURA UI:")
		print(f"   Secciones: {len(sections)}")
		print(f"   Tabs: {len(tabs)}")

		# Buscar la sección donde debería estar
		current_section = None
		for field in meta.fields:
			if field.fieldtype == "Section Break":
				current_section = field.fieldname
			elif field.fieldname == "fm_producto_servicio_sat":
				print(f"   Sección actual: {current_section}")
				break

		# 4. Verificar permisos
		print("\n🔐 PERMISOS:")
		roles = frappe.get_roles()
		print(f"   Roles usuario: {roles[:3]}...")

		# 5. Probar crear un Item para ver si aparece
		print("\n🧪 TEST CREACIÓN ITEM:")
		test_meta = frappe.get_meta("Item")
		visible_fields = [
			f.fieldname
			for f in test_meta.fields
			if not f.hidden and f.fieldtype not in ["Section Break", "Column Break", "Tab Break"]
		]

		if "fm_producto_servicio_sat" in visible_fields:
			print("   ✅ Campo debería ser visible")
		else:
			print("   ❌ Campo no está en campos visibles")

		return {
			"success": True,
			"field_found": found_field,
			"visible": "fm_producto_servicio_sat" in visible_fields,
			"section": current_section,
		}

	except Exception as e:
		print(f"💥 Error: {e!s}")
		return {"success": False, "error": str(e)}
