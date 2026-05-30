> **OBSOLETO**
>
> Este documento queda archivado como referencia histórica. No representa el plan vigente ni debe usarse como fuente operativa actual.

---

# Tabla Comparativa - Generación Parcial Templates Fiscales

**Fecha:** 2025-10-25
**Propósito:** Validar sistema de generación parcial basado en checkboxes
**Commit:** Post-corrección `_verificar_mapeos_disponibles()`

---

## 📋 **Configuración Checkboxes**

### **Estado Actual Checkboxes**

| Categoría | Checkbox | Estado | Impacto Templates |
|-----------|----------|--------|-------------------|
| **IVA Nacional** | *(siempre obligatorio)* | ✅ ENABLED | IVA 16% incluido en todos los templates |
| **IVA Frontera** | `enable_frontera` | ✅ ENABLED | Templates Frontera generados |
| **IVA Exportación** | `enable_exportacion` | ✅ ENABLED | ITT IVA 0% generado |
| **IEPS Alcohol** | `enable_ieps_alcohol` | ✅ ENABLED | Fila IEPS Alcohol incluida ✅ |
| **IEPS Azúcar** | `enable_ieps_azucar` | ❌ DISABLED | Fila IEPS Azúcar **OMITIDA** ✅ |
| **IEPS Combustibles** | `enable_ieps_combustibles` | ❌ DISABLED | Fila IEPS Combustibles **OMITIDA** ✅ |
| **IEPS Tabaco** | `enable_ieps_tabaco` | ✅ ENABLED | Filas Tabaco Tasa + Cuota incluidas ✅ |
| **Ret Honorarios** | `enable_ret_honorarios` | ✅ ENABLED | Filas IVA+ISR Honorarios incluidas ✅ |
| **Ret Arrendamiento** | `enable_ret_arrendamiento` | ❌ DISABLED | Filas IVA+ISR Arrendamiento **OMITIDAS** ✅ |
| **Ret Autotransporte** | `enable_ret_autotransporte` | ❌ DISABLED | Filas IVA+ISR Autotransporte **OMITIDAS** ✅ |
| **Ret RESICO** | `enable_ret_resico` | ✅ ENABLED | Filas IVA+ISR RESICO incluidas ✅ |

---

## 📊 **Tabla Comparativa STCT (Sales Taxes and Charges Templates)**

### **1. STCT "IVA Nacional - Total"**

| # | Antes (Caso Base Completo) | Después (Generación Parcial) | Estado |
|---|---------------------------|------------------------------|--------|
| **Total filas** | **14** | **8** | ✅ Reducción 6 filas |
| 1 | IVA Nacional 16% | IVA Nacional 16% | ✅ Incluido |
| 2 | IEPS Alcohol | IEPS Alcohol | ✅ Incluido |
| 3 | IEPS Azúcar | ~~IEPS Azúcar~~ | ❌ **OMITIDO** |
| 4 | IEPS Combustibles | ~~IEPS Combustibles~~ | ❌ **OMITIDO** |
| 5 | IEPS Tabaco (tasa) | IEPS Tabaco (tasa) | ✅ Incluido |
| 6 | IEPS Tabaco (cuota) | IEPS Tabaco (cuota) | ✅ Incluido |
| 7 | IVA Retenido Honorarios | IVA Retenido Honorarios | ✅ Incluido |
| 8 | ISR Retenido Honorarios | ISR Retenido Honorarios | ✅ Incluido |
| 9 | IVA Retenido Arrendamiento | ~~IVA Retenido Arrendamiento~~ | ❌ **OMITIDO** |
| 10 | ISR Retenido Arrendamiento | ~~ISR Retenido Arrendamiento~~ | ❌ **OMITIDO** |
| 11 | IVA Retenido Autotransporte | ~~IVA Retenido Autotransporte~~ | ❌ **OMITIDO** |
| 12 | ISR Retenido Autotransporte | ~~ISR Retenido Autotransporte~~ | ❌ **OMITIDO** |
| 13 | IVA Retenido RESICO | IVA Retenido RESICO | ✅ Incluido |
| 14 | ISR Retenido RESICO | ISR Retenido RESICO | ✅ Incluido |

