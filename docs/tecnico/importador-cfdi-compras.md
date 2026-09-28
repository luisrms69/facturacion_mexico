# Importador histórico de CFDI de compra (`cfdi_historico_compras`)

Carga masiva de CFDI de compra (XML recibidos) como **Purchase Invoice en Draft**, reutilizando
**sin modificar** el pipeline existente de `cfdi_recibidos`.

## Propósito y límites

- Reutiliza `cfdi_recibidos.services.xml_ingestion.ingest_xml()` y
  `cfdi_recibidos.services.purchase_invoice_builder.build_purchase_invoice()`. **No** duplica su
  lógica ni toca ese paquete.
- Crea **Purchase Invoice en Draft** (docstatus=0). No hace submit, no timbra, no llama al PAC, no
  crea Payment Entry.
- Es un **orquestador batch** sobre un directorio de XML, con `dry_run`, reporte JSON/CSV y savepoint
  por archivo.

## Flujo por XML

1. **dry-run (preflight 100% READ-ONLY):** parsea y reporta qué ocurriría; **no** llama `ingest_xml`
   ni `build_purchase_invoice`, **no** escribe BD ni archivos.
2. **apply:** reutiliza el pipeline real → crea `CFDI Recibido` (ancla del UUID + XML adjunto) y la
   **Purchase Invoice en Draft**; savepoint por archivo.

## Idempotencia

- Por **`Purchase Invoice.fm_cfdi_uuid`** (campo `unique`). `build_purchase_invoice` recupera la PI
  existente para el mismo UUID (no duplica) y falla-cerrado si el UUID pertenece a otro CFDI o el
  `grand_total` difiere.
- La ingestión también deduplica por `CFDI Recibido.uuid` (`unique`).

## Proveedores (fail-closed, NO auto-crea)

Antes de llamar `ingest_xml`, el importador verifica que exista **Supplier por RFC**:

- Si falta → estado `ERROR_SUPPLIER_MISSING`, **no** se llama al pipeline (evita la auto-creación de
  proveedores que hace `ingest_xml`), y el proveedor se acumula en un **CSV de proveedores faltantes**
  (`..._proveedores_faltantes.csv`) para carga por Data Import.
- Este importador **nunca** crea Suppliers.

## Fail-closed

`Item`, cuenta de gasto o regla de impuesto faltante → `build_purchase_invoice` lanza `ValidationError`
→ rollback del archivo y estado de error. No se crea una PI incompleta.

## Estados

`READY` (dry-run) · `CREADA` · `SKIP_EXISTING` · `ERROR_SUPPLIER` · `ERROR_ITEM` · `ERROR_ACCOUNT` ·
`ERROR_TAX` · `ERROR_TOTAL` · `ERROR_OTHER`. Reporte JSON + CSV por corrida.

## Manifest

`company` (requerido). El resto (mapeos, cuentas, reglas de impuesto) proviene de la configuración
existente de `cfdi_recibidos` (`Configuracion CFDI Recibidos`).

## Ejecución

```bash
# dry-run
bench --site <site> execute facturacion_mexico.cfdi_historico_compras.importer.run \
  --kwargs "{'source_dir': '<ruta_xml>', 'manifest': '<manifest.json>', 'dry_run': 1}"
# apply
bench --site <site> execute facturacion_mexico.cfdi_historico_compras.importer.run \
  --kwargs "{'source_dir': '<ruta_xml>', 'manifest': '<manifest.json>', 'dry_run': 0}"
```

## Estado de validación

Cubierto por **tests unitarios** (dry-run read-only, fail-closed de proveedor sin auto-crear,
idempotencia por UUID). **No** validado end-to-end con datos reales todavía.
