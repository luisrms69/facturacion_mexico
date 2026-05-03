# MÓDULO 5 — WORKFLOW DE CONFIGURACIÓN INICIAL
===============================================
Fecha: 2026-05-01
Fuente: Análisis de código — hooks.py, install.py, timbrado_api.py,
        factura_fiscal_mexico.py, branch_fiscal_fields.py

---

## TL;DR

El orden correcto es:

```
Settings (global) → Company → [Branch] → Customer + Address → Items → Sales Invoice → Factura Fiscal Mexico → TIMBRAR
```

Ningún paso puede saltarse. Cada nivel tiene prereqs del nivel anterior.

---

## PASO 1 — Company

**Dónde:** Setup → Company → Nuevo

| Campo | Obligatorio | Notas |
|-------|-------------|-------|
| `company_name` | ✅ | Nombre legal |
| `tax_id` | ✅ | RFC empresa (12-13 chars) |
| `default_currency` | ✅ | Debe ser `MXN` |
| `country` | ✅ | `México` |

**Qué rompe si falta:**
- Sin `tax_id`: FacturAPI rechazará la emisión (RFC emisor inválido)
- Sin `MXN`: cálculos fiscales incorrectos

---

## PASO 2 — Facturacion Mexico Settings

**Dónde:** Facturacion Mexico → Facturacion Mexico Settings (Single DocType)

| Campo | Obligatorio | Default | Notas |
|-------|-------------|---------|-------|
| `sandbox_mode` | ✅ | `1` | Activar para pruebas — usa `test_api_key` |
| `test_api_key` | ✅ si sandbox | — | API Key FacturAPI sandbox |
| `api_key` | ✅ si producción | `NULL` | API Key FacturAPI producción |
| `rfc_emisor` | ✅ | `NULL` | RFC de la empresa emisora |
| `lugar_expedicion` | ✅ | `NULL` | Código postal del domicilio fiscal |
| `regimen_fiscal_default` | — | `NULL` | Fallback si Customer no tiene régimen |
| `metodo_pago_default` | ✅ | `PUE` | `PUE` o `PPD` |
| `customer_email_fallback` | ✅ | valor demo | Email si cliente no tiene email |
| `timeout` | ✅ | `30` | Segundos timeout al PAC |

**Qué rompe si falta:**
- Sin `rfc_emisor` → `frappe.throw("Field required")` al construir payload
- Sin `lugar_expedicion` → XML CFDI inválido ante el SAT
- Sin API Key → `FacturAPI 401 Unauthorized`
- Sin API Key y sandbox_mode=0 → intenta producción con key nula → 401

---

## PASO 3 — Branch / Sucursal (opcional, recomendado para multi-folio)

**Dónde:** Setup → Branch → Nuevo

| Campo | Obligatorio | Default | Notas |
|-------|-------------|---------|-------|
| `branch` | ✅ | — | Nombre sucursal |
| `company` | ✅ | — | Link a Company |
| `fm_enable_fiscal` | ✅ para folios | `0` | Activar control fiscal |
| `fm_serie_pattern` | ✅ si fiscal | — | Ej: `"A{####}"` → extrae serie `"A"` |
| `fm_folio_start` | ✅ si fiscal | — | Folio inicial del rango |
| `fm_folio_current` | ✅ si fiscal | — | Folio actual (se incrementa por timbrado) |
| `fm_folio_end` | ✅ si fiscal | — | Folio final (alerta si se acerca) |
| `fm_lugar_expedicion` | — | — | Override del lugar_expedicion global |

**Al guardar con `fm_enable_fiscal=1`:** el sistema crea automáticamente
un doc `Configuracion Fiscal Sucursal` vinculado a esta Branch.

**Qué rompe si falta:**
- Sin Branch: las Sales Invoices no tendrán serie/folio asignados (se usa el global de FacturAPI)
- `fm_serie_pattern` mal formado: la extracción de serie falla silenciosamente → folio sin serie

---

## PASO 4 — Customer

**Dónde:** CRM → Customer → Nuevo

