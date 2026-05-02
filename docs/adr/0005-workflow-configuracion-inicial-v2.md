# WORKFLOW DE CONFIGURACIÓN INICIAL — v2
========================================
Fecha: 2026-05-01
Branch: feature/e4-ieps-on-item-quantity
Supersede: docs/adr/0005-workflow-configuracion-inicial.md

Diferencia respecto a v1: incluye el sistema de Configuracion Fiscal Mexico,
generación de 8 STCT específicos, ITTs automáticos y mapeo de cuentas contables.

---

## Orden estricto de dependencias

```
Company + Chart of Accounts
        │
        ▼
Facturacion Mexico Settings  ←── API Key + RFC + CP
        │
        ▼
Configuracion Fiscal Mexico  ←── checkboxes alcance fiscal
        │
        ▼
Mapeo Cuenta Fiscal Mexico   ←── cuentas Tax por rol (usuario)
        │
        ▼
Generate Templates           ←── 8 STCT + ITTs (botón UI)
        │
        ├──▶ Sales Taxes and Charges Templates (8)
        └──▶ Item Tax Templates (3–18)
                │
                ▼
         Customer + Address + fm_regimen_fiscal
                │
                ▼
          Item + UOM SAT + fm_producto_servicio_sat
                │
                ▼
           Sales Invoice → SUBMIT
                │
                ▼
       Factura Fiscal Mexico → SUBMIT
                │
                ▼
           timbrar_factura()
```

---

## PASO 1 — Company

**Dónde:** Setup → Company

| Campo | Obligatorio | Notas |
|-------|-------------|-------|
| `company_name` | ✅ | — |
| `tax_id` | ✅ | RFC de la empresa emisora |
| `default_currency` | ✅ | `MXN` |
| `country` | ✅ | `México` |
| `abbr` | ✅ | Se usa como sufijo en nombres de templates: `"IVA Nacional - Básico - {abbr}"` |

El `abbr` es crítico: todos los STCT e ITT llevan el sufijo de la empresa.
Si se cambia después de generar los templates, los templates existentes quedan
huérfanos y hay que regenerarlos.

**Qué rompe si falta:** `generate_8_stct_for_company()` falla al intentar
leer `Company.abbr` — no puede construir nombres de templates.

---

## PASO 2 — Chart of Accounts (cuentas Tax)

**Dónde:** Accounting → Chart of Accounts

Antes de crear `Configuracion Fiscal Mexico`, deben existir cuentas contables
de tipo **Tax** para cada rol fiscal que se vaya a usar. El sistema no las crea —
son parte del plan de cuentas de la empresa.

**Cuentas mínimas para MVP (IVA básico):**

| Rol fiscal | Nombre sugerido | Tipo |
|------------|-----------------|------|
| `IVA por Pagar (Nacional)` | IVA por Pagar (16%) | Tax |
| `IVA Exento` | IVA Exento | Tax |

**Cuentas adicionales según alcance:**

| Checkbox | Roles requeridos | Cuentas necesarias |
|----------|-----------------|-------------------|
| `enable_frontera` | `IVA por Pagar (Frontera)` | 1 cuenta Tax |
| `enable_exportacion` | `IVA por Pagar (0% exportación)` | 1 cuenta Tax |
| `enable_ieps_alcohol` | `IEPS por Pagar (Alcohol)` | 1 cuenta Tax |
| `enable_ieps_azucar` | `IEPS por Pagar (Azúcar/Bebidas)` | 1 cuenta Tax |
| `enable_ieps_combustibles` | `IEPS por Pagar (Combustibles)` | 1 cuenta Tax |
| `enable_ieps_tabaco` | `IEPS por Pagar (Tabaco)` + `IEPS por Pagar (Tabaco Cuota)` | 2 cuentas Tax |
| `enable_ret_honorarios` | `IVA Retenido (Honorarios)` + `ISR Retenido (Honorarios)` | 2 cuentas Tax |
| `enable_ret_arrendamiento` | `IVA Retenido (Arrendamiento)` + `ISR Retenido (Arrendamiento)` | 2 cuentas Tax |
| `enable_ret_autotransporte` | `IVA Retenido (Autotransporte)` + `ISR Retenido (Autotransporte)` | 2 cuentas Tax |
| `enable_ret_resico` | `IVA Retenido (RESICO)` + `ISR Retenido (RESICO)` | 2 cuentas Tax |

