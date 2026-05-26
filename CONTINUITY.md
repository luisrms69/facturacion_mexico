# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-25
**Rama activa:** `feature/cfdi-recibidos-fase3-pi`
**Último PR mergeado:** #156 (Fase 1) y #157 (Fase 2) — ambos en main

---

## Cómo ponerse al tanto — leer en este orden

```
1. /home/erpnext/frappe-bench-v16/.claude/CLAUDE.md     ← reglas globales del bench
2. CLAUDE.md (raíz de este repo)                         ← contexto del app
3. Este archivo: CONTINUITY.md                           ← estado actual
4. docs/development/cfdi-recibidos-fase-3-purchase-invoice.md ← plan Fase 3
```

---

## Estado del módulo cfdi_recibidos

### Fase 1 — ✅ Mergeada (PR #156)
### Fase 2 — ✅ Mergeada (PR #157)

### Fase 3 — 🔄 En progreso (rama: feature/cfdi-recibidos-fase3-pi)

**Rediseño UX aprobado 2026-05-25.** El flujo original (directo a clasificación y PI) fue
reemplazado por un flujo por etapas explícitas, una acción por etapa.

#### Etapas del flujo aprobado

```
Upload XML
  → XML inválido          (no crea doc)
  → Duplicado             (link al existente)
  → No aplicable          (doc creado, excluido del flujo)
  → Falta proveedor       (candidato a "Generar proveedores")
  → Proveedor encontrado  (siguiente: clasificar conceptos — hito futuro)
  [→ Falta clasificación  — hito futuro]
  [→ Listo para PI        — hito futuro]
  [→ Convertido a PI      — hito futuro]
  [→ Error conversión     — hito futuro]
```

#### Hito actual: Upload → Proveedor

**Objetivo:** Al subir XML, cada archivo queda en exactamente uno de estos estados:
`XML inválido`, `Duplicado`, `No aplicable`, `No procesar`, `Proveedor encontrado`, `Falta proveedor`

**Decisiones de diseño vigentes:**
- `cfdi_type` válido para este flujo: solo `"I"` (Ingreso) — leído de `sat.constants.TIPO_COMPROBANTE`
- Tipos no soportados (P, E, T, N) → doc creado con status `"No aplicable"`, no entra al flujo
- RFC receptor no coincide con empresa → NO crear doc, retornar `"XML inválido"`
- `no_procesar` es campo Check manual — el usuario lo activa después, no es resultado de carga
- NO clasificar conceptos en este hito
- NO llamar a ConceptClassifier, PurchaseInvoiceBuilder, TaxResolver ni API de PI
- Estados futuros (`Falta clasificación`, `Listo`, `Convertido a PI`, `Error conversión`) se conservan en el DocType

**Resultado de upload por archivo:**
```
file_name, cfdi_recibido, uuid, supplier_rfc,
supplier_found, status, candidato_generar_proveedor, message
```

#### Archivos a modificar en hito actual

| Archivo | Cambio |
|---|---|
| `cfdi_recibidos/services/xml_ingestion.py` | Eliminar classify_concepts; validar cfdi_type; RFC mismatch sin doc; agregar supplier_found y candidato al resultado |
| `cfdi_recibidos/doctype/cfdi_recibido/cfdi_recibido.json` | Agregar `no_procesar` (Check); agregar states `"Proveedor encontrado"` y `"No aplicable"` |
| `cfdi_recibidos/services/status_manager.py` | compute_stage solo devuelve Proveedor encontrado / Falta proveedor; agregar mensajes nuevos |
| `cfdi_recibidos/doctype/cfdi_recibido/cfdi_recibido_list.js` | Mostrar supplier_rfc, supplier_found, candidato en tabla de resultados |
| `cfdi_recibidos/tests/test_xml_ingestion.py` | Actualizar tests existentes; agregar tests para tipo P/E, RFC mismatch sin doc, supplier_found |

#### Tests mínimos aprobados

1. XML roto → `"XML inválido"`, sin doc
2. RFC receptor no coincide → `"XML inválido"`, sin doc
3. `cfdi_type="P"` → `"No aplicable"`, doc creado, `candidato=False`
4. `cfdi_type="E"` → `"No aplicable"`, doc creado, `candidato=False`
5. `cfdi_type="I"`, Supplier existe → `"Proveedor encontrado"`, `supplier_found=True`, `candidato=False`
6. `cfdi_type="I"`, sin Supplier → `"Falta proveedor"`, `supplier_found=False`, `candidato=True`
7. Duplicado → `"duplicado"`, `candidato=False`

**No hacer commit hasta validación GUI.**

---

## Componentes implementados en la rama (no en main aún)

| Componente | Estado |
|---|---|
| `PurchaseInvoiceBuilder` | ✅ Implementado, tests OK — en espera de hitos previos |
| `TaxResolver` (lee `Configuracion CFDI Recibidos`) | ✅ Implementado, 22/22 tests |
| DocType `Configuracion CFDI Recibidos` + wizard | ✅ Implementado |
| DocType `Regla Impuesto CFDI Recibido` (child) | ✅ Implementado |
| DocType `Tasa IVA SAT` (catálogo) | ✅ Implementado, fixture en repo |
| Endpoints `build_purchase_invoice`, `suggest_supplier_from_cfdi` | ✅ Implementados |
| `cfdi_recibido.json` — campo `status` como `Data` | ✅ Listo |
| `cfdi_recibido.json` — `states` con colores | ✅ Parcial (faltan estados nuevos del rediseño) |
| UI list JS — botón "Cargar XML" persistente | ✅ Funcional |

---

## Cambios sin commitear (sesión 2026-05-25)

- `cfdi_recibido.json` — status cambiado de Select a Data
- `cfdi_recibido_list.js` — nuevo archivo (untracked)
- `cfdi_recibido.js` — nuevo archivo (untracked)
- `status_manager.py` — nuevo archivo (untracked)
- `xml_ingestion.py` — ajustes menores mensaje duplicado

**Todos pendientes de commit — no commitear hasta terminar hito actual y validación GUI.**

---

## PRs recientes

| PR | Descripción | Estado |
|---|---|---|
| #155 | docs: arquitectura CFDI Recibidos aprobada | Mergeado |
| #156 | feat: Fase 1 — ingesta, parser y DocTypes | Mergeado |
| #157 | feat: Fase 2 — SupplierResolver, ConceptClassifier, CFDI Concepto Mapping | Mergeado |

---

## Configuración de desarrollo

| Ítem | Valor |
|---|---|
| Bench | `/home/erpnext/frappe-bench-v16` |
| Site desarrollo | `facturacion-v16.dev` |
| Site tests | `test-facturacion.localhost` |
| Seed tests | `bench --site test-facturacion.localhost execute facturacion_mexico.tests.ci_pre_tests.run` |
| Comando tests | `bench --site test-facturacion.localhost run-tests --module <módulo> --lightmode` |
| Fixtures | `bench --site facturacion-v16.dev export-fixtures --app facturacion_mexico` |
