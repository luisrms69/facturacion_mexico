# ADR-0036 — Integridad de la proyección de cancelación y consolidación del flujo manual

- **Estado:** Propuesto
- **Fecha:** 2026-06-24
- **Rama:** `fix/cancelacion-integridad`
- **Relacionado:** [[0034-integridad-correlacion-ffm]] (correlación estricta y writer) · [[0035-motor-reconciliacion-ffm]] (motor de reconciliación)
- **Extiende/corrige:** ADR-0035 (clasificación de cancelación, persistencia y flujo manual). **No** lo reemplaza por completo.

---

## 1. Contexto y problema

Tras ADR-0035, se detectaron en producción (LlantasCS) FFM marcadas localmente como `CANCELADO` que
**no estaban canceladas ante el SAT** o que quedaron con campos incompletos. Causas confirmadas
(forense sobre FFMX-2026-00117 y 00137):

1. **`CANCELADO` prematuro.** El writer clasificaba la respuesta de la cancelación por **HTTP 200**
   (`Solicitud Cancelación → CANCELADO`), ignorando `cancellation_status`. Una respuesta
   `valid + verifying` (la cancelación apenas se está verificando en el SAT) se marcaba CANCELADO.
2. **Crash `(1406) Data too long for column 'method'`** durante la finalización: el antipatrón
   `frappe.log_error(<texto largo>, "título")` contra la firma `log_error(title, message)` desbordaba
   la columna `method` (140) y abortaba la FASE 3, dejando `cancellation_reason` residual (`01`),
   `cancellation_date` vacía y el snapshot de la SI sin sincronizar.
3. **Finalización asíncrona incompleta.** El motor (ADR-0035) escribía solo `status` + `fm_sync_status`
   al llegar a CANCELADO; no completaba `cancellation_reason`/`cancellation_date`/snapshot SI.
4. **Duplicación de flujo manual.** Coexistían dos botones que consultaban el PAC: "Verificar estado
   en FacturAPI" (motor, con company/correlación/lock/permiso) y "Revisar Estatus Cancelación"
   (camino laxo, sin esas protecciones).
5. **Fecha de cancelación = `now()`** en vez del `canceled_at` real del PAC.

Efecto convergente: `CANCELADO` + `cancellation_reason="01"` + `cancellation_date` vacía + snapshot
SI stale → **la Sales Invoice no se podía cancelar** (el guard validaba el snapshot, no el estado real).

## 2. Decisión

### 2.1 Clasificación de cancelación **fail-closed** (corrige ADR-0035 §2.4)

El HTTP 200 confirma que la *solicitud* se procesó, **no** que el SAT canceló. La cancelación se
clasifica con un helper acotado `derive_cancellation_reconciliation(remote_status, cancellation_status)`:

| Respuesta PAC | Estado local |
|---|---|
| `status = canceled` | **CANCELADO** (único terminal) |
| `valid` + `pending` / `verifying` / `accepted` (aislado) | **PENDIENTE_CANCELACION** |
| `valid` + `rejected` / `expired` | TIMBRADO (sigue vigente) |
| `valid` + ninguno | TIMBRADO |
| desconocido / incoherente | sin transición (**nunca CANCELADO**) |

> **Corrección a ADR-0035:** `accepted` **aislado** (sin `status=canceled`) ya **no** produce
> CANCELADO. Solo `status=canceled` es terminal.

El mismo criterio se usa en los tres caminos: cancelación síncrona (FASE 3), `revisar_estatus_cancelacion`
y el motor de reconciliación.

### 2.2 Operación autoritativa única: `apply_cancellation_state`

Una sola función escribe el estado de cancelación, idempotente y monotónica:
- conserva `fm_motivo_cancelacion` (motivo SAT solicitado);
- deriva `cancellation_reason` desde ese motivo (sobrescribe residuos como `01`);
- fija `cancellation_date` (ver §2.4);
- fija `fm_sync_status` (valor derivado, no asumido);
- sincroniza `SI.fm_fiscal_status` **solo si** la SI apunta a esa FFM (`SI.fm_factura_fiscal_mx == FFM.name`);
- **monotonicidad:** una FFM `CANCELADO` **no se degrada** a PENDIENTE/TIMBRADO por una respuesta vieja;
- **reparación:** `CANCELADO → CANCELADO` **sí** ejecuta la parte reparadora para completar campos faltantes;
- devuelve si escribió algún campo (para decidir trazabilidad).

La escritura de estado en cancelación deja de pasar por el writer (que solo crea el Response Log con
`skip_state_persist`), eliminando la doble escritura / commit parcial.

