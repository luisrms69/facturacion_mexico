# 📖 MANUAL DE USUARIO - WIZARD MAPEO FISCAL MÉXICO

**Versión:** E0.5
**Fecha:** 2025-09-22
**Audiencia:** Operadores de Contabilidad, Administradores Fiscales
**Propósito:** Configurar mapeo transparente de cuentas fiscales mexicanas

---

## 🎯 **¿QUÉ ES EL WIZARD DE MAPEO FISCAL?**

El Wizard de Mapeo Fiscal es una herramienta que te permite:

- **Mapear cuentas de impuestos** de tu empresa a roles fiscales mexicanos
- **Generar automáticamente** templates de impuestos (STCT/ITT/Tax Rules)
- **Configurar el alcance fiscal** de tu empresa (frontera, IEPS, retenciones)
- **Validar en tiempo real** que tu configuración sea correcta

**🚨 IMPORTANTE:** Este wizard es **obligatorio** antes de emitir facturas fiscales mexicanas.

---

## 📋 **ANTES DE COMENZAR - REQUISITOS**

### ✅ **Pre-requisitos:**

1. **Empresa creada** en ERPNext con datos mexicanos
2. **Chart of Accounts** configurado con cuentas de impuestos tipo "Tax"
3. **Permisos de usuario** como System Manager o Accounts Manager
4. **Conocimiento básico** de impuestos mexicanos (IVA, IEPS, retenciones)

### 📊 **Verificar Cuentas Tax Disponibles:**

Antes de usar el wizard, verifica que tu empresa tenga cuentas de impuestos:

1. Ve a **Contabilidad → Chart of Accounts**
2. Busca cuentas con **Account Type = "Tax"**
3. Debe haber al menos **2-3 cuentas Tax** (IVA por Pagar, IVA Retenido, etc.)

---

## 🚀 **PASO 1: ACCEDER AL WIZARD**

### **Navegación:**

1. **Menú principal** → **Facturación México**
2. Buscar **"Configuración Fiscal México"**
3. Click **"+ Nuevo"**

### **Pantalla Inicial:**

```
┌─ Configuración Fiscal México - Nueva ─────────────────┐
│                                                       │
│ Empresa: [Seleccionar Empresa]                        │
│                                                       │
│ ⚙️ ALCANCE FISCAL                                     │
│ ☐ Zona Fronteriza (IVA 8%)                          │
│ ☐ Exportación (IVA 0%)                              │
│ ☐ IEPS Alcohol                                      │
│ ☐ IEPS Azúcar/Bebidas                               │
│ ☐ IEPS Combustibles                                 │
│ ☐ IEPS Tabaco                                       │
│                                                       │
│ 🔄 RETENCIONES                                       │
│ ☐ Retenciones Honorarios                            │
│ ☐ Retenciones Arrendamiento                         │
│ ☐ Retenciones Autotransporte                        │
│                                                       │
└───────────────────────────────────────────────────────┘
```

---

## ⚙️ **PASO 2: CONFIGURAR ALCANCE FISCAL**

### **2.1 Seleccionar Empresa:**

- Elige la empresa para la cual configurarás los impuestos
- **Una configuración por empresa** (cada empresa es independiente)

### **2.2 Marcar Alcance Según Tu Empresa:**

#### **✅ Siempre Habilitar:**
- ✅ **Exportación (IVA 0%)** - La mayoría de empresas lo necesitan

#### **⚠️ Habilitar Solo Si Aplica:**

**Zona Fronteriza:**
- ✅ Solo si tu empresa tiene autorización SAT para zona fronteriza
- **IMPORTANTE:** Habilita IVA 8% SIN eliminar IVA 16% (ambos coexisten)
- Se determina por lugar de expedición (código postal), NO por domicilio cliente

**IEPS (Impuesto Especial):**
- ✅ **IEPS Alcohol** - Solo si vendes bebidas alcohólicas
- ✅ **IEPS Azúcar/Bebidas** - Solo si vendes bebidas azucaradas
- ✅ **IEPS Combustibles** - Solo si vendes gasolina/diesel
- ✅ **IEPS Tabaco** - Solo si vendes productos de tabaco

**Retenciones:**
- ✅ **Honorarios** - Si pagas servicios profesionales
- ✅ **Arrendamiento** - Si pagas rentas
- ✅ **Autotransporte** - Si pagas servicios de transporte

