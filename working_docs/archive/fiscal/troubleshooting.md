# 🔧 Troubleshooting - Problemas Fiscales Comunes

Esta guía te ayuda a resolver los problemas más frecuentes en el sistema de facturación fiscal.

## 🚨 **Problemas de Timbrado**

### **Error: "RFC del emisor no válido"**

#### **Síntomas**
- Error al intentar timbrar
- Mensaje: "RFC no encontrado en padrón SAT"
- Proceso se detiene antes de enviar a FacturAPI

#### **Causas Comunes**
- RFC mal capturado en configuración empresa
- Certificados no corresponden al RFC
- RFC dado de baja en SAT

#### **Soluciones**
1. **Verificar RFC empresa:**
   - Ir a Company → RFC debe ser exacto
   - Confirmar en sitio SAT que esté activo
   - Validar formato (12-13 caracteres)

2. **Validar certificados:**
   - Confirmar que certificados pertenecen al RFC
   - Verificar vigencia de certificados
   - Re-subir certificados si es necesario

---

### **Error: "Certificado vencido"**

#### **Síntomas**
- Falla timbrado con error de certificado
- Mensaje relacionado con vigencia
- FacturAPI rechaza la petición

#### **Soluciones**
1. **Renovar certificados:**
   - Obtener nuevos certificados del SAT
   - Actualizar en FacturAPI
   - Configurar nuevas rutas en sistema

2. **Verificar fechas:**
   ```bash
   openssl x509 -in certificado.cer -text -noout | grep "Not After"
   ```

---

### **Error: "Serie no configurada"**

#### **Síntomas**
- Error: "No se encontró serie para centro de costo"
- Usa serie default inesperadamente
- Folios inconsistentes

#### **Soluciones**
1. **Configurar mapeo series:**
   ```json
   {
     "fm_series_mapping": {
       "Centro Costo": "Serie SAT"
     }
   }
   ```

2. **Verificar en FacturAPI:**
   - Confirmar que serie existe
   - Validar folios disponibles
   - Revisar configuración Series Group

---

## 🔄 **Problemas de Cancelación**

### **Error: "CFDI no encontrado para cancelar"**

#### **Síntomas**
- Error al intentar cancelar
- UUID no reconocido por FacturAPI
- Cancelación falla silenciosamente

#### **Causas**
- UUID mal formado o corrupto
- CFDI fue cancelado manualmente
- Problema de sincronización

#### **Soluciones**
1. **Verificar UUID:**
   - Confirmar formato (36 caracteres con guiones)
   - Validar en portal FacturAPI
   - Verificar en sistema SAT

2. **Sincronizar estado:**
   ```bash
   bench --site sitio.dev execute facturacion_mexico.utils.sync_fiscal_status --args "['SI-2024-00001']"
   ```

---

### **Error: "Plazo de cancelación vencido"**

#### **Síntomas**
- SAT rechaza cancelación
- Error de tiempo excedido
- CFDI queda en estado inconsistente

#### **Soluciones**
1. **Para CFDIs recientes (72 horas):**
   - Cancelación directa permitida
   - Reintentar proceso

2. **Para CFDIs antiguos:**
   - Requiere solicitud de cancelación
   - Cliente debe aceptar/rechazar
   - Proceso puede tomar días

---

## 👥 **Problemas de Clientes**

### **Error: "RFC del receptor inválido"**

#### **Síntomas**
- Validación falla al timbrar
- Error específico de RFC receptor
- Rechazo por formato o existencia

#### **Soluciones**
1. **Validar formato RFC:**
   ```python
   # Personas físicas: 13 caracteres
   # Personas morales: 12 caracteres
   ```

2. **Verificar en SAT:**
   - Consultar padrón de contribuyentes
   - Confirmar que esté activo
   - Validar régimen fiscal

3. **Corregir en sistema:**
   - Actualizar RFC en Customer
   - Verificar homoclave si aplica
   - Confirmar datos fiscales completos

---

### **Error: "Código postal no válido"**

#### **Síntomas**
- Error de domicilio fiscal
- Rechazo por CP incorrecto
- Validación SAT falla

#### **Soluciones**
1. **Verificar código postal:**
   - Usar catálogo oficial SAT
   - Confirmar que corresponda a estado/municipio
   - Validar formato (5 dígitos)

2. **Actualizar dirección:**
   - Corregir en Customer Address
   - Sincronizar con datos SAT
   - Verificar consistencia estatal

