# 👤 Guía de Usuario - Facturación Fiscal

Esta guía completa te enseña a usar el sistema de facturación fiscal mexicana paso a paso.

## 🚀 **Primeros Pasos**

### **Acceso al Sistema**
1. Iniciar sesión en ERPNext
2. Verificar permisos de facturación fiscal
3. Confirmar configuración de empresa activa

### **Navegación Principal**
- **Sales Invoice List** - Listado de facturas
- **Factura Fiscal México List** - CFDIs generados
- **Customer List** - Gestión de clientes
- **Reports** - Reportes fiscales

---

## 📄 **Crear Factura Fiscal**

### **1. Crear Sales Invoice**

#### **Información Básica**
1. Ir a **Sales Invoice** > **New**
2. Seleccionar **Customer**
3. Configurar **Cost Center** (para multisucursal)
4. Agregar **Items** con claves SAT válidas

#### **Datos Fiscales**
- `fm_uso_cfdi` - Uso que dará el cliente
- `fm_forma_pago` - Forma de pago (99 por defecto)
- `fm_metodo_pago` - Método de pago específico

#### **Validaciones Automáticas**
- RFC del cliente válido
- Claves SAT de productos
- Cálculo correcto de impuestos
- Domicilio fiscal completo

### **2. Timbrar CFDI**

#### **Proceso de Timbrado**
1. **Save** el Sales Invoice
2. **Submit** para confirmar
3. Click en **"Generar Factura Fiscal"**
4. Revisar serie fiscal asignada
5. Confirmar timbrado

#### **Resultado Esperado**
- `fm_fiscal_status` = "TIMBRADO"
- UUID del CFDI generado
- PDF y XML disponibles
- Link a Factura Fiscal México

---

## 🔄 **Cancelar CFDI**

### **Motivos de Cancelación SAT**

#### **01 - Sustitución**
Para correcciones que requieren nueva factura
- Cambio de conceptos
- Modificación de importes
- Corrección de datos del receptor

#### **02 - Error con Relación**
Para cambios menores con documento relacionado
- Cambio de régimen fiscal
- Modificación de uso CFDI

#### **03 - Error sin Relación**
Para cambios menores sin documento relacionado
- Correcciones de captura
- Cambios de forma de pago

#### **04 - Sustitución Global**
Para reemplazos en esquemas especiales

### **Proceso de Cancelación**

#### **Pasos Generales**
1. Abrir Sales Invoice con CFDI timbrado
2. Click en **"Cancelar CFDI"**
3. Seleccionar **motivo** de cancelación
4. Si es motivo 04: ingresar **UUID de sustitución**
5. **Confirmar** cancelación

#### **Tiempos de Procesamiento**
- Cancelación inmediata: 30-60 segundos
- Confirmación SAT: hasta 72 horas
- Actualización automática de estados

---

## 🔁 **Re-facturación**

### **Workflow 02/03/04 (Misma Sales Invoice)**

#### **Cuándo Usar**
- Solo cambios de régimen fiscal
- Solo cambios de uso CFDI
- NO para cambios de importes/conceptos

#### **Proceso**
1. Después de cancelar CFDI (02/03/04)
2. Click en **"Nueva FFM (misma SI)"**
3. Sistema valida cambios permitidos
4. Modificar solo régimen y/o uso CFDI
5. Click en **"Generar Factura Fiscal"**

#### **Validaciones**
- Solo régimen y uso CFDI modificables
- Otros cambios → sistema bloquea
- Sugerencia de crear nueva SI

### **Workflow 01 (Sustitución)**

#### **Cuándo Usar**
- Cambios de conceptos
- Modificación de importes
- Correcciones amplias

#### **Proceso**
1. En SI con CFDI timbrado
2. Click en **"Sustituir CFDI (01)"**
3. Sistema crea nueva Sales Invoice
4. Realizar correcciones necesarias
5. Timbrar con TipoRelación 04
6. Sistema cancela CFDI original automáticamente

---

## 📊 **Consultar Estados Fiscales**

