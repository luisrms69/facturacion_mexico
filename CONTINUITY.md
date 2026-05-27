# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-27
**Rama activa:** `feature/cfdi-recibidos-fase3-pi`
**Tarea actual:** Implementar Bloque C — ItemResolver (propone Item por 3 niveles)

---

## Recuperación rápida

Estoy trabajando en:
Módulo CFDI Recibidos — flujo de recepción y procesamiento de facturas de proveedores.
Bloques A y B completados. Próximo: Bloque C (ItemResolver).

Plan que estoy siguiendo:
`docs/development/PLAN_CFDI_RECIBIDOS_ITEMS_GASTO_UOM.md` — PLAN ACTIVO.
Contiene arquitectura Bloques A-E, matriz 84 Items, decisiones DC-01 a DC-11.
Leer completo antes de tocar ItemResolver, clasificación o PI Builder.

Objetivo inmediato:
Bloque C — `ItemResolver`: propone Item por 3 niveles de precisión:
  1. Mapeado (CFDI Concepto Mapping existente)
  2. Específico (match por descripción/ClaveProdServ)
  3. Genérico (ítem GASTO-{CAT}-{NNN} según item_group del concepto)

Criterio de avance:
ItemResolver retorna `item_code` correcto en los 3 niveles + tests pasan en
`test-facturacion.localhost`.

---

## Estado actual

### Ya cerrado
- Bloque A `30022f9` — 84 Items genéricos GASTO-{CAT}-{NNN}, setup idempotente, 10 tests
- Bloque B `6e2321f` — item_group/item_code/item_resolution en concepto; estado Clasificado;
  compute_stage() por item_code; filtro GUI Item Groups bajo Gastos; 8 tests nuevos

### En progreso
- Nada — Bloque B recién commiteado, sesión limpia

### Pendiente inmediato
1. Bloque C — ItemResolver (3 niveles)
2. Bloque D — UI/API de clasificación de conceptos
3. Bloque E — Diagnóstico y limpieza UOM no-SAT (prerequisito hard de PI Builder)
4. PI Builder — bloqueado hasta Bloque E

### No repetir
- No proponer commits sin que el usuario lo solicite explícitamente en ese turno
- No mover Items/ItemGroups de gasto a after_migrate — solo after_install
- No usar `hasattr()` para detectar campos en Frappe docs — usar `meta.fields` o `getattr(..., None)`
- Validación de conceptos va en `cfdi_recibido.py` (parent), NO en `cfdi_recibido_concepto.py` (child)

---

## Decisiones vigentes
- `compute_stage()`: supplier → department → item_code en cada concepto → Clasificado
- Item Group es dimensión independiente del concepto, asignada por usuario en UI
- Bloqueo (frappe.throw) si item_group del concepto ≠ item_group del Item seleccionado
- Estado "Listo" fue renombrado a "Clasificado" — no usar "Listo" en ningún contexto nuevo
- KWH no está en fixture — ítem #51 (Energía eléctrica) usa MON provisional. Bloqueante antes de PI
- 9 códigos ClaveProdServ 🔴 son placeholders — validar contra c_ClaveProdServ.xls antes de producción
- No tocar `tax_resolver.py`, `purchase_invoice_builder.py` sin leer REPORTE primero

---

## Archivos relevantes ahora

### Leer primero
- `docs/development/PLAN_CFDI_RECIBIDOS_ITEMS_GASTO_UOM.md` — plan activo, sección Bloque C
- `facturacion_mexico/cfdi_recibidos/services/status_manager.py` — compute_stage() actualizado
- `facturacion_mexico/cfdi_recibidos/doctype/cfdi_recibido_concepto/cfdi_recibido_concepto.json` — campos nuevos

### Probablemente editar
- Archivo nuevo: `facturacion_mexico/cfdi_recibidos/services/item_resolver.py`
- `facturacion_mexico/cfdi_recibidos/tests/` — tests de ItemResolver

### No tocar
- `facturacion_mexico/cfdi_recibidos/services/tax_resolver.py` — sin leer REPORTE primero
- `facturacion_mexico/cfdi_recibidos/purchase_invoice_builder.py` — bloqueado hasta Bloque E
- `facturacion_mexico/one_offs/` — nunca commitear

---

## Riesgos / cuidados
- UOM KWH faltante bloquea PI Builder — no ignorar en Bloque E
- `CFDI Concepto Mapping` con `target_type='ExpenseAccount'` es ignorado por ItemResolver (futuro)
- bench migrate debe correr en `facturacion-v16.dev` Y `test-facturacion.localhost` al cambiar schema

---

## Información faltante
- Ninguna bloqueante para Bloque C
