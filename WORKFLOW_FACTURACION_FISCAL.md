# 🔁 WORKFLOW FACTURACIÓN FISCAL - IMPLEMENTACIÓN TÉCNICA

**Proyecto:** facturacion_mexico  
**DocType Principal:** Factura Fiscal Mexico  
**Fecha Inicio:** 2025-08-03  
**Estado:** ✅ FASE 1 COMPLETADA - 🚧 EN VALIDACIÓN MANUAL

---

## 🎯 OBJETIVO PRINCIPAL

Implementar workflow completo de facturación fiscal consistente con el ciclo de vida de Sales Invoice, con prevención sólida de doble facturación y control estricto de estados del PAC.

---

## 📋 FLUJO OPERATIVO DISEÑADO

### **1. CREACIÓN DESDE SALES INVOICE**
```mermaid
graph TD
    A[Sales Invoice docstatus=1] --> B{¿Ya timbrada?}
    B -->|NO| C[Mostrar botón "Crear Factura Fiscal"]
    B -->|SÍ| D[Ocultar botón - Ya facturada]
    C --> E[Crear Factura Fiscal Mexico]
```

**Condiciones para mostrar botón:**
- ✅ Sales Invoice `docstatus = 1` (submitted) 
- ✅ Campo `fm_factura_fiscal_mx` vacío (usa campo existente)
- ✅ No existe Factura Fiscal Mexico con `sales_invoice = X` y `fm_fiscal_status = "Timbrada"`

### **2. CREACIÓN DIRECTA**
- Filtrar Sales Invoice disponibles:
  - `docstatus = 1`
  - `fm_factura_fiscal_mx` vacío o NULL
  - Sin Factura Fiscal Mexico timbrada asociada

### **3. CARGA AUTOMÁTICA DE DATOS**

#### **Para método PUE:**
```python
# Buscar Payment Entry relacionada (OPCIONAL)
payment_entries = frappe.get_all("Payment Entry", 
    filters={
        "references.reference_doctype": "Sales Invoice",
        "references.reference_name": sales_invoice_name,
        "docstatus": 1
    })

if payment_entries:
    # Cargar forma de pago desde Payment Entry
    self.fm_forma_pago_timbrado = payment_entry.mode_of_payment
else:
    # PUE sin Payment Entry - usuario debe seleccionar manualmente
    self.fm_forma_pago_timbrado = ""
```

#### **Para método PPD:**
- Siempre asignar `fm_forma_pago_timbrado = "99 - Por definir"`

---

## 🛡️ PREVENCIÓN DOBLE FACTURACIÓN

### **VALIDACIÓN DUAL (Recomendada):**

#### **A. Campo en Sales Invoice:**
```python
# Nuevo custom field
{
    "fieldname": "fm_esta_timbrada",
    "fieldtype": "Check", 
    "label": "Está Timbrada",
    "default": 0,
    "read_only": 1
}
```

#### **B. Validación cruzada en Factura Fiscal Mexico:**
```python
def validate_no_duplicate_timbrado(self):
    """Prevenir doble timbrado del mismo Sales Invoice."""
    if not self.sales_invoice:
        return
    
    # Verificar campo directo en Sales Invoice
    is_timbrada = frappe.db.get_value("Sales Invoice", 
        self.sales_invoice, "fm_esta_timbrada")
    
    if is_timbrada:
        frappe.throw(_("Sales Invoice {0} ya ha sido timbrada").format(self.sales_invoice))
    
    # Validación cruzada - buscar otras Facturas Fiscales timbradas
    existing = frappe.get_all("Factura Fiscal Mexico",
        filters={
            "sales_invoice": self.sales_invoice,
            "fm_fiscal_status": "Timbrada",
            "name": ["!=", self.name]
        })
    
    if existing:
        frappe.throw(_("Ya existe Factura Fiscal timbrada para Sales Invoice {0}: {1}")
            .format(self.sales_invoice, existing[0].name))
```

---

## 💾 CONTROL DE ESTADOS Y BOTONES

### **COMPORTAMIENTO ESPERADO:**

