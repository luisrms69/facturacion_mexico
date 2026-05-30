# Evaluación Cambios Sustantivos E4-RO (ChatGPT)

**Fecha:** 2025-10-08
**Revisor:** Claude Code
**Contexto:** Comparación Propuesta E4 Final vs 5 Cambios ChatGPT

---

## 📋 Resumen Evaluación

| # | Cambio | Validez | Implementable | Recomendación |
|---|--------|---------|---------------|---------------|
| 1 | Withholding por add_deduct_tax | ❌ | ❌ | **RECHAZAR** - Campo no existe |
| 2 | ObjetoImp validación estricta | ✅ | ✅ | **APROBAR** - Blindaje crítico |
| 3 | Lectura robusta item_wise_tax_detail | ✅ | ✅ | **APROBAR** - Evita falsos 0.00 |
| 4 | Validación moneda/TC | ⚠️ | ⚠️ | **APROBAR SIMPLIFICADO** |
| 5 | Hash anti-deriva | N/A | N/A | **OMITIR** - Ya cubierto |

---

## Cambio 1: Withholding por add_deduct_tax

### Propuesta ChatGPT

```python
# Determinar withholding por add_deduct_tax
if tax_row.add_deduct_tax == "Deduct":
    withholding = True
elif tax_row.add_deduct_tax == "Add":
    withholding = False
else:
    withholding = rate < 0  # Fallback
```

### ❌ Problema Crítico

**Campo `add_deduct_tax` NO EXISTE en Sales Taxes and Charges (ERPNext v15)**

```bash
# Verificado en facturacion.dev
✅ account_head: existe
✅ rate: existe
✅ tax_amount: existe
❌ add_deduct_tax: NO EXISTE
✅ charge_type: existe
```

### Investigación Alternativas

**¿Cómo saber si es retención en ERPNext v15?**

1. **Account.account_type** (mejor opción):
   ```python
   account = frappe.get_cached_doc("Account", tax.account_head)
   is_withholding = account.account_type == "Tax"  # Verificar si es expense/liability
   ```

2. **Naming convention** (actual en mi propuesta):
   ```python
   is_withholding = rate < 0  # Rate negativo = retención
   ```

3. **Configuración mapeo SAT** (más robusto):
   ```python
   # En mapeo SAT agregar campo "es_retencion"
   mapeo = get_mapeo_sat(account_head)
   is_withholding = mapeo.es_retencion
   ```

### ✅ Solución Propuesta (Mejorada)

**Usar mapeo SAT con campo `es_retencion`:**

```python
def _map_tax_account_to_sat(self, account_head):
    """Mapear cuenta → SAT incluyendo naturaleza retención."""
    config = frappe.get_single("Configuracion Fiscal Mexico")

    for mapeo in config.mapeos_cuentas_fiscales:
        if mapeo.cuenta_impuesto == account_head:
            return {
                "impuesto_sat": mapeo.impuesto_sat,
                "tipo_factor": mapeo.tipo_factor,
                "nombre_sat": mapeo.nombre_impuesto_sat,
                "es_retencion": mapeo.es_retencion  # ← NUEVO campo
            }

    frappe.throw(f"Cuenta '{account_head}' sin mapeo SAT")
```

**Ventajas:**
- ✅ Fuente única verdad (configuración)
- ✅ No depende de naming convention
- ✅ Administrable por usuario

**Desventajas:**
- ⚠️ Requiere agregar campo `es_retencion` a tabla mapeos (cambio menor)

### 🎯 Recomendación Final

**RECHAZAR propuesta ChatGPT** (campo no existe)
**IMPLEMENTAR solución mejorada** (mapeo SAT con es_retencion)

---

## Cambio 2: ObjetoImp validación estricta

### Propuesta ChatGPT

```python
# Si ObjetoImp=01/03/04 pero SI trae taxes → ERROR
if objeto_imp in ["01", "03", "04"] and item_taxes_data:
    frappe.throw(
        f"Inconsistencia: ObjetoImp '{objeto_imp}' (sin impuestos) "
        f"pero SI tiene {len(item_taxes_data)} taxes configurados"
    )

# Si ObjetoImp=02 pero SI NO trae taxes → ERROR
if objeto_imp == "02" and not item_taxes_data:
    frappe.throw(
        f"Inconsistencia: ObjetoImp '02' (con impuestos) "
        f"pero SI no tiene taxes"
    )
```

### ✅ Evaluación

**Ventajas:**
- ✅ Blindaje crítico contra inconsistencias datos
- ✅ Previene rechazos PAC por payload incoherente
- ✅ Fuerza corrección en origen (catálogo o ITT)
- ✅ Sin cálculos, solo validación

**Desventajas:**
- ⚠️ Bloquea facturación si hay desfase catálogo vs ITT
- ⚠️ Requiere mantenimiento catálogo SAT actualizado

### 🎯 Recomendación

**✅ APROBAR COMPLETAMENTE**

Esta validación es **crítica** y alineada con principio E4-RO:
- Payload debe reflejar **exactamente** SI
- No hay "arreglos" automáticos
- Errores son datos incompletos, no bugs código

---

## Cambio 3: Lectura robusta item_wise_tax_detail

### Propuesta ChatGPT

```python
def _get_tax_amount_for_item(self, tax_row, item_code, item_name, row_name):
    """
    Lectura robusta con fallback de llaves.

    Prioridad:
    1. row.name (row interno SI)
    2. item_code
    3. item_name
    """
    import json

    if not tax_row.item_wise_tax_detail:
        return 0.0

    item_wise = json.loads(tax_row.item_wise_tax_detail)

    # Intentar con row.name primero
    if row_name in item_wise:
        return float(item_wise[row_name][1])

    # Fallback a item_code
    if item_code in item_wise:
        return float(item_wise[item_code][1])

    # Fallback a item_name
    if item_name in item_wise:
        return float(item_wise[item_name][1])

    return 0.0
```

