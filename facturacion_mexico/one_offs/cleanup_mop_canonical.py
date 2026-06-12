"""
one_off: cleanup_mop_canonical

Elimina registros Mode of Payment con formato canónico "NN - Descripción"
dejados por fixtures anteriores de facturacion_mexico.

El estándar actual del app es "NN Descripción" (sin guion). Los registros
canónicos con guion ya no corresponden a ningún fixture activo y no deben
estar disponibles en selectores.

Uso (siempre dry_run primero):
    bench --site <site> execute facturacion_mexico.one_offs.cleanup_mop_canonical.run
    bench --site <site> execute facturacion_mexico.one_offs.cleanup_mop_canonical.run --kwargs "{'dry_run': False}"

IMPORTANTE: No ejecutar dry_run=False hasta revisar el reporte completo.
"""

import frappe

# DocTypes que tienen Link a Mode of Payment en facturacion_mexico.
# Actualizar si se agregan nuevos Link fields al app.
_LINK_FIELDS = [
	("Payment Entry", "mode_of_payment"),
	("Factura Fiscal Mexico", "fm_forma_pago_timbrado"),
]


def run(dry_run: bool = True) -> None:
	modo = "DRY RUN" if dry_run else "EJECUCIÓN REAL"
	print(f"\n{'=' * 60}")
	print(f"  cleanup_mop_canonical — {modo}")
	print(f"{'=' * 60}\n")

	# 1. Detectar registros canónicos con guion
	canonical = frappe.db.sql(
		"SELECT name FROM `tabMode of Payment` WHERE name REGEXP %s ORDER BY name",
		(r"^[0-9]{2} - ",),
		as_dict=True,
	)

	if not canonical:
		print("✅ No hay registros Mode of Payment con formato canónico (NN - Descripción).")
		print("   Nada que limpiar.\n")
		return

	print(f"Encontrados {len(canonical)} registros con formato canónico:\n")

	can_delete = []
	cannot_delete = []

	for mop in canonical:
		name = mop.name
		# Equivalente sin guion (para verificar que ya existe la versión correcta)
		legacy_name = name.replace(" - ", " ", 1)
		legacy_exists = frappe.db.exists("Mode of Payment", legacy_name)

		# 2. Revisar todas las referencias Link
		refs = {}
		for doctype, fieldname in _LINK_FIELDS:
			count = frappe.db.count(doctype, {fieldname: name})
			if count:
				refs[f"{doctype}.{fieldname}"] = count

		if refs:
			cannot_delete.append({"name": name, "legacy": legacy_name, "refs": refs})
		else:
			can_delete.append({"name": name, "legacy": legacy_name, "legacy_exists": bool(legacy_exists)})

	# 3. Reporte — pueden borrarse
	print(f"{'─' * 60}")
	print(f"✅ SIN REFERENCIAS — pueden eliminarse: {len(can_delete)}\n")
	for r in can_delete:
		legacy_status = "✅ existe" if r["legacy_exists"] else "⚠️  NO existe"
		print(f"   • {r['name']}")
		print(f"     Equivalente legacy: {r['legacy']} → {legacy_status}")

	# 4. Reporte — no pueden borrarse
	print(f"\n{'─' * 60}")
	print(f"⛔ CON REFERENCIAS — no se borrarán: {len(cannot_delete)}\n")
	for r in cannot_delete:
		print(f"   • {r['name']}")
		for ref_field, count in r["refs"].items():
			print(f"     └─ {ref_field}: {count} documento(s)")

	print(f"\n{'─' * 60}")

	if dry_run:
		print("INFO: MODO DRY RUN — no se eliminó nada.")
		print("   Para ejecutar: --kwargs '{\"dry_run\": False}'\n")
		return

	# 5. Ejecución real — solo registros sin referencias
	if not can_delete:
		print("⚠️  No hay registros elegibles para borrar. Nada que hacer.\n")
		return

	print(f"\n🗑️  Eliminando {len(can_delete)} registros...\n")
	deleted = []
	errors = []

	for r in can_delete:
		try:
			# Sin ignore_links — Frappe verifica referencias adicionales en FK de BD
			frappe.delete_doc("Mode of Payment", r["name"], ignore_permissions=True)
			deleted.append(r["name"])
			print(f"   ✅ Eliminado: {r['name']}")
		except Exception as e:
			errors.append({"name": r["name"], "error": str(e)})
			print(f"   ❌ Error al eliminar {r['name']}: {e}")

	frappe.db.commit()

	print(f"\n{'=' * 60}")
	print(f"  Resultado: {len(deleted)} eliminados, {len(errors)} errores, {len(cannot_delete)} conservados")
	print(f"{'=' * 60}\n")
