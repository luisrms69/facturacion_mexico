# Módulo Multi-Sucursal

Este módulo maneja la funcionalidad de múltiples sucursales y lugar de expedición para el sistema de facturación mexicana.

## Funcionalidades

### Lugar de Expedición
- Determinación automática del lugar de expedición basado en reglas de negocio
- Soporte para múltiples fuentes de información (warehouse, customer, company)
- Validación de códigos postales mexicanos
- Integración automática con Sales Invoice

### APIs Disponibles

#### `get_lugar_expedicion(company, sales_invoice=None, customer=None)`
Obtiene el lugar de expedición apropiado según las reglas de negocio.

#### `get_sucursales_disponibles(company)`
Lista todas las sucursales disponibles para una empresa.

#### `establecer_lugar_expedicion(sales_invoice, codigo_postal, force_update=False)`
Establece manualmente el lugar de expedición en una factura.

#### `validar_configuracion_sucursales(company)`
Valida la configuración de sucursales y proporciona recomendaciones.

#### `bulk_set_lugar_expedicion(invoices, codigo_postal)`
Establece lugar de expedición en múltiples facturas.

#### `get_facturas_sin_lugar_expedicion(company, days=30, limit=100)`
Encuentra facturas que no tienen lugar de expedición configurado.

## Reglas de Negocio

### Orden de Prioridad para Lugar de Expedición:
1. Campo específico en Sales Invoice (`fm_lugar_expedicion`)
2. Warehouse del primer item en la factura
3. Shipping address de la factura
4. Configuración específica del Customer
5. Configuración por Territory
6. Dirección principal del Customer
7. Configuración por defecto de la Company
8. Dirección de la Company
9. Fallback (código postal 00000)

### Validaciones:
- Códigos postales deben ser de 5 dígitos numéricos
- Facturas submitted requieren lugar de expedición válido
- Se registra auditoría de cambios automáticos

## Hooks Automáticos

- `on_sales_invoice_validate`: Establece lugar de expedición automáticamente
- `on_sales_invoice_submit`: Valida que el lugar de expedición esté presente y sea válido

## Campos Personalizados Requeridos

Para funcionalidad completa, se requieren los siguientes campos personalizados:

### Sales Invoice:
- `fm_lugar_expedicion_cp`: Código postal del lugar de expedición
- `fm_lugar_expedicion_info`: JSON con información detallada

### Company:
- `fm_lugar_expedicion_default`: Lugar de expedición por defecto

### Customer:
- `fm_lugar_expedicion_preferido`: Lugar de expedición preferido

### Warehouse:
- `fm_codigo_postal`: Código postal del warehouse
- `fm_es_sucursal`: Marcar si es una sucursal

## Uso

```python
from facturacion_mexico.multi_sucursal.utils import LugarExpedicionManager

# Obtener lugar de expedición
lugar = LugarExpedicionManager.get_lugar_expedicion("Mi Empresa", customer="CLIENTE001")

# Validar código postal
is_valid = LugarExpedicionManager.validate_codigo_postal("06600")

# Obtener sucursales
sucursales = LugarExpedicionManager.get_available_sucursales("Mi Empresa")
```

## Testing

El módulo incluye validaciones automáticas y logging de errores. Para testing:

```python
# API testing
import frappe
from facturacion_mexico.multi_sucursal.api import get_lugar_expedicion

result = get_lugar_expedicion("Mi Empresa")
print(result)
```