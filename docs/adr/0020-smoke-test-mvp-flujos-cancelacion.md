# ADR-0020: Smoke Test MVP v0.1 — Flujos de Cancelación y Refacturación

**Fecha:** 2026-05-09  
**Estado:** ✅ Parcialmente validado — flujos de cancelación completos, Bloque E pendiente  
**Contexto:** Primera validación funcional real de los flujos de cancelación y refacturación post-RC-NO-VIABLE

---

## Contexto

El RC anterior fue declarado NO VIABLE por falta de instructivo de flujos fiscales. Este ADR documenta la primera ejecución real del smoke test MVP y los hallazgos encontrados.

**Site de prueba:** `test-fm-v010.localhost`  
**Branch:** `fix/mvp-cancelacion-flujos-fiscales`

---

## Flujos validados

### Bloque A — Timbrado

| ID | Prueba | Doc | Resultado |
|---|---|---|---|
| A1 | Timbrar FFM PUE (forma pago 03) | FFMX-2026-00005 | ✅ PASS |
| A2 | Timbrar FFM PPD | FFMX-2026-00004 | ✅ PASS |
| A3 | Crear Payment Entry | ACC-PAY-2026-00003 | ✅ PASS |
| A3b | Generar Complemento | COMP-PAG-2026-00002 | ✅ PASS |
| A4 | Timbrar Complemento | COMP-PAG-2026-00002 | ✅ PASS |
| Guard | FFM bloqueada con PE activo | FFMX-2026-00004 | ✅ PASS — guard JS + Python |

### Bloque B — Complemento motivo 02 + Sustitución FFM motivo 01

**Nota:** B1/B2 probaron motivo 02 en complemento, no motivo 01. Motivo 01 en complemento **no está implementado** en el app (el diálogo de cancelación de complemento solo ofrece 02/03/04).

| ID | Prueba | Doc | Resultado |
|---|---|---|---|
| B1 | Cancelar Complemento **motivo 02** | COMP-PAG-2026-00002 | ✅ PASS |
| B2 | Generar y timbrar nuevo Complemento | COMP-PAG-2026-00003 | ✅ PASS |
| B3/B4 | Sustituir CFDI (01): nueva SI + FFM sustituta con TipoRelación 04 | FFMX-2026-00006 | ✅ PASS |

### Bloques C y E — No validados

| Bloque | Descripción | Estado |
|---|---|---|
| C | Complemento motivos 03/04: cancelar y regenerar | ❌ No validado |
| E | FFM con pagos activos motivos 02/03/04 | ❌ No validado |

Estos bloques deben completarse antes de declarar el MVP como validado.

### Bloque D — FFM sin pagos motivos 02/03/04

| ID | Prueba | Doc | Resultado |
|---|---|---|---|
| D1 | Cancelar FFM PUE motivo 02 | FFMX-2026-00007 | ✅ PASS |
| D2 | Retimbrar misma factura (Nueva factura fiscal) | FFMX-2026-00008 | ✅ PASS |
| D2b | Cancelar SI post-fiscal (❌ Cancelar documento) | ACC-SINV-2026-00008 | ✅ PASS |

---

## Workflow correcto por escenario (para usuarios)

### Timbrado inicial

```
1. Crear Sales Invoice → Submit
2. En SI: botón "Timbrar Factura" → crea FFM en borrador
3. En FFM: Submit → botón "Timbrar con FacturAPI"
4. FFM queda TIMBRADO con UUID SAT
```

### Cancelación de Complemento de Pago

```
Condición: tener FFM PPD timbrada + Payment Entry + Complemento timbrado

1. En Complemento: botón "Cancelar" → seleccionar motivo (02/03)
2. Complemento queda Cancelado
3. Cancelar Payment Entry → Amend → nuevo PE
4. Desde nuevo PE: "Generar Complemento" → timbrar nuevo Complemento

Nota: motivo 01 en complemento no está implementado.
Nota: al hacer cancel/amend del PE se pierde la relación histórica PE→Complemento anterior.
```

### Cancelación FFM — Motivo 01 (sustitución con CFDI relacionado)

```
Condición: FFM TIMBRADO, SI sin pagos activos

1. En SI (con FFM TIMBRADO): "Acciones Fiscales → 🔄 Sustituir CFDI (01)"
2. Se crea SI nueva de reemplazo en borrador — modificar datos si es necesario
3. Submit SI nueva → Timbrar FFM nueva
4. Al timbrar la nueva FFM: la FFM original se cancela automáticamente ante el SAT
   con TipoRelación 04 referenciando el UUID original ✅
5. Verificar en log: related_documents[{relationship: "04", documents: [UUID_original]}]

Regla SAT respetada: FFM original permanece TIMBRADA hasta que la sustituta esté timbrada.
```

### Cancelación FFM — Motivos 02/03/04 (sin CFDI relacionado)

```
Condición: FFM TIMBRADO

[Si hay Complemento activo]
→ Primero cancelar Complemento → luego cancelar FFM

1. En FFM: "Cancelar en FacturAPI" → seleccionar motivo → Confirmar
2. FFM queda CANCELADO
3. En SI aparece grupo "Opciones Fiscales":

   Opción A — Retimbrar misma factura (error fue en FFM, no en SI):
   → "🔄 Nueva factura fiscal" → desvincuala SI de FFM cancelada
   → "Generar Factura Fiscal" → nueva FFM → timbrar
   → ⚠️ La SI no se puede modificar en este flujo

   Opción B — Cambiar datos de la factura o motivo 03 (operación no realizada):
   → "❌ Cancelar documento" → desvincula FFMs y cancela SI en un paso
   → Si necesita nueva factura: Amend → nueva SI → nueva FFM → timbrar
   → Si no necesita nueva factura (motivo 03): fin

   Opción C — Motivo 04 (operación en factura global):
   → "❌ Cancelar documento" → cancela SI
   → ⚠️ DEUDA TÉCNICA: flujo de Factura Global no implementado
```

