# Cancelar un CFDI

Guía para cancelar comprobantes fiscales timbrados según la normativa SAT.

---

## Motivos de cancelación

El SAT requiere seleccionar uno de estos motivos al cancelar:

| Código | Motivo | Cuándo usar |
|---|---|---|
| **01** | Comprobante emitido con errores **con** relación | Error en la factura; ya existe o vas a emitir un CFDI sustituto |
| **02** | Comprobante emitido con errores **sin** relación | Error sin sustituto; el cliente no requiere corrección |
| **03** | No se llevó a cabo la operación | La venta o servicio no se realizó |
| **04** | Operación nominativa relacionada en factura global | El ticket ya fue incluido en una Factura Global |

> Los motivos **02, 03 y 04** siguen el mismo camino: cancelación directa sin UUID sustituto.
> El motivo **01** requiere un UUID sustituto y sigue un camino diferente.

---

## Prerrequisito: cancelar el Complemento de Pago primero

Si la factura tiene un **Complemento de Pago** activo, **no se puede cancelar** hasta cancelar primero el complemento.

El sistema bloquea la cancelación y muestra: *"Cancela primero el complemento y luego regresa a cancelar la factura."*

---

## Camino A — Motivos 02, 03 y 04 (cancelación directa)

Este camino cancela el CFDI sin emitir uno nuevo.

### Pasos

1. Abrir el **Sales Invoice** timbrado (`fm_fiscal_status = TIMBRADO`)
2. Desde el Sales Invoice → abrir la **Factura Fiscal Mexico** (botón **"Ver Factura Fiscal"**)
3. En el FFM → sección **Cancelación** → seleccionar el **motivo** (02, 03 o 04)
4. Confirmar

El sistema envía la solicitud de cancelación a FacturAPI.io.

### Qué pasa después

| Respuesta del SAT | Estado resultante | Qué significa |
|---|---|---|
| `canceled` / `accepted` | `CANCELADO` | Cancelación aceptada de inmediato |
| `pending` | `PENDIENTE_CANCELACION` | El receptor tiene 72 horas para aceptar o rechazar |
| `rejected` | `TIMBRADO` (sin cambio) | El receptor rechazó la cancelación |

Si queda en `PENDIENTE_CANCELACION`: esperar. El SAT acepta automáticamente después de 72 horas si el receptor no responde. Puedes verificar el estado con el botón **"Revisar estatus cancelación"** en el FFM.

---

## Camino B — Motivo 01 (cancelación con sustitución)

Este camino se usa cuando hay un error en la factura y necesitas emitir una versión corregida. El CFDI original se cancela y queda relacionado con el nuevo.

**Flujo obligatorio: primero timbras el sustituto, luego cancelas el original.**

### Pasos

1. **Crear el Sales Invoice sustituto** — nuevo SI con los datos correctos
2. **Timbrar el SI sustituto** — obtener su UUID (ver [Emitir un CFDI](emitir-cfdi.md))
3. Volver al **Sales Invoice original** (`fm_fiscal_status = TIMBRADO`)
4. Buscar el botón **"Sustituir CFDI (01)"** en el Sales Invoice
5. Ingresar el **UUID del CFDI sustituto** (el que timbraste en el paso 2)
6. Confirmar

El sistema envía la cancelación con `TipoRelación = 04` (sustitución).

> **Importante:** Si intentas usar motivo 01 desde el FFM directamente (no desde el SI), el sistema te redirigirá al Sales Invoice. El flujo de sustitución está controlado desde el SI.

### Qué pasa después

La cancelación motivo 01 generalmente es inmediata (`CANCELADO`). El SAT vincula ambos CFDIs mediante la relación.

---

## Estado después de cancelar

El campo `fm_fiscal_status` en el Sales Invoice cambia a `CANCELADO` (o `PENDIENTE_CANCELACION` mientras espera al receptor).

El Sales Invoice permanece en ERPNext — la cancelación fiscal no implica cancelar el documento ERPNext.

---

## Acuse de cancelación

Al completar la cancelación, el sistema descarga automáticamente el **acuse de cancelación** (PDF y XML) desde FacturAPI.io y los adjunta al FFM.

Puedes verificar cualquier operación de cancelación en **FacturAPI Response Log** (ver [Emitir un CFDI — FacturAPI Response Log](emitir-cfdi.md#facturapi-response-log)).

---

## Permisos requeridos para cancelar

Solo los siguientes roles pueden cancelar una Factura Fiscal Mexico:

| Rol | Puede cancelar FFM |
|---|---|
| System Manager | ✅ Sí |
| Facturacion Mexico Manager | ✅ Sí |
| Facturacion Mexico System Manager | ✅ Sí |
| Accounts Manager | ❌ No |
| Accounts User | ❌ No |

El botón **Cancel** no aparece en la UI si el usuario no tiene uno de los roles autorizados.

---

## Restricciones adicionales

- Solo se pueden cancelar facturas con `fm_fiscal_status = TIMBRADO`
- CFDIs con complementos de pago activos requieren cancelar el complemento primero
- Notas de crédito (tipo E) pueden requerir cancelar la nota antes que la factura original en algunos casos
