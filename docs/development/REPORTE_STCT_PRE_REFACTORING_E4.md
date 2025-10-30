# Reporte STCT Pre-Refactoring E4

**Proyecto:** Facturación México
**Fecha:** 2025-10-27
**Objetivo:** Documentar estado completo STCT generados ANTES de refactorización mapeo charge_type

---

## 📊 RESUMEN EJECUTIVO

**Total STCT generados:** 8
**Company:** _Test Company
**Total renglones:** 80 (suma todos STCT)

### ✅ Validación charge_type IEPS Cuotas

**CRÍTICO E4:** Todas las filas IEPS Cuota deben tener `charge_type="On Item Quantity"`

| STCT | Filas IEPS Cuota | charge_type | Estado |
|------|------------------|-------------|--------|
| IVA Nacional - IEPS | 3 (idx 4, 6, 10) | On Item Quantity | ✅ CORRECTO |
| IVA Nacional - Total | 3 (idx 4, 6, 10) | On Item Quantity | ✅ CORRECTO |
| IVA Frontera - IEPS | 3 (idx 4, 6, 10) | On Item Quantity | ✅ CORRECTO |
| IVA Frontera - Total | 3 (idx 4, 6, 10) | On Item Quantity | ✅ CORRECTO |

**Resultado:** ✅ 12/12 filas IEPS Cuota con charge_type correcto

---

## 📋 DETALLE POR STCT

### 1. IVA Nacional - Básico

**Total renglones:** 1
**Disabled:** No

| idx | charge_type | account_head | description | rate |
|-----|-------------|--------------|-------------|------|
| 1 | On Net Total | 123456 - iva 16% | IVA Nacional - Base (Resto) | 16.0 |

---

### 2. IVA Nacional - IEPS

**Total renglones:** 11
**Disabled:** No

| idx | charge_type | account_head | description | rate | row_id |
|-----|-------------|--------------|-------------|------|--------|
| 1 | On Net Total | 123456 - iva 16% | IVA Nacional - Base (Resto) | 16.0 | null |
| 2 | On Net Total | 2117001 - IEPS Alcohol | IEPS Alcohol - Tasa (via ITT) | 0.0 | null |
| 3 | On Previous Row Amount | 123456 - iva 16% | IVA sobre IEPS Alcohol | 16.0 | 2 |
| 4 | **On Item Quantity** ✅ | 2117002 - IEPS Azucar Bebidas | **IEPS Azúcar/Bebidas - Cuota** | 0.0 | null |
| 5 | On Previous Row Amount | 123456 - iva 16% | IVA sobre IEPS Azúcar/Bebidas | 16.0 | 4 |
| 6 | **On Item Quantity** ✅ | 2117003 - IEPS Combustibles | **IEPS Combustibles - Cuota** | 0.0 | null |
| 7 | On Previous Row Amount | 123456 - iva 16% | IVA sobre IEPS Combustibles | 16.0 | 6 |
| 8 | On Net Total | 2117004 - IEPS Tabaco | IEPS Tabaco - Tasa (via ITT) | 0.0 | null |
| 9 | On Previous Row Amount | 123456 - iva 16% | IVA sobre IEPS Tabaco (Tasa) | 16.0 | 8 |
| 10 | **On Item Quantity** ✅ | 2117005 - IEPS Tabaco Cuota | **IEPS Tabaco - Cuota** | 0.0 | null |
| 11 | On Previous Row Amount | 123456 - iva 16% | IVA sobre IEPS Tabaco (Cuota) | 16.0 | 10 |

**Filas IEPS Cuota:** 3 (idx 4, 6, 10) - ✅ Todas con `On Item Quantity`
**Filas IEPS Tasa:** 2 (idx 2, 8) - ✅ Todas con `On Net Total`
**Filas IVA cascada:** 5 (idx 3, 5, 7, 9, 11) - ✅ Todas con `On Previous Row Amount`

