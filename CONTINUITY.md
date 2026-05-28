# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-28
**Rama activa:** `feature/cfdi-recibidos-fase3-pi`
**Tarea actual:** Implementar motor de resolución de Items para conceptos CFDI Recibidos

---

## Recuperación rápida

Estoy trabajando en:
Motor de resolución de Items: dado un concepto CFDI (sat_product_key, no_identificacion,
descripción), propone qué ERPNext Item asignar usando reglas configurables + búsqueda textual.
F.3 (PIBuilder) está commiteado como WIP — funcional pero no arquitectura final validada.

Plan que estoy siguiendo:
Arquitectura documentada en conversación: "Resolución de Items para conceptos CFDI recibidos".
8 niveles: Reglas → no_identificacion → texto → crear específico → genérico.

Objetivo inmediato:
Implementar TODO en un solo paso:
1. DocType `Regla Item CFDI Recibido`
2. `concept_text_normalizer.py`
3. `item_resolution_engine.py` (8 niveles)
4. 5 endpoints nuevos en `api.py`
5. Botón "Resolver Items pendientes" + diálogo en `cfdi_recibido.js`
6. Tests `test_concept_text_normalizer.py` + `test_item_resolution_engine.py`

Criterio de avance:
Motor implementado + tests pasan + `bench migrate` limpio.

---

## Estado actual

### Ya cerrado
- Hito A–C.2 — Upload, Proveedores, Config, Department
- Bloque A–E.3 — Items genéricos, clasificación, UOM SAT enforcement
- F.3 WIP `(este commit)` — PIBuilder 21/21 PASS, item_resolver refinado

### En progreso
- Motor resolución items: DocType Regla + normalizer + engine + API + JS + tests

### Pendiente inmediato
1. Crear DocType `Regla Item CFDI Recibido` (JSON + .py + __init__.py)
2. `concept_text_normalizer.py` — normalize() + keywords_match()
3. `item_resolution_engine.py` — 8 niveles, retorna {primary, alternatives, generic}
4. 5 endpoints en api.py: get_item_resolution_options, assign_item_to_concepto,
   create_specific_item_from_concepto, create_grouping_item_from_concepto,
   assign_generic_item_to_concepto
5. `cfdi_recibido.js` — botón "Resolver Items pendientes" + diálogo por concepto
6. Tests: test_concept_text_normalizer.py + test_item_resolution_engine.py
7. Actualizar `cfdi_recibido_concepto.json` — campos item_match_reason, item_match_confidence,
   opciones item_resolution: Pendiente/Mapeado/Código proveedor/Sugerido/Nuevo específico/
   Nuevo agrupador/Genérico/Manual
8. `bench --site facturacion-v16.dev migrate` (requiere autorización)

### No repetir
- No asignar Items genéricos GASTO-* automáticamente — solo con acción explícita del usuario
- No crear ítems por línea XML sin input del usuario
- No usar FrappeTestCase — usar unittest.TestCase
- No proponer commits sin que el usuario lo solicite explícitamente
- No hacer bench migrate sin autorización explícita

---

## Decisiones vigentes
- item_resolution values: Pendiente/Mapeado/Código proveedor/Sugerido/Nuevo específico/
  Nuevo agrupador/Genérico/Manual
- match_confidence: Alta (regla exacta/RFC+SAT/no_ident) | Media (keywords) | Baja (texto)
- classify_all_concepts: solo asigna Mapeado (reglas) + Código proveedor (no_ident alta confianza)
- Genérico y Nuevo específico/agrupador: SIEMPRE requieren acción explícita del usuario
- SAT_UOMS: frozenset 21 entradas — fuente de verdad única
- test setUp: default_warehouse="" en item_defaults para evitar contaminación Stores-TQC

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/cfdi_recibidos/doctype/cfdi_recibido_concepto/cfdi_recibido_concepto.json`
- `facturacion_mexico/cfdi_recibidos/services/item_resolver.py`
- `facturacion_mexico/cfdi_recibidos/api.py`
- `facturacion_mexico/cfdi_recibidos/doctype/cfdi_recibido/cfdi_recibido.js`

### Probablemente editar
- Los 4 anteriores + nuevos archivos a crear (ver pendiente inmediato)

### No tocar
- `facturacion_mexico/one_offs/` — nunca commitear
- `facturacion_mexico/cfdi_recibidos/services/purchase_invoice_builder.py` — WIP, no modificar

---

## Riesgos / cuidados
- bench migrate requerido después de agregar DocType y campos nuevos
- El diálogo JS puede ser complejo; priorizar funcionalidad sobre estética
- item_resolver.py ya tiene búsqueda de candidatos — no duplicar lógica
