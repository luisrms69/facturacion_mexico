# 📋 REPORTE EXTENSO E0.5 - TEMPLATES IMPUESTOS Y CUENTAS CONTABLES

**Fecha:** 2025-09-22
**Para:** ChatGPT continuación implementación E0.5
**Objetivo:** Configuración completa sistema fiscal mexicano (cuentas + templates)

---

## 🎯 **RESUMEN EJECUTIVO**

### ✅ **Análisis Completado**
- **Código revisado:** install.py con setup_wizard fiscal completo
- **Documentación buzola:** Migración arquitectural fiscal identificada
- **Estado actual:** 0 templates mexicanos - Setup wizard NO ejecutado
- **Gap crítico:** Sistema insuficiente para E1 (asignación automática IVA)

### 🚨 **Hallazgo Crítico**
**CONFIGURACIÓN FISCAL INSUFICIENTE** para proceder a E1:
- ❌ 0/16+ templates fiscales mexicanos configurados
- ❌ 0/13+ cuentas contables impuestos mexicanos
- ⚠️ Setup wizard fiscal disponible pero NO ejecutado

---

## 🏗️ **ARQUITECTURA FISCAL IDENTIFICADA**

### **Componentes Sistema Fiscal:**
1. **STCT** (Sales Tax and Charges Template) → Templates impuestos venta/compra
2. **ITT** (Item Tax Template) → Impuestos por producto/grupo
3. **Tax Rules** → Selección automática templates por contexto
4. **Accounts** (Tax type) → Cuentas contables impuestos

### **Flujo Diseñado:**
```
Item + ClaveProdServ → ObjetoImp → Tax Rules → STCT → Account
   ↓                     ↓            ↓         ↓        ↓
Producto              01/02/03    Contexto   Template  Cuenta
```

---

## 📊 **ANÁLISIS ESTADO ACTUAL**

### **Templates Existentes (Por Company):**
**Company Principal (_Test Company 1):**
- 🟢 Templates IVA: 0
- 🟡 Templates Retenciones: 0
- 🔵 Templates IEPS: 0
- ⚪ Otros: 3 (US ST 4%, 6%, 6.25% - no mexicanos)

**Otras Companies:**
- _Test Company 2: 9 templates alemanes (no mexicanos)
- _Test Company 3-5: 1 template Pakistan c/u (no mexicanos)

### **Cuentas Contables Impuestos:**
**Company Principal:**
- 🟢 Cuentas IVA mexicanas: 0
- 🟡 Cuentas ISR mexicanas: 0
- 🔵 Cuentas IEPS mexicanas: 0
- ⚪ Otras: 4 (Excise Duty, ST - no mexicanas)

### **Item Tax Templates:**
**Company Principal:**
- Total ITT: 7 (todos US/Excise - no mexicanos)
- Configuración: tax_rate definidos pero tax_type no mexicano

---

## 🎯 **SETUP WIZARD FISCAL IDENTIFICADO**

### **Función Principal:** `create_fiscal_setup_wizard()` en install.py

### **Capacidades Wizard:**
1. **Auto-detección** cuentas existentes con patrones inteligentes
2. **Creación automática** 13+ cuentas impuestos faltantes
3. **Generación** 16+ templates STCT comprehensivos
4. **Configuración** ITT con matching tax_type ↔ account_head

### **Templates Diseñados (16+ tipos):**

#### **🟢 VENTAS (8 templates):**
1. **IVA 16% - México** (base nacional)
2. **IVA 8% - Zona Fronteriza** (estímulo frontera)
3. **IVA 0% - Exportación** (tasa cero export)
4. **Sin Impuestos - Exento** (sin nodo impuestos)
5. **IEPS + IVA 16% - Bebidas Alcohólicas** (53% + 16% cascada)
6. **IEPS + IVA 16% - Tabaco** (160% + 16% cascada)
7. **IEPS + IVA 16% - Combustibles** (cuotas + 16% cascada)
8. **IEPS + IVA 16% - Bebidas Azucaradas** (8% + 16% cascada)

#### **🟡 RETENCIONES (8+ templates):**
1. **Honorarios - ISR 10% + IVA Ret 2/3** (profesionales)
2. **Honorarios RESICO - ISR 1.25% + IVA Ret 2/3** (régimen simplificado)
3. **Arrendamientos - ISR 10% + IVA Ret 2/3** (rentas)
4. **Autotransporte - ISR 4% + IVA Ret 4%** (transporte carga)
5. **Autotransporte RESICO - ISR 1.25% + IVA Ret 4%** (transporte RESICO)
6. **Dividendos - ISR 10%** (distribución utilidades)
7. **Intereses - ISR 10%** (rendimientos financieros)
8. **Regalías - ISR 10%** (derechos autor/patentes)

### **Cuentas Contables Diseñadas (13+ tipos):**

#### **Pasivos (Por Pagar):**
- IVA por Pagar 16%
- IVA por Pagar 8% - Zona Fronteriza
- IVA por Pagar 0%
- IEPS por Pagar
- ISR por Pagar
- ISR Retenido Honorarios
- ISR Retenido Arrendamientos
- ISR Retenido Autotransporte
- IVA Retenido Servicios Profesionales
- IVA Retenido Arrendamientos
- IVA Retenido Autotransporte

#### **Activos (Por Cobrar):**
- IVA Acreditable 16%
- IVA Acreditable 8%
- ISR Retenido a Favor

