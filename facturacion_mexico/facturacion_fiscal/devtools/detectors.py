import frappe


def find_broken_table_fields():
	"""Detector meta-efectivo para encontrar Table fields problemáticos"""
	bad = []

	def _exists_dt(name: str) -> bool:
		return bool(name) and frappe.db.exists("DocType", name)

	print("=== DETECTOR META-EFECTIVO INICIANDO ===")
	print(f"SITIO: {frappe.local.site}")
	print(f"DB: {frappe.conf.db_name}")

	doctypes_processed = 0

	for dt in frappe.get_all("DocType", pluck="name"):
		try:
			meta = frappe.get_meta(dt)
			doctypes_processed += 1
		except Exception as e:
			bad.append(("META_ERROR", dt, repr(e)))
			print(f"! meta error: {dt} - {e!r}")
			continue

		for df in meta.fields:
			if df.fieldtype in ("Table", "Table MultiSelect"):
				opts = (df.options or "").strip()
				if not opts:
					bad.append((dt, df.fieldname, df.fieldtype, "EMPTY_OPTIONS"))
				elif not _exists_dt(opts):
					bad.append((dt, df.fieldname, df.fieldtype, f"CHILD_NOT_FOUND:{opts}"))

	print(f"\nDocTypes procesados: {doctypes_processed}")
	print("\n=== RESULTADO DEL DETECTOR ===")

	# imprime y devuelve (para que 'bench execute' lo muestre)
	if not bad:
		print("✅ OK: No hay Table/Table MultiSelect con options problemáticos.")
	else:
		print(f"🚨 PROBLEMAS ENCONTRADOS ({len(bad)} issues):")
		print("(DocType, fieldname, fieldtype, motivo)")
		for row in bad:
			print(f" - {row}")

	return bad