---

### 3. IVA Nacional - Retenciones

**Total renglones:** 9
**Disabled:** No

| idx | charge_type | account_head | description | rate |
|-----|-------------|--------------|-------------|------|
| 1 | On Net Total | 123456 - iva 16% | IVA Nacional - Base (Resto) | 16.0 |
| 2 | On Net Total | 1538403 - iva retenido serv prof | Retención IVA - Honorarios | 0.0 |
| 3 | On Net Total | 09752834 - ISR Ret honorarios | Retención ISR - Honorarios | 0.0 |
| 4 | On Net Total | 2119001 - IVA Ret Arrendamiento | Retención IVA - Arrendamiento | 0.0 |
| 5 | On Net Total | 2118001 - ISR Ret Arrendamiento | Retención ISR - Arrendamiento | 0.0 |
| 6 | On Net Total | 2119002 - IVA Ret Autotransporte | Retención IVA - Autotransporte | 0.0 |
| 7 | On Net Total | 2118002 - ISR Ret Autotransporte | Retención ISR - Autotransporte | 0.0 |
| 8 | On Net Total | 2119003 - IVA Ret RESICO | Retención IVA - RESICO | 0.0 |
| 9 | On Net Total | 2118003 - ISR Ret RESICO | Retención ISR - RESICO | 0.0 |

**Todas retenciones:** `On Net Total` con rate=0.0 (correcto - calculado por ITT)

---

### 4. IVA Nacional - Total

**Total renglones:** 19
**Disabled:** No

**Estructura:** Combina IVA base + IEPS (5 impuestos + 5 IVA cascada) + Retenciones (8)

| idx | charge_type | account_head | description | rate | row_id |
|-----|-------------|--------------|-------------|------|--------|
| 1 | On Net Total | 123456 - iva 16% | IVA Nacional - Base (Resto) | 16.0 | null |
| 2 | On Net Total | 2117001 - IEPS Alcohol | IEPS Alcohol - Tasa (via ITT) | 0.0 | null |
| 3 | On Previous Row Amount | 123456 - iva 16% | IVA sobre IEPS Alcohol | 16.0 | 2 |
| 4 | **On Item Quantity** ✅ | 2117002 - IEPS Azucar Bebidas | **IEPS Azúcar/Bebidas - Cuota** | 0.0 | null |
| 5 | On Previous Row Amount | 123456 - iva 16% | IVA sobre IEPS Azúcar/Bebidas | 16.0 | 4 |
| 6 | **On Item Quantity** ✅ | 2117003 - IEPS Combustibles | **IEPS Combustibles - Cuota** | 0.0 | null |
| 7 | On Previous Row Amount | 123456 - iva 16% | IVA sobre IEPS Combustibles | 16.0 | 6 |
| 8 | On Net Total | 2117004 - IEPS Tabaco | IEPS Tabaco - Tasa (via ITT) | 0.0 | null |
| 9 | On Previous Row Amount | 123456 - iva 16% | IVA sobre IEPS Tabaco (Tasa) | 16.0 | 8 |
| 10 | **On Item Quantity** ✅ | 2117005 - IEPS Tabaco Cuota | **IEPS Tabaco - Cuota** | 0.0 | null |
| 11 | On Previous Row Amount | 123456 - iva 16% | IVA sobre IEPS Tabaco (Cuota) | 16.0 | 10 |
| 12 | On Net Total | 1538403 - iva retenido serv prof | Retención IVA - Honorarios | 0.0 | null |
| 13 | On Net Total | 09752834 - ISR Ret honorarios | Retención ISR - Honorarios | 0.0 | null |
| 14 | On Net Total | 2119001 - IVA Ret Arrendamiento | Retención IVA - Arrendamiento | 0.0 | null |
| 15 | On Net Total | 2118001 - ISR Ret Arrendamiento | Retención ISR - Arrendamiento | 0.0 | null |
| 16 | On Net Total | 2119002 - IVA Ret Autotransporte | Retención IVA - Autotransporte | 0.0 | null |
| 17 | On Net Total | 2118002 - ISR Ret Autotransporte | Retención ISR - Autotransporte | 0.0 | null |
| 18 | On Net Total | 2119003 - IVA Ret RESICO | Retención IVA - RESICO | 0.0 | null |
| 19 | On Net Total | 2118003 - ISR Ret RESICO | Retención ISR - RESICO | 0.0 | null |

