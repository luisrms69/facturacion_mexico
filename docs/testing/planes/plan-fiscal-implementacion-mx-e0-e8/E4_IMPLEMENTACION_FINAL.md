# E4 - Implementación Final (Read-Only)

**Fecha:** 2025-10-08
**Autor:** Claude Code
**Versión:** Final integrada con cambios aprobados

---

## 🎯 Principio Fundamental

**Sales Invoice es la fuente única de verdad.**

- ✅ Solo **leer y pasar** valores desde SI
- ❌ **Zero cálculos** (SI ya los hizo en E1)
- ❌ **Zero campos nuevos en SI/Item**
- ✅ Usar **catálogo interno** existente (SAT Producto Servicio)
- ✅ **Validaciones estrictas** sin arreglos automáticos

---

## 📊 Fuentes de Datos

### 1. Sales Invoice (SI) - Fuente única

**Items:**
```python
{
    "item_code": str,
    "item_name": str,
    "name": str,  # row.name interno
    "item_tax_rate": str  # JSON: {"account_head": rate, ...}
}
```

**Taxes:**
```python
{
    "account_head": str,
    "rate": float,
    "tax_amount": float,
    "item_wise_tax_detail": str  # JSON: {"key": [rate, amount]}
}
```

### 2. Item (E0)

```python
{
    "fm_producto_servicio_sat": str  # ClaveProdServ
}
```

### 3. SAT Producto Servicio (catálogo interno)

```python
{
    "codigo": str,                      # "78101802"
    "incluye_objeto_impuesto": str      # "01", "02", "03", "04"
}
```

### 4. Configuración Fiscal México (mapeo SAT)

**Tabla:** `mapeos_cuentas_fiscales`

```python
{
    "cuenta_impuesto": str,        # "123456 - iva 16% - _TC"
    "impuesto_sat": str,           # "002" (IVA)
    "tipo_factor": str,            # "Tasa"
    "nombre_impuesto_sat": str,    # "IVA"
    "es_retencion": bool           # ← NUEVO (Cambio 4)
}
```

---

## 🔧 Implementación E4-RO

### E4.1 - Leer Impuestos desde SI (passthrough)

**Función:** `_read_taxes_from_sales_invoice_item(item, sales_invoice)`

```python
def _read_taxes_from_sales_invoice_item(self, item, sales_invoice):
    """
    Leer impuestos de un item desde Sales Invoice.

    E4-RO: Solo lectura, sin cálculos.

    Args:
        item: Row de Sales Invoice.items
        sales_invoice: Documento Sales Invoice completo

    Returns:
        List[dict]: [
            {
                "account_head": str,
                "rate": float,
                "amount": float
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
        # Buscar amount desde SI con lectura robusta (Cambio 3)
        amount = self._get_tax_amount_for_item_robust(
            sales_invoice,
            account_head,
            item.item_code,
            item.item_name,
            item.name  # row.name
        )

        taxes_data.append({
            "account_head": account_head,
            "rate": rate,
            "amount": amount
        })

    return taxes_data
```

---

### E4.2 - Lectura Robusta item_wise_tax_detail (Cambio 3 - Aprobado)

**Función:** `_get_tax_amount_for_item_robust()`

```python
def _get_tax_amount_for_item_robust(self, sales_invoice, account_head, item_code, item_name, row_name):
    """
    Extraer amount con fallback de llaves.

    CAMBIO 3 APROBADO: Lectura robusta según versión ERPNext.

    Prioridad llaves en item_wise_tax_detail:
    1. row.name (row interno SI)
    2. item_code
    3. item_name

    Args:
        sales_invoice: Documento SI
        account_head: Cuenta impuesto
        item_code: Código item
        item_name: Nombre item
        row_name: row.name interno

    Returns:
        float: Tax amount para el item
    """
    import json

    # Buscar tax row en SI
    tax_row = None
    for tax in sales_invoice.taxes:
        if tax.account_head == account_head:
            tax_row = tax
            break

    if not tax_row or not tax_row.item_wise_tax_detail:
        return 0.0

    # Parse JSON
    item_wise = json.loads(tax_row.item_wise_tax_detail)

    # CAMBIO 3: Fallback de llaves (row.name → item_code → item_name)
    for key in [row_name, item_code, item_name]:
        if key in item_wise:
            # item_wise[key] = [rate, amount]
            return float(item_wise[key][1])  # Posición 1 = amount

    # No encontrado
    frappe.logger().warning(
        f"Tax amount no encontrado para item {item_code} en {account_head}"
    )
    return 0.0
```

