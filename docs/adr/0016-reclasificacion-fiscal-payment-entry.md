# ADR 0016 — Reclasificación Fiscal de Impuestos en Payment Entry

**Fecha:** 2026-05-05
**Estado:** APROBADO — implementado y probado en GUI
**Autor:** Luis Montanaro Sánchez

---

## Contexto

En México, el IVA se registra en dos momentos:

1. **Al timbrar la factura** — el impuesto queda en una cuenta de "IVA pendiente por cobrar". Contablemente es devengado.
2. **Al cobrar/pagar** — el impuesto se vuelve efectivo. Contablemente debe moverse a "IVA cobrado/pagado".

ERPNext no genera este movimiento automáticamente al registrar un Payment Entry. Sin esta reclasificación, el IVA permanece en la cuenta "pendiente" aunque la factura esté completamente cobrada.

El patrón fue identificado en `facturacion_mx` (bench v15, llantascs.dev), donde se usaba manualmente el template **"002 IVA Cobranza - LLCS"**. Este PR automatiza ese flujo existente.

---

## Decisión

**Usar el mecanismo nativo de `Payment Entry.taxes` (AdvanceTaxesandCharges) de ERPNext.**

Se cargan dos filas en `PE.taxes` en el evento `validate`, visibles desde Save. Al submit, ERPNext genera el GL nativo. Al cancel, ERPNext revierte todo automáticamente.

---

## Patrón implementado (comprobado en producción llantascs.dev)

```
charge_type          = On Paid Amount
included_in_paid_amount = 1
add_deduct_tax       = Add   (para ambas filas)

Fila destino (IVA cobrado):
  account_head = cuenta_destino
  rate         = +rate_efectiva   → GL: Cr cuenta_destino

Fila origen (IVA pendiente):
  account_head = cuenta_origen
  rate         = -rate_efectiva   → GL: Dr cuenta_origen (negativo = reverso)
```

**Por qué `included_in_paid_amount = 1`:**
Con `included_in_paid_amount = 0`, ERPNext genera una contraparte contra `paid_to` (banco/caja). Con `included_in_paid_amount = 1`, solo genera la entrada del tax account — sin tocar banco. La combinación `Actual + included=1` está bloqueada por `validate_inclusive_tax`, pero `On Paid Amount + included=1` es válida.

---

## Fórmula de cálculo

```
monto_reclasificar = tax_amount_factura * (allocated_amount / grand_total)
rate_efectiva      = monto_reclasificar / pe.paid_amount * 100
```

**Ejemplos:**

| Caso | IVA factura | paid_amount | rate |
|---|---|---|---|
| IVA 16% puro ($1,740 total) | $240 | $1,740 | 13.793% |
| IVA 16% parcial (54% pagado) | $384 × 0.538 = $207 | $1,500 | 13.793% |
| Mezcla 16%+0% | calculado de tax_amount real | variable | variable |

La rate se calcula siempre de los datos reales de la factura. No hay tasas hardcodeadas. Funciona con cualquier combinación de IVA, incluyendo facturas con ítems al 0%.

---

## GL resultante

```
Dr  Banco/Caja         paid_amount   ← pago normal (siempre presente)
Cr  Clientes           paid_amount   ← pago normal

Dr  IVA pendiente      monto_reclasificar   ← reclasificación
Cr  IVA cobrado        monto_reclasificar   ← reclasificación
```

El Cash/Banco aparece UNA vez (el pago normal). Las filas de taxes no generan entradas adicionales de banco porque `included_in_paid_amount = 1`.

---

## Componentes implementados

### DocType: Mapeo Reclasificacion Fiscal Payment Entry

Configura la relación `cuenta_origen → cuenta_destino` por empresa y tipo de operación.

| Campo | Descripción |
|---|---|
| `company` | Empresa |
| `tipo_operacion` | Cobro (ventas) / Pago (compras) |
| `cuenta_origen` | Cuenta de impuesto al timbrar (IVA pendiente) |
| `cuenta_destino` | Cuenta de impuesto al cobrar/pagar (IVA efectivo) |
| `activo` | Activar/desactivar sin eliminar |

Validaciones: `account_type = Tax`, misma empresa, no grupo, no deshabilitada,
sin duplicado activo por `company + tipo_operacion + cuenta_origen`.

### Archivo: `payment_entry_reclasificacion.py`

- `cargar_impuestos_en_payment_entry(doc)` — hook `validate`. Lee referencias, calcula montos proporcionales, carga filas en `PE.taxes`. Llama `doc.apply_taxes()` al final para forzar recálculo (el hook corre después del PE.validate de ERPNext).
- `generar_reclasificacion_payment_entry` / `cancelar_reclasificacion_payment_entry` — no-ops. ERPNext maneja GL y reversión nativamente.

### Archivo: `payment_entry_cancel.py`

Stub creado — el módulo existía referenciado en hooks.py pero faltaba el archivo. Cancela el Complemento Pago MX vinculado si existe.

---

## Pruebas GUI aprobadas (2026-05-05)

| SI | PE | Tipo | Pago | IVA reclasificado | GL |
|---|---|---|---|---|---|
| ACC-SINV-2026-00024 | ACC-PAY-2026-00017 | Total | $1,740 | **$240** | ✅ limpio |
| ACC-SINV-2026-00025 | ACC-PAY-2026-00018 | Parcial (54%) | $1,500 de $2,784 | **$206.90** | ✅ limpio |
| ACC-PAY-2026-00017 (cancel) | — | Cancel | — | **revertido** | ✅ |

Taxes visibles desde Save (antes de Submit). GL generado por ERPNext al Submit.

---

## Alternativas descartadas

| Opción | Razón de descarte |
|---|---|
| GL Entry directo (`make_gl_entries` en on_submit) | No visible en taxes del PE; usuario no puede verificar antes del submit |
| `Actual + included=1` | Bloqueado por `validate_inclusive_tax` en ERPNext |
| `Actual + included=0` | Genera entradas extras de banco/caja que se cancelan entre sí — "Cash extra" visible en GL |
| Journal Entry | Pierde trazabilidad directa contra el PE |
| Payment Entry Deduction | Diseñado para diferencias de tipo de cambio/descuentos, no reclasificación de IVA |

---

## Fuera de alcance (para implementación futura)

| Item | Estado |
|---|---|
| IVA frontera 8% | No probado — no hay SIs de frontera en site dev |
| Múltiples referencias con tasas distintas | No probado — requiere datos de prueba |
| Purchase Invoice (Pago) | Implementado en código, no probado end-to-end |
| Backfill de PEs históricos | No incluido — one-off bajo demanda |
| Complemento Pago MX | Siguiente bloque |

---

## Hooks registrados

```python
"Payment Entry": {
    "validate": [
        "...payment_entry_validate.check_ppd_requirement",
        "...payment_entry_reclasificacion.cargar_impuestos_en_payment_entry",
    ],
    "on_submit": "...payment_entry_submit.create_complement_if_required",
    "on_cancel": "...payment_entry_cancel.cancel_related_complement",
}
```

---

## Referencias

- `facturacion_fiscal/services/payment_entry_reclasificacion.py`
- `facturacion_fiscal/doctype/mapeo_reclasificacion_fiscal_payment_entry/`
- `complementos_pago/hooks_handlers/payment_entry_cancel.py`
- Template "002 IVA Cobranza - LLCS" en llantascs.dev (patrón de referencia)
- ERPNext `payment_entry.py:add_tax_gl_entries` — mecanismo nativo
