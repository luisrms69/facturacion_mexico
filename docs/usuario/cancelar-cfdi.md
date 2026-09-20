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
2. Desde el Sales Invoice → abrir la **Factura Fiscal Mexico** (botón **"Abrir Factura Fiscal"**)
3. En el FFM → sección **Cancelación** → seleccionar el **motivo** (02, 03 o 04)

> Los motivos **02, 03 y 04** se procesan **desde la Factura Fiscal Mexico**. El motivo **01
> no se ejecuta mediante cancelación directa**: se realiza por **sustitución**, que inicia desde el
> Sales Invoice con el botón **"Sustituir CFDI (01)"** (ver Camino B). El sistema crea una factura de
> reemplazo y cancela el CFDI anterior mediante la cascada de sustitución.
4. Confirmar

El sistema envía la **solicitud** de cancelación a FacturAPI.io. Que FacturAPI reciba la solicitud
**no** significa que el CFDI ya esté cancelado: solo cuando el SAT lo confirma queda en `CANCELADO`.

### Qué pasa después

| Estado real en el SAT | Estado resultante | Qué significa |
|---|---|---|
| `canceled` | `CANCELADO` | Cancelación **confirmada** por el SAT |
| `pending` / `verifying` / `accepted` (sin `canceled`) | `PENDIENTE_CANCELACION` | La solicitud se procesó; el SAT/receptor aún no la confirma |
| `rejected` / `expired` | `TIMBRADO` (sin cambio) | La cancelación no procedió; el CFDI sigue vigente |

Si queda en `PENDIENTE_CANCELACION`: esperar. El SAT acepta automáticamente después de 72 horas si el
receptor no responde. Puedes verificar o actualizar el estado con el botón **"Verificar estado en
FacturAPI"** en el FFM (ver [Verificar estado en FacturAPI](verificar-estado-facturapi.md)).

---

## Camino B — Motivo 01 (cancelación con sustitución)

Este camino se usa cuando hay un error en la factura y necesitas emitir una versión corregida. El
sistema crea el CFDI sustituto, lo relaciona con el original mediante **TipoRelación 04** y, una vez
timbrado el sustituto, cancela el CFDI original con **Motivo de cancelación 01**.

**El flujo lo inicia el sistema desde el Sales Invoice original: tú NO creas la factura sustituta a mano
ni ingresas UUIDs.**

### Pasos

1. Abrir el **Sales Invoice original** timbrado (`fm_fiscal_status = TIMBRADO`).
2. Pulsar el botón **"🔄 Sustituir CFDI (01)"** (grupo *Opciones Fiscales*).
3. El sistema **crea automáticamente una nueva Sales Invoice sustituta** (copia de la original en
   Borrador) que conserva la referencia al CFDI original (`ffm_substitution_source_uuid` = UUID del CFDI
   original). Verás el mensaje *"SI de reemplazo creado: …"*.
4. Abrir la **nueva Sales Invoice sustituta**, **corregir los datos** y **timbrarla**
   (ver [Emitir un CFDI](emitir-cfdi.md)). Al timbrarse, el CFDI sustituto incluye **automáticamente
   `TipoRelación = 04`** apuntando al **UUID del CFDI original**.
5. Cuando el sustituto queda timbrado (obtiene su propio UUID), el sistema **cancela automáticamente el
   CFDI original con Motivo 01**, usando el **UUID del sustituto** como folio de sustitución (cascada).
   No ingresas UUIDs manualmente.

> **Importante:** el **Motivo 01 no se ejecuta desde la Factura Fiscal Mexico.** Si intentas cancelar con
> motivo 01 desde el FFM, el sistema te remite al Sales Invoice y al botón **"Sustituir CFDI (01)"**.

> **No confundir tres conceptos con el mismo número:** el **Motivo de cancelación 01** (la razón por la
> que se cancela el CFDI original), la **TipoRelación 01** (nota de crédito por descuento/bonificación;
> ver [Notas de Crédito](notas-credito.md)) y la **TipoRelación 04** (relación del CFDI sustituto hacia el
> original en este flujo). Son catálogos SAT distintos.

### Qué pasa después

La cancelación motivo 01 generalmente es inmediata (`CANCELADO`). El SAT vincula ambos CFDIs: el sustituto
referencia al original con **TipoRelación 04**, y el original se cancela citando el **UUID del sustituto**.

#### Si la cancelación del CFDI anterior queda pendiente

A veces el PAC no procesa la cancelación del CFDI original en el mismo instante en que se timbra el
sustituto (un desfase momentáneo del servicio). En ese caso verás un mensaje **amarillo** (no un error):

> **Factura sustituta timbrada correctamente. La cancelación del CFDI anterior quedó pendiente y el
> sistema continuará reintentándola automáticamente.**

Qué significa:

- **La factura sustituta SÍ quedó timbrada** correctamente. No es un error de timbrado.
- El CFDI **anterior** queda en **`PENDIENTE_CANCELACION`**: su cancelación se solicitó pero el PAC aún
  no la confirmó.
- **No tienes que hacer nada.** El sistema reintenta la cancelación automáticamente (con más frecuencia
  en los primeros minutos y luego cada pocos minutos). Cuando el PAC la confirma, el CFDI anterior pasa
  a `CANCELADO` solo.
- Si tras un periodo prolongado no se logra, el CFDI anterior se marca para **revisión manual** (queda
  con un mensaje indicando que requiere intervención).

> El sistema **nunca** marca un CFDI como cancelado sin la confirmación real del PAC: mientras esté
> `PENDIENTE_CANCELACION`, el CFDI anterior sigue vigente ante el SAT.

---

## Estado después de cancelar

El campo `fm_fiscal_status` en el Sales Invoice cambia a `CANCELADO` (o `PENDIENTE_CANCELACION` mientras espera al receptor).

En general, el Sales Invoice **permanece** en ERPNext — la cancelación fiscal no implica cancelar el documento ERPNext.

**Excepción — sustitución (motivo 01):** cuando el CFDI anterior se cancela por sustitución, al confirmarse la cancelación el sistema **sí cancela también el documento ERPNext**: el Sales Invoice y su Factura Fiscal Mexico originales pasan a `docstatus = 2` (cancelados). Si la cancelación quedó `PENDIENTE_CANCELACION`, esto ocurre cuando la cancelación se confirma (de inmediato o por el reintento automático).

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

El control de acceso opera en dos niveles:

- **Botón Cancel nativo de Frappe** — depende del permiso `cancel` del DocPerm: solo se
  habilita para los roles con `cancel=1`.
- **Acción de cancelación personalizada** (`cancel_ffm_keep_si`) — la autorización se valida
  en el servidor mediante `frappe.only_for`. Si el usuario no tiene uno de los roles
  autorizados, la operación se rechaza con error de permisos al ejecutarse.

---

## Restricciones adicionales

- Solo se pueden cancelar facturas con `fm_fiscal_status = TIMBRADO`
- CFDIs con complementos de pago activos requieren cancelar el complemento primero
- Notas de crédito (tipo E) pueden requerir cancelar la nota antes que la factura original en algunos casos
