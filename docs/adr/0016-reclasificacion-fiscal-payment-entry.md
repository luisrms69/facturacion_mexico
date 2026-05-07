# ADR 0016 — Reclasificación Fiscal de Impuestos en Payment Entry

**Fecha:** 2026-05-05 | **Última revisión:** 2026-05-06 | **Estado:** APROBADO — implementado y probado

---

## Decisión

Usar `Payment Entry.taxes` nativo de ERPNext. No GL directo, no Journal Entry.

Patrón comprobado en producción (`facturacion_mx`, template "002 IVA Cobranza - LLCS").

---

## Patrón de filas

```
charge_type             = On Paid Amount
included_in_paid_amount = 1    → sin Cash/Bank counterpart
add_deduct_tax          = Add  → ambas filas

Fila destino: rate = +rate_efectiva  → Cr cuenta_destino (IVA cobrado)
Fila origen:  rate = -rate_efectiva  → Dr cuenta_origen  (IVA pendiente)
```

## Fórmula

```
monto_reclasificar = tax_amount × (allocated_amount / grand_total)
rate               = monto_reclasificar / paid_amount × 100
```

## GL resultante

```
Dr Banco        paid_amount    ← pago normal
Cr Cliente      paid_amount    ← pago normal
Dr IVA pendiente  monto        ← reclasificación
Cr IVA cobrado    monto        ← reclasificación
```

Cash aparece solo por el pago normal. Las filas de taxes no generan Cash extra.

---

## Componentes implementados

- **`Mapeo Reclasificacion Fiscal Payment Entry`** — DocType: company + tipo_operacion + cuenta_origen → cuenta_destino
- **`cargar_impuestos_en_payment_entry`** — hook `validate`, carga filas visibles desde Save
- **Tests** — 7 tests DocType + 13 tests lógica de cálculo

---

## Pruebas GUI (2026-05-05)

- ACC-PAY-2026-00017: pago total $1,740 → IVA $240 ✅
- ACC-PAY-2026-00018: pago parcial $1,500/$2,784 → IVA $206.90 ✅
- Cancelación: reversión automática ✅

---

## Gaps

- IVA frontera 8% — no probado en site dev
- Purchase Invoice — implementado, no probado end-to-end
- Backfill PEs históricos — one-off bajo demanda
