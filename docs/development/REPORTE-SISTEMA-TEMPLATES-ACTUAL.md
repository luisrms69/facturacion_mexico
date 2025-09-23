# 📊 REPORTE AS-IS: SISTEMA TEMPLATES FISCALES MÉXICO

**Fecha:** 2025-09-22
**Audiencia:** Operador del Sistema
**Propósito:** Documentar estado actual del sistema de generación de templates fiscales

---

## 🎯 **RESUMEN EJECUTIVO**

El sistema de templates fiscales está **parcialmente implementado**. Solo genera templates básicos de IVA, pero **NO genera templates para IEPS ni retenciones**, a pesar de que el wizard permite configurarlos.

### **✅ QUÉ FUNCIONA:**
- Wizard de mapeo fiscal completo
- Generación templates IVA (16%, 8%, 0%, exento)
- Preview funcional de templates
- Mapeo manual de cuentas

### **❌ QUÉ NO FUNCIONA:**
- **Templates IEPS no se generan** (alcohol, azúcar, combustibles, tabaco)
- **Templates retenciones no se generan** (honorarios, arrendamiento, autotransporte)
- **Código excesivamente hardcodeado** (tasas, estructuras fijas)

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

## 📋 **TEMPLATES GENERADOS ACTUALMENTE**

### **Sales Tax and Charges Templates (STCT):**
✅ **IVA 16% - México - [Empresa]**
✅ **IVA 0% - México - [Empresa]** (exportación)
✅ **Sin Impuestos - México - [Empresa]** (exento)
✅ **IVA 8% Frontera - México - [Empresa]** (condicional)

### **Item Tax Templates (ITT):**
✅ **ITT IVA 16% - [Empresa]**
✅ **ITT IVA 0% - [Empresa]**
✅ **ITT Exento - [Empresa]**
✅ **ITT IVA 8% Frontera - [Empresa]** (condicional)

### **Tax Rules:**
✅ **MX General 16 - [Empresa]**
✅ **MX Zero 0 - [Empresa]**
✅ **MX Exempt - [Empresa]**
✅ **MX Border 8 - [Empresa]** (condicional)

---

## ❌ **TEMPLATES NO IMPLEMENTADOS**

### **IEPS Faltantes:**
❌ **IEPS Alcohol** - Usuario puede mapear cuenta pero no se genera template
❌ **IEPS Azúcar/Bebidas** - Usuario puede mapear cuenta pero no se genera template
❌ **IEPS Combustibles** - Usuario puede mapear cuenta pero no se genera template
❌ **IEPS Tabaco** - Usuario puede mapear cuenta pero no se genera template

### **Retenciones Faltantes:**
❌ **ISR Retenido (Honorarios)** - Usuario puede mapear cuenta pero no se genera template
❌ **IVA Retenido (Servicios Profesionales)** - Usuario puede mapear cuenta pero no se genera template
❌ **ISR Retenido (Arrendamiento)** - Usuario puede mapear cuenta pero no se genera template
❌ **IVA Retenido (Arrendamiento)** - Usuario puede mapear cuenta pero no se genera template
❌ **ISR Retenido (Autotransporte)** - Usuario puede mapear cuenta pero no se genera template
❌ **IVA Retenido (Autotransporte)** - Usuario puede mapear cuenta pero no se genera template

---

## 🔧 **UBICACIONES CRÍTICAS PARA MANTENIMIENTO**

### **Configuración de Tasas (HARDCODED):**
📍 **Archivo:** `generador_templates_fiscal.py`
📍 **Líneas:** 107-153 (templates IVA)

```python
# HARDCODED - Tasas IVA
"rate": 16.0,  # IVA General
"rate": 8.0,   # IVA Frontera
"rate": 0.0,   # IVA Exportación
```

### **Roles Fiscales:**
📍 **Archivo:** `configuracion_fiscal_mexico.py`
📍 **Líneas:** 145-197 (método `_obtener_roles_requeridos`)

### **Estructura Templates:**
📍 **Archivo:** `generador_templates_fiscal.py`
📍 **Líneas:** 107-290 (métodos `_generar_stct`, `_generar_itt`, `_generar_tax_rules`)

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