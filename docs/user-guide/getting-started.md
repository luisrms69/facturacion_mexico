# Primeros Pasos - Facturación México

Guía completa para comenzar a usar el sistema de facturación electrónica.

## 🚀 Instalación Inicial

### Requisitos Previos

Antes de instalar, asegúrate de tener:

- **Frappe Framework v15** instalado y funcionando
- **ERPNext** (opcional pero recomendado)
- **Python 3.8+** con todas las dependencias
- **Certificados SAT** válidos para timbrado
- **Credenciales PAC** activas

### Instalación Paso a Paso

#### 1. Obtener la App

=== "Desde GitHub"

    ```bash
    # Clonar el repositorio
    cd /path/to/frappe-bench
    bench get-app facturacion_mexico https://github.com/tu-org/facturacion_mexico.git
    ```

=== "Desde Local"

    ```bash
    # Si tienes el código localmente
    bench get-app facturacion_mexico /path/to/local/repo
    ```

#### 2. Instalar en Site

```bash
# Instalar en tu site
bench --site tu-sitio.local install-app facturacion_mexico

# Verificar instalación
bench --site tu-sitio.local console
```

```python
# En la consola de Frappe
import frappe
frappe.get_installed_apps()
# Debe aparecer 'facturacion_mexico' en la lista
```

#### 3. Configuración Inicial

```bash
# Ejecutar setup inicial
bench --site tu-sitio.local execute facturacion_mexico.install.before_tests

# Esto creará:
# - Datos básicos de prueba
# - Catalogos SAT mínimos  
# - Configuración de company
# - Tipos de addenda básicos
```

## ⚙️ Configuración Básica

### Site Config

Agrega la siguiente configuración a tu `site_config.json`:

```json
{
  "pac_provider": "finkok",
  "pac_username": "tu_usuario_pac",
  "pac_password": "tu_password_pac",
  "pac_test_mode": 1,
  "multisucursal_enabled": 1,
  "addendas_auto_generation": 1,
  "cfdi_version": "4.0"
}
```

### Certificados SAT

#### Subir Certificados

1. Ve a **Setup > Facturación México > Certificados SAT**
2. Sube tu archivo `.cer` (certificado público)
3. Sube tu archivo `.key` (llave privada)
4. Ingresa la contraseña de la llave privada
5. Verifica que el estado sea "Válido"

```python
# Verificar certificados desde consola
import frappe
from facturacion_mexico.utils.certificates import validate_certificates

result = validate_certificates()
print(f"Certificados válidos: {result['valid']}")
print(f"Vigencia hasta: {result['expires_on']}")
```

### Configuración de Company

#### Datos Fiscales Obligatorios

Ve a **Setup > Company** y completa:

- **Tax ID (RFC)**: RFC de tu empresa
- **Régimen Fiscal**: Selecciona de la lista SAT
- **Dirección Fiscal**: Completa con código postal válido
- **Moneda Base**: MXN (requerido)

#### Configuración Multi-sucursal (Opcional)

Si usarás múltiples sucursales:

```python
# Crear branches desde consola
import frappe

# Branch principal
branch_doc = frappe.get_doc({
    "doctype": "Branch",
    "branch_code": "MATRIZ_01",
    "branch_name": "Casa Matriz",
    "is_primary": 1,
    "pac_provider": "finkok",
    "status": "Active"
})
branch_doc.insert()

# Branch secundario
branch_doc = frappe.get_doc({
    "doctype": "Branch", 
    "branch_code": "SUCURSAL_01",
    "branch_name": "Sucursal Norte",
    "is_primary": 0,
    "pac_provider": "finkok", 
    "status": "Active"
})
branch_doc.insert()
```

## 📋 Primera Factura CFDI

### Crear Customer con Datos Fiscales

1. Ve a **Selling > Customer**
2. Crea un nuevo cliente
3. En la sección **Tax Details**:
   - **Tax ID**: RFC del cliente
   - **Tax Category**: Selecciona apropiada
