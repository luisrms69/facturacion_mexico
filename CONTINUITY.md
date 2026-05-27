# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-26  
**Rama activa:** `feature/cfdi-recibidos-fase3-pi`  
**Último commit:** `30022f9` — Bloque A completado (84 Items genéricos de gasto)

---

## Recuperación rápida

Módulo en trabajo: **CFDI Recibidos** — flujo de recepción y procesamiento de facturas de proveedores.

### ⚠️ LEER ESTO AL REGRESAR — en este orden

1. **`docs/development/PLAN_CFDI_RECIBIDOS_ITEMS_GASTO_UOM.md`** ← **PLAN DE IMPLEMENTACIÓN ACTIVO**  
   Es el documento que rige todo el trabajo actual y futuro de clasificación → PI.  
   Contiene: arquitectura de Bloques A-E, matriz 84 Items, decisiones DC-01 a DC-11, estado por bloque.  
   **Leer completo antes de tocar cualquier código de clasificación, ItemResolver o PI.**

2. `docs/development/PLAN_ACTUAL_CFDI_RECIBIDOS.md` — contexto general del módulo (hitos A/B/C ya completados). Solo si se necesita recuperar el porqué del flujo Upload → Proveedor → Department.

**No usar ningún otro archivo de `docs/development/` como guía. Los demás son obsoletos o reportes puntuales.**

---

## Estado actual por hito

### Completado en esta rama

| Hito | Commit | Descripción |
|---|---|---|
| Hito A | `7c6b44f` | Upload XML → Proveedor resuelto (SupplierResolver) |
| Hito B | `ac318a7` | Generar proveedores faltantes |
| Hito C.1 | `40638d5` | Configuracion CFDI Recibidos + defaults proveedor + Payment Terms |
| Item Groups gastos | `82e9849` | 96 grupos (11 padre + 84 hoja) bajo "Gastos", idempotente |
| Hito C.2 | `8699ae7` | Department assignment: campo, status, endpoints, GUI, 23 tests |
| Parser NoIdentificacion | `c9f61d7` | Parsea NoIdentificacion en conceptos + tipo_factor/tasa_cuota en retenciones |
| **Bloque A** | **`30022f9`** | **84 Items genéricos de gasto (GASTO-{CAT}-{NNN}), setup idempotente, 10 tests** |

### Pendiente de implementar (en orden)

| Bloque | Descripción | Estado |
|---|---|---|
| **Bloque B** | Campos `item_group`, `item_code`, `item_resolution` en CFDI Recibido Concepto + estados "Falta clasificación"/"Clasificado" | ❌ No iniciado |
| **Bloque C** | `ItemResolver` — propone Item por 3 niveles (Mapeado → Específico → Genérico) | ❌ No iniciado |
| **Bloque D** | UI/API de clasificación de conceptos | ❌ No iniciado |
| **Bloque E** | Diagnóstico y limpieza UOM no-SAT — **prerequisito hard de PI** | ❌ No iniciado |
| **PI Builder** | Generar Purchase Invoice desde CFDI Recibido | ❌ Bloqueado hasta Bloque E |

---

## Deuda técnica conocida

### 3 tests fallando en suite completa

**Archivo:** `facturacion_mexico/cfdi_recibidos/tests/test_concept_classifier.py`  
**Causa:** `compute_stage()` en `status_manager.py` evalúa `doc.department` antes de clasificación.  
Los tests crean CFDIs con supplier pero sin department → siempre retorna "Falta departamento".  
**Tests afectados:**
1. `TestMatchingExacto.test_status_doc_listo` — espera "Listo", obtiene "Falta departamento"
2. `TestSinMatch.test_status_doc_falta_clasif` — espera "Falta clasificación", obtiene "Falta departamento"
3. `TestSinMatch.test_child_no_recibe_clasificacion` — `hasattr()` en Frappe doc retorna True para campos inexistentes

**Decisión:** Aceptados como deuda de Bloque B. Los tests se corregirán cuando se implemente Bloque B (el setup de los tests debe asignar department antes de llamar `classify_concepts()`).  
**No commitear con tests fallando** — correr solo por módulo específico para Bloque A.

---

## Git status al cerrar sesión

