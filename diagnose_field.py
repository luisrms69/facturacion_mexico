#!/usr/bin/env python3

import frappe


def execute():
	"""Diagnosticar problema con fm_producto_servicio_sat"""

	print("=== DIAGNÓSTICO fm_producto_servicio_sat ===")

	# 1. Buscar en Custom Field
	custom_fields = frappe.get_all(
		"Custom Field",
		filters={"fieldname": "fm_producto_servicio_sat"},
		fields=["name", "dt", "fieldtype", "options"],
	)
	print(f"Custom Fields encontrados: {custom_fields}")

	# 2. Verificar DocType SAT Producto Servicio existe
	sat_doctype_exists = frappe.db.exists("DocType", "SAT Producto Servicio")
	print(f"DocType SAT Producto Servicio existe: {sat_doctype_exists}")

	# 3. Verificar registros en SAT Producto Servicio
	if sat_doctype_exists:
		count = frappe.db.count("SAT Producto Servicio")
		print(f"Registros en SAT Producto Servicio: {count}")

	# 4. Buscar el campo en tabItem directamente
	try:
		result = frappe.db.sql("DESCRIBE tabItem")
		producto_servicio_found = False
		for row in result:
			if "fm_producto_servicio_sat" in str(row):
				print(f"Campo en tabla: {row}")
				producto_servicio_found = True
		if not producto_servicio_found:
			print("Campo fm_producto_servicio_sat NO encontrado en tabla Item")
	except Exception as e:
		print(f"Error verificando tabla: {e}")

	# 5. Intentar crear el campo para ver el error específico
	try:
		if not frappe.db.exists("Custom Field", "Item-fm_producto_servicio_sat"):
			print("Intentando crear campo...")
			custom_field = frappe.get_doc(
				{
					"doctype": "Custom Field",
					"dt": "Item",
					"fieldname": "fm_producto_servicio_sat",
					"fieldtype": "Link",
					"options": "SAT Producto Servicio",
					"label": "SAT Producto/Servicio",
					"insert_after": "fm_column_break_item_sat",
				}
			)
			custom_field.insert()
			frappe.db.commit()
			print("✅ Campo fm_producto_servicio_sat creado exitosamente")
		else:
			print("⚠️ Campo ya existe")
	except Exception as e:
		print(f"❌ Error creando campo: {e}")
		print(f"Tipo de error: {type(e)}")

	return "Diagnóstico completado"
