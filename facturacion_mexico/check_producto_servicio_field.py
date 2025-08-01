import frappe


def run():
	"""Verificar campo fm_producto_servicio_sat en Item"""

	print("=== DIAGNÓSTICO fm_producto_servicio_sat ===")

	try:
		# 1. Verificar si custom field existe
		field = frappe.db.get_value(
			"Custom Field",
			"Item-fm_producto_servicio_sat",
			["fieldname", "label", "fieldtype", "options", "hidden"],
			as_dict=True,
		)

		if field:
			print(f"✅ Custom Field existe: {field}")
		else:
			print("❌ Custom Field NO existe")

		# 2. Verificar en metadata de Item
		meta = frappe.get_meta("Item")
		producto_fields = [f for f in meta.fields if "producto" in f.fieldname.lower()]

		print(f"\n📋 Campos producto en Item ({len(producto_fields)}):")
		for field in producto_fields:
			print(f"  - {field.fieldname}: {field.label} ({field.fieldtype}) - Hidden: {field.hidden}")

		# 3. Verificar si hay catálogo SAT Producto Servicio
		count_productos = frappe.db.count("SAT Producto Servicio")
		print(f"\n📊 Registros SAT Producto Servicio: {count_productos}")

		if count_productos > 0:
			# Primero verificar estructura
			meta_sat = frappe.get_meta("SAT Producto Servicio")
			print("   Campos disponibles:")
			for field in meta_sat.fields[:5]:
				print(f"   - {field.fieldname}: {field.label}")

			samples = frappe.get_all("SAT Producto Servicio", fields=["name"], limit=3)
			print("   Ejemplos:")
			for sample in samples:
				print(f"   - {sample.name}")

		# 4. Verificar si field está oculto o con depends_on
		if frappe.db.exists("Custom Field", "Item-fm_producto_servicio_sat"):
			field_details = frappe.get_doc("Custom Field", "Item-fm_producto_servicio_sat")
			print(f"\n🔍 Detalles campo:")
			print(f"   Hidden: {field_details.hidden}")
			print(f"   Depends on: {field_details.depends_on}")
			print(f"   Read only: {field_details.read_only}")
			print(f"   Options: {field_details.options}")

		return {"success": True, "fields_found": len(producto_fields)}

	except Exception as e:
		print(f"💥 Error: {str(e)}")
		return {"success": False, "error": str(e)}
