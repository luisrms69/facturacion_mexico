# Multi-sucursal - Gestión de Branches

Documentación de las funciones para gestión multi-sucursal y coordinación entre branches.

## Arquitectura Multi-sucursal

### Concepto de Branches

El sistema multi-sucursal permite gestionar múltiples sucursales de una empresa con:

- **Timbrado coordinado** entre sucursales
- **Selección automática** de branch según cliente/ubicación  
- **Failover automático** en caso de fallas
- **Load balancing** para distribución de carga

### Configuración de Branches

#### Estructura de Branch

```python
{
    "branch_code": "SUCURSAL_01",
    "branch_name": "Sucursal Centro",
    "pac_provider": "finkok",
    "pac_credentials": {...},
    "is_primary": True,
    "status": "active",
    "coordination_group": "GRUPO_A"
}
```

## Tests de Integración

### Branch Customer Selection Workflows

Pruebas de selección automática de branch basada en cliente.

#### `TestBranchCustomerSelection`

**Test Cases:**
- **test_customer_branch_assignment**: Asignación automática por cliente
- **test_geographic_branch_selection**: Selección por ubicación geográfica  
- **test_customer_preference_override**: Override manual de preferencias
- **test_branch_capacity_management**: Gestión de capacidad por branch

#### Lógica de Selección

```python
def select_branch_for_customer(customer_code, invoice_data):
    """
    Selecciona el branch óptimo para un cliente específico.
    
    Criterios de selección:
    1. Preferencia explícita del cliente
    2. Ubicación geográfica
    3. Capacidad disponible del branch
    4. Estado del PAC provider
    """
    # Implementación de algoritmo de selección
    pass
```

### CFDI Multi-sucursal Generation

Pruebas de generación coordinada de CFDI entre múltiples branches.

#### `TestCFDIMultisucursalGeneration`

**Test Cases:**
- **test_coordinated_cfdi_generation**: Generación coordinada
- **test_branch_failover_mechanism**: Mecanismo de failover
- **test_pac_coordination**: Coordinación entre PACs
- **test_xml_sequence_management**: Gestión de secuencias XML

#### Proceso de Coordinación

```python
def coordinate_cfdi_generation(branches, invoice_data):
    """
    Coordina la generación de CFDI entre múltiples branches.
    
    Proceso:
    1. Validar disponibilidad de branches
    2. Seleccionar branch principal
    3. Configurar branches de respaldo
    4. Ejecutar generación con failover
    """
    # Implementación de coordinación
    pass
```

## Tests de Producción

### Production Readiness Testing

Pruebas de preparación para producción del sistema multi-sucursal.

#### `TestMultisucursalProduction`

**Test Cases:**
- **test_high_volume_coordination**: Coordinación con alto volumen
- **test_branch_synchronization**: Sincronización entre branches  
- **test_pac_provider_failover**: Failover de proveedores PAC
- **test_xml_validation_under_load**: Validación XML bajo carga

### Coordinación PAC

#### Algoritmo de Balanceo

```python
def balance_pac_load(branches, current_load):
    """
    Distribuye la carga entre diferentes PAC providers.
    
    Factores considerados:
    1. Capacidad del PAC
    2. Latencia de respuesta
    3. Tasa de éxito histórica  
    4. Costo por transacción
    """
    # Implementación de balanceador
    pass
```

#### Manejo de Failover

```python
def handle_pac_failover(primary_branch, backup_branches):
    """
    Maneja el failover automático entre branches.
    
    Proceso:
    1. Detectar falla en branch principal
    2. Seleccionar branch de respaldo óptimo
    3. Transferir contexto de timbrado
    4. Reanudar operaciones sin pérdida
    """
    # Implementación de failover
    pass
```

## Métricas y Monitoreo

### KPIs del Sistema

#### Disponibilidad por Branch

```python
def calculate_branch_availability(branch_code, time_period):
    """
    Calcula la disponibilidad de un branch específico.
    
    Métricas:
    - Uptime percentage
    - Response time promedio
    - Tasa de éxito de timbrado
    - Volumen procesado
    """
    # Cálculo de métricas
    pass
```

#### Coordinación Global

```python
def monitor_global_coordination():
    """
    Monitorea la coordinación global del sistema.
    
    Indicadores:
    - Latencia de coordinación
    - Efectividad del failover
    - Distribución de carga
    - Sincronización de datos
    """
    # Monitoreo en tiempo real
    pass
```

---

## Configuración Avanzada

### Branch Groups

Los branches se pueden agrupar para coordinación específica:

```python
BRANCH_GROUPS = {
    "GRUPO_NORTE": ["TIJUANA_01", "MONTERREY_01", "CHIHUAHUA_01"],
    "GRUPO_SUR": ["CANCUN_01", "MERIDA_01", "VILLAHERMOSA_01"],
    "GRUPO_CENTRO": ["MEXICO_01", "GUADALAJARA_01", "PUEBLA_01"]
}
```

### Políticas de Failover

```python
FAILOVER_POLICIES = {
    "geographic_priority": True,  # Priorizar branches geográficamente cercanos
    "pac_diversity": True,        # Usar diferentes PACs en failover
    "load_balancing": True,       # Considerar carga actual
    "cost_optimization": False    # Optimizar por costo vs velocidad
}
```

---

!!! tip "Configuración Óptima"
    Para obtener el mejor rendimiento, configure al menos 3 branches por grupo de coordinación con diferentes proveedores PAC.

!!! warning "Sincronización"
    La sincronización entre branches es crítica. Asegure conectividad estable entre todas las sucursales.