# Arquitectura — Facturación México

Estado actual del sistema. Se actualiza cuando un PR cambia arquitectura real.

---

## Módulos principales

| Módulo | Ruta | Función |
|---|---|---|
| `facturacion_fiscal` | `facturacion_fiscal/` | Timbrado, cancelación, Factura Fiscal Mexico |
| `complementos_pago` | `complementos_pago/` | Complemento de Pago PPD |
| `ereceipts` | `ereceipts/` | E-Receipts / autofactura |
| `facturas_globales` | `facturas_globales/` | Factura Global periódica |
| `cfdi_recibidos` | `cfdi_recibidos/` | Pipeline CFDI Recibidos → Purchase Invoice |
| `addendas` | `addendas/` | Addendas genéricas por cliente |
| `catalogos_sat` | `catalogos_sat/` | Catálogos SAT (uso CFDI, forma pago, etc.) |
| `multi_sucursal` | `multi_sucursal/` | Configuración fiscal por Branch |
| `validaciones` | `validaciones/` | RFC, lista 69B SAT |

---

## Flujo principal — CFDI emitido

```
Sales Invoice (submit)
  → hooks: before_validate (STCT por Branch), validate (cost_center + clave SAT)
  → Factura Fiscal Mexico
  → timbrado_api.py → FacturAPI.io → SAT
```

## Flujo principal — CFDI recibido

```
Upload XML
  → xml_ingestion.py → CFDI Recibido (Falta proveedor)
  → Paso 7: auto-crea Supplier si no existe
  → compute_stage → Falta departamento
  → Asignar departamento
  → Clasificar conceptos (item_code por concepto)
  → PurchaseInvoiceBuilder → Purchase Invoice Draft
```

## Flujo — Complemento de Pago PPD

```
Payment Entry (submit)
  → hook on_submit → create_complement_if_required
  → Complemento Pago MX → timbrado → SAT
```

---

## DocTypes principales

| DocType | Tipo | Función |
|---|---|---|
| `Factura Fiscal Mexico` | Submittable | CFDI tipo I/E timbrado |
| `Complemento Pago MX` | Submittable | CFDI tipo P (PPD) |
| `EReceipt MX` | Submittable | Recibo para autofacturación |
| `Factura Global MX` | Submittable | CFDI global periódico |
| `Facturacion Mexico Company Settings` | Por Company | Credenciales FacturAPI y defaults por empresa |
| `Configuracion Fiscal Mexico` | Por empresa | Wizard STCT/ITT (emitidos) |
| `Configuracion CFDI Recibidos` | Por empresa | Config impuestos + tolerancias (recibidos) |
| `CFDI Recibido` | Normal | XML recibido en proceso |
| `Addenda Type` | Normal | Template Jinja2 de addenda — global, un registro por formato de cadena |

---

## Integraciones externas

| Sistema | Uso | Configuración |
|---|---|---|
| **FacturAPI.io** | PAC para timbrado y cancelación | `Facturacion Mexico Company Settings` |
| **SAT (lista 69B)** | Validación RFC | Vía API REST |

---

## Custom Fields críticos

**Sales Invoice:** `fm_fiscal_status`, `fm_factura_fiscal_mx`, `fm_addenda_*`, `fm_branch`, `fm_es_ppd`
**Customer:** `fm_tax_regime`, `fm_uso_cfdi_default`, `fm_requires_addenda`, `fm_default_addenda_type`, `fm_buyer_gln`, `fm_seller_gln`, `fm_seller_id`, `fm_invoice_creator_gln`, `fm_dias_credito_addenda`
**Address:** `fm_gln` (GLN de sucursal destino para addendas EDI)
**Item Customer Detail:** `ref_code` (nativo ERPNext), `fm_customer_uom`, `fm_customer_description`
**Branch:** `fm_enable_fiscal`, `fm_lugar_expedicion`, `fm_serie_pattern`, folios
**Payment Entry:** `fm_complemento_pago`, `fm_complement_generated`
**Purchase Invoice:** `fm_cfdi_uuid`, `fm_cfdi_recibido`

## Item Groups fiscales

El app crea automáticamente grupos raíz y subgrupos de categorización fiscal. El ITT (Item Tax Template) se asigna al grupo raíz; los items en subgrupos heredan el impuesto.

| Grupo raíz | Subgrupos incluidos |
|---|---|
| `Artículos con IVA al 0%` | Frutas y verduras, Carnes, Lácteos y huevo, Medicamentos, Agua natural, etc. |
| `Artículos Exentos` | Libros, Servicios médicos, Servicios educativos, etc. |
| `Artículos IEPS Alcohol` | Cerveza, Vinos, Licores, etc. |
| `Artículos IEPS Azúcar` | Refrescos, Bebidas energéticas, Botanas, etc. |
| `Artículos IEPS Combustibles` | Gasolina, Diésel, Gas LP, etc. |
| `Artículos IEPS Tabaco` | Cigarros, Puros, Tabaco labrado |

Los subgrupos se crean idempotentemente en cada `bench migrate` — nunca se modifican ni borran grupos existentes.

---

> Este documento describe el estado actual. Para el historial de decisiones, ver [ADRs](../adr/index.md).
