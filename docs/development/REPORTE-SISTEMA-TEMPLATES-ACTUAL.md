# 📊 REPORTE AS-IS: SISTEMA TEMPLATES FISCALES MÉXICO (POST-HITO 1)

**Fecha:** 2025-09-22 (Actualizado post-Hito 1)
**Audiencia:** Operador del Sistema
**Propósito:** Documentar estado actual del sistema de generación de templates fiscales

---

## 🎯 **RESUMEN EJECUTIVO**

El sistema de templates fiscales está **completamente funcional** tras la implementación del Hito 1. Genera templates completos para todos los tipos de impuestos mexicanos con tasas centralizadas.

### **✅ QUÉ FUNCIONA (POST-HITO 1):**
- ✅ **Wizard de mapeo fiscal completo** - Mapeo manual 100% operativo
- ✅ **Generación templates IVA** (16%, 8%, 0%, exento) - Constantes centralizadas
- ✅ **Generación templates IEPS** (alcohol, azúcar, combustibles, tabaco) + IVA cascada
- ✅ **Generación templates retenciones** (ISR/IVA honorarios, arrendamiento, autotransporte)
- ✅ **Preview funcional completo** - Dinámico según alcance real
- ✅ **Constantes centralizadas** - Zero hardcode en generador
- ✅ **Mapeo manual de cuentas** - Control total usuario

### **🔧 MEJORAS IMPLEMENTADAS HITO 1:**
- **Arquitectura modular** - Métodos especializados por tipo impuesto
- **Tax Categories automáticas** - Creación según alcance habilitado
- **Cascada IEPS → IVA** - "On Previous Row Amount" correctamente implementado
- **Retenciones como "Deduct"** - Add/Deduct correcto según tipo impuesto

---

## 🏗️ **ARQUITECTURA ACTUAL**

### **Componentes Principales:**

1. **Wizard de Configuración:**
   - `configuracion_fiscal_mexico.py` - DocType principal
   - `configuracion_fiscal_mexico.js` - Interfaz usuario
   - Permite configurar alcance: frontera, IEPS, retenciones

2. **Generador de Templates:**
   - `generador_templates_fiscal.py` - Motor de generación
   - **PROBLEMA:** Solo implementa IVA, ignora IEPS/retenciones

3. **Documentación:**
   - `MANUAL-WIZARD-MAPEO-FISCAL.md` - Manual usuario

---

## 📋 **TEMPLATES GENERADOS ACTUALMENTE (POST-HITO 1)**

### **Sales Tax and Charges Templates (STCT):**

**✅ Base IVA (4 templates):**
- **IVA 16% - México - [Empresa]** (tasa desde constantes)
- **IVA 0% - México - [Empresa]** (exportación)
- **Sin Impuestos - México - [Empresa]** (exento)
- **IVA 8% Frontera - México - [Empresa]** (condicional)

**✅ IEPS + IVA Cascada (4 templates condicionales):**
- **IEPS Alcohol + IVA - México - [Empresa]** (26.5% + 16% cascada)
- **IEPS Azúcar + IVA - México - [Empresa]** (1.0 + 16% cascada)
- **IEPS Combustibles + IVA - México - [Empresa]** (4.58 + 16% cascada)
- **IEPS Tabaco + IVA - México - [Empresa]** (160% + 16% cascada)

**✅ Retenciones (3 templates condicionales):**
- **Retenciones Honorarios - México - [Empresa]** (ISR 10% + IVA 10.67% Deduct)
- **Retenciones Arrendamiento - México - [Empresa]** (ISR 10% + IVA 10.67% Deduct)
- **Retenciones Autotransporte - México - [Empresa]** (ISR 4% + IVA 4% Deduct)

### **Item Tax Templates (ITT):**

**✅ Base IVA (4 templates):**
- **ITT IVA 16% - [Empresa]**
- **ITT IVA 0% - [Empresa]**
- **ITT Exento - [Empresa]**
- **ITT IVA 8% Frontera - [Empresa]** (condicional)

**✅ IEPS (4 templates condicionales):**
- **ITT IEPS Alcohol - [Empresa]**
- **ITT IEPS Azúcar - [Empresa]**
- **ITT IEPS Combustibles - [Empresa]**
- **ITT IEPS Tabaco - [Empresa]**

**✅ Retenciones (6 templates condicionales):**
- **ITT ISR Honorarios - [Empresa]**
- **ITT IVA Retenido Servicios - [Empresa]**
- **ITT ISR Arrendamiento - [Empresa]**
- **ITT IVA Retenido Arrendamiento - [Empresa]**
- **ITT ISR Autotransporte - [Empresa]**
- **ITT IVA Retenido Autotransporte - [Empresa]**

### **Tax Rules:**

