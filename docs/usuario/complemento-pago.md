# Complemento de Pago PPD

Guía para registrar pagos de facturas emitidas con método de pago PPD
(Pago en Parcialidades o Diferido).

---

## ¿Cuándo se usa?

Cuando emites una factura con `Método de Pago = PPD`, el SAT exige que registres
cada cobro mediante un **Complemento de Pago** (CFDI tipo P). Sin este complemento
el IVA no se reconoce fiscalmente.

---

## Flujo automático

Al registrar un `Payment Entry` para una factura PPD y hacer Submit:

1. El sistema detecta que el pago corresponde a una factura PPD
2. Crea automáticamente el `Complemento Pago MX`
3. Timbra el complemento con FacturAPI.io
4. El campo `fm_complemento_pago` del Payment Entry queda vinculado

No se requiere acción manual — el complemento se genera al hacer Submit del Payment Entry.

---

## Prerequisitos

- La Sales Invoice debe tener `fm_payment_method_sat = PPD`
- El Payment Entry debe estar vinculado a la Sales Invoice
- Debe existir `Configuracion Fiscal Mexico` con el wizard completado

---

## Ver los complementos generados

En el workspace **Facturación México**: shortcut **Complemento Pago MX**.

O desde el Payment Entry, campo `fm_complemento_pago` → link al complemento.

---

## Complementos migrados del sistema legacy

Los complementos creados durante la migración desde `facturacion_mx` muestran
**Origen de Creación = Migración legacy facturacion_mx** en el campo `fm_creation_source`.

El botón **Cancelar Complemento** no está disponible para estos registros —
la cancelación debe gestionarse directamente en el portal del SAT o a través del equipo técnico.

Los complementos nuevos creados por el sistema muestran `Timbrado directo` y sí permiten cancelación desde la UI.

---

## Enviar complemento por email

Desde el Complemento Pago MX timbrado, el menú **Comprobantes** incluye el botón
**Enviar por email**.

El sistema envía el CFDI tipo P directamente al cliente vía FacturAPI. El destinatario
se resuelve en este orden:

1. Email del contacto en el Payment Entry
2. Email del cliente (`Customer.email_id`)

Si no hay destinatario, aparece un aviso naranja. En ese caso, configura el email
en el cliente o el Payment Entry y vuelve a intentarlo.

---

## Troubleshooting

**El complemento no se generó al hacer Submit:**
1. Verificar que la Sales Invoice tiene `fm_payment_method_sat = PPD`
2. Verificar que el Payment Entry está en estado Submit
3. Revisar `FacturAPI Response Log` para errores de timbrado
