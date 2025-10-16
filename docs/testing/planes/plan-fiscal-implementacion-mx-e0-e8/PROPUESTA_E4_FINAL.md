# Propuesta E4 Final - Puente Sales Invoice → PAC (Read-Only)

**Fecha:** 2025-10-08
**Autor:** Claude Code
**Versión:** Final alineada con instrucciones

---

## 🎯 Principio Fundamental

**Sales Invoice es la fuente única de verdad.**

- ✅ Solo **leer y pasar** valores desde SI
- ❌ **Zero cálculos** (SI ya los hizo en E1)
- ❌ **Zero campos nuevos**
- ✅ Usar **catálogo interno** existente (SAT Producto Servicio)

---

## 📊 Fuentes de Datos

### 1. Sales Invoice (SI)

**Encabezado:**
- Cliente: RFC (`customer.tax_id`), régimen (`customer.fm_tax_regime`), uso CFDI
- Serie/folio, moneda, TC
- Forma de pago, método de pago
- Totales: `total`, `net_total`, `total_taxes_and_charges`, `grand_total`

**Items (por renglón):**
```python
{
    "item_code": str,
    "description": str,
    "qty": float,
    "rate": float,
    "amount": float,
    "item_tax_template": str,
    "item_tax_rate": str  # JSON: {"account_head": rate, ...}
}
```

**Taxes (consolidados):**
```python
{
    "account_head": str,
    "rate": float,
    "tax_amount": float,
    "item_wise_tax_detail": str  # JSON: {"item_code": [rate, amount]}
}
```

### 2. Item (campos SAT E0)

```python
{
    "fm_producto_servicio_sat": str,  # ClaveProdServ: "78101802"
    "fm_unidad_sat": str              # ClaveUnidad: "E48"
}
```

### 3. SAT Producto Servicio (catálogo interno)

**DocType existente en el app:**
```python
{
    "codigo": str,                      # "78101802"
    "descripcion": str,
    "incluye_objeto_impuesto": str      # "01", "02", "03", "04"
}
```

**Lookup:** `Item.fm_producto_servicio_sat` → `SAT Producto Servicio.codigo` → `incluye_objeto_impuesto`

### 4. Configuración Fiscal México (mapeo cuentas)

**Tabla child existente:** `mapeos_cuentas_fiscales`

```python
{
    "cuenta_impuesto": str,        # Account: "123456 - iva 16% - _TC"
    "impuesto_sat": str,           # Código: "002" (IVA)
    "tipo_factor": str,            # "Tasa", "Cuota", "Exento"
    "nombre_impuesto_sat": str     # "IVA", "ISR", "IEPS"
}
```

---

## 🔧 Implementación E4-RO

### E4-RO.1 - Leer Impuestos desde SI (passthrough)

**Función:** `_read_taxes_from_sales_invoice_item(item, sales_invoice)`

```python
def _read_taxes_from_sales_invoice_item(self, item, sales_invoice):
    """
    Leer impuestos de un item desde Sales Invoice.

    E4-RO: Solo lectura, sin cálculos.

    Fuente: item.item_tax_rate (JSON)

    Returns:
        List[dict]: [
            {
                "account_head": str,
                "rate": float,
                "amount": float,
                "withholding": bool
            }
        ]
    """
    import json

    if not item.item_tax_rate:
        return []

    # item.item_tax_rate = '{"account_head": rate, ...}'
    item_tax_rate = json.loads(item.item_tax_rate)

    taxes_data = []
    for account_head, rate in item_tax_rate.items():
        # Buscar amount desde SI.taxes[].item_wise_tax_detail
        amount = self._get_tax_amount_for_item(sales_invoice, account_head, item.item_code)

        taxes_data.append({
            "account_head": account_head,
            "rate": rate,
            "amount": amount,
            "withholding": rate < 0  # Rate negativo = retención
        })

    return taxes_data


def _get_tax_amount_for_item(self, sales_invoice, account_head, item_code):
    """
    Extraer amount desde SI.taxes[].item_wise_tax_detail.

    item_wise_tax_detail = '{"item_code": [rate, amount]}'
    """
    import json

    for tax in sales_invoice.taxes:
        if tax.account_head != account_head:
            continue

        if not tax.item_wise_tax_detail:
            return 0.0

        item_wise = json.loads(tax.item_wise_tax_detail)

        if item_code in item_wise:
            # item_wise[item_code] = [rate, amount]
            return float(item_wise[item_code][1])  # Posición 1 = amount

    return 0.0
```

---

### E4-RO.2 - Resolver ObjetoImp (lookup catálogo)

**Función:** `_resolve_objeto_impuesto(item_doc)`

