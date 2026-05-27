# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-27
**Rama activa:** `feature/cfdi-recibidos-fase3-pi`
**Tarea actual:** Bloque E (UOM) — E.1 commiteado, próximo E.2 (enforcement CFDI Recibidos)

---

## Recuperación rápida

Estoy trabajando en:
Módulo CFDI Recibidos — flujo de recepción y clasificación de facturas de proveedores.
Bloques A–D completados. Bloque E.1 (política base UOM) commiteado. Próximo: E.2.

Plan que estoy siguiendo:
`docs/development/PLAN_CFDI_RECIBIDOS_ITEMS_GASTO_UOM.md` — PLAN ACTIVO.

Objetivo inmediato:
Bloque E.2 — enforcement UOM en CFDI Recibidos: validar UOM SAT en item_validator.py
y filtrar UOM SAT en get_expense_items() / queries.py.

Criterio de avance:
Tests de E.2 pasan. item_validator.py lanza error si concepto tiene UOM no-SAT.
get_expense_items() solo retorna ítems con UOM SAT.

---

## Estado actual

### Ya cerrado
- Bloque A `30022f9` — 84 Items genéricos GASTO-{CAT}-{NNN}, setup idempotente, 10 tests
- Bloque B `6e2321f` — item_group/item_code/item_resolution en concepto; compute_stage(); 8 tests
- Bloque C `d4b6e96` — ItemResolver 3 niveles (Mapeado/Específico/Genérico), 9 tests
- Bloque D `72969fa` — validate_expense_item; classify_all_concepts; get_expense_items; 23 tests
- Bloque E.1 (commit de esta sesión) — uom_policy.py, enforce_sat_uom.py, hooks, 15 tests;
  bench migrate facturacion-v16.dev: 20 SAT enabled, 255 no-SAT disabled, _Test* intactas

### En progreso
- Nada — E.1 recién commiteado, sesión limpia

### Pendiente inmediato
1. Bloque E.2 — validación UOM SAT en item_validator.py (validate_expense_item)
2. Bloque E.2 — filtro UOM SAT en get_expense_items() queries
3. Bloque E.3 — enforcement Sales Invoice / timbrado (bloqueado hasta E.2)
4. KWH — confirmar c_ClaveUnidad SAT; descomentar en uom_policy.py y corregir GASTO-OPR-003

### No repetir
- No proponer commits sin que el usuario lo solicite explícitamente en ese turno
- No hacer bench migrate sin autorización explícita
- No usar `FrappeTestCase` en tests nuevos — usar `unittest.TestCase`
- No borrar UOMs, no migrar documentos históricos, no tocar conversiones
- No cambiar el default de `stock_uom` en Item DocType — es ERPNext nativo
- item_group en concepto es read_only y siempre derivado — nunca input manual

---

## Decisiones vigentes
- SAT_UOMS: frozenset de 20 entradas en `uom_policy.py` — fuente de verdad única
- KWH comentado en SAT_UOMS — descomentar solo cuando se confirme c_ClaveUnidad
- enforce_sat_uom_policy: after_migrate solo loguea si stock_uom no es SAT;
  after_install sí cambia stock_uom a H87 si no es SAT y H87 existe y está enabled
- `set_single_value` para Stock Settings (evita deprecation warning v16)
- `update_modified=False` en set_value sobre UOMs (no contaminar timestamps)
- GASTO-OPR-003 usa MON — válido porque MON está en SAT_UOMS; KWH es solo corrección semántica

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/cfdi_recibidos/services/uom_policy.py` — SAT_UOMS y contratos públicos
- `facturacion_mexico/setup/enforce_sat_uom.py` — política aplicada en setup

### Probablemente editar (E.2)
- `facturacion_mexico/cfdi_recibidos/services/item_validator.py` — agregar check UOM SAT
- `facturacion_mexico/cfdi_recibidos/queries.py` — filtrar UOM SAT en get_expense_items()
- `facturacion_mexico/cfdi_recibidos/tests/` — tests E.2

### No tocar
- `facturacion_mexico/cfdi_recibidos/services/item_resolver.py` — no modificar sin plan
- `facturacion_mexico/cfdi_recibidos/services/purchase_invoice_builder.py` — bloqueado hasta E.2
- `facturacion_mexico/one_offs/` — nunca commitear

---

## Riesgos / cuidados
- KWH con UOM=MON en GASTO-OPR-003: semánticamente incorrecto para PI Builder,
  pero no bloquea E.2 ni E.3 — corregir después de confirmar c_ClaveUnidad SAT
- bench migrate debe correr en `facturacion-v16.dev` al cambiar schema
- Tests con FrappeTestCase fallan por preloading Sales Invoice — usar unittest.TestCase

---

## Información faltante
- UOM SAT correcta para KWH — verificar catálogo SAT c_ClaveUnidad
