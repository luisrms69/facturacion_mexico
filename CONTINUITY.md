# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-06
**Rama activa:** `feature/ereceipts-fase0-payload-y-trazabilidad`
**Tarea actual:** PR #184 — correcciones CodeRabbit listas para push

---

## Recuperación rápida

Estoy trabajando en:
Issue #118 E-Receipts Fase 0. PR #184 abierto. Correcciones CodeRabbit aplicadas y en commit.
Pendiente: push del commit fix-up.

Plan que estoy siguiendo:
ADR-0032 (arquitectura FacturAPI heavy lifting). Fases 0→1→2→3→4.

Objetivo inmediato:
Push commit fix-up → CI verde → merge.

Criterio de avance:
CI verde en PR #184, merge autorizado.

---

## Estado actual

### Ya cerrado
- PR #183 mergeado ✅ — hardcodes FG
- PR #181 mergeado ✅ — fallbacks silenciosos

### En progreso
- PR #184 abierto — Fase 0 E-Receipts
  - commit 1: `5db2a13` código Fase 0
  - commit 2: `3c8811a` documentación
  - commit 3: (este) correcciones CodeRabbit
  - Pendiente: push

### Pendiente inmediato
1. Push del commit fix-up de CodeRabbit
2. CI verde
3. Merge autorizado

### No repetir
- `mock_db_get.return_value = None` rompe tests cuando `_get_product_key_for_item` lanza throw — usar `_db_get_with_product_key` helper
- `frappe.throw` en función mockeada llama `frappe.get_doc` con kwargs — mockear también `frappe.log_error` en esos tests
- Gate documental en `/ship commit` — docs van en el mismo commit que el código

---

## Decisiones vigentes (CodeRabbit fixes aplicados)

- C1: `cancel_ereceipt()` solo persiste "cancelled" si FacturAPI confirma
- C2: `FiscalStates.to_dict()` exporta E_RECEIPT y E_RECEIPT_FACTURADO
- C3: `get_ereceipt_summary()` verifica permisos read antes de retornar datos
- C7: botón "Copiar URL" usa data-url + addEventListener (no onclick inline)
- C11: `_get_product_key_for_item` lanza ValidationError si falta clave SAT — no fallback

---

## Archivos relevantes ahora
- `facturacion_mexico/ereceipts/doctype/ereceipt_mx/ereceipt_mx.py` — cancel_ereceipt
- `facturacion_mexico/api/ereceipt_summary.py` — permisos
- `facturacion_mexico/ereceipts/api.py` — _get_product_key_for_item
- `facturacion_mexico/public/js/si_ereceipt_summary.js` — widget