---

### E4.3 - Resolver ObjetoImp (lookup catálogo)

**Función:** `_resolve_objeto_impuesto(item_doc)`

```python
def _resolve_objeto_impuesto(self, item_doc):
    """
    Resolver ObjetoImp desde catálogo SAT Producto Servicio.

    E4-RO: Solo lookup, sin inferencias.

    Pipeline:
    1. Leer Item.fm_producto_servicio_sat
    2. Lookup SAT Producto Servicio.incluye_objeto_impuesto
    3. Retornar "01", "02", "03", o "04"

    Returns:
        str: ObjetoImp
    """
    clave_prod_serv = item_doc.get("fm_producto_servicio_sat")

    if not clave_prod_serv:
        frappe.throw(
            f"Item {item_doc.name} no tiene ClaveProdServ (fm_producto_servicio_sat) configurada.\n"
            f"Configure el campo SAT en Item.",
            title="ClaveProdServ Faltante"
        )

    # Lookup en catálogo interno
    sat_producto = frappe.db.get_value(
        "SAT Producto Servicio",
        clave_prod_serv,
        "incluye_objeto_impuesto"
    )

    if not sat_producto:
        frappe.throw(
            f"ClaveProdServ '{clave_prod_serv}' no encontrada en catálogo SAT.\n"
            f"Verifique que existe en DocType 'SAT Producto Servicio'.",
            title="ClaveProdServ No Encontrada"
        )

    return sat_producto
```

---

### E4.4 - Mapear Account → SAT (Cambio 4 - Aprobado)

**Función:** `_map_tax_account_to_sat(account_head)`

```python
def _map_tax_account_to_sat(self, account_head):
    """
    Mapear cuenta ERPNext → metadata SAT.

    CAMBIO 4 APROBADO: Usar campo es_retencion del mapeo.

    Fuente: Configuración Fiscal México → mapeos_cuentas_fiscales

    Args:
        account_head: Nombre cuenta (ej: "123456 - iva 16% - _TC")

    Returns:
        {
            "impuesto_sat": str,      # "002"
            "tipo_factor": str,       # "Tasa"
            "nombre_sat": str,        # "IVA"
            "es_retencion": bool      # True/False
        }

    Raises:
        frappe.ValidationError: Si cuenta no mapeada
    """
    config = frappe.get_single("Configuracion Fiscal Mexico")

    for mapeo in config.mapeos_cuentas_fiscales:
        if mapeo.cuenta_impuesto == account_head:
            return {
                "impuesto_sat": mapeo.impuesto_sat,
                "tipo_factor": mapeo.tipo_factor,
                "nombre_sat": mapeo.nombre_impuesto_sat,
                "es_retencion": mapeo.get("es_retencion", False)  # CAMBIO 4
            }

    # Cuenta no mapeada = error (datos incompletos)
    frappe.throw(
        f"Cuenta '{account_head}' no tiene mapeo SAT configurado.\n\n"
        f"Configure en: Configuración Fiscal México → Mapeos Cuentas Fiscales\n"
        f"Campos requeridos: impuesto_sat, tipo_factor, nombre_impuesto_sat, es_retencion",
        title="Mapeo SAT Faltante"
    )
```

---

### E4.5 - Construir Payload PAC (serialización)

**Modificar:** `timbrado_api.py:_prepare_facturapi_data()` líneas 475-491

