# ADR-0035 — Motor de reconciliación FFM ↔ FacturAPI

- **Estado:** Propuesto
- **Fecha:** 2026-06-21
- **Rama:** `feat/motor-reconciliacion-ffm`
- **Relacionado:** [[0034-integridad-correlacion-ffm]] (integridad y correlación del FFM)

---

## 1. Contexto y problema

Tras el bloque de integridad (ADR-0034), el estado local de una `Factura Fiscal Mexico` (FFM)
puede **divergir** del estado real en FacturAPI/SAT por causas históricas o respuestas inconclusas:

- ~70 FFM `TIMBRADO` con `fm_sync_status="pending"` (residuo del bug de doble FFM): ya tienen
  `fm_uuid` y `facturapi_id` —están timbrados ante el PAC— pero el flag local quedó en `pending`.
- Cancelaciones en `PENDIENTE_CANCELACION` cuyo desenlace (aceptación/rechazo/expiración) ocurre
  más tarde y nadie vuelve a consultar.

No existía un proceso que **consultara el PAC y alineara el estado local**. ADR-0034 declaró
expresamente que el motor de reconciliación NO formaba parte de ese bloque.

## 2. Decisión

Implementar un motor que **consulta** FacturAPI por **GET** y reconcilia el estado local del FFM,
reutilizando la infraestructura de ADR-0034 (correlación estricta, writer, Response Log).

**Principio rector:** el PAC es la fuente de verdad. El motor **solo lee**. Nunca timbra, cancela
ni sustituye CFDI, y nunca cancela la Sales Invoice.

### 2.1 Alcance inicial
Selector acotado a los FFM que necesitan seguimiento:

```
facturapi_id != ''  AND  (fm_sync_status = 'pending'  OR  status = 'PENDIENTE_CANCELACION')
```

Fuera de alcance: barrido del histórico completo, `fm_sync_status='error'`, reparación de
duplicados, archivado de huérfanos.

### 2.2 Operación contra el PAC
Exclusivamente `GET /invoices/{facturapi_id}`, vía `FacturAPIClient.get_invoice(ffm.facturapi_id)`.
**Prohibido:** `create_invoice`, `cancel_invoice`, cualquier POST/DELETE, timbrado o sustitución.
El cliente se construye con la compañía del FFM: `get_facturapi_client(company=ffm.company)`.

### 2.3 Identidad y correlación estricta
La reconciliación inicia con un `FFM.name` explícito; nunca se busca otro FFM por Sales Invoice,
UUID, folio o serie. Antes de decidir si hay cambios, se valida la correlación (reutilizando
`_resolve_validated_ffm` de ADR-0034): `response.id == ffm.facturapi_id` y `response.uuid ==
ffm.fm_uuid` (UUID normalizado). Ante contradicción → no se toca el estado fiscal, `fm_sync_status
= error`, y se preserva/registra `FiscalCorrelationError`.

### 2.4 Helper único de mapeo
`derive_pac_reconciliation(remote_status, cancellation_status) -> (estado_fiscal | None, fm_sync_status)`
en `facturacion_mexico/config/fiscal_states_config.py`. Es la **única fuente de verdad** del mapeo,
compartida por `cancelar_factura` (FASE 3), `revisar_estatus_cancelacion` y el motor.

| Estado remoto | Estado local | `fm_sync_status` |
|---|---|---|
| `valid` + sin cancelación | `TIMBRADO` (vigente) | `synced` |
| `valid` + `pending`/`verifying` | `PENDIENTE_CANCELACION` | `synced` |
| `valid` + `rejected`/`expired` | `TIMBRADO` | `synced` |
| `accepted` / `canceled` | `CANCELADO` | `synced` |
| `pending` (remoto no definitivo) | sin transición | `pending` |
| `draft`/desconocido | sin transición | `error` |

Precedencia: `status==canceled` manda sobre cualquier `cancellation_status` contradictorio.

### 2.5 Semántica de campos
- **`fm_sync_status`:** `synced` (respuesta concluyente reflejada) · `pending` (inconclusa:
  timeout/429/5xx/remoto pending) · `error` (no reintentable: 4xx, identidad contradictoria,
  estado desconocido).
- **`fm_last_pac_sync`** (Datetime): se actualiza **exclusivamente** cuando el GET fue exitoso y
  correlacionado con el mismo FFM (cambio o no-op). En **cualquier fallo de consulta** se conserva
  el valor anterior.

