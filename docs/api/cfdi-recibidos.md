# CFDI Recibidos - API Reference

Documentación de los endpoints para ingesta, clasificación y conversión de CFDIs recibidos (XML de proveedores).

---

## Endpoints disponibles

| Endpoint | Método | Descripción |
|---|---|---|
| `upload_xml` | POST (form-data) | Ingesta uno o varios XMLs CFDI 4.0 |
| `resolve_supplier` | POST | Asigna proveedor por RFC o vinculación manual |
| `classify_concepts` | POST | Aplica reglas de clasificación a los conceptos del CFDI |
| `save_mapping_rule` | POST | Crea o actualiza una regla de CFDI Concepto Mapping |
| `build_purchase_invoice` | POST | Convierte CFDI Recibido Listo a Purchase Invoice Draft |
| `suggest_supplier_from_cfdi` | POST | Sugiere datos de proveedor sin crearlo automáticamente |

Todos los endpoints están bajo:

```
/api/method/facturacion_mexico.cfdi_recibidos.api.<endpoint>
```

---

## `upload_xml`

Carga uno o varios archivos XML CFDI 4.0 y los persiste como documentos **CFDI Recibido**.

### Parámetros (form-data)

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `company` | string | ✅ | Nombre de la empresa en ERPNext |
| `files` | archivo(s) | ✅ | Uno o más archivos XML (campo `files` o `file`) |

### Respuesta

Lista de resultados por archivo:

```json
[
  {
    "file_name": "factura_proveedor.xml",
    "status": "ok",
    "cfdi_recibido": "CFDI-REC-0001",
    "uuid": "6128396f-c09b-4ec6-8699-43855fd7d7a2",
    "message": "CFDI procesado correctamente"
  }
]
```

| Campo | Valores posibles | Descripción |
|---|---|---|
| `status` | `ok` / `duplicado` / `error` | Resultado del procesamiento |
| `cfdi_recibido` | string / null | Nombre del doc creado |
| `uuid` | string / null | UUID extraído del XML |
| `message` | string | Descripción del resultado |

### Comportamiento por estado

- **`ok`** — CFDI procesado y creado en estado `Parseado`. RFC del receptor coincide con `Company.tax_id`.
- **`duplicado`** — Ya existe un CFDI Recibido con ese UUID. No se crea documento nuevo.
- **`error`** — XML inválido, CFDI versión 3.3, o RFC receptor no corresponde a la empresa. El documento se crea en estado `Error` con `error_message`.

### Validaciones internas

1. Calcula SHA256 del XML para detectar archivos idénticos
2. Parsea el XML (solo CFDI 4.0 — rechaza versión 3.3)
3. Detecta duplicados por UUID antes de insertar
4. Valida que `receiver_rfc` del XML coincida con `Company.tax_id`
5. Persiste conceptos como filas child en `CFDI Recibido Concepto`
6. Adjunta el XML original como archivo privado al documento

---

## `resolve_supplier`

Asigna el proveedor al CFDI Recibido. Busca automáticamente por RFC o acepta vinculación manual.

### Parámetros

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `cfdi_recibido` | string | ✅ | Nombre del CFDI Recibido |
| `supplier` | string | ❌ | Supplier específico (vinculación manual) |

### Respuesta

```json
{
  "status": "ok",
  "supplier": "Proveedor Ejemplo S.A.",
  "message": "Proveedor asignado por RFC"
}
```

| `status` | Descripción |
|---|---|
| `ok` | Proveedor asignado correctamente |
| `falta_proveedor` | No existe `Supplier` con `tax_id` igual al RFC del CFDI |
| `error` | Error interno (CFDI sin RFC emisor, Supplier inexistente, etc.) |

### Modos de operación

**Automático** (sin `supplier`): busca `Supplier` donde `tax_id == cfdi_recibido.supplier_rfc`. No autocrea proveedores.

**Manual** (con `supplier`): asigna el Supplier indicado directamente, aunque el RFC no coincida. Útil para CFDIs de proveedores sin `tax_id` configurado en ERPNext.

### Efecto en el estado del CFDI

- Si se asigna proveedor: estado avanza a `Parseado` (listo para clasificar conceptos).
- Si no se encuentra: estado queda en `Falta proveedor`.

---

## `classify_concepts`

Aplica las reglas de **CFDI Concepto Mapping** sobre todos los conceptos del CFDI y actualiza su estado.

### Parámetros

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `cfdi_recibido` | string | ✅ | Nombre del CFDI Recibido |

### Respuesta

```json
{
  "status": "ok",
  "total": 3,
  "matched": 3,
  "unmatched": 0,
  "message": "Todos los conceptos clasificados"
}
```

