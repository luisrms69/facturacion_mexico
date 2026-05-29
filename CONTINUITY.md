# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-29
**Rama activa:** `feature/cfdi-recibidos-fase3-pi`
**Tarea actual:** PR #166 abierto — correcciones de linters CI bloqueantes

---

## Recuperación rápida

Estoy trabajando en:
PR #166 abierto. Se corrigieron 21 findings bloqueantes de CI (semgrep):
frappe-manual-commit, frappe-missing-translate-function-python,
frappe-sql-format-injection, missing-argument-type-hint.
Pendiente: merge del PR, cierre explícito de issue #152.

Plan que estoy siguiendo:
Issue #152 — criterios todos implementados; PR #166 es el paso final antes del merge.

Objetivo inmediato:
Push de las correcciones de linters al branch del PR para que CI pase.

Criterio de avance:
CI verde en PR #166 → merge a main → cerrar issue #152 si el usuario lo decide.

---

## Estado actual

### Ya cerrado (PR #166 cubre todo esto)
- Pipeline completo CFDI Recibido → Purchase Invoice (builder + TaxResolver)
- Idempotencia por fm_cfdi_uuid (casos A/B/C)
- Tolerancia configurable por empresa (absoluta MXN + porcentual %)
- Motor guiado de resolución de items (3 niveles + auto-aprendizaje)
- 84 Items genéricos GASTO-{CAT}-{NNN}
- Enforcement UOM SAT (E.1 política base, E.2 CFDI Recibidos, E.3 timbrado SI)
- Botón "Generar PI" individual + botón "Generar PIs pendientes" (batch best-effort)
- Bloqueo UI "Convertido a PI" (frm.disable_form + validate hook)
- Pipeline proveedores → departamentos → clasificación → conversión PI
- Configuracion CFDI Recibidos como hub central por empresa
- 40 tests pasando, GUI validada

### Correcciones de CI (este commit)
- invoice_uom_validator.py: frappe.throw con _() + type hint items: list
- queries.py: f-strings SQL → concatenación + type hints en ambas funciones
- api.py: 3 commits removidos (end-of-function), 4 con nosemgrep, type hint cfdi_names
- status_manager.py: type hints doc: object en compute_stage y compute_supplier_stage

### Pendiente
- CI verde en PR #166
- Merge del PR #166 a main
- Cierre explícito de issue #152 (decisión del usuario)
- Issue #165: is_submittable para CFDI Recibido — deuda técnica antes de producción
- Errores de documentación (>5000 líneas) — identificados pero no atendidos en esta sesión

### No repetir
- No proponer commits sin que el usuario lo solicite
- No incluir one_offs/ ni REPORTE_*.md en commits
- No hacer bench migrate sin autorización
- No reiniciar servidor sin autorización
- No usar "closes/fixes/resolves #152" en commits ni PRs
- No volver a incluir cost_center ni bill_no collision en pendientes de #152

---

## Decisiones vigentes
- Squash and merge recomendado para #166 (32 commits → 1 en main)
- Mensaje de squash sugerido documentado en conversación de 2026-05-28
- Tolerancia: abs=1.00 MXN y pct=0.5% en Configuracion CFDI Recibidos por empresa
- posting_date = issue_date del CFDI (no today())
- due_date = issue_date del CFDI (explícito, evita type mismatch con Payment Terms)
- Bloqueo "Convertido a PI" es temporal — issue #165 registra la deuda (is_submittable)
- frappe.flags.in_cfdi_builder como bypass del validate lock para saves internos
- TaxResolver lee de Configuracion CFDI Recibidos, no de Configuracion Fiscal Mexico
- Batch consulta internamente elegibles; no acepta lista seleccionada por usuario
- bench migrate ejecutado en test-facturacion.localhost y facturacion-v16.dev
- Commits en batch (frappe.db.commit en loop) son intencionales — nosemgrep documentado

---

## Archivos relevantes ahora

### Leer primero
- PR #166: https://github.com/luisrms69/facturacion_mexico/pull/166

### Probablemente editar
- Ninguno — trabajo del issue #152 completo, correcciones CI aplicadas

### No tocar
- facturacion_mexico/one_offs/ — nunca commitear
- docs/development/REPORTE_*.md — no commitear

---

## Riesgos / cuidados
- PR #166 tiene 32 commits + este fix de CI — usar squash and merge
- issue #165 (is_submittable) debe hacerse antes de producción
- api_backup.py escribe en /tmp/ — defecto pre-existente conocido
- bench migrate requerido en cualquier site nuevo
- Errores de documentación en CI pendientes de atención (>5000 líneas)
