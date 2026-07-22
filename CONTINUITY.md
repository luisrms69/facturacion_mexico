# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-07-21
**Rama activa:** `fix/ffm-nace-error-fiscal-event-fallback`
**Tarea actual:** Fix — la Factura Fiscal Mexico (FFM) nacía en estado `ERROR` al crearse, sin ninguna llamada al PAC. Commit en la rama (flujo `/ship commit`). Validación GUI ya confirmada por el usuario.

---

## Recuperación rápida

Estoy trabajando en:
Corrección del bug "FFM nace en ERROR". Al crear una FFM (flujo normal desde Sales Invoice), la FFM
quedaba de inmediato en `ERROR` con todas sus implicaciones (botón "Reintentar Timbrado", badge de sync
rojo), **sin contactar a FacturAPI**. Causa raíz: los eventos de ciclo de vida de la FFM
(`create`/`status_change`) se escribían, vía un fallback (`_log_event_to_response_log`), como
respuestas PAC fallidas en `FacturAPI Response Log` (`success=0`, `operation_type` mapeado por defecto a
`"Consulta Estado"`, HTTP 500), porque el DocType `Fiscal Event MX` fue deprecado/eliminado. Luego
`calculate_fiscal_status_from_logs` marcaba `ERROR` ante **cualquier** log `success=0`.

Plan que estoy siguiendo:
Fix mínimo en dos capas (aprobado en revisión con ChatGPT):
- **Capa 1 (origen):** retirar por completo el fallback y su código muerto — `after_insert`, el bloque
  `create_fiscal_event` de `on_update`, y los métodos `create_fiscal_event` / `_log_event_to_response_log`.
  Los guards `fiscal_event_*` de `api/__init__.py` se conservan (defensivos y cubiertos por tests).
- **Capa 2 (blindaje):** `calculate_fiscal_status_from_logs` deriva `ERROR` fiscal **solo** de un
  `Timbrado` fallido, consistente con la regla canónica por operación de `api/__init__.py:790-816`.
  Consulta/reconciliación/cancelación fallidas pertenecen a `fm_sync_status`, no al estado fiscal.

Objetivo inmediato:
Commit en la rama (código + test + docs mínimos del gate; sin ADR). Sin push, sin PR (pendientes de
autorización separada). Después: investigar y registrar con `/ship issue` un problema DISTINTO (validación
fiscal temprana en Sales Invoice — `ObjetoImp=02` sin impuestos), sin mezclar código.

Criterio de avance:
Tests verdes (`test_ffm_nace_error_fiscal_event` 5/5, más sin regresión en `test_sync_status_semantics`
17, `test_cancelacion_integridad` 37, `test_cascade_cancel_01_recovery` 15) + `ruff` limpio +
`mkdocs build --strict` exit 0 + validación GUI del usuario OK (FFM nueva queda en `BORRADOR`).

---

## Estado actual

### Ya cerrado (en esta rama)

- **Capa 1:** eliminado el fallback a `FacturAPI Response Log` en `factura_fiscal_mexico.py`
  (`after_insert`, bloque `create_fiscal_event` de `on_update`, métodos `create_fiscal_event` y
  `_log_event_to_response_log`). `Factura Global MX` tiene su propio `create_fiscal_event` — no se tocó.
- **Capa 2:** `calculate_fiscal_status_from_logs` — `ERROR` solo si el último `Timbrado` falló y no hay
  timbrado/cancelación exitoso posterior. Se retiró la heurística de "cualquier `success=0` en 24h".
- **Tests:** `test_ffm_nace_error_fiscal_event.py` (5): nace BORRADOR sin logs sintéticos; timbrado
  fallido → ERROR; fallido→éxito → TIMBRADO; consulta fallida → NO ERROR; PENDIENTE_CANCELACION intacto.
- **Docs (gate):** `docs/tecnico/arquitectura.md` (derivación de estado fiscal) y
  `docs/usuario/troubleshooting.md` (FFM en ERROR sin timbrar). Sin ADR (corrige comportamiento contra
  el diseño existente, no es decisión nueva).

### Siguiente paso concreto

1. (Este commit) `/ship commit` en la rama. **Sin push ni PR** hasta autorización.
2. Investigar + `/ship issue` del problema de **validación fiscal temprana en Sales Invoice**
   (`ObjetoImp=02` sin impuestos por configuración fiscal de sucursal incompleta; se detecta tarde, en
   la FFM antes del timbrado). Solo issue, sin código, sin rama nueva.
3. **Remediación de datos (separada, futura, con autorización):** las FFM históricas ya pegadas en
   `ERROR` deben recalcularse (one-off idempotente por sitio) tras desplegar y validar el fix.

---

## Decisiones vigentes no reflejadas en código

- **RCA cronología (cerrada):** el bug estaba latente desde agosto 2025 (commits #37/#51/#60). El
  disparador operativo fue la eliminación efectiva del DocType `Fiscal Event MX` de la BD de producción
  entre el 15 y el 18 de junio de 2026 (no se conserva evidencia del deploy/migración específico). Antes
  del 15-jun el `frappe.db.exists` daba True y el fallback no corría; desde el 18-jun las FFM nacen en ERROR.
- **`fm_sync_status` / `fm_sync_error`:** NO se tocan en este fix (capa distinta con su propia derivación).
- **Config FacturAPI de `llantascs-v16.dev`** (aparte de este fix): ya saneada a sandbox (sk_live borrada,
  `sandbox_mode=1`); el usuario carga la `sk_test` real. Prevención universal en issue #215 (guards
  multi-capa + indicador de ambiente).
