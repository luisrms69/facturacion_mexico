# ADR-0033: Eliminación de defaults fiscales silenciosos en Factura Global

**Fecha:** 2026-06-06
**Estado:** Activo
**Issue:** #160
**PR:** fix(global-invoice): eliminar hardcodes fiscales en factura global (#183)

---

## Contexto

El módulo de Factura Global (`facturas_globales/`) agrega E-Receipts de un período en un CFDI
tipo I con complemento "Información Global". Antes de este PR, el código tenía cuatro defaults
silenciosos que causaban que la Factura Global se timbrara con valores fiscales incorrectos
sin ningún error ni advertencia:

| Default silencioso | Código original | Problema |
|---|---|---|
| Tasa IVA | `flt(receipt.get("tax_rate", 16))` | Asumía 16% aunque el receipt fuera exento o tasa 0% |
| Clave unidad SAT | `unit_key = item.get("fm_unidad_sat") or "ACT"` | Usaba ACT aunque el item tuviera otra unidad |
| Forma de pago global | `return ... or "01"` | Usaba "01 - Efectivo" aunque no estuviera configurado |
| IEPS ignorado | Sin validación | Receipts con IEPS entraban a la FG sin generar impuesto correcto |

Adicionalmente, el SQL del aggregator usaba `total * 0.16` y `total * 0.84` hardcodeados,
lo que producía cálculos incorrectos para cualquier tasa diferente de 16%.

---

## Decisión

**Bloquear explícitamente en lugar de asumir valores incorrectos.**

Cada uno de los cuatro defaults se reemplazó con un `ValidationError` que indica exactamente
qué dato falta y en qué DocType configurarlo:

1. **Tasa IVA sin determinar** → `ValidationError`: "No se puede determinar la tasa IVA..."
   El `tax_rate` debe ser poblado desde las taxes del Sales Invoice al crear el EReceipt.

2. **Clave unidad SAT faltante** → `ValidationError`: "El item global no tiene `fm_unidad_sat`..."
   Configurar en `Configuracion Fiscal Mexico` → item global de la empresa.

3. **Forma de pago global faltante** → `ValidationError`: "Falta `global_payment_form_default`..."
   Configurar en `Facturacion Mexico Company Settings`.

4. **IEPS en receipt** → `ValidationError` con referencia a issue #182:
   "IEPS en Factura Global no soportado aún. Ver issue #182."
   Los receipts con IEPS no pueden incluirse en Factura Global hasta que #182 implemente
   el modelo line-level de impuestos.

El SQL del aggregator se corrigió a:
```sql
total / (1 + tax_rate / 100) AS base_amount,
total - (total / (1 + tax_rate / 100)) AS tax_amount
```

---

## Campos transitorios en EReceipt MX

Para poder validar la tasa IVA antes de incluir un receipt en la Factura Global, se agregaron
dos campos a `EReceipt MX`:

| Campo | Tipo | Descripción |
|---|---|---|
| `tax_rate` | Percent (read_only) | Tasa IVA extraída de las taxes del SI al crear el EReceipt |
| `has_ieps` | Check (hidden) | True si el SI tiene líneas de IEPS |

Estos campos son **transitorios** — el modelo definitivo está pendiente en issue #182
(impuestos por línea: `EReceipt MX Tax Line` child table). Cuando #182 se implemente,
`tax_rate` y `has_ieps` serán eliminados.

La extracción se hace con `extract_iva_info_from_si_taxes()` en `utils/calculo_impuestos.py`:
- Soporta IVA 16%, 8%, 0% explícito (tasa cero confirmada)
- Retorna `None` si la tasa no es determinable (sin nodos IVA, o múltiples tasas)
- `None` bloquea el timbrado de Factura Global — nunca asume

---

## Consecuencias

### Positivas
- El sistema no puede timbrar una Factura Global con datos fiscales incorrectos en silencio
- Los errores indican exactamente qué configurar y dónde
- El cálculo de base/impuesto es correcto para IVA 8%, 16%, y 0%

### Negativas / trade-offs
- EReceipts existentes creados antes de este PR no tienen `tax_rate` → ValidationError al
  incluirlos en Factura Global. Solución: recrear los EReceipts desde sus Sales Invoices.
- Clientes con productos IEPS no pueden usar Factura Global hasta #182

### Pendiente
- Issue #182: modelo line-level de impuestos para EReceipt MX / Factura Global
