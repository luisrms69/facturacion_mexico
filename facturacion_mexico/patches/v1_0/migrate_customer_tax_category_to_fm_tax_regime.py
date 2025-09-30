import frappe
from frappe.utils import now

BATCH_SIZE = 500


def _exists_custom_field(dt: str, fieldname: str) -> bool:
	meta = frappe.get_meta(dt)
	return any(df.fieldname == fieldname for df in meta.fields)


def _nonempty(val) -> bool:
	return bool(val and str(val).strip())


def execute():
	"""
	MIGRACIÓN SEGURA: Customer.tax_category → Customer.fm_tax_regime (y limpieza condicional).
	- Idempotente y escalable (lotes).
	- Sin EXPECTED_COUNTS fijos: usa baseline dinámico.
	- Limpia tax_category SOLO si fm_tax_regime queda idéntico al original.
	- No crea campos: aborta si fm_tax_regime no existe (aplicar fixtures antes).
	- No usa commits manuales ni UPDATE SQL masivos.
	"""

	dt = "Customer"
	src = "tax_category"
	dst = "fm_tax_regime"

	print("=== PATCH: Customer.tax_category → Customer.fm_tax_regime ===")
	print(f"   Hora inicio: {now()}")

	# 0) Precondición: el custom field debe existir
	if not _exists_custom_field(dt, dst):
		frappe.throw(f"ABORT: Falta el custom field {dt}.{dst}. Aplica fixtures antes de correr el patch.")

	# 1) Baseline dinámico
	baseline_total_src = frappe.db.count(dt, {src: ["!=", ""]})
	baseline_dst_already = frappe.db.count(dt, {dst: ["!=", ""]})
	print(
		f"   Baseline: {baseline_total_src} customers con {src} poblado; {baseline_dst_already} ya tienen {dst}."
	)

	migrated = 0
	cleaned = 0
	mismatches = 0
	already_equal = 0

	# 2) FASE 1 — Migración (copiar donde haga falta)
	page_start = 0
	while True:
		rows = frappe.get_all(
			dt,
			filters={src: ["!=", ""]},
			fields=["name", src, dst],
			limit_start=page_start,
			limit_page_length=BATCH_SIZE,
			order_by="name asc",
		)
		if not rows:
			break
		for r in rows:
			src_val = (r.get(src) or "").strip()
			dst_val = (r.get(dst) or "").strip()

			if not _nonempty(src_val):
				continue

			# Caso 1: ya está copiado idéntico → nada que migrar
			if src_val == dst_val:
				already_equal += 1
				continue

			# Caso 2: destino vacío → copiar
			if not _nonempty(dst_val):
				frappe.db.set_value(dt, r["name"], dst, src_val, update_modified=False)
				migrated += 1
				continue

			# Caso 3: conflicto (dst tiene valor distinto) → NO tocar; reportar mismatch
			mismatches += 1
		page_start += BATCH_SIZE

	print(f"   Migrados: {migrated} | Ya iguales: {already_equal} | Conflictos (mismatch): {mismatches}")

	# 3) Validación intermedia — verificar que lo copiado quedó bien
	#    (Idempotente: si se re-ejecuta, no vuelve a migrar lo ya igual)
	#    No realizamos scans adicionales costosos; confiamos en set_value + lectura inmediata al limpiar.

	# 4) FASE 2 — Limpieza condicional: vaciar tax_category cuando QUEDÓ copiado idéntico en fm_tax_regime
	page_start = 0
	while True:
		rows = frappe.get_all(
			dt,
			filters={src: ["!=", ""]},
			fields=["name", src, dst],
			limit_start=page_start,
			limit_page_length=BATCH_SIZE,
			order_by="name asc",
		)
		if not rows:
			break
		for r in rows:
			src_val = (r.get(src) or "").strip()
			dst_val = (r.get(dst) or "").strip()

			# Solo limpiar cuando destino coincide 1:1 (seguro)
			if _nonempty(src_val) and src_val == dst_val:
				frappe.db.set_value(dt, r["name"], src, None, update_modified=False)
				cleaned += 1
		page_start += BATCH_SIZE

	# 5) Post-checks (verificación real, sin cifras "esperadas")
	remaining_src = frappe.db.count(dt, {src: ["!=", ""]})
	final_dst = frappe.db.count(dt, {dst: ["!=", ""]})

	print("=== RESULTADO FINAL ===")
	print(f"   Copias nuevas realizadas (fase 1): {migrated}")
	print(f"   Registros limpiados (fase 2): {cleaned}")
	print(f"   Conflictos detectados (no tocados): {mismatches}")
	print(f"   Aún con {src} poblado (deben revisarse): {remaining_src}")
	print(f"   Total con {dst} poblado post-patch: {final_dst}")
	print(f"   Hora fin: {now()}")

	# 6) Semántica de éxito:
	#    - Éxito "pleno": remaining_src == 0 (todos limpiados) y mismatches == 0
	#    - Éxito "parcial controlado": remaining_src > 0 por conflictos → requiere corrección manual
	if remaining_src == 0 and mismatches == 0:
		print("🎉 PATCH EXITOSO (pleno): Customer.tax_category migrado y limpiado completamente.")
	elif remaining_src == 0 and mismatches > 0:
		print(
			"✅ PATCH EXITOSO (con advertencias): Hay conflictos que ya estaban en datos; revisar los mismatches."
		)
	else:
		print("⚠️ PATCH PARCIAL: Aún quedan registros con tax_category poblado. Revisar datos/manual.")
