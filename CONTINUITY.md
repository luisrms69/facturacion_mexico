# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-04
**Rama activa:** `main` (post-merge PR #178)
**Tarea actual:** Preparar micro-PR de fixes CodeRabbit + continuar roadmap Fase 4

---

## Recuperación rápida

Estoy trabajando en:
PR #178 mergeado. Pendiente micro-PR con 3 fixes de CodeRabbit (PR #177 + #178).
Después de ese micro-PR, siguiente tarea es Fase 4 — Registrar pago (#153).

Objetivo inmediato:
1. Micro-PR de fixes CodeRabbit (ver propuesta en frappe-infrastructure/checkpoints/micro-pr-coderabbit-followup.md)
2. Iniciar Fase 4 — botón "Registrar Pago" con API nativa ERPNext (#153)

Criterio de avance:
Micro-PR mergeado + issue #153 iniciado.

---

## Estado actual

### Ya cerrado
- PR #177 mergeado: wizard PTCT porcentual + cargar_reglas Pagos ✅
- PR #178 mergeado: simplificación resolución contable 2 modos estrictos ✅
- bench migrate: test-facturacion.localhost + facturacion-v16.dev + actiglobal-restore.dev ✅

### Pendiente inmediato
1. Micro-PR: 3 fixes CodeRabbit (propuesta lista en checkpoints)
2. Issue #153: Fase 4 — Registrar Pago via API nativa ERPNext

### No repetir
- Mapeo Equivalencias SAT eliminado — no reintroducir
- actiglobal-restore.dev: problema enc_key DFP External Storage — no escribir

---

## Decisiones vigentes
- Resolución contable CFDI Recibidos: 2 modos (Manual / Automatico CoA SAT), sin fallbacks
- fm_codigo_sufijo_sat se puebla via after_migrate (81 item groups)
- Micro-PR CodeRabbit pendiente: ver frappe-infrastructure/checkpoints/micro-pr-coderabbit-followup.md

---

## Archivos relevantes ahora

### Leer primero
- `frappe-infrastructure/checkpoints/micro-pr-coderabbit-followup.md` — propuesta micro-PR

### No tocar
- `one_offs/` — no se commitean
- `actiglobal-restore.dev` — problema enc_key DFP External Storage
