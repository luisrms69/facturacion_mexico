# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-29
**Rama activa:** `feature/cfdi-recibidos-fase3-pi`
**Tarea actual:** PR #166 — correcciones CI en curso, pendiente CI verde

---

## Recuperación rápida

Estoy trabajando en:
PR #166 abierto. Se corrigieron semgrep (21 findings), 14 fallos de tests,
4 fallos adicionales de tests y cobertura de docstrings (interrogate 80%).
Pendiente: CI verde → merge → cierre de issue #152.

Plan que estoy siguiendo:
Issue #152 — criterios implementados; PR #166 es el paso final.

Objetivo inmediato:
CI verde en PR #166 → merge a main.

Criterio de avance:
CI verde → merge a main → cerrar issue #152 si el usuario lo decide.

---

## Estado actual

### Commits de corrección CI en esta sesión (sobre PR #166)

- `500a683` — 21 findings semgrep + 14 fallos tests (supplier_resolver,
  xml_ingestion, test_api_cfdi_recibidos, test_setup_expense_items,
  test_bloque_d_classification)
- Commit siguiente (pendiente push) — 4 fallos tests restantes + interrogate:
  - pyproject.toml: [tool.interrogate] excluye cfdi_recibidos/tests, fail-under=80
  - test_api_cfdi_recibidos: _get_or_create_expense_item + item_code en _make_cfdi
  - test_supplier_resolver: db.set_value post-insert en _make_cfdi

### Pendiente
- CI verde en PR #166
- Merge del PR #166 a main
- Cierre explícito de issue #152 (decisión del usuario)
- Issue #165: is_submittable para CFDI Recibido — deuda técnica antes de producción

### No repetir
- No proponer commits sin que el usuario lo solicite
- No incluir one_offs/ ni REPORTE_*.md en commits
- No hacer bench migrate sin autorización
- No usar "closes/fixes/resolves #152" en commits ni PRs
- No volver a incluir cost_center ni bill_no collision en pendientes de #152

---

## Decisiones vigentes
- Squash and merge para PR #166 (34 commits → 1 en main)
- Mensaje squash documentado en conversación 2026-05-28
- Tolerancia PI: abs=1.00 MXN y pct=0.5% en Configuracion CFDI Recibidos
- posting_date = issue_date del CFDI; due_date = issue_date del CFDI
- Bloqueo "Convertido a PI" temporal — issue #165 (is_submittable)
- frappe.flags.in_cfdi_builder como bypass del validate lock
- TaxResolver lee de Configuracion CFDI Recibidos, no de Configuracion Fiscal Mexico
- Batch: commit por CFDI exitoso (best-effort), nosemgrep documentado
- xml_ingestion: NO auto-crea proveedores en upload (Paso 7 eliminado)
- generate_missing_suppliers → "Proveedor encontrado" (no "Falta departamento")
- _assign_supplier → compute_supplier_stage (no compute_stage)
- classify_all_concepts: solo auto-asigna "Código proveedor", Mapeado requiere usuario

---

## Archivos relevantes ahora

### Leer primero
- PR #166: https://github.com/luisrms69/facturacion_mexico/pull/166

### Probablemente editar
- Ninguno — pendiente solo CI verde

### No tocar
- facturacion_mexico/one_offs/ — nunca commitear
- docs/development/REPORTE_*.md — no commitear

---

## Riesgos / cuidados
- PR #166: 34 commits — usar squash and merge
- issue #165 (is_submittable) debe hacerse antes de producción
- api_backup.py escribe en /tmp/ — defecto pre-existente
- bench migrate requerido en cualquier site nuevo