**MVP mínimo:** 2 cuentas Tax (IVA Nacional + IVA Exento).

**Qué rompe si falta:** `Mapeo Cuenta Fiscal Mexico` valida que cada cuenta
sea tipo Tax, pertenezca a la empresa y no esté deshabilitada. Sin cuentas
válidas, `configuracion_completa` nunca se marca como `True` y no se pueden
generar los templates.

---

## PASO 3 — Facturacion Mexico Settings

**Dónde:** Facturacion Mexico → Facturacion Mexico Settings (Single)

| Campo | Obligatorio | Default | Notas |
|-------|-------------|---------|-------|
| `sandbox_mode` | ✅ | `1` | Usar `test_api_key` en lugar de `api_key` |
| `test_api_key` | ✅ si sandbox | — | API Key FacturAPI sandbox |
| `api_key` | ✅ si producción | `NULL` | API Key FacturAPI producción |
| `rfc_emisor` | ✅ | `NULL` | RFC empresa — campo obligatorio del CFDI |
| `lugar_expedicion` | ✅ | `NULL` | Código postal domicilio fiscal |
| `metodo_pago_default` | ✅ | `PUE` | `PUE` o `PPD` |
| `customer_email_fallback` | ✅ | valor demo | Email cuando cliente no tiene |
| `timeout` | ✅ | `30` | Segundos antes de timeout al PAC |

**Relación con Configuracion Fiscal Mexico:** independiente. Los Settings
son credenciales del PAC; la CFM es la configuración fiscal contable.
Ambos son necesarios para timbrar, pero en diferente momento del flujo.

---

## PASO 4 — Configuracion Fiscal Mexico

**Dónde:** Facturacion Mexico → Configuracion Fiscal Mexico → Nuevo
**Autoname:** `CFM-{company}` (uno por empresa)

Este DocType es el **wizard central** de la configuración fiscal. Orquesta
la creación de todos los templates de impuestos.

### 4a — Crear el documento

| Campo | Obligatorio | Default | Notas |
|-------|-------------|---------|-------|
| `company` | ✅ | — | Link único por empresa |
| `enable_exportacion` | — | `1` | IVA 0% exportación — activo por defecto |
| `enable_frontera` | — | `0` | Solo si empresa opera en zona fronteriza |
| `enable_ieps_alcohol` | — | `0` | Solo si vende alcohol |
| `enable_ieps_azucar` | — | `0` | Solo si vende bebidas azucaradas |
| `enable_ieps_combustibles` | — | `0` | Solo si vende combustibles |
| `enable_ieps_tabaco` | — | `0` | Solo si vende tabaco |
| `enable_ret_honorarios` | — | `0` | Solo si paga honorarios |
| `enable_ret_arrendamiento` | — | `0` | Solo si paga arrendamiento |
| `enable_ret_autotransporte` | — | `0` | Solo si usa autotransporte |
| `enable_ret_resico` | — | `0` | Solo si opera con RESICO |
| `tasa_isr_resico` | — | `1.25` | Solo si `enable_ret_resico = 1` |

Al guardar, el sistema sincroniza automáticamente `mapeo_cuentas` con las
filas de roles fiscales requeridos según los checkboxes.

**Roles siempre requeridos** (independiente de checkboxes):
- `IVA por Pagar (Nacional)`
- `IVA Exento`

### 4b — Completar el mapeo de cuentas

La tabla `mapeo_cuentas` se llena automáticamente con las filas de roles
requeridos. El usuario debe asignar la cuenta contable correspondiente a
cada fila:

| Columna | Qué hacer |
|---------|-----------|
| `rol_fiscal` | Solo lectura — asignado por el sistema |
| `cuenta_impuesto` | **Usuario selecciona** la cuenta Tax de su CoA |
| `estado_validacion` | Solo lectura — `Válido` / `Advertencia` / `Error` |
| `integra_base_iva` | Marcar si este IEPS integra la base del IVA (cascada) |

El campo `configuracion_completa` se marca automáticamente como `True`
cuando todos los roles requeridos tienen `estado_validacion = "Válido"`.

**Validaciones automáticas por cuenta:**
- La cuenta debe ser de tipo `Tax`
- La cuenta debe pertenecer a la empresa
- La cuenta no debe estar deshabilitada
- La cuenta debe estar en el Chart of Accounts de la empresa

### 4c — Generar templates (botón UI)

