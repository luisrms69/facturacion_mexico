# 🔧 Troubleshooting - Cancelaciones Múltiples

Esta guía te ayuda a resolver problemas comunes relacionados con cancelaciones fiscales y re-facturación en el sistema.

## 🚨 **Problemas Comunes**

### **Error: "No se puede re-facturar con la misma Sales Invoice"**

#### **Síntomas:**
- Pantalla congelada en "Generando nueva factura fiscal..."
- Error de validación: "Cambios detectados en: currency, exchange_rate, subtotal, total, items"
- Mensaje: "Crea un nuevo Sales Invoice"

#### **Causa:**
Sistema detecta cambios que requieren nuevo Sales Invoice en lugar de re-facturación

#### **Solución:**
1. **Para cambios menores (régimen/uso CFDI):**
   - Cancelar CFDI con motivo 02/03/04
   - Usar botón "Nueva FFM (misma SI)"
   - Modificar solo régimen fiscal o uso CFDI

2. **Para cambios mayores (importes/conceptos):**
   - Usar workflow de sustitución (motivo 01)
   - Crear nueva Sales Invoice
   - Establecer relación de sustitución

---

### **FFM Duplicadas con Archivos Mezclados**

#### **Síntomas:**
- Múltiples FFM con mismo nombre
- Archivos PDF/XML aparecen en facturas incorrectas
- Historial fiscal confuso

#### **Causa:**
Reutilización de nombres FFM o vinculación incorrecta

#### **Solución:**
1. Verificar que cada FFM tenga nombre único (FFMX-YYYY-#####)
2. Confirmar que SI apunte solo a FFM vigente
3. Revisar que FFM cancelada mantenga sus archivos históricos
4. Si persiste: contactar soporte técnico

---

### **Pantalla Congelada Durante Cancelación**

#### **Síntomas:**
- UI no responde después de click "Cancelar CFDI"
- Mensaje "Procesando..." permanece indefinidamente
- No se recibe confirmación de proceso

#### **Solución:**
1. **NO refrescar página** inmediatamente
2. Esperar 2-3 minutos para timeout automático
3. Verificar estado en FacturAPI directamente
4. Si no hay respuesta:
   - Refrescar página
   - Verificar estado fiscal en Sales Invoice
   - Reintentar si es necesario

---

### **Error de Conexión con FacturAPI**

#### **Síntomas:**
- "Error de red" o "Timeout"
- "Credenciales inválidas"
- "Servicio no disponible"

#### **Solución:**
1. Verificar credenciales en site_config.json:
   ```json
   {
     "facturapi_secret_key": "sk_test_...",
     "facturapi_secret_key_live": "sk_live_..."
   }
   ```
2. Confirmar conectividad a Internet
3. Verificar status de FacturAPI en su sitio oficial
4. Si persiste: verificar logs del sistema

---

### **UUID No Válido para Sustitución**

#### **Síntomas:**
- Error: "UUID no encontrado"
- "CFDI no existe en FacturAPI"
- Cancelación falla en validación

#### **Solución:**
1. Verificar que UUID esté correcto (36 caracteres)
2. Confirmar que CFDI existe en FacturAPI
3. Validar que CFDI esté vigente (no cancelado)
4. Si es sustitución (motivo 04): verificar UUID del sustituto

---

## 🛠️ **Procedimientos de Recuperación**

### **Recuperar de Cancelación Incompleta**

Si una cancelación falló a medio proceso:

1. **Verificar estado actual:**
   - Revisar `fm_fiscal_status` en Sales Invoice
   - Confirmar estado en FacturAPI
   - Verificar FFM vinculada

2. **Sincronizar estados:**
   - Si FacturAPI muestra cancelado pero SI no: actualizar SI
   - Si SI muestra cancelado pero FacturAPI no: reintentar cancelación
   - Si hay inconsistencia: contactar soporte

### **Limpiar Vinculaciones Rotas**

Para Sales Invoice con vinculación incorrecta:

1. Usar botón "Nueva factura fiscal"
2. Sistema desvincula automáticamente
3. Modificar SI según necesidades
4. Usar "Generar Factura Fiscal" para crear nueva FFM

### **Restaurar Archivos Perdidos**

Si archivos PDF/XML no aparecen:

1. Verificar en FFM original (no en SI)
2. Revisar sección "Historial Fiscal"
3. Re-descargar desde FacturAPI si necesario
4. Adjuntar manualmente si no está disponible

---

## ⚠️ **Mejores Prácticas Preventivas**

### **Antes de Cancelar**
- [ ] Confirmar motivo de cancelación correcto
- [ ] Verificar que tipo de cambios se requieren
- [ ] Backup de datos importantes
- [ ] Confirmar permisos de usuario

### **Durante el Proceso**
- [ ] No hacer doble-click en botones
- [ ] Esperar confirmación antes de siguiente acción
- [ ] No cerrar ventana durante procesamiento
- [ ] Monitorear mensajes de estado

### **Después de Cancelar**
- [ ] Verificar estado fiscal actualizado
- [ ] Confirmar archivos en ubicación correcta
- [ ] Validar vinculaciones SI ↔ FFM
- [ ] Documentar cambios realizados

---

## 📞 **Escalación de Problemas**

### **Casos que Requieren Soporte Técnico**
- Inconsistencias persistentes SI ↔ FacturAPI
- Archivos perdidos irreversiblemente
- Errores de integridad de datos
- Fallos repetidos sin causa aparente

### **Información a Proporcionar**
- ID de Sales Invoice afectada
- UUID de CFDI involucrado
- Pasos exactos que causaron error
- Screenshots de mensajes de error
- Logs relevantes del sistema

---

*Para casos complejos o errores no documentados, consultar documentación técnica completa en buzola-internal*