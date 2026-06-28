# Emitir un CFDI

Guía del flujo completo: Sales Invoice → Factura Fiscal Mexico → Timbrado.

---

## Cómo funciona el sistema

El timbrado en facturacion_mexico tiene dos documentos:

- **Sales Invoice** — la venta en ERPNext. Se submittea normalmente.
- **Factura Fiscal Mexico (FFM)** — el documento fiscal. Se crea la primera vez que haces clic en **"Timbrar Factura"** sobre el Sales Invoice, y es donde ocurre el timbrado real.

> **Un solo FFM activo por Sales Invoice.** La creación del FFM la resuelve el servidor: la primera vez crea el documento y lo vincula; las siguientes veces reutiliza el mismo. No se pueden generar dos facturas fiscales activas para la misma venta.

Los dos documentos están vinculados. El estado fiscal visible en el Sales Invoice (campo `fm_fiscal_status`) refleja siempre el estado del FFM.

---

## Estados fiscales

| Estado | Significa |
|---|---|
| `BORRADOR` | FFM creada, pendiente de timbrar |
| `PROCESANDO` | Solicitud de timbrado en curso |
| `TIMBRADO` | CFDI timbrado y válido ante el SAT |
| `ERROR` | El PAC rechazó el timbrado — revisar logs |
| `PENDIENTE_CANCELACION` | Solicitud de cancelación enviada al SAT, esperando aceptación del receptor |
| `CANCELADO` | CFDI cancelado ante el SAT |
| `E-RECEIPT` | Venta en modo E-Receipt — el cliente puede autofacturarse vía portal |
| `E-RECEIPT-FACTURADO` | El E-Receipt fue facturado (individual o incluido en Factura Global) |

Los estados `E-RECEIPT` y `E-RECEIPT-FACTURADO` **no provienen del flujo FFM** — son actualizados
por el módulo EReceipt MX cuando la venta opera en modo autofactura. Una Sales Invoice en modo
E-Receipt no tiene Factura Fiscal Mexico vinculada; el campo `fm_ereceipt_mx` apunta al EReceipt MX.
Ver [E-Receipts y Autofactura](ereceipts.md) para el detalle de ese flujo.

---

## Flujo paso a paso

### 1. Crear y configurar el Sales Invoice

Antes de hacer Submit, verificar:

| Dato | Dónde se configura | Obligatorio |
|---|---|---|
| RFC del cliente | Customer → `tax_id` | Sí |
| Régimen fiscal del cliente | Customer → `fm_tax_regime` | Sí |
| Uso CFDI | Sales Invoice → `fm_cfdi_use` | Sí |
| Clave SAT de cada item | Item → `fm_producto_servicio_sat` | Sí |
| Template de impuestos | Sales Invoice → `taxes_and_charges` | Sí |
| Método de pago | Sales Invoice → `fm_payment_method_sat` | Sí (PUE o PPD) |

> **PUE** — Pago en Una Exhibición: la factura se paga en el mismo momento.
> **PPD** — Pago en Parcialidades o Diferido: se pagará después. Requiere Complemento de Pago al cobrar.

### 2. Submit del Sales Invoice

Al hacer Submit:
- El Sales Invoice muestra el botón **"Timbrar Factura"** como acción primaria
- Todavía **no** existe Factura Fiscal Mexico — se crea en el siguiente paso

### 3. Generar / abrir la Factura Fiscal Mexico

Clic en **"Timbrar Factura"** en el Sales Invoice:
- Si la venta aún no tiene FFM, el servidor **crea** uno en estado `BORRADOR`, lo vincula y te lleva a él.
- Si ya tiene un FFM activo, **reutiliza** el existente y te lleva a él (no crea otro).
- Si el FFM ya está `TIMBRADO`, el sistema avisa que no se puede volver a timbrar.

En el FFM revisar antes de timbrar:
- **Régimen fiscal** (`fm_tax_system`) — cargado desde el cliente
- **Forma de pago** (`fm_forma_pago_timbrado`) — cargada desde Payment Entry si PUE
- **Método de pago** (`fm_payment_method_sat`) — PUE o PPD
- **Tipo de comprobante** — `I - Ingreso` para factura normal; `E - Egreso` para nota de crédito

