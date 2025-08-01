import frappe


def run():
	"""Poblar UOM nativo con 20 unidades SAT principales - VERSION SIMPLE"""

	# Verificar si ya se ejecutó
	existing_sat_uoms = frappe.db.count("UOM", {"uom_name": ["like", "% - %"]})
	if existing_sat_uoms >= 18:
		print(f"⚠️  Script ya ejecutado. Encontradas {existing_sat_uoms} UOMs SAT")
		return {"created": 0, "updated": 0, "skipped": existing_sat_uoms}

	# 20 UOMs SAT principales
	sat_uoms = [
		{"code": "H87", "name": "Pieza"},
		{"code": "KGM", "name": "Kilogramo"},
		{"code": "GRM", "name": "Gramo"},
		{"code": "LTR", "name": "Litro"},
		{"code": "MLT", "name": "Mililitro"},
		{"code": "MTR", "name": "Metro"},
		{"code": "CMT", "name": "Centímetro"},
		{"code": "MMT", "name": "Milímetro"},
		{"code": "MTK", "name": "Metro cuadrado"},
		{"code": "MTQ", "name": "Metro cúbico"},
		{"code": "HUR", "name": "Hora"},
		{"code": "MIN", "name": "Minuto"},
		{"code": "SEC", "name": "Segundo"},
		{"code": "DAY", "name": "Día"},
		{"code": "E48", "name": "Servicio"},
		{"code": "ACT", "name": "Actividad"},
		{"code": "E51", "name": "Trabajo"},
		{"code": "MON", "name": "Mes"},
		{"code": "ANN", "name": "Año"},
		{"code": "NA", "name": "No Aplica"},
	]

	created = 0
	updated = 0

	for uom_data in sat_uoms:
		uom_name = f"{uom_data['code']} - {uom_data['name']}"

		if frappe.db.exists("UOM", uom_name):
			# Activar si está desactivado
			uom_doc = frappe.get_doc("UOM", uom_name)
			if not uom_doc.enabled:
				uom_doc.enabled = 1
				uom_doc.save()
				updated += 1
				print(f"🔄 Activado: {uom_name}")
		else:
			# Crear nuevo UOM
			uom_doc = frappe.get_doc(
				{"doctype": "UOM", "uom_name": uom_name, "enabled": 1, "must_be_whole_number": 0}
			)

			uom_doc.insert(ignore_permissions=True)
			created += 1
			print(f"✅ Creado: {uom_name}")

	frappe.db.commit()

	print("\n📊 RESUMEN:")
	print(f"   Creadas: {created}")
	print(f"   Actualizadas: {updated}")

	return {"created": created, "updated": updated}