### **Estados Disponibles**
- `BORRADOR` - Factura no timbrada
- `TIMBRADO` - CFDI vigente en SAT
- `CANCELADO` - CFDI cancelado
- `ERROR` - Error en proceso fiscal

### **Información Disponible**
- **UUID del CFDI**
- **Fecha de timbrado**
- **Serie y folio asignados**
- **Motivo de cancelación** (si aplica)
- **Enlaces a PDF/XML**

### **Reportes Fiscales**
- Facturas por período
- Cancelaciones realizadas
- Estados fiscales resumidos
- Errores pendientes

---

## 🏢 **Multisucursal**

### **Configuración por Sucursal**

#### **Centro de Costos**
- Cada sucursal = Centro de Costo
- Asignación automática por usuario
- Selección manual en cada factura

#### **Series Fiscales**
- Serie automática por centro de costo
- Serie default si no hay mapeo
- Aviso visible cuando se usa default

### **Workflow Multisucursal**
1. Seleccionar **Cost Center** en SI
2. Sistema determina **serie fiscal**
3. Mostrar serie antes de timbrar
4. Proceder con timbrado normal

---

## 👥 **Gestión de Clientes**

### **Datos Fiscales Requeridos**

#### **Información Básica**
- RFC (validación automática)
- Razón Social o Nombre
- Régimen Fiscal del receptor

#### **Configuración Fiscal**
- Uso CFDI por defecto
- Forma de pago preferida
- Método de pago habitual

#### **Domicilio Fiscal**
- Dirección completa
- Código postal (validación SAT)
- Estado y municipio

### **Validaciones Automáticas**
- Formato RFC correcto
- Régimen fiscal válido
- Código postal existente
- Consistencia entre datos

---

## 🛒 **Productos y Servicios**

### **Claves SAT Obligatorias**

#### **Por Producto**
- Clave de Producto/Servicio
- Clave de Unidad
- Descripción fiscal

#### **Configuración de Impuestos**
- IVA (0%, 8%, 16%)
- IEPS (productos específicos)
- Retenciones (servicios profesionales)

### **Validaciones**
- Claves SAT válidas y vigentes
- Unidades congruentes
- Tasas de impuesto correctas

---

## ⚠️ **Errores Comunes y Soluciones**

### **Error: RFC Inválido**
- **Causa:** Formato incorrecto o RFC inexistente
- **Solución:** Validar en sitio SAT, corregir formato

### **Error: Clave SAT No Válida**
- **Causa:** Clave de producto obsoleta o incorrecta
- **Solución:** Actualizar catálogo SAT, verificar claves

### **Error: Conexión FacturAPI**
- **Causa:** Credenciales incorrectas o servicio no disponible
- **Solución:** Verificar configuración, contactar soporte

### **Error: CFDI Ya Cancelado**
- **Causa:** Intento de cancelar CFDI ya cancelado
- **Solución:** Verificar estado actual, actualizar si necesario

---

## 📋 **Mejores Prácticas**

### **Antes de Timbrar**
- [ ] Verificar datos del cliente
- [ ] Confirmar claves SAT de productos
- [ ] Validar cálculo de impuestos
- [ ] Revisar información fiscal

### **Gestión de Cancelaciones**
- [ ] Confirmar motivo correcto SAT
- [ ] Documentar razón de cancelación
- [ ] Informar al cliente si es necesario
- [ ] Seguir workflow apropiado

### **Mantenimiento Regular**
- [ ] Actualizar catálogos SAT
- [ ] Verificar vigencia de certificados
- [ ] Revisar configuración FacturAPI
- [ ] Monitorear errores recurrentes

---

## 📞 **Soporte y Ayuda**

### **Recursos Disponibles**
- Troubleshooting: `docs/troubleshooting/`
- API Documentation: `docs/api/`
- Setup Guide: `docs/fiscal/setup.md`

### **Contacto**
- Soporte técnico para errores del sistema
- Capacitación para nuevos usuarios
- Consultoría fiscal para casos complejos

---

*Esta guía cubre los casos de uso más comunes. Para situaciones específicas, consultar documentación técnica adicional.*