# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-27
**Rama activa:** `feature/cfdi-recibidos-fase3-pi`
**Tarea actual:** Prerequisites PI completos (incl. KWH) — próximo: revisión TaxResolver/PIBuilder para desbloquear Hito D

---

## Recuperación rápida

Estoy trabajando en:
Módulo CFDI Recibidos — flujo completo XML → Purchase Invoice.
Bloques A–E (items de gasto + clasificación + UOM) completados y commiteados.
Estos bloques son infraestructura prerequisito del PI Builder, no el PI Builder en sí.

Plan que estoy siguiendo:
`docs/development/PLAN_ACTUAL_CFDI_RECIBIDOS.md` — FUENTE DE VERDAD ÚNICA.
(PLAN_CFDI_RECIBIDOS_ITEMS_GASTO_UOM.md era el plan de los Bloques A–E, ya terminado.)

Objetivo inmediato:
Revisión arquitectónica de `tax_resolver.py` y `purchase_invoice_builder.py` para
definir plan de implementación de Hito D. Ningún código nuevo antes de ese plan.

Criterio de avance:
Plan de Hito D aprobado + decisión sobre retenciones + KWH confirmado → implementar PI Builder.

---

## Estado actual

### Ya cerrado
- Hito A `7c6b44f` — Upload → Proveedor
- Hito B `ac318a7` — Generar proveedores faltantes
- Hito C.1 `40638d5` / `82e9849` — Config CFDI Recibidos + Item Groups
- Hito C.2 `8699ae7` — Department assignment (23 tests)
- Bloque A `30022f9` — 84 Items genéricos GASTO-{CAT}-{NNN}
- Bloque B `6e2321f` — campos clasificación en concepto
- Bloque C `d4b6e96` — ItemResolver 3 niveles
- Bloque D `72969fa` — validate_expense_item, classify_all_concepts, UI
- Bloque E.1 `795e179` — uom_policy.py, enforce_sat_uom.py, hooks
- Bloque E.2 `0ff3ad3` — enforcement UOM en CFDI Recibidos
- Bloque E.3 `7467c45` — invoice_uom_validator.py, enforcement en timbrado
- KWH `(este commit)` — c_ClaveUnidad confirmado, SAT_UOMS=21, GASTO-OPR-003 corregido

### En progreso
- Nada — prerequisites completos, pendiente arquitectura Hito D

### Pendiente inmediato
1. Revisión `tax_resolver.py` + `purchase_invoice_builder.py` — arquitectura y plan Hito D
2. Decisión sobre retenciones (ISR/IVA retenido) — requiere XML real de honorarios
3. ~~KWH~~ — resuelto en este commit
4. Implementar Hito D (PI Builder) — bloqueado hasta los 2 puntos anteriores

### No repetir
- No proponer commits sin que el usuario lo solicite explícitamente en ese turno
- No hacer bench migrate sin autorización explícita
- No usar `FrappeTestCase` — usar `unittest.TestCase`
- No modificar `tax_resolver.py` ni `purchase_invoice_builder.py` sin plan aprobado
- No borrar UOMs, no migrar histórico, no tocar conversiones
- GUI test de E.3 no es posible: E.1 deshabilita UOMs no-SAT system-wide. Validación aceptada vía 8 tests unitarios.

---

## Decisiones vigentes
- SAT_UOMS: frozenset 20 entradas en `uom_policy.py` — fuente de verdad única
- KWH - Kilowatt hora en SAT_UOMS (21 entradas) — c_ClaveUnidad SAT confirmado
- GASTO-OPR-003 usa KWH - Kilowatt hora (corregido)
- E.3 enforcement en `_validate_invoice_for_timbrado()` — no en `before_submit`
- `get_expense_items()`: params posicionales `%s` para IN clause
- Test helpers: `stock_uom = "H87 - Pieza"` hardcoded — no leer Stock Settings

---

## Archivos relevantes ahora

### Leer primero (para Hito D)
- `docs/development/PLAN_ACTUAL_CFDI_RECIBIDOS.md` — fuente de verdad del flujo completo
- `facturacion_mexico/cfdi_recibidos/services/purchase_invoice_builder.py`
- `facturacion_mexico/cfdi_recibidos/services/tax_resolver.py`
- `docs/development/REPORTE_INVESTIGACION_SAT_CFDI_RECIBIDOS.md` — problemas encontrados

### No tocar sin plan aprobado
- `facturacion_mexico/cfdi_recibidos/services/purchase_invoice_builder.py`
- `facturacion_mexico/cfdi_recibidos/services/tax_resolver.py`
- `facturacion_mexico/one_offs/` — nunca commitear

---

## Riesgos / cuidados
- PIBuilder original falló en GUI al paso ~2 de 20+ — necesita reescritura con arquitectura nueva
- Retenciones ERPNext v16 pueden diferir de v15 — no implementar sin XML real
- KWH: nombre exacto en c_ClaveUnidad SAT puede diferir de "KWH - Kilowatt hora"
- bench migrate requerido al agregar campos en Purchase Invoice (Hito D)

---

## Información faltante
- XML real de honorarios con ISR/IVA retenido (prerequisito retenciones)
- Arquitectura correcta de TaxResolver para v16
