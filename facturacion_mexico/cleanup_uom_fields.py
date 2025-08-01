import frappe


def run():
	"""Limpiar Custom Fields UOM problemáticos antes de población SAT"""

	print("🧹 Limpiando Custom Fields UOM problemáticos...")

	# Custom Fields UOM que causan problemas
	problematic_fields = [
		"fm_sat_section",
		"fm_clave_sat",
		"fm_mapping_confidence",
		"fm_mapping_source",
		"fm_last_sync_date",
		"fm_mapping_verified",
	]

	deleted = 0

	for field_name in problematic_fields:
		try:
			if frappe.db.exists("Custom Field", {"dt": "UOM", "fieldname": field_name}):
				frappe.delete_doc("Custom Field", f"UOM-{field_name}")
				deleted += 1
				print(f"🗑️  Eliminado: UOM-{field_name}")
		except Exception as e:
			print(f"⚠️  Error eliminando {field_name}: {e!s}")

	if deleted > 0:
		frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to persist UOM field cleanup before population
		frappe.clear_cache()
		print(f"✅ Eliminados {deleted} Custom Fields problemáticos")
		print("🔄 Cache limpiado - listo para población UOM")
	else:
		print("✅ No se encontraron Custom Fields problemáticos")

	return {"deleted": deleted}