### Campos estándar obligatorios para timbrado

| Campo | Obligatorio | Notas |
|-------|-------------|-------|
| `customer_name` | ✅ | Nombre legal tal como va en el CFDI |
| `tax_id` | ✅ | RFC del receptor (12-13 chars). Sin esto: `throw("El cliente debe tener RFC")` |
| `email_id` | — | Si falta, usa `Settings.customer_email_fallback` |

### Address PRIMARIA obligatoria

Debe existir al menos un Address vinculado al Customer marcado como primario:

| Campo Address | Obligatorio | Notas |
|---------------|-------------|-------|
| `address_line1` | ✅ | Calle y número → campo `street` en FacturAPI |
| `city` | ✅ | Ciudad |
| `state` | ✅ | Estado |
| `country` | ✅ | Debe ser `"México"` (con acento). Acepta también `MEX`, `MX`, `Mexico` |
| `pincode` | ✅ | Código postal 5 dígitos |

**Qué rompe si falta:**
- Sin Address primaria → `Exception: customer.address_required: El cliente no tiene dirección primaria`
- Country inválido → `ValidationError: País 'X' no es reconocido. Use: México, MEX, MX`

### Custom fields fiscales

| Campo | Obligatorio | Notas |
|-------|-------------|-------|
| `fm_regimen_fiscal` | ✅ | Link a Regimen Fiscal SAT. Códigos comunes: `601` (PF sin actividad), `603` (PF con actividad), `701` (PM general). Si falta → `Exception: customer.tax_system_required` |
| `fm_uso_cfdi_default` | — | Uso CFDI por defecto. Se hereda a Factura Fiscal Mexico |
| `fm_rfc_validated` | — | Flag de validación contra SAT. No bloquea timbrado si es `0` |
| `fm_lista_69b_status` | — | Estado en lista negra SAT. Informativo |

---

## PASO 5 — Items

**Dónde:** Inventory → Item → Nuevo

| Campo | Obligatorio | Notas |
|-------|-------------|-------|
| `item_code` | ✅ | — |
| `item_name` | ✅ | Va como descripción en el CFDI si `description` está vacío |
| `stock_uom` | ✅ | Debe tener formato SAT: `"H87 - Pieza"`. El sistema extrae `"H87"` del prefijo |
| `fm_producto_servicio_sat` | — | Clave SAT 6-8 dígitos. **Si falta usa default `"01010101"`** (Servicios generales). No bloquea — pero el SAT puede rechazar la clave si no corresponde al producto |

**Formato UOM SAT obligatorio:** `"CODIGO - Descripción"` → ej: `"H87 - Pieza"`, `"KGM - Kilogramo"`, `"LTR - Litro"`

El parser `_extract_sat_code_from_uom()` toma todo lo que esté antes del ` - `. Si la UOM no tiene ese formato, intenta un mapeo interno; si falla, usa `"H87"` como fallback.

**Qué rompe si falta:**
- UOM sin formato SAT: el código de unidad puede ser incorrecto en el XML → rechazo SAT
- Sin `fm_producto_servicio_sat`: se timbra con `"01010101"` (válido pero genérico)

---

## PASO 6 — Sales Invoice

**Dónde:** Accounting → Sales Invoice → Nuevo

| Campo | Obligatorio | Notas |
|-------|-------------|-------|
| `company` | ✅ | — |
| `customer` | ✅ | Debe cumplir el Paso 4 completo |
| `posting_date` | ✅ | Fecha de la factura |
| `items` | ✅ ≥1 | Cada ítem debe cumplir el Paso 5 |
| `fm_branch` | — | Si se usa multi-sucursal. Debe cumplir el Paso 3 |

**Luego de llenar → SUBMIT (docstatus=1)**

El sistema valida en el hook `on_submit` de Sales Invoice:
- Si el Customer requiere addenda (`fm_requires_addenda=1`) verifica que esté configurada
- Actualiza `fm_fiscal_status = "BORRADOR"` en la SI