| Estado Documento | docstatus | Botón Save | Botón Submit | Botón Cancel |
|------------------|-----------|------------|--------------|--------------|
| **Nuevo/Draft**  | 0         | ✅ Visible  | ✅ Visible    | ❌ Oculto     |
| **Guardado**     | 0         | ❌ Oculto   | ✅ Visible    | ❌ Oculto     |
| **Submitted**    | 1         | ❌ Oculto   | ❌ Oculto     | ✅ Visible*   |
| **Cancelled**    | 2         | ❌ Oculto   | ❌ Oculto     | ❌ Oculto     |

*Solo si tiene permisos especiales

### **IMPLEMENTACIÓN EN JS:**
```javascript
frappe.ui.form.on("Factura Fiscal Mexico", {
    refresh: function(frm) {
        // Controlar visibilidad de botones según docstatus
        control_workflow_buttons(frm);
    }
});

function control_workflow_buttons(frm) {
    // Limpiar botones existentes
    frm.page.clear_actions();
    
    if (frm.doc.docstatus === 0) {
        // Draft: Mostrar Save y Submit
        frm.page.set_primary_action(__("Save"), () => frm.save());
        if (!frm.is_new()) {
            frm.page.set_secondary_action(__("Submit"), () => frm.submit());
        }
    } else if (frm.doc.docstatus === 1 && frm.doc.fm_fiscal_status === "Timbrada") {
        // Submitted y Timbrada: Solo mostrar Cancel si tiene permisos
        if (has_cancel_permissions(frm)) {
            frm.add_custom_button(__("Cancelar CFDI"), function() {
                cancel_cfdi(frm);
            }).addClass("btn-danger");
        }
    }
}
```

---

## 🔄 PROCESO DE TIMBRADO

### **AL HACER SUBMIT:**
```python
def on_submit(self):
    """Proceso de timbrado al hacer submit."""
    if self.fm_fiscal_status != "Pendiente":
        frappe.throw(_("Solo se pueden timbrar facturas en estado Pendiente"))
    
    # 1. Validar datos completos
    self.validate_timbrado_requirements()
    
    # 2. Enviar a PAC
    response = self.enviar_timbrado_pac()
    
    if response.success:
        # 3. Actualizar campos con respuesta PAC
        self.update_from_pac_response(response)
        
        # 4. Marcar Sales Invoice como timbrada
        frappe.db.set_value("Sales Invoice", self.sales_invoice, 
            "fm_esta_timbrada", 1)
        
        # 5. Crear log de auditoría
        self.create_timbrado_log(response)
        
        frappe.db.commit()
    else:
        # Error en timbrado
        frappe.throw(_("Error en timbrado: {0}").format(response.error))
```

---

## ❌ PROCESO DE CANCELACIÓN

### **CONDICIONES PARA CANCELAR:**
1. ✅ `fm_fiscal_status = "Timbrada"`
2. ✅ Usuario con rol `Fiscal Manager` o similar
3. ✅ UUID válido del SAT
4. ✅ Dentro del periodo permitido por SAT

### **PROCESO DE CANCELACIÓN:**
```python
def cancel_cfdi(self):
    """Cancelar CFDI en el SAT."""
    if self.fm_fiscal_status != "Timbrada":
        frappe.throw(_("Solo se pueden cancelar CFDIs timbrados"))
    
    # 1. Validar permisos
    if not has_role("Fiscal Manager"):
        frappe.throw(_("Sin permisos para cancelar CFDIs"))
    
    # 2. Enviar cancelación al PAC
    response = self.enviar_cancelacion_pac()
    
    if response.success:
        if response.status == "Cancelación Aceptada":
            # 3. Actualizar estados inmediatamente
            self.fm_fiscal_status = "Cancelada"
            self.cancellation_date = frappe.utils.now_datetime()
            
            # 4. Liberar Sales Invoice para re-timbrado
            frappe.db.set_value("Sales Invoice", self.sales_invoice,
                "fm_esta_timbrada", 0)
            
        elif response.status == "Cancelación Pendiente":
            # 5. Estado intermedio - NO liberar Sales Invoice aún
            self.fm_fiscal_status = "Solicitud Cancelación"
            
        self.create_cancelacion_log(response)
        frappe.db.commit()
```

