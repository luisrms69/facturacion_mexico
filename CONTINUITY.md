# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-06
**Rama activa:** `feature/ereceipts-fase0-payload-y-trazabilidad`
**Tarea actual:** Issue #118 E-Receipts — Fase 0 lista para commit/push/PR

---

## Recuperación rápida

Estoy trabajando en:
Issue #118: E-Receipts flujo completo. Fase 0 (payload correcto + trazabilidad SI↔EReceipt)
implementada y validada. Commit autorizado, listo para ejecutar.

Plan que estoy siguiendo:
Plan arquitectónico aprobado: FacturAPI hace heavy lifting, ERPNext mantiene trazabilidad.
Fases: 0 (este commit) → 1 (self_invoice_url en UI) → 2 (sync) → 3 (factura individual) → 4 (FG).

Objetivo inmediato:
Commit Fase 0 → push → PR.

Criterio de avance:
PR abierto, CI verde, merge autorizado.

---

## Estado actual

### Ya cerrado
- PR #183 mergeado ✅ — issue #160 cerrado (hardcodes FG)
- PR #181 mergeado ✅ — issues #161 y #162 cerrados

### En progreso
- Rama `feature/ereceipts-fase0-payload-y-trazabilidad`: commit pendiente

### Pendiente inmediato
1. git commit (autorizado)
2. push → upstream
3. PR → main
4. Revisión + merge
5. Siguiente fase E-Receipts (#1: exponer self_invoice_url)

### No repetir
- `ruff check --fix` sobre app completa modifica tests ajenos — revertir antes del PR
- `git checkout -f main` necesario si CONTINUITY.md tiene cambios locales al cambiar de rama
- `fm_fiscal_status` options en fixture no se sincronizan via migrate solo — usar after_migrate
  (`setup/add_ereceipt_fiscal_states.py`) como patrón para opciones de Select fields
- `\n` dentro de `_()` dispara `frappe-translation-python-splitting`

---

## Decisiones vigentes

- **Fase 0 aprobada**: FacturAPI heavy lifting, ERPNext solo trazabilidad
- UUID/folio/invoice_id NUNCA en Sales Invoice — viven en EReceipt MX o Factura Global MX
- Widget usa relación SI → EReceipt MX → (Factura Global MX) — mismo patrón que FFM
- tax_rate/has_ieps en EReceipt MX son transitorios (#160) — definitivo es #182
- FiscalStates.E_RECEIPT y E_RECEIPT_FACTURADO como constantes
- after_migrate garantiza sync de opciones Select que fixtures no actualizan
- main nunca es rama de trabajo

---

## Archivos relevantes ahora

### Leer primero (si hay comentario de revisión en PR)
- `facturacion_mexico/ereceipts/api.py` — `_generar_facturapi_ereceipt` y helpers
- `facturacion_mexico/api/ereceipt_summary.py` — widget API
- `facturacion_mexico/public/js/si_ereceipt_summary.js` — widget JS

### Próximas fases
- **Fase 1**: exponer `self_invoice_url` en SI form (botón + widget)
- **Fase 2**: `sync_ereceipt()` + scheduler + botón manual
- **Fase 3**: `POST /receipts/{id}/invoice` desde ERPNext
- **Fase 4**: `POST /receipts/global-invoice` para Factura Global
- **Fase posterior**: webhooks, IEPS line-level (#182)

---

## Riesgos / cuidados

- EReceipts existentes sin `tax_rate` — al crear receipt en FacturAPI sin taxes, autofactura podría generar CFDI sin IVA
- `fm_ereceipt_summary_html` no muestra nada hasta Fase 1 (botón de creación)
- `setup/add_ereceipt_fiscal_states.py` debe ejecutarse con cada `bench migrate` (registrado en after_migrate)
