# Reporte E4 - Análisis item_tax_rate Vacío

**Fecha:** 2025-10-09
**Caso:** Sales Invoice ACC-SINV-2025-01596
**Item:** Servicio E2E Test
**Error:** Validación E4.6 - "Sales Invoice NO tiene impuestos configurados"

---

## 📋 Hallazgos

### 1. Configuración Item

**Item:** Servicio E2E Test
- ✅ **Item Tax Template (Item level):** SÍ configurado → "Mexico Tax - TCCS"
- ❌ **Item Group:** "_Test Item Group B - 3" NO tiene ITT configurado
- ✅ **ClaveProdServ:** 81112000 (ObjetoImp "02" - sí objeto de impuesto)

### 2. Sales Invoice - Tax Application

**SI:** ACC-SINV-2025-01596
- **Company:** _Test Company
- **Taxes and Charges Template:** "IVA 16% - México - _TC" (default por ubicación branch)
- **Customer Tax Category:** None

**Taxes aplicados:**
- ✅ IVA 16% aplicado: $80.00 (16% sobre $500.00)
- ✅ `sales_invoice.taxes` contiene el tax con amount correcto
- ❌ `item.item_tax_rate` = `{}` (VACÍO)

### 3. Causa Raíz

**Configuración STCT (Smart Tax Category Template) actual:**
- Item NO tiene ITT por defecto (correcto - sin asumir)
- Item Group NO tiene ITT (correcto - sin asumir)
- **Template aplicado:** Por ubicación branch/company → "IVA 16% - México - _TC"

**Comportamiento ERPNext:**
- Cuando ITT está en **Item master** pero NO se selecciona explícitamente en SI:
  - ERPNext aplica taxes desde **Sales Taxes and Charges Template** (global)
  - Llena `sales_invoice.taxes[]` con amounts correctos
  - **NO llena** `item.item_tax_rate` (queda vacío `{}`)

**Resultado:**
- ✅ Impuestos SÍ están calculados y aplicados correctamente
- ✅ Totales SI correctos ($500 + $80 = $580)
- ❌ E4.1 no puede leer impuestos porque depende de `item.item_tax_rate`

---

## ✅ Confirmaciones

### Confirmación 1: Configuración Item correcta
**SÍ, es correcta.**

Razones:
1. ✅ Item NO debe tener ITT por defecto (evita asumir)
2. ✅ Item Group NO debe tener ITT (evita asumir)
3. ✅ Sistema STCT permite configuración granular cuando se requiera
4. ✅ Aplicación de taxes por ubicación branch es el comportamiento esperado

### Confirmación 2: Fallback depende de ubicación emisor
**SÍ, depende de ubicación.**

Flujo actual:
1. Item sin ITT explícito
2. ERPNext busca **Sales Taxes and Charges Template** default
3. Template default determinado por:
   - Company
   - Branch/Address location
   - Tax Category (customer)
4. Template aplicado: "IVA 16% - México - _TC"

**Esto es lógica ERPNext estándar y es correcta.**

---

## 🔧 Propuesta Solución

### Problema Técnico

**E4.1** `_read_taxes_from_sales_invoice_item()` línea 1512-1513:

```python
if not item.item_tax_rate:
    return []  # ❌ Retorna vacío, no busca alternativa
```

**Casos donde `item.item_tax_rate` está vacío:**
1. Item sin ITT explícito
2. Taxes aplicados desde Sales Taxes and Charges Template global
3. ERPNext calculó correctamente pero NO llenó `item.item_tax_rate`

### Solución Propuesta: Fallback a `item_wise_tax_detail`

**Modificar E4.1** para agregar fallback cuando `item_tax_rate` vacío:

```python
def _read_taxes_from_sales_invoice_item(self, item, sales_invoice):
    """
    E4.1: Leer impuestos de un item desde Sales Invoice.

    FUENTES (prioridad):
    1. item.item_tax_rate (cuando ITT explícito)
    2. FALLBACK: sales_invoice.taxes con item_wise_tax_detail (template global)
    """
    import json

    # INTENTO 1: Leer desde item.item_tax_rate (ITT explícito)
    if item.item_tax_rate:
        item_tax_rate = json.loads(item.item_tax_rate)

        taxes_data = []
        for account_head, rate in item_tax_rate.items():
            amount = self._get_tax_amount_for_item_robust(
                sales_invoice,
                account_head,
                item.item_code,
                item.item_name,
                item.name
            )

            taxes_data.append({
                "account_head": account_head,
                "rate": rate,
                "amount": amount
            })

        return taxes_data

    # FALLBACK: Leer desde sales_invoice.taxes (template global aplicado)
    # Caso: Item sin ITT pero taxes aplicados por ubicación/branch
    taxes_data = []

    for tax in sales_invoice.taxes:
        if not tax.item_wise_tax_detail:
            continue

        # Parse item_wise_tax_detail
        item_wise = json.loads(tax.item_wise_tax_detail)

        # Buscar este item con fallback de llaves (Cambio 3)
        amount = 0.0
        rate = 0.0

        for key in [item.name, item.item_code, item.item_name]:
            if key in item_wise:
                rate = float(item_wise[key][0])  # Position 0 = rate
                amount = float(item_wise[key][1])  # Position 1 = amount
                break

        # Solo agregar si hay rate o amount > 0
        if rate != 0 or amount != 0:
            taxes_data.append({
                "account_head": tax.account_head,
                "rate": rate,
                "amount": amount
            })

    return taxes_data
```