**Filas incluidas post-corrección:**
```
1. 123456 - iva 16% - _TC | 16.0% | On Net Total
2. 2117001 - IEPS Alcohol - _TC | 0.0% | On Net Total
3. 2117004 - IEPS Tabaco - _TC | 0.0% | On Net Total
4. 2117005 - IEPS Tabaco Cuota - _TC | 0.0% | Actual
5. 1538403 - iva retenido serv prof - _TC | 0.0% | On Net Total
6. 09752834 - ISR Ret honorarios - _TC | 0.0% | On Net Total
7. 2119003 - IVA Ret RESICO - _TC | 0.0% | On Net Total
8. 2118003 - ISR Ret RESICO - _TC | 0.0% | On Net Total
```

---

### **2. STCT "IVA Nacional - IEPS"**

| # | Antes | Después | Estado |
|---|-------|---------|--------|
| **Total filas** | **6** | **4** | ✅ Reducción 2 filas |
| 1 | IVA Nacional 16% | IVA Nacional 16% | ✅ Incluido |
| 2 | IEPS Alcohol | IEPS Alcohol | ✅ Incluido |
| 3 | IEPS Azúcar | ~~IEPS Azúcar~~ | ❌ **OMITIDO** |
| 4 | IEPS Combustibles | ~~IEPS Combustibles~~ | ❌ **OMITIDO** |
| 5 | IEPS Tabaco (tasa) | IEPS Tabaco (tasa) | ✅ Incluido |
| 6 | IEPS Tabaco (cuota) | IEPS Tabaco (cuota) | ✅ Incluido |

---

### **3. STCT "IVA Nacional - Retenciones"**

| # | Antes | Después | Estado |
|---|-------|---------|--------|
| **Total filas** | **9** | **5** | ✅ Reducción 4 filas |
| 1 | IVA Nacional 16% | IVA Nacional 16% | ✅ Incluido |
| 2 | IVA Retenido Honorarios | IVA Retenido Honorarios | ✅ Incluido |
| 3 | ISR Retenido Honorarios | ISR Retenido Honorarios | ✅ Incluido |
| 4 | IVA Retenido Arrendamiento | ~~IVA Retenido Arrendamiento~~ | ❌ **OMITIDO** |
| 5 | ISR Retenido Arrendamiento | ~~ISR Retenido Arrendamiento~~ | ❌ **OMITIDO** |
| 6 | IVA Retenido Autotransporte | ~~IVA Retenido Autotransporte~~ | ❌ **OMITIDO** |
| 7 | ISR Retenido Autotransporte | ~~ISR Retenido Autotransporte~~ | ❌ **OMITIDO** |
| 8 | IVA Retenido RESICO | IVA Retenido RESICO | ✅ Incluido |
| 9 | ISR Retenido RESICO | ISR Retenido RESICO | ✅ Incluido |

---

### **4. STCT "IVA Frontera - Total/IEPS/Retenciones"**

**Estructura idéntica** a templates Nacional pero con IVA Frontera 8%:
- **Frontera - Total:** 8 filas (mismas omisiones)
- **Frontera - IEPS:** 4 filas (mismas omisiones)
- **Frontera - Retenciones:** 5 filas (mismas omisiones)

---

## 📊 **Tabla Comparativa ITT (Item Tax Templates)**

### **Observación Importante:**

⚠️ **Los ITT se generan INDEPENDIENTEMENTE de los checkboxes.**

El generador ITT (`generate_itt_for_company()`) crea templates para TODOS los roles fiscales que tienen mapeo en `mapeo_cuentas`, sin verificar si el checkbox está habilitado.

**Comportamiento actual:**

