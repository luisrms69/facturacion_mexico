# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-06
**Rama activa:** `feature/ereceipts-fase0-payload-y-trazabilidad`
**Tarea actual:** Issue #118 E-Receipts — Fase 0 completa, push + PR pendientes

---

## Recuperación rápida

Estoy trabajando en:
Issue #118: E-Receipts flujo completo. Fase 0 implementada con documentación completa.
Dos commits en la rama: (1) código Fase 0, (2) documentación para PR #183 y Fase 0.
Push y PR pendientes de autorización.

Plan que estoy siguiendo:
Plan arquitectónico aprobado: FacturAPI hace heavy lifting, ERPNext mantiene trazabilidad.
Fases: 0 (lista) → 1 (self_invoice_url en UI) → 2 (sync) → 3 (factura individual) → 4 (FG).

Objetivo inmediato:
Push → PR.

Criterio de avance:
PR abierto, CI verde, merge autorizado.

---

## Estado actual

### Ya cerrado
- PR #183 mergeado ✅ — issue #160 cerrado (hardcodes FG)
- PR #181 mergeado ✅ — issues #161 y #162 cerrados

### En progreso
- Rama `feature/ereceipts-fase0-payload-y-trazabilidad`: 2 commits, push pendiente
  - `5db2a13` — código Fase 0
  - (este commit) — documentación PR #183 + Fase 0

### Pendiente inmediato
1. `/ship push`
2. `/ship pr`

### No repetir
- Gate documental ahora está en `/ship commit` (ship.md actualizado en frappe-infrastructure)
- `ruff check --fix` sobre app completa modifica tests ajenos — revertir antes del PR
- `fm_fiscal_status` options en fixture no se sincronizan via migrate solo — usar after_migrate
- `\n` dentro de `_()` dispara `frappe-translation-python-splitting`

---

## Decisiones vigentes

- **Fase 0 aprobada**: FacturAPI heavy lifting, ERPNext solo trazabilidad — ADR-0032
- UUID/folio/invoice_id NUNCA en Sales Invoice — viven en EReceipt MX o Factura Global MX
- Widget usa relación SI → EReceipt MX → (FG) — mismo patrón que FFM
- Defaults silenciosos eliminados en Factura Global — ADR-0033
- after_migrate garantiza sync de opciones Select que fixtures no actualizan
- main nunca es rama de trabajo

---

## Archivos relevantes ahora

### Documentación actualizada en esta rama
- `docs/usuario/ereceipts.md` — nueva página E-Receipts / Autofactura
- `docs/tecnico/arquitectura.md` — flujo E-Receipt, Factura Global validaciones
- `docs/adr/0032-ereceipts-facturapi-arquitectura.md` — ADR Fase 0
- `docs/adr/0033-factura-global-hardcodes.md` — ADR PR #183

### Próximas fases E-Receipts
- Fase 1: exponer `self_invoice_url` en SI form (botón + widget)
- Fase 2: `sync_ereceipt()` + scheduler + botón manual
- Fase 3: `POST /receipts/{id}/invoice`
- Fase 4: `POST /receipts/global-invoice`
