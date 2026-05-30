# Addendas - Guía de Usuario

Guía completa para configurar y usar el sistema de addendas automáticas.

## 📄 ¿Qué son las Addendas?

Las addendas son documentos XML adicionales que se anexan al CFDI para cumplir con requisitos específicos de grandes clientes como:

- **Walmart México** - Formato de requestForPayment
- **Liverpool** - Datos de proveedor y pedido
- **Chedraui** - Información de orden de compra
- **Soriana** - Detalles de entrega y facturación
- **OXXO** - Códigos de producto específicos

## ⚙️ Configuración Inicial

### 1. Habilitar Addendas

En tu `site_config.json`:

```json
{
  "addendas_auto_generation": 1,
  "addenda_validation_strict": 1,
  "addenda_templates_path": "addendas/templates/"
}
```

### 2. Configurar Templates

Los templates están en `addendas/templates/`:

```
addendas/templates/
├── walmart_mx.xml
├── liverpool_mx.xml  
├── chedraui_mx.xml
├── soriana_mx.xml
└── custom/
    └── cliente_especial.xml
```

### 3. Configurar Tipos de Addenda

Ve a **Setup > Facturación México > Addenda Types**:

#### Walmart México

```
Addenda Type: WALMART_MX
Template File: walmart_mx.xml
Auto Apply: ✓ (marcado)
Required Fields:
- purchase_order
- vendor_number  
- store_number
```

#### Liverpool

```
Addenda Type: LIVERPOOL_MX
Template File: liverpool_mx.xml
Auto Apply: ✓ (marcado)
Required Fields:
- proveedor_id
- num_pedido
- sucursal
```

## 👥 Configurar Clientes

### Cliente con Addenda Automática

1. Ve a **Selling > Customer**
2. Abrir o crear cliente (ej: "Walmart de México")
3. En sección **Facturación México**:
   - Marcar **FM Addenda Required**: ✓
   - Seleccionar **Addenda Type**: `WALMART_MX`
   - Configurar **Auto Apply**: ✓

### Campos Específicos por Cliente

#### Para Walmart

En **Customer > Custom Fields**:

```
Vendor Number: WAL001234
Store Network: Walmart México
Payment Terms: NET30
Purchase Order Pattern: ^\d{10}$
```

#### Para Liverpool

```
Proveedor ID: LIV001234  
Sucursal Code: LIV-CENTRO
Num Pedido Pattern: ^LP\d{8}$
```

## 📋 Uso Diario

### Crear Factura con Addenda

#### Proceso Automático

1. Crear **Sales Invoice** para cliente con addenda configurada
2. Completar campos obligatorios:
   - **Purchase Order**: 1234567890 (para Walmart)
   - **Store Number**: 2587
3. **Submit** la factura
4. La addenda se genera automáticamente

#### Verificar Addenda Generada

Después del submit:

```python
# Desde consola
import frappe

invoice = frappe.get_doc("Sales Invoice", "SINV-00001")
print(f"Addenda generada: {bool(invoice.get('addenda_xml'))}")
print(f"Tipo de addenda: {invoice.get('addenda_type')}")
print(f"Validación: {invoice.get('addenda_validation_status')}")
```

### Proceso Manual

Si necesitas generar la addenda manualmente:

1. En Sales Invoice, ir a **More > Generate Addenda**
2. Seleccionar tipo de addenda
3. Completar campos requeridos
4. Clic en **Generate**

## 🔧 Templates Personalizados

### Estructura de Template

#### Walmart Template (walmart_mx.xml)

```xml
<cfdi:Addenda>
    <Walmart>
        <requestForPayment>
            <PaymentTerms>{{ payment_terms | default('NET30') }}</PaymentTerms>
            <InvoiceNumber>{{ invoice_number }}</InvoiceNumber>
            <PurchaseOrder>{{ purchase_order | rfc_format }}</PurchaseOrder>
            <VendorNumber>{{ vendor_number }}</VendorNumber>
            <StoreNumber>{{ store_number }}</StoreNumber>
            <InvoiceDate>{{ invoice_date | sat_datetime }}</InvoiceDate>
            <InvoiceAmount currency="MXN">{{ grand_total | round(2) }}</InvoiceAmount>
        </requestForPayment>
    </Walmart>
</cfdi:Addenda>
```

### Custom Filters

#### Filtros Disponibles

- `sat_datetime`: Formato de fecha SAT (AAAA-MM-DDTHH:MM:SS)
- `rfc_format`: Validación de formato RFC
- `currency_format`: Formato de moneda (2 decimales)
- `uppercase`: Convertir a mayúsculas
- `remove_accents`: Quitar acentos

#### Crear Filtros Personalizados

```python
# En hooks.py
def custom_addenda_filters():
    return {
        "walmart_date": lambda date: date.strftime("%Y%m%d"),
        "pad_zeros": lambda value, length: str(value).zfill(length),
        "truncate": lambda text, max_len: text[:max_len] if text else ""
    }
```

### Crear Template Personalizado

#### 1. Crear archivo XML

`addendas/templates/custom/mi_cliente.xml`:

```xml
<cfdi:Addenda>
    <MiCliente>
        <DatosFactura>
            <NumeroFactura>{{ invoice_number }}</NumeroFactura>
            <FechaFactura>{{ invoice_date | sat_datetime }}</FechaFactura>
            <CodigoCliente>{{ customer_code | uppercase }}</CodigoCliente>
            <ImporteTotal>{{ grand_total | currency_format }}</ImporteTotal>
        </DatosFactura>
        <DetalleItems>
            {% for item in items %}
            <Item>
                <Codigo>{{ item.item_code }}</Codigo>
                <Descripcion>{{ item.description | truncate(50) }}</Descripcion>
                <Cantidad>{{ item.qty }}</Cantidad>
                <Precio>{{ item.rate | currency_format }}</Precio>
            </Item>
            {% endfor %}
        </DetalleItems>
    </MiCliente>
</cfdi:Addenda>
```

