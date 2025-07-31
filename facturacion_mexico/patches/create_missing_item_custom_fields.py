import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""Create missing Item custom fields - Issue #31 Critical Migration."""

	print("🔧 PATCH: Creando custom fields faltantes de Item...")

	# Campos que deben existir según la definición original
	item_fields = {
		"Item": [
			{
				"fieldname": "fm_producto_servicio_sat",
				"fieldtype": "Link",
				"label": "Código Producto/Servicio SAT",
				"options": "SAT Producto Servicio",
				"insert_after": "fm_clasificacion_sat_section",
				"translatable": 0,
			},
			{
				"fieldname": "fm_column_break_item_sat",
				"fieldtype": "Column Break",
				"insert_after": "fm_producto_servicio_sat",
			},
			{
				"fieldname": "fm_unidad_sat",
				"fieldtype": "Data",
				"label": "Código Unidad SAT",
				"insert_after": "fm_column_break_item_sat",
				"translatable": 0,
			},
		]
	}

	try:
		# Verificar si ya existen antes de crear
		existing_fields = []
		missing_fields = []

		for field_def in item_fields["Item"]:
			field_name = f"Item-{field_def['fieldname']}"
			if frappe.db.exists("Custom Field", field_name):
				existing_fields.append(field_name)
				print(f"✅ {field_name} ya existe")
			else:
				missing_fields.append(field_name)
				print(f"❌ {field_name} faltante - será creado")

		if missing_fields:
			# Crear solo los campos faltantes
			create_custom_fields(item_fields)
			print(f"✅ {len(missing_fields)} custom fields de Item creados exitosamente")

			# Verificar creación
			for field_def in item_fields["Item"]:
				field_name = f"Item-{field_def['fieldname']}"
				if frappe.db.exists("Custom Field", field_name):
					print(f"✅ Verificado: {field_name}")
				else:
					print(f"❌ Falló verificación: {field_name}")
		else:
			print("✅ Todos los custom fields de Item ya existen")

	except Exception as e:
		print(f"❌ Error en patch Item custom fields: {e}")
		import traceback

		traceback.print_exc()
		raise

	print("🎯 PATCH completado - Issue #31 Item custom fields migration")