```python
# Items de la factura
items = []
for item in sales_invoice.items:
    item_doc = frappe.get_doc("Item", item.item_code)

    # E4.1: Leer taxes desde SI (NO calcular)
    item_taxes_data = self._read_taxes_from_sales_invoice_item(item, sales_invoice)

    # E4.3: Resolver ObjetoImp desde catálogo SAT
    objeto_imp = self._resolve_objeto_impuesto(item_doc)

    # E4.4: Mapear taxes a estructura FacturAPI
    taxes_payload = []
    for tax_data in item_taxes_data:
        sat_mapping = self._map_tax_account_to_sat(tax_data["account_head"])

        taxes_payload.append({
            "type": sat_mapping["nombre_sat"],           # "IVA", "ISR", "IEPS"
            "factor": sat_mapping["tipo_factor"],        # "Tasa"
            "rate": abs(tax_data["rate"]) / 100,         # 16.0 → 0.16
            "withholding": sat_mapping["es_retencion"]   # CAMBIO 4: desde mapeo
        })

    # CAMBIO 2: Validación estricta ObjetoImp vs taxes
    self._validate_objeto_imp_consistency(objeto_imp, taxes_payload, item)

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
            "tax_object": objeto_imp,
        },
    }

    # Solo agregar taxes[] si ObjetoImp = "02"
    if objeto_imp == "02":
        item_payload["product"]["taxes"] = taxes_payload

    items.append(item_payload)

# CAMBIO 3: Validación moneda (simplificada)
self._validate_currency_consistency(invoice_data, sales_invoice)
```

---

### E4.6 - Validación ObjetoImp Estricta (Cambio 2 - Aprobado)

**Función:** `_validate_objeto_imp_consistency()`

```python
def _validate_objeto_imp_consistency(self, objeto_imp, taxes_payload, item):
    """
    Validar coherencia ObjetoImp vs presencia de impuestos.

    CAMBIO 2 APROBADO: Validación estricta sin arreglos automáticos.

    Reglas:
    - ObjetoImp 01/03/04 (sin impuestos) → NO debe tener taxes
    - ObjetoImp 02 (con impuestos) → DEBE tener taxes

    Args:
        objeto_imp: str ("01", "02", "03", "04")
        taxes_payload: list de impuestos
        item: Row de Sales Invoice.items

    Raises:
        frappe.ValidationError: Si inconsistencia detectada
    """
    # Si ObjetoImp indica "sin impuestos" pero SI tiene taxes
    if objeto_imp in ["01", "03", "04"] and taxes_payload:
        frappe.throw(
            f"Inconsistencia datos item '{item.item_code}':\n\n"
            f"• ObjetoImp: '{objeto_imp}' (no objeto de impuesto)\n"
            f"• Sales Invoice tiene: {len(taxes_payload)} impuesto(s) configurado(s)\n\n"
            f"Corrija:\n"
            f"1. Si el item SÍ causa impuestos → Actualizar catálogo SAT a ObjetoImp '02'\n"
            f"2. Si el item NO causa impuestos → Quitar Item Tax Template en Sales Invoice",
            title="Inconsistencia ObjetoImp vs Impuestos"
        )

    # Si ObjetoImp indica "con impuestos" pero SI NO tiene taxes
    if objeto_imp == "02" and not taxes_payload:
        frappe.throw(
            f"Inconsistencia datos item '{item.item_code}':\n\n"
            f"• ObjetoImp: '02' (sí objeto de impuesto)\n"
            f"• Sales Invoice NO tiene impuestos configurados\n\n"
            f"Corrija:\n"
            f"1. Si el item causa impuestos → Configurar Item Tax Template\n"
            f"2. Si el item NO causa impuestos → Actualizar catálogo SAT a ObjetoImp '01'",
            title="Inconsistencia ObjetoImp vs Impuestos"
        )
```

---

### E4.7 - Validación Moneda (Cambio 3 - Aprobado Simplificado)

**Función:** `_validate_currency_consistency()`

```python
def _validate_currency_consistency(self, invoice_data, sales_invoice):
    """
    Validar consistencia moneda payload vs SI.

    CAMBIO 3 APROBADO: Validación simplificada sin conversiones.

    Args:
        invoice_data: Payload FacturAPI
        sales_invoice: Documento Sales Invoice

    Raises:
        frappe.ValidationError: Si moneda inconsistente
    """
    payload_currency = invoice_data.get("currency", "MXN")
    si_currency = sales_invoice.currency

    if payload_currency != si_currency:
        frappe.throw(
            f"Moneda inconsistente:\n\n"
            f"• Payload: {payload_currency}\n"
            f"• Sales Invoice: {si_currency}\n\n"
            f"El payload debe usar la misma moneda que Sales Invoice.",
            title="Moneda Inconsistente"
        )

    # Log informativo si hay tipo de cambio
    if sales_invoice.conversion_rate and sales_invoice.conversion_rate != 1.0:
        frappe.logger().info(
            f"SI {sales_invoice.name} con tipo cambio {sales_invoice.conversion_rate}. "
            f"Amounts ya están convertidos a {si_currency}."
        )
```