**Qué rompe si falta:**
- SI en Draft (docstatus=0) → `ValidationError: Sales Invoice debe estar en estado Enviada`

---

## PASO 7 — Factura Fiscal Mexico

**Dónde:** Facturacion Mexico → Factura Fiscal Mexico → Nuevo  
(o desde el botón en Sales Invoice)

| Campo | Obligatorio | Default | Notas |
|-------|-------------|---------|-------|
| `sales_invoice` | ✅ | — | Link a SI submitted. Valida que no tenga otra FFM activa |
| `customer` | ✅ | auto-fetch | — |
| `company` | ✅ | auto-fetch | — |
| `fm_tipo_comprobante` | ✅ | `I - Ingreso` | Auto-asignado: SI normal → `I`, SI devolución → `E` |
| `fm_payment_method_sat` | ✅ | `PUE` | `PUE` = pago único, `PPD` = diferido |
| `fm_forma_pago_timbrado` | ✅ | — | Link a Mode of Payment. Ej: `"01 - Efectivo"`. Si PPD, debe ser `"99 - Por definir"` |
| `fm_cfdi_use` | ✅ | — | Link a Uso CFDI SAT. Ej: `G01`, `S01`, `D04` |
| `fm_tipo_relacion_sat` | ✅ si Egreso | — | Obligatorio cuando `tipo = E` |
| `fm_uuid_relacionado` | ✅ si Egreso | — | UUID del CFDI original (36 chars) |

**Validaciones en `validate()` antes del submit:**

1. `validate_tipo_comprobante()` — tipo vs is_return de la SI
2. `validate_payment_method()` — PUE o PPD
3. `validate_ppd_vs_forma_pago()` — PPD exige forma `99`
4. `validate_cfdi_use()` — fm_cfdi_use no puede estar vacío
5. `validate_sales_invoice()` — SI submitted + sin FFM activa duplicada
6. `validate_no_duplicate_timbrado()` — previene doble timbrado

**Luego de llenar → SUBMIT (docstatus=1)**

La FFM queda en `fm_fiscal_status = "BORRADOR"` y lista para timbrar.

---

## PASO 8 — Timbrar

**Cómo:** Botón "Generar CFDI" en Sales Invoice, o directamente:
```python
timbrado_api.timbrar_factura("<nombre_sales_invoice>")
```

**Fases internas:**

```
FASE 1 — Validación pre-timbrado
  _validate_invoice_for_timbrado(si)
    ├─ Customer.tax_id existe
    ├─ Address primaria existe
    ├─ Country válido (MEX/MX/México)
    ├─ fm_regimen_fiscal resuelto
    └─ FFM en docstatus=1

FASE 2 — Construcción del payload
  _prepare_facturapi_data(si, ffm)
    ├─ RFC emisor (Settings.rfc_emisor)
    ├─ RFC receptor (Customer.tax_id)
    ├─ Dirección receptor (Address)
    ├─ Régimen fiscal (Customer.fm_regimen_fiscal)
    ├─ Uso CFDI (FFM.fm_cfdi_use)
    ├─ Forma de pago (FFM.fm_forma_pago_timbrado → código SAT)
    ├─ Método de pago (FFM.fm_payment_method_sat)
    ├─ Lugar expedición (Branch.fm_lugar_expedicion o Settings.lugar_expedicion)
    ├─ Serie (Branch.fm_serie_pattern → extrae prefijo)
    └─ Items: por cada línea →
         product_key = Item.fm_producto_servicio_sat || "01010101"
         unit_key    = UOM.name.split(" - ")[0]
         description = item.description || item.item_name
         quantity, unit_price, taxes

FASE 3 — Llamada a FacturAPI
  POST https://www.facturapi.io/v2/invoices
  Bearer: Settings.test_api_key (sandbox) | Settings.api_key (producción)

FASE 4 — Procesamiento de respuesta
  _process_timbrado_success(si, ffm, response)
    ├─ FFM.fm_uuid        = response["uuid"]
    ├─ FFM.facturapi_id   = response["id"]
    ├─ FFM.serie          = response["series"]
    ├─ FFM.folio          = response["folio_number"]
    ├─ FFM.total_fiscal   = response["total"]
    ├─ FFM.fecha_timbrado = now()
    ├─ FFM.fm_fiscal_status = "TIMBRADO"
    ├─ SI.fm_fiscal_status  = "TIMBRADO"
    ├─ SI.fm_factura_fiscal_mx = ffm.name
    ├─ SI.fm_uuid_fiscal  = response["uuid"]
    ├─ Descargar PDF y XML (si Settings.download_files_default=1)
    ├─ Enviar email (si Settings.send_email_default=1)
    └─ Branch.fm_folio_current += 1 (si hay Branch)
```

