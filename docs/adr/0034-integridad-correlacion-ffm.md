# ADR-0034 — Integridad y correlación de Factura Fiscal Mexico

- **Estado:** Propuesto
- **Fecha:** 2026-06-21
- **Rango de código:** `9d7353d^..52676d7` (11 commits)
- **Supersede parcialmente:** ADR-0018 (estados FFM), ADR-0015 (relación SI↔FFM)
- **Declaración previa:** Este bloque **NO** implementa un motor de conciliación automática FFM ↔ PAC/SAT. Ese motor **no forma parte de este ADR** (ver §8).

---

## 1. Contexto e incidente original

### Incidente original (producción LlantasCS)
Una Sales Invoice (SI) terminó con **dos Factura Fiscal Mexico (FFM)** y una **cancelación se aplicó al FFM equivocado**. Causa raíz: la respuesta del PAC se asociaba al FFM resolviendo **por Sales Invoice** (`frappe.db.get_value` con `order_by` por defecto → `ORDER BY creation`, es decir el más antiguo), no por el FFM que originó la operación.

### Defectos estructurales descubiertos durante el análisis
- Creación del FFM en **JavaScript** (`frappe.client.insert` + `frappe.client.set_value`), con **ventana de carrera** entre la lectura del vínculo y la inserción.
- Podían **coexistir varios FFM activos** para una SI (sin regla de cardinalidad).
- Un fallo del **Response Log** podía revertir u ocultar el estado fiscal ya confirmado por el PAC.
- `fm_sync_status` con **semántica inconsistente**: escrito como "¿la respuesta trae `success`?", consumido como "¿hay operación en curso?".
- La refacturación 02/03/04 se **bloqueaba incorrectamente** por `fm_sync_status == "pending"`.
- En timbrado exitoso, el writer derivaba **`ERROR` transitorio** porque el UUID llega dentro de `raw_response`, no a nivel superior.

### Datos históricos existentes (no creados por este bloque)
- 11.668 FFM cargan correctamente.
- 77 con `fm_sync_status="pending"` (70 `TIMBRADO`, 6 `BORRADOR`, 1 `ERROR`); los 70 `TIMBRADO` tienen `fm_uuid` y `facturapi_id`.
- 6 grupos con 2 FFM activos por SI (patrón `TIMBRADO + BORRADOR/ERROR`).

> Separación: **(a)** incidente original = doble FFM + cancelación equivocada; **(b)** defectos estructurales = causas que lo permitieron; **(c)** datos históricos = residuos que este bloque **no** repara.

---

## 2. Alcance exacto

### Seis archivos productivos
| Archivo | Responsabilidad |
|---|---|
| `facturacion_fiscal/api/__init__.py` | Writer PAC: correlación estricta, persistencia independiente del log, derivación de estado/UUID/`facturapi_id`, `_derive_sync_status_from_response`, propagación de `FiscalCorrelationError` |
| `facturacion_fiscal/timbrado_api.py` | Orquestación timbrado/cancelación/consulta: propagación FCE, advertencia de auditoría (6B1), recuperación de persistencia (6B2), escritura de sync best-effort |
| `factura_fiscal_mexico/factura_fiscal_mexico.py` | `get_or_create_active_ffm` (creación centralizada + lock + resolución por activos), guard `before_insert` (Regla B) |
| `config/fiscal_states_config.py` | `ACTIVE_STATES` + helpers `is_active`/`is_final` |
| `api/fiscal_operations.py` | Refacturación 02/03/04: eliminación del guard `pending` |
| `public/js/sales_invoice.js` | Botón "Generar Factura Fiscal" → `get_or_create_active_ffm` (servidor); elimina `client.insert`/`set_value` |

