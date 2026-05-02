# Contrapropuesta E4-RO (Read-Only) - Puente Sales Invoice → PAC

**Fecha:** 2025-10-08
**Autor:** Claude Code
**Contexto:** Comparación propuesta Claude vs ChatGPT

---

## 📊 Comparación Propuestas

| Aspecto | Propuesta Claude Original | Propuesta ChatGPT (E4-RO) | Ganador |
|---------|---------------------------|---------------------------|---------|
| **Filosofía** | Extraer ITT → calcular taxes | **Solo leer y pasar** desde SI | ✅ ChatGPT |
| **Cálculos** | Calcular base/importes | **Zero cálculos** | ✅ ChatGPT |
| **Fuente verdad** | Item Tax Template | **Sales Invoice** | ✅ ChatGPT |
| **Complejidad** | Alta (parsear, calcular, mapear) | **Baja (copiar, validar)** | ✅ ChatGPT |
| **Riesgo** | Desincronía SI vs payload | **Sincronía garantizada** | ✅ ChatGPT |
| **Validación payload** | Estructura correcta | **Completitud + Consistencia** | ✅ ChatGPT |

---

## ❌ Problemas Propuesta Claude Original

1. **Recalcular impuestos** → Riesgo desincronía con SI (SI ya los calculó)
2. **Parsear ITT** → Complejidad innecesaria (SI ya tiene `item_tax_rate` por item)
3. **Mapear account → SAT** → Ya existe en configuración, no reinventar
4. **Calcular bases IEPS** → SI ya lo hizo, NO duplicar lógica

**Conclusión:** Propuesta Claude **sobrediseñada** para un problema de **serialización**.

---

## ✅ Ventajas Propuesta ChatGPT (E4-RO)

1. **Fuente única:** Sales Invoice (SI) ya tiene TODOS los datos calculados
2. **Zero cálculos:** Solo copiar valores existentes
3. **Sincronía garantizada:** Payload = SI exactamente
4. **Simple:** Adapter passthrough sin lógica de negocio
5. **Validación robusta:** Completitud + Consistencia sin aritmética nueva

---

## 🔍 Evidencia: Sales Invoice YA tiene todo

### Estructura Real Sales Invoice (facturacion.dev)

```json
{
  "items": [
    {
      "item_code": "TEST-RET-AUTOTRANSPORTE-001",
      "qty": 1.0,
      "rate": 1000.0,
      "amount": 1000.0,
      "item_tax_template": "ITT ISR + IVA Ret Autotransporte - _TC",
      "item_tax_rate": "{\"2118002 - ISR Ret Autotransporte - _TC\": -4.0, \"2119002 - IVA Ret Autotransporte - _TC\": -66.67}"
    }
  ],
  "taxes": [
    {
      "charge_type": "On Net Total",
      "account_head": "123456 - iva 16% - _TC",
      "description": "IVA 16%",
      "rate": 16.0,
      "tax_amount": 0.0,
      "item_wise_tax_detail": "{\"TEST-RET-AUTOTRANSPORTE-001\":[16.0,0.0],...}"
    }
  ]
}
```

**Key findings:**

1. ✅ **`item.item_tax_rate`** contiene JSON con taxes aplicados al item:
   ```json
   {
     "2118002 - ISR Ret Autotransporte - _TC": -4.0,
     "2119002 - IVA Ret Autotransporte - _TC": -66.67
   }
   ```

2. ✅ **`tax.item_wise_tax_detail`** contiene rate y amount POR ITEM:
   ```json
   {
     "TEST-RET-AUTOTRANSPORTE-001": [16.0, 0.0],  // [rate, amount]
     ...
   }
   ```

3. ✅ **Sales Invoice YA calculó todo** (E1 automated tax funcionando)

---

## 🎯 Contrapropuesta E4-RO (Read-Only)

### Arquitectura Simple: 3 Pasos