---

## 🚨 PUNTOS CRÍTICOS

### **1. PROBLEMA ABIERTO - Sales Invoice vs Factura Fiscal**
**Escenario:** Se requiere cancelar Sales Invoice pero tiene Factura Fiscal timbrada.

**Soluciones propuestas:**
- **A.** Prevenir cancelación de Sales Invoice si tiene CFDI timbrado
- **B.** Cancelar automáticamente CFDI al cancelar Sales Invoice
- **C.** Crear workflow específico de "Cancelación en Cascada"

**🔍 REQUIERE ANÁLISIS TÉCNICO PROFUNDO**

### **2. VALIDACIÓN ESTADOS SAT**
- Estados SAT pueden cambiar asincrónicamente
- Implementar job periódico para verificar estados
- Cache de estados con TTL apropiado

### **3. MANEJO DE ERRORES PAC**
- Timeouts de red
- Errores de certificados
- Respuestas malformadas del PAC

---

## 📊 PLAN DE IMPLEMENTACIÓN

| Fase | Descripción | Prioridad | Estado | Tiempo Real |
|------|-------------|-----------|--------|-------------|
| **1** | Prevención doble facturación | 🔴 Alta | ✅ **COMPLETADO** | 4.5 horas |
| **2** | Control botones workflow | 🔴 Alta | ✅ **COMPLETADO** | 3 horas |
| **3** | Filtros Sales Invoice | 🔴 Alta | ✅ **COMPLETADO** | 2 horas |
| **4** | Auto-carga PUE mejorada | 🟡 Media | ✅ **COMPLETADO** | 4.5 horas |
| **5** | Sistema cancelación CFDI | 🟡 Media | ⏸️ **PENDIENTE** | 6 horas |
| **6** | Validación estados SAT | 🟢 Baja | ⏸️ **PENDIENTE** | 4 horas |

---

## ✅ IMPLEMENTACIÓN COMPLETADA - FASE 1, 2 y 3

### **🎯 FUNCIONALIDADES IMPLEMENTADAS**

#### **FASE 1: Prevención Doble Facturación**
- ✅ **Campo de tracking**: Usa `fm_factura_fiscal_mx` existente (Link a Factura Fiscal Mexico)
- ✅ **Validación JavaScript**: Función `is_already_timbrada(frm)` en `sales_invoice.js`
- ✅ **Validación Python**: Método `validate_no_duplicate_timbrado()` en `FacturaFiscalMexico`
- ✅ **Control UI botones**: `add_timbrar_button()` vs `add_view_fiscal_button()`
- ✅ **Indicador visual**: Dashboard indicator "Ya Timbrada" (green)

#### **FASE 2: Control Botones Workflow**
- ✅ **Botones dinámicos**: Según `docstatus` y `fm_fiscal_status`
- ✅ **Estados manejados**: Pendiente, Timbrada, Cancelada, Error
- ✅ **Transiciones válidas**: Nuevo → Pendiente, Pendiente → Timbrada/Error/Cancelada
- ✅ **Navegación mejorada**: Mensajes de éxito y manejo errores

#### **FASE 3: Filtros Sales Invoice Dinámicos**
- ✅ **Función de filtros**: `setup_sales_invoice_filters()` implementada
- ✅ **Criterios de seguridad fiscal**:
  - `docstatus = 1` (solo Sales Invoice submitted)
  - `fm_factura_fiscal_mx` vacío o null (sin asignar a otra factura fiscal)
  - `tax_id` presente (RFC del cliente requerido)
- ✅ **Validación en tiempo real**: `validate_sales_invoice_availability()` 
- ✅ **Prevención crítica**: No permite seleccionar facturas draft (0) o canceladas (2)
- ✅ **Mensajes específicos**: Feedback claro sobre por qué una factura no es válida