### Los 11 commits
| # | Hash | Propósito | Depende de | Antes → Después | Riesgo |
|---|---|---|---|---|---|
| 1 | `9d7353d` | Correlación estricta por `FFM.name` | — | respuesta por SI (ambigua) → por FFM explícito | Medio |
| 2 | `13bdd97` | Estado fiscal independiente del Response Log | 1 | log falla → revertía estado → estado primero, log aislado (savepoint) | Medio |
| 3 | `caed009` | Creación centralizada `get_or_create_active_ffm` | — | JS `client.insert` → servidor | Medio-alto |
| 4 | `d0b97ea` | Lock `for_update` sobre SI | 3 | carrera concurrente → serializado | Medio |
| 5 | `0bb8caf` | Regla B (1 FFM activo) + `before_insert` | 3,4 | múltiples activos → uno; guard toda vía de inserción | **Alto** |
| 6 | `c0c5e97` | Propagación `FiscalCorrelationError` | 1 | aplanada/ignorada → detiene flujo con mensaje seguro | Medio |
| 7 | `503bf15` | TIMBRADO correcto (UUID en `raw_response`) | 2 | ERROR transitorio → TIMBRADO directo; persiste `facturapi_id` | Medio |
| 8 | `3430fae` | Advertencia no bloqueante de auditoría | 6 | `audit_log_failed` silencioso → advertencia + metadata | Bajo |
| 9 | `2a92aea` | Recuperación tras fallo del writer | 7,8 | `success=False` ignorado → verificación post-FASE 3 | Medio |
| 10 | `2ac44ac` | Semántica de `fm_sync_status` | 7,9 | `response.get("success")` → respuesta concluyente | Bajo-medio |
| 11 | `52676d7` | Refacturación sin guard `pending` | 10 | bloqueo incorrecto → solo estado/motivo | Bajo |

---

## 3. Decisiones arquitectónicas

1. **Correlación estricta por `FFM.name`.** La respuesta del PAC se asocia **solo** al FFM explícito (`factura_fiscal_name`). *Alt.:* resolver por SI / por UUID. *Seleccionado:* nombre explícito. *+:* elimina ambigüedad. *−:* el caller debe pasar el nombre. *Dep.:* 2, 6.
2. **Prohibición de selección arbitraria por SI.** Ante ≥2 activos: `FiscalCorrelationError`, no se elige. *+:* integridad. *−:* requiere intervención manual. *Dep.:* 6.
3. **Estado fiscal independiente del Response Log.** PASO 1 persiste y **commitea** el FFM (`api/__init__.py:614`); PASO 2 (log) aislado con **savepoint** (`pac_audit_log`). *Alt.:* log primero. *+:* el fallo de auditoría no revierte fiscal. *−:* doble paso. *Dep.:* 1.
4. **Creación exclusiva por servicio servidor** (`get_or_create_active_ffm`). *Alt.:* mantener JS. *+:* punto único e idempotente. *−:* —. *Dep.:* base de 4, 5.
5. **Lock `for_update` sobre la SI.** `frappe.get_doc("Sales Invoice", name, for_update=True)`. *Alt. rechazadas:* `filelock` (libera antes del commit del request), índice único (rompe Regla B). *Seleccionado:* row lock liberado por el commit/rollback normal del request, **sin commit manual**. *+:* serializa concurrencia. *−:* espera bajo contención. *Dep.:* 3, 4.
6. **Regla B — máx. 1 FFM activo por SI.** Decisión por `status` (no `docstatus`); búsqueda por `sales_invoice` + `status in ACTIVE_STATES`. *Alt.:* unicidad absoluta. *Seleccionado:* Regla B. *+:* permite reemisión tras CANCELADO; varios históricos. *−:* ≥2 activos preexistentes requieren intervención. *Dep.:* 4, 5.
7. **Estados activos/terminales.** `ACTIVE_STATES = {BORRADOR, PROCESANDO, TIMBRADO, ERROR, PENDIENTE_CANCELACION}`; terminales `FINAL_STATES = {CANCELADO, ARCHIVADO}`. *Razón:* CANCELADO/ARCHIVADO no tienen operación viva; ARCHIVADO sin transiciones salientes y ningún flujo lo asigna. *+:* fuente única. *Dep.:* 6.
8. **Propagación de `FiscalCorrelationError`.** El wrapper público re-lanza la FCE (no la aplana a `{success:False}`); los flujos la preservan y detienen con mensaje seguro ("No repita la operación…"). *+:* restaura la garantía de la decisión 1 en la orquestación. *−:* —. *Dep.:* 1.
9. **Doble persistencia writer / FASE 3 como defensa en profundidad.** El writer persiste el estado esencial (commit inmediato); la FASE 3 reafirma y completa campos. *Alt.:* consolidar en una. *Seleccionado:* conservar ambas. *Razón:* recuperación cruzada de 6B2 (writer falla → FASE 3 recupera; FASE 3 falla → writer ya commiteó). *−:* inconsistencia temporal en campos **secundarios** entre dos commits. *Dep.:* 2, 9 (6B2).
10. **Semántica final de `fm_sync_status`.** `synced` = respuesta concluyente del PAC reflejada (incluye rechazo conocido y HTTP 2xx/4xx); `pending` = inconclusa (timeout/5xx/0/sin señal); `error` = no resuelto (6B2). Fallback `fiscal_event_*` no altera el campo. *Razón:* el flag indica sincronización local, no operación viva. *Dep.:* 7, 9.
11. **Refacturación 02/03/04 independiente de `fm_sync_status`.** Se eliminó el guard `pending`; el flujo se delimita por `docstatus==1` + `status==CANCELADO` + motivo 02/03/04. *Razón:* un FFM CANCELADO es terminal, no tiene operación viva. *Dep.:* 10.