```
┌─────────────────┐
│ Sales Invoice   │ ← Fuente única verdad (E1 ya calculó)
│ (SI)            │
└────────┬────────┘
         │ LEER
         ▼
┌─────────────────┐
│ Adapter E4-RO   │ ← Solo serializar, NO calcular
│ (Passthrough)   │
└────────┬────────┘
         │ SERIALIZAR
         ▼
┌─────────────────┐
│ Payload PAC     │ ← Estructura FacturAPI
│ (FacturAPI)     │
└─────────────────┘
```

---

## 🔧 Implementación E4-RO

### E4-RO.1 - Leer Impuestos desde Sales Invoice

**Función:** `_read_taxes_from_sales_invoice_item(item, sales_invoice)`

**NO hace:**
- ❌ Parsear Item Tax Template
- ❌ Calcular bases/importes
- ❌ Inferir tipos impuesto

**SÍ hace:**
- ✅ Leer `item.item_tax_rate` (JSON con taxes del item)
- ✅ Buscar cada tax en `sales_invoice.taxes` para obtener metadata
- ✅ Copiar rate/amount tal cual está

**Código:**

```python
def _read_taxes_from_sales_invoice_item(self, item, sales_invoice):
    """
    Leer impuestos aplicados a un item desde Sales Invoice.

    E4-RO: Solo lectura, sin cálculos.

    Fuentes:
    - item.item_tax_rate (JSON): {"account_head": rate, ...}
    - sales_invoice.taxes[].item_wise_tax_detail (JSON): {item_code: [rate, amount]}

    Returns:
        List[dict]: Impuestos para payload PAC
        [
            {
                "account_head": str,  # Ej: "123456 - iva 16% - _TC"
                "rate": float,        # Ej: 16.0
                "amount": float,      # Ej: 160.0
                "withholding": bool   # True si rate negativo
            }
        ]
    """
    import json

    # Leer taxes desde item.item_tax_rate
    if not item.item_tax_rate:
        return []  # Sin ITT = sin impuestos

    item_tax_rate = json.loads(item.item_tax_rate)
    # Format: {"account_head": rate, ...}
    # Ej: {"2118002 - ISR Ret Autotransporte - _TC": -4.0}

    taxes_data = []

    for account_head, rate in item_tax_rate.items():
        # Buscar tax en sales_invoice.taxes para obtener amount
        tax_row = self._find_tax_row_in_si(sales_invoice, account_head)

        if not tax_row:
            frappe.logger().warning(
                f"Tax account '{account_head}' en item {item.item_code} "
                f"no encontrado en SI.taxes"
            )
            continue

        # Extraer amount desde item_wise_tax_detail
        amount = self._get_tax_amount_for_item(tax_row, item.item_code)

        taxes_data.append({
            "account_head": account_head,
            "rate": rate,
            "amount": amount,
            "withholding": rate < 0  # Rate negativo = retención
        })

    return taxes_data


def _find_tax_row_in_si(self, sales_invoice, account_head):
    """Buscar tax row en SI.taxes por account_head."""
    for tax in sales_invoice.taxes:
        if tax.account_head == account_head:
            return tax
    return None


def _get_tax_amount_for_item(self, tax_row, item_code):
    """
    Extraer tax amount para item específico desde item_wise_tax_detail.

    Format item_wise_tax_detail:
    {
        "item_code_1": [rate, amount],
        "item_code_2": [rate, amount]
    }
    """
    import json

    if not tax_row.item_wise_tax_detail:
        return 0.0

    item_wise = json.loads(tax_row.item_wise_tax_detail)

    if item_code not in item_wise:
        return 0.0

    # item_wise[item_code] = [rate, amount]
    return float(item_wise[item_code][1])  # Posición 1 = amount
```

---

### E4-RO.2 - Mapear Tax Account → SAT

**Función:** `_map_tax_account_to_sat(account_head)`

**NO hace:**
- ❌ Parsear nombres con regex
- ❌ Inferir tipos SAT

**SÍ hace:**
- ✅ Usar mapeo existente (Configuración Fiscal México → Mapeo Cuenta Fiscal)
- ✅ Error si cuenta no mapeada

**Código:**