Con `configuracion_completa = True`, el botón **"Generate Templates"** llama
a `aplicar_mapeo_y_generar_templates()` que ejecuta en secuencia:

```
1. generate_8_stct_for_company(company)
   → Crea/actualiza los 8 Sales Taxes and Charges Templates
   → Deshabilita templates consolidados viejos (con porcentajes en nombre)

2. generate_itt_for_company(company)
   → Crea/actualiza los Item Tax Templates según alcance habilitado

3. assign_itt_to_groups(company)
   → Asigna cada ITT al Item Group correspondiente
```

**Templates STCT generados (mínimo 4, máximo 8):**

| Template | Cuándo se crea | Filas |
|----------|----------------|-------|
| `IVA Nacional - Básico - {abbr}` | Siempre | 1 (IVA) |
| `IVA Nacional - IEPS - {abbr}` | Si algún IEPS habilitado | 6 (IVA + IEPS + cascada) |
| `IVA Nacional - Retenciones - {abbr}` | Si alguna retención habilitada | 3 (IVA + ISR Ret + IVA Ret) |
| `IVA Nacional - Total - {abbr}` | Si IEPS + retenciones | 8 (todo) |
| `IVA Frontera - Básico - {abbr}` | Si `enable_frontera` | 1 |
| `IVA Frontera - IEPS - {abbr}` | Si frontera + IEPS | 6 |
| `IVA Frontera - Retenciones - {abbr}` | Si frontera + retenciones | 3 |
| `IVA Frontera - Total - {abbr}` | Si frontera + IEPS + retenciones | 8 |

**Item Tax Templates generados (3 base, hasta 18 con todos los alcances):**

| ITT | Siempre | Condicional |
|-----|:-------:|:-----------:|
| `ITT IVA Nacional (16%) - {abbr}` | ✅ | — |
| `ITT IVA 0% - {abbr}` | ✅ | — |
| `ITT Exento - {abbr}` | ✅ | — |
| `ITT IVA Frontera (8%) - {abbr}` | — | `enable_frontera` |
| `ITT IEPS Alcohol - {abbr}` | — | `enable_ieps_alcohol` |
| `ITT IEPS Azúcar - {abbr}` | — | `enable_ieps_azucar` |
| `ITT IEPS Combustibles - {abbr}` | — | `enable_ieps_combustibles` |
| `ITT IEPS Tabaco - {abbr}` | — | `enable_ieps_tabaco` |
| `ITT ISR Honorarios - {abbr}` | — | `enable_ret_honorarios` |
| `ITT IVA Retenido Honorarios - {abbr}` | — | `enable_ret_honorarios` |
| `ITT ISR + IVA Ret Honorarios - {abbr}` | — | `enable_ret_honorarios` |
| `ITT ISR Arrendamiento - {abbr}` + 2 más | — | `enable_ret_arrendamiento` |
| `ITT ISR Autotransporte - {abbr}` + 2 más | — | `enable_ret_autotransporte` |
| `ITT ISR + IVA Ret RESICO - {abbr}` | — | `enable_ret_resico` |

**Item Groups y asignación automática de ITTs:**

La función `assign_itt_to_groups()` asigna cada ITT al Item Group correspondiente.
Los Item Groups se crean automáticamente si no existen:

| Item Group | ITT asignado |
|------------|--------------|
| `Artículos con IVA al 0%` | `ITT IVA 0% - {abbr}` |
| `Artículos Exentos` | `ITT Exento - {abbr}` |
| `Artículos IEPS Alcohol` | `ITT IEPS Alcohol - {abbr}` |
| `Artículos IEPS Azúcar` | `ITT IEPS Azúcar - {abbr}` |
| `Artículos IEPS Combustibles` | `ITT IEPS Combustibles - {abbr}` |
| `Artículos IEPS Tabaco` | `ITT IEPS Tabaco - {abbr}` |
| `Servicios Profesionales (Honorarios)` | `ITT ISR + IVA Ret Honorarios - {abbr}` |
| `Arrendamiento` | `ITT ISR + IVA Ret Arrendamiento - {abbr}` |
| `Autotransporte` | `ITT ISR + IVA Ret Autotransporte - {abbr}` |
| `RESICO` | `ITT ISR + IVA Ret RESICO - {abbr}` |

Los Items que pertenecen a uno de estos grupos heredan automáticamente
el ITT correcto en la Sales Invoice, sin configuración adicional.

---

## PASO 5 — Branch (opcional, recomendado para multi-sucursal)

