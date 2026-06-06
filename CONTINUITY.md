# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-06
**Rama activa:** `fix/issue-162-clave-sat-obligatoria`
**Tarea actual:** Commit listo — pendiente push + PR

---

## Recuperación rápida

Estoy trabajando en:
Issue #162 — eliminar fallback "01010101" para clave SAT en timbrado.

Objetivo inmediato:
Push → PR.

Criterio de avance:
PR mergeado, main sincronizado, continuar con issue #161 (Complemento Pago) o Fase 4.

---

## Estado actual

### Ya cerrado

- PR #177–#180 mergeados ✅
- Issue #162: fallback "01010101" eliminado, 3 capas de defensa implementadas ✅
- Validado en GUI (actiglobal-restore.dev:8406) ✅

### Pendiente inmediato

1. Push + PR de la rama actual
2. Decidir: issue #161 (Complemento Pago fallbacks) o Fase 4 (#153)

### No repetir

- Sin `set_posting_time = 1` → ERPNext silencia posting_date — ya corregido (PR #180)
- `or "01010101"` como fallback — eliminado en esta rama

---

## Decisiones vigentes

- Clave SAT obligatoria en flujo fiscal (no global en Item)
- 3 capas de defensa: SI validate hook (automated_tax) → FFM.validate() → timbrado_api
- Mensaje de error en español claro: "Clave SAT de Producto o Servicio"
- DashboardWidgetConfig write = solo System Manager (PR #180)
- PI posting_date = issue_date del XML (PR #180)

---

## Archivos modificados en esta rama

- `timbrado_api.py` — _validate_items_clave_sat_for_timbrado + defensa final + sin "01010101"
- `factura_fiscal_mexico.py` — _validate_items_clave_sat en validate()
- `hooks_handlers/sales_invoice_automated_tax.py` — mensaje error mejorado
- `tests/test_issue162_clave_sat_obligatoria.py` — 9 tests nuevos

### No tocar

- `one_offs/` — no se commitean
- `actiglobal-restore.dev` — enc_key DFP External Storage (no adjuntos)