### 2.6 Persistencia y Response Log
- **Cambio** de `status`/`fm_sync_status` → `write_pac_response(operation_type="reconciliacion")`:
  persiste el FFM y crea Response Log correlacionado.
- **Sin cambios (no-op)** → solo se sella `fm_last_pac_sync`; **no** se crea Response Log.
- **Error/contradicción** → se registra (Response Log para errores HTTP; alerta crítica para
  contradicción de identidad) y se fija `fm_sync_status`, conservando `fm_last_pac_sync`.

### 2.7 Selector, lote y scheduler
- `BATCH_SIZE = 100`. Prioridad: `PENDIENTE_CANCELACION`, luego `pending`, luego `fm_last_pac_sync`
  más antiguo, luego `name`.
- Scheduler: una tarea en **`hourly_long`** → `run_auto_reconciliation`. Un FFM fallido no detiene
  el lote.

### 2.8 Verificación manual
Botón **"Verificar estado en FacturAPI"** (grupo **Comprobantes**) en el FFM, visible solo cuando
el documento está guardado y tiene `facturapi_id`. Llama al mismo núcleo (`reconcile_ffm` →
`_reconcile_ffm`). El JavaScript no contiene lógica fiscal: solo consulta, muestra el resultado y
recarga. El endpoint `reconcile_ffm` está whitelisted y exige el **mismo permiso fiscal que la
cancelación** (`frappe.only_for(System Manager / Facturacion Mexico System Manager / Manager)`).

### 2.9 Concurrencia (locks)
Locks de cache (Redis), no bloqueantes, con TTL, liberados en `finally`:
- Lote: `facturacion_mexico:ffm_auto_reconciliation` (TTL 2 h).
- Por-FFM: `facturacion_mexico:ffm_reconciliation:<name>` (TTL 5 min) — evita la carrera
  scheduler/botón sobre el mismo FFM.

Liberación con **compare-and-delete atómico** (script Lua): solo se borra la clave si su valor
sigue siendo el token del dueño, evitando que un proceso cuyo lock expiró borre el lock de otro.

### 2.10 Sin configuración, campos ni DocTypes nuevos
No se agrega campo de activación, ni nuevos campos, ni DocTypes, ni patches, ni fixtures, ni
cambios de esquema. El único cambio de despliegue es registrar el evento `hourly_long`.

## 3. Consecuencias

- Los ~70 FFM `TIMBRADO+pending` se reconcilian a `synced` al confirmar `valid` con el PAC.
- Las cancelaciones `PENDIENTE_CANCELACION` se resuelven solas hasta su estado terminal.
- **`expired` quedó unificado a `TIMBRADO`** en los tres flujos (antes la cancelación caía a
  `PENDIENTE_CANCELACION`). `accepted → CANCELADO` se conserva.
- El refactor de unificación toca `timbrado_api.py` (flujo de cancelación productivo): la suite de
  regresión de ADR-0034 es la red de seguridad.

## 4. Riesgos operativos y despliegue

`bench migrate` registra `hourly_long`; con el scheduler habilitado, **el motor empieza a correr
solo (cada hora) y a hacer GET reales contra FacturAPI**. Por eso el despliegue y la habilitación
del scheduler deben hacerse **únicamente cuando se autorice iniciar ese tráfico GET**. La primera
prueba será local y controlada en `llantascs-v16.dev` (backup de producción). `hourly_long` corre
para todas las companies con FFM pendientes; si una no tiene credenciales, el aislamiento por-FFM
evita que rompa el lote.

## 5. Alternativas descartadas

- **Modo dry-run:** descartado; el botón individual + el flag por respuesta concluyente cubren la
  necesidad de verificación previa sin un modo separado.
- **Nuevo DocType de log:** descartado; se reutiliza `FacturAPI Response Log`.
- **Búsqueda del FFM por Sales Invoice:** descartado; viola la correlación estricta de ADR-0034.
- **Barrido completo de todos los FFM:** descartado; el alcance se acota a los que necesitan
  seguimiento.
- **Botones con lógica fiscal en JavaScript:** descartado; toda la decisión fiscal y la seguridad
  viven en el servidor.

## 6. Despliegue (resumen)
```
bench --site <site> migrate            # registra hourly_long (a partir de aquí el motor puede correr solo)
bench build --app facturacion_mexico   # compila el asset JS del botón
bench --site <site> clear-cache
```
Habilitar el scheduler solo cuando se autorice el tráfico GET. No ejecutar una corrida PAC real
durante el desarrollo de esta feature.