#### 2. Registrar Template

```python
# Setup del template personalizado
frappe.get_doc({
    "doctype": "Addenda Type",
    "addenda_type": "MI_CLIENTE_MX",
    "template_file": "custom/mi_cliente.xml",
    "auto_apply": True,
    "required_fields": ["customer_code", "invoice_date"],
    "validation_rules": {
        "customer_code": r"^MC\d{6}$"
    }
}).insert()
```

## 🧪 Validación y Testing

### Validar Addenda

```python
# Validar addenda generada
from facturacion_mexico.addendas.validator import validate_addenda

invoice = frappe.get_doc("Sales Invoice", "SINV-00001")
result = validate_addenda(invoice.addenda_xml, invoice.addenda_type)

print(f"Válida: {result.is_valid}")
if not result.is_valid:
    print(f"Errores: {result.errors}")
```

### Test de Generación

```python
# Test completo de generación
from facturacion_mexico.addendas.generator import generate_test_addenda

# Generar addenda de prueba
test_data = {
    "customer": "Walmart de México",
    "purchase_order": "1234567890",
    "vendor_number": "WAL001234",
    "store_number": "2587"
}

addenda_xml = generate_test_addenda("WALMART_MX", test_data)
print("Addenda generada exitosamente")
```

## 📊 Monitoreo y Reportes

### Reporte de Addendas

Ve a **Reports > Facturación México > Addenda Generation Report**:

- Addendas generadas por período
- Tasa de éxito por tipo
- Errores de validación frecuentes
- Clientes sin configuración

### Métricas de Performance

```python
# Métricas de addendas
from facturacion_mexico.addendas.metrics import get_addenda_metrics

metrics = get_addenda_metrics(days=30)
print(f"Total generadas: {metrics['total_generated']}")
print(f"Tasa de éxito: {metrics['success_rate']}%")
print(f"Tiempo promedio: {metrics['avg_generation_time']}ms")
```

## 🔄 Mantenimiento

### Actualizar Templates

1. **Backup del template actual**:
   ```bash
   cp addendas/templates/walmart_mx.xml addendas/templates/backup/walmart_mx_v1.xml
   ```

2. **Actualizar template**:
   - Editar el archivo XML
   - Validar sintaxis
   - Probar con datos de ejemplo

3. **Deploy gradual**:
   ```python
   # Activar nueva versión gradualmente
   frappe.db.set_value("Addenda Type", "WALMART_MX", "template_version", "v2.0")
   ```

### Migrar Configuraciones

```python
# Script de migración
def migrate_addenda_configs():
    """Migrar configuraciones de addenda a nueva versión."""
    
    # Actualizar tipos existentes
    old_types = frappe.get_all("Addenda Type", 
                              filters={"template_version": ["<", "2.0"]})
    
    for addenda_type in old_types:
        doc = frappe.get_doc("Addenda Type", addenda_type.name)
        
        # Actualizar configuración
        doc.template_version = "2.0"
        doc.validation_rules = upgrade_validation_rules(doc.validation_rules)
        doc.save()
        
        print(f"Migrado: {doc.addenda_type}")
```

## 🚨 Troubleshooting

### Addenda No Se Genera

**Síntomas:**
- Campo `addenda_xml` vacío después del submit
- No aparece en el PDF del CFDI

**Solución:**
1. Verificar que el cliente tenga `FM Addenda Required` marcado
2. Confirmar que el tipo de addenda esté configurado
3. Revisar que `auto_apply` esté habilitado

```python
# Debug de configuración
customer = frappe.get_doc("Customer", "WALMART-001")
print(f"Addenda required: {customer.get('fm_addenda_required')}")
print(f"Addenda type: {customer.get('addenda_type')}")

addenda_type = frappe.get_doc("Addenda Type", customer.addenda_type)
print(f"Auto apply: {addenda_type.auto_apply}")
```

### Error de Validación

**Síntomas:**
- Addenda se genera pero falla validación
- Errores en XML structure

**Solución:**
1. Revisar template syntax
2. Verificar que todos los campos requeridos estén presentes
3. Validar formato de datos

```python
# Debug de validación
from facturacion_mexico.addendas.validator import validate_addenda_xml

xml_content = invoice.get('addenda_xml')
validation_result = validate_addenda_xml(xml_content)

if not validation_result.is_valid:
    for error in validation_result.errors:
        print(f"Error: {error['message']} en línea {error['line']}")
```

### Template No Se Encuentra

**Síntomas:**
- Error "Template not found"
- Template file missing

**Solución:**
1. Verificar que el archivo existe en `addendas/templates/`
2. Confirmar permisos de lectura
3. Validar path en configuración

```bash
# Verificar templates disponibles
ls -la addendas/templates/
find . -name "*.xml" -type f | grep addendas
```

---

!!! success "Automatización Completa"
    Las addendas se generan automáticamente sin intervención manual una vez configuradas.

!!! tip "Validación Estricta"
    Activa `addenda_validation_strict: 1` para detectar errores temprano en desarrollo.

!!! warning "Backup Templates"
    Siempre mantén backup de templates antes de actualizaciones para permitir rollback rápido.