# Referencia — Campos fiscales (custom fields de usuario)

Referencia de los **custom fields** de `facturacion_mexico` que son **visibles y relevantes
para el usuario**: los que el usuario **captura** (categoría 1, visible-configurable) y los que
el **sistema calcula o refleja** en solo lectura (categoría 2, visible-informativo).

**Alcance:** 48 campos (31 configurables + 17 informativos/solo-lectura), agrupados por DocType.

**Fuera de alcance (no se documentan aquí):** Section/Column/Tab Break y widgets HTML
(estructura visual), campos ocultos internos, campos MOCK de *Draft management*
(`fm_draft_*`, `fm_create_as_draft`) y campos legados sin consumo real en código.

**Cómo leer la columna "Origen":**

- **Usuario captura** → el usuario escribe o selecciona el valor (campo configurable).
- **Sistema calcula / solo lectura** → el sistema lo escribe automáticamente; el usuario
  no debe llenarlo (informativo).

> Los atributos (etiqueta, tipo, solo-lectura, obligatorio, default) están validados contra
> `facturacion_mexico/fixtures/custom_field.json`.

---

## Sales Invoice

Campos fiscales sobre la factura de venta. Aparecen en la sección **Información Fiscal México**
(y subsecciones de multi-sucursal, e-receipt y addenda) de la Sales Invoice.

| Etiqueta | fieldname | Tipo | Origen | Propósito | Cuándo aparece | Flujo que lo usa |
|---|---|---|---|---|---|---|
| Estado Fiscal | `fm_fiscal_status` | Select | Sistema calcula / solo lectura | Estado fiscal del CFDI de la factura (refleja el estado de la FFM) | Siempre, en la sección fiscal | Timbrado I/E, cancelación, capa de estado fiscal UI |
| Folio Fiscal FFM | `fm_folio_fiscal` | Data | Sistema calcula / solo lectura | Folio fiscal (UUID) reflejado desde la Factura Fiscal México | Tras timbrado exitoso | Timbrado; reflejo desde FFM (`utils.py`, `tasks.py`) |
| Factura Fiscal México | `fm_factura_fiscal_mx` | Link | Sistema calcula / solo lectura | Liga al documento Factura Fiscal México (CFDI) generado | Tras crear la Factura Fiscal | Creación de FFM; resumen CFDI en la SI |
| Requiere Complemento de Pago | `fm_es_ppd` | Check | Sistema calcula / solo lectura | Marca la factura como PPD (requiere complemento de pago) | Según método de pago de la factura | Complemento de Pago PPD |
| Sucursal Fiscal | `fm_branch` | Link | Usuario captura | Sucursal responsable de la facturación fiscal | Cuando la factura requiere timbrado (`fm_requires_stamp`) | Multi-sucursal; asignación automática STCT; impuestos automatizados |
| Modo de Facturación | `fm_ereceipt_mode` | Select | Usuario captura | Normal = timbrado directo; E-Receipt = recibo para autofacturación (default: `Normal`) | Siempre, en la sección E-Receipt | E-Receipts / autofactura |
| Tipo de Vencimiento | `fm_ereceipt_expiry_type` | Select | Usuario captura | Tipo de vencimiento del E-Receipt (default: `Fixed Days`) | Solo si `fm_ereceipt_mode == "E-Receipt"` | E-Receipts |
| Días de Vencimiento | `fm_ereceipt_expiry_days` | Int | Usuario captura | Días de vigencia del E-Receipt (default: `3`) | Si es E-Receipt y tipo `Fixed Days` | E-Receipts |
| Fecha de Vencimiento | `fm_ereceipt_expiry_date` | Date | Usuario captura | Fecha de vencimiento del E-Receipt | Si es E-Receipt y tipo `Custom Date` | E-Receipts |
| E-Receipt MX | `fm_ereceipt_mx` | Link | Sistema calcula / solo lectura | Liga al EReceipt MX generado | Tras generar el E-Receipt | E-Receipts |
| Requiere Addenda | `fm_addenda_required` | Check | Usuario captura | Indica si la factura requiere addenda (default: `0`) | Siempre, en la sección de addenda | Addendas |
| Tipo de Addenda | `fm_addenda_type` | Link | Usuario captura | Tipo de addenda a generar | Si `fm_addenda_required` | Addendas |
| Estado de Addenda | `fm_addenda_status` | Select | Sistema calcula / solo lectura | Estado de generación de la addenda | Si `fm_addenda_required` | Addendas |
| XML de Addenda | `fm_addenda_xml` | Code | Sistema calcula / solo lectura | XML de addenda generado | Cuando el estado de addenda es `Completada` | Addendas |
| Errores de Addenda | `fm_addenda_errors` | Small Text | Sistema calcula / solo lectura | Errores de generación de la addenda | Cuando el estado de addenda es `Error` | Addendas |
| Fecha Generación Addenda | `fm_addenda_generated_date` | Datetime | Sistema calcula / solo lectura | Fecha de generación de la addenda | Cuando el estado de addenda es `Completada` | Addendas |

