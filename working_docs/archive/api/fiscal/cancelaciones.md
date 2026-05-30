# 🔌 API Endpoints - Cancelaciones Fiscales

Esta sección documenta los endpoints públicos disponibles para integración con el sistema de cancelaciones fiscales.

## 📋 **Endpoints Disponibles**

### **POST /api/method/facturacion_mexico.fiscal_operations.cancelar_cfdi**

Cancela un CFDI timbrado con motivos SAT específicos.

#### **Parámetros**
```json
{
  "si_name": "SI-2024-00001",
  "motivo": "02",
  "uuid_sustituto": "12345678-1234-1234-1234-123456789012"
}
```

#### **Respuesta Exitosa**
```json
{
  "message": "CFDI cancelado exitosamente",
  "status": "success",
  "data": {
    "si_name": "SI-2024-00001",
    "fm_fiscal_status": "CANCELADO",
    "cancellation_uuid": "87654321-4321-4321-4321-210987654321"
  }
}
```

---

### **POST /api/method/facturacion_mexico.fiscal_operations.refacturar_misma_si**

Desvincula Sales Invoice de FFM cancelada para permitir re-facturación.

#### **Parámetros**
```json
{
  "si_name": "SI-2024-00001"
}
```

#### **Respuesta Exitosa**
```json
{
  "message": "Sales Invoice preparado para re-facturación",
  "status": "success",
  "data": {
    "si_name": "SI-2024-00001",
    "fm_fiscal_status": "",
    "fm_factura_fiscal_mx": ""
  }
}
```

---

### **GET /api/method/facturacion_mexico.fiscal_operations.get_fiscal_status**

Consulta el estado fiscal actual de una Sales Invoice.

#### **Parámetros**
```
?si_name=SI-2024-00001
```

#### **Respuesta**
```json
{
  "message": "Estado fiscal consultado",
  "status": "success",
  "data": {
    "si_name": "SI-2024-00001",
    "fm_fiscal_status": "TIMBRADO",
    "fm_cfdi_uuid": "12345678-1234-1234-1234-123456789012",
    "fm_factura_fiscal_mx": "FFMX-2024-00001",
    "can_cancel": true,
    "can_refacture": false
  }
}
```

---

### **POST /api/method/facturacion_mexico.fiscal_operations.sustituir_cfdi**

Inicia proceso de sustitución CFDI (motivo 01).

#### **Parámetros**
```json
{
  "si_name": "SI-2024-00001"
}
```

#### **Respuesta Exitosa**
```json
{
  "message": "Sales Invoice de sustitución creado",
  "status": "success",
  "data": {
    "original_si": "SI-2024-00001",
    "substitute_si": "SI-2024-00002",
    "substitute_status": "Draft"
  }
}
```

---

## 🔐 **Autenticación**

Todos los endpoints requieren autenticación via:

### **API Key & Secret**
```bash
curl -X POST \
  -H "Authorization: token api_key:api_secret" \
  -H "Content-Type: application/json" \
  -d '{"si_name": "SI-2024-00001", "motivo": "02"}' \
  https://tu-sitio.com/api/method/facturacion_mexico.fiscal_operations.cancelar_cfdi
```

### **Session Cookie**
Para aplicaciones web integradas que ya manejan sesión de usuario.

---

## ⚠️ **Códigos de Error**

### **400 - Bad Request**
```json
{
  "message": "Parámetros inválidos",
  "status": "error",
  "error": "si_name es requerido"
}
```

### **403 - Forbidden**
```json
{
  "message": "Permisos insuficientes",
  "status": "error",
  "error": "Usuario no tiene permisos para cancelar CFDI"
}
```

### **404 - Not Found**
```json
{
  "message": "Sales Invoice no encontrado",
  "status": "error",
  "error": "No existe SI-2024-99999"
}
```

### **409 - Conflict**
```json
{
  "message": "Estado fiscal inválido",
  "status": "error",
  "error": "CFDI ya está cancelado"
}
```

### **500 - Internal Server Error**
```json
{
  "message": "Error interno del servidor",
  "status": "error",
  "error": "Error de conexión con FacturAPI"
}
```

---

## 🔄 **Estados Fiscales**

### **Estados Válidos**
- `BORRADOR` - Factura no timbrada
- `TIMBRADO` - CFDI vigente
- `CANCELADO` - CFDI cancelado
- `ERROR` - Error en proceso fiscal

### **Transiciones Permitidas**
- `BORRADOR` → `TIMBRADO` (timbrado)
- `TIMBRADO` → `CANCELADO` (cancelación)
- `CANCELADO` → `BORRADOR` (re-facturación)

---

## 📝 **Ejemplos de Integración**

### **JavaScript/Node.js**
```javascript
const axios = require('axios');

async function cancelarCFDI(siName, motivo) {
  try {
    const response = await axios.post(
      'https://tu-sitio.com/api/method/facturacion_mexico.fiscal_operations.cancelar_cfdi',
      {
        si_name: siName,
        motivo: motivo
      },
      {
        headers: {
          'Authorization': 'token api_key:api_secret',
          'Content-Type': 'application/json'
        }
      }
    );

    return response.data;
  } catch (error) {
    console.error('Error cancelando CFDI:', error.response.data);
    throw error;
  }
}
```

### **Python**
```python
import requests

def cancelar_cfdi(si_name, motivo):
    url = 'https://tu-sitio.com/api/method/facturacion_mexico.fiscal_operations.cancelar_cfdi'
    headers = {
        'Authorization': 'token api_key:api_secret',
        'Content-Type': 'application/json'
    }
    data = {
        'si_name': si_name,
        'motivo': motivo
    }

    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()
    return response.json()
```

---

## 📋 **Rate Limits**

- **Cancelaciones:** 10 por minuto por usuario
- **Consultas estado:** 100 por minuto por usuario
- **Re-facturación:** 5 por minuto por usuario

---

*Para documentación completa de integración y casos avanzados, contactar equipo técnico*