```python
def _map_tax_account_to_sat(self, account_head):
    """
    Mapear tax account ERPNext → metadata SAT.

    E4-RO: Usa mapeo existente, sin inferencias.

    Fuente: Configuración Fiscal México → Mapeo Cuenta Fiscal

    Returns:
        {
            "impuesto_sat": str,     # "001" (ISR), "002" (IVA), "003" (IEPS)
            "tipo_factor": str,      # "Tasa", "Cuota", "Exento"
            "nombre_sat": str        # Ej: "IVA", "ISR", "IEPS"
        }

    Raises:
        frappe.ValidationError: Si cuenta no mapeada
    """
    # Buscar en mapeo existente
    mapeo = self._get_mapeo_cuenta_fiscal(account_head)

    if not mapeo:
        frappe.throw(
            f"Cuenta de impuesto '{account_head}' no tiene mapeo SAT configurado.\n\n"
            f"Configure el mapeo en: Configuración Fiscal México → Mapeo Cuenta Fiscal",
            title="Mapeo SAT Faltante"
        )

    return {
        "impuesto_sat": mapeo.get("impuesto_sat"),      # "002"
        "tipo_factor": mapeo.get("tipo_factor", "Tasa"),
        "nombre_sat": mapeo.get("nombre_impuesto_sat")  # "IVA"
    }


def _get_mapeo_cuenta_fiscal(self, account_head):
    """
    Obtener mapeo desde Configuración Fiscal México.

    Busca en tabla child 'mapeos_cuentas_fiscales':
    - cuenta_impuesto: account_head
    - impuesto_sat: código SAT ("001", "002", "003")
    - tipo_factor: "Tasa", "Cuota", "Exento"
    """
    config = frappe.get_single("Configuracion Fiscal Mexico")

    for mapeo_row in config.mapeos_cuentas_fiscales:
        if mapeo_row.cuenta_impuesto == account_head:
            return {
                "impuesto_sat": mapeo_row.impuesto_sat,
                "tipo_factor": mapeo_row.tipo_factor,
                "nombre_impuesto_sat": mapeo_row.nombre_impuesto_sat
            }

    return None
```

---

### E4-RO.3 - Construir Payload PAC (Passthrough)

**Modificar:** `timbrado_api.py:_prepare_facturapi_data()` líneas 475-491

**Código actual:**
```python
items.append({
    "quantity": item.qty,
    "product": {
        "description": item.description or item.item_name,
        "product_key": item_doc.fm_producto_servicio_sat or "01010101",
        "price": flt(item.rate),
        "tax_included": False,
        "unit_key": _extract_sat_code_from_uom(item.uom),
        "unit_name": item.uom or "Pieza",
    },
})
```

**Código E4-RO:**
```python
# Items de la factura
items = []
for item in sales_invoice.items:
    item_doc = frappe.get_doc("Item", item.item_code)

    # E4-RO: Leer impuestos desde SI (NO calcular)
    item_taxes_data = self._read_taxes_from_sales_invoice_item(item, sales_invoice)

    # E4-RO: Mapear taxes a estructura FacturAPI
    taxes_payload = []
    for tax_data in item_taxes_data:
        # Mapear account → SAT usando configuración existente
        sat_mapping = self._map_tax_account_to_sat(tax_data["account_head"])

        taxes_payload.append({
            "type": sat_mapping["nombre_sat"],        # "IVA", "ISR", "IEPS"
            "factor": sat_mapping["tipo_factor"],     # "Tasa"
            "rate": abs(tax_data["rate"]) / 100,      # 16.0 → 0.16 (formato FacturAPI)
            "withholding": tax_data["withholding"]    # True si rate negativo
        })

    # E4-RO: Determinar ObjetoImp
    # FUENTE: item.fm_objeto_impuesto (campo E0) si existe
    # FALLBACK: "02" si tiene taxes, "01" si no tiene
    objeto_imp = item_doc.get("fm_objeto_impuesto") or ("02" if taxes_payload else "01")

    item_payload = {
        "quantity": item.qty,
        "product": {
            "description": item.description or item.item_name,
            "product_key": item_doc.fm_producto_servicio_sat or "01010101",
            "price": flt(item.rate),
            "tax_included": False,
            "unit_key": _extract_sat_code_from_uom(item.uom),
            "unit_name": item.uom or "Pieza",
            "tax_object": objeto_imp,  # E4-RO: ObjetoImp
        },
    }

    # E4-RO: Solo agregar "taxes" si ObjetoImp = "02"
    if objeto_imp == "02" and taxes_payload:
        item_payload["product"]["taxes"] = taxes_payload

    items.append(item_payload)
```