**✅ Base + Todas las categorías según alcance (hasta 10 rules):**
- **MX General 16 - [Empresa]**
- **MX Zero 0 - [Empresa]**
- **MX Exempt - [Empresa]**
- **MX Border 8 - [Empresa]** (condicional)
- **MX IEPS Alcohol - [Empresa]** (condicional)
- **MX IEPS Azucar - [Empresa]** (condicional)
- **MX IEPS Combustibles - [Empresa]** (condicional)
- **MX IEPS Tabaco - [Empresa]** (condicional)
- **MX Retenciones Honorarios - [Empresa]** (condicional)
- **MX Retenciones Arrendamiento - [Empresa]** (condicional)
- **MX Retenciones Autotransporte - [Empresa]** (condicional)

---

## 🔧 **UBICACIONES CRÍTICAS PARA MANTENIMIENTO (POST-HITO 1)**

### **✅ Configuración de Tasas (CENTRALIZADAS):**
📍 **Archivo:** `constantes_fiscales.py` - **PUNTO ÚNICO DE VERDAD**
📍 **Secciones:** TASAS_IVA, TASAS_IEPS, TASAS_RETENCIONES
📍 **Helper functions:** `obtener_tasa()`, `obtener_configuracion_por_rol()`

```python
# ✅ CONSTANTES CENTRALIZADAS - Ejemplo
TASAS_IVA = {
    "general": {"tasa": 16.0, "descripcion": "IVA 16%", "add_deduct_tax": "Add"},
    "frontera": {"tasa": 8.0, "descripcion": "IVA Frontera 8%", "add_deduct_tax": "Add"}
}
```

### **Roles Fiscales:**
📍 **Archivo:** `configuracion_fiscal_mexico.py`
📍 **Líneas:** 145-197 (método `_obtener_roles_requeridos`)

### **✅ Generación Templates (MODULAR):**
📍 **Archivo:** `generador_templates_fiscal.py`
📍 **Métodos especializados:**
- `_obtener_templates_iva_base()` - Templates IVA base
- `_obtener_templates_ieps_cascada()` - IEPS + IVA cascada
- `_obtener_templates_retenciones()` - Retenciones ISR/IVA
- `_obtener_itt_base()`, `_obtener_itt_ieps()`, `_obtener_itt_retenciones()` - ITT por tipo

### **✅ Mapeo Rol → Configuración:**
📍 **Archivo:** `constantes_fiscales.py`
📍 **Variable:** `MAPEO_ROLES_CONFIGURACION`
📍 **Propósito:** Traducir roles wizard → configuraciones centralizadas

---

## ⚠️ **LIMITACIONES OPERATIVAS**

### **Para Cambios Fiscales:**
1. **Cambio de tasa IVA:** Requiere modificar código fuente (líneas hardcodeadas)
2. **Nueva obligación IEPS:** Requiere implementar generación completa desde cero
3. **Cambio retenciones:** Requiere implementar generación completa desde cero

### **Para Nuevas Empresas:**
1. **Solo IVA disponible:** Empresas que requieren IEPS/retenciones NO pueden usar el sistema completamente
2. **Configuración parcial:** Wizard permite mapear pero generador ignora configuración

---

## 🎯 **IMPACTO EN OPERACIONES**

### **Para Usuarios Finales:**
- ✅ **Empresas solo IVA:** Sistema funcional
- ❌ **Empresas con IEPS:** Configuración incompleta, templates faltantes
- ❌ **Empresas con retenciones:** Configuración incompleta, templates faltantes

### **Para Desarrolladores:**
- ⚠️ **Mantenimiento complejo:** Código hardcodeado dificulta actualizaciones
- ⚠️ **Inconsistencia:** Wizard vs Generador desalineados
- ⚠️ **Escalabilidad limitada:** Agregar nuevos impuestos requiere reescritura

---

## 📞 **RECOMENDACIONES INMEDIATAS**

### **Operativas (Corto Plazo):**
1. **Documentar limitación** en manual usuario
2. **Validar alcance** antes de permitir configuración IEPS/retenciones
3. **Mensaje claro** sobre templates no implementados

### **Técnicas (Mediano Plazo):**
1. **Implementar generación IEPS** completa
2. **Implementar generación retenciones** completa
3. **Parametrizar tasas** (eliminar hardcode)

---

## 📊 **MÉTRICAS ACTUALES**

| **Categoría** | **Implementado** | **Faltante** | **% Completitud** |
|---------------|------------------|--------------|-------------------|
| IVA Templates | 4/4 | 0/4 | 100% |
| IEPS Templates | 0/4 | 4/4 | 0% |
| Retenciones Templates | 0/6 | 6/6 | 0% |
| **TOTAL SISTEMA** | **4/14** | **10/14** | **29%** |

---

*📖 Reporte generado para operaciones ERPNext v15 + Facturación México v5.0*
*🤖 Generated with [Claude Code](https://claude.ai/code)*