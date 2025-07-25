# CFDI - Timbrado y Validación

Documentación de las funciones principales para generación y timbrado de CFDI 4.0.

## Hooks de Sales Invoice

### Sales Invoice Submit Handler

El handler principal para procesamiento de addendas durante submit de Sales Invoice.

#### `sales_invoice_on_submit(doc, method)`

Hook handler que se ejecuta después de que la factura es enviada exitosamente.

**Parámetros:**
- `doc` (Document): Documento Sales Invoice
- `method` (str): Método de hook ('on_submit')

**Flujo de Procesamiento:**
1. Verifica si debe procesar addenda con `should_process_addenda_on_submit()`
2. Procesa addenda después del submit con `process_addenda_after_submit()`
3. Maneja errores sin interrumpir el flujo principal

**Código:**
```python
def sales_invoice_on_submit(doc, method):
    try:
        if not should_process_addenda_on_submit(doc):
            return
        process_addenda_after_submit(doc)
    except Exception as e:
        frappe.log_error(f"Error procesando addenda en submit de {doc.name}: {e!s}")
```

#### `should_process_addenda_on_submit(doc) -> bool`

Determina si se debe procesar addenda durante el submit.

**Parámetros:**
- `doc` (Document): Documento Sales Invoice

**Retorna:**
- `bool`: True si debe procesar addenda, False en caso contrario

**Lógica de Validación:**
1. Verifica si `fm_addenda_required` está activado
2. Obtiene configuración de addenda del cliente
3. Valida si `auto_apply` está habilitado

### Sales Invoice Validate Handler

Handler para validaciones durante la validación de Sales Invoice.

## Instalación y Setup

### Funciones de Instalación

#### `before_tests()`

Configura el entorno para pruebas automatizadas.

**Funcionalidades:**
- Crea datos básicos de prueba
- Configura catalogos SAT mínimos
- Establece configuración de company básica
- Crea warehouse types y UOMs necesarios

#### `_create_basic_addenda_types()`

Crea tipos de addenda básicos para el sistema.

**Tipos Creados:**
- **WALMART_MX**: Addenda para Walmart México
- **LIVERPOOL_MX**: Addenda para Liverpool
- **CHEDRAUI_MX**: Addenda para Chedraui
- **SORIANA_MX**: Addenda para Soriana

**Configuración por Tipo:**
```python
{
    "addenda_type": "WALMART_MX",
    "template_path": "addendas/templates/walmart_mx.xml",
    "validation_rules": {...},
    "auto_apply": True
}
```

#### `_create_basic_test_customers()`

Crea clientes de prueba con configuraciones específicas.

**Clientes de Prueba:**
- **Walmart de México**: Con addenda automática habilitada
- **Liverpool Sucursal**: Con configuración multi-sucursal
- **Chedraui Regional**: Con validaciones específicas

#### `_ensure_basic_erpnext_records()`

Asegura que existan registros básicos de ERPNext necesarios.

**Registros Verificados:**
- Company con configuración fiscal
- Accounts con mapping SAT
- Tax Categories básicas
- Cost Centers por sucursal

---

## Funciones Auxiliares

### Validación de Documentos

#### `validate_cfdi_requirements(doc)`

Valida que el documento cumpla con requisitos CFDI.

**Validaciones:**
- RFC válido del cliente
- Datos fiscales completos
- Items con códigos SAT
- Moneda y tipo de cambio válidos

### Generación de XML

#### `generate_cfdi_xml(doc)`

Genera el XML CFDI 4.0 para el documento.

**Proceso:**
1. Valida datos del documento
2. Aplica catalogos SAT
3. Genera estructura XML
4. Valida contra XSD oficial
5. Retorna XML listo para timbrado

---

!!! info "Integración PAC"
    El timbrado se realiza automáticamente tras la generación del XML usando la configuración PAC definida en Site Config.

!!! warning "Validaciones"
    Todas las funciones incluyen validaciones estrictas según normativas SAT para CFDI 4.0.