# Reporte Verificación Pre-Regeneración E3 Retenciones

**Fecha:** 2025-10-08
**Contexto:** Verificación antes de regenerar templates con fix signos retenciones
**Facturas analizadas:** ACC-SINV-2025-01583, ACC-SINV-2025-01584

---

## 🔍 Objetivo

Verificar que el fix de signos negativos en ITT retenciones:
1. ✅ Resuelve problema retenciones (deben restar, no sumar)
2. ✅ No rompe funcionalidad E2 IEPS existente

---

## 📊 ACC-SINV-2025-01583 - Retenciones Honorarios (Problema Detectado)

### Configuración
- **Customer:** CONCESIONARIA VUELA COMPAÑIA DE AVIACION
- **Company:** _Test Company
- **Zona:** Frontera (IVA 8%)
- **Item:** TEST-RET-HONORARIOS-001 ($1,000)
- **ITT:** ITT ISR + IVA Ret Honorarios - _TC

### Cálculo Actual (INCORRECTO)

```
Subtotal:              1,000.00
+ IVA 8%:                 80.00   ✓ Correcto
+ Ret IVA:               +53.34   ❌ SUMA (debería RESTAR)
+ Ret ISR:              +100.00   ❌ SUMA (debería RESTAR)
─────────────────────────────────
Grand Total:          1,233.34   ❌ INCORRECTO
```

### Problema Identificado

**Las retenciones tienen signo POSITIVO y SUMAN al total en lugar de RESTAR.**

- Row 10 (Ret IVA): `tax_amount = +53.34` (debería ser `-53.34`)
- Row 11 (Ret ISR): `tax_amount = +100.00` (debería ser `-100.00`)

### Causa Raíz

ERPNext usa el **signo del rate en ITT** para determinar si suma o resta:
- Rate positivo → SUMA
- Rate negativo → RESTA

**ITT actual (incorrecto):**
```python
# generador_templates_fiscal.py línea 554-555 (ANTES del fix)
{"rol_fiscal": cfg["rol_isr"], "tax_rate": cfg["tasa_isr"]},  # 10.0 ← POSITIVO
{"rol_fiscal": cfg["rol_iva"], "tax_rate": cfg["proporcion_iva_retenido"]},  # 66.67 ← POSITIVO
```

### Fix Aplicado

**ITT corregido (después del fix):**
```python
# generador_templates_fiscal.py línea 557-558 (DESPUÉS del fix)
{"rol_fiscal": cfg["rol_isr"], "tax_rate": -1 * cfg["tasa_isr"]},  # -10.0 ← NEGATIVO
{"rol_fiscal": cfg["rol_iva"], "tax_rate": -1 * cfg["proporcion_iva_retenido"]},  # -66.67 ← NEGATIVO
```

### Resultado Esperado (después de regenerar)

```
Subtotal:              1,000.00
+ IVA 8%:                 80.00
- Ret IVA:               -53.34   ✓ RESTA
- Ret ISR:              -100.00   ✓ RESTA
─────────────────────────────────
Grand Total:             926.66   ✓ CORRECTO
```

### Verificación Proporcional

**IVA Trasladado:** 80.00
**2/3 del IVA (esperado):** 53.33
**Ret IVA (actual):** 53.34
**Diferencia:** 0.01 (redondeo aceptable)

✅ **Proporción 2/3 correcta** (aunque con signo equivocado)

---

## 📊 ACC-SINV-2025-01584 - IEPS Cascada (Sin Problemas)

### Configuración
- **Customer:** CONCESIONARIA VUELA COMPAÑIA DE AVIACION
- **Company:** _Test Company
- **Zona:** Frontera (IVA 8%)
- **Items:**
  - TEST-IEPS-TABACO-001 ($100)
  - TEST-IEPS-COMBUSTIBLES-002 ($25)
  - TEST-IEPS-AZUCAR-001 ($20)
  - TEST-IEPS-ALCOHOL-002 ($35)

### Cálculo Verificado