---

## Customer

Campos fiscales sobre el cliente. Aparecen en la pestaña **Fiscal México** y en la sección
**Configuración de Addendas** del Customer.

| Etiqueta | fieldname | Tipo | Origen | Propósito | Cuándo aparece | Flujo que lo usa |
|---|---|---|---|---|---|---|
| Centro de Costo Por Defecto | `fm_customer_default_cost_center` | Link | Usuario captura | Centro de costo que se asigna automáticamente en facturas de este cliente | Siempre | Impuestos automatizados; JS de Sales Invoice |
| Envío automático de CFDI | `fm_envio_email_cliente` | Select | Usuario captura | Preferencia de envío automático de CFDI por email (default: `Default (usar settings)`) | Siempre, en la pestaña fiscal | Envío de CFDI por email (FFM) |
| Régimen Fiscal SAT | `fm_tax_regime` | Link | Usuario captura | Régimen fiscal del cliente según catálogo SAT | Siempre | Timbrado; factura global; FFM |
| Puede facturar como Venta Mostrador | `fm_allow_generic_rfc` | Check | Usuario captura | Permite emitir CFDI con RFC genérico XAXX010101000 — venta mostrador (default: `0`) | Siempre | Venta mostrador / CFDI individual con RFC genérico |
| Uso CFDI por Defecto | `fm_uso_cfdi_default` | Link | Usuario captura | Uso de CFDI por defecto para este cliente | Siempre | Timbrado; catálogos SAT; validación de SI |
| RFC Validado con SAT | `fm_rfc_validated` | Check | Sistema calcula / solo lectura | Indica si el RFC fue validado ante el SAT | Siempre, en la sección Validación SAT | Validación RFC contra SAT |
| Fecha Validación RFC | `fm_rfc_validation_date` | Date | Sistema calcula / solo lectura | Fecha de la validación del RFC | Siempre, en la sección Validación SAT | Validación RFC contra SAT |
| Requiere Addenda | `fm_requires_addenda` | Check | Usuario captura | Indica que el cliente requiere addenda (default: `0`) | Siempre, en la sección de addendas | Addendas; propagación a la SI |
| Tipo de Addenda Por Defecto | `fm_default_addenda_type` | Link | Usuario captura | Tipo de addenda por defecto del cliente | Si `fm_requires_addenda` | Addendas; propagación a la SI |
| GLN Comprador (Addenda) | `fm_buyer_gln` | Data | Usuario captura | GLN (Global Location Number) del comprador para addendas EDI | Si `fm_requires_addenda` | Addendas EDI |
| Días de Crédito (Addenda) | `fm_dias_credito_addenda` | Int | Usuario captura | Días de crédito a incluir en addendas EDI (default: `0`) | Si `fm_requires_addenda` | Addendas EDI |
| GLN Proveedor (Addenda) | `fm_seller_gln` | Data | Usuario captura | GLN asignado por el cliente a nuestra empresa como proveedor | Si `fm_requires_addenda` | Addendas EDI |
| ID Proveedor (Addenda) | `fm_seller_id` | Data | Usuario captura | Número de proveedor asignado por el cliente a nuestra empresa | Si `fm_requires_addenda` | Addendas EDI |
| GLN Invoice Creator (Addenda) | `fm_invoice_creator_gln` | Data | Usuario captura | GLN del nodo InvoiceCreator requerido por el cliente | Si `fm_requires_addenda` | Addendas EDI |

