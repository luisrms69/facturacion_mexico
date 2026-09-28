# Preparación de terceros desde CFDI (`preparacion_terceros`)

Funcionalidad satélite **V1 solo lectura** para preparar altas de Customers/Suppliers a partir de
lotes de XML CFDI. **No** crea nada en BD: genera CSV listos para **Data Import**.

## Propósito y límites

- Analiza un directorio de XML, identifica la Company por su RFC y determina el **rol** de la
  contraparte (empresa Emisor ⇒ contraparte = Receptor = **Customer**; empresa Receptor ⇒ contraparte
  = Emisor = **Supplier**).
- **No** toca `cfdi_recibidos` ni `cfdi_emitidos`. Reutiliza el parser XXE-safe `utils/secure_xml`.
- **100% read-only**: no escribe BD de ninguna forma.
- **NO crea** Customer ni Supplier automáticamente. **NO inventa** Customer Group, Territory, Supplier
  Group, cuentas ni clasificaciones — esos defaults se agregan al CSV antes de importar.

## Datos extraídos (solo confiables del XML)

RFC, razón social, régimen fiscal, código postal fiscal y, para extranjeros, `ResidenciaFiscal` /
`NumRegIdTrib` cuando existan.

## Dedupe e identidad

- Nacional: por **RFC**.
- Extranjero genérico (`XEXX010101000`): **no** se asume identidad por RFC — se usa `NumRegIdTrib`, y
  si falta, nombre normalizado + residencia.

## Detección de existencia (read-only)

Customer por `tax_id` (o `fm_num_reg_id_trib` para extranjeros); Supplier por `tax_id`.

## Estados

`EXISTENTE` · `A_CREAR_CUSTOMER` · `A_CREAR_SUPPLIER` · `DATOS_INSUFICIENTES` · `ERROR_PARSE` ·
`ERROR_COMPANY_RFC` · `ERROR_AMBIGUO`.

## Salidas

- Reporte JSON + CSV general (por tercero consolidado).
- **CSV de Customers faltantes** (`customer_name, tax_id, fm_tax_regime, fm_num_reg_id_trib,
  codigo_postal_fiscal, residencia_fiscal`).
- **CSV de Suppliers faltantes** (`supplier_name, tax_id, regimen_fiscal, codigo_postal_fiscal`).

## Límites reales

- Supplier no tiene campos fiscales `fm_*` ni campo de TIN extranjero → régimen/CP quedan como
  columnas informativas; un Supplier extranjero genérico no es identificable con confianza
  (`DATOS_INSUFICIENTES`).
- `fm_tax_regime` es Link a `Régimen Fiscal SAT`: el CSV lleva el código; puede requerir mapeo en el
  Data Import.

## Ejecución

```bash
bench --site <site> execute facturacion_mexico.preparacion_terceros.preparador.run \
  --kwargs "{'source_dir': '<ruta_xml>', 'report_dir': '<ruta_salida>'}"
```

## Estado de validación

Cubierto por **tests unitarios** (parseo real, rol por RFC, dedupe nacional/extranjero, existencia
read-only, generación de CSV). **No** validado end-to-end con datos reales.