### **2.3 Completar Tabla de Cuentas de Impuestos:**

**🚨 CRÍTICO:** Después de seleccionar el alcance, aparecerá la tabla **"Cuentas de Impuestos"** con las filas requeridas según tu configuración.

**ANTES de guardar, debes:**
1. **Revisar cada fila** en la tabla inferior
2. **Mapear todas las cuentas** marcadas como requeridas
3. **Verificar que no hay errores** (estado rojo)

**Ejemplo con Zona Fronteriza + Retenciones Honorarios:**
```
Tabla "Cuentas de Impuestos":
• IVA por Pagar (16%)                    → [Cuenta requerida]
• IVA Exento                             → [Cuenta requerida]
• IVA por Pagar (8% frontera)           → [Cuenta requerida]
• ISR Retenido (Honorarios)             → [Cuenta requerida]
• IVA Retenido (Servicios Profesionales) → [Cuenta requerida]
```

**⚠️ NO puedes guardar si alguna cuenta obligatoria está vacía.**

---

## 🔍 **PASO 3: MAPEO DE CUENTAS (CRÍTICO)**


### **3.1 Mapeo Manual:**

Para mapear manualmente:

1. **Click en campo "Cuenta de Impuesto"**
2. **Buscar cuenta apropiada** (solo muestra cuentas Tax de tu empresa)
3. **Seleccionar cuenta correcta**
4. **Estado cambia automáticamente** a Válido/Error

### **3.2 Reglas de Mapeo:**

**✅ Permitido:**
- Usar **misma cuenta para roles diferentes** (ej. misma cuenta para IVA 16% y 0%)
- **No mapear roles opcionales** que no uses

**❌ NO Permitido:**
- **Cuentas que NO sean tipo "Tax"** (el sistema las rechaza)
- **Cuentas de otras empresas** (filtradas automáticamente)
- **Dejar sin mapear roles obligatorios** según tu alcance

---

## 👁️ **PASO 4: PREVIEW Y VALIDACIÓN**

### **4.1 Verificar Completitud:**

En la parte inferior, verifica:

```
Estado de Configuración: ✅ Configuración Completa
Última Actualización: 2025-09-22 14:30:00
Templates Generados: 0 (pendiente)
```

**🚨 Si NO dice "Configuración Completa":**
- Revisa roles obligatorios faltantes
- Completa mapeos requeridos según tu alcance

### **4.2 Preview de Templates:**

Antes de generar, puedes ver qué se creará:

1. **Click botón "👁️ Preview Templates"** (en menú Templates)
2. **Revisa lista de STCT/ITT** que se generarán en el diálogo
3. **Verifica cuentas mapeadas** en preview

**Ejemplo Preview:**
```
STCT a crear:
• IVA 16% - México - TC
• IVA 0% - México - TC
• Sin Impuestos - México - TC

ITT a crear:
• ITT IVA 16% - TC
• ITT IVA 0% - TC
• ITT Exento - TC

Mapeo cuentas:
• IVA por Pagar (16%) → IVA por Pagar - TC
• IVA por Pagar (0% exportación) → IVA Exportación - TC
```

---

## 🚀 **PASO 5: GENERAR TEMPLATES FISCALES**

### **5.1 Aplicar Configuración:**

Cuando todo esté correcto:

1. **Click "⚙️ Generar Templates"** (en menú Templates)
2. **Esperar mensaje de confirmación**
3. **Verificar cantidad de templates creados**

### **5.2 Mensaje de Éxito:**

```
✅ Se generaron/actualizaron 8 templates fiscales para Mi Empresa

Templates Generados: 8
• 3 Sales Tax Templates (STCT)
• 3 Item Tax Templates (ITT)
• 2 Tax Rules
```

### **5.3 Verificar Templates Creados:**

**STCT (Sales Taxes and Charges Template):**
- Ve a **Contabilidad → Sales Taxes and Charges Template**
- Busca templates con nombre **"MX - [Tipo] - [AbbrEmpresa]"**
- Ej: "MX - IVA 16% - México - TC"

**ITT (Item Tax Template):**
- Ve a **Contabilidad → Item Tax Template**
- Busca templates **"MX - ITT [Tipo] - [AbbrEmpresa]"**
- Ej: "MX - ITT IVA 16% - TC"