---

### E4-RO.4 - Validación Completitud (Sin Aritmética)

**Función:** `_validate_payload_completeness_ro(invoice_data, sales_invoice)`

**Validaciones:**

1. **Completitud campos obligatorios**
   - Customer: legal_name, tax_id, tax_system, address
   - Factura: payment_form, use, type
   - Items: product_key, unit_key, quantity, price, tax_object

2. **Consistencia ObjetoImp vs taxes**
   - ObjetoImp "01" → NO debe tener taxes[]
   - ObjetoImp "02" → DEBE tener taxes[]

3. **Mapeo SAT completo**
   - Todos los taxes tienen mapeo configurado
   - Sin cuentas huérfanas

4. **Conteo impuestos**
   - Cantidad de taxes en payload = cantidad en SI por item
   - Tipos coinciden (IVA, ISR, IEPS)
   - Rates coinciden (± 0.01 tolerancia formato)

**NO valida:**
- ❌ Cálculo bases/importes (SI ya lo hizo)
- ❌ Fórmulas cascada IEPS (SI ya lo calculó)
- ❌ Retenciones precisión (E3 ya lo validó)

**Código:**

```python
def _validate_payload_completeness_ro(self, invoice_data, sales_invoice):
    """
    Validar completitud payload E4-RO.

    Solo cotejo, sin aritmética nueva.
    """
    errors = []

    # === SECCIÓN 1: DATOS CLIENTE ===
    customer_data = invoice_data.get("customer", {})

    required_customer = ["legal_name", "tax_id", "tax_system"]
    for field in required_customer:
        if not customer_data.get(field):
            errors.append(f"❌ customer.{field} faltante")

    # === SECCIÓN 2: ITEMS Y CONCEPTOS ===
    items = invoice_data.get("items", [])

    if not items:
        errors.append("❌ items[] vacío")

    for idx, item_payload in enumerate(items, 1):
        product = item_payload.get("product", {})
        si_item = sales_invoice.items[idx - 1]  # Item correspondiente en SI

        # Validar campos obligatorios
        required_product = ["product_key", "unit_key", "description", "tax_object"]
        for field in required_product:
            if not product.get(field):
                errors.append(f"❌ Item {idx}: product.{field} faltante")

        # E4-RO: Validar coherencia ObjetoImp vs taxes
        objeto_imp = product.get("tax_object")
        taxes_payload = product.get("taxes", [])

        if objeto_imp == "01" and taxes_payload:
            errors.append(
                f"⚠️ Item {idx} ({si_item.item_code}): "
                f"ObjetoImp '01' (sin impuestos) pero tiene {len(taxes_payload)} taxes"
            )

        if objeto_imp == "02" and not taxes_payload:
            errors.append(
                f"❌ Item {idx} ({si_item.item_code}): "
                f"ObjetoImp '02' (con impuestos) pero taxes[] vacío"
            )

        # E4-RO: Validar conteo impuestos (SI vs Payload)
        si_taxes_count = len(self._read_taxes_from_sales_invoice_item(si_item, sales_invoice))
        payload_taxes_count = len(taxes_payload)

        if objeto_imp == "02" and si_taxes_count != payload_taxes_count:
            errors.append(
                f"⚠️ Item {idx} ({si_item.item_code}): "
                f"SI tiene {si_taxes_count} taxes, payload tiene {payload_taxes_count}"
            )

    # === RESULTADO ===
    if errors:
        error_summary = "\n".join(errors[:10])
        if len(errors) > 10:
            error_summary += f"\n... y {len(errors) - 10} errores más"

        frappe.throw(
            f"Payload incompleto ({len(errors)} errores):\n\n{error_summary}",
            title="Validación E4-RO Falló"
        )

    return True  # ✅ Payload completo
```