---

## 🔧 **ESTRATEGIA TÉCNICA WIZARD**

### **1. Auto-detección Cuentas:**
```python
search_patterns = {
    "iva_pagar": ["IVA", "Impuesto al Valor", "VAT", "por Pagar"],
    "isr_pagar": ["ISR", "Impuesto Sobre la Renta", "Income Tax"],
    "ieps_pagar": ["IEPS", "Impuesto Especial"],
    # ... más patrones
}
```

### **2. Creación Inteligente:**
- **Parent account detection** - Verifica Current Liabilities/Assets existe
- **Naming convention** - `[Nombre] - [Company Abbr]`
- **Account type** - Tax con configuración específica
- **Rollback safety** - Skip si ya existe, no sobreescribir

### **3. Templates IEPS Complejos:**
```python
# Ejemplo: Bebidas Alcohólicas
{
    "charge_type": "On Net Total",      # IEPS sobre base
    "account_head": "IEPS por Pagar",
    "rate": 53.0,
    "row_id": 1
},
{
    "charge_type": "On Previous Row Amount",  # IVA sobre (base + IEPS)
    "account_head": "IVA por Pagar 16%",
    "rate": 16.0,
    "row_id": 2
}
```

### **4. ITT Matching Strategy:**
- **tax_type** field debe coincidir exactamente con **account_head** del STCT
- **Ejemplo:** ITT.tax_type = "IVA por Pagar 16% - WP" = STCT.account_head
- **Validación:** Verificar existencia cuenta antes crear template

---

## ⚠️ **GAPS CRÍTICOS IDENTIFICADOS**

### **1. Setup No Ejecutado:**
- Wizard disponible pero no invocado en company principal
- Company usa templates US/alemanes no aplicables a México

### **2. Tax Rules Faltantes:**
- Sin reglas automáticas selección STCT por contexto
- Selección manual templates requerida actualmente

### **3. ITT-STCT Mapping:**
- Sin mapeo automático ITT → STCT por producto
- tax_type matching manual requerido

### **4. Validación Cruzada:**
- Sin verificación ObjetoImp (E0) ↔ Template seleccionado
- Posible inconsistencia fiscal en CFDI generado

---

## 🎯 **PLAN E0.5 DETALLADO**

### **Tareas Críticas:**

#### **E0.5.1 - Ejecutar Setup Wizard**
```python
# En company principal
from facturacion_mexico.install import create_fiscal_setup_wizard
create_fiscal_setup_wizard()
```

#### **E0.5.2 - Verificar Cuentas Creadas**
- Validar 13+ cuentas tax type configuradas
- Verificar parent accounts correctos
- Testing creación sin duplicados

#### **E0.5.3 - Validar Templates STCT**
- Confirmar 16+ templates funcionales
- Testing charge_type configuraciones
- Verificar templates IEPS cascada (tax-on-tax)

#### **E0.5.4 - Configurar ITT Base**
- Crear ITT por principales categorías producto
- Validar tax_type ↔ account_head matching
- Testing herencia Item Group → Item

#### **E0.5.5 - Templates Default Company**
- Configurar template default por company
- Establecer fallbacks inteligentes
- Documentar criterios selección

#### **E0.5.6 - Testing IEPS Complejos**
- Validar cálculo cascada IEPS + IVA
- Verificar "On Previous Row Amount" funciona
- Testing totales correctos

#### **E0.5.7 - Testing Automático**
- Suite testing selección templates
- Validación consistency ObjetoImp ↔ Template
- Performance testing con volumen

---

## 🚀 **INTEGRACIÓN CON E0/E1**

### **Post E0 (ObjetoImp por ClaveProdServ):**
- Templates deben respetar ObjetoImp desde SAT Producto Servicio
- ObjetoImp 01/03 → Templates sin impuestos o exentos
- ObjetoImp 02 → Templates con desglose correcto

### **Pre E1 (Tax Rules Automáticas):**
- STCT configurados listos para Tax Rules
- Contexto transaccional (territorio, cliente) → Template automático
- Base sólida para asignación automática IVA

### **Criterios Éxito E0.5:**
✅ 16+ templates fiscales operativos
✅ 13+ cuentas contables configuradas
✅ ITT base con tax_type matching
✅ Testing automático funcional
✅ E1 ready (Tax Rules pueden usar templates)

---

## 📂 **ARCHIVOS CLAVE REFERENCIA**

### **Implementación:**
- `facturacion_mexico/install.py` → Setup wizard fiscal completo
- `facturacion_mexico/hooks.py` → Fixtures custom fields

### **Documentación:**
- `buzola-internal/projects/facturacion_mexico/MIGRACION_ARQUITECTURAL_FISCAL_2025.md`
- `buzola-internal/projects/facturacion_mexico/install.py` (líneas 741-1484)

### **Testing:**
- `facturacion_mexico/tests/bootstrap.py` → Setup testing fiscal
- Suite E0.5 (crear nueva para templates)

---

## 💬 **SIGUIENTE PASO CHATGPT**

**Ready para implementar E0.5:**
1. **Ejecutar** setup wizard fiscal en company principal
2. **Validar** creación automática cuentas + templates
3. **Configurar** ITT base con matching correcto
4. **Testing** selección automática y cálculos
5. **Preparar** base para E1 Tax Rules automáticas

**Arquitectura fiscal completa lista para activar.**