---

## Estados fiscales

```
BORRADOR ──submit──► PROCESANDO ──éxito──► TIMBRADO ──cancela──► PENDIENTE_CANCELACION ──SAT confirma──► CANCELADO
                         │
                       error
                         │
                         ▼
                        ERROR ──fix + reintento──► PROCESANDO
```

---

## Tabla de errores comunes

| Error | Causa raíz | Fix |
|-------|-----------|-----|
| `El cliente debe tener RFC` | `Customer.tax_id` vacío | Llenar RFC en Customer |
| `dirección primaria requerida` | Sin Address PRIMARY | Crear Address con todos los campos |
| `País 'X' no reconocido` | `Address.country` ≠ MEX | Cambiar a `México` (con acento) |
| `Tax system requerido` | `Customer.fm_regimen_fiscal` vacío | Link a Regimen Fiscal SAT |
| `Uso CFDI requerido` | `FFM.fm_cfdi_use` vacío | Llenar en Factura Fiscal Mexico |
| `Forma de pago requerida` | `FFM.fm_forma_pago_timbrado` vacío | Link a Mode of Payment SAT |
| `PPD requiere forma 99` | PPD con forma ≠ `99` | Cambiar forma a `99 - Por definir` |
| `SI debe estar submitted` | `SI.docstatus = 0` | Submit la Sales Invoice |
| `FFM debe estar submitted` | `FFM.docstatus = 0` | Submit la Factura Fiscal Mexico |
| `Ya existe FFM activa` | FFM duplicada para misma SI | Cancelar la FFM anterior |
| `UUID relacionado obligatorio` | Egreso sin UUID | Llenar `fm_uuid_relacionado` |
| `FacturAPI 401 Unauthorized` | API Key inválida/vencida | Actualizar API Key en Settings |
| `FacturAPI 400 Invalid tax ID` | RFC formato incorrecto | Verificar RFC en Customer |
| `Timeout` | PAC lento o sin internet | Aumentar `Settings.timeout` y reintentar |

---

## Checklist pre-primer-timbrado

```
☐ PASO 1  Company con tax_id (RFC) y currency=MXN
☐ PASO 2  Facturacion Mexico Settings
          ☐ sandbox_mode = 1
          ☐ test_api_key configurada
          ☐ rfc_emisor = RFC empresa
          ☐ lugar_expedicion = CP domicilio fiscal
☐ PASO 3  Branch (si multi-sucursal)
          ☐ fm_enable_fiscal = 1
          ☐ fm_serie_pattern, fm_folio_start/current/end
☐ PASO 4  Customer
          ☐ tax_id (RFC receptor)
          ☐ Address PRIMARY completa (calle, ciudad, estado, país, CP)
          ☐ fm_regimen_fiscal → Link a Regimen Fiscal SAT
☐ PASO 5  Items
          ☐ stock_uom en formato "COD - Descripción"
          ☐ fm_producto_servicio_sat (o aceptar default 01010101)
☐ PASO 6  Sales Invoice → SUBMITTED
☐ PASO 7  Factura Fiscal Mexico → SUBMITTED
          ☐ fm_payment_method_sat = PUE
          ☐ fm_forma_pago_timbrado = "01 - Efectivo" (u otro)
          ☐ fm_cfdi_use = G01 (u otro)
☐ PASO 8  Botón Timbrar / timbrar_factura()
```