---

## 4. Invariantes que el código debe preservar

- Una SI puede tener **varios FFM históricos**.
- Solo puede existir **un FFM activo** por SI (Regla B).
- FFM `CANCELADO` o `ARCHIVADO` **no bloquea** la creación de uno nuevo.
- Ninguna respuesta PAC puede actualizar un FFM **ambiguo** (sin nombre explícito / de otra SI).
- UUID o `facturapi_id` **contradictorios** detienen la operación (`FiscalCorrelationError`).
- Un **fallo de auditoría** (Response Log) no revierte el estado fiscal.
- Una respuesta PAC exitosa **nunca** provoca repetición automática de timbrado/cancelación.
- `pending` = respuesta **inconclusa**, no operación activa.
- Documentos **históricos duplicados** deben poder abrirse.
- `before_insert` **no** bloquea actualizaciones de documentos existentes (solo inserciones).

---

## 5. Flujos afectados

Notación: **In** = documento de entrada · **Id** = identidad usada · **Lock** · **P** = persistencia · **U** = respuesta al usuario · **Fin** = estado final.

### 5.1 Generación de FFM desde SI
`In:` SI submitted sin FFM · `Id:` SI.name · `Lock:` `for_update` SI · `P:` insert FFM + `set_value` vínculo (commit request) · `U:` "Documento fiscal listo" + navegación · `Fin:` 1 FFM activo vinculado.

### 5.2 Segunda solicitud secuencial
Igual, pero bajo el lock se halla el activo existente → **se reutiliza y repara el vínculo**. `Fin:` mismo FFM, no se crea otro.

### 5.3 Solicitudes concurrentes
La 2ª espera el `for_update` de la 1ª; al desbloquearse ve el FFM vinculado → reutiliza. `Fin:` 1 solo FFM.

### 5.4 Timbrado exitoso
`In:` SI+FFM · PAC `create_invoice` OK · writer persiste `TIMBRADO`+`fm_uuid`+`facturapi_id`+`synced` (commit) · FASE 3 completa serie/folio/fecha/total · `U:` "Timbrado Exitoso" · `Fin:` TIMBRADO/synced.

### 5.5 Rechazo de timbrado
PAC rechaza → `except pac_error` → writer registra `ERROR`+`synced` (rechazo conocido) · SI→ERROR · `U:` "Timbrado rechazado". `Fin:` ERROR/synced.

### 5.6 Cancelación inmediata
PAC `cancel_invoice` OK · FASE 3 → `CANCELADO` · writer → `synced` · `Fin:` CANCELADO/synced.

### 5.7 Cancelación pendiente
FASE 3 → `PENDIENTE_CANCELACION` (estado fiscal) · `fm_sync_status=synced` (la respuesta ya se reflejó). `Fin:` PENDIENTE_CANCELACION/synced.

### 5.8 Consulta de cancelación (`revisar_estatus_cancelacion`)
`query_pac_status` → escribe estado sobre **el mismo FFM** → writer log. `Fin:` estado verificado/synced.

### 5.9 Fallo del writer con recuperación (6B2)
writer `success=False` (PAC OK) → FASE 3 ejecuta una vez → **verificación con lectura nueva de BD** → si OK: `success=True` + `persistence_status=recovered_by_phase3` + `retry_allowed=False`; si no: `unresolved`/`error`. **Nunca** re-PAC.

