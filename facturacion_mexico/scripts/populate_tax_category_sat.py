import frappe


def run():
	"""Poblar Tax Category con Regímenes Fiscales SAT"""

	# Verificar si ya se ejecutó este script
	existing_sat_categories = frappe.db.count("Tax Category", {"title": ["like", "%-%"]})
	if existing_sat_categories >= 20:
		print(f"⚠️  Script ya ejecutado anteriormente. Encontrados {existing_sat_categories} Tax Category SAT")
		print("   Para re-ejecutar, elimine primero las Tax Category con formato 'XXX - Descripción'")
		return {"created": 0, "updated": 0, "skipped": existing_sat_categories}

	# Obtener todos los regímenes fiscales SAT disponibles
	sat_regimenes = frappe.get_all("Regimen Fiscal SAT", fields=["code", "description"], order_by="code")

	created_count = 0
	updated_count = 0

	for regimen in sat_regimenes:
		# Crear nombre de Tax Category: "601 - General de Ley Personas Morales"
		category_name = f"{regimen.code} - {regimen.description}"

		# Verificar si ya existe
		if not frappe.db.exists("Tax Category", category_name):
			# Crear nueva Tax Category
			category_doc = frappe.get_doc(
				{
					"doctype": "Tax Category",
					"title": category_name,
					"disabled": 0,  # Habilitada por defecto
				}
			)

			category_doc.insert()
			created_count += 1
			print(f"✅ Creado: {category_name}")
		else:
			# Asegurar que esté habilitada
			existing_category = frappe.get_doc("Tax Category", category_name)
			if existing_category.disabled:
				existing_category.disabled = 0
				existing_category.save()
				updated_count += 1
				print(f"🔄 Habilitado: {category_name}")

	frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to persist Tax Categories SAT population

	print("\n📊 RESUMEN:")
	print(f"   Creados: {created_count}")
	print(f"   Actualizados: {updated_count}")
	print(f"   Total regímenes SAT: {len(sat_regimenes)}")

	return {"created": created_count, "updated": updated_count}
