# ADR-0037 — Resiliencia de la cancelación de sustitución (motivo 01) ante fallos transitorios del PAC

- **Estado:** Propuesto
- **Fecha:** 2026-07-17
- **Rama:** `fix/cascade-cancel-01-transient-404-and-doc-reconcile`
- **Relacionado:** [[0013-arquitectura-sistema-cancelaciones-cfdi]] · [[0035-motor-reconciliacion-ffm]] (motor de reconciliación) · [[0036-integridad-proyeccion-cancelacion]] (clasificación fail-closed de cancelación)
- **Extiende/corrige:** ADR-0035 y ADR-0036. No los reemplaza.

---

## 1. Contexto y defecto real observado

En el flujo de sustitución motivo 01, tras timbrar el CFDI sustituto (B), una cascada cancela
automáticamente el CFDI original (A) con `TipoRelación = 04` y `FolioSustitución = UUID_B`.

En una prueba de integración real contra FacturAPI TEST (par A=`FFMX-2026-00045` / B=`FFMX-2026-00046`)
se reprodujo **de forma natural** el defecto: el `DELETE` de A inmediatamente después de timbrar B
devolvió **HTTP 404 `invoice_not_found`** (consistencia eventual del PAC: A existe y está timbrado,
pero el PAC no lo resuelve por unos instantes). Evidencia en `FacturAPI Response Log` de A:

- `00:52:02` Timbrado de B → 200
- `00:52:08` Solicitud Cancelación de A → **404 `invoice_not_found`** (transitorio)
- `01:21:21` Solicitud Cancelación de A → **200** (cuando el PAC ya lo resolvía)

El diseño previo trataba ese 404 como fallo terminal y, peor, presentaba el timbrado **exitoso** de B
como si hubiera fallado. Además, la prueba real destapó **tres defectos** que los tests con mock no
podían ver:

1. **Timbrado de B presentado como error** por un fallo que era solo de la cancelación de A.
2. **La recuperación diferida no cancelaba nunca:** el guard de `cancelar_factura` exige
   `fm_fiscal_status == TIMBRADO`; al reintentar A ya estaba en `PENDIENTE_CANCELACION`, el guard la
   rechazaba y **devolvía `{success: False}` sin lanzar excepción**, que el scheduler ignoraba.
3. **La reconciliación pasiva destruía la cancelación en curso:** `run_auto_reconciliation` veía A
   `valid/none` (el DELETE no se había registrado) y `derive_cancellation_reconciliation` la revertía
   `PENDIENTE_CANCELACION → TIMBRADO`, sacándola de la cola del scheduler → cancelación perdida y
   **A y B ambos vigentes** (doble CFDI).

## 2. Decisión

### 2.1 Reintentos inmediatos acotados en la cascada

Al timbrar B, la cancelación de A se intenta con reintentos **inmediatos y cortos** solo ante errores
**transitorios** (`404 invoice_not_found`, `429`, `5xx`, timeouts, errores de conexión):

```text
intento 1 (t0) → espera 0.5 s → intento 2 → espera 1.0 s → intento 3 (≈ +1.5 s acumulado)
(3 intentos, ventana total ≈ 1.5 s, dentro del request)
```

Si el error no es transitorio, no se reintenta.

### 2.2 Transición a `PENDIENTE_CANCELACION` sin falsear el timbrado

Si los reintentos inmediatos se agotan, la cascada **no lanza error** (el timbrado de B fue real y
exitoso). A queda en `PENDIENTE_CANCELACION` + `fm_sync_status = pending` + `fm_sync_error` explicativo.
B permanece `TIMBRADO`; SI/FFM de A intactos (docstatus sin tocar).

### 2.3 Recuperación programada (scheduler dedicado)

Una tarea `cron` **cada 1 minuto** (`retry_pending_substitution_cancellations`) redescubre los casos
pendientes desde el estado en BD (no usa contadores ni jobs efímeros; sobrevive reinicios). Por cada A:

- **GET-first**: consulta el estado remoto real de A.
  - Si el PAC ya la reporta `canceled` → no reenvía DELETE; reconcilia + completa documental.
  - Si sigue `valid` → envía **un** DELETE motivo 01 + `UUID_B` (vía `cancelar_factura` con el flag
    interno `_allow_pending_cancellation`, ver §2.5).
- Solo actúa si A es **origen de sustitución real**: existe una SI con
  `ffm_substitution_source_uuid == A.fm_uuid` y su FFM está `TIMBRADO`. Cualquier cancelación ajena
  (motivos 02/03/04, o pendientes sin sustituto) se ignora sin efectos.

### 2.4 Throttle escalonado y corte temporal (anti-bloqueo del PAC)