4. Si requiere addenda, marca **FM Addenda Required**

### Crear Sales Invoice

1. Ve a **Selling > Sales Invoice**  
2. Selecciona el customer creado
3. Agrega items con códigos SAT válidos
4. Verifica que los impuestos se calculen correctamente
5. **Submit** la factura

### Verificar CFDI Generado

Después del submit, verifica:

```python
# Desde consola
import frappe

# Obtener la factura
invoice = frappe.get_doc("Sales Invoice", "SINV-00001")

# Verificar campos CFDI
print(f"CFDI UUID: {invoice.get('cfdi_uuid')}")
print(f"XML generado: {bool(invoice.get('cfdi_xml'))}")
print(f"Estado PAC: {invoice.get('cfdi_status')}")
print(f"Fecha timbrado: {invoice.get('cfdi_stamped_date')}")
```

## 🧪 Ejecutar Tests

### Tests Básicos

```bash
# Tests completos
bench --site tu-sitio.local run-tests --app facturacion_mexico

# Tests específicos por layer
bench --site tu-sitio.local run-tests --app facturacion_mexico --module facturacion_mexico.tests.test_layer1_basic_cfdi_functionality

# Tests de integración
bench --site tu-sitio.local run-tests --app facturacion_mexico --module facturacion_mexico.tests.test_layer3_complete_system_integration_sprint6
```

### Verificar Resultados

Los tests deben mostrar:

```
Ran 46 tests in XXX.XXXs

PASSED (46 tests)
- Layer 1: 15 tests ✅ 
- Layer 2: 15 tests ✅
- Layer 3: 12 tests ✅
- Layer 4: 4 tests ✅
```

## 🔧 Troubleshooting Común

### Error: "No PAC configured"

**Solución:**
```bash
# Verificar configuración PAC
bench --site tu-sitio.local console
```

```python
import frappe
print(frappe.conf.get('pac_provider'))
print(frappe.conf.get('pac_username'))
# No imprimas la password por seguridad
```

### Error: "Invalid SAT Catalog"

**Solución:**
```bash
# Sincronizar catalogos SAT
bench --site tu-sitio.local execute facturacion_mexico.catalogos_sat.sync_all_catalogs
```

### Error: "Certificate validation failed"

**Solución:**
1. Verifica que los archivos .cer y .key sean válidos
2. Confirma que la contraseña sea correcta
3. Verifica que no estén vencidos

```python
# Verificar certificados
from facturacion_mexico.utils.certificates import validate_certificates
result = validate_certificates()
if not result['valid']:
    print(f"Error: {result['error']}")
```

### Error en Addendas

**Síntomas:** Addenda no se genera automáticamente

**Solución:**
1. Verifica que el customer tenga **FM Addenda Required** marcado
2. Confirma que exista configuración de addenda para ese cliente
3. Revisa logs de error

```python
# Debug addenda
from facturacion_mexico.addendas.api import get_addenda_configuration

result = get_addenda_configuration("CUSTOMER-001")
print(f"Config found: {result['success']}")
if result['success']:
    print(f"Auto apply: {result['data']['auto_apply']}")
```

## 📚 Próximos Pasos

Una vez completada la configuración básica:

1. **[Configurar Multi-sucursal](multisucursal.md)** - Si manejas múltiples branches
2. **[Configurar Addendas](addendas.md)** - Para clientes que requieren addendas específicas  
3. **[Troubleshooting Avanzado](troubleshooting.md)** - Solución de problemas complejos

---

!!! success "¡Listo para Producción!"
    Si todos los tests pasan y puedes generar CFDIs correctamente, tu sistema está listo para producción.

!!! tip "Monitoreo"
    Configura alertas para monitorear el estado de tus certificados y credenciales PAC.

!!! warning "Respaldos"
    Siempre mantén respaldos de tus certificados SAT y configuración PAC.