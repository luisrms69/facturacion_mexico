# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-29
**Rama activa:** `feature/cfdi-recibidos-fase3-pi`
**Tarea actual:** PR #166 — correcciones pre-merge CodeRabbit aplicadas, pendiente CI verde y merge

---

## Recuperación rápida

Estoy trabajando en:
PR #166 abierto. CI verde tras correcciones semgrep/tests/docstrings.
Se aplicaron 9 correcciones pre-merge identificadas por CodeRabbit.
Pendiente: CI verde con estas correcciones → merge → cierre de issue #152.

Plan que estoy siguiendo:
Issue #152 — criterios implementados; PR #166 es el paso final.

Objetivo inmediato:
CI verde en PR #166 → merge a main.

Criterio de avance:
CI verde → merge a main → cerrar issue #152 si el usuario lo decide.

---

## Estado actual

### Commits de corrección CI + CodeRabbit en esta sesión

- `500a683` — 21 findings semgrep + 14 fallos tests (supplier_resolver,
  xml_ingestion, test_api_cfdi_recibidos, test_setup_expense_items,
  test_bloque_d_classification)
- `854dcf9` — 4 fallos tests restantes + interrogate 80%
  (pyproject.toml, test_api_cfdi_recibidos item fixture, test_supplier_resolver)
- Commit siguiente (pendiente push) — 9 correcciones pre-merge CodeRabbit:
  - item_resolution: options con acentos correctos + Específico faltante
  - api.py: "Generico" → "Genérico"
  - cfdi_recibido_list.js: escape_html en r.file_name y e.message (XSS)
  - cfdi_recibido.json: depends_on quita estado 'Error' muerto
  - configuracion_cfdi_recibidos.js: escape_html en warnings/message
  - mapeo_departamento: familia_sat reqd=1
  - regla_item: label "Item" → "Artículo"
  - tax_resolver: guard cuenta_impuesto vacía antes de _build_row

### Pendiente
- CI verde en PR #166 con las 9 correcciones
- Merge del PR #166 a main (squash and merge)
- Cierre explícito de issue #152 (decisión del usuario)
- Issue #165: is_submittable para CFDI Recibido — deuda técnica antes de producción

### Pendiente CodeRabbit (no atendido en este PR)
- FrappeTestCase en tests con unittest.TestCase (varios archivos)
- test_item_resolver.py: mocks de frappe.db (heavy lift)
- Naming/comments en inglés (concept_classifier, regla_item)
- Throttle en batch classify (cfdi_recibido_list.js)
- Parámetro config unused en wizard_cfdi_recibidos.py

### No repetir
- No proponer commits sin que el usuario lo solicite
- No incluir one_offs/ ni REPORTE_*.md en commits
- No hacer bench migrate sin autorización
- No usar "closes/fixes/resolves #152" en commits ni PRs

---

## Decisiones vigentes
- Squash and merge para PR #166
- Mensaje squash documentado en conversación 2026-05-28
- item_resolution options canónicos: Mapeado, Código proveedor, Específico,
  Sugerido, Nuevo especifico, Nuevo agrupador, Genérico, Manual
- tax_resolver valida cuenta_impuesto no vacía en regla activa antes de _build_row
- xml_ingestion: NO auto-crea proveedores en upload (Paso 7 eliminado)
- generate_missing_suppliers → "Proveedor encontrado" (no "Falta departamento")
- _assign_supplier → compute_supplier_stage (no compute_stage)
- classify_all_concepts: solo auto-asigna "Código proveedor", Mapeado requiere usuario
- bench migrate ejecutado en test-facturacion.localhost y facturacion-v16.dev

---

## Archivos relevantes ahora

### Leer primero
- PR #166: https://github.com/luisrms69/facturacion_mexico/pull/166

### Probablemente editar
- Ninguno — pendiente solo CI verde y merge

### No tocar
- facturacion_mexico/one_offs/ — nunca commitear
- docs/development/REPORTE_*.md — no commitear

---

## Riesgos / cuidados
- PR #166: 35 commits — usar squash and merge
- issue #165 (is_submittable) debe hacerse antes de producción
- api_backup.py escribe en /tmp/ — defecto pre-existente
- bench migrate requerido en cualquier site nuevo
- Las 9 correcciones CodeRabbit pueden activar tests de tax_resolver
  que testean cuenta_impuesto vacía (si existen)
