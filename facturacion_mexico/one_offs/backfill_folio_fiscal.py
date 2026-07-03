"""Backfill one-off de Sales Invoice.fm_folio_fiscal (cache de folio fiscal para CxC).

Recorre las Sales Invoice con FFM ligada o con folio ya poblado, y sincroniza
`fm_folio_fiscal` con el folio (UUID) del CFDI VIGENTE usando el mismo helper que el flujo
en vivo: `facturacion_fiscal.utils.sincronizar_folio_fiscal`.

- Idempotente y repetible. Sin FacturAPI (solo lee campos internos ya persistidos).
- Dry-run por DEFAULT: `apply=0` no escribe nada, solo clasifica y reporta.
- Modo escritura explícito: `apply=1`.

Uso (dry-run, no escribe):
    bench --site <site> execute facturacion_mexico.one_offs.backfill_folio_fiscal.run

Uso (escritura real — MODIFICA LA BASE DE DATOS):
    bench --site <site> execute facturacion_mexico.one_offs.backfill_folio_fiscal.run --kwargs "{'apply': 1}"

Reporta: revisadas, actualizadas, limpiadas, sin_cambio, errores.
"""

import frappe

from facturacion_mexico.facturacion_fiscal.utils import (
	_FOLIO_VIGENTE_STATES,
	sincronizar_folio_fiscal,
)


def _folio_vigente_esperado(si_name):
	"""Read-only: folio que DEBERÍA tener la SI (misma regla que el helper), sin escribir."""
	ffm = frappe.db.get_value("Sales Invoice", si_name, "fm_factura_fiscal_mx")
	if not ffm:
		return ""
	row = frappe.db.get_value("Factura Fiscal Mexico", ffm, ["status", "fm_uuid"], as_dict=True)
	if row and (row.fm_uuid or "").strip() and row.status in _FOLIO_VIGENTE_STATES:
		return row.fm_uuid.strip()
	return ""


def run(apply=0):
	"""Backfill de fm_folio_fiscal. apply=0 (default) → dry-run; apply=1 → escribe."""
	apply = int(apply)
	stats = {"revisadas": 0, "actualizadas": 0, "limpiadas": 0, "sin_cambio": 0, "errores": 0}
	ejemplos = {"actualizadas": [], "limpiadas": [], "sin_cambio": []}
	MAX_EJEMPLOS = 3

	def _muestra(categoria, name, current, desired):
		if len(ejemplos[categoria]) < MAX_EJEMPLOS:
			ejemplos[categoria].append((name, current, desired))

	# Alcance: SIs con FFM ligada (a poblar) o con folio ya escrito (a reverificar/limpiar).
	names = frappe.get_all(
		"Sales Invoice",
		or_filters=[["fm_factura_fiscal_mx", "!=", ""], ["fm_folio_fiscal", "!=", ""]],
		pluck="name",
	)

	for name in names:
		stats["revisadas"] += 1
		try:
			current = frappe.db.get_value("Sales Invoice", name, "fm_folio_fiscal") or ""
			desired = _folio_vigente_esperado(name)

			if current == desired:
				stats["sin_cambio"] += 1
				_muestra("sin_cambio", name, current, desired)
				continue

			categoria = "actualizadas" if desired else "limpiadas"
			stats[categoria] += 1
			_muestra(categoria, name, current, desired)

			if apply:
				# Escritura autoritativa vía el mismo helper del flujo en vivo
				sincronizar_folio_fiscal(name)
		except Exception as e:
			stats["errores"] += 1
			frappe.log_error(f"Backfill folio fiscal falló en {name}: {e!s}", "Backfill Folio Fiscal Error")

	if apply:
		frappe.db.commit()

	modo = "ESCRITURA (apply=1)" if apply else "DRY-RUN (apply=0, sin cambios)"
	print("=" * 60)
	print(f"Backfill fm_folio_fiscal — {modo}")
	print("-" * 60)
	print(f"  Revisadas:   {stats['revisadas']}")
	print(f"  Actualizadas:{stats['actualizadas']:>6}  (se poblaría/pobló un folio vigente)")
	print(f"  Limpiadas:   {stats['limpiadas']:>6}  (folio obsoleto → vacío)")
	print(f"  Sin cambio:  {stats['sin_cambio']:>6}")
	print(f"  Errores:     {stats['errores']:>6}")
	print("=" * 60)

	# Ejemplos por categoría (hasta 3): (Sales Invoice, folio_actual, folio_esperado)
	for categoria in ("actualizadas", "limpiadas", "sin_cambio"):
		if ejemplos[categoria]:
			print(f"Ejemplos [{categoria}]:")
			for name, current, desired in ejemplos[categoria]:
				print(f"  - {name}: actual={current or '∅'} → esperado={desired or '∅'}")

	if not apply:
		print("DRY-RUN: no se escribió nada. Para aplicar: --kwargs \"{'apply': 1}\"")

	return stats