### 4. Submit del FFM

El FFM debe estar en estado **Submitted** (docstatus = 1) para poder timbrar.

Si aún está en Draft: clic en **Submit**.

### 5. Timbrar

Con el FFM en estado Submitted y `status = BORRADOR`:

Clic en **"Timbrar con FacturAPI"** → el sistema envía el CFDI a FacturAPI.io → el PAC lo timbra ante el SAT.

Si el timbrado fue exitoso:
- El campo `status` del FFM cambia a **TIMBRADO**
- El Sales Invoice muestra `fm_fiscal_status = TIMBRADO`
- El FFM queda con UUID, fecha de timbrado, XML y PDF

Si falló: `status = ERROR`. Ver la sección [Revisar errores de timbrado](#revisar-errores-de-timbrado).

---

## Datos que quedan en el FFM tras el timbrado

| Campo | Contenido |
|---|---|
| `fm_uuid` | UUID del CFDI timbrado |
| `fm_serie_folio` | Serie y folio asignados |
| `fm_fecha_timbrado` | Fecha y hora del timbrado |
| `fm_xml_url` | URL al archivo XML del CFDI |
| `fm_pdf_url` | URL al PDF del CFDI |
| `fm_rfc_pac` | RFC del PAC que timbró |
| `fm_no_certificado_sat` | Número de certificado SAT |

El XML y PDF quedan adjuntos al FFM como archivos privados.

---

## FacturAPI Response Log

Cada operación con el PAC (timbrado, cancelación, consulta) genera un registro en **FacturAPI Response Log**.

Acceso: workspace **Facturación México** → sección **Logs** → **FacturAPI Response Log**.

O desde el FFM: campo `fm_last_response_log` → link al log más reciente.

| Campo del log | Contenido |
|---|---|
| `operation_type` | `timbrado`, `cancelacion` |
| `success` | Si la operación fue exitosa |
| `facturapi_response` | Respuesta JSON completa del PAC |
| `error_message` | Mensaje de error si falló |
| `timestamp` | Fecha y hora de la operación |

---

## Revisar errores de timbrado

Si `status = ERROR`:

1. Abrir el FFM
2. Ir al campo `fm_last_response_log` → clic en el link al log
3. Ver `error_message` para el mensaje de error del PAC
4. Ver `facturapi_response` para la respuesta completa del PAC

Errores comunes:

| Error | Causa probable | Solución |
|---|---|---|
| `RFC inválido` | RFC del cliente con formato incorrecto | Corregir `tax_id` en Customer |
| `ClaveProdServ no encontrada` | Item sin clave SAT o clave inexistente en catálogo | Corregir `fm_producto_servicio_sat` en Item |
| `Régimen fiscal inválido` | Código de régimen fuera del rango 600–630 | Verificar `fm_tax_regime` en Customer |
| `Payload incompleto` | Faltan campos obligatorios | Ver detalle en el error — revisa datos fiscales del cliente o item |

Después de corregir: volver al FFM y clic en **"Reintentar Timbrado"**.

---

## Nota sobre clientes sin RFC (Público en General)

Si el cliente usa RFC genérico `XAXX010101000`:
- El sistema permite el timbrado con receptor "Público en General"
- El `fm_cfdi_use` debe ser `S01 - Sin efectos fiscales`
- El régimen fiscal del receptor debe ser `616 - Sin obligaciones fiscales`

---

## Envío por correo

Si el cliente tiene configurado envío automático de CFDI (`fm_enviar_email_timbrado = 1`),
el sistema envía el XML y PDF por correo al hacer el timbrado.

La configuración de correo se hereda de `Customer.fm_auto_send_cfdi` con fallback a
`Facturacion Mexico Company Settings` (configuración por compañía).

---

## Siguientes pasos

- [Complemento de Pago PPD](complemento-pago.md) — si la factura es PPD
- [Cancelar un CFDI](cancelar-cfdi.md) — si necesitas cancelar
- [Troubleshooting](troubleshooting.md) — errores frecuentes