### 5.10 Fallo del Response Log
PASO 1 ok (estado fiscal persistido) · PASO 2 falla → rollback al savepoint · `audit_log_failed=True` + advertencia. `Fin:` estado fiscal **conservado**, sin Response Log.

### 5.11 Refacturación 02/03/04
`In:` SI + FFM `CANCELADO` motivo 02/03/04 · `refacturar_misma_si` **desvincula** la SI (no toca el FFM) · luego "Generar" → `get_or_create` crea nuevo FFM (CANCELADO no bloquea). `Fin:` SI→nuevo FFM activo; cancelado intacto; 1 activo.

---

## 6. Transacciones y commits

- **`frappe.db.commit()` del writer:** `api/__init__.py` (`_update_factura_fiscal`, PASO 1). Persiste el estado fiscal esencial **de inmediato** → **no revertible** por excepción posterior.
- **Savepoint:** `pac_audit_log` (PASO 2). Su rollback afecta **solo** el Response Log, no el FFM ya commiteado.
- **FASE 3:** commit propio (timbrado/cancelación). Es un **segundo commit**, separado del writer.
- **`get_or_create_active_ffm`:** **sin** commit manual; el lock `for_update` se libera con el commit/rollback **normal del request**.
- **`fiscal_operations.py` / `timbrado_api.py` (consulta):** `frappe.db.commit()` preexistentes (no añadidos como atajo).
- **Qué persiste el writer:** `status`, `fm_uuid`, `facturapi_id` (TIMBRADO), `fm_sync_status`, `fm_last_pac_sync`.
- **Qué persiste FASE 3:** reafirma `status`/`fm_uuid`/`facturapi_id` + `serie`, `folio`, `fecha_timbrado`, `total_fiscal`, URLs, campos de la SI.
- **Si falla cada etapa:** PASO 1 falla → relanza, no se crea log, 6B2 evalúa; PASO 2 falla → 6B1 advierte, estado conservado; FASE 3 falla con writer ok → estado del writer sobrevive.
- **Por qué se conserva la doble escritura:** recuperación cruzada de 6B2 (§3.9).
- **Riesgo de inconsistencia temporal:** entre el commit del writer y el de FASE 3, el FFM está commiteado con estado fiscal correcto pero **sin** campos secundarios (serie/folio/fecha). Antes de 6B0 esta ventana mostraba `ERROR`; 6B0 la redujo a campos secundarios. **No se minimiza esta complejidad: existe y es intencional.**

---

## 7. Compatibilidad con datos existentes (hallazgos reales, lectura)

- **11.668 FFM históricos** cargan correctamente con el código nuevo.
- **77** con `fm_sync_status="pending"` (70 `TIMBRADO`, 6 `BORRADOR`, 1 `ERROR`).
- Los **70 `TIMBRADO+pending`** tienen `fm_uuid` y `facturapi_id` (ya sincronizados con el PAC; el flag es residuo del bug).
- **6 grupos** con 2 FFM activos por SI (`TIMBRADO + BORRADOR/ERROR`).
- **Estos datos NO se reparan en este bloque.**
- `get_or_create_active_ffm` ante un grupo con ≥2 activos **se detiene** (`FiscalCorrelationError`), no elige.
- Los documentos existentes (incluidos los duplicados) **sí pueden abrirse y evaluarse** (helpers de solo lectura).

---

## 8. Qué NO resuelve este bloque (declaración expresa)

- **No** existe motor automático de conciliación FFM ↔ PAC/SAT (las funciones `process_pending_complements` y `reconcile_payment_tracking` son **placeholders vacíos**, preexistentes).
- **No** consulta automáticamente los 70 FFM contra el PAC.
- **No** repara los 77 `pending`.
- **No** corrige los 6 grupos duplicados.
- **No** repara el caso incidente.
- **No** resuelve referencias rotas (`refacturar_misma_si` hace `get_doc` sin verificar existencia).
- **No** corrige el `TypeError` defensivo de `_derive_status_from_response` (raw_response `dict` sin `status_code`).
- **No** modifica datos históricos.
- **No** agrega scheduler de conciliación.

---

## 9. Pruebas y evidencia

