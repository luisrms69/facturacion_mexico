# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-07-17
**Rama activa:** `fix/cascade-cancel-01-transient-404-and-doc-reconcile`
**Tarea actual:** Fix — resiliencia de la cancelación de sustitución (motivo 01) ante fallos transitorios del PAC. En fase de commit (flujo `/ship`).

---

## Recuperación rápida

Estoy trabajando en:
Corrección de un defecto real en el flujo de sustitución motivo 01. Al timbrar el CFDI sustituto (B),
la cascada cancela el original (A) con `TipoRelación = 04`; un `404 invoice_not_found` transitorio del
PAC (consistencia eventual justo tras timbrar B) rompía el flujo y presentaba el timbrado exitoso de B
como error. La prueba de integración real (par A=`FFMX-2026-00045` / B=`FFMX-2026-00046`, FacturAPI TEST)
reprodujo el 404 de forma natural y destapó **tres defectos**: (1) B mostrado como error; (2) la
recuperación diferida no cancelaba nunca porque `cancelar_factura` exige `TIMBRADO` y devolvía
`{success: False}` sin excepción; (3) `run_auto_reconciliation` revertía `PENDIENTE_CANCELACION → TIMBRADO`
(valid/none) destruyendo la cancelación en curso.

Plan que estoy siguiendo:
Fix mínimo y proporcionado (sin campos nuevos, sin contadores, un solo scheduler): reintentos inmediatos
(0.5s/1s) → `PENDIENTE_CANCELACION` sin falsear el timbrado → scheduler cada minuto con throttle escalonado
y corte 2h → guard interno `_allow_pending_cancellation` (manual sigue exigiendo TIMBRADO) + manejo de
`{success: False}` → protección Gap 2 en reconciliación (no revertir sustitución vigente) → convergencia
documental idempotente. UX: mensaje amarillo, nunca falso error. Detalle en ADR-0037.

Objetivo inmediato:
Commit en la rama (flujo `/ship commit`), con código + tests + documentación exigida por el gate.
Sin push, sin PR (pendientes de autorización separada).

Criterio de avance:
Tests específicos verdes (`test_cascade_cancel_01_recovery` 15/15, `test_cancelacion_integridad` 37/37,
Gap 2 en `test_ffm_reconciliation`) + linters limpios + `mkdocs build --strict` limpio + validación real
en sandbox (A convergió a CANCELADO/docstatus=2, B TIMBRADO, XML `04 → UUID_A` PASS, local==PAC).

---

## Estado actual

### Ya cerrado
- **Cascada:** reintentos inmediatos transitorios (0.5s/1s); si se agotan, A → `PENDIENTE_CANCELACION`
  + `fm_sync_status=pending` + `fm_sync_error`, sin `frappe.throw` (B queda TIMBRADO).
- **Scheduler** `retry_pending_substitution_cancellations` (cron `* * * * *` en `hooks.py`): GET-first,
  throttle escalonado anclado en `B.fecha_timbrado` + `fm_last_pac_sync` (rápido 5 min → ~5 min → corte 2h),
  batch 50. Solo procesa orígenes de sustitución reales.
- **Guard acotado:** `cancelar_factura(..., _allow_pending_cancellation=True)` (keyword-only) para el
  reintento automático; manual intacto. Scheduler maneja excepción **y** `{success: False}`.
- **Gap 2:** `_es_origen_sustitucion_vigente` en `ffm_reconciliation`; la reconciliación (solo-lectura)
  no revierte `PENDIENTE_CANCELACION → TIMBRADO` de una sustitución con B TIMBRADO vigente.
- **Gap 3 / documental:** `_complete_documental_cancellation` única e idempotente (cascada/scheduler/reconcile).
- **UX:** `base_result.cancelacion_previa_pendiente` → mensaje amarillo en `factura_fiscal_mexico.js`.
- **Tests:** nuevo `test_cascade_cancel_01_recovery.py` (15) + Gap 2 en `test_ffm_reconciliation.py` (2)
  + adaptación de `test_cancelacion_integridad` al nuevo contrato.
- **Docs (gate):** ADR-0037, `docs/usuario/cancelar-cfdi.md`, `docs/tecnico/arquitectura.md`,
  `mkdocs.yml`, `docs/adr/index.md`.
- **Validación real (sandbox FacturAPI TEST):** flujo completo verificado end-to-end.

### Pendiente / siguiente paso
- Push + PR: requieren autorización explícita separada.
- Incidentes **separados** (no en este fix): duplicación de nodos `cfdi:Traslado` (IVA 0%); sistema de
  alertas en tiempo real; "error visual al timbrar hasta refresh".
- Artefactos locales sin commitear (correcto): `one_offs/` de validación, `poc-playwright-demo/val01/`.
- Servidor dev `facturacion-v16.dev:8888` levantado en tmux `serve_facturacion-v16_dev`.