---

### E4.8 - Validación Completitud Payload

**Función:** `_validate_payload_completeness_ro()`

```python
def _validate_payload_completeness_ro(self, invoice_data, sales_invoice):
    """
    Validar completitud payload E4-RO.

    Solo cotejo estructura, sin aritmética.

    Args:
        invoice_data: Payload FacturAPI
        sales_invoice: Documento Sales Invoice

    Raises:
        frappe.ValidationError: Si payload incompleto
    """
    errors = []

    # === DATOS CLIENTE ===
    customer_data = invoice_data.get("customer", {})
    required_fields = ["legal_name", "tax_id", "tax_system"]

    for field in required_fields:
        if not customer_data.get(field):
            errors.append(f"❌ customer.{field} faltante")

    # === DATOS FACTURA ===
    if not invoice_data.get("payment_form"):
        errors.append("❌ payment_form faltante")

    if not invoice_data.get("use"):
        errors.append("❌ use (Uso CFDI) faltante")

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

        # Validar estructura taxes[] si existe
        taxes_payload = product.get("taxes", [])
        for tax_idx, tax in enumerate(taxes_payload, 1):
            if not tax.get("type"):
                errors.append(f"❌ Item {idx}, Tax {tax_idx}: type faltante")

            if not tax.get("factor"):
                errors.append(f"❌ Item {idx}, Tax {tax_idx}: factor faltante")

            if tax.get("rate") is None:
                errors.append(f"❌ Item {idx}, Tax {tax_idx}: rate faltante")

            if "withholding" not in tax:
                errors.append(f"❌ Item {idx}, Tax {tax_idx}: withholding faltante")

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

## 🔧 Modificación Configuración Fiscal

### Campo Nuevo: `es_retencion`

**DocType:** Configuracion Fiscal Mexico
**Child Table:** mapeos_cuentas_fiscales

**Campo agregar:**

```json
{
  "fieldname": "es_retencion",
  "fieldtype": "Check",
  "label": "Es Retención",
  "description": "Marcar si es impuesto retenido (withholding=True en CFDI)",
  "insert_after": "nombre_impuesto_sat",
  "default": 0
}
```

**Justificación:**
- Reemplaza inferencia por signo rate (no confiable)
- Fuente única verdad para naturaleza retención
- Administrable por usuario sin código
- No requiere `add_deduct_tax` (que no existe en ERPNext v15)

---

## 📋 Casos de Prueba E4-RO

### Caso 1: IVA 16% simple

**Input SI:**
- Item: ClaveProdServ "01010101" → ObjetoImp "02"
- item_tax_rate: `{"123456 - iva 16%": 16.0}`

**Mapeo SAT:**
- 123456 - iva 16%: impuesto_sat="002", nombre="IVA", es_retencion=False

**Output esperado:**
```json
{
  "product": {
    "tax_object": "02",
    "taxes": [
      {"type": "IVA", "factor": "Tasa", "rate": 0.16, "withholding": false}
    ]
  }
}
```

---

### Caso 2: Retenciones ISR + IVA

**Input SI:**
- Item: ClaveProdServ "80101500" → ObjetoImp "02"
- item_tax_rate: `{"2118002 - ISR Ret": -10.0, "2119002 - IVA Ret": -66.67}`

**Mapeo SAT:**
- 2118002 - ISR Ret: impuesto_sat="001", nombre="ISR", es_retencion=True
- 2119002 - IVA Ret: impuesto_sat="002", nombre="IVA", es_retencion=True

**Output esperado:**
```json
{
  "product": {
    "tax_object": "02",
    "taxes": [
      {"type": "ISR", "factor": "Tasa", "rate": 0.10, "withholding": true},
      {"type": "IVA", "factor": "Tasa", "rate": 0.6667, "withholding": true}
    ]
  }
}
```

---

### Caso 3: Error ObjetoImp inconsistente (CAMBIO 2)

**Input SI:**
- Item: ClaveProdServ "84111506" → ObjetoImp "01" (sin impuestos)
- item_tax_rate: `{"123456 - iva 16%": 16.0}` ← INCONSISTENTE

**Resultado esperado:**
```
❌ ValidationError:
Inconsistencia datos item 'TEST-ITEM-001':
• ObjetoImp: '01' (no objeto de impuesto)
• Sales Invoice tiene: 1 impuesto(s) configurado(s)

