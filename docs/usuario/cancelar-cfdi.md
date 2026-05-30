# Cancelar un CFDI

Guía para cancelar comprobantes fiscales timbrados según la normativa SAT.

---

## Motivos de cancelación

El SAT requiere seleccionar uno de estos motivos al cancelar:

| Código | Motivo | Cuándo usar |
|---|---|---|
| 01 | Comprobante emitido con errores **con** relación | Hay un CFDI sustituto (corrección con TipoRelación 04) |
| 02 | Comprobante emitido con errores **sin** relación | Error sin sustituto, monto ≤ $1,000 o CFDI no deducible |
| 03 | No se llevó a cabo la operación | La venta o servicio no se realizó |
| 04 | Operación nominativa relacionada en factura global | El ticket ya fue incluido en una Factura Global |

---

## Cómo cancelar

1. Abrir el **Sales Invoice** timbrado
2. Clic en el botón **Cancelar CFDI** (aparece cuando `fm_fiscal_status = TIMBRADO`)
3. Seleccionar el **motivo** de cancelación
4. Si el motivo es **01**: ingresar el UUID del CFDI sustituto
5. Confirmar

El sistema envía la solicitud de cancelación a FacturAPI.io, que la gestiona ante el SAT.

---

## Estado después de cancelar

El campo `fm_fiscal_status` cambia a `CANCELADO`. El Sales Invoice permanece en ERPNext pero el CFDI queda cancelado ante el SAT.

---

## Emitir un CFDI sustituto (motivo 01)

Si necesitas emitir una versión corregida:

1. Desde el Sales Invoice cancelado, clic en **"Nueva factura fiscal"** (aparece cuando `fm_fiscal_status = CANCELADO`)
2. El sistema crea un nuevo Sales Invoice vinculado con **TipoRelación 04**
3. Corrige los datos y hace Submit para timbrar el sustituto

---

## Notas importantes

- La cancelación ante el SAT puede tardar 72 horas en ser aceptada si el receptor no la acepta directamente
- Un CFDI con complemento de pago registrado no puede cancelarse sin cancelar primero el complemento
- Los CFDI de tipo E (nota de crédito) requieren cancelar también la nota antes que la factura original en algunos casos
