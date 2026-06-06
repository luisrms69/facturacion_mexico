# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-05
**Rama activa:** `fix/pi-posting-date-y-dashboard-sql`
**Tarea actual:** Commit listo — validado en GUI, pendiente push + PR

---

## Recuperación rápida

Estoy trabajando en:
Rama `fix/pi-posting-date-y-dashboard-sql` con dos correcciones puntuales listas para PR.

Objetivo inmediato:
Push → PR.

Criterio de avance:
PR mergeado, main sincronizado.

---

## Estado actual

### Ya cerrado

- PR #177, #178, #179 mergeados ✅
- posting_date fix: set_posting_time=1 + guard issue_date vacío + tests ✅ (confirmado GUI)
- DashboardWidgetConfig: write quitado a Accounts Manager ✅

### Pendiente inmediato

1. Push + PR de la rama actual
2. Iniciar Fase 4 — Registrar Pago (#153) después del merge

### No repetir

- Mapeo Equivalencias SAT eliminado — no reintroducir
- actiglobal-restore.dev: enc_key DFP — no escribir
- Sin `set_posting_time = 1`, ERPNext ignora posting_date y usa today() — ya corregido

---

## Decisiones vigentes

- PI posting_date = issue_date del XML, usando `set_posting_time = 1`
- Si issue_date vacío → ValidationError, no se crea PI (no fallback a today)
- DashboardWidgetConfig write = solo System Manager
- auditoria_fiscal.py WHERE: confirmado seguro (campos internos + valores parametrizados)
- ereceipts expire_ereceipts: confirmado seguro (scheduler, sin input externo)
- Resolución contable CFDI Recibidos: 2 modos, sin fallbacks

---

## Archivos modificados en esta rama

- `cfdi_recibidos/services/purchase_invoice_builder.py` — set_posting_time + guard issue_date
- `cfdi_recibidos/tests/test_purchase_invoice_builder.py` — 3 tests fechas
- `dashboard_fiscal/doctype/dashboard_widget_config/dashboard_widget_config.json` — permisos

### No tocar

- `one_offs/` — no se commitean
- `actiglobal-restore.dev` — enc_key DFP External Storage
