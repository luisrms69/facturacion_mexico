# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-06
**Rama activa:** `feature/ereceipts-fase0-payload-y-trazabilidad`
**Tarea actual:** PR #184 listo para merge — pendiente bench update en producción

---

## Recuperación rápida

Estoy trabajando en:
Issue #118 E-Receipts. Fase 0 completa. PR #184 abierto con CI verde.
El usuario está haciendo `bench update` antes del merge.
Una vez que el bench update termine, el PR puede mergearse.

Plan que estoy siguiendo:
ADR-0032 (arquitectura FacturAPI heavy lifting, ERPNext solo trazabilidad).
Fases: 0 (✅ lista en PR #184) → 1 (exponer self_invoice_url) → 2 (sync) → 3 (factura individual) → 4 (FG via API).

Objetivo inmediato:
Merge PR #184 → abrir rama para Fase 1.

Criterio de avance:
PR #184 mergeado a main. CONTINUITY.md actualizado en main post-merge.

---

## Estado actual

### Ya mergeado
- PR #183 ✅ — eliminar hardcodes fiscales en Factura Global (#160)
- PR #181 ✅ — fallbacks silenciosos forma de pago y clave SAT (#161 #162)

### Listo para merge
- PR #184 — Fase 0 E-Receipts (#118)
  - `5db2a13` feat: código Fase 0 (payload, trazabilidad, DocType, custom fields)
  - `3c8811a` docs: ADR-0032, ADR-0033, ereceipts.md, arquitectura
  - `59a4a35` fix: correcciones CodeRabbit (C1-C14)
  - CI: ✅ verde
  - URL: https://github.com/luisrms69/facturacion_mexico/pull/184

### Pendiente inmediato
1. Merge PR #184 (después de bench update)
2. Abrir `feature/ereceipts-fase1-url-ui` para Fase 1

### No repetir
- `mock_db_get.return_value = None` rompe tests si `_get_product_key_for_item` lanza throw → usar helper `_db_get_with_product_key`
- `frappe.throw` en función mockeada llama `frappe.get_doc` con kwargs → mockear también `frappe.log_error` en esos tests
- Gate documental en `/ship commit` — docs van en el mismo commit que el código, no después
- `fm_fiscal_status` options en fixtures no se sincronizan via migrate → usar after_migrate (`setup/add_ereceipt_fiscal_states.py`)

---

## Decisiones vigentes — Fase 0 E-Receipts

- **ADR-0032:** FacturAPI hace el heavy lifting; ERPNext solo trazabilidad y control
- UUID/folio/invoice_id **nunca** en Sales Invoice — viven en EReceipt MX o FG MX
- Widget sigue relación SI → EReceipt MX → (FG MX si aplica) — patrón idéntico a FFM
- `cancel_ereceipt()`: solo persiste "cancelled" si FacturAPI confirma la cancelación
- `_get_product_key_for_item`: lanza ValidationError si falta `fm_producto_servicio_sat` — no fallback
- `FiscalStates.to_dict()` exporta `E_RECEIPT` y `E_RECEIPT_FACTURADO`
- `get_ereceipt_summary()` verifica permisos read antes de exponer datos fiscales
- Botón "Copiar URL" usa `data-url` + `addEventListener` — no `onclick` inline

---

## Fases siguientes E-Receipts (#118)

| Fase | Objetivo | Estado |
|---|---|---|
| 0 | Payload correcto + trazabilidad SI↔EReceipt | ✅ En PR #184 |
| 1 | Exponer self_invoice_url en UI (botón envío email) | Pendiente |
| 2 | Sincronización de estado (scheduler + manual) | Pendiente |
| 3 | Facturar individualmente via `POST /receipts/{id}/invoice` | Pendiente |
| 4 | Factura Global via `POST /receipts/global-invoice` | Pendiente |
| ∞ | Webhooks, IEPS line-level (#182) | Futuro |

---

## Archivos relevantes para Fase 1 (referencia)
- `facturacion_mexico/ereceipts/api.py` — `crear_ereceipt()`, agregar botón envío email
- `facturacion_mexico/api/ereceipt_summary.py` — widget de estado
- `facturacion_mexico/public/js/si_ereceipt_summary.js` — widget UI
- `facturacion_mexico/facturacion_fiscal/api_client.py` — cliente FacturAPI