**Tax Rules:**
- Ve a **Contabilidad → Tax Rule**
- Busca reglas **"MX [Category] - [Empresa]"**
- Ej: "MX General 16 - Mi Empresa"

---

## ✅ **PASO 6: TESTING Y VALIDACIÓN**

### **6.1 Crear Factura de Prueba:**

1. **Crear Sales Invoice de prueba**
2. **Agregar items** con diferentes tipos impuestos
3. **Verificar cálculo automático** de impuestos
4. **Verificar totales correctos**

### **6.2 Scenarios de Testing:**

**Test 1 - IVA General 16%:**
- Tax Category: "General 16"
- ✅ Debe aplicar 16% automáticamente

**Test 2 - Exportación 0%:**
- Tax Category: "Zero 0"
- ✅ Debe aplicar 0% automáticamente

**Test 3 - Sin Impuestos:**
- Tax Category: "Exempt"
- ✅ No debe aplicar impuestos

### **6.3 Troubleshooting Común:**

**❌ "No se aplican impuestos automáticamente"**
- Verificar que Tax Category esté seleccionada
- Verificar que Tax Rules estén activas
- Verificar que ITT.tax_type coincida con STCT.account_head

**❌ "Cuentas contables incorrectas"**
- Re-ejecutar wizard con mapeo corregido
- Sistema es idempotente (actualiza sin duplicar)

---

## 🔄 **MANTENIMIENTO Y ACTUALIZACIONES**

### **7.1 Cambios de Alcance:**

Si tu empresa cambia de alcance (ej. empieza a vender IEPS):

1. **Editar configuración existente**
2. **Marcar nuevos checkboxes** (ej. IEPS Alcohol)
3. **Mapear nuevas cuentas** requeridas
4. **Re-ejecutar "⚙️ Generar Templates"** (en menú Templates)
5. **Sistema actualiza** sin duplicar templates existentes

### **7.2 Cambios de Cuentas:**

Si cambias de cuenta contable para un impuesto:

1. **Editar mapeo en configuración**
2. **Seleccionar nueva cuenta**
3. **Re-ejecutar wizard**
4. **Templates se actualizan** automáticamente

### **7.3 Múltiples Empresas:**

Cada empresa tiene **configuración independiente**:

- **Empresa A:** Puede tener IEPS habilitado
- **Empresa B:** Puede no tener IEPS
- **Mapeos diferentes** según Chart of Accounts de cada empresa

---

## 📞 **SOPORTE Y TROUBLESHOOTING**

### **🔧 Problemas Comunes:**

| **Problema** | **Causa** | **Solución** |
|--------------|-----------|--------------|
| No aparece en menú | Permisos insuficientes | Solicitar rol System Manager |
| No sugiere cuentas | Sin cuentas Tax | Crear cuentas tipo Tax primero |
| Error al generar | Mapeo incompleto | Completar todos los roles obligatorios |
| Templates no funcionan | Tax Categories faltantes | Re-ejecutar wizard (las crea automáticamente) |

### **📧 Reportar Issues:**

Si encuentras problemas:

1. **Capturar pantalla** del error
2. **Describir pasos** que causaron el problema
3. **Incluir empresa** y configuración usada
4. **Reportar en** sistema de tickets interno

---

## 📚 **REFERENCIAS TÉCNICAS**

### **DocTypes Involucrados:**
- **Configuracion Fiscal Mexico** - Configuración principal
- **Sales Taxes and Charges Template** - Templates impuestos ventas
- **Item Tax Template** - Templates impuestos por item
- **Tax Rule** - Reglas selección automática
- **Tax Category** - Categorías fiscales

### **Roles Fiscales Soportados:**
- IVA por Pagar (16%, 8%, 0%)
- IVA Exento
- IEPS (Alcohol, Azúcar, Combustibles, Tabaco)
- Retenciones IVA (Servicios Prof, Arrendamiento, Autotransporte)
- Retenciones ISR (Honorarios, RESICO, Autotransporte)

---

**🎯 Con este manual, cualquier operador puede configurar el mapeo fiscal de su empresa de manera transparente y sin conocimiento técnico avanzado.**

---

*📖 Manual generado para ERPNext v15 + Facturación México v5.0*
*🤖 Generated with [Claude Code](https://claude.ai/code)*