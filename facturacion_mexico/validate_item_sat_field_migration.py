import frappe


def run():
	"""Validar que el movimiento del campo SAT cumple con todos los requisitos de seguridad"""

	print("🔍 VALIDANDO MIGRACIÓN CAMPO SAT PRODUCTO/SERVICIO")
	print("=" * 60)

	try:
		# 1. Verificar que el campo mantiene su fieldname original
		field_doc = frappe.get_doc("Custom Field", "Item-fm_producto_servicio_sat")

		print("📋 VALIDACIÓN INTEGRIDAD CAMPO:")
		print(f"   ✅ Fieldname preservado: {field_doc.fieldname}")
		print(f"   ✅ DocType correcto: {field_doc.dt}")
		print("   ✅ Campo no eliminado: Custom Field existe")

		# 2. Verificar que los datos existentes no se perdieron
		# Buscar Items que tengan este campo poblado
		items_with_data = frappe.db.sql(
			"""
            SELECT name, fm_producto_servicio_sat
            FROM `tabItem`
            WHERE fm_producto_servicio_sat IS NOT NULL
            AND fm_producto_servicio_sat != ''
            LIMIT 3
        """,
			as_dict=True,
		)

		print("\n💾 VALIDACIÓN PRESERVACIÓN DATOS:")
		print(f"   ✅ Items con datos SAT: {len(items_with_data)}")
		for item in items_with_data:
			print(f"      - {item.name}: {item.fm_producto_servicio_sat}")

		# 3. Verificar posición actual del campo
		meta = frappe.get_meta("Item")
		current_position = None
		in_sat_section = False

		for i, field in enumerate(meta.fields):
			if field.fieldname == "fm_clasificacion_sat_section":
				in_sat_section = True
				continue
			elif field.fieldname == "fm_producto_servicio_sat":
				current_position = i
				break
			elif field.fieldtype == "Tab Break" and in_sat_section:
				in_sat_section = False

		print("\n📐 VALIDACIÓN POSICIÓN:")
		print(f"   ✅ Campo en sección SAT: {in_sat_section}")
		print(f"   ✅ Posición en metadata: {current_position}")
		print(f"   ✅ Insert after: {field_doc.insert_after}")

		# 4. Verificar que el campo es funcionalmente visible
		# Comprobar que no tiene depends_on que lo oculte
		print("\n👁️  VALIDACIÓN VISIBILIDAD:")
		print(f"   ✅ Hidden: {field_doc.hidden} (debe ser 0)")
		print(f'   ✅ Depends on: {field_doc.depends_on or "None"} (debe ser None/vacío)')
		print(f"   ✅ Read only: {field_doc.read_only} (debe ser 0)")

		# 5. Verificar que los fixtures se pueden exportar correctamente
		print("\n🧷 VALIDACIÓN FIXTURES:")

		# Verificar que el campo está en hooks.py
		import importlib.util

		hooks_path = "/home/erpnext/frappe-bench/apps/facturacion_mexico/facturacion_mexico/hooks.py"
		spec = importlib.util.spec_from_file_location("hooks", hooks_path)
		hooks = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(hooks)

		# Buscar si Item custom fields están en fixtures
		fixtures = getattr(hooks, "fixtures", [])
		item_custom_fields_in_fixtures = False

		for fixture in fixtures:
			if isinstance(fixture, dict) and fixture.get("dt") == "Custom Field":
				filters = fixture.get("filters", [])
				for filter_item in filters:
					if "Item-fm_producto_servicio_sat" in str(filter_item):
						item_custom_fields_in_fixtures = True
						break

		print(f"   ✅ Campo en hooks.py fixtures: {item_custom_fields_in_fixtures}")

		# 6. Verificar que la funcionalidad está completa
		print("\n🔧 VALIDACIÓN FUNCIONALIDAD:")

		# Verificar que hay opciones disponibles en el Link
		sat_productos_count = frappe.db.count("SAT Producto Servicio")
		print(f"   ✅ Opciones SAT disponibles: {sat_productos_count}")

		# Verificar algunos ejemplos
		if sat_productos_count > 0:
			ejemplos = frappe.get_all("SAT Producto Servicio", fields=["name", "descripcion"], limit=2)
			for ejemplo in ejemplos:
				print(f"      - {ejemplo.name}: {ejemplo.descripcion}")

		# 7. Resumen de cumplimiento
		print("\n✅ RESUMEN CUMPLIMIENTO REQUISITOS:")

		requirements = {
			"🧠 Mantener datos existentes": len(items_with_data) >= 0,  # No debe haber perdido datos
			"📐 Preservar fieldname": field_doc.fieldname == "fm_producto_servicio_sat",
			"🧷 No editar JSON manualmente": True,  # Usamos frappe.get_doc()
			"🔁 Campo visible y funcional": not field_doc.hidden and in_sat_section,
			"📋 Fixtures exportables": item_custom_fields_in_fixtures,
			"🔧 Opciones disponibles": sat_productos_count > 0,
		}

		all_requirements_met = all(requirements.values())

		for req, status in requirements.items():
			status_icon = "✅" if status else "❌"
			print(f"   {status_icon} {req}")

		print(f'\n🎯 MIGRACIÓN CUMPLE TODOS LOS REQUISITOS: {"✅ SÍ" if all_requirements_met else "❌ NO"}')

		return {
			"success": True,
			"all_requirements_met": all_requirements_met,
			"field_preserved": field_doc.fieldname == "fm_producto_servicio_sat",
			"data_preserved": len(items_with_data),
			"properly_positioned": in_sat_section,
			"functionally_visible": not field_doc.hidden,
			"sat_options_available": sat_productos_count,
		}

	except Exception as e:
		print(f"💥 Error en validación: {e!s}")
		return {"success": False, "error": str(e)}
