# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-27
**Rama activa:** `feature/cfdi-recibidos-fase3-pi`
**Tarea actual:** Bloque D completado — próximo Bloque E (UOM) → PI Builder

---

## Recuperación rápida

Estoy trabajando en:
Módulo CFDI Recibidos — flujo de recepción y clasificación de facturas de proveedores.
Bloques A–D completados. Próximo: Bloque E (diagnóstico y limpieza UOM no-SAT).

Plan que estoy siguiendo:
`docs/development/PLAN_CFDI_RECIBIDOS_ITEMS_GASTO_UOM.md` — PLAN ACTIVO.

Objetivo inmediato:
Bloque E — verificar que todos los Items genéricos de gasto tienen UOM válida SAT.
KWH (ítem #51) usa MON provisional — bloqueante antes de PI Builder.

Criterio de avance:
`bench --site facturacion-v16.dev execute facturacion_mexico.one_offs.<script>.run`
retorna lista de ítems con UOM no-SAT. Si KWH sigue con MON → corregir fixture.

---

## Estado actual

### Ya cerrado
- Bloque A `30022f9` — 84 Items genéricos GASTO-{CAT}-{NNN}, setup idempotente, 10 tests
- Bloque B `6e2321f` — item_group/item_code/item_resolution en concepto; compute_stage(); 8 tests
- Bloque C `d4b6e96` — ItemResolver 3 niveles (Mapeado/Específico/Genérico), 9 tests
- Bloque D (este commit) — validate_expense_item; item_group read_only derivado; classify_all_concepts;
  get_expense_items query; JS simplificado; cfdi_recibido_list.js con botones agrupados; 23 tests

### En progreso
- Nada — Bloque D recién commiteado, sesión limpia

### Pendiente inmediato
1. Bloque E — diagnóstico UOM: script one-off que lista Items con UOM fuera de catálogo SAT
2. Bloque E — corregir KWH (ítem #51) de MON → UOM SAT correcta en fixture
3. PI Builder — bloqueado hasta Bloque E resuelto

### No repetir
- No proponer commits sin que el usuario lo solicite explícitamente en ese turno
- No hacer bench migrate sin autorización explícita
- No usar `FrappeTestCase` en tests nuevos — usar `unittest.TestCase` para evitar
  preloading de Sales Invoice que falla por hook SAT
- item_group en concepto es read_only y siempre derivado — nunca input manual del usuario
- validate_expense_item() es el único punto de validación de ítems de gasto

---

## Decisiones vigentes
- `validate_expense_item()`: 5 condiciones (exists, is_purchase_item=1, is_stock_item=0,
  is_sales_item=0, grupo hoja bajo árbol Gastos)
- item_group en concepto: siempre derivado de item.item_group en validate(), nunca throw por inconsistencia
- classify_all_concepts usa validate_expense_item — rechaza cualquier ítem inválido
- ItemResolver nivel 3 con múltiples candidatos retorna None — no elige arbitrariamente
- Estado "Clasificado" (no "Listo") — consistente en todo el código
- Pendiente arquitectónico: botón "Clasificar automáticamente" en form view vs. list view —
  revisar si tiene valor en form view (registrado, no bloqueante)

---

## Archivos relevantes ahora

### Leer primero
- `docs/development/PLAN_CFDI_RECIBIDOS_ITEMS_GASTO_UOM.md` — sección Bloque E y PI Builder

### Probablemente editar
- `facturacion_mexico/cfdi_recibidos/setup/items_gasto.py` — fixture de 84 ítems (corregir UOM KWH)
- `facturacion_mexico/cfdi_recibidos/tests/` — tests Bloque E

### No tocar
- `facturacion_mexico/cfdi_recibidos/services/item_resolver.py` — no modificar sin plan
- `facturacion_mexico/cfdi_recibidos/services/tax_resolver.py` — leer REPORTE primero
- `facturacion_mexico/cfdi_recibidos/services/purchase_invoice_builder.py` — bloqueado hasta Bloque E
- `facturacion_mexico/one_offs/` — nunca commitear

---

## Riesgos / cuidados
- KWH con UOM=MON rompe cálculo de conversión en PI Builder — corregir antes de avanzar
- bench migrate debe correr en `facturacion-v16.dev` al cambiar schema
- Tests que usen FrappeTestCase fallan por preloading de Sales Invoice — usar unittest.TestCase

---

## Información faltante
- UOM SAT correcta para KWH — verificar catálogo SAT c_ClaveUnidad