---

## 🛒 **Problemas de Productos**

### **Error: "Clave de producto no válida"**

#### **Síntomas**
- Rechazo al timbrar por clave SAT
- Error de catálogo no actualizado
- Validación falla en items

#### **Soluciones**
1. **Actualizar catálogo SAT:**
   - Descargar última versión
   - Actualizar claves en productos
   - Verificar vigencia

2. **Corregir claves:**
   - Buscar clave correcta en SAT
   - Actualizar en Item Master
   - Validar clave de unidad también

---

### **Error: "Unidad de medida incorrecta"**

#### **Síntomas**
- Error de clave de unidad
- Incompatibilidad producto-unidad
- Rechazo de validación SAT

#### **Soluciones**
1. **Verificar combinación:**
   - Producto debe ser compatible con unidad
   - Consultar catálogo SAT oficial
   - Corregir en Item Master

---

## 💻 **Problemas Técnicos**

### **Error: "Conexión con FacturAPI fallida"**

#### **Síntomas**
- Timeouts frecuentes
- Errores de red
- Credenciales rechazadas

#### **Soluciones**
1. **Verificar credenciales:**
   ```json
   {
     "facturapi_secret_key": "sk_test_...",
     "facturapi_test_mode": 1
   }
   ```

2. **Probar conectividad:**
   ```bash
   curl -H "Authorization: Bearer sk_test_..." https://facturapi.io/v1/invoices
   ```

3. **Verificar red:**
   - Confirmar acceso a Internet
   - Revisar firewall/proxy
   - Validar DNS resolution

---

### **Error: "Base de datos inconsistente"**

#### **Síntomas**
- Estados fiscales incorrectos
- Links rotos SI ↔ FFM
- Datos duplicados

#### **Soluciones**
1. **Reparar links:**
   ```bash
   bench --site sitio.dev execute facturacion_mexico.utils.repair_fiscal_links
   ```

2. **Limpiar duplicados:**
   ```bash
   bench --site sitio.dev execute facturacion_mexico.utils.cleanup_duplicate_ffm
   ```

---

## 🔍 **Herramientas de Diagnóstico**

### **Verificar Estado Sistema**

```bash
# Estado general del sitio
bench --site sitio.dev execute facturacion_mexico.utils.system_health_check

# Verificar configuración FacturAPI
bench --site sitio.dev execute facturacion_mexico.utils.test_facturapi_connection

# Sincronizar estados fiscales
bench --site sitio.dev execute facturacion_mexico.utils.sync_all_fiscal_status
```

### **Logs de Depuración**

#### **Ubicaciones de Logs**
- Sistema general: `logs/bench.log`
- Errores específicos: `logs/error.log`
- FacturAPI requests: buscar "facturapi" en logs

#### **Habilitar Debug Mode**
```json
{
  "developer_mode": 1,
  "facturapi_debug": 1
}
```

---

## 📋 **Procedimientos de Emergencia**

### **Recuperación de Sesión Colgada**

1. **Identificar proceso:**
   ```bash
   ps aux | grep bench
   ```

2. **Terminar proceso seguro:**
   ```bash
   bench --site sitio.dev migrate
   bench --site sitio.dev clear-cache
   ```

### **Rollback de Cambios**

```bash
# Rollback última migración
bench --site sitio.dev migrate --skip-failing

# Restaurar backup
bench --site sitio.dev restore database_backup.sql
```

---

## 📞 **Escalación**

### **Cuándo Contactar Soporte**
- Errores persistentes no documentados
- Inconsistencias de datos críticas
- Problemas de conectividad complejos
- Fallos de migración/actualización

### **Información a Proporcionar**
- [ ] Descripción exacta del error
- [ ] Pasos para reproducir
- [ ] Screenshots de errores
- [ ] Logs relevantes del sistema
- [ ] Configuración actual (sin credenciales)

---

## ✅ **Prevención**

### **Mantenimiento Regular**
- [ ] Actualizar catálogos SAT mensualmente
- [ ] Verificar vigencia certificados
- [ ] Monitorear logs de errores
- [ ] Backup regular de configuración
- [ ] Pruebas de conectividad semanales

### **Mejores Prácticas**
- Validar datos antes de timbrar
- Mantener usuarios capacitados
- Documentar cambios de configuración
- Monitorear reportes fiscales regularmente

---

*Para problemas no cubiertos en esta guía, consultar documentación técnica completa o contactar soporte especializado*