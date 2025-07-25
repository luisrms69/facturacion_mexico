# Addendas - Generación Dinámica

Sistema avanzado de generación automática de addendas según reglas de negocio específicas por cliente.

## Arquitectura de Addendas

### Concepto General

Las addendas son documentos XML adicionales que se anexan al CFDI para cumplir con requisitos específicos de clientes corporativos como Walmart, Liverpool, Chedraui, etc.

#### Características del Sistema:
- **Generación dinámica** basada en templates configurables
- **Validación automática** de formato y contenido
- **Multi-formato** (XML, JSON, EDI)
- **Integración seamless** con el proceso de timbrado

### Tipos de Addenda Soportados

#### Retail Chains (Cadenas Comerciales)

```python
ADDENDA_TYPES = {
    "WALMART_MX": {
        "template": "walmart_mx.xml",
        "required_fields": ["purchase_order", "vendor_number", "store_number"],
        "validation_rules": {"purchase_order": r"^\d{10}$"},
        "auto_apply": True
    },
    "LIVERPOOL_MX": {
        "template": "liverpool_mx.xml", 
        "required_fields": ["proveedor_id", "num_pedido", "sucursal"],
        "validation_rules": {"proveedor_id": r"^LIV\d{6}$"},
        "auto_apply": True
    },
    "CHEDRAUI_MX": {
        "template": "chedraui_mx.xml",
        "required_fields": ["codigo_proveedor", "orden_compra"],
        "validation_rules": {"codigo_proveedor": r"^CHE\d{5}$"},
        "auto_apply": False  # Manual approval required
    }
}
```

## Tests de Validación

### End-to-End Validation Workflows

Pruebas completas de validación de addendas desde generación hasta aplicación.

#### `TestAddendaValidationE2E`

**Test Cases Principales:**

##### `test_walmart_addenda_generation()`
```python
def test_walmart_addenda_generation():
    """
    Prueba generación completa de addenda Walmart.
    
    Proceso:
    1. Crear Sales Invoice con datos Walmart
    2. Aplicar template de addenda automáticamente  
    3. Validar estructura XML generada
    4. Verificar campos obligatorios
    5. Confirmar integración con CFDI
    """
    # Datos de prueba Walmart
    invoice_data = {
        "customer": "Walmart de México",
        "purchase_order": "1234567890",
        "vendor_number": "WAL001234",
        "store_number": "2587"
    }
    
    # Generar addenda
    addenda_xml = generate_addenda(invoice_data, "WALMART_MX")
    
    # Validaciones
    assert_xml_structure_valid(addenda_xml)
    assert_required_fields_present(addenda_xml, WALMART_REQUIRED_FIELDS)
```

##### `test_dynamic_field_mapping()`
```python
def test_dynamic_field_mapping():
    """
    Prueba el mapeo dinámico de campos según el tipo de cliente.
    
    Escenarios:
    - Mapeo automático por código de cliente
    - Override manual de mappings
    - Validación de campos requeridos
    - Handling de campos opcionales
    """
    # Test con diferentes tipos de clientes
    for customer_type in ["WALMART", "LIVERPOOL", "CHEDRAUI"]:
        mapping = get_dynamic_field_mapping(customer_type)
        assert validate_mapping_completeness(mapping)
```

### Multi-sucursal con Addendas

Pruebas de generación de addendas en entorno multi-sucursal.

#### `TestAddendaMultisucursalWorkflows`

**Test Cases:**

##### `test_branch_specific_addenda_rules()`
```python
def test_branch_specific_addenda_rules():
    """
    Prueba reglas específicas de addenda por branch.
    
    Casos:
    - Addendas diferentes por sucursal del mismo cliente
    - Priorización de reglas por geografía
    - Fallback a reglas generales
    """
    branches = ["NORTE_01", "SUR_01", "CENTRO_01"]
    
    for branch in branches:
        rules = get_addenda_rules_for_branch(branch, "WALMART_MX")
        assert validate_branch_specific_rules(rules, branch)
```

##### `test_coordinated_addenda_generation()`
```python
def test_coordinated_addenda_generation():
    """
    Prueba coordinación de generación entre múltiples branches.
    
    Escenarios:
    - Generación paralela en múltiples sucursales
    - Sincronización de templates actualizados
    - Manejo de conflicts en reglas
    """
    # Coordinación multi-branch
    results = coordinate_addenda_generation(
        branches=["SUC_A", "SUC_B", "SUC_C"],
        customer="WALMART_MX",
        invoice_batch=[...]
    )
    
    assert all_branches_synchronized(results)
```

## Tests de Stress

### Addendas Stress Testing

Pruebas de rendimiento y resistencia del sistema de addendas.

#### `TestAddendaStressTesting`

**Test Cases de Carga:**