Anclados en `fecha_timbrado` de B (momento real en que A pasó a pendiente) y en `fm_last_pac_sync`:

- **Ventana rápida** (primeros 5 min): 1 intento por tick de 1 minuto.
- **Después**: 1 intento cada ~5 min (throttle vía `fm_last_pac_sync`).
- **Corte total ~2 h**: pasada la ventana se abandona el ciclo automático → `fm_sync_status = error` +
  `fm_sync_error` accionable (intervención manual). Evita ~120 DELETE para un caso prolongado.

Cronología: `t0 → +0.5 s → +1 s → +1 → +2 → +3 → +4 → +5 min → luego ~cada 5 min → corte 2 h`.

### 2.5 Guard acotado sin abrir el flujo manual

La cancelación manual sigue exigiendo `TIMBRADO`. **Solo** el reintento automático pasa el flag
keyword-only `_allow_pending_cancellation=True`, que permite reintentar una FFM en
`PENDIENTE_CANCELACION`. El scheduler además maneja **ambas** formas de fallo: excepción **y** retorno
`{success: False}` — clasificando transitorio (conservar pendiente) vs definitivo (salir del ciclo);
nunca interpreta un fallo como éxito.

### 2.6 Protección de la reconciliación (no revertir una sustitución en curso)

En `run_auto_reconciliation` (que **sigue siendo estrictamente de solo lectura** ante el PAC: no envía
DELETE, no cancela, no cambia su contrato), cuando A está `PENDIENTE_CANCELACION`, es origen de
sustitución con B `TIMBRADO` vigente, y el PAC responde `valid/none`, **se conserva
`PENDIENTE_CANCELACION`** en vez de aplicar la transición genérica `valid/none → TIMBRADO`. Así el
scheduler dedicado puede seguir reintentando. La excepción está acotada exclusivamente a sustituciones
motivo 01 verificables (`_es_origen_sustitucion_vigente`), no se generaliza a cualquier pendiente.

### 2.7 Convergencia documental

La cancelación fiscal (`status = CANCELADO`) y la documental (`docstatus = 2` de SI y FFM) están
separadas. `_complete_documental_cancellation` es la **única** implementación (reutilizada por cascada,
scheduler y reconciliación), idempotente: si ambos ya están en `docstatus = 2` no hace nada. Si A queda
`CANCELADO` con `docstatus = 1` (p. ej. proceso interrumpido), la reconciliación completa el documental
sin reenviar DELETE.

### 2.8 UX

El timbrado de B se reporta **siempre como éxito**. Cuando A queda pendiente, la respuesta al frontend
incluye `cancelacion_previa_pendiente = true` y el formulario muestra un mensaje **amarillo** (no un
error): *"Factura sustituta timbrada correctamente. La cancelación del CFDI anterior quedó pendiente y
el sistema continuará reintentándola automáticamente."* La fuente de verdad es el estado del documento
(A en `PENDIENTE_CANCELACION`).

## 3. Alternativas descartadas

- **Reintento ciego con `sleep` fijo (1.5 s / 3 s):** arbitrario y bloquea el request; rechazado.
- **Diseño durable sobredimensionado:** máquina de estados multinivel con campos nuevos
  (`cancellation_retry_count`, `last_retry_at`, `next_retry_at`), múltiples schedulers (30 s / 60 s /
  5 min) y persistencia de acuses. **Desproporcionado** para un 404 intermitente y raro. Se descartó a
  favor del diseño mínimo actual: sin campos nuevos, sin contadores, un solo scheduler, durabilidad vía
  el estado ya persistido (`PENDIENTE_CANCELACION` / `fm_sync_status = pending`).
- **Validar el XML timbrado antes de cancelar A:** requeriría una descarga extra justo en la ventana de
  consistencia eventual (reintroduce el 404) y añade latencia/timeout de UX. Se prefiere validar contra
  la respuesta de `create_invoice` (coste ~0) y dejar la validación del XML como verificación posterior.

## 4. Consecuencias

- El timbrado de B nunca se presenta como error por un fallo de cancelación de A.
- La cancelación de A es **fail-closed**: nunca se marca `CANCELADO` en falso; converge cuando el PAC lo
  permite, o sale a intervención tras ~2 h.
- La reconciliación pasiva ya no destruye una cancelación de sustitución en curso.
- Sin cambios de esquema (no requiere `bench migrate`). Requiere que el scheduler esté activo para la
  recuperación diferida.

## 5. Fuera de alcance (incidentes separados)

- Duplicación de nodos `cfdi:Traslado` (IVA 0%) observada en A y B — problema general de generación de
  impuestos, ajeno a este fix.
- Sistema de alertas en tiempo real de facturación.
- "Error visual al timbrar hasta refrescar" reportado en producción.