| Template ITT | Checkbox | Mapeo Existe | ¿Se Generó? | Observación |
|--------------|----------|--------------|-------------|-------------|
| ITT IEPS Alcohol | ✅ ENABLED | ✅ Sí | ✅ Generado | Correcto |
| ITT IEPS Azúcar | ❌ DISABLED | ✅ Sí | ✅ **Generado** | ⚠️ Se generó aunque checkbox disabled |
| ITT IEPS Combustibles | ❌ DISABLED | ✅ Sí | ✅ **Generado** | ⚠️ Se generó aunque checkbox disabled |
| ITT IEPS Tabaco | ✅ ENABLED | ✅ Sí | ✅ Generado | Correcto |
| ITT Ret Honorarios | ✅ ENABLED | ✅ Sí | ✅ Generado | Correcto |
| ITT Ret Arrendamiento | ❌ DISABLED | ✅ Sí | ✅ **Generado** | ⚠️ Se generó aunque checkbox disabled |
| ITT Ret Autotransporte | ❌ DISABLED | ✅ Sí | ✅ **Generado** | ⚠️ Se generó aunque checkbox disabled |
| ITT Ret RESICO | ✅ ENABLED | ✅ Sí | ✅ Generado | Correcto |

### **ITT Generados (Total: 21)**

**IVA Básicos (5):**
- ITT IVA 0% - _TC
- ITT IVA 16% - _TC *(obsoleto - nomenclatura antigua)*
- ITT IVA 8% Frontera - _TC *(obsoleto - nomenclatura antigua)*
- ITT IVA Frontera - _TC
- ITT IVA Nacional - _TC

**IEPS (4):**
- ✅ ITT IEPS Alcohol - _TC *(checkbox enabled)*
- ⚠️ ITT IEPS Azúcar - _TC *(checkbox disabled pero generado)*
- ⚠️ ITT IEPS Combustibles - _TC *(checkbox disabled pero generado)*
- ✅ ITT IEPS Tabaco - _TC *(checkbox enabled)*

**Retenciones (8):**
- ✅ ITT ISR + IVA Ret Honorarios - _TC *(checkbox enabled)*
- ⚠️ ITT ISR + IVA Ret Arrendamiento - _TC *(checkbox disabled pero generado)*
- ⚠️ ITT ISR + IVA Ret Autotransporte - _TC *(checkbox disabled pero generado)*
- ✅ ITT ISR + IVA Ret RESICO - _TC *(checkbox enabled)*
- ITT IVA Retenido Honorarios - _TC *(individual)*
- ITT IVA Retenido Arrendamiento - _TC *(individual)*
- ITT IVA Retenido Autotransporte - _TC *(individual)*
- ITT IVA Retenido Servicios - _TC *(obsoleto)*

**Exento (1):**
- ITT Exento - _TC

---

## ✅ **Validación Corrección Implementada**

### **Función `_verificar_mapeos_disponibles()` - FUNCIONANDO CORRECTAMENTE**

**Lógica implementada:**
```python
def _disponible(checkbox_enabled: bool, rol: str) -> bool:
    """Retorna True solo si checkbox=True AND mapeo con cuenta existe."""
    return checkbox_enabled and rol in roles_disponibles
```

**Validación:**

| Caso | Checkbox | Mapeo | Resultado Esperado | Resultado Real | ✅ |
|------|----------|-------|-------------------|----------------|---|
| IEPS Alcohol | ✅ Sí | ✅ Sí | DISPONIBLE | DISPONIBLE | ✅ |
| IEPS Azúcar | ❌ No | ✅ Sí | NO DISPONIBLE | NO DISPONIBLE | ✅ |
| IEPS Combustibles | ❌ No | ✅ Sí | NO DISPONIBLE | NO DISPONIBLE | ✅ |
| IEPS Tabaco | ✅ Sí | ✅ Sí | DISPONIBLE | DISPONIBLE | ✅ |
| Ret Honorarios | ✅ Sí | ✅ Sí | DISPONIBLE | DISPONIBLE | ✅ |
| Ret Arrendamiento | ❌ No | ✅ Sí | NO DISPONIBLE | NO DISPONIBLE | ✅ |
| Ret Autotransporte | ❌ No | ✅ Sí | NO DISPONIBLE | NO DISPONIBLE | ✅ |
| Ret RESICO | ✅ Sí | ✅ Sí | DISPONIBLE | DISPONIBLE | ✅ |

