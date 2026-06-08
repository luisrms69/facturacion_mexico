# Addendas EDI

Guía para configurar y emitir CFDIs con addenda para clientes corporativos (La Comer, Liverpool, Walmart, etc.).

---

## ¿Qué es una addenda?

Una addenda es un bloque XML adicional que se agrega al CFDI a petición del cliente receptor. Las cadenas comerciales lo usan para intercambio EDI: incluye GLNs, número de pedido, códigos de producto del cliente y datos de entrega.

---

## Arquitectura

| Dónde vive el dato | Qué contiene |
|---|---|
| **Addenda Type** | Template Jinja2 del XML. Global — un template por formato de cadena. |
| **Customer** (tab Fiscal México) | `fm_buyer_gln`, `fm_seller_gln`, `fm_seller_id`, `fm_invoice_creator_gln`, `fm_dias_credito_addenda` |
| **Address** (tienda destino) | `fm_gln` — GLN de la sucursal receptora |
| **Item > Sales > Customer Details** | `ref_code` — código/GTIN que el cliente asigna a este producto |
| **Company** (dirección principal) | CP, calle y ciudad del emisor (`emisor_cp`, `emisor_calle`, `emisor_ciudad`) |

---

## Configuración paso a paso

### 1. Addenda Type

Accede desde **Facturación México → Addenda Type → New** (o abre el existente).

| Campo | Descripción |
|---|---|
| Nombre del Tipo | Identificador único (ej: `La Comer`) |
| Versión | Versión del formato EDI (ej: `AMC7.1`) |
| Namespace XML | URI del namespace si aplica |
| Activo | Debe estar marcado |
| Template XML (Jinja2) | El XML de la addenda con variables Jinja2 |

El template usa variables que el generador resuelve automáticamente desde los DocTypes de ERPNext. Ver variables disponibles al final de esta página.

### 2. Customer — datos EDI

En **Selling → Customer**, pestaña **Fiscal México**, sección **Configuración de Addendas**:

| Campo | Descripción |
|---|---|
| Requiere Addenda | Activar para este cliente |
| Tipo de Addenda Por Defecto | Link al Addenda Type |
| GLN Comprador (Addenda) | GLN que el cliente usa como comprador |
| GLN Proveedor (Addenda) | GLN que el cliente asignó a tu empresa como proveedor |
| ID Proveedor (Addenda) | Número de proveedor asignado por el cliente |
| GLN Invoice Creator (Addenda) | GLN del nodo InvoiceCreator |
| Días de Crédito (Addenda) | Días de crédito para el bloque `paymentTerms` |

### 3. Direcciones del cliente receptor

El cliente corporativo normalmente tiene dos tipos de Address en ERPNext:

**Dirección de facturación (Billing)**

Una sola dirección fiscal del cliente. Se crea en **Contacts → Address → New**:

| Campo | Valor |
|---|---|
| Address Title | Nombre del cliente (ej: `COMERCIAL CITY FRESKO`) |
| Address Type | `Billing` |
| Address Line 1 | Domicilio fiscal |
| City / State / Pincode | Datos del domicilio fiscal |
| Is Primary Address | ✅ |
| Links → Customer | Vincular al Customer |

**Direcciones de envío por sucursal (Shipping)**

Una Address por cada tienda/cedis a la que se envía mercancía. Cada una lleva el GLN específico de esa sucursal:

1. Ir a **Contacts → Address → New**
2. Llenar:

| Campo | Valor |
|---|---|
| Address Title | Nombre identificador de la sucursal (ej: `CITY FRESKO SUC 420 - LA COMER INSURGENTES`) |
| Address Type | `Shipping` |
| Address Line 1 | Calle y número |
| City / State / Pincode | Datos de la tienda |
| **GLN (Addenda EDI)** (`fm_gln`) | GLN de esta sucursal específica (ej: `7505000354205`) |
| Links → Customer | Vincular al mismo Customer |

> El GLN en la Shipping Address es el que aparece en el nodo `<shipTo><gln>` de la addenda. Si no hay GLN configurado, el nodo quedará vacío y el EDI fallará la validación del cliente.

### 4. Dirección del emisor (InvoiceCreator)

El bloque `<InvoiceCreator>` de la addenda usa la dirección de la **Company** de ERPNext, no de un Branch específico.

Verifica que la Company emisora tenga una Address vinculada con `Is Primary Address = 1` y los campos correctos:

| Campo ERPNext | Variable addenda | Descripción |
|---|---|---|
| Address Line 1 | `emisor_calle` | Calle y número del emisor |
| City | `emisor_ciudad` | Ciudad del emisor |
| Pincode | `emisor_cp` | Código postal fiscal del emisor |

Si la dirección de la Company no existe o no tiene los campos completos, los datos del emisor quedarán vacíos en la addenda.

### 5. Códigos de producto del cliente

En **Stock → Item → pestaña Sales → Customer Details**:

Agrega una fila por cada cliente con los datos de mapeo:

| Campo | Descripción |
|---|---|
| **Customer Name** | El cliente (ej: COMERCIAL CITY FRESKO) |
| **Ref Code** | GTIN o código interno que el cliente asigna a este producto (ej: `45865`) |
| **Customer UOM** (`fm_customer_uom`) | Código EDI de unidad que el cliente espera en la addenda (ej: `EA`, `KGM`, `PCE`). Si está vacío, se usa el código SAT del item (ej: `H87`). |
| **Descripción Addenda** (`fm_customer_description`) | Descripción del producto según catálogo del cliente (ej: `ALBAHACAR   1 PZA`). Si está vacío, se usa el `item_name` de ERPNext. |

No se requiere un DocType separado — ERPNext ya tiene esta funcionalidad nativa con dos campos custom adicionales.

### 6. Company — verificación final

El paso 4 anterior cubre la Address de la Company. Antes de emitir, confirma que:
- La Company tiene Address vinculada con `Is Primary Address = 1`
- `fm_invoice_creator_gln` en el Customer tiene el GLN correcto del nodo `InvoiceCreator`
- Todos los campos GLN del Customer están llenos (pasos 2)

---

## Emitir una factura con addenda

1. Crear **Sales Invoice** para el cliente con addenda configurada (ej: COMERCIAL CITY FRESKO)
2. En el campo **Shipping Address** seleccionar la sucursal destino — debe ser una de las Shipping Addresses del cliente con `fm_gln` configurado (paso 3)
3. Completar la factura normalmente (items, cantidades, impuestos)
4. **Submit** — al hacer submit, el sistema detecta que el cliente requiere addenda y genera el XML antes del timbrado
5. Desde la Factura Fiscal Mexico generada, clic en **"Timbrar con FacturAPI"** — el CFDI incluirá el bloque `<Addenda>` con el XML generado
6. El XML de addenda queda en `fm_addenda_xml`; el estado en `fm_addenda_status`

!!! warning "Shipping Address obligatorio"
    Si la Sales Invoice no tiene Shipping Address seleccionado, el nodo `<shipTo>` de la addenda quedará vacío. La mayoría de cadenas rechazan el CFDI en su sistema EDI si el GLN de entrega está vacío.

---

## Variables Jinja2 disponibles en el template

### Datos de la factura
| Variable | Origen |
|---|---|
| `invoice.posting_date` | Fecha de la factura |
| `invoice.name` | Número/folio de la factura |
| `invoice.po_no` | Número de orden de compra |
| `invoice.net_total` | Subtotal antes de impuestos |
| `invoice.total_taxes_and_charges` | Total de impuestos |
| `invoice.grand_total` | Total con impuestos |
| `invoice.conversion_rate` | Tipo de cambio |
| `invoice.items` | Lista de líneas (qty, rate, amount, item_code, item_name, uom) |

### Datos del comprador
| Variable | Origen |
|---|---|
| `customer.fm_buyer_gln` | Customer → GLN Comprador |
| `dias_credito` | Customer → Días de Crédito (Addenda) |

### Datos del vendedor (proveedor)
| Variable | Origen |
|---|---|
| `seller_gln` | Customer → GLN Proveedor |
| `seller_id` | Customer → ID Proveedor |
| `invoice_creator_gln` | Customer → GLN Invoice Creator |

### Dirección de envío
| Variable | Origen |
|---|---|
| `shipping_address.fm_gln` | Address → GLN (Addenda EDI) |
| `shipping_address.address_title` | Address → Address Title |
| `shipping_address.address_line1` | Address → Address Line 1 |
| `shipping_address.city` | Address → City |
| `shipping_address.pincode` | Address → Pincode |

### Datos del emisor
| Variable | Origen |
|---|---|
| `company.tax_id` | Company → Tax ID (RFC) |
| `company.name` | Company → Company Name |
| `emisor_cp` | Company Address → Pincode |
| `emisor_calle` | Company Address → Address Line 1 |
| `emisor_ciudad` | Company Address → City |

### Importe en letras
| Variable | Origen |
|---|---|
| `importe_letras` | Calculado automáticamente desde `invoice.grand_total` (español, formato MXN) |

Ejemplo: `DOS MIL SEISCIENTOS OCHENTA Pesos 00/100 M.N.`

### Mapeo de productos
| Variable | Uso |
|---|---|
| `product_mapping` | Dict `{item_code: {customer_item_code, customer_item_description, customer_uom}}` |

- `customer_item_code`: del campo `ref_code` en Item Customer Detail
- `customer_item_description`: de `fm_customer_description` (fallback: `item_name` del item)
- `customer_uom`: de `fm_customer_uom` (fallback: código SAT del UOM, ej: `H87` de `H87 - Pieza`)

Ejemplo en template:
```xml
{% set m = product_mapping.get(item.item_code) %}
<gtin>{{ m.customer_item_code if m else item.item_code }}</gtin>
<invoicedQuantity unitOfMeasure="{{ m.customer_uom if m else item.uom }}">
```

### Helpers
| Helper | Descripción |
|---|---|
| `helpers.format_currency(x)` | Formatea número con 2 decimales |
| `helpers.upper(x)` | Mayúsculas |
| `helpers.lower(x)` | Minúsculas |

---

## Gaps conocidos

- **Items globales**: Los items y sus `Customer Details` son globales del site — no hay aislamiento por Company en un entorno multi-empresa de giros distintos.