---

## Branch

Campos fiscales multi-sucursal sobre el Branch. Aparecen en las secciones **Configuración Fiscal**
y **Gestión de Folios**.

| Etiqueta | fieldname | Tipo | Origen | Propósito | Cuándo aparece | Flujo que lo usa |
|---|---|---|---|---|---|---|
| Company | `company` | Link | Usuario captura | Empresa asociada a la sucursal (**obligatorio**) | Siempre | Multi-sucursal; impuestos; factura global |
| Habilitar para Facturación Fiscal | `fm_enable_fiscal` | Check | Usuario captura | Activa la sucursal para emisión de CFDI (default: `0`) | Siempre | Multi-sucursal |
| Lugar de Expedición (Código Postal) | `fm_lugar_expedicion` | Data | Usuario captura | Código postal fiscal donde se expiden las facturas | Si `fm_enable_fiscal` | Timbrado (lugar de expedición) |
| Zona Fronteriza (MX) | `fm_is_border_zone` | Check | Usuario captura | Marca la sucursal en zona fronteriza para aplicar IVA Frontera (default: `0`) | Si `fm_enable_fiscal` | Impuestos automatizados (IVA frontera) |
| Patrón de Serie | `fm_serie_pattern` | Data | Usuario captura | Patrón para generar series de folios, ej. `SUC1-{yyyy}` (default: `{abbr}-{yyyy}`) | Si `fm_enable_fiscal` | Gestión de folios y series |
| Folio Inicial | `fm_folio_start` | Int | Usuario captura | Primer folio disponible para esta sucursal (default: `1`) | Si `fm_enable_fiscal` | Gestión de folios |
| Folio Final | `fm_folio_end` | Int | Usuario captura | Último folio disponible para esta sucursal | Si `fm_enable_fiscal` | Gestión de folios |

---

## Payment Entry

Campos fiscales sobre el registro de pago. Aparecen en la sección **Información Fiscal MX**.

| Etiqueta | fieldname | Tipo | Origen | Propósito | Cuándo aparece | Flujo que lo usa |
|---|---|---|---|---|---|---|
| Complemento Pago Generado | `fm_complemento_pago` | Link | Sistema calcula / solo lectura | Liga al Complemento de Pago MX generado | Tras generarse el complemento | Complemento de Pago PPD |
| Requiere Complemento | `fm_require_complement` | Check | Usuario captura | Indica que el pago requiere complemento PPD | Siempre, en la sección fiscal | Complemento de Pago PPD |
| Complemento Generado | `fm_complement_generated` | Check | Sistema calcula / solo lectura | Indica si ya se generó el complemento de pago | Siempre, en la sección fiscal | Complemento de Pago PPD |

---

## Item

Campo de clasificación SAT sobre el artículo. Aparece en la sección **Clasificación SAT**.

| Etiqueta | fieldname | Tipo | Origen | Propósito | Cuándo aparece | Flujo que lo usa |
|---|---|---|---|---|---|---|
| SAT Producto/Servicio | `fm_producto_servicio_sat` | Link | Usuario captura | Clave SAT Producto/Servicio del artículo | Siempre | Timbrado (obligatorio por línea); factura global |

---

## Cost Center

Campos de mapeo del centro de costo a la operación fiscal.