```python
def _resolve_objeto_impuesto(self, item_doc):
    """
    Resolver ObjetoImp desde catálogo SAT Producto Servicio.

    E4-RO: Solo lookup, sin inferencias.

    Pipeline:
    1. Leer Item.fm_producto_servicio_sat (ClaveProdServ)
    2. Lookup SAT Producto Servicio.incluye_objeto_impuesto
    3. Retornar "01", "02", "03", o "04"

    Returns:
        str: ObjetoImp ("02" default si no encontrado)
    """
    clave_prod_serv = item_doc.get("fm_producto_servicio_sat")

    if not clave_prod_serv:
        frappe.logger().warning(
            f"Item {item_doc.name} sin fm_producto_servicio_sat, usando ObjetoImp '02' default"
        )
        return "02"

    # Lookup en catálogo interno
    sat_producto = frappe.db.get_value(
        "SAT Producto Servicio",
        clave_prod_serv,
        "incluye_objeto_impuesto"
    )

    if not sat_producto:
        frappe.logger().warning(
            f"ClaveProdServ {clave_prod_serv} no encontrado en catálogo SAT, "
            f"usando ObjetoImp '02' default"
        )
        return "02"

    return sat_producto
```

---

### E4-RO.3 - Mapear Account → SAT (configuración existente)

**Función:** `_map_tax_account_to_sat(account_head)`

```python
def _map_tax_account_to_sat(self, account_head):
    """
    Mapear cuenta ERPNext → metadata SAT.

    E4-RO: Usa configuración existente, sin parsear nombres.

    Fuente: Configuración Fiscal México → mapeos_cuentas_fiscales

    Returns:
        {
            "impuesto_sat": str,      # "002"
            "tipo_factor": str,       # "Tasa"
            "nombre_sat": str         # "IVA"
        }
    """
    config = frappe.get_single("Configuracion Fiscal Mexico")

    for mapeo in config.mapeos_cuentas_fiscales:
        if mapeo.cuenta_impuesto == account_head:
            return {
                "impuesto_sat": mapeo.impuesto_sat,
                "tipo_factor": mapeo.tipo_factor,
                "nombre_sat": mapeo.nombre_impuesto_sat
            }

    # Cuenta no mapeada = error (datos incompletos)
    frappe.throw(
        f"Cuenta '{account_head}' no tiene mapeo SAT configurado.\n\n"
        f"Configure en: Configuración Fiscal México → Mapeos Cuentas Fiscales",
        title="Mapeo SAT Faltante"
    )
```

---

### E4-RO.4 - Construir Payload (serialización 1:1)

**Modificar:** `timbrado_api.py:_prepare_facturapi_data()` líneas 475-491

```python
# Items de la factura
items = []
for item in sales_invoice.items:
    item_doc = frappe.get_doc("Item", item.item_code)

    # E4-RO.1: Leer taxes desde SI (NO calcular)
    item_taxes_data = self._read_taxes_from_sales_invoice_item(item, sales_invoice)

    # E4-RO.2: Resolver ObjetoImp desde catálogo SAT
    objeto_imp = self._resolve_objeto_impuesto(item_doc)

    # E4-RO.3: Mapear taxes a estructura FacturAPI
    taxes_payload = []
    for tax_data in item_taxes_data:
        sat_mapping = self._map_tax_account_to_sat(tax_data["account_head"])

        taxes_payload.append({
            "type": sat_mapping["nombre_sat"],           # "IVA", "ISR", "IEPS"
            "factor": sat_mapping["tipo_factor"],        # "Tasa"
            "rate": abs(tax_data["rate"]) / 100,         # 16.0 → 0.16
            "withholding": tax_data["withholding"]       # True/False
        })

    # Construir concepto
    item_payload = {
        "quantity": item.qty,
        "product": {
            "description": item.description or item.item_name,
            "product_key": item_doc.fm_producto_servicio_sat or "01010101",
            "price": flt(item.rate),
            "tax_included": False,
            "unit_key": _extract_sat_code_from_uom(item.uom),
            "unit_name": item.uom or "Pieza",
            "tax_object": objeto_imp,  # E4-RO.2
        },
    }

    # Solo agregar taxes[] si ObjetoImp = "02"
    if objeto_imp == "02" and taxes_payload:
        item_payload["product"]["taxes"] = taxes_payload

    items.append(item_payload)
```

---

### E4-RO.5 - Validación Completitud (sin aritmética)

**Función:** `_validate_payload_completeness_ro(invoice_data, sales_invoice)`

