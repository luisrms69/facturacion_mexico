"""Backfill one-off de Sales Invoice.fm_folio_fiscal (cache de folio fiscal para CxC).

Recorre las Sales Invoice con FFM ligada o con folio ya poblado, y sincroniza
`fm_folio_fiscal` con el folio consecutivo (FFM.folio) del CFDI VIGENTE usando el mismo
helper que el flujo en vivo: `facturacion_fiscal.utils.sincronizar_folio_fiscal`.

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
	resolver_folio_vigente,
	sincronizar_folio_fiscal,
)


def run(apply=0):
	"""Backfill de fm_folio_fiscal. apply=0 (default) → dry-run; apply=1 → escribe."""
	apply = int(apply)
	stats = {"revisadas": 0, "actualizadas": 0, "limpiadas": 0, "sin_cambio": 0, "errores": 0}
	examples = {"actualizadas": [], "limpiadas": [], "sin_cambio": []}
	max_examples = 3

	def record_example(category, name, current, expected):
		if len(examples[category]) < max_examples:
			examples[category].append((name, current, expected))

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
			expected = resolver_folio_vigente(name)

			if current == expected:
				stats["sin_cambio"] += 1
				record_example("sin_cambio", name, current, expected)
				continue

			category = "actualizadas" if expected else "limpiadas"
			stats[category] += 1
			record_example(category, name, current, expected)

			if apply:
				# Escritura autoritativa vía el mismo helper del flujo en vivo
				sincronizar_folio_fiscal(name)
		except Exception as e:
			stats["errores"] += 1
			frappe.log_error(f"Backfill folio fiscal falló en {name}: {e!s}", "Backfill Folio Fiscal Error")

	if apply:
		# One-off manual vía `bench execute`: el commit explícito es necesario para persistir
		# (no corre dentro de una request web con auto-commit).
		frappe.db.commit()  # nosemgrep

	mode = "ESCRITURA (apply=1)" if apply else "DRY-RUN (apply=0, sin cambios)"
	print("=" * 60)
	print(f"Backfill fm_folio_fiscal — {mode}")
	print("-" * 60)
	print(f"  Revisadas:   {stats['revisadas']}")
	print(f"  Actualizadas:{stats['actualizadas']:>6}  (se poblaría/pobló un folio vigente)")
	print(f"  Limpiadas:   {stats['limpiadas']:>6}  (folio obsoleto → vacío)")
	print(f"  Sin cambio:  {stats['sin_cambio']:>6}")
	print(f"  Errores:     {stats['errores']:>6}")
	print("=" * 60)

	# Ejemplos por categoría (hasta 3): (Sales Invoice, folio_actual, folio_esperado)
	for category in ("actualizadas", "limpiadas", "sin_cambio"):
		if examples[category]:
			print(f"Ejemplos [{category}]:")
			for name, current, expected in examples[category]:
				print(f"  - {name}: actual={current or '∅'} → esperado={expected or '∅'}")

	if not apply:
		print("DRY-RUN: no se escribió nada. Para aplicar: --kwargs \"{'apply': 1}\"")

	return stats
