# Importador histórico de CFDI emitidos (`cfdi_emitidos`)

Capacidad reusable para **reconstruir Sales Invoice históricas** a partir de los
CFDI 4.0 de Ingreso ya timbrados (emitidos) de una empresa. Cada CFDI vigente
produce una `Sales Invoice` nativa en **Draft** (`docstatus = 0`) con su XML —y su
PDF si existe— adjuntos.

Módulo: `facturacion_mexico/cfdi_emitidos/` (`parser.py`, `importer.py`).

---

## Propósito y límites

- **Propósito:** cargar el histórico de facturación emitida como Sales Invoice
  Draft, preservando fielmente los importes fiscales del CFDI.
- **NO** timbra, **NO** hace Submit, **NO** llama al PAC, **NO** crea Payment Entry.
- **NO** crea Items ni Customers, y **no resuelve automáticamente datos faltantes**:
  cuando falta el Item o el Customer, la factura se **reporta** como excepción y no
  se importa (ver estados abajo).
- El precio **siempre** viene del XML.

---

## Configuración por `manifest` externo

La configuración específica de cada corrida **no** vive en el repositorio: se pasa
como un `manifest` (dict o ruta a JSON) externo. Campos:

| Campo | Requerido | Descripción |
|---|---|---|
| `company` | sí | Company destino de las Sales Invoice. |
| `item_map` | sí | Mapa `NoIdentificacion` del CFDI → `item_code` real del site. |
| `iva_account` | si hay traslados | Cuenta para el IVA trasladado. |
| `default_cost_center` | no | Default si el Customer no tiene uno (si se omite, el de la Company). |
| `cancelled_marker` | no (`cancel`) | Subcadena en el nombre de archivo que marca un CFDI cancelado. |
| `tolerance` | no (`0.05`) | Tolerancia decimal de la reconciliación de importes. |

El motor es **genérico**: no contiene mapeos, cuentas ni datos de ninguna empresa.

---

## Idempotencia

La llave canónica es **`Sales Invoice.fm_folio_fiscal == UUID`** (Folio Fiscal SAT =
UUID del Timbre). En cada corrida:

- Si ya existe una Sales Invoice con ese UUID → `SKIP_EXISTING` (no se duplica).
- Si el UUID aparece en más de una Sales Invoice → `ERROR_DUPLICATE`.
- Si la Sales Invoice fue borrada, el CFDI vuelve a clasificarse como `READY`.

No depende del archivo adjunto: la idempotencia es por el campo fiscal.

---

## Dry-run vs apply

`run(source_dir, manifest, dry_run=1|0, ...)`:

- **`dry_run=1`** (default): clasifica y reconcilia importes **sin escribir en la
  base de datos** (no inserta Sales Invoice ni adjunta archivos).
- **`dry_run=0`**: crea las Draft `READY`, adjunta XML/PDF y reconcilia, con
  transacción por factura.

Emite un resumen con contadores y reportes JSON/CSV.

---

## Adjuntos XML/PDF

- El **XML** es la fuente de verdad y siempre se adjunta.
- El **PDF** se adjunta solo si existe su hermano determinista: **mismo nombre base
  (stem) en el mismo directorio** que el XML (`<stem>.xml` ↔ `<stem>.pdf`). Sin
  emparejamiento difuso.
- Un PDF sin XML correspondiente se **reporta como huérfano** y nunca genera una
  Sales Invoice.
- Los adjuntos son **idempotentes** (no se duplican en reejecuciones). El PDF se
  adjunta escribiéndolo por filesystem para evitar el reparseo costoso del contenido.

---

## Precio histórico fiel (sin descuento ficticio)

Para cada línea el importador envía explícitamente:

```
price_list_rate = ValorUnitario del CFDI
rate            = ValorUnitario del CFDI
```

Al enviar `price_list_rate == rate`, ERPNext **no fabrica** `discount_amount` contra
el `Item Price` maestro (que puede tener un precio vigente distinto al histórico).
Así la Sales Invoice refleja el precio real del CFDI y `discount_amount = 0` /
`discount_percentage = 0` cuando el CFDI no trae descuento.

### `ERROR_DESCUENTO` (fail-closed)

Los CFDI con **descuento real** (`Concepto@Descuento` / `Comprobante@Descuento`)
**aún no están soportados**. En vez de representarlos de forma incorrecta o destruir
el descuento, el importador los **bloquea y reporta** como `ERROR_DESCUENTO` y no los
importa. El caso sin descuento funciona de forma segura.

---

## Protección de `Item Price`

El importador **no crea ni modifica `Item Price`** durante la carga. ERPNext, con
`Stock Settings.auto_insert_price_list_rate_if_missing = 1`, puede crear un
`Item Price` al resolver los detalles del ítem. Para impedirlo **solo durante la
importación**, el motor desactiva ese ajuste **en memoria** (sobre el documento
cacheado por request), sin escribir en la base de datos ni cambiar configuración
global, y lo **restaura con `try/finally`** al terminar el lote. No afecta a otras
operaciones concurrentes.

---

## Estados de clasificación

| Estado | Significado |
|---|---|
| `READY` / `CREADA` | Listo para crear / creado en Draft. |
| `SKIP_EXISTING` | Ya existe una Sales Invoice con ese UUID. |
| `SKIP_CANCELLED` | CFDI cancelado (por `cancelled_marker`). |
| `ERROR_CUSTOMER` / `ERROR_CUSTOMER_AMB` | Customer no resuelto / ambiguo. |
| `ERROR_ITEM` | `NoIdentificacion` sin mapeo a Item. |
| `ERROR_TAX` / `ERROR_TOTAL` | Falta cuenta de IVA / importes no reconcilian. |
| `ERROR_DESCUENTO` | CFDI con descuento real (no soportado). |
| `ERROR_DUPLICATE` | UUID en más de una Sales Invoice. |

### Receptores extranjeros

Los receptores extranjeros comparten el RFC genérico `XEXX010101000`, por lo que el
`tax_id` no los distingue. La resolución usa la evidencia adicional del CFDI
(`NumRegIdTrib`, `ResidenciaFiscal`, Nombre) contra los datos reales del Customer:
un match inequívoco resuelve; 0 → `ERROR_CUSTOMER`; más de uno → `ERROR_CUSTOMER_AMB`.
