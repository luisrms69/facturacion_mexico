# ADR 0042 — Complemento Pago MX: soporte de múltiples nodos Pago (REP 2.0)

**Estado:** Aceptado
**Fecha:** 2026-09-27

## Contexto

Un CFDI de pago (REP 2.0) puede contener **N nodos `pago20:Pago`**, cada uno con su propia fecha,
forma de pago, moneda, tipo de cambio, monto, cuentas de cadena de pago y su propio conjunto de
`DoctoRelacionado`. El modelo `Complemento Pago MX` (ver ADR 0017) representaba **un solo Pago** con
campos escalares en el padre y un único `payment_entry`, y `documentos_relacionados`/
`detalles_impuestos` planos. Eso impedía cargar REP históricos con varios Pagos sin colapsar
información fiscal ni partir el UUID en varios Complementos (imposible: `folio_fiscal` es `unique`).

## Decisión

- Nuevo child DocType **`Complemento Pago Detalle Pago MX`** y Table **`pagos`** en el padre: una fila
  por nodo Pago, con su `payment_entry` propio.
- **`pago_idx`** en `Documento Relacionado Pago MX` y `Detalle Complemento Pago MX` para agrupar cada
  documento/impuesto con su Pago.
- **Canónico vs legacy (sin data patch):** con filas `pagos` la fuente de verdad fiscal es la tabla
  `pagos`; los campos escalares del padre quedan como **espejo del primer Pago** (compatibilidad/UI).
  Registros legacy sin `pagos` se interpretan como **un Pago único implícito** vía escalares.
  `validate_documentos_relacionados` valida el cuadre **por nodo Pago** (agrupando por `pago_idx`)
  cuando hay `pagos`; si no, por escalares.
- Un CFDI = un Complemento (folio_fiscal único) + N `pagos` + **N Payment Entry** (uno por Pago).

## Alternativas descartadas

- **Colapsar N Pagos en uno**: pierde fecha/moneda/forma/monto por Pago (información fiscal real).
- **N Complementos por CFDI**: rompe la unicidad de `folio_fiscal` y la idempotencia por UUID.
- **Data patch de registros existentes**: innecesario — la ruta legacy (escalares) los mantiene
  válidos sin migración de datos.

## Consecuencias

- El importador histórico `cfdi_historico_rep` crea N Payment Entry (orden `FechaPago`) y un
  Complemento con N `pagos`; rollback total del REP si falla un Pago.
- El generador del payload de timbrado consume `pagos` → N elementos en `complements[].data`
  (fallback legacy a escalares). FacturAPI admite múltiples pagos.
- El flujo saliente (`crear_complemento_pago_desde_pe`) crea la fila `pagos` (pago_idx=1) también para
  un solo Pago; los escalares se mantienen sincronizados para compatibilidad.
- Se aplica por `bench migrate` (DocTypes propios del app); no requiere `fixtures export`.
