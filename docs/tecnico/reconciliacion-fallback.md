# Reconciliación FFM ↔ FacturAPI y fallback de timbrado

> **Estado:** este documento describe los mecanismos de resiliencia **vigentes**:
>
> 1. **Reconciliación FFM ↔ FacturAPI** (consultas GET de solo lectura, por scheduler y botón
>    manual): el código está presente; **pendiente de una prueba operativa controlada** (no
>    ejecutada aún).
> 2. **Fallback de timbrado**: persistencia de la respuesta RAW del PAC en un archivo bajo
>    **archivos privados del sitio**, con advertencia visible al usuario. El archivo conserva la
>    evidencia, pero **no es por sí mismo una recuperación automática**.
>
> El mecanismo histórico de recuperación por `/tmp` con `api_backup.py` fue **removido** (PR #142) y
> **ya no forma parte de la arquitectura**; no se documenta aquí.

---

## 1. Propósito

La reconciliación mantiene el estado local de cada **Factura Fiscal Mexico (FFM)** alineado
con el estado real del CFDI en **FacturAPI** (el PAC). Su única operación contra el PAC es
un **GET de solo lectura** (`client.get_invoice(facturapi_id)`); nunca timbra ni cancela.

Resuelve el hueco entre "el PAC ya hizo algo" y "el sistema local lo refleja": timbrados o
cancelaciones cuya respuesta se perdió por timeout, fallo de BD o error posterior a una
respuesta exitosa del PAC. La verdad fiscal siempre reside en el PAC/SAT; el estado local
es una proyección que la reconciliación acerca a esa verdad.

**Fuente:** `facturacion_fiscal/services/ffm_reconciliation.py` (docstring del módulo y
`_reconcile_ffm`).

> **Garantía de diseño (docstring del módulo):** *"nunca create_invoice / cancel_invoice;
> nunca busca otro FFM por Sales Invoice; nunca cancela ni guarda la Sales Invoice"*. La
> reconciliación **no debe retimbrar ni cancelar** documentos por iniciativa propia fuera de
> los flujos diseñados. La única excepción acotada es completar la cancelación **documental**
> (no fiscal, sin llamar al PAC) de un CFDI ya CANCELADO que es origen de una sustitución
> motivo 01 con sustituto TIMBRADO vigente (`_reconcile_substitution_documental`).

---

## 2. Ejecución automática por scheduler

Frecuencias reales declaradas en `hooks.py` (`scheduler_events`):

| Frecuencia | Función | Rol |
|---|---|---|
| `hourly_long` | `facturacion_fiscal.services.ffm_reconciliation.run_auto_reconciliation` | Reconciliación FFM ↔ FacturAPI por lote. Solo GET; nunca timbra ni cancela. |
| `cron: * * * * *` (cada minuto) | `facturacion_fiscal.timbrado_api.retry_pending_substitution_cancellations` | Reintento diferido de cancelaciones motivo 01 (sustitución) que quedaron `PENDIENTE_CANCELACION`. |
| `weekly` | `facturacion_fiscal.tasks.sync_folio_fiscal_scheduled` | Red de seguridad: reconcilia `SI.fm_folio_fiscal` con `FFM.folio`. Idempotente, **sin** FacturAPI. |

`run_auto_reconciliation(limit=None)` es el punto de entrada del scheduler y de ejecución
manual por lote. Adquiere el lock global de lote, selecciona candidatos, procesa cada FFM de
forma aislada (un fallo no detiene el lote: `frappe.log_error` + continúa) y devuelve un
resumen con `selected/processed/changed/unchanged/pending/errors/locked`.

**Fuente:** `hooks.py` (líneas 447–479); `ffm_reconciliation.py::run_auto_reconciliation`.

---

## 3. Botón manual "Verificar estado en FacturAPI"

En el formulario de **Factura Fiscal Mexico** existe el botón **"Verificar estado en
FacturAPI"** (grupo "Comprobantes"), visible para cualquier FFM guardado que tenga
`facturapi_id`, sin importar su estado de sync/cancelación.

- Llama a `ffm_reconciliation.reconcile_ffm(ffm_name)` (whitelisted) con `freeze: true`
  (congela la UI e impide doble clic durante la consulta).
- El JS **solo** consulta, traduce el `outcome` a un texto breve
  (`changed/unchanged/locked/pending/error`) y recarga el formulario. **No** interpreta
  `status`/`cancellation_status`, **no** decide estados ni escribe campos: toda la lógica y
  la seguridad viven en el servidor.
- `reconcile_ffm` valida que el FFM exista y aplica `frappe.only_for(FISCAL_ROLES)` — los
  mismos roles que la cancelación fiscal (`System Manager`, `Facturacion Mexico System
  Manager`, `Facturacion Mexico Manager`, idénticos a `cancel_ffm_keep_si`, PR #197).

Tanto el botón manual como el lote automático ejecutan **exactamente** el mismo núcleo
`_reconcile_ffm`.

**Fuente:** `factura_fiscal_mexico.js` (líneas ~2735–2778);
`ffm_reconciliation.py::reconcile_ffm`.

---

## 4. Selección de candidatos, locks e idempotencia

### Selección de candidatos

`_select_candidates(limit=None)` (SQL de **solo lectura**) selecciona FFM que tengan
`facturapi_id` **y** estén `fm_sync_status = 'pending'` **o** `status =
'PENDIENTE_CANCELACION'`. Orden de prioridad:

1. Cancelación (`PENDIENTE_CANCELACION`) primero.
2. `pending` primero.
3. `fm_last_pac_sync` más antiguo (NULL primero).
4. `name`.

`BATCH_SIZE = 100` es el límite por defecto. El SQL crudo se usa porque el `ORDER BY` con
`CASE` no es expresable en `frappe.get_all`; no modifica datos.

### Locks (Redis, distribuidos, no bloqueantes, con TTL)

| Lock | Prefijo | TTL |
|---|---|---|
| Lote global | `facturacion_mexico:ffm_auto_reconciliation` | 2 horas |
| Por FFM | `facturacion_mexico:ffm_reconciliation:<ffm>` | 5 minutos |

- Adquisición atómica no bloqueante con `SET NX EX` (`_acquire_lock`); devuelve un token de
  propietario o `None` si ya está ocupado.
- Liberación segura por **compare-and-delete atómico** vía script Lua (`_release_lock`): solo
  borra la clave si su valor sigue siendo el token del dueño, evitando que un proceso cuyo
  lock expiró borre el de otro. Se libera **siempre** en `finally`.
- Namespacing por sitio (`_lock_key` → `frappe.local.site:...`) para benches multi-sitio.
- Si el FFM ya está bloqueado, `_reconcile_ffm` devuelve `outcome = "locked"` sin tocar nada.
- Para la cancelación documental de sustitución se usa el mismo lock por documento que la
  cascada/scheduler (`ffm:cascade:<ffm>`) para evitar carreras.

### Idempotencia

- Sin cambios detectados: **no** se crea Response Log; solo se sella `fm_last_pac_sync` con la
  hora de la consulta exitosa.
- Los errores de consulta (timeout / 4xx / 5xx) **conservan** `fm_last_pac_sync` previo: un
  error no cuenta como última consulta exitosa (`_log_and_set_sync`).
- La aplicación del estado de cancelación (`apply_cancellation_state`) es **idempotente y
  monotónica**: relee siempre desde BD, escribe solo campos que cambian, y una fecha de
  cancelación existente nunca se sobrescribe.

**Fuente:** `ffm_reconciliation.py` (`_select_candidates`, `_acquire_lock`, `_release_lock`,
`_lock_key`, `_reconcile_ffm`); `cancellation_state.py::apply_cancellation_state`.

---

## 5. Estados que actualiza y protección contra degradar CANCELADOS

Tras un GET exitoso, la reconciliación valida **primero** la correlación estricta
(`_resolve_validated_ffm`: el FFM explícito debe coincidir por `name`, pertenecer a la misma
Sales Invoice, y no contradecir UUID/`facturapi_id`). Una contradicción lanza
`FiscalCorrelationError`, registra alerta crítica, marca `fm_sync_status = error` y **no**
toca el estado fiscal.

Luego decide **explícitamente** si la respuesta corresponde a una cancelación
(`is_cancellation`): lo es si el FFM ya está en `PENDIENTE_CANCELACION`/`CANCELADO`, si el
estado remoto es `canceled`, o si hay `cancellation_status` en
`pending/verifying/accepted/rejected/expired`. Según eso deriva estado con
`derive_cancellation_reconciliation` (acotado, fail-closed) o `derive_pac_reconciliation`.

Estados objetivo posibles: `TIMBRADO`, `PENDIENTE_CANCELACION`, `CANCELADO`, y
`fm_sync_status` en `synced/pending/error`.

### Protecciones contra degradar un estado de cancelación

- **CORR-1 (decisión explícita):** una FFM ya `CANCELADO` **no** se degrada por una respuesta
  `valid` que carezca de estado de cancelación. El branch de cancelación se elige por
  decisión explícita, no solo por el estado derivado.
- **Monotonicidad (`apply_cancellation_state`):** *"una FFM CANCELADO no se degrada a
  PENDIENTE/TIMBRADO por una respuesta vieja"*. `CANCELADO → CANCELADO` sí ejecuta la parte
  reparadora (completa `reason`/`date`/`sync`/snapshot SI faltantes) sin degradar.
- **GAP 2 (sustitución en curso):** si A está `PENDIENTE_CANCELACION`, es origen de una
  sustitución motivo 01 con sustituto B TIMBRADO vigente, y la reconciliación derivaría
  `TIMBRADO` (el DELETE aún no se registró en el PAC), se **conserva** `PENDIENTE_CANCELACION
  + pending` para que el scheduler dedicado siga reintentando. `run_auto_reconciliation`
  **no** envía DELETE ni cancela: solo evita borrar un estado de cancelación activa con
  evidencia de sustitución.
- **Persistencia autoritativa separada:** en cancelación, el estado de negocio lo persiste
  **exclusivamente** `apply_cancellation_state` (`skip_state_persist=True` en el writer), que
  crea el Response Log pero **no** persiste el estado fiscal, evitando doble escritura.

**Fuente:** `ffm_reconciliation.py::_reconcile_ffm` (CORR-1, GAP 2);
`cancellation_state.py` (`derive_cancellation_reconciliation`, `apply_cancellation_state`);
`api/__init__.py::PACResponseWriter._resolve_validated_ffm`.

---

## 6. Sincronización del folio fiscal

`SI.fm_folio_fiscal` es una **proyección de cache de solo lectura** para reportes de Cuentas
por Cobrar; la fuente fiscal sigue siendo la FFM. Se sincroniza con el consecutivo del CFDI
**vigente** (`FFM.folio` — el consecutivo, **no** el UUID/timbre).

- **En vivo:** `apply_cancellation_state` invoca `sincronizar_folio_fiscal(si)` al proyectar
  el snapshot de la SI (limpia el folio si la FFM dejó de ser vigente, p. ej. CANCELADO).
- **Red de seguridad (weekly):** `sync_folio_fiscal_scheduled` recorre SIs con FFM ligada o
  folio ya escrito, y reconcilia/limpia el folio. Es **idempotente**, escribe con
  `update_modified=False` (no altera el timestamp de auditoría) y **no** usa FacturAPI: solo
  lee campos internos ya persistidos. Vigente = la FFM ligada tiene folio y su status está en
  `{TIMBRADO, PENDIENTE_CANCELACION}`.

**Fuente:** `facturacion_fiscal/utils.py::sincronizar_folio_fiscal`;
`facturacion_fiscal/tasks.py::sync_folio_fiscal_scheduled`;
`cancellation_state.py::apply_cancellation_state`.

---

## 7. Persistencia de respuestas RAW del PAC (fallback de timbrado)

### Persistencia de respuestas RAW del PAC (`PACResponseWriter`)

La persistencia se apoya en `PACResponseWriter` (`api/__init__.py`). Principio: **PAC
Response First** — la respuesta del PAC se registra íntegra y su estado fiscal se persiste
**primero e independientemente** del Response Log de auditoría:

- **PASO 1 — estado fiscal:** `_update_factura_fiscal` valida correlación estricta y persiste
  estado/UUID/`facturapi_id`/`fm_sync_status` en el FFM, con commit. Un fallo aquí **relanza**
  (alerta crítica) y **no** se crea Response Log ni se reporta éxito.
- **PASO 2 — Response Log:** `_write_to_database` crea el "FacturAPI Response Log" con la
  respuesta **RAW** completa (`raw_response` si existe, o el payload completo) y adjunta el
  JSON como File privado. Va **aislado con savepoint**: si su inserción falla, se revierte
  **solo** el log (rollback al savepoint); el FFM ya persistido permanece intacto y **no** se
  degrada.
- **PASO 3 — enlace de auditoría:** se enlaza `fm_last_response_log`; su fallo no revierte ni
  el FFM ni el log.

`FiscalCorrelationError` **nunca** se degrada a `{success: False}` ni al fallback de
filesystem: representa una contradicción de integridad fiscal, no una indisponibilidad de BD;
se propaga para detener el flujo.

### Comportamiento ante fallo posterior a una respuesta exitosa del PAC

- **Timbrado (PAC OK, persistencia principal del writer falló):** se hace una **lectura nueva
  de BD** con `_verify_timbrado_persisted` (¿el FFM quedó `TIMBRADO` con UUID/`facturapi_id`
  coincidentes?). Si la FASE 3 lo recuperó → `sync = synced`; si no → `sync = error` e
  intervención manual. **No** se re-llama al PAC.
- **Cancelación (PAC OK, Frappe falló después):** si el writer sí persistió, se conserva el
  manejo existente; si la persistencia principal también falló, el estado local puede quedar
  temporalmente **sin reflejar** la cancelación. El mecanismo que realinea el estado local con la
  verdad de FacturAPI en una corrida posterior es la **reconciliación** (GET, ver §1–§5). **No** se
  re-llama al PAC en el momento del fallo.

**Fuente:** `api/__init__.py::PACResponseWriter` (`write_pac_response`, `_update_factura_fiscal`,
`_write_to_database`, `_resolve_validated_ffm`); `timbrado_api.py::_verify_timbrado_persisted`.

---

## 8. Aclaraciones explícitas (con evidencia)

- **Ya NO se usa recuperación mediante `/tmp`.** El directorio de fallback se calcula por
  sitio en `sites/<site>/private/files/facturacion_mexico_pac_fallback`
  (`_get_fallback_dir`, con `chmod 0700`). La ruta `/tmp/facturacion_mexico_pac_fallback`
  solo aparece como **último recurso** dentro del `except` de `_get_fallback_dir` (si no se
  puede resolver el path del sitio) y en código de tests/validadores — **no** como mecanismo
  primario. La estrategia primaria de persistencia es **BD**; el fallback file conserva la
  evidencia RAW pero **no constituye por sí mismo una recuperación automática**.
- **`api_backup.py` ya NO existe.** Verificado: `find . -iname "*api_backup*"` no devuelve
  ningún archivo en el repositorio.
- **Reconciliación pendiente de validación operativa.** La reconciliación (GET) está presente pero
  **pendiente de una prueba operativa controlada** (roadmap interno). No debe describirse como
  "operativa" ni "validada" hasta ejecutar esa prueba.
- **La reconciliación NO retimbra ni cancela por iniciativa propia.** Su única llamada al PAC
  es un GET de solo lectura; nunca `create_invoice`/`cancel_invoice`, nunca cancela/guarda la
  Sales Invoice, nunca busca otro FFM por Sales Invoice. La única acción de convergencia fuera
  del GET es completar la cancelación **documental** (sin PAC) de un caso de sustitución
  motivo 01 ya CANCELADO fiscalmente, de forma idempotente y acotada.

**Fuente:** `api/__init__.py::_get_fallback_dir`; verificación `find`;
`working_docs/active/auditoria_manual/I_scope_roadmap.md`;
`ffm_reconciliation.py` (docstring del módulo y `_reconcile_ffm`).