##### `test_massive_concurrent_addenda_generation()`
```python
def test_massive_concurrent_addenda_generation():
    """
    Prueba generación masiva concurrente de addendas.
    
    Parámetros de Stress:
    - 1000+ addendas simultáneas
    - 10+ tipos diferentes de templates
    - 5+ branches coordinados
    - 30 segundos de duración sostenida
    """
    concurrent_requests = 1000
    addenda_types = ["WALMART", "LIVERPOOL", "CHEDRAUI", "SORIANA", "OXXO"]
    
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = []
        for i in range(concurrent_requests):
            addenda_type = random.choice(addenda_types)
            future = executor.submit(generate_addenda_stress, addenda_type, i)
            futures.append(future)
        
        # Validar resultados
        results = [f.result() for f in futures]
        success_rate = sum(1 for r in results if r["success"]) / len(results)
        
        assert success_rate >= 0.95  # 95% minimum success rate
```

##### `test_template_hot_swapping()`
```python
def test_template_hot_swapping():
    """
    Prueba intercambio de templates en caliente durante operación.
    
    Proceso:
    1. Iniciar generación continua de addendas
    2. Actualizar templates durante operación
    3. Verificar transición sin interrupciones
    4. Validar consistency de documentos generados
    """
    # Generación continua en background
    with continuous_addenda_generation():
        # Hot swap de templates
        for template_version in ["v1.0", "v1.1", "v1.2"]:
            update_template_version("WALMART_MX", template_version) 
            time.sleep(10)  # Permitir transición
            
            # Validar consistency
            recent_addendas = get_recent_addendas(last_minutes=1)
            assert all_addendas_valid(recent_addendas)
```

## Algoritmos de Generación

### Template Engine

#### Sistema de Plantillas

```python
class AddendaTemplateEngine:
    """
    Motor de plantillas para generación dinámica de addendas.
    
    Características:
    - Jinja2-based templating
    - Custom filters for SAT compliance
    - Multi-language support (ES/EN)
    - Hot-reloading de templates
    """
    
    def __init__(self, template_path: str):
        self.template_path = template_path
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_path),
            autoescape=select_autoescape(['xml', 'html'])
        )
        
        # Custom filters
        self.jinja_env.filters['sat_datetime'] = self._format_sat_datetime
        self.jinja_env.filters['rfc_format'] = self._format_rfc
        
    def generate_addenda(self, template_name: str, context: dict) -> str:
        """
        Genera addenda usando template y contexto dados.
        
        Args:
            template_name: Nombre del template (ej: 'walmart_mx.xml')
            context: Datos para renderizar el template
            
        Returns:
            XML string de la addenda generada
        """
        template = self.jinja_env.get_template(template_name)
        return template.render(**context)
```

### Validation Engine

#### Sistema de Validación

```python
class AddendaValidator:
    """
    Validador completo de addendas generadas.
    
    Validaciones:
    - XML structure compliance
    - SAT catalog consistency  
    - Client-specific business rules
    - Character encoding (UTF-8)
    """
    
    def validate_addenda(self, addenda_xml: str, addenda_type: str) -> ValidationResult:
        """
        Valida una addenda generada contra todas las reglas aplicables.
        
        Args:
            addenda_xml: XML de la addenda a validar
            addenda_type: Tipo de addenda (WALMART_MX, etc.)
            
        Returns:
            ValidationResult con detalles de la validación
        """
        result = ValidationResult()
        
        # 1. XML structure validation
        result.merge(self._validate_xml_structure(addenda_xml))
        
        # 2. SAT compliance validation  
        result.merge(self._validate_sat_compliance(addenda_xml))
        
        # 3. Client-specific rules
        result.merge(self._validate_client_rules(addenda_xml, addenda_type))
        
        return result
```

---

## Configuración Avanzada

### Custom Templates

Para crear templates personalizados:

```xml
<!-- walmart_mx.xml template -->
<cfdi:Addenda>
    <Walmart>
        <requestForPayment>
            <PaymentTerms>{{ payment_terms | default('NET30') }}</PaymentTerms>
            <InvoiceNumber>{{ invoice_number }}</InvoiceNumber>
            <PurchaseOrder>{{ purchase_order | rfc_format }}</PurchaseOrder>
            <VendorNumber>{{ vendor_number }}</VendorNumber>
            <StoreNumber>{{ store_number }}</StoreNumber>
            <InvoiceDate>{{ invoice_date | sat_datetime }}</InvoiceDate>
        </requestForPayment>
    </Walmart>
</cfdi:Addenda>
```

### Business Rules

```python
BUSINESS_RULES = {
    "WALMART_MX": {
        "required_fields": ["purchase_order", "vendor_number", "store_number"],
        "format_validations": {
            "purchase_order": r"^\d{10}$",
            "vendor_number": r"^WAL\d{6}$", 
            "store_number": r"^\d{4}$"
        },
        "auto_apply_conditions": [
            "customer.customer_name LIKE '%Walmart%'",
            "customer.tax_id LIKE 'WMT%'"
        ]
    }
}
```

---

!!! success "Production Ready"
    El sistema de addendas ha pasado todas las pruebas de stress con 95%+ de tasa de éxito bajo carga máxima.

!!! info "Extensibilidad" 
    Nuevos tipos de addenda se pueden agregar fácilmente creando templates XML y definiendo reglas de validación específicas.