**Resultado:** 8/8 casos validados correctamente ✅

---

## 📋 **Resumen Ejecutivo**

### **STCT - Generación Parcial ✅ FUNCIONANDO**

| Template | Antes | Después | Filas Omitidas |
|----------|-------|---------|----------------|
| IVA Nacional - Básico | 1 | 1 | 0 |
| IVA Nacional - IEPS | 6 | 4 | 2 (Azúcar, Combustibles) |
| IVA Nacional - Retenciones | 9 | 5 | 4 (Arrendamiento, Autotransporte × 2) |
| IVA Nacional - Total | 14 | 8 | 6 (combinado) |
| IVA Frontera - Básico | 1 | 1 | 0 |
| IVA Frontera - IEPS | 6 | 4 | 2 (Azúcar, Combustibles) |
| IVA Frontera - Retenciones | 9 | 5 | 4 (Arrendamiento, Autotransporte × 2) |
| IVA Frontera - Total | 14 | 8 | 6 (combinado) |

**Total STCT generados:** 8/8 ✅
**Total filas omitidas correctamente:** 24 filas (6 por template × 4 templates Total/IEPS/Retenciones × 2 zonas)

---

### **ITT - Genera TODOS Independientemente de Checkboxes**

**Comportamiento actual:** Generador ITT ignora checkboxes, crea template si existe mapeo.

**Decisión arquitectónica tomada:**

### **📋 Opción 3 - Mantener ITT Existentes (NO Eliminar)**

**Razón de la decisión:**
1. ✅ **Seguridad:** ITT pueden estar en uso en Sales Invoices existentes
2. ✅ **Verificación realizada:** ITT ISR + IVA Ret RESICO usado en **4 Sales Invoice Items + 1 Item**
3. ✅ **Riesgo eliminación:** Links rotos, errores runtime, documentos históricos afectados
4. ✅ **Flexibilidad:** ITT disponibles si usuario habilita checkbox después
5. ✅ **Consistencia parcial:** STCT omiten filas, ITT permanecen como referencia

**Comportamiento final implementado:**

| Acción Usuario | STCT Behavior | ITT Behavior |
|----------------|---------------|--------------|
| **Deshabilitar checkbox** | ✅ Omite filas en regeneración | ⚠️ ITT existentes NO se eliminan |
| **Habilitar checkbox** | ✅ Incluye filas en regeneración | ✅ Crea ITT si no existe |
| **Regenerar templates** | ✅ Actualiza filas según checkboxes | ✅ Crea nuevos, mantiene existentes |

**ITT que permanecen aunque checkboxes disabled:**
- ITT IEPS Azúcar (checkbox disabled, **sin uso** - seguro eliminar pero se mantiene)
- ITT IEPS Combustibles (checkbox disabled, **sin uso** - seguro eliminar pero se mantiene)
- ITT ISR + IVA Ret Arrendamiento (checkbox disabled, **sin uso**)
- ITT ISR + IVA Ret Autotransporte (checkbox disabled, **sin uso**)
- ITT ISR + IVA Ret Honorarios (checkbox disabled, **sin uso**)
- ITT ISR + IVA Ret RESICO (checkbox disabled, **⚠️ USADO en 4 SIs + 1 Item** - crítico mantener)

**Alternativas consideradas y rechazadas:**
- ❌ **Opción A - Eliminar ITT con checkbox disabled:** Rompe links en documentos existentes
- ❌ **Opción B - Limpiar referencias antes de eliminar:** Modifica SIs históricos, pérdida información fiscal
- ❌ **Opción C - Agregar campo disabled a ITT DocType:** Requiere modificar ERPNext core

---

## 🎯 **Mensaje Generación Templates**