| Tipo | Detalle |
|---|---|
| Unitarias / integración | **110** pruebas en 11 suites del bloque (todas verdes) |
| Concurrencia | procesos independientes (`multiprocessing` spawn), `for_update` serializa |
| Funcionales reales (site test) | `get_or_create_active_ffm` y `refacturar_misma_si` reales; flujo integrado 02/04 |
| Lectura histórica | 11.668 FFM evaluados en `llantascs-v16.dev` (solo lectura, baseline inicial=final) |
| Aislamiento PAC | cliente real **no instanciable** en `test-facturacion.localhost` (sin Company Settings); boundaries mockeados |
| Suites relacionadas | `ffm_cancel_permissions` (6), `ffm_js_multisucursal_cleanup` (6), `layer1` (5) verdes |

**Limitaciones / deuda documentadas:**
- **Smoke GUI real (navegador) NO ejecutado** por el agente CLI (sin navegador). Pendiente para operador humano.
- Fallos **preexistentes de entorno**: `test_custom_fields_naming_consistency` (custom fields UAE/VAT de ERPNext), `test_refacturar_workflow`/`test_tipo_e_nota_credito` (`_Test Item is not a stock Item`, setup de stock). Ajenos al bloque.
- **Response Logs residuales** en site de test por `tearDown` incompleto de algunas suites (deuda de entorno, no productiva).

---

## 10. Matriz de riesgos

| Riesgo | Prob. | Impacto | Parte del código | Prueba que mitiga | Monitoreo | Rollback |
|---|---|---|---|---|---|---|
| Bloqueo legítimo por cardinalidad | Media | Alto | `before_insert` (commit 5) | `test_unico_ffm_activo` (16) | alertas "FFM activo ya existe" | revert commit 5 |
| Deadlock/espera por `for_update` | Baja | Medio | `get_or_create` (commit 4) | `test_get_or_create_concurrencia` (4) | tiempos de lock | revert commit 4 |
| Inconsistencia writer/FASE 3 | Baja | Bajo | api/timbrado (2,9) | suites 6B2 | FFM TIMBRADO sin serie/folio | — (defensa en profundidad) |
| Consumidor con semántica vieja de `fm_sync_status` | Baja | Medio | sync (10) | `test_sync_status_semantics` (15) | uso de `pending` en reportes | revert commit 10 |
| Documentos duplicados existentes | Baja | Alto | Regla B / `before_insert` | `test_15` (modificación no bloqueada) + lectura prod | apertura de FFM viejos | — |
| Errores JS / permisos no verificados en GUI | Media | Medio | `sales_invoice.js` | análisis estático + `ffm_cancel_permissions` | **smoke GUI humano** | revert commit 3 (JS) |
| Ausencia de conciliación automática | Alta | Medio (negocio) | — (no existe) | — | `pending` que no se cierran solos | feature nueva (fuera de alcance) |

---

## 11. Despliegue (documentado, no ejecutado)

- **No hay** cambios de esquema, patches nuevos ni fixtures nuevos en el bloque.
- La rama **no requiere `migrate` por sí misma**.
- ⚠️ `bench migrate` ejecutaría los hooks `after_migrate` (5 funciones que **escriben** Item Groups/Items/UOM/estados) y sincronizaría `fixtures` (Custom Fields + catálogos SAT) → puede **modificar datos**. Evaluar por separado.
- Pasos a evaluar (sin comandos destructivos aquí): pull/checkout del código → `bench build` de assets → reinicio controlado (vía `frappe-multisite`) → smoke test → monitoreo.

---

## 12. Rollback

- **Reversión por commits:** `git revert` del rango / del PR squash. Código puro, sin migraciones → reversión limpia.
- **Efecto sobre documentos creados mientras el bloque estuvo activo:** los FFM creados por `get_or_create` bajo Regla B **permanecen**; revertir el código no los borra.
- **Si ya existen nuevos FFM bajo Regla B:** seguirán siendo válidos; sin el guard `before_insert`, futuras inserciones dejan de validarse (vuelve el riesgo de duplicado).
- **Datos no revertidos automáticamente:** estados fiscales, `fm_sync_status` y vínculos ya persistidos.
- **Backup previo obligatorio** antes de desplegar (para poder restaurar datos si fuese necesario).
- **Criterios objetivos de rollback:** aparición de nuevos FFM duplicados atribuibles al bloque; `FiscalCorrelationError` masivos en flujos legítimos; bloqueo de creación/refacturación legítima; errores de timbrado introducidos por el cambio.

