# 🔧 API Reference - Draft Management

El módulo **Draft Management** proporciona APIs para gestionar el ciclo de vida completo de facturas en borrador.

## 📋 Endpoints Principales

### create_draft_invoice()

Crear una factura en modo borrador para revisión previa.

```python
@frappe.whitelist()
def create_draft_invoice(sales_invoice_name: str) -> Dict[str, Any]
```

#### Parámetros
- **sales_invoice_name** (`str`): Nombre del documento Sales Invoice

#### Respuesta Exitosa
```json
{
  "success": true,
  "message": "Borrador creado exitosamente",
  "draft_id": "draft_abc123",
  "preview_url": "https://factorapi.io/preview/draft_abc123"
}
```

#### Respuesta Error
```json
{
  "success": false,
  "message": "La factura no está marcada para crear como borrador"
}
```

#### Ejemplo de Uso
```python
import frappe
from facturacion_mexico.draft_management.api import create_draft_invoice

# Crear borrador para factura existente
result = create_draft_invoice("SINV-2025-001")

if result["success"]:
    print(f"Borrador creado: {result['draft_id']}")
    print(f"Preview: {result['preview_url']}")
else:
    print(f"Error: {result['message']}")
```

---

### approve_and_invoice_draft()

Aprobar un borrador existente y convertirlo a factura timbrada.

```python
@frappe.whitelist()
def approve_and_invoice_draft(sales_invoice_name: str, approved_by: Optional[str] = None) -> Dict[str, Any]
```

#### Parámetros
- **sales_invoice_name** (`str`): Nombre del documento Sales Invoice
- **approved_by** (`str`, opcional): Usuario que aprueba (por defecto usuario actual)

#### Respuesta Exitosa
```json
{
  "success": true,
  "message": "Borrador aprobado y timbrado exitosamente",
  "cfdi_uuid": "12345678-1234-1234-1234-123456789abc",
  "pdf_url": "https://factorapi.io/pdf/final_invoice.pdf"
}
```

#### Ejemplo de Uso
```python
# Aprobar borrador con usuario específico
result = approve_and_invoice_draft("SINV-2025-001", "supervisor@empresa.com")

if result["success"]:
    print(f"Factura timbrada: {result['cfdi_uuid']}")
    print(f"PDF disponible: {result['pdf_url']}")
```

---

### cancel_draft()

Cancelar un borrador sin proceder al timbrado.

```python
@frappe.whitelist()
def cancel_draft(sales_invoice_name: str) -> Dict[str, Any]
```

#### Parámetros
- **sales_invoice_name** (`str`): Nombre del documento Sales Invoice

#### Respuesta Exitosa
```json
{
  "success": true,
  "message": "Borrador cancelado exitosamente"
}
```

#### Ejemplo de Uso
```python
# Cancelar borrador para permitir edición
result = cancel_draft("SINV-2025-001")

if result["success"]:
    print("Borrador cancelado, puede editar la factura")
```

---

### get_draft_preview()

Obtener vista previa del borrador (XML y PDF).

```python
@frappe.whitelist()
def get_draft_preview(sales_invoice_name: str) -> Dict[str, Any]
```

#### Parámetros
- **sales_invoice_name** (`str`): Nombre del documento Sales Invoice

#### Respuesta Exitosa
```json
{
  "success": true,
  "preview_xml": "<cfdi:Comprobante>...</cfdi:Comprobante>",
  "preview_pdf_url": "https://factorapi.io/preview/draft_123.pdf",
  "draft_data": {
    "created_date": "2025-07-25 12:30:00",
    "status": "Borrador",
    "draft_id": "draft_abc123"
  }
}
```

#### Ejemplo de Uso
```python
# Obtener preview para revisión
result = get_draft_preview("SINV-2025-001")

if result["success"]:
    xml_content = result["preview_xml"]
    pdf_url = result["preview_pdf_url"]
    draft_info = result["draft_data"]
```

## 🔄 Flujo de Trabajo Programático

### Flujo Completo Automatizado

```python
def automated_draft_workflow(sales_invoice_name):
    """Ejemplo de flujo automatizado completo"""
    
    # 1. Crear borrador
    create_result = create_draft_invoice(sales_invoice_name)
    if not create_result["success"]:
        return {"error": "No se pudo crear borrador", "details": create_result}
    
    # 2. Obtener preview para validación
    preview_result = get_draft_preview(sales_invoice_name)
    if not preview_result["success"]:
        return {"error": "No se pudo obtener preview", "details": preview_result}
    
    # 3. Validación personalizada (ejemplo)
    xml_content = preview_result["preview_xml"]
    if not validate_xml_content(xml_content):
        # Cancelar borrador si validación falla
        cancel_draft(sales_invoice_name)
        return {"error": "Validación XML falló", "xml": xml_content}
    
    # 4. Aprobar automáticamente si pasa validación
    approve_result = approve_and_invoice_draft(sales_invoice_name, "sistema_automatico")
    if not approve_result["success"]:
        return {"error": "Error en aprobación", "details": approve_result}
    
    return {
        "success": True,
        "message": "Flujo completado exitosamente",
        "cfdi_uuid": approve_result["cfdi_uuid"],
        "pdf_url": approve_result["pdf_url"]
    }

def validate_xml_content(xml_content):
    """Función personalizada de validación"""
    # Implementar validaciones específicas del negocio
    return True  # Ejemplo simplificado
```

