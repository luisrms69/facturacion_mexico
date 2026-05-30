# ⚙️ Configuración Inicial - Sistema Fiscal

Esta guía te ayuda a configurar el sistema de facturación fiscal desde cero.

## 🏢 **Configuración de Empresa**

### **1. Datos Fiscales Básicos**

#### **Información Requerida**
- [ ] Razón Social completa
- [ ] RFC de la empresa (12-13 caracteres)
- [ ] Régimen Fiscal (clave SAT)
- [ ] Domicilio fiscal completo
- [ ] Logo de la empresa (opcional)

#### **Configuración en ERPNext**
1. Ir a **Company List**
2. Abrir tu empresa
3. Completar campos fiscales:
   - `Tax ID` = RFC
   - `fm_regimen_fiscal` = Clave régimen SAT
   - Dirección principal como domicilio fiscal

### **2. Certificados Digitales**

#### **Archivos Requeridos**
- [ ] Certificado (.cer)
- [ ] Llave privada (.key)
- [ ] Contraseña de llave privada

#### **Instalación**
1. Subir archivos a servidor
2. Configurar rutas en `site_config.json`
3. Validar vigencia de certificados
4. Probar conectividad con SAT

---

## 🔐 **Configuración FacturAPI**

### **1. Obtener Credenciales**

#### **Entorno de Pruebas**
1. Registrarse en [FacturAPI](https://facturapi.io)
2. Obtener `secret_key` de pruebas (inicia con `sk_test_`)
3. Configurar empresa de prueba

#### **Entorno Productivo**
1. Completar proceso de validación FacturAPI
2. Obtener `secret_key` productivo (inicia con `sk_live_`)
3. Subir certificados reales

### **2. Configurar en ERPNext**

#### **En site_config.json**
```json
{
  "facturapi_secret_key": "sk_test_tu_key_de_prueba",
  "facturapi_secret_key_live": "sk_live_tu_key_productivo",
  "facturapi_test_mode": 1
}
```

#### **Validar Configuración**
```bash
bench --site tu-sitio.dev execute facturacion_mexico.utils.test_facturapi_connection
```

---

## 🏪 **Configuración Multisucursal**

### **1. Centros de Costo**

#### **Crear Centros de Costo**
1. Ir a **Cost Center List**
2. Crear un centro por sucursal:
   - `Sucursal Norte`
   - `Sucursal Sur`
   - `Matriz`

#### **Asignar a Transacciones**
- Configurar centro de costo por defecto en usuarios
- Seleccionar en cada Sales Invoice
- Usar para determinar serie fiscal

### **2. Series Fiscales**

#### **Configurar en FacturAPI**
1. Crear Series Group por sucursal:
   - `Serie A` → Sucursal Norte
   - `Serie B` → Sucursal Sur
   - `Serie M` → Matriz

#### **Mapeo en ERPNext**
```json
{
  "fm_series_mapping": {
    "Sucursal Norte": "A",
    "Sucursal Sur": "B",
    "Matriz": "M"
  },
  "fm_default_series": "A"
}
```

---

## 👥 **Configuración de Usuarios**

### **1. Roles Fiscales**

#### **Crear Roles Personalizados**
- `Fiscal Manager` - Permisos completos
- `Fiscal User` - Solo timbrado y consulta
- `Fiscal Viewer` - Solo lectura

#### **Asignar Permisos**
1. Ir a **Role Permissions Manager**
2. Configurar accesos por DocType:
   - Sales Invoice: Read, Write, Create
   - Factura Fiscal México: Read, Write, Create, Cancel

### **2. Restricciones por Sucursal**

#### **Filtros de Usuario**
- Restringir por Cost Center
- Limitar acceso a otras sucursales
- Configurar series permitidas

---

## 📋 **Configuración de Clientes**

### **1. Datos Fiscales Obligatorios**

#### **Campos Requeridos**
- [ ] RFC (12-13 caracteres)
- [ ] Razón Social o Nombre
- [ ] Régimen Fiscal del receptor
- [ ] Uso de CFDI por defecto
- [ ] Domicilio completo (código postal obligatorio)

#### **Validaciones Automáticas**
- Formato RFC válido
- Código postal existente
- Régimen fiscal válido según SAT

### **2. Configuración por Defecto**

#### **Uso CFDI Común**
- `G03` - Gastos en general (más común)
- `G01` - Adquisición de mercancías
- `I01` - Construcciones

#### **Forma de Pago**
- `99` - Por definir (permite cambio posterior)
- `01` - Efectivo
- `03` - Transferencia electrónica

---

## 🛠️ **Configuración de Productos**

### **1. Claves SAT**

#### **Campos Obligatorios**
- [ ] Clave de Producto/Servicio SAT
- [ ] Clave de Unidad SAT
- [ ] Descripción fiscal
- [ ] Tipo de impuesto (IVA, IEPS, etc.)

#### **Configuración Masiva**
1. Exportar lista de productos
2. Completar claves SAT en Excel
3. Importar con Data Import Tool

### **2. Impuestos**

#### **Templates de Impuestos**
- `IVA 16%` - Impuesto estándar
- `IVA 0%` - Productos exentos
- `IEPS` - Productos específicos
- `ISR Retención` - Servicios profesionales

---

## ✅ **Validación de Configuración**

### **Checklist Pre-Producción**

#### **Datos Maestros**
- [ ] Empresa configurada completamente
- [ ] Certificados vigentes y funcionales
- [ ] FacturAPI respondiendo correctamente
- [ ] Series fiscales configuradas
- [ ] Usuarios con roles apropiados

#### **Pruebas Funcionales**
- [ ] Timbrar factura de prueba
- [ ] Cancelar CFDI de prueba
- [ ] Validar PDF/XML generados
- [ ] Probar re-facturación
- [ ] Verificar multisucursal

#### **Integración**
- [ ] Webhooks configurados (si aplica)
- [ ] APIs funcionando
- [ ] Respaldos configurados
- [ ] Monitoreo activo

---

## 🚀 **Go-Live**

### **Pasos Finales**

1. **Cambiar a Productivo**
   ```json
   {
     "facturapi_test_mode": 0
   }
   ```

2. **Migrar Datos**
   - Importar catálogo de clientes
   - Configurar productos finales
   - Validar series productivas

3. **Capacitar Usuarios**
   - Workflow de facturación
   - Proceso de cancelación
   - Resolución de errores comunes

4. **Monitoreo Inicial**
   - Verificar primeras facturas
   - Validar conectividad estable
   - Confirmar cumplimiento normativo

---

## 📞 **Soporte**

### **Recursos Disponibles**
- Documentación técnica en buzola-internal
- Guías de usuario en docs/user-guide/
- API reference en docs/api/

### **Contacto Técnico**
- Para configuración inicial: equipo implementación
- Para soporte operativo: soporte técnico
- Para desarrollo: equipo desarrollo

---

*Esta configuración inicial debe completarse antes de usar el sistema en producción*