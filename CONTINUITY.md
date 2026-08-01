# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-08-01
**Rama activa:** `fix/ffm-tipo-nc-derivado-simetrico`
**Tarea actual:** Puntos 4-5 FFM — `fm_tipo_nota_credito` derivado/read-only + clasificación positiva fail-closed. Listo para commit; falta autorización de push + PR.

---

## Recuperación rápida

Estoy trabajando en:
Hacer `fm_tipo_nota_credito` un **dato derivado y read-only** en la FFM: la decisión Descuento vs Devolución se toma en la **Sales Invoice Return**; la FFM la **clasifica desde el estado exacto del origen** (vía `sales_invoice_item`) de forma **positiva y fail-closed**. Devolución exacta → 01... no: **03/G02/FormaPago general**; descuento exacto → **01/G02/15**; estado ambiguo o vínculos faltantes → **bloquea** sin mutación parcial. Protección `docstatus` para no reinterpretar submitted/cancelled.

Plan que estoy siguiendo:
ADR `docs/adr/0025-notas-credito-cfdi-tipo-e-issue116.md`, sección «Puntos 4–5». Diseño aprobado: Opción A (no bandera en SI). PATCH 1.3.1.

Objetivo inmediato:
`/ship push` → `/ship pr` (base `main`), con autorización explícita en cada paso.

Criterio de avance:
Focalizados verdes (clasificación exacta, estados ambiguos, ciclo Draft→Submit, meta) + full suite en baseline (2 failures/11 errors preexistentes) + ruff/prettier/mkdocs limpios.

---

## Estado actual

### Ya cerrado
- Controller: `_classify_nota_credito` (positivo, fail-closed, no muta antes de derivar) reemplaza a `_detect_nota_credito_motivo`; derivación simétrica 01/03 con G02 en ambos; guard `docstatus`; `-> None`.
- DocType JSON: `fm_tipo_nota_credito` `read_only:1` + description corta. JS: campo siempre bloqueado.
- Tests: clasificación (7 escenarios), derivación, protección submitted/cancelled, ciclo Draft→Submit, meta.
- Bump `1.3.0 → 1.3.1`. ADR actualizado.
- `bench migrate` corrido **solo** en `test-facturacion.localhost` (metadata read_only/description).

### Pendiente inmediato
1. `/ship push` (con autorización).
2. `/ship pr` hacia `main` (con autorización) → tras merge: tag `v1.3.1` + Release.

### No repetir
- **NO** reintroducir default «sin cuenta → devolución»: la clasificación es por **estado exacto**, fail-closed.
- **NO** clasificar por prefijo de descripción; validar el estado completo (`build_descuento_description`, income_account, update_stock).
- **NO** mutar campos fiscales antes de lanzar en estado ambiguo.
- **NO** tocar `depends_on`/visibilidad ni otros pendientes CodeRabbit (#3 test guard, RG-001, IDs mocks, RG-003 get_doc, DRY JS SI).

---

## Decisiones vigentes
- `fm_tipo_nota_credito` es derivado/read-only; fuente de verdad = estado de la SI Return.
- UsoCFDI **G02** aplica a **ambos** (descuento y devolución).
- FormaPago de devolución: se limpia residuo de descuento y se delega en `_auto_populate_forma_pago_tipo_e` (política #136 sin cambios).
- Clasificación fail-closed corre en `validate` de cada FFM Draft de nota de crédito y **puede lanzar** (a validar en GUI del despliegue).

---

## Archivos relevantes ahora

### Leer primero
- `docs/adr/0025-notas-credito-cfdi-tipo-e-issue116.md` (sección «Puntos 4–5»).

### No tocar
- `timbrado_api.py`, `api/nota_credito.py` (flujo SI-stage, ya en 1.3.0).

---

## Riesgos / cuidados
- **Cambio de comportamiento:** una SI Return editada manualmente o sin `sales_invoice_item` bloquea la creación/guardado de la FFM (fail-closed). Devoluciones `make_return_doc` y descuentos por la acción pasan sin bloqueo (0 regresiones en full suite).
- Este PR **requiere `bench migrate`** al instalar (metadata del DocType).

---

## Información faltante
- Validación GUI del bloque de despliegue de 1.3.1 (estados válidos/ambiguos en el sitio real).