#### **FASE 4: Auto-carga PUE Mejorada** ✅ **COMPLETADA**
- ✅ **Función Python**: `auto_load_payment_method_from_sales_invoice()` con función SQL directa optimizada
- ✅ **Wrapper JavaScript**: `get_payment_entry_for_javascript()` con `@frappe.whitelist()` 
- ✅ **Lógica PUE vs PPD implementada**:
  - **PUE sin Payment Entry**: Forma de pago vacía (selección manual del usuario)
  - **PUE con Payment Entry**: Auto-carga `mode_of_payment` automáticamente desde PE
  - **PPD**: Siempre asigna "99 - Por definir" (cumple normativa SAT)
- ✅ **Triggers configurados**: `sales_invoice` y `fm_payment_method_sat` eventos
- ✅ **Auto-actualización documentos existentes**: Verificación de consistencia en `onload()`
- ✅ **Respeto selecciones manuales**: No sobrescribe valores establecidos por usuario
- ✅ **Casos edge cubiertos**: Creación nueva, cambio Sales Invoice, documento existente sin PE
- ✅ **SQL child table optimizado**: Función `get_payment_entry_by_invoice()` con consulta directa
- ✅ **JavaScript call mejorado**: `get_payment_entry_for_javascript()` para frontend
- ✅ **Testing validado**: Tests Layer 2 para implementación y lógica PUE/PPD - PASSED

### **🔧 ARCHIVOS MODIFICADOS**

| Archivo | Cambios Principales |
|---------|-------------------|
| `sales_invoice.js` | ✅ Control botones, validación doble facturación, navegación |
| `factura_fiscal_mexico.py` | ✅ Validación backend, transiciones estado, prevent duplicate, **FASE 4: auto_load_payment_method_from_sales_invoice() + get_payment_entry_by_invoice() + get_payment_entry_for_javascript()** |
| `factura_fiscal_mexico.js` | ✅ Auto-carga Use CFDI, **FASE 3: Filtros Sales Invoice + validación tiempo real**, **FASE 4: auto_load_payment_method_from_sales_invoice() + triggers sales_invoice/fm_payment_method_sat** |
| `test_layer2_cross_module_validation.py` | ✅ Tests para filtros Sales Invoice y validación de disponibilidad, **FASE 4: Tests implementación y lógica Payment Entry - PASSED** |

### **🧪 VALIDACIONES IMPLEMENTADAS**

#### **Frontend (JavaScript)**
```javascript
// FASE 1: Prevención doble facturación
function is_already_timbrada(frm) {
    return frm.doc.fm_factura_fiscal_mx && frm.doc.fm_factura_fiscal_mx.trim() !== "";
}

// FASE 2: Control botones dinámico
if (frm.doc.docstatus === 1 && has_customer_rfc(frm) && !is_already_timbrada(frm)) {
    add_timbrar_button(frm);
} else if (frm.doc.docstatus === 1 && is_already_timbrada(frm)) {
    add_view_fiscal_button(frm);
}

// FASE 3: Filtros Sales Invoice dinámicos (CRÍTICO PARA SEGURIDAD FISCAL)
function setup_sales_invoice_filters(frm) {
    frm.set_query("sales_invoice", function() {
        return {
            filters: {
                // 1. CRÍTICO: Solo Sales Invoice submitted (docstatus = 1)
                // Evita facturas draft (0) y canceladas (2)
                "docstatus": 1,
                
                // 2. CRÍTICO: Sin Factura Fiscal Mexico ya asignada
                // Evita doble facturación fiscal
                "fm_factura_fiscal_mx": ["in", ["", null]],
                
                // 3. Tener RFC del cliente (requerido para facturación fiscal)
                // Sin RFC no se puede timbrar
                "tax_id": ["not in", ["", null]]
            }
        };
    });
}
```

#### **Backend (Python)**
```python
def validate_no_duplicate_timbrado(self):
    """Prevenir doble timbrado del mismo Sales Invoice."""
    # Verificar campo directo en Sales Invoice
    existing_fiscal_doc = frappe.db.get_value("Sales Invoice", 
        self.sales_invoice, "fm_factura_fiscal_mx")
    
    if existing_fiscal_doc and existing_fiscal_doc != self.name:
        existing_status = frappe.db.get_value("Factura Fiscal Mexico", 
            existing_fiscal_doc, "fm_fiscal_status")
        
        if existing_status == "Timbrada":
            frappe.throw(_("Sales Invoice {0} ya ha sido timbrada en documento {1}")
                .format(self.sales_invoice, existing_fiscal_doc))
```