### 2.3 Reparación idempotente desde el motor (extiende ADR-0035 §2.6)

El reconciliador ejecuta `apply_cancellation_state` en cancelaciones **aunque `status` y
`fm_sync_status` no cambien**, para reparar FFM terminales incompletas (reason/fecha/snapshot SI).
Se crea Response Log de reconciliación cuando hubo cambio real (status, sync **o** reparación de
campos); si nada cambió, no se crea log. **No** se altera el selector de candidatos asíncronos
(`_select_candidates`): el scheduler sigue procesando solo `pending` / `PENDIENTE_CANCELACION`.

### 2.4 `cancellation_date` desde `canceled_at` del PAC

La fecha de cancelación usa el `canceled_at` **real** que entrega FacturAPI (UTC ISO-8601 con `Z`),
normalizado a la zona horaria del sitio (`convert_utc_to_system_timezone`). `now()` solo se usa como
respaldo si el PAC no entrega `canceled_at`. Una `cancellation_date` ya existente nunca se sobrescribe.
Solo se fija fecha cuando el estado es CANCELADO.

### 2.5 Consolidación del flujo manual (corrige ADR-0035 §2.8)

Queda **un solo** botón de consulta: **"Verificar estado en FacturAPI"** (→ `reconcile_ffm`). El botón
duplicado "Revisar Estatus Cancelación" se eliminó. La función `revisar_estatus_cancelacion` se mantiene
por compatibilidad como **wrapper** que delega en `reconcile_ffm` (hereda company, correlación estricta,
lock por FFM y permiso fiscal; no realiza una segunda consulta al PAC).

### 2.6 Otros endurecimientos

- **Guard de cancelación de SI:** `cancelar_si_post_fiscal` valida el estado **real** de la FFM activa,
  no el snapshot `SI.fm_fiscal_status` (derivado).
- **Resolución de FFM en el endpoint de cancelación:** se resuelve la FFM activa por
  `SI.fm_factura_fiscal_mx` (validando el vínculo), no por `get_all(... limit=1)`.
- **`cancellation_reason` (Select):** primera opción **vacía** + `read_only`. Evita que una FFM nueva
  nazca con el motivo `01` implícito (default de Select de Frappe).
- **Logging:** las llamadas `frappe.log_error` del camino de cancelación usan argumentos nombrados
  (`title=`, `message=`); el fallo del logger ya no reemplaza la excepción original (corrige el 1406).

## 3. Consecuencias

- Una solicitud de cancelación en proceso permanece en `PENDIENTE_CANCELACION` hasta que el SAT confirme.
- El motor y la verificación manual **completan/reparan** FFM CANCELADO incompletas sin degradarlas.
- `cancellation_date` refleja el instante fiscal real (`canceled_at`).
- La SI vuelve a ser cancelable cuando la FFM activa está realmente CANCELADO.
- **Estado de los ADR:** ADR-0035 sigue vigente en lo relativo al motor (GET-only, correlación,
  selector de candidatos, scheduler `hourly_long`, locks, semántica de `fm_sync_status`/`fm_last_pac_sync`,
  sin DocTypes/campos nuevos). ADR-0034 sigue vigente (correlación estricta y writer). Este ADR-0036
  **corrige** la clasificación de cancelación y la persistencia de cancelación de ADR-0035, y **agrega**
  la proyección completa, la reparación idempotente, el `canceled_at` y la consolidación del flujo manual.

## 4. Validación

Validado en `llantascs-v16.dev` (backup de producción) con datos reales del PAC:
- **FFMX-2026-00137:** PAC `status=canceled`, motivo `02`, SAT `2026-06-23T18:01:23.572Z` → local
  `2026-06-23 12:01:23.572` (UTC-6), `cancellation_reason → 02`, `SI.fm_fiscal_status → CANCELADO`,
  Response Log de reconciliación, **0** nuevas solicitudes de cancelación, **0** nuevos errores 1406.
- Suites de regresión de ADR-0034/0035 verdes + suite nueva de integridad de cancelación.

## 5. Alternativas descartadas

- **Mantener los dos botones** alineando el laxo con company/correlación/lock/permiso: descartado;
  deja dos puertas para la misma operación.
- **Comando de "reparación" separado** del reconciliador: descartado; la reparación idempotente dentro
  del motor reutiliza el flujo único sin arquitectura nueva.
- **Incluir las FFM `CANCELADO` incompletas en el selector asíncrono:** descartado en este alcance; la
  reparación de terminales se hace por el botón manual, sin tocar `_select_candidates`.
- **Usar `now()` como fecha de cancelación:** descartado; no es el instante fiscal real cuando el PAC
  entrega `canceled_at`.
