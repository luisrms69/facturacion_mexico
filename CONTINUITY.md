# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-27
**Rama activa:** `feature/cfdi-recibidos-fase3-pi`
**Tarea actual:** Bloque E (UOM) — E.2 listo para commit, próximo E.3 (Sales Invoice)

---

## Recuperación rápida

Estoy trabajando en:
Módulo CFDI Recibidos — flujo de recepción y clasificación de facturas de proveedores.
Bloques A–D + E.1 commiteados. E.2 implementado y validado, pendiente commit.

Plan que estoy siguiendo:
`docs/development/PLAN_CFDI_RECIBIDOS_ITEMS_GASTO_UOM.md` — PLAN ACTIVO.

Objetivo inmediato:
Commitear E.2 y avanzar a E.3 — enforcement UOM en Sales Invoice / timbrado.

Criterio de avance:
E.3: timbrado de Sales Invoice con línea de item UOM no-SAT debe ser bloqueado.

---

## Estado actual

### Ya cerrado
- Bloque A `30022f9` — 84 Items genéricos GASTO-{CAT}-{NNN}, 10 tests
- Bloque B `6e2321f` — campos clasificación en concepto, 8 tests
- Bloque C `d4b6e96` — ItemResolver 3 niveles, 9 tests
- Bloque D `72969fa` — validate_expense_item, classify_all_concepts, UI, 23 tests
- Bloque E.1 `795e179` — uom_policy.py, enforce_sat_uom.py, hooks, 15 tests

### En progreso
- E.2 implementado y validado — pendiente commit en este turno

### Pendiente inmediato
1. Commit E.2 (este turno)
2. Bloque E.3 — enforcement UOM en Sales Invoice / timbrado
3. KWH — confirmar c_ClaveUnidad SAT; descomentar en uom_policy.py y corregir GASTO-OPR-003

### No repetir
- No proponer commits sin que el usuario lo solicite explícitamente en ese turno
- No hacer bench migrate sin autorización explícita
- No usar `FrappeTestCase` — usar `unittest.TestCase`
- No borrar UOMs, no migrar histórico, no tocar conversiones
- No cambiar el default de `stock_uom` en Item DocType — es ERPNext nativo
- item_group en concepto es read_only y siempre derivado

---

## Decisiones vigentes
- SAT_UOMS: frozenset 20 entradas en `uom_policy.py` — fuente de verdad única
- `validate_expense_item()`: 6 condiciones — la 5ª es `is_sat_uom(stock_uom)`
- `get_expense_items()`: usa params posicionales `%s` (necesario para IN clause)
- Test helpers en Bloque B/D usan `stock_uom = "H87 - Pieza"` — no leer Stock Settings
- KWH comentado en SAT_UOMS — descomentar solo cuando se confirme c_ClaveUnidad
- GASTO-OPR-003 usa MON — válido (MON está en SAT_UOMS); KWH es corrección semántica futura

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/cfdi_recibidos/services/uom_policy.py` — SAT_UOMS
- `facturacion_mexico/cfdi_recibidos/services/item_validator.py` — 6 condiciones actuales

### Probablemente editar (E.3)
- Código de timbrado / Sales Invoice validate — agregar check UOM SAT en líneas
- Tests E.3

### No tocar
- `facturacion_mexico/cfdi_recibidos/services/item_resolver.py`
- `facturacion_mexico/cfdi_recibidos/services/purchase_invoice_builder.py`
- `facturacion_mexico/one_offs/` — nunca commitear

---

## Riesgos / cuidados
- E.3 requiere identificar el punto exacto de enforcement en Sales Invoice / timbrado
  (before_submit o validate según alcance definido)
- KWH con MON en GASTO-OPR-003: semánticamente incorrecto para PI Builder,
  no bloquea E.3 — corregir después de confirmar c_ClaveUnidad SAT
- bench migrate debe correr en `facturacion-v16.dev` al cambiar schema

---

## Información faltante
- UOM SAT correcta para KWH — verificar catálogo SAT c_ClaveUnidad
- Punto exacto de enforcement E.3: ¿validate() o before_submit() en Sales Invoice?
