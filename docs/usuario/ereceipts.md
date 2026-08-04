# E-Receipts y Autofactura

!!! warning "Funcionalidad pendiente de validación integral"
    Existe implementación parcial de E-Receipts, pero **el flujo completo contra FacturAPI y el
    portal de autofacturación no ha sido validado integralmente ni aprobado para producción ni
    capacitación**. Esta página describe el comportamiento **de diseño según el código**; no debe
    tomarse como guía operativa aprobada. En particular, **no** están validados: el portal de
    autofactura, la autofacturación por el receptor, ni la expiración automática. Ver el estado en
    `working_docs/active/auditoria_manual/I_scope_roadmap.md` (F-01).

Los E-Receipts son recibos digitales para ventas a público en general. El cliente puede
autofacturarse en un portal web con su RFC, sin intervención del operador.

---

## ¿Cuándo usar E-Receipts?

Cuando la venta es a público general (sin RFC conocido de antemano) pero el cliente
puede necesitar su factura después. Ejemplos: tienda retail, punto de venta, servicio al cliente.

**No usar** para ventas B2B donde el RFC ya se conoce antes de la venta. Para esas, el flujo
normal de [Emitir un CFDI](emitir-cfdi.md) es el correcto.

---

## Flujo general

```text
Sales Invoice (Modo E-Receipt)
  ↓
EReceipt MX creado automáticamente
  ↓ FacturAPI genera el receipt + portal URL
self_invoice_url → cliente lo visita y captura su RFC
  ↓ FacturAPI timbra el CFDI
EReceipt MX sincroniza: UUID, folio, fecha
```

El CFDI lo genera FacturAPI — ERPNext guarda la trazabilidad y el link al portal.

---

## Configurar una venta en modo E-Receipt

En el Sales Invoice, antes de hacer Submit:

1. Ir a la sección **Configuración E-Receipt**
2. Cambiar el campo **Modo de Facturación** a `E-Receipt`
3. Configurar vencimiento (cuántos días tiene el cliente para autofacturarse):
   - `Fixed Days` — N días desde la fecha de emisión
   - `End of Month` — hasta el último día del mes
4. Hacer **Submit**

El sistema crea automáticamente un documento **EReceipt MX** vinculado.

---

## El widget E-Receipt en la Sales Invoice

Después del Submit, en la sección **Configuración E-Receipt** del Sales Invoice aparece
un widget con el estado del E-Receipt:

| Estado | Color | Significa |
|---|---|---|
| `Abierto` | Naranja | El portal de autofactura está disponible |
| `Autofacturado` | Verde | El cliente ya se autofacturó; CFDI generado |
| `Factura Global` | Verde | El receipt fue incluido en una Factura Global periódica |
| `Expirado` | Gris | La fecha límite pasó sin autofactura |
| `Cancelado` | Rojo | El E-Receipt fue cancelado |

Cuando está `Abierto`, el widget muestra:
- La URL del portal de autofactura (botón **Copiar URL** y botón **Abrir portal**)
- La fecha de expiración

---

## Entregar la URL al cliente

El cliente necesita la URL del portal para autofacturarse. Opciones:

- **Copiar URL** desde el widget del Sales Invoice y enviársela por mensaje/correo manualmente
- (Fase siguiente) Botón de envío por email directo desde ERPNext

La URL tiene el formato: `https://factura.space/<dominio-empresa>/<clave-receipt>`

---

## Qué hace el cliente en el portal

1. Visita la URL
2. Ingresa su RFC, razón social, email y uso CFDI
3. FacturAPI genera y timbra el CFDI automáticamente
4. El cliente descarga su XML y PDF

ERPNext no interviene en este paso. Al sincronizar, el EReceipt MX queda con el UUID del CFDI.

---

## Sincronización de estado

El estado del E-Receipt en FacturAPI (autofacturado, cancelado, etc.) se sincroniza
automáticamente cada 24 horas. También se puede sincronizar manualmente:

- Abrir el documento **EReceipt MX**
- Clic en el botón **Sincronizar con FacturAPI**

!!! warning "Si no sincronizas antes de Factura Global"
    Un EReceipt que aparece como `open` localmente puede haber sido autofacturado por el
    cliente en el portal. **Siempre sincronizar antes de generar la Factura Global** para
    evitar incluir un receipt que ya tiene CFDI individual.

---

## Datos fiscales que guarda el EReceipt MX

El EReceipt MX es el espejo local del receipt en FacturAPI. Estos son los campos principales:

| Campo | Descripción |
|---|---|
| `self_invoice_url` | URL del portal de autofactura |
| `status` | Estado: open / invoiced_to_customer / invoiced_globally / cancelled |
| `invoice_uuid` | UUID del CFDI generado (se llena al sincronizar tras autofactura) |
| `invoice_folio` | Folio fiscal del CFDI |
| `invoiced_at` | Fecha en que se generó el CFDI |
| `factura_global_mx` | Link a la Factura Global si fue incluido en una |
| `last_sync_at` | Última sincronización con FacturAPI |

**El Sales Invoice NO guarda UUID, folio ni PDF.** Solo guarda el link (`fm_ereceipt_mx`) y el
estado operativo (`fm_fiscal_status = E-RECEIPT`). Los datos fiscales se leen desde el EReceipt MX.

---

## Factura Global

!!! warning "Factura Global — pendiente de interfaz y validación integral"
    La **Factura Global** existe a nivel de API (métodos del servidor) pero **no cuenta con una
    interfaz de usuario completa** ni con validación integral end-to-end. **No** está aprobada como
    flujo operativo: no la uses como procedimiento de producción hasta que exista UI y validación.

En el diseño, si el cliente no se autofactura antes de que expire el receipt, la empresa podría
incluirlo en una **Factura Global** periódica que agrupa los receipts abiertos del período. Hoy ese
agrupamiento y su timbrado solo están disponibles vía API del servidor, sin pantalla operable.

!!! note "Limitación de diseño"
    Los E-Receipts con **IEPS** no pueden incluirse en Factura Global hasta que se implemente
    el modelo line-level de impuestos (issue #182).

---

## Configurar los defaults de E-Receipt por empresa

En `Facturacion Mexico Company Settings`:

| Campo | Para qué |
|---|---|
| `ereceipt_expiry_type_default` | Tipo de vencimiento por defecto |
| `ereceipt_expiry_days_default` | Días de vencimiento por defecto |
| `ereceipt_payment_form_default` | Forma de pago SAT por defecto para E-Receipts |
| `global_payment_form_default` | Forma de pago SAT por defecto para Factura Global |

---

## Próximas funcionalidades

- Fase 1: Botón de envío de URL por email directo desde ERPNext
- Fase 2: Sincronización manual y scheduler configurable
- Fase 3: Facturar individualmente desde ERPNext (para casos donde el operador necesita hacerlo)
- Fase 4: Factura Global vía API de FacturAPI (simplifica la generación)