**Filas IEPS Cuota:** 3 (idx 4, 6, 10) - ✅ Todas con `On Item Quantity`

---

### 5. IVA Frontera - Básico

**Total renglones:** 1
**Disabled:** No

| idx | charge_type | account_head | description | rate |
|-----|-------------|--------------|-------------|------|
| 1 | On Net Total | 746483 - Iva 8% zona fronteriza | IVA Frontera - Base (Resto) | 8.0 |

---

### 6. IVA Frontera - IEPS

**Total renglones:** 11
**Disabled:** No

**Estructura:** Idéntica a IVA Nacional - IEPS, solo cambia tasa IVA (8% vs 16%)

| idx | charge_type | account_head | description | rate | row_id |
|-----|-------------|--------------|-------------|------|--------|
| 1 | On Net Total | 746483 - Iva 8% zona fronteriza | IVA Frontera - Base (Resto) | 8.0 | null |
| 2 | On Net Total | 2117001 - IEPS Alcohol | IEPS Alcohol - Tasa (via ITT) | 0.0 | null |
| 3 | On Previous Row Amount | 746483 - Iva 8% zona fronteriza | IVA sobre IEPS Alcohol | 8.0 | 2 |
| 4 | **On Item Quantity** ✅ | 2117002 - IEPS Azucar Bebidas | **IEPS Azúcar/Bebidas - Cuota** | 0.0 | null |
| 5 | On Previous Row Amount | 746483 - Iva 8% zona fronteriza | IVA sobre IEPS Azúcar/Bebidas | 8.0 | 4 |
| 6 | **On Item Quantity** ✅ | 2117003 - IEPS Combustibles | **IEPS Combustibles - Cuota** | 0.0 | null |
| 7 | On Previous Row Amount | 746483 - Iva 8% zona fronteriza | IVA sobre IEPS Combustibles | 8.0 | 6 |
| 8 | On Net Total | 2117004 - IEPS Tabaco | IEPS Tabaco - Tasa (via ITT) | 0.0 | null |
| 9 | On Previous Row Amount | 746483 - Iva 8% zona fronteriza | IVA sobre IEPS Tabaco (Tasa) | 8.0 | 8 |
| 10 | **On Item Quantity** ✅ | 2117005 - IEPS Tabaco Cuota | **IEPS Tabaco - Cuota** | 0.0 | null |
| 11 | On Previous Row Amount | 746483 - Iva 8% zona fronteriza | IVA sobre IEPS Tabaco (Cuota) | 8.0 | 10 |

**Filas IEPS Cuota:** 3 (idx 4, 6, 10) - ✅ Todas con `On Item Quantity`

---

### 7. IVA Frontera - Retenciones

**Total renglones:** 9
**Disabled:** No

**Estructura:** Idéntica a IVA Nacional - Retenciones, solo cambia tasa IVA base (8% vs 16%)

| idx | charge_type | account_head | description | rate |
|-----|-------------|--------------|-------------|------|
| 1 | On Net Total | 746483 - Iva 8% zona fronteriza | IVA Frontera - Base (Resto) | 8.0 |
| 2-9 | On Net Total | (varias cuentas retención) | (8 retenciones) | 0.0 |

---

### 8. IVA Frontera - Total

**Total renglones:** 19
**Disabled:** No

**Estructura:** Combina IVA base + IEPS (5 impuestos + 5 IVA cascada) + Retenciones (8)