---

## 13. Observabilidad posterior al despliegue

Revisar: nuevos FFM duplicados por SI · frecuencia de `FiscalCorrelationError` · distribución de `fm_sync_status` · errores de Response Log (`audit_log_failed`) · FFM en `ERROR` · resultados con `retry_allowed=False` / mensajes "No repita la operación" · tiempos de espera por lock · cancelaciones en `PENDIENTE_CANCELACION` · errores JS del botón "Generar Factura Fiscal".

---

## 14. Decisión

**Se adopta el bloque de 11 commits** que: (a) corrige la correlación y la creación del FFM, (b) establece la cardinalidad Regla B, (c) hace la persistencia fiscal resiliente al Response Log, (d) corrige la semántica de `fm_sync_status` y la refacturación 02/03/04.

**Necesidad:** previene la repetición del incidente (doble FFM / cancelación equivocada), defecto con impacto fiscal y de negocio.

**Condición de despliegue:** sin `migrate` obligatorio por el bloque; con `build` + reinicio controlado + backup previo + smoke GUI humano + monitoreo de §13.

**Trabajo pendiente (fuera de este ADR):** motor de conciliación FFM ↔ SAT; reparación de los 77 `pending`, los 6 grupos duplicados y el caso incidente; referencias rotas; `TypeError` defensivo. **Este ADR no declara el sistema completo ni la recuperación de los 70 como resueltos.**

---

## Anexo A — Trazabilidad commit → decisión → prueba

| Commit | Decisión(es) | Suite(s) de prueba |
|---|---|---|
| `9d7353d` | D1, D2 | `test_pac_response_correlacion` (9) |
| `13bdd97` | D3 | `test_estado_fiscal_independiente_log` (7) |
| `caed009` | D4 | `test_get_or_create_active_ffm` (15) |
| `d0b97ea` | D5 | `test_get_or_create_concurrencia` (4) |
| `0bb8caf` | D6, D7 | `test_unico_ffm_activo` (16) |
| `c0c5e97` | D8 | `test_correlacion_propagacion` (8) |
| `503bf15` | (UUID/`facturapi_id`) | `test_writer_timbrado_uuid` (8) |
| `3430fae` | (6B1 auditoría) | `test_audit_warning` (9) |
| `2a92aea` | D9 (6B2) | `test_persistence_recovery` (11) |
| `2ac44ac` | D10 | `test_sync_status_semantics` (15) |
| `52676d7` | D11 | `test_refacturar_guard` (8) |

## Anexo B — Afirmaciones verificadas contra código
- Correlación estricta por `factura_fiscal_name` y rechazo de selección por SI — verificado en `_resolve_validated_ffm` / `get_or_create_active_ffm`.
- `frappe.db.commit()` del writer y savepoint `pac_audit_log` — verificado en `api/__init__.py`.
- `for_update=True` genera `SELECT ... FOR UPDATE` — verificado empíricamente.
- `before_insert` solo bloquea inserciones (no updates) — verificado (`test_15`).
- JS del botón llama solo `get_or_create_active_ffm`, sin `client.insert`/`set_value`, sin segunda creación — verificado en `sales_invoice.js`.
- Guard `pending` eliminado de `refacturar_misma_si`; guards `docstatus`/`status`/`motivo` intactos — verificado en `fiscal_operations.py`.
- `ACTIVE_STATES`/`FINAL_STATES` y `ARCHIVADO` sin transiciones salientes — verificado en `fiscal_states_config.py` y `valid_transitions`.
- 70 `TIMBRADO+pending` con `fm_uuid` y `facturapi_id`; 6 grupos duplicados — verificado por lectura en `llantascs-v16.dev`.
- `process_pending_complements`/`reconcile_payment_tracking` son placeholders — verificado.

## Anexo C — Puntos NO verificados (limitaciones)
- Comportamiento **visual en navegador**: render del botón, red/DevTools, consola JS, visibilidad por rol en UI — **no verificado** (sin navegador).
- Comportamiento del bloque bajo **carga real concurrente de producción** (solo probado con procesos de test).
- Efecto de `bench migrate` real en un site con datos de producción (solo analizado, no ejecutado).
