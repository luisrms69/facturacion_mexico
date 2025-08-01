import frappe


def run():
	"""Desactivar UOMs genéricas - versión simple sin conversiones"""

	print("🔧 Desactivando UOMs genéricas ERPNext (simple)...")

	try:
		# Obtener UOMs genéricas activas
		generic_uoms = frappe.get_all(
			"UOM", filters={"uom_name": ["not like", "% - %"], "enabled": 1}, fields=["name", "uom_name"]
		)

		print(f"   Encontradas {len(generic_uoms)} UOMs genéricas para desactivar")

		if len(generic_uoms) == 0:
			print("✅ No hay UOMs genéricas para desactivar")
			return {"success": True, "uoms_disabled": 0}

		# Desactivar en lotes, mostrando progreso
		disabled_count = 0

		# Mostrar primeras 5
		for i, uom in enumerate(generic_uoms[:5]):
			frappe.db.set_value("UOM", uom.name, "enabled", 0)
			disabled_count += 1
			print(f"   🔄 [{i+1}] Desactivado: {uom.uom_name}")

		# Desactivar el resto silenciosamente
		if len(generic_uoms) > 5:
			print(f"   🔄 Desactivando {len(generic_uoms) - 5} UOMs más...")

			for uom in generic_uoms[5:]:
				frappe.db.set_value("UOM", uom.name, "enabled", 0)
				disabled_count += 1

		# Commit cambios
		frappe.db.commit()

		# Verificar estado final
		remaining_generic = frappe.db.count("UOM", {"uom_name": ["not like", "% - %"], "enabled": 1})
		sat_active = frappe.db.count("UOM", {"uom_name": ["like", "% - %"], "enabled": 1})

		print("✅ Desactivación completada:")
		print(f"   UOMs desactivadas: {disabled_count}")
		print(f"   UOMs genéricas restantes: {remaining_generic}")
		print(f"   UOMs SAT activas: {sat_active}")

		return {
			"success": True,
			"uoms_disabled": disabled_count,
			"remaining_generic": remaining_generic,
			"sat_active": sat_active,
		}

	except Exception as e:
		print(f"💥 Error: {e!s}")
		return {"success": False, "error": str(e)}