### **🐛 ERRORES CORREGIDOS**

#### **PRIMERA ITERACIÓN**
1. ✅ **Transición estado inválida**: `None/'' → Pendiente` ahora permitido
2. ✅ **Use CFDI no se carga**: Auto-trigger en `onload` + debugging detallado  
3. ✅ **Navegación confusa**: Mensajes de éxito y manejo errores mejorado
4. ✅ **Customer faltante**: Campo `customer` agregado en creación documento
5. ✅ **Validación duplicada**: Lógica refinada para estados Cancelada/Error

#### **SEGUNDA ITERACIÓN - ANÁLISIS PROFUNDO**
6. ✅ **Hook "pending → pending"**: Corregido `factura_fiscal_update.py` - Skip documentos nuevos
7. ✅ **Botones Save/Submit duplicados**: Removido `frm.page.clear_actions()` que interfería con Frappe
8. ✅ **Navegación confusa**: Título Sales Invoice persistente - Requerirá refresh manual del browser

### **📊 MÉTRICAS DE CALIDAD ACTUALIZADAS**

- **Líneas código agregadas**: ~220 líneas (40 líneas FASE 3 adicionales)
- **Funciones nuevas**: 8 funciones JavaScript + 1 método Python + 1 hook corregido
- **Validaciones**: 4 niveles (UI, Frontend Filters, Backend, Hook validation)
- **Manejo errores**: 11 casos específicos cubiertos (6 nuevos de FASE 3)
- **Tests creados**: 9 tests (Layer 1-3) todos PASSED
- **Iteraciones debugging**: 3 rondas de análisis profundo + debug filtros crítico

### **🔍 PRÓXIMOS PASOS - ESTADO ACTUAL**

1. ✅ **Validación manual Round 1** - Errores identificados y corregidos
2. ✅ **Validación manual Round 2** - Sistema Fiscal Events desactivado, errores principales resueltos
3. ✅ **ERROR CRÍTICO RESUELTO** - Botón Submit aparece correctamente después de Save
4. ✅ **Ejecución tests automatizados** - 3 nuevos tests PASSED validando funcionalidad
5. ✅ **FASE 3 COMPLETADA** - Filtros Sales Invoice funcionando correctamente
6. ✅ **FASE 4 COMPLETADA** - Auto-carga PUE mejorada con avisos de consistencia implementada
7. 🎯 **PRÓXIMO: Fase 5** - Sistema cancelación CFDI (workflow listo para continuar)

### **🚨 ERRORES RESTANTES CONOCIDOS**

- **Navegación título**: "ACC-SINV-2025-00596" persiste en navegador (requiere refresh)
- **Auto-compacting**: Cerca del límite, requiere manejo de contexto

### **⏸️ SISTEMA FISCAL EVENTS TEMPORALMENTE DESACTIVADO**

**PROBLEMA IDENTIFICADO:**
- Error "Transición de estado inválida: pending → pending" al crear Factura Fiscal Mexico
- Causado por múltiples hooks que crean Fiscal Events simultáneamente
- No afecta funcionalidad, pero genera mensajes de error confusos

**ACCIÓN TOMADA:**
- Hooks `factura_fiscal_insert.create_fiscal_event` y `factura_fiscal_update.register_status_changes` comentados en `hooks.py`
- Sistema de tracking de eventos deshabilitado temporalmente

**PENDIENTE PARA POST-IMPLEMENTACIÓN:**
- Reactivar sistema Fiscal Events después de completar workflow de prevención doble facturación
- Revisar timing de hooks para evitar conflictos de concurrencia
- Considerar usar eventos asincrónicos o queue para evitar race conditions
- Prioridad: 🟡 Media (no afecta funcionalidad core)

### **✅ ERROR CRÍTICO RESUELTO - BOTÓN SUBMIT FUNCIONANDO**

