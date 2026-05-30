# Propuesta E4 - Mapeo Impuestos por Concepto CFDI 4.0

**Fecha:** 2025-10-08
**Autor:** Claude Code
**Contexto:** Plan E0-E8 Implementación Fiscal México

---

## 🎯 Objetivo E4

**Enviar estructura explícita de impuestos por concepto al PAC**, reflejando exactamente los Item Tax Templates (ITT) configurados en E1-E3, eliminando dependencia de auto-cálculo FacturAPI.

---

## 📊 Análisis Situación Actual

### ✅ Lo que YA funciona (E0-E3)

1. **E0:** Campos SAT en Item (`fm_producto_servicio_sat`, `fm_unidad_sat`)
2. **E1:** ITT automatizados con Customer → Cost Center → Branch → Tax auto-assignment
3. **E2:** IEPS granular (alcohol, azúcar, combustibles, tabaco) + IVA en cascada
4. **E3:** Retenciones multi-tipo (Honorarios, Arrendamiento, Autotransporte, RESICO) con precisión 66.6667%

### ⚠️ Lo que FALTA (E4)

**Payload actual a FacturAPI** (timbrado_api.py:475-491):

```python
items.append({
    "quantity": item.qty,
    "product": {
        "description": item.description or item.item_name,
        "product_key": item_doc.fm_producto_servicio_sat or "01010101",
        "price": flt(item.rate),
        "tax_included": False,  # ← Solo indica precio sin impuestos
        "unit_key": _extract_sat_code_from_uom(item.uom),
        "unit_name": item.uom or "Pieza",
    },
})
# ❌ NO ENVÍA: Estructura "taxes" por concepto
```

**¿Por qué no rechaza el PAC?**

- `"tax_included": False` → FacturAPI **auto-calcula impuestos** basándose solo en `product_key`
- **Funciona para casos simples** (IVA 16% estándar)
- **NO refleja ITT configurados** (IEPS, retenciones, ITT 0%, ObjetoImp)

---

## 🔧 Propuesta Implementación E4

### E4.1 - Extraer Impuestos desde Item Tax Template

**Función nueva:** `_extract_taxes_from_item_tax_template(item, sales_invoice)`

**Entrada:**
- `item`: Row de Sales Invoice.items
- `sales_invoice`: Documento Sales Invoice completo

**Proceso:**

1. **Obtener ITT aplicado** al item:
   ```python
   item_tax_template = item.item_tax_template
   if not item_tax_template:
       # Sin ITT → ObjetoImp "01" (sin impuestos)
       return []

   itt_doc = frappe.get_doc("Item Tax Template", item_tax_template)
   ```

2. **Parsear taxes del ITT** (estructura ERPNext):
   ```python
   # itt_doc.taxes = [
   #   {
   #     "tax_type": "IVA 16% - Impuesto - MF",  # Account name
   #     "tax_rate": 16.0
   #   },
   #   {
   #     "tax_type": "IEPS Alcohol 26.5% - Impuesto - MF",
   #     "tax_rate": 26.5
   #   },
   #   {
   #     "tax_type": "ISR Retenido Honorarios 10% - Impuesto - MF",
   #     "tax_rate": 10.0
   #   }
   # ]
   ```