### Integración con Hooks

```python
# En hooks.py
doc_events = {
    "Sales Invoice": {
        "on_submit": "facturacion_mexico.draft_management.api.on_sales_invoice_submit",
        "validate": "facturacion_mexico.draft_management.api.validate_draft_workflow"
    }
}
```

## 🏗️ Funciones Auxiliares

### build_cfdi_payload()

Construye el payload para enviar a FacturAPI.

```python
def build_cfdi_payload(sales_invoice) -> Dict[str, Any]:
    """
    Construir payload CFDI para FacturAPI
    
    Args:
        sales_invoice: Documento Sales Invoice
        
    Returns:
        Dict con estructura para FacturAPI
    """
```

### Estados y Transiciones

```python
# Estados válidos para borradores
DRAFT_STATES = {
    "": "Sin estado de borrador",
    "Borrador": "Creado en FacturAPI, pendiente revisión",
    "En Revisión": "Proceso de aprobación en curso",
    "Aprobado": "Aprobado, listo para timbrar",
    "Timbrado": "Factura timbrada definitivamente"
}

# Transiciones válidas
VALID_TRANSITIONS = {
    "": ["Borrador"],
    "Borrador": ["En Revisión", ""],  # Puede cancelarse
    "En Revisión": ["Aprobado", "Borrador"],  # Puede rechazarse
    "Aprobado": ["Timbrado"],
    "Timbrado": []  # Estado final
}
```

## 🔒 Seguridad y Permisos

### Validaciones de Acceso

```python
def check_draft_permissions(sales_invoice_name, action):
    """
    Verificar permisos para acciones de borrador
    
    Args:
        sales_invoice_name: Nombre del documento
        action: "create", "approve", "cancel", "preview"
    """
    # Verificar permisos básicos del documento
    if not frappe.has_permission("Sales Invoice", "read", sales_invoice_name):
        frappe.throw("Sin permisos para acceder a la factura")
    
    # Verificar permisos específicos por acción
    if action == "approve" and not frappe.has_permission("Sales Invoice", "write", sales_invoice_name):
        frappe.throw("Sin permisos para aprobar facturas")
```

### Rate Limiting

```python
@frappe.whitelist()
@frappe.rate_limit(limit=10, window=300)  # 10 calls per 5 minutes
def create_draft_invoice(sales_invoice_name):
    # Implementación con rate limiting
    pass
```

## 🚨 Manejo de Errores

### Códigos de Error Comunes

| Código | Descripción | Solución |
|--------|-------------|----------|
| `DRAFT_001` | Factura no marcada como borrador | Activar checkbox "Crear como Borrador" |
| `DRAFT_002` | Borrador ya existe | Usar borrador existente o cancelar primero |
| `DRAFT_003` | Error comunicación FacturAPI | Verificar conectividad y credenciales |
| `DRAFT_004` | Estado inválido para operación | Verificar estado actual del borrador |
| `DRAFT_005` | Permisos insuficientes | Verificar roles y permisos de usuario |

### Logging y Debugging

```python
import frappe

def log_draft_operation(operation, sales_invoice_name, result):
    """Log operaciones de borrador para auditoría"""
    frappe.log_error(
        title=f"Draft Operation: {operation}",
        message=f"""
        Invoice: {sales_invoice_name}
        Operation: {operation}
        Result: {result}
        User: {frappe.session.user}
        Timestamp: {frappe.utils.now()}
        """
    )
```

## 🧪 Testing

### Unit Tests Disponibles

```python
# Ejecutar tests específicos de draft management
bench --site sitename run-tests --module facturacion_mexico.tests.test_draft_management

# Tests incluidos:
# - test_create_draft_invoice_success()
# - test_approve_and_invoice_draft_success()
# - test_cancel_draft_success()
# - test_get_draft_preview_success()
# - test_error_handling_and_rollback()
```

### Mocking para Development

```python
from unittest.mock import patch

# Mock FacturAPI para desarrollo
with patch('facturacion_mexico.draft_management.api.send_to_factorapi') as mock_api:
    mock_api.return_value = {
        "success": True,
        "draft_id": "test_draft_123",
        "preview_url": "https://test.factorapi.io/preview/test"
    }
    
    result = create_draft_invoice("TEST-INVOICE-001")
```

## 📈 Métricas y Monitoreo

### KPIs Sugeridos

```python
def get_draft_metrics(date_range=None):
    """Obtener métricas del sistema de borradores"""
    return {
        "drafts_created": "Total borradores creados",
        "drafts_approved": "Total borradores aprobados", 
        "drafts_cancelled": "Total borradores cancelados",
        "approval_rate": "Porcentaje de aprobación",
        "avg_review_time": "Tiempo promedio de revisión",
        "error_rate": "Tasa de errores en el proceso"
    }
```

## 📚 Referencias

- [User Guide - Facturas en Borrador](../user-guide/draft-invoices.md)
- [Development Guide - Draft Workflow](../development/draft-workflow.md)
- [API Reference - Main Index](index.md)