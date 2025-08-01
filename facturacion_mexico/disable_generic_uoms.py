import frappe


def run():
	"""Desactivar UOMs genéricas ERPNext preservando las SAT"""

	print("🔧 Desactivando UOMs genéricas ERPNext...")

	try:
		# 1. Primero desactivar UOM Conversion Factors que involucren UOMs genéricas
		print("   Desactivando UOM Conversion Factors genéricos...")

		conversions_disabled = frappe.db.sql("""
            UPDATE `tabUOM Conversion Factor`
            SET disabled = 1
            WHERE (from_uom NOT LIKE '% - %' OR to_uom NOT LIKE '% - %')
            AND disabled = 0
        """)

		print(f"   ✅ UOM Conversion Factors desactivados")

		# 2. Desactivar UOMs genéricas (que no tienen formato SAT)
		print("   Desactivando UOMs genéricas...")

		# Obtener lista de UOMs que se van a desactivar
		generic_uoms = frappe.get_all(
			"UOM", filters={"uom_name": ["not like", "% - %"], "enabled": 1}, fields=["name", "uom_name"]
		)

		print(f"   Encontradas {len(generic_uoms)} UOMs genéricas para desactivar")

		# Desactivar en lotes
		disabled_count = 0
		for uom in generic_uoms[:10]:  # Mostrar solo primeras 10
			frappe.db.set_value("UOM", uom.name, "enabled", 0)
			disabled_count += 1
			print(f"   🔄 Desactivado: {uom.uom_name}")

		# Desactivar el resto sin mostrar
		if len(generic_uoms) > 10:
			for uom in generic_uoms[10:]:
				frappe.db.set_value("UOM", uom.name, "enabled", 0)
				disabled_count += 1

			print(f"   ... y {len(generic_uoms) - 10} UOMs más")

		# 3. Commit cambios
		frappe.db.commit()

		print(f"✅ Desactivación completada:")
		print(f"   UOMs desactivadas: {disabled_count}")
		print(f"   UOMs SAT activas: {frappe.db.count('UOM', {'uom_name': ['like', '% - %'], 'enabled': 1})}")

		return {
			"success": True,
			"uoms_disabled": disabled_count,
			"message": f"Desactivadas {disabled_count} UOMs genéricas",
		}

	except Exception as e:
		frappe.log_error(f"Error desactivando UOMs genéricas: {str(e)}", "UOM SAT Disable")
		print(f"💥 Error desactivando UOMs: {str(e)}")
		return {"success": False, "error": str(e)}
