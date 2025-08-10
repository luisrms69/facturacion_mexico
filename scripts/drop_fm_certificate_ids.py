#!/usr/bin/env python3
"""
Script idempotente para eliminar Custom Field Branch.fm_certificate_ids
Procedimiento robusto paso 1.1-1.2 según documentación experta Frappe
"""

import frappe


def drop_cf_and_ps():
	"""Eliminar Custom Field y Property Setters - Idempotente"""

	DT = "Branch"
	FIELD = "fm_certificate_ids"

	print(f"🔍 Procesando eliminación: {DT}.{FIELD}")

	# borrar Custom Field si existe
	cf_name = frappe.db.get_value("Custom Field", {"dt": DT, "fieldname": FIELD}, "name")
	if cf_name:
		frappe.delete_doc("Custom Field", cf_name, force=1, ignore_permissions=True)
		print(f"✅ Custom Field eliminado: {cf_name}")
	else:
		print("✅ Custom Field no existe (ok).")

	# borrar Property Setters para este field (por si alguien tocó fieldtype/options)
	ps_list = frappe.get_all("Property Setter", filters={"doc_type": DT, "field_name": FIELD}, pluck="name")
	for ps in ps_list:
		frappe.delete_doc("Property Setter", ps, force=1, ignore_permissions=True)
		print(f"✅ Property Setter eliminado: {ps}")

	if not ps_list:
		print("✅ No hay Property Setters para este campo (ok).")

	# Commit cambios - Required to ensure Custom Field elimination is persisted before verification
	frappe.db.commit()  # nosemgrep: frappe-manual-commit
	print("💾 Cambios confirmados en BD")

	# Verificación columna tabla (esperado: False para Table MultiSelect)
	has_col = frappe.db.has_column("Branch", FIELD)
	print(f"🔍 ¿Columna en tabBranch?: {has_col} (esperado: False)")

	print("🎯 Eliminación Custom Field completada exitosamente")
	return True


# Ejecutar función
if __name__ == "__main__":
	drop_cf_and_ps()