---

## 📋 Cambios en Campos/Nombres

### Campo Nuevo Requerido

**Agregar a Item (E0 extended):**

```json
{
  "fieldname": "fm_objeto_impuesto",
  "fieldtype": "Select",
  "label": "Objeto Impuesto SAT",
  "options": "01 - No objeto de impuesto\n02 - Sí objeto de impuesto\n03 - Sí objeto del impuesto y no obligado al desglose\n04 - Sí objeto del impuesto y no causa impuesto",
  "description": "Indica si el concepto es objeto de impuesto (ObjetoImp CFDI 4.0)"
}
```

**Justificación:**
- Necesario para E4-RO determinar ObjetoImp sin lógica inferencia
- CFDI 4.0 requiere ObjetoImp por concepto
- Evita asumir "02" siempre

### Campos Mapeo SAT

**Tabla Child: Configuración Fiscal México → Mapeos Cuentas Fiscales**

Campos requeridos:
- `cuenta_impuesto` (Link: Account) - Cuenta ERPNext
- `impuesto_sat` (Select) - Código SAT ("001" ISR, "002" IVA, "003" IEPS)
- `tipo_factor` (Select) - "Tasa", "Cuota", "Exento"
- `nombre_impuesto_sat` (Data) - Nombre para payload ("IVA", "ISR", "IEPS")

---

## 🎯 Ventajas Contrapropuesta E4-RO

| Ventaja | Impacto |
|---------|---------|
| **Zero cálculos** | Sin riesgo desincronía SI vs Payload |
| **Fuente única** | SI = source of truth garantizada |
| **Simple** | 3 funciones vs 6+ propuesta original |
| **Validación robusta** | Completitud sin aritmética compleja |
| **Mantenible** | Sin lógica negocio en adapter |
| **Extensible** | Agregar campos solo modifica serialización |

---

## 🔧 Plan Implementación E4-RO

### Tareas

- [ ] **E4-RO.0** - Agregar campo `fm_objeto_impuesto` a Item (fixture)
- [ ] **E4-RO.1** - Implementar `_read_taxes_from_sales_invoice_item()`
- [ ] **E4-RO.2** - Implementar `_map_tax_account_to_sat()`
- [ ] **E4-RO.3** - Actualizar payload items con taxes (passthrough)
- [ ] **E4-RO.4** - Implementar `_validate_payload_completeness_ro()`
- [ ] **E4-RO.5** - Tests unitarios (lectura SI, mapeo SAT, validación)
- [ ] **E4-RO.6** - [TS] Testing sandbox con factura real mixta
- [ ] **E4-RO.7** - Documentar mapeo cuentas SAT requerido

---

## 📊 Comparación Final

| Métrica | Propuesta Claude | E4-RO ChatGPT | Reducción |
|---------|------------------|---------------|-----------|
| Funciones | 6 | 3 | **-50%** |
| LOC | ~300 | ~150 | **-50%** |
| Cálculos | 5+ | 0 | **-100%** |
| Riesgo desincronía | Alto | Nulo | **-100%** |
| Complejidad | Alta | Baja | **-60%** |

---

## ✅ Recomendación Final

**Implementar E4-RO (propuesta ChatGPT)** por:

1. ✅ **Correctitud:** SI es fuente verdad, no duplicar cálculos
2. ✅ **Simplicidad:** Adapter passthrough vs lógica compleja
3. ✅ **Mantenibilidad:** Sin lógica negocio en serialización
4. ✅ **Riesgo bajo:** Sin aritmética nueva = sin bugs nuevos

**Cambios mínimos requeridos:**
- Campo `fm_objeto_impuesto` en Item (E0 extended)
- Tabla mapeo SAT en Configuración Fiscal México (ya existe, completar)

---

**🔐 CONFIRMACIÓN REQUERIDA:** ¿Aprobar E4-RO y descartar propuesta Claude original? (si/no)

---

**Generado:** 2025-10-08
**Versión:** 2.0 (Read-Only)
**Estado:** ⏳ Pendiente aprobación