**Beneficios:**
1. ✅ Soporta ITT explícito (prioridad)
2. ✅ Soporta taxes por template global (fallback)
3. ✅ Mantiene E4-RO (solo lectura, sin cálculos)
4. ✅ Compatible con lógica STCT actual
5. ✅ Usa lectura robusta existente (Cambio 3)

---

## 🎨 Mejora Formato Mensajes Validación

### Problema Actual

**Mensaje E4.6** (líneas 1688-1704 timbrado_api.py):

```python
frappe.throw(
    f"Inconsistencia datos item '{item.item_code}':\n"
    f"• ObjetoImp: '02' (sí objeto de impuesto)\n"
    f"• Sales Invoice NO tiene impuestos configurados\n\n"
    f"Corrija:\n"
    f"1. Si el item causa impuestos → Configurar Item Tax Template\n"
    f"2. Si el item NO causa impuestos → Actualizar catálogo SAT a ObjetoImp '01'",
    title="Inconsistencia ObjetoImp vs Impuestos"
)
```

**Problema:** Formato texto plano, difícil de leer en UI.

### Propuesta: Formato HTML/Markdown

```python
frappe.throw(
    _("""
    <div style="padding: 10px;">
        <h4 style="margin-top: 0;">❌ Inconsistencia Datos Fiscales</h4>

        <p><strong>Item:</strong> {item_code} - {item_name}</p>

        <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 10px 0;">
            <p style="margin: 5px 0;"><strong>ObjetoImp (Catálogo SAT):</strong> 02 - Sí objeto de impuesto</p>
            <p style="margin: 5px 0;"><strong>Sales Invoice:</strong> Sin impuestos configurados</p>
        </div>

        <h5>🔧 Soluciones:</h5>
        <ol style="margin-top: 5px;">
            <li><strong>Si el item causa impuestos:</strong><br>
                Configurar Item Tax Template en el Item o seleccionarlo al crear Sales Invoice</li>
            <li><strong>Si el item NO causa impuestos:</strong><br>
                Actualizar catálogo SAT Producto Servicio a ObjetoImp '01' (No objeto de impuesto)</li>
        </ol>

        <p style="margin-top: 15px; color: #6c757d; font-size: 0.9em;">
            <strong>Referencia:</strong> CFDI 4.0 c_ObjetoImp - SAT Anexo 20
        </p>
    </div>
    """).format(
        item_code=item.item_code,
        item_name=item.item_name or item.description
    ),
    title=_("Validación Fiscal CFDI 4.0"),
    as_list=False
)
```

**Alternativa Markdown (más simple):**

```python
msg = f"""
### ❌ Inconsistencia Datos Fiscales

**Item:** {item.item_code} - {item.item_name}

---

**Problema Detectado:**
- 🏷️ **ObjetoImp (Catálogo SAT):** `02` - Sí objeto de impuesto
- 📄 **Sales Invoice:** Sin impuestos configurados

---

### 🔧 Soluciones

1. **Si el item causa impuestos:**
   - Configurar Item Tax Template en el Item master
   - O seleccionarlo manualmente al crear Sales Invoice

2. **Si el item NO causa impuestos:**
   - Actualizar catálogo SAT Producto Servicio
   - Cambiar ObjetoImp a `01` (No objeto de impuesto)

---

📘 **Referencia:** CFDI 4.0 c_ObjetoImp - SAT Anexo 20
"""

frappe.throw(
    msg,
    title="Validación Fiscal CFDI 4.0"
)
```

---

## 📊 Resumen Propuestas

| Componente | Cambio | Beneficio |
|------------|--------|-----------|
| **E4.1** | Fallback a `item_wise_tax_detail` | Soporta taxes por template global |
| **E4.6** | Formato HTML/Markdown | Mensajes más claros y profesionales |
| **E4.6** | Item code + name en mensaje | Identificación precisa del problema |
| **E4.6** | Referencia SAT | Contexto normativo |

---

## ⚠️ Consideraciones

### Validación Fallback

**Pregunta:** ¿Debemos validar que taxes leídos desde fallback sean consistentes?

**Escenarios:**
1. ✅ **Template global con IVA 16%** → Leer y serializar (OK)
2. ⚠️ **Template con múltiples taxes condicionales** → Algunos en 0%, otros aplicados
3. ⚠️ **Item con descuento especial** → Tax amount no proporcional

**Recomendación:** Confiar en ERPNext. Si `item_wise_tax_detail` tiene valores, son correctos.

### Orden de Prioridad Fuentes

```
1. item.item_tax_rate (ITT explícito) ← PRIORIDAD
2. sales_invoice.taxes + item_wise_tax_detail (template global) ← FALLBACK
```

**No mezclar:** Si `item_tax_rate` tiene datos, NO usar fallback.

---

## ✅ Siguiente Paso

**Pendiente autorización para:**
1. Implementar fallback E4.1
2. Mejorar formato mensajes E4.6 (¿HTML o Markdown?)
3. Testing con SI ACC-SINV-2025-01596

---

**Generado:** 2025-10-09
**Versión:** 1.0