### **Mensaje Actual Sistema:**

```
✅ Templates creados (8):
IVA Nacional - Básico - _TC
IVA Nacional - IEPS - _TC
IVA Nacional - Retenciones - _TC
IVA Nacional - Total - _TC
IVA Frontera - Básico - _TC
IVA Frontera - IEPS - _TC
IVA Frontera - Retenciones - _TC
IVA Frontera - Total - _TC

📋 Filas omitidas por template:
IVA Nacional - IEPS:
  IEPS Azúcar (cuota)
  IEPS Combustibles (cuota)

IVA Nacional - Retenciones:
  Retención IVA Arrendamiento
  Retención ISR Arrendamiento
  Retención IVA Autotransporte
  Retención ISR Autotransporte

IVA Nacional - Total:
  IEPS Azúcar (cuota)
  IEPS Combustibles (cuota)
  Retención IVA Arrendamiento
  Retención ISR Arrendamiento
  Retención IVA Autotransporte
  Retención ISR Autotransporte

[Similar para templates Frontera...]

Resumen: 8/8 templates generados, 6 templates con filas parciales.

Recomendación: Configure los mapeos faltantes en Mapeo Cuenta Fiscal Mexico
para obtener templates completos.
```

**Análisis mensaje:**
- ✅ Informa claramente templates generados
- ✅ Lista filas omitidas por template
- ✅ Resumen cuantitativo
- ⚠️ Recomendación podría confundir: dice "configure mapeos faltantes" pero los mapeos SÍ existen, solo checkboxes disabled

**Mejora sugerida:**
```
Recomendación: Para obtener templates completos, habilite los checkboxes
correspondientes en la sección Alcance Fiscal y regenere templates.
```

---

## 🔧 **Archivos Modificados**

### **generador_templates_fiscal.py (líneas 79-186)**

**Función corregida:** `_verificar_mapeos_disponibles()`

**Cambio crítico:**
```python
# ANTES (INCORRECTO):
ieps_disponibles = {
    "Azucar": _rol_existe(ROL_IEPS_AZU),  # Solo mapeo
}

# DESPUÉS (CORRECTO):
ieps_disponibles = {
    "Azucar": _disponible(config.enable_ieps_azucar, ROL_IEPS_AZU),  # Checkbox AND mapeo
}
```

**Lógica helper:**
```python
def _disponible(checkbox_enabled: bool, rol: str) -> bool:
    """Retorna True solo si checkbox=True AND mapeo con cuenta existe."""
    return checkbox_enabled and rol in roles_disponibles
```

---

## 📝 **Conclusiones**

### **Sistema Generación Parcial STCT - ✅ VALIDADO**

1. ✅ Lee checkboxes correctamente desde Configuracion Fiscal Mexico
2. ✅ Valida checkbox enabled AND mapeo existe
3. ✅ Genera templates con solo filas disponibles
4. ✅ Omite filas cuando checkbox disabled (aunque mapeo exista)
5. ✅ Mensaje detallado con filas omitidas por template
6. ✅ Idempotencia: regeneración no crea duplicados

### **Casos Uso Validados**

**Escenario 1 - Licorería (solo IEPS Alcohol):**
- Checkbox: solo `enable_ieps_alcohol` = True
- Resultado: Template "IEPS" con 2 filas (IVA + Alcohol) ✅

**Escenario 2 - Servicios Profesionales (solo Retenciones Honorarios):**
- Checkbox: solo `enable_ret_honorarios` = True
- Resultado: Template "Retenciones" con 3 filas (IVA + IVA Ret + ISR Ret) ✅

**Escenario 3 - Configuración Parcial Actual:**
- IEPS: Alcohol, Tabaco
- Retenciones: Honorarios, RESICO
- Resultado: Templates con 8 filas (6 omitidas correctamente) ✅

---

**Documentado:** 2025-10-25
**Estado:** ✅ Sistema generación parcial funcionando según especificación
**Pendiente:** Decisión sobre aplicar checkboxes a generador ITT