### ✅ Evaluación

**Problema Real Confirmado:**

ERPNext puede usar diferentes llaves según:
- Configuración sitio
- Versión ERPNext
- Customizaciones

**Evidencia (facturacion.dev):**
```json
{
  "item_wise_tax_detail": "{\"TEST-RET-AUTOTRANSPORTE-001\":[16.0,0.0]}"
}
```
↑ Usa `item_code` como llave

**Ventajas:**
- ✅ Evita falsos 0.00 en amounts
- ✅ Robusto contra variaciones ERPNext
- ✅ Sin cálculos, solo lectura defensiva

**Desventajas:**
- Ninguna (es solo fallback lectura)

### 🎯 Recomendación

**✅ APROBAR COMPLETAMENTE**

Mejora robustez sin agregar complejidad.

---

## Cambio 4: Moneda/TC validación

### Propuesta ChatGPT

```python
def _validate_currency_consistency(self, invoice_data, sales_invoice):
    """Validar que payload use misma moneda que SI."""

    payload_currency = invoice_data.get("currency")
    si_currency = sales_invoice.currency

    if payload_currency != si_currency:
        frappe.throw(
            f"Moneda inconsistente: "
            f"Payload={payload_currency}, SI={si_currency}"
        )

    # Si SI tiene conversion_rate, solo confirmar (NO convertir)
    if sales_invoice.conversion_rate != 1.0:
        frappe.logger().info(
            f"SI {sales_invoice.name} con TC={sales_invoice.conversion_rate}, "
            f"amounts ya convertidos"
        )
```

### ⚠️ Evaluación

**Problema Real:**
- FacturAPI espera moneda consistente
- SI multimoneda puede causar rechazos

**Ventajas:**
- ✅ Previene rechazos PAC por moneda
- ✅ Sin conversiones (solo validación)

**Desventajas:**
- ⚠️ FacturAPI maneja su propia moneda en payload
- ⚠️ Validación puede ser redundante

### 🎯 Recomendación

**✅ APROBAR SIMPLIFICADO**

Validar solo que:
1. Payload currency = SI currency
2. Log warning si hay TC != 1.0 (informativo)

**NO validar:**
- Mezcla monedas por línea (ERPNext no lo permite)
- Conversiones (SI ya las hizo)

---

## Cambio 5: Hash anti-deriva

### Propuesta ChatGPT

```python
# Guardar hash SI en FFM
def _calculate_si_hash(self, sales_invoice):
    import hashlib
    fields = [
        sales_invoice.name,
        sales_invoice.modified,
        sales_invoice.grand_total
    ]
    return hashlib.md5(str(fields).encode()).hexdigest()
```

### N/A - Ya Cubierto

**Usuario confirmó:** "el punto 5 no aplica, ya esta cubierto en el sistema"

### 🎯 Recomendación

**OMITIR** - No implementar (ya existe mecanismo)

---

## 📊 Resumen Final Cambios

### ✅ Aprobar (3 de 5)

**Cambio 2 - ObjetoImp validación estricta:**
```python
if objeto_imp in ["01", "03", "04"] and item_taxes_data:
    frappe.throw("Inconsistencia: ObjetoImp sin impuestos pero SI tiene taxes")

if objeto_imp == "02" and not item_taxes_data:
    frappe.throw("Inconsistencia: ObjetoImp con impuestos pero SI sin taxes")
```

**Cambio 3 - Lectura robusta item_wise_tax_detail:**
```python
# Fallback: row.name → item_code → item_name
for key in [row_name, item_code, item_name]:
    if key in item_wise:
        return float(item_wise[key][1])
```

**Cambio 4 - Validación moneda (simplificada):**
```python
if invoice_data.get("currency") != sales_invoice.currency:
    frappe.throw("Moneda inconsistente payload vs SI")
```

### ❌ Rechazar (1 de 5)

**Cambio 1 - Withholding por add_deduct_tax:**
- Campo no existe en ERPNext v15
- **Solución alternativa:** Usar mapeo SAT con campo `es_retencion`

### N/A Omitir (1 de 5)

**Cambio 5 - Hash anti-deriva:**
- Ya cubierto en sistema

---

## 🔧 Cambios Menores Requeridos

### 1. Agregar campo a Mapeo SAT

**Tabla:** Configuración Fiscal México → mapeos_cuentas_fiscales

**Campo nuevo:**
```json
{
  "fieldname": "es_retencion",
  "fieldtype": "Check",
  "label": "Es Retención",
  "description": "Marcar si es impuesto retenido (withholding)"
}
```

**Justificación:**
- Reemplaza inferencia por `add_deduct_tax` (que no existe)
- Fuente única verdad para naturaleza impuesto
- Administrable por usuario

---

## ✅ Decisión Final

**Aprobar cambios 2, 3, 4 (simplificado)**
**Rechazar cambio 1** → Implementar solución alternativa (mapeo SAT)
**Omitir cambio 5** → Ya cubierto

**Modificaciones mínimas:**
- Agregar campo `es_retencion` a mapeos SAT (1 campo)
- Implementar validaciones aprobadas (código sin cálculos)

---

**🔐 CONFIRMACIÓN REQUERIDA:** ¿Aprobar esta evaluación e incorporar cambios 2, 3, 4 + solución alternativa cambio 1? (si/no)

---

**Generado:** 2025-10-08
**Versión:** 1.0
**Estado:** ⏳ Pendiente aprobación
