# ADR 0017 — Normalización Schema Complemento Pago MX (Bloque 3A)

**Fecha:** 2026-05-05
**Estado:** APROBADO — schema implementado, Bloque 3B pendiente
**Autor:** Luis Montanaro Sánchez

---

## Contexto

El DocType `Complemento Pago MX` existía con estructura orientada al CFDI fiscal
(datos de timbrado, documentos relacionados, impuestos trasladados) pero sin los
campos operativos necesarios para vincular el complemento a su Payment Entry.

El código existente en `payment_entry_submit.py` era inoperable:
- Usaba `related_invoices` (child table inexistente — el DocType tiene `documentos_relacionados`)
- Escribía campos `payment_entry`, `company`, `customer`, `complement_status` que no existían
- La detección PPD revisaba `fm_forma_pago` y `fm_uso_cfdi` en SI — campos que no existen
- La función nunca ejecutaba porque todas las condiciones fallaban silenciosamente

---

## Decisión

**Bloque 3A: normalización mínima de schema.**
Solo agregar los campos de vínculo operativo. No crear el flujo de generación todavía.

Objetivo: dejar el DocType en estado donde el código de Bloque 3B pueda funcionar correctamente.

---

## Campos agregados a Complemento Pago MX

| Campo | Tipo | Descripción |
|---|---|---|
| `payment_entry` | Link → Payment Entry | Vínculo principal con el pago |
| `company` | Link → Company | Empresa — requerida para GL y multi-empresa |
| `customer` | Link → Customer | Parte fiscal del complemento |
| `complement_status` | Select | Estado del flujo PPD: Pendiente/Timbrado/Cancelado/Error |

`complement_status` tiene `default = "Pendiente"`.

---

## Relación arquitectónica (espejo SI↔FFM)

```
Payment Entry                     Complemento Pago MX
─────────────────────────        ──────────────────────────
fm_complemento_pago  ──────────→ name
fm_require_complement (flag)     payment_entry (link) ←────
fm_complement_generated (flag)   complement_status
fm_forma_pago_sat                documentos_relacionados (child)
```

El patrón replica la arquitectura SI↔FFM:
- PE mantiene estado mínimo + link al complemento
- Complemento Pago MX es la fuente fiscal completa

---

## Hooks neutralizados hasta Bloque 3B

`payment_entry_submit.py` y `payment_entry_validate.py` convertidos a no-op.
La creación del complemento será **manual** mediante botón en el Bloque 3B.

Razón: el código anterior era inoperable (referenciaba campos y child tables inexistentes).
Mejor reescribir desde cero en Bloque 3B usando el schema correcto que ahora existe.

---

## Child tables existentes (sin cambio)

| Child DocType | Propósito | Campos clave |
|---|---|---|
| `Documento Relacionado Pago MX` | Facturas cubiertas por este complemento | `id_documento`, `num_parcialidad`, `imp_saldo_ant`, `imp_pagado`, `imp_saldo_insoluto` |
| `Detalle Complemento Pago MX` | Impuestos trasladados y retenidos | `tipo_impuesto`, `tasa_cuota`, `base_dr`, `importe_dr` |

Se usa `documentos_relacionados`, NO `related_invoices` (campo que no existe y causaba crash en el código anterior).

---

## Campos Payment Entry — sin cambio

Los custom fields de PE ya existían y son suficientes para Bloque 3B:

| Campo | Tipo | Para qué |
|---|---|---|
| `fm_complemento_pago` | Link → Complemento Pago MX | Referencia al complemento generado |
| `fm_require_complement` | Check | Flag: ¿este PE requiere complemento? |
| `fm_complement_generated` | Check | Flag: ¿ya se generó? |
| `fm_forma_pago_sat` | Link → Forma Pago SAT | Forma de pago para el XML |

---

## Bloque 3B — pendiente

Implementar la creación del Complemento Pago MX:
- Botón en PE o en Complemento Pago MX
- Llenado de `documentos_relacionados` con datos reales de las SIs referenciadas
- Uso de `fm_es_ppd` para detectar SIs PPD (campo creado en Bloque 2)
- Cálculo de `num_parcialidad`, `imp_saldo_ant`, `imp_saldo_insoluto`
- Timbrado vía FacturAPI (Bloque 3C)

---

## Archivos modificados

| Archivo | Cambio |
|---|---|
| `complementos_pago/doctype/complemento_pago_mx/complemento_pago_mx.json` | Agregar 4 campos nuevos |
| `complementos_pago/hooks_handlers/payment_entry_submit.py` | No-op hasta Bloque 3B |
| `complementos_pago/hooks_handlers/payment_entry_validate.py` | No-op hasta Bloque 3B |

---

## Referencias

- ADR 0016 — Reclasificación fiscal en Payment Entry (arquitectura PE)
- ADR 0014 — Diagnóstico SI↔FFM (patrón de referencia para la relación PE↔Complemento)
- `complementos_pago/doctype/complemento_pago_mx/complemento_pago_mx.json`
- `complementos_pago/doctype/documento_relacionado_pago_mx/documento_relacionado_pago_mx.json`
