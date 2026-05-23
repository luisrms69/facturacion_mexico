# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-23
**Último PR:** #157 — feat(cfdi-recibidos): Fase 2 — SupplierResolver, ConceptClassifier y CFDI Concepto Mapping
**Branch:** feature/issue151-cfdi-recibidos-fase2 → main (PR abierto)

---

## Cómo ponerse al tanto — leer en este orden

```
1. /home/erpnext/frappe-bench-v16/.claude/CLAUDE.md     ← reglas globales del bench
2. CLAUDE.md (raíz de este repo)                         ← contexto del app
3. Este archivo: CONTINUITY.md                           ← estado actual
4. gh pr view 157                                        ← último PR
```

---

## Estado del módulo cfdi_recibidos

### Fase 1 — ✅ Mergeada (PR #156, 2026-05-23)

| Componente | Estado |
|---|---|
| DocType `CFDI Recibido` | ✅ Funcional |
| DocType `CFDI Recibido Concepto` (child) | ✅ Funcional |
| Parser XML CFDI 4.0 | ✅ Funcional |
| Ingesta multi-archivo via API | ✅ Funcional |
| Deduplicación por UUID + hash | ✅ Funcional |
| Endpoint `upload_xml` | ✅ Funcional |

### Fase 2 — ⏳ PR #157 abierto

| Componente | Estado |
|---|---|
| DocType `CFDI Concepto Mapping` | ✅ Implementado, 18/18 tests |
| Servicio `SupplierResolver` | ✅ Implementado, tests OK |
| Servicio `ConceptClassifier` (3 niveles fallback) | ✅ Implementado, tests OK |
| Endpoints `resolve_supplier`, `classify_concepts`, `save_mapping_rule` | ✅ Implementados |
| UI inline en bandeja | ❌ Diferida a Fase 2.5 o Fase 3 |

### Restricciones de diseño confirmadas (no modificar sin PR)

- Child `CFDI Recibido Concepto` no almacena resultado de clasificación — estado derivado en servidor
- No autocreación de Suppliers
- Sin regex, sin priority, sin GroupedItem en mapping MVP
- Sin Custom Fields en Purchase Invoice

---

## PRs recientes

| PR | Descripción | Estado |
|---|---|---|
| #155 | docs: arquitectura CFDI Recibidos aprobada | Mergeado |
| #156 | feat: Fase 1 — ingesta, parser y DocTypes | Mergeado 2026-05-23 |
| #157 | feat: Fase 2 — SupplierResolver, ConceptClassifier, CFDI Concepto Mapping | Abierto |

---

## Próxima tarea

**Issue:** #152 — [CFDI Recibidos][Fase 3] PurchaseInvoiceBuilder, impuestos nativos y batch best-effort
**Épica:** #149 — [EPIC] CFDI Recibidos / Compras — MVP
**Dependencia:** PR #157 mergeado
**Rama a crear:** `feature/issue152-cfdi-recibidos-fase3`

**Pendientes de Fase 2 a resolver en Fase 2.5 o Fase 3:**
- UI inline en bandeja para resolver proveedor y clasificar conceptos
- Prueba manual explícita: fallback `supplier_rfc + any clave SAT`
- Prueba manual explícita: `save_mapping_rule` actualización de regla existente
- Advertencia en UI al vincular proveedor con RFC diferente al del CFDI

---

## Configuración de desarrollo

| Ítem | Valor |
|---|---|
| Bench | `/home/erpnext/frappe-bench-v16` |
| Site desarrollo | `facturacion-v16.dev` |
| Site tests | `test-facturacion.localhost` |
| Comando tests | `bench --site test-facturacion.localhost run-tests --app facturacion_mexico` |
| Fixtures | `bench --site facturacion-v16.dev export-fixtures --app facturacion_mexico` |