3. **Mapear a estructura FacturAPI** (según [API docs](https://www.facturapi.io/docs/api/#operation/createInvoice)):
   ```python
   taxes = []
   for tax_row in itt_doc.taxes:
       tax_info = _parse_tax_account_to_sat(tax_row)
       taxes.append({
           "type": tax_info["impuesto"],      # "IVA", "IEPS", "ISR"
           "factor": tax_info["tipo_factor"], # "Tasa", "Cuota", "Exento"
           "rate": tax_row.tax_rate / 100,    # 16.0 → 0.16
           "withholding": tax_info["retencion"]  # True/False
       })
   ```

**Salida:**
```python
# Ejemplo: Producto con IVA 16% + IEPS Alcohol 26.5% + ISR Retenido 10%
[
    {
        "type": "IVA",
        "factor": "Tasa",
        "rate": 0.16,
        "withholding": False
    },
    {
        "type": "IEPS",
        "factor": "Tasa",
        "rate": 0.265,
        "withholding": False
    },
    {
        "type": "ISR",
        "factor": "Tasa",
        "rate": 0.10,
        "withholding": True  # Es retención
    }
]
```

---

### E4.2 - Función Helper: Parsear Tax Account → SAT

**Función:** `_parse_tax_account_to_sat(tax_row)`

**Mapeo Account Name → Metadata SAT:**

```python
def _parse_tax_account_to_sat(tax_row):
    """
    Extrae metadata SAT desde account name del tax.

    Account name pattern: "{IMPUESTO} {TASA}% [{TIPO}] - Impuesto - MF"
    Ejemplos:
    - "IVA 16% - Impuesto - MF" → IVA, Tasa, 16%, No retenido
    - "ISR Retenido Honorarios 10% - Impuesto - MF" → ISR, Tasa, 10%, Retenido
    - "IEPS Alcohol 26.5% - Impuesto - MF" → IEPS, Tasa, 26.5%, No retenido

    Returns:
        {
            "impuesto": str,      # "IVA", "IEPS", "ISR"
            "tipo_factor": str,   # "Tasa", "Cuota", "Exento"
            "retencion": bool     # True si es retención
        }
    """
    account_name = tax_row.tax_type

    # Detectar tipo impuesto
    if "IVA" in account_name.upper():
        impuesto = "IVA"
    elif "IEPS" in account_name.upper():
        impuesto = "IEPS"
    elif "ISR" in account_name.upper():
        impuesto = "ISR"
    else:
        frappe.throw(f"Tipo impuesto no reconocido en: {account_name}")

    # Detectar si es retención
    retencion = "RETENIDO" in account_name.upper() or "RETENCION" in account_name.upper()

    # Tipo factor (por ahora solo "Tasa", expandir en E5 para "Cuota")
    tipo_factor = "Tasa"

    return {
        "impuesto": impuesto,
        "tipo_factor": tipo_factor,
        "retencion": retencion
    }
```

---

### E4.3 - Actualizar Payload FacturAPI

**Modificar:** `timbrado_api.py:_prepare_facturapi_data()` líneas 475-491

**Código actual:**
```python
# Items de la factura
items = []
for item in sales_invoice.items:
    item_doc = frappe.get_doc("Item", item.item_code)

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

**Código propuesto E4:**
```python
# Items de la factura
items = []
for item in sales_invoice.items:
    item_doc = frappe.get_doc("Item", item.item_code)

    # E4: Extraer impuestos desde ITT
    item_taxes = self._extract_taxes_from_item_tax_template(item, sales_invoice)

    # E4: Determinar ObjetoImp basado en existencia de impuestos
    objeto_imp = "02" if item_taxes else "01"  # 01=Sin impuestos, 02=Con impuestos

    item_payload = {
        "quantity": item.qty,
        "product": {
            "description": item.description or item.item_name,
            "product_key": item_doc.fm_producto_servicio_sat or "01010101",
            "price": flt(item.rate),
            "tax_included": False,
            "unit_key": _extract_sat_code_from_uom(item.uom),
            "unit_name": item.uom or "Pieza",
            "tax_object": objeto_imp,  # E4: ObjetoImp
        },
    }

    # E4: Solo agregar "taxes" si hay impuestos configurados
    if item_taxes:
        item_payload["product"]["taxes"] = item_taxes

    items.append(item_payload)
```

---

### E4.4 - Puntos de Revisión Payload Completo

**Checklist validación antes de enviar al PAC:**

```python
def _validate_payload_completeness(self, invoice_data, factura_fiscal, sales_invoice):
    """
    Validar que payload FacturAPI esté completo antes de enviar.

    Puntos de revisión E4 (mapeo impuestos por concepto).
    """
    errors = []

    # ===== SECCIÓN 1: DATOS CLIENTE =====
    customer_data = invoice_data.get("customer", {})

    if not customer_data.get("legal_name"):
        errors.append("❌ customer.legal_name faltante")

    if not customer_data.get("tax_id"):
        errors.append("❌ customer.tax_id (RFC) faltante")

    if not customer_data.get("tax_system"):
        errors.append("❌ customer.tax_system (régimen fiscal) faltante")

    address = customer_data.get("address", {})
    required_address_fields = ["zip", "country"]
    for field in required_address_fields:
        if not address.get(field):
            errors.append(f"❌ customer.address.{field} faltante")

    # ===== SECCIÓN 2: DATOS FACTURA =====
    if not invoice_data.get("payment_form"):
        errors.append("❌ payment_form faltante")

    if not invoice_data.get("use"):
        errors.append("❌ use (Uso CFDI) faltante")

    if not invoice_data.get("type"):
        errors.append("❌ type (Tipo Comprobante) faltante")

    # ===== SECCIÓN 3: ITEMS Y CONCEPTOS (E4 CRÍTICO) =====
    items = invoice_data.get("items", [])

    if not items:
        errors.append("❌ items[] vacío - debe tener al menos 1 concepto")

    for idx, item in enumerate(items, 1):
        product = item.get("product", {})

        # Validar campos obligatorios concepto
        if not product.get("description"):
            errors.append(f"❌ Item {idx}: product.description faltante")

        if not product.get("product_key"):
            errors.append(f"❌ Item {idx}: product.product_key (ClaveProdServ SAT) faltante")

        if not product.get("unit_key"):
            errors.append(f"❌ Item {idx}: product.unit_key (ClaveUnidad SAT) faltante")

        if item.get("quantity") is None or item.get("quantity") <= 0:
            errors.append(f"❌ Item {idx}: quantity inválida")

        if product.get("price") is None:
            errors.append(f"❌ Item {idx}: product.price faltante")

        # E4: Validar ObjetoImp
        objeto_imp = product.get("tax_object")
        if not objeto_imp:
            errors.append(f"❌ Item {idx}: product.tax_object (ObjetoImp) faltante")
        elif objeto_imp not in ["01", "02", "03", "04"]:
            errors.append(f"❌ Item {idx}: tax_object '{objeto_imp}' inválido (debe ser 01/02/03/04)")

        # E4: Validar coherencia ObjetoImp vs taxes
        item_taxes = product.get("taxes", [])

        if objeto_imp == "01" and item_taxes:
            # ObjetoImp 01 = Sin impuestos, pero tiene taxes[]
            errors.append(f"⚠️ Item {idx}: ObjetoImp '01' (sin impuestos) pero tiene {len(item_taxes)} taxes configurados")

        if objeto_imp == "02" and not item_taxes:
            # ObjetoImp 02 = Con impuestos, pero taxes[] vacío
            errors.append(f"❌ Item {idx}: ObjetoImp '02' (con impuestos) pero taxes[] vacío")

        # E4: Validar estructura taxes[] si existe
        for tax_idx, tax in enumerate(item_taxes, 1):
            if not tax.get("type"):
                errors.append(f"❌ Item {idx}, Tax {tax_idx}: type faltante")

            if tax.get("type") not in ["IVA", "IEPS", "ISR"]:
                errors.append(f"⚠️ Item {idx}, Tax {tax_idx}: type '{tax.get('type')}' no estándar")

            if not tax.get("factor"):
                errors.append(f"❌ Item {idx}, Tax {tax_idx}: factor faltante")

            if tax.get("rate") is None:
                errors.append(f"❌ Item {idx}, Tax {tax_idx}: rate faltante")

            if "withholding" not in tax:
                errors.append(f"⚠️ Item {idx}, Tax {tax_idx}: withholding no especificado (asumir False)")

    # ===== SECCIÓN 4: DOCUMENTOS RELACIONADOS (si aplica) =====
    if invoice_data.get("type") == "E":  # Tipo Egreso
        related_docs = invoice_data.get("related_documents", [])
        if not related_docs:
            errors.append("❌ Tipo 'E' (Egreso) requiere related_documents[]")
        else:
            for rel_doc in related_docs:
                if not rel_doc.get("relationship"):
                    errors.append("❌ related_documents[]: relationship faltante")
                if not rel_doc.get("uuid"):
                    errors.append("❌ related_documents[]: uuid faltante")

    # ===== RESULTADO VALIDACIÓN =====
    if errors:
        # Log todos los errores
        frappe.logger().error(f"Payload incompleto para {sales_invoice.name}:\n" + "\n".join(errors))

        # Generar mensaje usuario
        error_summary = "\n".join(errors[:5])  # Mostrar primeros 5 errores
        if len(errors) > 5:
            error_summary += f"\n... y {len(errors) - 5} errores más"

        frappe.throw(
            f"Payload FacturAPI incompleto ({len(errors)} errores):\n\n{error_summary}",
            title="Validación Payload Falló"
        )

    return True  # Payload completo ✅
```

**Llamar validación antes de enviar:**

```python
def timbrar_sales_invoice(self, sales_invoice_name: str):
    # ... código existente ...

    # Preparar datos FacturAPI
    invoice_data = self._prepare_facturapi_data(sales_invoice, factura_fiscal)

    # E4: Validar payload completo ANTES de enviar
    self._validate_payload_completeness(invoice_data, factura_fiscal, sales_invoice)

    # Enviar a FacturAPI
    response = client.create_invoice(invoice_data)
    # ...
```

---

## 📋 Casos de Prueba E4

### Caso 1: Item con IVA 16% simple
**Input:**
- Item Tax Template: "STCT IVA 16%"
- ITT.taxes: [{"tax_type": "IVA 16%", "tax_rate": 16.0}]

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

### Caso 2: Item con IEPS + IVA (cascada)
**Input:**
- Item Tax Template: "STCT IEPS Alcohol 26.5% + IVA 16%"
- ITT.taxes:
  - IEPS Alcohol 26.5%
  - IVA 16% (sobre neto + IEPS)

**Output esperado:**
```json
{
  "product": {
    "tax_object": "02",
    "taxes": [
      {"type": "IEPS", "factor": "Tasa", "rate": 0.265, "withholding": false},
      {"type": "IVA", "factor": "Tasa", "rate": 0.16, "withholding": false}
    ]
  }
}
```

---

### Caso 3: Servicios profesionales con retenciones
**Input:**
- Item Tax Template: "STCT Honorarios IVA 16% + Retenciones"
- ITT.taxes:
  - IVA 16%
  - ISR Retenido 10%
  - IVA Retenido (proporción 66.6667%)

**Output esperado:**
```json
{
  "product": {
    "tax_object": "02",
    "taxes": [
      {"type": "IVA", "factor": "Tasa", "rate": 0.16, "withholding": false},
      {"type": "ISR", "factor": "Tasa", "rate": 0.10, "withholding": true},
      {"type": "IVA", "factor": "Tasa", "rate": 0.666667, "withholding": true}
    ]
  }
}
```

**⚠️ NOTA:** Retención IVA debe enviarse como proporción del IVA trasladado (E3), NO como % del neto.

---

### Caso 4: Item sin impuestos (ITT 0%)
**Input:**
- Item Tax Template: "ITT 0% (Sin Impuestos)"
- ITT.taxes: []

**Output esperado:**
```json
{
  "product": {
    "tax_object": "01"
    // NO incluir "taxes" key
  }
}
```

---

### Caso 5: Factura mixta (items con/sin ITT)
**Input:**
- Item 1: Con ITT IVA 16%
- Item 2: Sin ITT (ObjetoImp 01)

**Output esperado:**
```json
{
  "items": [
    {
      "product": {
        "tax_object": "02",
        "taxes": [{"type": "IVA", "factor": "Tasa", "rate": 0.16, "withholding": false}]
      }
    },
    {
      "product": {
        "tax_object": "01"
        // Sin "taxes"
      }
    }
  ]
}
```

---

## 🎯 Tareas E4 (Checklist Implementación)

- [ ] **E4.1** - Implementar `_extract_taxes_from_item_tax_template()`
- [ ] **E4.2** - Implementar `_parse_tax_account_to_sat()`
- [ ] **E4.3** - Actualizar payload items con estructura "taxes"
- [ ] **E4.4** - Implementar `_validate_payload_completeness()`
- [ ] **E4.5** - Determinar ObjetoImp automático (01/02 según ITT)
- [ ] **E4.6** - Tests unitarios 5 casos (simple, IEPS, retenciones, sin ITT, mixto)
- [ ] **E4.7** - [TS] Validación PAC sandbox con factura real
- [ ] **E4.8** - Documentar mapping ITT → FacturAPI taxes structure

---

## 📊 Integración con E0-E3

**E4 depende de:**
- ✅ **E0:** Campos SAT en Item (product_key, unit_key)
- ✅ **E1:** ITT automatizados con Customer → Tax assignment
- ✅ **E2:** IEPS granular configurado en ITT
- ✅ **E3:** Retenciones multi-tipo con precisión 66.6667%

**E4 habilita:**
- 🎯 **E5:** Validación CFDI 4.0 completo pre-envío
- 🎯 **E6:** Testing PAC con validador SAT oficial
- 🎯 **E7:** Manejo errores PAC específicos por campo

---

## 🔧 Consideraciones Técnicas

### Retenciones IVA - Cálculo Especial (E3)

**Problema:** Retención IVA debe calcularse como % del IVA trasladado, NO del neto.

**Solución E4:**

```python
def _calculate_iva_retenido_rate(self, item, sales_invoice):
    """
    Calcular rate correcto para retención IVA según E3.

    Fórmula: IVA Retenido = IVA Trasladado × 66.6667%

    Returns:
        float: Rate para enviar a FacturAPI (ej: 0.666667)
    """
    # Obtener proporción desde constantes E3
    from facturacion_mexico.facturacion_fiscal.config.constantes_fiscales import (
        PROPORCION_IVA_RETENIDO_SAT
    )

    # Retornar como decimal (66.6667% → 0.666667)
    return PROPORCION_IVA_RETENIDO_SAT / 100
```

**En payload:**
```json
{
  "type": "IVA",
  "factor": "Tasa",
  "rate": 0.666667,  // ← 66.6667% del IVA trasladado
  "withholding": true
}
```

---

### Orden Impuestos (IEPS + IVA Cascada)

**Requisito SAT:** IEPS debe declararse ANTES de IVA en cascada.

**Implementación:**
```python
def _order_taxes_for_sat(self, taxes_list):
    """
    Ordenar impuestos según normativa SAT.

    Orden:
    1. IEPS (base para IVA cascada)
    2. IVA trasladado
    3. ISR retenido
    4. IVA retenido
    """
    order_priority = {
        ("IEPS", False): 1,  # IEPS trasladado
        ("IVA", False): 2,   # IVA trasladado
        ("ISR", True): 3,    # ISR retenido
        ("IVA", True): 4,    # IVA retenido
    }

    return sorted(
        taxes_list,
        key=lambda t: order_priority.get((t["type"], t["withholding"]), 99)
    )
```

---

## ⚠️ Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Mapping tax account name incorrecto | Media | Alto | Tests unitarios exhaustivos + validación strict |
| FacturAPI rechaza estructura "taxes" | Baja | Alto | Testing sandbox ANTES de producción |
| Retención IVA con rate incorrecto | Media | Crítico | Usar constantes E3 centralizadas + tests precisión |
| ObjetoImp 01/02 inconsistente | Media | Alto | Validación automática coherencia taxes[] vs ObjetoImp |
| Items sin ITT no detectados | Baja | Medio | Validación payload + logs WARNING |

---

## 📝 Siguiente Paso

**¿Proceder con implementación E4?**

1. ✅ Crear branch `feature/e4-taxes-per-concept`
2. ✅ Implementar E4.1-E4.2 (extractores ITT → SAT)
3. ✅ Actualizar payload E4.3
4. ✅ Agregar validaciones E4.4
5. ✅ Tests unitarios E4.6
6. ✅ Testing sandbox E4.7

**🔐 CONFIRMACIÓN REQUERIDA:** ¿Iniciar implementación E4 con esta propuesta? (si/no)

---

**Generado:** 2025-10-08
**Versión:** 1.0
**Estado:** ⏳ Pendiente aprobación
