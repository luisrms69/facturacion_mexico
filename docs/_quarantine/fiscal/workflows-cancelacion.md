# 🔄 Workflows de Cancelación CFDI

Esta guía explica los diferentes workflows de cancelación fiscal disponibles en el sistema, diseñados para cumplir con la normativa SAT mexicana.

## 📋 **Tipos de Cancelación**

El sistema maneja dos workflows principales según el motivo de cancelación:

### **Workflow A: Re-facturación (Motivos 02/03/04)**
Para cambios menores en la misma Sales Invoice

### **Workflow B: Sustitución (Motivo 01)**
Para correcciones amplias que requieren nueva Sales Invoice

---

## 🔄 **Workflow A: Re-facturación (02/03/04)**

### **¿Cuándo usar?**
- Cambio de régimen fiscal del receptor
- Cambio de uso de CFDI
- **NO aplica para:** cambios en conceptos, importes, impuestos

### **Proceso Paso a Paso**

#### **1. Cancelación Fiscal**
1. Abrir Sales Invoice con CFDI timbrado
2. Click en "Cancelar CFDI"
3. Seleccionar motivo:
   - **02:** Error con relación
   - **03:** Error sin relación
   - **04:** Sustitución global
4. Si es motivo 04: ingresar UUID de sustitución
5. Confirmar cancelación

#### **2. Nueva Facturación**
1. Después de cancelación exitosa, aparecen opciones:
   - **"Nueva FFM (misma SI)"**
   - **"Cancelar SI"**
2. Click en "Nueva FFM (misma SI)"
3. Sistema valida cambios permitidos
4. Modificar solo régimen y/o uso CFDI
5. Generar nueva factura fiscal

#### **Resultado**
- ✅ Sales Invoice mantiene mismo ID
- ✅ Nueva Factura Fiscal México vigente
- ✅ Factura anterior en historial fiscal
- ✅ Etiqueta "Re-facturado" en UI

---

## 🔄 **Workflow B: Sustitución (01)**

### **¿Cuándo usar?**
- Corrección de conceptos o cantidades
- Cambio de importes o impuestos
- Modificación de claves de producto
- Cualquier cambio que NO sea régimen/uso

### **Proceso Paso a Paso**

#### **1. Crear Factura Sustituta**
1. Abrir Sales Invoice con CFDI timbrado
2. Click en "Sustituir CFDI (01)"
3. Sistema crea nueva Sales Invoice (borrador)
4. Realizar correcciones necesarias
5. Timbar nueva factura con TipoRelación 04

#### **2. Cancelación Automática**
1. Sistema valida que sustituto esté vigente
2. Cancela automáticamente CFDI original (motivo 01)
3. Cancela Sales Invoice original
4. Establece vínculos entre facturas

#### **Resultado**
- ✅ Nueva Sales Invoice con ID diferente
- ✅ Sales Invoice original cancelada
- ✅ Vínculos "sustituye a" / "sustituida por"
- ✅ Etiqueta "Sustituido" en factura original
- ❌ Factura original NO se puede re-facturar

---

## 🎯 **Reglas de Validación**

### **Cambios Permitidos 02/03/04**
- ✅ Régimen fiscal del receptor
- ✅ Uso de CFDI
- ❌ Conceptos, cantidades, precios
- ❌ Impuestos, claves de producto
- ❌ Datos del emisor

### **Cambios Permitidos 01 (Sustitución)**
- ✅ Cualquier modificación
- ✅ Correcciones amplias
- ✅ Cambio de conceptos completos

## 🔧 **Consideraciones Técnicas**

### **Series y Folios**
- Serie se determina por Centro de Costos
- Serie default si no hay mapeo
- Folio asignado automáticamente por PAC
- Aviso cuando se usa serie default

### **Evidencias Fiscales**
- Sales Invoice muestra solo FFM vigente
- FFM cancelada mantiene PDF/XML + acuse
- Historial fiscal completo disponible

### **Plazos SAT**
- Sistema muestra avisos para cancelaciones
- Recordatorio de plazos normativos
- Confirmación requerida para cancelaciones antiguas

## ⚠️ **Casos Especiales**

### **Error en Validación**
Si el sistema detecta cambios no permitidos para 02/03/04:
- Bloquea el proceso
- Sugiere crear nueva Sales Invoice
- Proporciona enlace a workflow de sustitución

### **Fallo en Sustitución**
Si la creación del sustituto falla:
- CFDI original permanece vigente
- Sales Invoice original no se cancela
- Usuario puede reintentar proceso

---

*Para detalles técnicos de implementación, consultar documentación en buzola-internal*