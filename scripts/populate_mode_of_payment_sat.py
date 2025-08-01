import frappe


def run():
	"""Poblar Mode of Payment con Formas de Pago SAT principales"""

	# Verificar si ya se ejecutó este script
	existing_sat_modes = frappe.db.count("Mode of Payment", {"name": ["like", "%-%"]})
	if existing_sat_modes >= 20:
		print(f"⚠️  Script ya ejecutado anteriormente. Encontrados {existing_sat_modes} Mode of Payment SAT")
		print("   Para re-ejecutar, elimine primero los Mode of Payment con formato 'XX - Descripción'")
		return {"created": 0, "updated": 0, "skipped": existing_sat_modes}

	# Obtener todas las formas SAT disponibles
	sat_forms = frappe.get_all("Forma Pago SAT", fields=["name", "description"], order_by="name")

	created_count = 0
	updated_count = 0

	for sat_form in sat_forms:
		# Crear nombre del Mode of Payment: "01 - Efectivo"
		mode_name = f"{sat_form.name} - {sat_form.description}"

		# Verificar si ya existe
		if not frappe.db.exists("Mode of Payment", mode_name):
			# Crear nuevo Mode of Payment
			mode_doc = frappe.get_doc(
				{
					"doctype": "Mode of Payment",
					"mode_of_payment": mode_name,
					"enabled": 1,
					"type": "General",  # Tipo por defecto
				}
			)

			mode_doc.insert()
			created_count += 1
			print(f"✅ Creado: {mode_name}")
		else:
			# Asegurar que esté habilitado
			existing_mode = frappe.get_doc("Mode of Payment", mode_name)
			if not existing_mode.enabled:
				existing_mode.enabled = 1
				existing_mode.save()
				updated_count += 1
				print(f"🔄 Habilitado: {mode_name}")

	frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to persist Mode of Payment SAT population

	print("\n📊 RESUMEN:")
	print(f"   Creados: {created_count}")
	print(f"   Actualizados: {updated_count}")
	print(f"   Total formas SAT: {len(sat_forms)}")

	return {"created": created_count, "updated": updated_count}
