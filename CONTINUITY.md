# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-29
**Rama activa:** `chore/archive-docs-development` → PR #167 abierto
**Tarea actual:** PR #167 — limpieza docs/development post-merge PR #166

---

## Recuperación rápida

PR #167 archiva 18 documentos de docs/development/ después del merge de PR #166.
PR simple de docs, sin código, sin tests. Pendiente merge.

---

## Estado actual

### Completado
- PR #166 mergeado — pipeline CFDI Recibidos completo en main
- issue #152 cerrado
- sync-check.md actualizado (frappe-infrastructure `c055158`) con 3 reglas nuevas

### PR #167 — en revisión
- 13 docs marcados OBSOLETO + archivados
- 5 docs archivados sin nota
- 18 archivos movidos a docs/development/archive/

### Pendiente después de PR #167
- **Issue #165** — is_submittable para CFDI Recibido antes de producción
- 6 docs pendientes de verificación ADR en docs/development/
- 4 docs pendientes de decisión de ubicación permanente

### No repetir
- No proponer commits sin que el usuario lo solicite
- No incluir one_offs/ ni REPORTE_*.md en commits
- No hacer bench migrate sin autorización
- sync-check: leer cada doc antes de clasificar; nunca commitear en main

---

## Decisiones vigentes
- item_resolution options: Mapeado, Código proveedor, Específico,
  Sugerido, Nuevo especifico, Nuevo agrupador, Genérico, Manual
- tax_resolver valida cuenta_impuesto no vacía
- xml_ingestion NO auto-crea proveedores en upload
- classify_all_concepts solo auto-asigna "Código proveedor"

---

## Archivos relevantes ahora
- PR #167: https://github.com/luisrms69/facturacion_mexico/pull/167
- docs/development/ — 6 ADR pendientes, 2 vigentes, 4 pendientes permanente, 2 protegidos
- frappe-infrastructure/checkpoints/coderabbit-pr166-review.md — items CodeRabbit pendientes

---

## Riesgos / cuidados
- issue #165 (is_submittable) antes de producción
- 6 candidatos ADR sin convertir todavía
- api_backup.py escribe en /tmp/ — defecto pre-existente