Corrija:
1. Si el item SÍ causa impuestos → Actualizar catálogo SAT a ObjetoImp '02'
2. Si el item NO causa impuestos → Quitar Item Tax Template en Sales Invoice
```

---

### Caso 4: Lectura robusta item_wise_tax_detail (CAMBIO 3)

**Input SI (llave = row.name):**
- item_wise_tax_detail: `{"row-abc-123": [16.0, 160.0]}`
- item_code: "TEST-ITEM-001"

**Resultado esperado:**
- Amount = 160.0 ✅ (encontrado por row.name fallback)
- Sin warnings falsos 0.00

---

### Caso 5: Validación moneda (CAMBIO 3)

**Input SI:**
- currency: "USD"
- conversion_rate: 20.0

**Payload:**
- currency: "MXN" ← INCONSISTENTE

**Resultado esperado:**
```
❌ ValidationError:
Moneda inconsistente:
• Payload: MXN
• Sales Invoice: USD

El payload debe usar la misma moneda que Sales Invoice.
```

---

## ✅ Checklist Implementación

- [ ] **E4.1** - `_read_taxes_from_sales_invoice_item()` (leer item_tax_rate)
- [ ] **E4.2** - `_get_tax_amount_for_item_robust()` (CAMBIO 3 - fallback llaves)
- [ ] **E4.3** - `_resolve_objeto_impuesto()` (lookup SAT Producto Servicio)
- [ ] **E4.4** - `_map_tax_account_to_sat()` (CAMBIO 4 - usar es_retencion)
- [ ] **E4.5** - Actualizar payload items con taxes[] (passthrough)
- [ ] **E4.6** - `_validate_objeto_imp_consistency()` (CAMBIO 2 - validación estricta)
- [ ] **E4.7** - `_validate_currency_consistency()` (CAMBIO 3 - simplificada)
- [ ] **E4.8** - `_validate_payload_completeness_ro()` (completitud)
- [ ] **E4.9** - Agregar campo `es_retencion` a mapeos SAT (fixture)
- [ ] **E4.10** - Tests unitarios (5 casos + cambios 2,3,4)
- [ ] **E4.11** - [TS] Testing sandbox PAC con factura real

---

## 🎯 Garantías E4-RO

1. ✅ **Zero cálculos** - Solo lectura/serialización
2. ✅ **Zero campos nuevos SI/Item** - Solo config (es_retencion)
3. ✅ **Sincronía SI-Payload** - Payload = SI exactamente
4. ✅ **Validación robusta** - Cambios 2,3,4 integrados
5. ✅ **Mantenible** - Adapter passthrough simple
6. ✅ **Errores claros** - Mensajes específicos con soluciones

---

## 📐 Decisiones Arquitectura (Cambios Aprobados)

### Cambio 2: ObjetoImp Validación Estricta
- ✅ Error bloqueante si inconsistencia catálogo vs SI
- ✅ Sin arreglos automáticos
- ✅ Mensajes con soluciones específicas

### Cambio 3: Lectura Robusta + Moneda
- ✅ Fallback llaves item_wise_tax_detail (row.name → item_code → item_name)
- ✅ Validación moneda payload = SI (simplificada)
- ✅ Log informativo si TC != 1.0

### Cambio 4: Withholding desde Mapeo
- ✅ Campo `es_retencion` en configuración SAT
- ✅ No depende de signo rate
- ✅ Administrable por usuario

### Cambio 5: Hash Anti-Deriva
- N/A - Ya cubierto en sistema

---

**🔐 CONFIRMACIÓN REQUERIDA:** ¿Proceder con implementación E4-RO según este documento? (si/no)

---

**Generado:** 2025-10-08
**Versión:** Final con cambios 2,3,4 integrados
**Estado:** ⏳ Pendiente aprobación implementación