| `status` | Descripción |
|---|---|
| `ok` | Todos los conceptos tienen regla aplicable → CFDI pasa a `Listo` |
| `falta_clasif` | Al menos un concepto sin regla → CFDI pasa a `Falta clasif.` |

### Algoritmo de matching (3 niveles)

Para cada concepto, busca en `CFDI Concepto Mapping` en orden de especificidad decreciente:

| Nivel | Condiciones | Descripción |
|---|---|---|
| 1 | `company` + `supplier_rfc` + `sat_product_key` | Exacto — empresa + proveedor + clave SAT |
| 2 | `company` + `supplier_rfc` + `sat_product_key` vacío | Fallback por proveedor — cualquier clave SAT |
| 3 | `company` + `supplier_rfc` vacío + `sat_product_key` | Fallback por clave SAT — cualquier proveedor |

Las reglas con `company` vacío son **globales** y aplican a cualquier empresa.
Solo se consideran reglas con `is_active = 1`.

---

## `save_mapping_rule`

Crea o actualiza una regla en **CFDI Concepto Mapping**. Si ya existe una regla con la misma combinación `(company, supplier_rfc, sat_product_key)`, la actualiza. Si no, crea una nueva.

### Parámetros

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `target_type` | string | ✅ | `"Item"` o `"ExpenseAccount"` |
| `supplier_rfc` | string | ❌ | RFC del proveedor (vacío = cualquier proveedor) |
| `sat_product_key` | string | ❌ | Clave SAT del producto/servicio (vacío = cualquier clave) |
| `target_item` | string | ❌ | Nombre del Item en ERPNext (requerido si `target_type = "Item"`) |
| `target_account` | string | ❌ | Nombre de la cuenta de gasto (requerido si `target_type = "ExpenseAccount"`) |
| `target_cost_center` | string | ❌ | Centro de costo (opcional) |
| `company` | string | ❌ | Empresa (vacío = regla global) |

### Respuesta

```json
{
  "status": "ok",
  "mapping": "CFDI-MAP-0001",
  "message": "Regla creada: CFDI-MAP-0001"
}
```

### Ejemplos

**Regla exacta para un proveedor específico:**
```json
{
  "target_type": "ExpenseAccount",
  "supplier_rfc": "PROV901011AAA",
  "sat_product_key": "43231500",
  "target_account": "Gastos de Tecnología - MX",
  "company": "Mi Empresa S.A. de C.V."
}
```

**Regla global para toda la empresa (cualquier proveedor, cualquier clave SAT):**
```json
{
  "target_type": "ExpenseAccount",
  "supplier_rfc": "",
  "sat_product_key": "",
  "target_account": "Gastos Generales - MX",
  "company": "Mi Empresa S.A. de C.V."
}
```

---

## `build_purchase_invoice`

Convierte un **CFDI Recibido** en estado `Listo` a una **Purchase Invoice Draft** de ERPNext.

### Parámetros

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `cfdi_recibido` | string | ✅ | Nombre del CFDI Recibido |

### Respuesta

```json
{
  "status": "ok",
  "purchase_invoice": "ACC-PINV-2024-00001",
  "recovered": false,
  "message": "Purchase Invoice ACC-PINV-2024-00001 creada correctamente"
}
```

| `status` | `recovered` | Descripción |
|---|---|---|
| `ok` | `false` | PI creada por primera vez |
| `recovered` | `true` | UUID ya tenía PI vinculada — se reparó el vínculo |
| `error` | `false` | Error de configuración o datos — PI no creada |

### Comportamiento

- Solo permite conversión si el CFDI está en estado `Listo`, `Error conversión` o `Convertido a PI`.
- Al crear la PI exitosamente, el CFDI pasa a estado `Convertido a PI`.
- En caso de error, el CFDI pasa a `Error conversión` y se guarda el detalle en `error_message`.
- **Idempotente por UUID**: si ya existe una `Purchase Invoice` con el mismo `fm_cfdi_uuid`, retorna `recovered=True` sin crear duplicados.
- La PI se crea como **Draft** (`docstatus=0`). No se hace submit automáticamente.

### Configuración requerida

Para que la conversión funcione, deben existir:

1. **Configuracion CFDI Recibidos** para la empresa (nombre: `CFDI-REC-CFG-{empresa}`) — con reglas de impuesto configuradas y `wizard_completado=True`.
2. **CFDI Concepto Mapping** activo para cada concepto del CFDI — con cuenta de gasto o Item destino.
3. El `supplier` del CFDI debe estar asignado (usar `resolve_supplier` antes si es necesario).

### Flujo de impuestos

Los impuestos del XML se resuelven vía `TaxResolver`:

- **Traslados IVA 16% / 8% / 0%** → `charge_type=Actual`, `add_deduct_tax=Add`
- **Traslados IEPS** → `charge_type=Actual`, `add_deduct_tax=Add`
- **Retenciones ISR/IVA** → `charge_type=Actual`, `add_deduct_tax=Deduct`, importe negativo en la PI

!!! warning "Tolerancia de cuadre"
    Se valida que `grand_total` calculado no difiera del `total` del XML en más de **0.02 MXN**.
    Si difiere más, se lanza error y el CFDI queda en `Error conversión`.

---

## `suggest_supplier_from_cfdi`

Busca si existe un `Supplier` en ERPNext con `tax_id` igual al RFC del CFDI y retorna sugerencia
de datos para alta manual. **Nunca crea proveedores automáticamente.**

### Parámetros

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `cfdi_recibido` | string | ✅ | Nombre del CFDI Recibido |

### Respuesta — Proveedor encontrado

```json
{
  "status": "found",
  "supplier_exists": true,
  "supplier": "Proveedor Ejemplo S.A.",
  "message": "Proveedor encontrado: Proveedor Ejemplo S.A. (PROV901011AAA)",
  "suggested_data": {
    "supplier_name": "Proveedor Ejemplo S.A.",
    "tax_id": "PROV901011AAA"
  }
}
```

### Respuesta — Proveedor no encontrado

```json
{
  "status": "not_found",
  "supplier_exists": false,
  "supplier": null,
  "message": "No existe Supplier con RFC PROV901011AAA",
  "suggested_data": {
    "supplier_name": "Nombre del Proveedor según XML",
    "tax_id": "PROV901011AAA",
    "tax_regime": "601"
  }
}
```

### Respuesta — CFDI sin RFC

```json
{
  "status": "no_rfc",
  "supplier_exists": false,
  "supplier": null,
  "message": "El CFDI no tiene RFC de proveedor",
  "suggested_data": {}
}
```

| `status` | Descripción |
|---|---|
| `found` | Existe `Supplier` con `tax_id == supplier_rfc` del CFDI |
| `not_found` | No existe; `suggested_data` contiene datos para alta asistida |
| `no_rfc` | El CFDI no tiene RFC de proveedor |

!!! info "Alta asistida"
    Use `suggested_data` para pre-poblar el formulario de alta de proveedor.
    Una vez creado el `Supplier`, use `resolve_supplier` para vincularlo al CFDI.

---

## DocTypes relacionados

### CFDI Recibido

Documento principal que representa un CFDI recibido de un proveedor.

| Campo | Descripción |
|---|---|
| `uuid` | UUID único del CFDI (clave de deduplicación) |
| `company` | Empresa receptora |
| `supplier_rfc` | RFC del emisor (proveedor) |
| `supplier` | Link al `Supplier` en ERPNext (asignado por `resolve_supplier`) |
| `status` | `Parseado` / `Falta proveedor` / `Falta clasif.` / `Listo` / `Error` |
| `cfdi_type` | Tipo de comprobante: `I` (Ingreso), `E` (Egreso), `P` (Pago), etc. |
| `xml_file` | URL del XML original adjunto (privado) |
| `xml_hash` | SHA256 del XML para detección de duplicados |
| `conceptos` | Child table — filas `CFDI Recibido Concepto` |

### CFDI Recibido Concepto

Fila child del CFDI Recibido. Representa una línea del XML.

| Campo | Descripción |
|---|---|
| `sat_product_key` | Clave SAT del producto/servicio |
| `description` | Descripción del concepto |
| `quantity` | Cantidad |
| `unit_price` | Precio unitario |
| `amount` | Importe total |
| `taxes_json` | Impuestos del concepto en JSON |

### CFDI Concepto Mapping

Reglas de clasificación para mapear conceptos de CFDIs recibidos a Items o cuentas de gasto.

| Campo | Descripción |
|---|---|
| `company` | Empresa a la que aplica (vacío = global) |
| `supplier_rfc` | RFC del proveedor (vacío = cualquier proveedor) |
| `sat_product_key` | Clave SAT (vacío = cualquier clave) |
| `target_type` | `Item` o `ExpenseAccount` |
| `target_item` | Item de ERPNext destino |
| `target_account` | Cuenta de gasto destino |
| `target_cost_center` | Centro de costo (opcional) |
| `is_active` | Activa / inactiva (solo reglas activas aplican en el matching) |

!!! warning "Unicidad de reglas"
    No puede existir más de una regla activa con la misma combinación `(company, supplier_rfc, sat_product_key)`.
    El DocType valida esto en `validate()` y la API lo maneja como upsert.