| Etiqueta | fieldname | Tipo | Origen | Propósito | Cuándo aparece | Flujo que lo usa |
|---|---|---|---|---|---|---|
| Sucursal Fiscal Mapeada | `fm_mapped_branch` | Link | Usuario captura | Asocia el Centro de Costo a una sucursal fiscal | Cuando hay company definida | Multi-sucursal; selección automática de sucursal |
| Price List Ventas por Defecto | `fm_default_selling_price_list` | Link | Usuario captura | Price List por defecto al facturar desde este Centro de Costo | Siempre | Impuestos automatizados; JS de Sales Invoice |

---

## Purchase Invoice

Campos de trazabilidad de CFDI recibidos sobre la factura de compra.

| Etiqueta | fieldname | Tipo | Origen | Propósito | Cuándo aparece | Flujo que lo usa |
|---|---|---|---|---|---|---|
| UUID CFDI Recibido | `fm_cfdi_uuid` | Data | Sistema calcula / solo lectura | UUID del CFDI recibido de origen (único; garantiza idempotencia y recupera PI huérfano en reintento) | Al generar la PI desde un CFDI recibido | CFDI recibidos |
| CFDI Recibido | `fm_cfdi_recibido` | Link | Sistema calcula / solo lectura | Liga al CFDI Recibido del que se generó esta factura de compra | Al generar la PI desde un CFDI recibido | CFDI recibidos |

---

## Item Customer Detail

Campos de addenda por combinación artículo/cliente (tabla hija dentro de Item).

| Etiqueta | fieldname | Tipo | Origen | Propósito | Cuándo aparece | Flujo que lo usa |
|---|---|---|---|---|---|---|
| UOM Addenda (Cliente) | `fm_customer_uom` | Data | Usuario captura | Código de unidad EDI que el cliente espera en la addenda (ej. EA, KGM, PCE) | En la tabla de detalle por cliente del Item | Addendas EDI |
| Descripción Addenda (Cliente) | `fm_customer_description` | Data | Usuario captura | Descripción del producto según el catálogo del cliente para la addenda | En la tabla de detalle por cliente del Item | Addendas EDI |

---

## Item Group

Campo de clasificación SAT de gasto para CFDI recibidos.

| Etiqueta | fieldname | Tipo | Origen | Propósito | Cuándo aparece | Flujo que lo usa |
|---|---|---|---|---|---|---|
| Sufijo SAT de gasto | `fm_codigo_sufijo_sat` | Data | Usuario captura | Sufijo del Código Agrupador SAT (Anexo 24) para la categoría de gasto — 2 dígitos sin punto (ej. 48 combustibles, 50 teléfono) | Siempre | CFDI recibidos (resolución de cuenta de gasto) |

---

## Notas de reconciliación

- **Address:** sus dos custom fields quedan fuera de esta referencia. `fm_gln` (GLN para
  addenda EDI) no tiene consumidor funcional en código (solo declaración) → categoría legado;
  `is_your_company_address` es un campo legado sin prefijo `fm_`. Por eso Address no tiene tabla.
- **Campos calculados de sucursal** (`fm_folio_current`, `fm_last_invoice_date`,
  `fm_monthly_average`) y **administrativos de folios/certificados**
  (`fm_folio_warning_threshold`, `fm_share_certificates`, `fm_certificate_ids`) se tratan como
  configuración operativa/administrativa y se documentan en `referencia/configuracion.md`, no aquí.
- **Excluidos por legado/sin-consumo** (categoría 5): `fm_folio_reserved`, `fm_pending_amount`,
  `fm_complementos_count`, `fm_certificate_info`, `fm_branch_health_status`,
  `fm_auto_selected_branch`, `fm_lista_69b_status`, `fm_gln`, `fm_last_invoice_date`,
  `fm_monthly_average`, y los 7 campos MOCK de *Draft management*.
- **Ocultos internos** (categoría 3): `ffm_substitution_source_uuid` (Data, `hidden=1`).
