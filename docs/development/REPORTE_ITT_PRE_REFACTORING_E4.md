# Reporte ITT Pre-Refactoring E4

**Proyecto:** Facturación México
**Fecha:** 2025-10-27
**Objetivo:** Documentar estado completo ITT IEPS ANTES de refactorización mapeo charge_type

---

## 📊 RESUMEN EJECUTIVO

**Total ITT IEPS documentados:** 4
**Company:** _Test Company
**Total taxes rows:** 4 (1 por template)

### Clasificación ITT

| ITT | Tipo IEPS | tax_rate | Cuenta |
|-----|-----------|----------|--------|
| ITT IEPS Alcohol | **Tasa** | 26.5% | 2117001 - IEPS Alcohol |
| ITT IEPS Azúcar | **Cuota** | 0.0 | 2117002 - IEPS Azucar Bebidas |
| ITT IEPS Combustibles | **Cuota** | 0.0 | 2117003 - IEPS Combustibles |
| ITT IEPS Tabaco | **Tasa** | 160.0% | 2117004 - IEPS Tabaco |

**Nota:** ITT rate=0.0 para cuotas es **CORRECTO** - el cálculo es dinámico por hooks

---

## 📋 DETALLE POR ITT

### 1. ITT IEPS Alcohol - _TC

**Company:** _Test Company
**Total taxes:** 1
**Tipo IEPS:** Tasa (Porcentual)

| idx | tax_type | tax_rate |
|-----|----------|----------|
| 1 | 2117001 - IEPS Alcohol - _TC | 26.5 |

**Validación:**
✅ Tax rate correcto: 26.5% (TASAS_IEPS en constantes_fiscales.py)
✅ Tipo: Tasa porcentual (no cuota)

---

### 2. ITT IEPS Azúcar - _TC

**Company:** _Test Company
**Total taxes:** 1
**Tipo IEPS:** Cuota

| idx | tax_type | tax_rate |
|-----|----------|----------|
| 1 | 2117002 - IEPS Azucar Bebidas - _TC | 0.0 |

**Validación:**
✅ Tax rate=0.0 es **CORRECTO** para cuotas (calculado dinámicamente)
✅ Tipo: Cuota por cantidad (hooks calcular_ieps_cuota)
✅ Cuenta correcta para Bebidas Azucaradas

---

### 3. ITT IEPS Combustibles - _TC

**Company:** _Test Company
**Total taxes:** 1
**Tipo IEPS:** Cuota

| idx | tax_type | tax_rate |
|-----|----------|----------|
| 1 | 2117003 - IEPS Combustibles - _TC | 0.0 |

**Validación:**
✅ Tax rate=0.0 es **CORRECTO** para cuotas (calculado dinámicamente)
✅ Tipo: Cuota por cantidad (hooks calcular_ieps_cuota)
✅ Cuenta correcta para Combustibles

**Nota LIEPS:** Combustibles NO integran base IVA (Art. 2-A)

---

### 4. ITT IEPS Tabaco - _TC

**Company:** _Test Company
**Total taxes:** 1
**Tipo IEPS:** Tasa (Porcentual)

| idx | tax_type | tax_rate |
|-----|----------|----------|
| 1 | 2117004 - IEPS Tabaco - _TC | 160.0 |

**Validación:**
✅ Tax rate correcto: 160% (TASAS_IEPS en constantes_fiscales.py)
✅ Tipo: Tasa porcentual (no cuota)

**Nota:** Existe también "ITT IEPS Tabaco Cuota" separado (no capturado - verificar existencia)

---

## 🔍 ANÁLISIS ARQUITECTURA ITT

### Patrón ITT vs STCT

| Aspecto | ITT | STCT |
|---------|-----|------|
| **Propósito** | Override per-item | Document-level default |
| **Precedencia** | Mayor (sobrescribe STCT) | Menor (default) |
| **Rate para Cuotas** | 0.0 (hooks dinámicos) | 0.0 (hooks dinámicos) |
| **Rate para Tasas** | % fijo (TASAS_IEPS) | 0.0 (heredado de ITT) |
| **charge_type** | N/A (no aplica ITT) | Crucial E4 ("On Item Quantity") |

### Flujo IEPS Cuota

```
1. Item → tiene ITT "IEPS Azúcar" (rate=0.0)
2. Sales Invoice → carga STCT "IVA Nacional - IEPS"
3. STCT tiene fila: IEPS Azúcar - charge_type="On Item Quantity", rate=0.0
4. Hook calcular_ieps_cuota():
   - Detecta fila con cuenta 2117002
   - Obtiene cuota desde DocType "IEPS Cuota SAT" (e.g. $1.27/litro)
   - Calcula: qty × conversion_factor × cuota_unitaria
   - Setea tax_amount (NO muta charge_type en E4)
5. ERPNext calcula automáticamente con "On Item Quantity"
```

**KEY E4:** Hook NO debe mutar charge_type (deprecado líneas 348, 351 sales_invoice_ieps.py)

---

## 🚨 IMPORTANTE: ITT NO USAN charge_type

**CRÍTICO:** Item Tax Templates NO tienen campo `charge_type`

- charge_type es **exclusivo de STCT** (Sales Taxes and Charges Template)
- ITT solo tienen: `tax_type` (cuenta) + `tax_rate` (tasa/porcentaje)
- Refactorización mapeo charge_type **NO afecta ITT**
- ITT permanecen **idénticos** post-refactorización

---

## 🎯 CRITERIOS VALIDACIÓN POST-REFACTORING

### ✅ Criterio 1: ITT deben permanecer IDÉNTICOS

Después de refactorización, los 4 ITT deben tener:

| ITT | tax_type | tax_rate |
|-----|----------|----------|
| ITT IEPS Alcohol | 2117001 - IEPS Alcohol - _TC | 26.5 |
| ITT IEPS Azúcar | 2117002 - IEPS Azucar Bebidas - _TC | 0.0 |
| ITT IEPS Combustibles | 2117003 - IEPS Combustibles - _TC | 0.0 |
| ITT IEPS Tabaco | 2117004 - IEPS Tabaco - _TC | 160.0 |

**Diff esperado:** 0 cambios (ITT no afectados por refactorización)

### ✅ Criterio 2: Verificar SOLO generación STCT

La refactorización solo afecta:
- `generador_templates_fiscal.py` (función _charge_type_por_rol)
- STCT generados (no ITT)

Los ITT se regeneran con otro proceso (no afectado por E4)

---

## 📊 COMANDO COMPARACIÓN POST-REFACTORING

```bash
# 1. Capturar ITT después de refactorización
bench --site facturacion.dev execute \
  "facturacion_mexico.one_offs.capturar_itt_post_refactoring.run"

# 2. Comparar JSONs
bench --site facturacion.dev execute \
  "facturacion_mexico.one_offs.comparar_itt_pre_post_refactoring.run"
```

**Resultado esperado:** 0 diferencias (ITT no cambian)

---

## ✅ ESTADO ACTUAL

**Fecha captura:** 2025-10-27
**Estado:** ✅ DOCUMENTADO COMPLETO
**Siguiente paso:** Implementar refactorización (solo afecta STCT)

**Archivos generados:**
- JSON raw: `/facturacion_mexico/one_offs/itt_pre_refactoring.json`
- Reporte markdown: Este archivo

---

**Nota final:** La refactorización `utils/mapeo_charge_type.py` **NO modifica ITT**. Este reporte sirve como baseline para verificar que ITT permanecen intactos después del refactoring.

---

**Preparado por:** Claude Code
**Versión E4:** Pre-refactorización mapeo charge_type