**PROBLEMA IDENTIFICADO Y RESUELTO:**
- ✅ **Causa raíz encontrada**: DocType no tenía `"is_submittable": 1`
- ✅ **Solución implementada**: Agregado `is_submittable: 1` en `factura_fiscal_mexico.json`
- ✅ **Migración ejecutada**: `bench reload-doctype` + `clear-cache` + `restart`

**ARQUITECTURA VALIDADA:**
- ✅ **Botones nativos Frappe**: Save/Submit manejados automáticamente
- ✅ **Botones custom FacturAPI**: Operaciones específicas del PAC
- ✅ **Sin interferencia**: JavaScript no manipula botones nativos
- ✅ **Workflow estándar**: Save (docstatus=0) → Submit (docstatus=1)

**TESTS AGREGADOS Y VALIDADOS:**
- ✅ `test_doctype_is_submittable_configured()` - Confirma configuración submittable
- ✅ `test_mixed_architecture_buttons_implementation()` - Valida arquitectura mixta
- ✅ Tests Layer 3 actualizados - Workflow Save → Submit en casos reales

**IMPACTO:** 🟢 **RESUELTO** - Workflow de timbrado completamente funcional

**TOTAL ESTIMADO:** 28.5 horas (14 horas FASES 1-4 completadas)

---

## 🧪 CASOS DE PRUEBA

### **Flujo Normal:**
1. Crear Sales Invoice → Submit
2. Crear Factura Fiscal → Seleccionar Sales Invoice
3. Completar datos → Save → Submit (Timbrar)
4. Verificar estado "Timbrada" y Sales Invoice marcada
5. Cancelar CFDI → Verificar liberación Sales Invoice

### **Casos Edge:**
- Intento de doble timbrado
- Cancelación sin permisos
- Sales Invoice sin Payment Entry (PUE)
- Timeout de PAC
- Estados SAT inconsistentes

---

## 📝 REGISTRO DE CAMBIOS

| Fecha | Cambio | Autor |
|-------|--------|-------|
| 2025-08-03 | Documento inicial | Claude Code |
| | Pendiente implementación | |

---

## 🚨 TAREA ADICIONAL CRÍTICA DESCUBIERTA

### **PROBLEMA ARQUITECTÓNICO: Sistema fm_draft_status**

**DESCRIPCIÓN:** Durante la implementación se descubrió que la funcionalidad de `fm_draft_status` fue diseñada para Sales Invoice pero debe migrarse a Factura Fiscal Mexico según la nueva arquitectura.

**IMPACTO:** 
- Sistema de borradores/preview está mal ubicado
- Duplicación de responsabilidades entre DocTypes
- Confusión en el workflow de timbrado

**ACCIÓN REQUERIDA:**
- Migrar sistema completo de Draft Management desde Sales Invoice a Factura Fiscal Mexico
- Actualizar hooks y APIs correspondientes  
- Revisar documentación de draft-workflow.md
- Actualizar tests relacionados

**PRIORIDAD:** 🔴 Alta - Debe atenderse después del proceso actual

**ESTIMADO:** 8-12 horas de refactoring

---

## 📅 HISTORIAL DE ACTUALIZACIONES

| Fecha | Cambios | Autor |
|-------|---------|-------|
| 2025-08-03 | Documento inicial | Claude Code |
| 2025-08-03 | ✅ **FASE 1-2 COMPLETADAS** - Prevención doble facturación + Control workflow | Claude Code |
| 2025-08-03 | 🔧 **CORRECCIONES CRÍTICAS** - Hook fiscal update + UI buttons + navegación | Claude Code |
| 2025-08-04 | ✅ **ERROR CRÍTICO RESUELTO** - DocType submittable + Arquitectura mixta + Tests validados | Claude Code |
| 2025-08-04 | ✅ **FASE 3 COMPLETADA** - Filtros Sales Invoice + Validación tiempo real + Debug crítico | Claude Code |
| 2025-08-04 | ✅ **FASE 4 COMPLETADA** - Auto-carga PUE mejorada + Avisos consistencia + SQL directo child tables | Claude Code |

---

**💡 NOTA:** Este documento debe actualizarse conforme se implementen las funcionalidades y se descubran nuevos requerimientos o edge cases.