---

## Hallazgos y fixes aplicados durante el smoke test

### F1 — Guard Python cancelación FFM con complemento activo
**Problema:** bloqueo solo existía en JS, no en Python. Llamada directa a API podía evadir el guard.  
**Fix:** `cancelar_factura()` en `timbrado_api.py` verifica complemento activo antes de contactar PAC.

### F2 — Default motivo en diálogo cancelación FFM
**Problema:** `default: "02"` no coincidía con el formato real de opciones `"02\tDescripción"`.  
**Fix:** `filtered_options.find((o) => o.startsWith("02"))` para encontrar el valor correcto.

### F3 — Outlier: fm_require_complement = 0 en PE PPD
**Problema:** PE creado desde SI PPD tenía `fm_require_complement=0` en BD aunque el aviso UI mostraba que se requería complemento y el botón "Crear Complemento" aparecía.  
**Causa:** El hook `check_ppd_requirement()` no actualizó el campo correctamente.  
**Estado:** Detectado, no corregido. Tres fuentes de verdad fragmentadas (BD, mensaje UI, botón UI). Issue pendiente de refactor.

### F4 — Flujo Opciones Fiscales post-cancelación
**Implementado:**
- Grupo "Opciones Fiscales" con "🔄 Nueva factura fiscal" y "❌ Cancelar documento"
- Guard: se ocultan si hay PE activo vinculado a la SI
- Cancel nativo oculto cuando hay FFM vinculada (cualquier estado)
- `cancelar_si_post_fiscal()`: desvincula todas las FFMs que referencian la SI antes de cancelar

### F5 — Freeze en timbrado de Complemento
**Problema:** no había freeze durante timbrado — riesgo de doble-click y duplicación.  
**Fix:** `freeze: true, freeze_message: "Enviando a FacturAPI..."` en `complemento_pago_mx.js`.

### F6 — Pérdida de relación PE → Complemento post cancel/amend
**Problema:** al cancelar y amend del PE, el nuevo PE no tiene referencia al Complemento cancelado.  
**Estado:** Detectado, documentado como deuda técnica. No impacta funcionalidad actual.

---

## Deuda técnica identificada

| Item | Descripción | Impacto | Bloquea MVP |
|---|---|---|---|
| DT-01 | **Motivo 04 incompleto:** cancelación funciona pero no hay flujo para agregar operación a Factura Global. Hoy solo se cancela/cierra. | Alto | No bloquea cancelación; sí bloquea flujo global |
| DT-02 | **`fm_require_complement` inconsistente:** campo existe en fixture y se escribe al crear/cancelar complemento, pero no al crear el PE (hook es no-op). UI y botón leen `fm_es_ppd` de SI directamente. Tres fuentes de verdad: BD, mensaje UI, botón. **No usar como fuente de verdad en automatizaciones hasta resolver.** | Alto | No bloquea flujo manual; sí bloquea automatización |
| DT-03 | **Pérdida relación PE → Complemento:** al cancelar y amend PE, el nuevo PE no referencia el complemento anterior. Aceptado en MVP como limitación conocida. | Bajo | No bloquea |
| DT-04 | **Bloque E no validado:** FFM con pagos activos motivos 02/03/04 | Pendiente | Sí — requerido para cierre |
| DT-05 | **Bloque C no validado:** Complemento motivos 03/04 | Pendiente | Sí — requerido para cierre |
| DT-06 | **Motivo 01 en Complemento no implementado:** diálogo solo ofrece 02/03/04. Motivo 01 requeriría complemento sustituto con TipoRelación 04, flujo no diseñado. | Medio | No bloquea MVP actual |

---

## Lecciones aprendidas

1. **`refacturar_misma_si()` es para errores en FFM, no en SI.** Si el error está en los datos de la SI, hay que cancelarla y crear una nueva. El nombre de la función confundía — ahora el mensaje en UI lo aclara.

2. **El cancel de SI con FFM histórica requiere limpiar ambos lados del vínculo.** `fm_factura_fiscal_mx` en SI + `sales_invoice` en FFM. El bloqueo de ERPNext viene del lado FFM.

3. **Complemento tiene flujo más limpio que FFM.** Va directo a Cancelado sin estado intermedio PENDIENTE_CANCELACION en sandbox. Facilita refacturación.

4. **Motivo 01 es el más complejo.** Involucra crear SI nueva, FFM nueva, y la cancelación de la original es automática al timbrar la sustituta. La relación TipoRelación 04 se envía correctamente a FacturAPI.

5. **Cancel nativo de SI debe siempre ir por Opciones Fiscales cuando hay FFM.** El botón nativo no hace limpieza fiscal — dejaba referencias huérfanas.

---

## Criterio de cierre del MVP

El MVP se considera **validado y listo** cuando se completen:

- [ ] Bloque C: Complemento motivos 03 y 04 — cancelar y regenerar
- [ ] Bloque E: FFM con pagos activos motivos 02/03/04 — bloqueo, cancelar complemento, cancelar FFM, refacturar
- [ ] `fm_require_complement` revisado y consistente (o documentado como no-usar)

Los bloques A, B (parcial) y D están validados. Los fixes de esta sesión son estables.