**Dónde:** Setup → Branch

| Campo | Obligatorio | Notas |
|-------|-------------|-------|
| `branch` | ✅ | Nombre sucursal |
| `company` | ✅ | Link a Company |
| `fm_enable_fiscal` | ✅ para folios | Activa control multi-sucursal |
| `fm_serie_pattern` | ✅ si fiscal | Ej: `"A{####}"` → serie `"A"` |
| `fm_folio_start/current/end` | ✅ si fiscal | Rango de folios |
| `fm_lugar_expedicion` | — | Override del CP global de Settings |
| `fm_is_border_zone` | — | Si `True` → autoselección usa STCT "Frontera" |

El hook `before_validate` de Sales Invoice lee `Branch.fm_is_border_zone`
para determinar qué STCT asignar automáticamente (Nacional vs Frontera).

---

## PASO 6 — Customer

**Dónde:** CRM → Customer

| Campo | Obligatorio | Notas |
|-------|-------------|-------|
| `customer_name` | ✅ | Nombre legal para el CFDI |
| `tax_id` | ✅ | RFC receptor. Sin esto: `throw("El cliente debe tener RFC")` |
| `email_id` | — | Fallback: `Settings.customer_email_fallback` |
| `fm_regimen_fiscal` | ✅ | Link a Regimen Fiscal SAT. Sin esto: `throw("customer.tax_system_required")` |
| `fm_uso_cfdi_default` | — | Se hereda a Factura Fiscal Mexico |

**Address PRIMARY obligatoria:**

| Campo | Obligatorio | Notas |
|-------|-------------|-------|
| `address_line1` | ✅ | Calle y número |
| `city` | ✅ | Ciudad |
| `state` | ✅ | Estado |
| `country` | ✅ | `"México"` (con acento). Acepta: `MEX`, `MX`, `Mexico` |
| `pincode` | ✅ | Código postal 5 dígitos |

---

## PASO 7 — Items

**Dónde:** Inventory → Item

| Campo | Obligatorio | Notas |
|-------|-------------|-------|
| `item_code` | ✅ | — |
| `item_name` | ✅ | Descripción en CFDI si `description` vacío |
| `stock_uom` | ✅ | Formato SAT: `"H87 - Pieza"`. El sistema extrae `"H87"` |
| `item_group` | — | Si pertenece a grupo fiscal (IEPS, Retenciones), hereda ITT automáticamente |
| `fm_producto_servicio_sat` | ✅ efectivo | Sin esto el hook `validate` lanza `frappe.throw()` al guardar cualquier SI. Default `"01010101"` ya no es fallback silencioso — es error activo |

**Cambio respecto a v1:** En `feature/e4-ieps-on-item-quantity` el campo
`fm_producto_servicio_sat` es **obligatorio efectivo**. El hook `validate`
de Sales Invoice lanza `frappe.throw()` en cada línea sin código SAT.
No hay fallback silencioso.

---

## PASO 8 — Sales Invoice → SUBMIT

**Dónde:** Accounting → Sales Invoice

| Campo | Obligatorio | Notas |
|-------|-------------|-------|
| `company` | ✅ | — |
| `customer` | ✅ | Debe cumplir Paso 6 |
| `cost_center` | ✅ | El hook `validate` lanza `throw` si está vacío |
| `posting_date` | ✅ | — |
| `items` | ✅ ≥1 | Cada ítem debe cumplir Paso 7 |
| `fm_branch` | — | Si se usa multi-sucursal → autoselección STCT |

**Hooks activos en esta branch (en orden de ejecución):**

```
before_validate:
  sales_invoice_automated_tax.before_validate()
    1. Si no hay cost_center → copia Customer.fm_customer_default_cost_center
    2. Con cost_center → deriva Branch (fm_mapped_branch)
    3. Con Branch → _set_stct_by_branch():
         a. Lee Branch.fm_is_border_zone → zona (Nacional/Frontera)
         b. Clasifica items → variante (Básico/IEPS/Retenciones/Total)
         c. Busca STCT: "IVA {zona} - {variante} - {abbr}"
         d. Fallback: "IVA {zona} - Básico - {abbr}"
         e. Si no encuentra ninguno → frappe.throw() ← BLOQUEANTE
         f. Carga tax rows completas desde STCT
    4. Para cada línea sin ITT → intenta asignar desde Item master

validate:
  sales_invoice_automated_tax.validate()
    1. cost_center obligatorio → throw si vacío
    2. Cada línea → Item.fm_producto_servicio_sat obligatorio → throw si vacío
```