```
Subtotal:                    180.00

IEPS:
  Alcohol (26.5%):             9.28
  Azúcar (1 peso/L):           0.20
  Combustibles (4.58):         1.14
  Tabaco (160%):             160.00
                            ───────
  Total IEPS:                170.62

IVA sobre IEPS (8%):
  Alcohol:                     0.74  ✓ (9.28 × 8%)
  Azúcar:                      0.02  ✓ (0.20 × 8%)
  Combustibles:                0.09  ✓ (1.14 × 8%)
  Tabaco:                     12.80  ✓ (160.00 × 8%)
                            ───────
  Total IVA/IEPS:             13.65

IVA base (8% neto):           14.40  ✓ (180 × 8%)
─────────────────────────────────────
Grand Total:                 378.67  ✓ CORRECTO
```

### Verificación Cascadas IEPS → IVA

| IEPS | Monto IEPS | IVA Esperado (8%) | IVA Actual | ✓ |
|------|------------|-------------------|------------|---|
| Alcohol | 9.28 | 0.74 | 0.74 | ✅ |
| Azúcar | 0.20 | 0.02 | 0.02 | ✅ |
| Combustibles | 1.14 | 0.09 | 0.09 | ✅ |
| Tabaco | 160.00 | 12.80 | 12.80 | ✅ |

**Todos los pares IEPS → IVA funcionando correctamente.**

### Conclusión E2 IEPS

✅ **E2 IEPS NO AFECTADO POR FIX DE RETENCIONES**

- Cascadas IEPS → IVA funcionan correctamente
- Cálculos proporcionalen zona frontera (8%) correctos
- Ningún impacto del cambio en `_obtener_itt_retenciones()`

---

## 🔧 Cambio Aplicado en Código

### Archivo Modificado

`/home/erpnext/frappe-bench/apps/facturacion_mexico/facturacion_mexico/facturacion_fiscal/setup/generador_templates_fiscal.py`

### Función Modificada

`_obtener_itt_retenciones()` (líneas 537-607)

### Cambio Específico

**ANTES:**
```python
configs.append({
    "title": "ITT ISR + IVA Ret Honorarios",
    "taxes": [
        {"rol_fiscal": cfg["rol_isr"], "tax_rate": cfg["tasa_isr"]},  # 10.0
        {"rol_fiscal": cfg["rol_iva"], "tax_rate": cfg["proporcion_iva_retenido"]},  # 66.67
    ],
})
```

**DESPUÉS:**
```python
configs.append({
    "title": "ITT ISR + IVA Ret Honorarios",
    "taxes": [
        {"rol_fiscal": cfg["rol_isr"], "tax_rate": -1 * cfg["tasa_isr"]},  # -10.0
        {"rol_fiscal": cfg["rol_iva"], "tax_rate": -1 * cfg["proporcion_iva_retenido"]},  # -66.67
    ],
})
```

**Comentario agregado:**
```python
"""
IMPORTANTE: Tasas deben ser NEGATIVAS porque son retenciones (deducción).
ERPNext usa el signo del rate para determinar si suma o resta.
"""
```

### Alcance del Cambio

Aplica a **4 tipos de retenciones:**
1. ✅ Honorarios (Servicios Profesionales)
2. ✅ Arrendamiento
3. ✅ Autotransporte
4. ✅ RESICO

---

## ✅ Checklist Pre-Regeneración

- [x] Fix aplicado en código
- [x] Problema retenciones confirmado (signos positivos)
- [x] E2 IEPS verificado funcional (no afectado)
- [x] Proporción 2/3 IVA confirmada correcta
- [x] Zona frontera (8%) confirmada funcional
- [x] Documentación actualizada

---

## 🚀 Siguiente Paso

**REGENERAR TEMPLATES DESDE UI**

1. Ir a: Configuracion Fiscal Mexico → "_Test Company"
2. Click: "Generar Templates Fiscales"
3. Esperar: Templates regenerados con tasas negativas
4. Probar: Nueva factura retenciones honorarios

**Resultado Esperado:**
- Grand Total = 926.66 (en lugar de 1,233.34)
- Retenciones con signo negativo (restan del total)
- E2 IEPS sin cambios (funcionando normal)

---

**Generado:** 2025-10-08
**Autor:** Claude Code
**Versión:** 1.0
