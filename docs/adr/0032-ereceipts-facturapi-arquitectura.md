# ADR-0032: Arquitectura E-Receipts — FacturAPI como motor fiscal, ERPNext como trazabilidad

**Fecha:** 2026-06-06
**Estado:** Activo
**Issue:** #118 (E-Receipts flujo completo), Fase 0
**PR:** feat(ereceipts): Fase 0 — payload fiscal correcto + trazabilidad SI ↔ EReceipt MX

---

## Contexto

El módulo E-Receipts permite emitir recibos digitales a clientes de ventas a público en general,
ofreciéndoles un portal para autofacturarse cuando lo necesiten. FacturAPI.io (el PAC que ya usa
la app para timbrado normal) ofrece un flujo completo para esto:

- `POST /receipts` — crea el receipt con items y forma de pago
- Portal `factura.space/<domain>/<key>` — el cliente captura su RFC y FacturAPI genera el CFDI
- `POST /receipts/{id}/invoice` — facturar individualmente desde la API
- `POST /receipts/global-invoice` — factura global de todos los receipts abiertos del período

Antes de esta decisión, el código existente intentaba duplicar parte de este trabajo en ERPNext:
`invoice_ereceipt()` creaba un Sales Invoice local y lo pasaba por el flujo FFM/timbrado_api.py,
y `cfdi_global_builder.py` construía el payload CFDI manualmente en lugar de usar el endpoint
de FacturAPI para receipts.

---

## Decisión

**FacturAPI hace el heavy lifting fiscal. ERPNext solo mantiene control, trazabilidad y sincronización.**

Reglas resultantes:

1. **No portal propio.** El portal de autofactura es `factura.space/<domain>/<key>`. Solo guardamos
   y exponemos `self_invoice_url`. No construimos microsite propio.

2. **No crear Sales Invoice nueva para facturar un EReceipt.** Cuando el cliente autofactura o
   cuando el operador factura desde ERPNext, se usa `POST /receipts/{id}/invoice` de FacturAPI.
   FacturAPI genera el CFDI. ERPNext solo sincroniza el resultado.

3. **No usar el flujo FFM/timbrado_api.py para E-Receipts.** Ese flujo es para CFDI directos
   (Sales Invoice → FFM → timbrado). Para E-Receipts el flujo es diferente: el receipt vive
   en FacturAPI; ERPNext es un espejo.

4. **No construir Factura Global CFDI manualmente si FacturAPI puede hacerlo desde receipts.**
   Usar `POST /receipts/global-invoice` (pendiente Fase 4) en lugar de `POST /invoices` con
   payload construido localmente.

5. **UUID, folio, invoice_id, PDF, XML nunca se copian a Sales Invoice.** Esos datos viven en
   `EReceipt MX` (autofactura individual) o en `Factura Global MX` (factura global). La Sales
   Invoice solo guarda el Link (`fm_ereceipt_mx`) y el status operativo (`fm_fiscal_status`).
   El widget del SI lee los datos por relación bajo demanda — mismo patrón que `fm_ffm_summary_html`.

---

## Modelo de datos resultante

### Sales Invoice (campos nuevos)

| Campo | Tipo | Cuándo se llena |
|---|---|---|
| `fm_ereceipt_mx` | Link → EReceipt MX | Al crear EReceipt desde esta SI |
| `fm_ereceipt_summary_html` | HTML (widget) | Siempre visible si hay fm_ereceipt_mx |
| `fm_fiscal_status` | Select | `E-RECEIPT` al crear; `E-RECEIPT-FACTURADO` tras facturar |

### EReceipt MX (campos relevantes)

| Campo | Fuente | Descripción |
|---|---|---|
| `facturapi_id` | FacturAPI response | ID del receipt en FacturAPI — clave para todas las operaciones |
| `key` | FacturAPI response | Clave del receipt para el portal |
| `self_invoice_url` | FacturAPI response | URL completa del portal de autofactura |
| `status` | FacturAPI (sincronizado) | open / invoiced_to_customer / invoiced_globally / cancelled |
| `tax_rate` | SI.taxes (transitorio) | Tasa IVA del receipt — ver ADR-0033 |
| `invoice_id` | FacturAPI (sync) | ID del CFDI generado cuando se factura |
| `invoice_uuid` | FacturAPI (sync) | UUID fiscal del CFDI |
| `invoice_folio` | FacturAPI (sync) | Folio fiscal |
| `invoiced_at` | FacturAPI (sync) | Fecha de facturación |
| `factura_global_mx` | ERPNext (al incluir en FG) | Link a Factura Global MX |
| `last_sync_at` | ERPNext | Última sincronización con FacturAPI |

---

## Consecuencias

### Positivas
- Sin duplicación de lógica fiscal — FacturAPI ya lo resuelve correctamente para SAT
- Portal de autofactura sin infraestructura propia — FacturAPI lo provee con branding
- El CFDI generado por FacturAPI desde el receipt siempre es consistente con el receipt original
- Modelo de sincronización simple: `GET /receipts/{id}` actualiza el EReceipt MX local

### Negativas / trade-offs
- Requiere conexión a FacturAPI para operaciones fiscales (ya era el caso para timbrado normal)
- El status del EReceipt puede quedar desincronizado si no se ejecuta el scheduler de sync
- Si el cliente autofactura y no hay webhook/sync, ERPNext lo ve como `open` temporalmente

### Fuera de alcance de esta decisión
- IEPS line-level en E-Receipts: pendiente ADR-0034 e issue #182
- Webhooks: pendiente Fase posterior (#118)

---

## Alternativa descartada

**ERPNext como motor fiscal para E-Receipts** — crear una Sales Invoice nueva con los datos del cliente
que autofactura, pasarla por `timbrado_api.py` y generar un FFM. Descartada porque:
- Duplica el CFDI: FacturAPI ya lo genera al autofacturar en el portal
- El FFM duplicado no representa la venta original — representa una copia fiscal inconsistente
- No sincroniza el estado del receipt en FacturAPI → risk de doble facturación en Factura Global