```python
def _validate_payload_completeness_ro(self, invoice_data, sales_invoice):
    """
    Validar completitud payload E4-RO.

    Solo cotejo estructura, sin cálculos.
    """
    errors = []

    # === DATOS CLIENTE ===
    customer_data = invoice_data.get("customer", {})
    required_fields = ["legal_name", "tax_id", "tax_system"]

    for field in required_fields:
        if not customer_data.get(field):
            errors.append(f"❌ customer.{field} faltante")

    # === ITEMS Y CONCEPTOS ===
    items = invoice_data.get("items", [])

    if not items:
        errors.append("❌ items[] vacío")

    for idx, item_payload in enumerate(items, 1):
        product = item_payload.get("product", {})
        si_item = sales_invoice.items[idx - 1]

        # Campos obligatorios concepto
        required_product = ["product_key", "unit_key", "description", "tax_object"]
        for field in required_product:
            if not product.get(field):
                errors.append(f"❌ Item {idx}: product.{field} faltante")

        # Coherencia ObjetoImp vs taxes[]
        objeto_imp = product.get("tax_object")
        taxes_payload = product.get("taxes", [])

        if objeto_imp == "02" and not taxes_payload:
            errors.append(
                f"❌ Item {idx} ({si_item.item_code}): "
                f"ObjetoImp '02' requiere taxes[], pero está vacío"
            )

        if objeto_imp in ["01", "03", "04"] and taxes_payload:
            errors.append(
                f"⚠️ Item {idx} ({si_item.item_code}): "
                f"ObjetoImp '{objeto_imp}' NO debe tener taxes[], pero tiene {len(taxes_payload)}"
            )

        # Validar estructura taxes[]
        for tax_idx, tax in enumerate(taxes_payload, 1):
            if not tax.get("type"):
                errors.append(f"❌ Item {idx}, Tax {tax_idx}: type faltante")

            if not tax.get("factor"):
                errors.append(f"❌ Item {idx}, Tax {tax_idx}: factor faltante")

            if tax.get("rate") is None:
                errors.append(f"❌ Item {idx}, Tax {tax_idx}: rate faltante")

    # === RESULTADO ===
    if errors:
        error_summary = "\n".join(errors[:10])
        if len(errors) > 10:
            error_summary += f"\n... y {len(errors) - 10} errores más"

        frappe.throw(
            f"Payload incompleto ({len(errors)} errores):\n\n{error_summary}",
            title="Validación E4-RO Falló"
        )

    return True
```

---

## 📋 Contrato de Datos (Interfaces)

### Input: Sales Invoice

```python
# Lectura desde SI
{
    "items[].item_code": str,
    "items[].item_tax_rate": str,  # JSON: {"account": rate}
    "taxes[].account_head": str,
    "taxes[].item_wise_tax_detail": str  # JSON: {"item": [rate, amount]}
}
```

### Input: Item (E0)

```python
{
    "fm_producto_servicio_sat": str  # ClaveProdServ
}
```

### Input: SAT Producto Servicio (catálogo interno)

```python
{
    "codigo": str,                     # ClaveProdServ
    "incluye_objeto_impuesto": str     # "01", "02", "03", "04"
}
```

### Input: Configuración Fiscal México

```python
{
    "mapeos_cuentas_fiscales[]": {
        "cuenta_impuesto": str,
        "impuesto_sat": str,
        "tipo_factor": str,
        "nombre_impuesto_sat": str
    }
}
```

### Output: Payload FacturAPI

```python
{
    "items[]": {
        "product": {
            "tax_object": str,  # "01", "02", "03", "04"
            "taxes[]": [        # Solo si tax_object = "02"
                {
                    "type": str,        # "IVA", "ISR", "IEPS"
                    "factor": str,      # "Tasa"
                    "rate": float,      # 0.16
                    "withholding": bool
                }
            ]
        }
    }
}
```

---

## ✅ Checklist Implementación

- [ ] **E4-RO.1** - `_read_taxes_from_sales_invoice_item()` (leer item_tax_rate)
- [ ] **E4-RO.2** - `_resolve_objeto_impuesto()` (lookup SAT Producto Servicio)
- [ ] **E4-RO.3** - `_map_tax_account_to_sat()` (usar mapeo existente)
- [ ] **E4-RO.4** - Actualizar payload items con taxes[] (passthrough)
- [ ] **E4-RO.5** - `_validate_payload_completeness_ro()` (sin aritmética)
- [ ] **E4-RO.6** - Tests unitarios (lectura, lookup, mapeo, validación)
- [ ] **E4-RO.7** - [TS] Testing sandbox PAC con factura real

---

## 🎯 Garantías E4-RO

1. ✅ **Zero cálculos** - Solo lectura/serialización
2. ✅ **Zero campos nuevos** - Usa catálogo existente
3. ✅ **Sincronía SI-Payload** - Payload = SI exactamente
4. ✅ **Validación robusta** - Completitud sin aritmética
5. ✅ **Mantenible** - Adapter passthrough simple

---

**🔐 CONFIRMACIÓN REQUERIDA:** ¿Aprobar E4-RO Final? (si/no)

---

**Generado:** 2025-10-08
**Versión:** 3.0 Final
**Estado:** ⏳ Pendiente aprobación