**Filas IEPS Cuota:** 3 (idx 4, 6, 10) - ✅ Todas con `On Item Quantity`

*Detalle completo idéntico a IVA Nacional - Total, solo cambia tasa IVA a 8%*

---

## 🔍 ANÁLISIS PATRÓN CHARGE_TYPE

### Distribución charge_type por categoría

| Categoría | charge_type | Ocurrencias | Templates |
|-----------|-------------|-------------|-----------|
| **IEPS Cuota** | **On Item Quantity** ✅ | 12 | 4 (Nacional/Frontera IEPS + Total) |
| IEPS Tasa | On Net Total | 8 | 4 (Nacional/Frontera IEPS + Total) |
| IVA Base | On Net Total | 8 | Todos |
| IVA Cascada | On Previous Row Amount | 20 | 4 (Nacional/Frontera IEPS + Total) |
| Retenciones | On Net Total | 32 | 4 (Nacional/Frontera Retenciones + Total) |

**Total renglones:** 80

### Verificación E4: IEPS Cuotas

✅ **12/12 filas IEPS Cuota** tienen `charge_type="On Item Quantity"`
✅ **0 filas IEPS Cuota** con legacy `"On Net Total"` (problema Pre-E4)

**Cuentas IEPS Cuota verificadas:**
- 2117002 - IEPS Azucar Bebidas (4 ocurrencias)
- 2117003 - IEPS Combustibles (4 ocurrencias)
- 2117005 - IEPS Tabaco Cuota (4 ocurrencias)

---

## 🎯 CRITERIOS VALIDACIÓN POST-REFACTORING

Después de la refactorización, DEBE regenerarse y verificar:

### ✅ Criterio 1: Número renglones idéntico
- Cada STCT debe tener **exactamente** el mismo número de renglones
- Total global: **80 renglones**

### ✅ Criterio 2: charge_type idéntico
- Cada renglón debe conservar **exactamente** el mismo `charge_type`
- IEPS Cuota: `On Item Quantity` (12 filas)
- IEPS Tasa: `On Net Total` (8 filas)
- IVA Cascada: `On Previous Row Amount` (20 filas)
- Retenciones: `On Net Total` (32 filas)
- IVA Base: `On Net Total` (8 filas)

### ✅ Criterio 3: Metadatos idénticos
- `account_head` (debe coincidir 100%)
- `description` (debe coincidir 100%)
- `rate` (debe coincidir 100%)
- `row_id` (debe coincidir 100% para IVA cascada)
- `idx` (orden debe conservarse)

### ✅ Criterio 4: Estado templates
- Todos los STCT deben tener `disabled=0` (activos)
- Company debe ser `_Test Company`

---

## 📊 COMANDOS COMPARACIÓN POST-REFACTORING

```bash
# 1. Regenerar STCT después de refactorización
bench --site facturacion.dev execute \
  "facturacion_mexico.facturacion_fiscal.setup.generador_templates_fiscal.generate_8_stct_for_company" \
  --kwargs "{'company':'_Test Company'}"

# 2. Capturar estado post-refactoring (script similar)
bench --site facturacion.dev execute \
  "facturacion_mexico.one_offs.capturar_stct_post_refactoring.run"

# 3. Comparar JSONs (script diff)
bench --site facturacion.dev execute \
  "facturacion_mexico.one_offs.comparar_stct_pre_post_refactoring.run"
```

---

## ✅ ESTADO ACTUAL

**Fecha captura:** 2025-10-27
**Estado:** ✅ DOCUMENTADO COMPLETO
**Siguiente paso:** Implementar refactorización `utils/mapeo_charge_type.py`

**Archivos generados:**
- JSON raw: `/facturacion_mexico/one_offs/stct_pre_refactoring.json`
- Reporte markdown: Este archivo

---

**Preparado por:** Claude Code
**Versión E4:** Pre-refactorización mapeo charge_type