Working tree limpio. Solo untracked excluidos permanentemente:
- `docs/development/REPORTE_INVESTIGACION_SAT_CFDI_RECIBIDOS.md` — reporte arquitectónico TaxResolver, **leer antes de tocar tax_resolver.py**
- `docs/development/REPORTE_NORMATIVA_NOTA_CREDITO_PENDIENTES.md` — reporte normativa
- `facturacion_mexico/one_offs/` — ~11 scripts de diagnóstico (nunca commitear)

---

## Próxima sesión — qué hacer primero

1. Leer `PLAN_CFDI_RECIBIDOS_ITEMS_GASTO_UOM.md` sección 11 (Bloques B-E) y sección 10 (campos nuevos)
2. Leer `PLAN_ACTUAL_CFDI_RECIBIDOS.md` para contexto general
3. Leer `REPORTE_INVESTIGACION_SAT_CFDI_RECIBIDOS.md` (untracked) si se va a tocar TaxResolver
4. Confirmar que la rama es `feature/cfdi-recibidos-fase3-pi` antes de tocar código
5. **Próximo trabajo:** Bloque B — agregar campos a `cfdi_recibido_concepto.json` + controller + estados

Comando para correr tests de Bloque A (módulo específico, no suite completa):
```bash
bench --site test-facturacion.localhost run-tests \
  --module facturacion_mexico.tests.test_setup_expense_items --lightmode
```

---

## Decisiones vigentes

- `compute_stage()` evalúa: supplier → department → clasificación conceptos → Listo
- Department solo determina familia SAT (601/602/603/604). No resuelve Item Group.
- Item Group es dimensión independiente, asignada por usuario en UI de clasificación.
- Bloqueo (no advertencia) si item_group del concepto ≠ item_group del Item seleccionado
- KWH no está en fixture — ítem #51 (Energía eléctrica) usa MON provisional. Bloqueante antes de PI.
- 9 códigos ClaveProdServ 🔴 son placeholders — validar contra c_ClaveProdServ.xls antes de producción
- `CFDI Concepto Mapping` con `target_type='ExpenseAccount'` es ignorado por ItemResolver (futuro)
- No tocar `tax_resolver.py`, `purchase_invoice_builder.py` sin leer REPORTE primero
- Linters obligatorios antes de commit: `ruff check` + `ruff format` para `.py`, `prettier@2.7.1` para `.js`

---

## Archivos clave del módulo

| Archivo | Qué es |
|---|---|
| `facturacion_mexico/cfdi_recibidos/services/status_manager.py` | `compute_stage()` — flujo de estados |
| `facturacion_mexico/cfdi_recibidos/services/concept_classifier.py` | `classify_concepts()` — matching Concepto Mapping |
| `facturacion_mexico/cfdi_recibidos/services/supplier_resolver.py` | `resolve_supplier()` |
| `facturacion_mexico/cfdi_recibidos/doctype/cfdi_recibido_concepto/cfdi_recibido_concepto.json` | Schema concepto (campos Bloque B van aquí) |
| `facturacion_mexico/setup/cfdi_received_expense_items.py` | Setup 84 Items genéricos (Bloque A) |
| `facturacion_mexico/setup/cfdi_received_expense_item_groups.py` | Setup 96 Item Groups |
| `facturacion_mexico/cfdi_recibidos/api.py` | Endpoints públicos |

---

## Configuración de desarrollo

| Ítem | Valor |
|---|---|
| Bench | `/home/erpnext/frappe-bench-v16` |
| Site desarrollo | `facturacion-v16.dev` |
| Site tests | `test-facturacion.localhost` |
| Seed tests | `bench --site test-facturacion.localhost execute facturacion_mexico.tests.ci_pre_tests.run` |
| Tests Bloque A | `bench --site test-facturacion.localhost run-tests --module facturacion_mexico.tests.test_setup_expense_items --lightmode` |
| Tests dept assignment | `bench --site test-facturacion.localhost run-tests --module facturacion_mexico.cfdi_recibidos.tests.test_department_assignment --lightmode` |
| Tests dept mapping | `bench --site test-facturacion.localhost run-tests --module facturacion_mexico.cfdi_recibidos.tests.test_department_mapping --lightmode` |
| Tests supplier | `bench --site test-facturacion.localhost run-tests --module facturacion_mexico.cfdi_recibidos.tests.test_supplier_resolver --lightmode` |
| Tests Item Groups | `bench --site test-facturacion.localhost run-tests --module facturacion_mexico.tests.test_setup_expense_item_groups --lightmode` |
