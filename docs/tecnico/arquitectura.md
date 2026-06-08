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

## Flujo E-Receipt / Autofactura

```text
Sales Invoice (submit, fm_ereceipt_mode="E-Receipt")
  → crear_ereceipt() → EReceipt MX (local)
  → POST /receipts → FacturAPI.io
  → FacturAPI genera: receipt + self_invoice_url + key
  → EReceipt MX guarda: facturapi_id, key, self_invoice_url, status=open
  → SI actualiza: fm_ereceipt_mx = EReceipt.name, fm_fiscal_status = "E-RECEIPT"

Cliente visita self_invoice_url → portal FacturAPI
  → captura RFC, razón social, email
  → FacturAPI timbra CFDI tipo I
  → receipt.status → invoiced_to_customer

Sync (scheduler o manual)
  → GET /receipts/{facturapi_id}
  → EReceipt MX actualiza: status, invoice_uuid, invoice_folio, invoiced_at
  → SI actualiza: fm_fiscal_status = "E-RECEIPT-FACTURADO"
```

**Principio arquitectónico:** FacturAPI hace el heavy lifting fiscal (timbrado, portal, CFDI global).
ERPNext solo conserva trazabilidad y control. UUID/folio/invoice_id **nunca** se copian a Sales Invoice.
Ver [ADR-0032](../adr/0032-ereceipts-facturapi-arquitectura.md).

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
| `EReceipt MX` | Submittable | Recibo para autofacturación — espejo local del receipt en FacturAPI |
| `Factura Global MX` | Submittable | CFDI global periódico — agrupa EReceipts abiertos del período |
| `Facturacion Mexico Company Settings` | Por Company | Credenciales FacturAPI y defaults por empresa |
| `Configuracion Fiscal Mexico` | Por empresa | Wizard STCT/ITT (emitidos) |
| `Configuracion Reclasificacion Fiscal Mexico` | Por empresa | Reglas de reclasificación IVA en Payment Entry (cobros y pagos) |
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

**Sales Invoice:** `fm_fiscal_status`, `fm_factura_fiscal_mx`, `fm_addenda_*`, `fm_branch`, `fm_es_ppd`,
`fm_ereceipt_mx` (link al EReceipt MX), `fm_ereceipt_summary_html` (widget estado E-Receipt),
`fm_ereceipt_mode` (Normal / E-Receipt), `fm_ereceipt_expiry_*` (configuración vencimiento)
**Customer:** `fm_tax_regime`, `fm_uso_cfdi_default`, `fm_requires_addenda`, `fm_default_addenda_type`, `fm_buyer_gln`, `fm_seller_gln`, `fm_seller_id`, `fm_invoice_creator_gln`, `fm_dias_credito_addenda`
**Address:** `fm_gln` (GLN de sucursal destino para addendas EDI), `is_your_company_address` (workaround ERPNext v16 — campo requerido por `erpnext/accounts/custom/address.py` pero no declarado en el DocType nativo; se agrega como Custom Field con default=0 para evitar AttributeError al guardar Address de clientes)
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

## Factura Global — validaciones fiscales (desde PR #183)

El módulo `facturas_globales/` tiene un conjunto de validaciones estrictas antes de timbrar.
Si alguna condición no se cumple, **bloquea con ValidationError** — nunca asume valores por defecto.

| Validación | Error si... | Cómo resolver |
|---|---|---|
| `tax_rate` del EReceipt | Es `None` (no determinable) | El EReceipt debe tener tasa IVA definida. Recrear desde SI con taxes configurados. |
| `fm_unidad_sat` del item global | Falta en el item configurado | Configurar en el item global de la empresa |
| `global_payment_form_default` | No configurado | `Facturacion Mexico Company Settings` → campo `global_payment_form_default` |
| IEPS en receipt | El EReceipt tiene `has_ieps = 1` | Pendiente issue #182. Los receipts con IEPS no pueden ir a Factura Global aún. |

**Cálculo de base e impuesto (correcto desde PR #183):**

```python
base = total / (1 + tax_rate / 100)
impuesto = total - base
```

Antes del PR #183, el aggregator usaba `total * 0.84` y `total * 0.16` (hardcoded 16%),
lo que producía valores incorrectos para IVA 8% y tasa 0%.

Ver [ADR-0033](../adr/0033-factura-global-hardcodes.md) para el razonamiento completo.

### Campos transitorios en EReceipt MX (PR #183)

`tax_rate` (Percent) y `has_ieps` (Check) son campos transitorios agregados para habilitar
las validaciones de Factura Global sin implementar el modelo definitivo de impuestos por línea.

Serán eliminados cuando issue #182 implemente `EReceipt MX Tax Line` (child table con
impuestos por línea de producto). Ver [ADR-0033](../adr/0033-factura-global-hardcodes.md).

---

> Este documento describe el estado actual. Para el historial de decisiones, ver [ADRs](../adr/index.md).