**Consecuencia:** Si los STCT no existen para la empresa (no se completó
el Paso 4), el `before_validate` bloqueará el guardado de cualquier SI
que tenga un Branch con `fm_is_border_zone` definido.

---

## PASO 9 — Factura Fiscal Mexico → SUBMIT

**Dónde:** Facturacion Mexico → Factura Fiscal Mexico

| Campo | Obligatorio | Default | Notas |
|-------|-------------|---------|-------|
| `sales_invoice` | ✅ | — | SI submitted, sin otra FFM activa |
| `fm_tipo_comprobante` | ✅ | `I - Ingreso` | Auto-asignado según SI |
| `fm_payment_method_sat` | ✅ | `PUE` | `PUE` o `PPD` |
| `fm_forma_pago_timbrado` | ✅ | — | Link a Mode of Payment SAT |
| `fm_cfdi_use` | ✅ | — | Link a Uso CFDI SAT (G01, S01, etc.) |
| `fm_tipo_relacion_sat` | ✅ si Egreso | — | Solo cuando `tipo = E` |
| `fm_uuid_relacionado` | ✅ si Egreso | — | UUID del CFDI original |

---

## PASO 10 — Timbrar

```python
timbrado_api.timbrar_factura("<nombre_sales_invoice>")
```

O desde el botón "Generar CFDI" en la Sales Invoice.

---

## Tabla de errores por paso omitido

| Paso omitido | Error en | Mensaje |
|--------------|----------|---------|
| Company sin `abbr` | Generar templates | Templates no pueden nombrarse |
| Sin cuentas Tax | Mapeo CFM | `estado_validacion = "Error"`, `configuracion_completa = False` |
| Sin CFM | before_validate SI | `frappe.throw("No se encontró STCT… Generate Templates")` |
| Sin STCT generados | before_validate SI | `frappe.throw("No se encontró STCT mínimo requerido")` |
| `cost_center` vacío en SI | validate SI | `frappe.throw("Centro de Costos es obligatorio")` |
| Item sin `fm_producto_servicio_sat` | validate SI | `frappe.throw("Línea N sin ClaveProdServ SAT")` |
| Customer sin `tax_id` | timbrar_factura | `frappe.throw("El cliente debe tener RFC")` |
| Customer sin Address PRIMARY | timbrar_factura | `Exception: dirección primaria requerida` |
| Customer sin `fm_regimen_fiscal` | timbrar_factura | `Exception: customer.tax_system_required` |
| FFM sin `fm_cfdi_use` | timbrar_factura | `frappe.throw("Uso CFDI requerido")` |
| Settings sin `rfc_emisor` | timbrar_factura | `frappe.throw("Field required")` |
| Settings sin API Key | FacturAPI | `HTTP 401 Unauthorized` |

---

## MVP mínimo para primer timbrado

Lo que se puede omitir para llegar al primer timbrado lo antes posible:

| Paso | MVP | Completo |
|------|:---:|:--------:|
| Company con abbr y RFC | ✅ | ✅ |
| 2 cuentas Tax (IVA Nac + Exento) | ✅ | ✅ |
| FM Settings (sandbox + test_api_key + rfc_emisor + lugar_expedicion) | ✅ | ✅ |
| CFM solo con IVA básico (sin IEPS, sin retenciones) | ✅ | ✅ |
| Generar 4 STCT + 3 ITT mínimos | ✅ | ✅ |
| Branch con fm_is_border_zone definido | ✅ requerido si hay Branch | ✅ |
| Customer RFC + Address + fm_regimen_fiscal | ✅ | ✅ |
| Todos los Items con fm_producto_servicio_sat | ✅ obligatorio | ✅ |
| IEPS / Retenciones / Frontera en CFM | omitir | ✅ |
| Branch con folios/series | omitir | ✅ |

**Secuencia MVP en 7 pasos:**
```
1. Company (tax_id + abbr + MXN)
2. 2 cuentas Tax en CoA
3. FM Settings (test_api_key + rfc_emisor + lugar_expedicion)
4. CFM: company + mapear IVA Nacional → cuenta + IVA Exento → cuenta + Generate
5. Customer (RFC + Address + fm_regimen_fiscal)
6. Items (fm_producto_servicio_sat en TODOS)
7. SI → submit → FFM → submit → timbrar
```
