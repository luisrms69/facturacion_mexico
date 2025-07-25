# Troubleshooting - Solución de Problemas

Guía completa para resolver problemas comunes del sistema de facturación.

## 🚨 Problemas de Timbrado

### Error: "PAC Provider Not Configured"

**Síntomas:**
- Error al hacer submit de Sales Invoice
- Mensaje: "No PAC provider configured"

**Solución:**

1. **Verificar configuración PAC**:
   ```bash
   bench --site tu-sitio.local console
   ```
   
   ```python
   import frappe
   print(f"PAC Provider: {frappe.conf.get('pac_provider')}")
   print(f"PAC Username: {frappe.conf.get('pac_username')}")
   print(f"Test Mode: {frappe.conf.get('pac_test_mode')}")
   ```

2. **Configurar en site_config.json**:
   ```json
   {
     "pac_provider": "finkok",
     "pac_username": "tu_usuario",
     "pac_password": "tu_password",
     "pac_test_mode": 1
   }
   ```

3. **Reiniciar servicios**:
   ```bash
   bench restart
   ```

### Error: "Certificate Validation Failed"

**Síntomas:**
- Timbrado falla con error de certificado
- XML se genera pero no se timbre

**Solución:**

1. **Verificar certificados**:
   ```python
   from facturacion_mexico.utils.certificates import validate_certificates
   
   result = validate_certificates()
   print(f"Válido: {result['valid']}")
   print(f"Error: {result.get('error')}")
   print(f"Expira: {result.get('expires_on')}")
   ```

2. **Re-subir certificados**:
   - Ve a **Setup > Facturación México > Certificados SAT**
   - Sube nuevamente los archivos .cer y .key
   - Ingresa la contraseña correcta

3. **Verificar permisos**:
   ```bash
   # Verificar que los archivos sean legibles
   ls -la sites/tu-sitio.local/private/files/
   chmod 644 sites/tu-sitio.local/private/files/*.cer
   chmod 600 sites/tu-sitio.local/private/files/*.key
   ```

### Error: "Invalid XML Structure"

**Síntomas:**
- XML se genera con errores de estructura
- PAC rechaza el XML por formato inválido

**Solución:**

1. **Validar datos de company**:
   ```python
   company = frappe.get_doc("Company", "Tu Empresa")
   print(f"RFC: {company.tax_id}")
   print(f"Régimen Fiscal: {company.default_tax_regime}")
   print(f"Código Postal: {company.zip_code}")
   ```

2. **Verificar catalogos SAT**:
   ```bash
   bench --site tu-sitio.local execute facturacion_mexico.catalogos_sat.sync_all_catalogs
   ```

3. **Validar XML manualmente**:
   ```python
   from facturacion_mexico.cfdi.xml_validator import validate_cfdi_xml
   
   invoice = frappe.get_doc("Sales Invoice", "SINV-00001")
   result = validate_cfdi_xml(invoice.cfdi_xml)
   
   if not result['valid']:
       for error in result['errors']:
           print(f"Error: {error}")
   ```

## 🏢 Problemas Multi-sucursal

### Branch No Responde

**Síntomas:**
- Timeouts al procesar facturas
- Branch marcado como "Not Available"

**Solución:**

1. **Verificar conectividad**:
   ```python
   from facturacion_mexico.multisucursal.diagnostics import test_branch_connectivity
   
   result = test_branch_connectivity("NORTE_01")
   print(f"Status: {result['status']}")
   print(f"Response Time: {result['response_time']}ms")
   print(f"PAC Available: {result['pac_available']}")
   ```

2. **Revisar credenciales PAC del branch**:
   ```python
   branch = frappe.get_doc("Branch", "NORTE_01")
   
   # Verificar configuración (sin mostrar password)
   print(f"PAC Provider: {branch.pac_provider}")
   print(f"Username configured: {bool(branch.pac_username)}")
   print(f"Status: {branch.status}")
   ```

3. **Forzar health check**:
   ```bash
   bench --site tu-sitio.local execute facturacion_mexico.multisucursal.coordination.force_health_check --args "['NORTE_01']"
   ```

### Failover No Funciona

**Síntomas:**
- Falla un branch pero el sistema no cambia automáticamente
- Errores continúan en lugar de usar backup

**Solución:**

1. **Verificar configuración de failover**:
   ```python
   import frappe
   
   # Verificar configuración global
   failover_enabled = frappe.conf.get('branch_failover_enabled')
   print(f"Failover habilitado: {failover_enabled}")
   
   # Verificar grupos de coordinación
   from facturacion_mexico.multisucursal.coordination import get_coordination_groups
   groups = get_coordination_groups()
   print(f"Grupos configurados: {list(groups.keys())}")
   ```

2. **Revisar logs de coordinación**:
   ```bash
   tail -f logs/frappe.log | grep "multisucursal"
   ```

3. **Configurar backup branches**:
   ```python
   # Configurar backups para un grupo
   group_config = {
       "GRUPO_NORTE": {
           "primary": "MONTERREY_01",
           "backups": ["TIJUANA_01", "CHIHUAHUA_01"],
           "failover_threshold": 3  # errores consecutivos
       }
   }
   
   frappe.db.set_value("Branch Settings", None, "coordination_groups", 
                      json.dumps(group_config))
   ```

## 📄 Problemas de Addendas

### Addenda No Se Genera

**Síntomas:**
- Campo `addenda_xml` permanece vacío
- No aparece addenda en el PDF

**Solución:**

1. **Verificar configuración del cliente**:
   ```python
   customer = frappe.get_doc("Customer", "WALMART-001")
   
   print(f"Addenda Required: {customer.get('fm_addenda_required')}")
   print(f"Addenda Type: {customer.get('addenda_type')}")
   print(f"Auto Apply: {customer.get('addenda_auto_apply')}")
   ```

2. **Verificar tipo de addenda**:
   ```python
   if customer.addenda_type:
       addenda_type = frappe.get_doc("Addenda Type", customer.addenda_type)
       print(f"Template File: {addenda_type.template_file}")
       print(f"Auto Apply: {addenda_type.auto_apply}")
       print(f"Required Fields: {addenda_type.required_fields}")
   ```

3. **Verificar template file**:
   ```bash
   # Verificar que el template existe
   ls -la addendas/templates/walmart_mx.xml
   
   # Verificar permisos
   chmod 644 addendas/templates/*.xml
   ```

4. **Generar manualmente**:
   ```python
   from facturacion_mexico.addendas.generator import generate_addenda_for_invoice
   
   invoice = frappe.get_doc("Sales Invoice", "SINV-00001")
   result = generate_addenda_for_invoice(invoice)
   
   if result['success']:
       print("Addenda generada exitosamente")
   else:
       print(f"Error: {result['error']}")
   ```

### Error de Validación en Addenda

**Síntomas:**
- Addenda se genera pero falla validación
- Errores de formato XML

**Solución:**

1. **Validar XML estructura**:
   ```python
   from facturacion_mexico.addendas.validator import validate_addenda_xml
   import xml.etree.ElementTree as ET
   
   try:
       ET.fromstring(invoice.addenda_xml)
       print("XML bien formado")
   except ET.ParseError as e:
       print(f"Error XML: {e}")
   ```

2. **Verificar campos requeridos**:
   ```python
   from facturacion_mexico.addendas.validator import check_required_fields
   
   invoice = frappe.get_doc("Sales Invoice", "SINV-00001") 
   missing_fields = check_required_fields(invoice, "WALMART_MX")
   
   if missing_fields:
       print(f"Campos faltantes: {missing_fields}")
   ```

3. **Debug del template**:
   ```python
   # Verificar datos disponibles para el template
   from frappe.utils.jinja import get_jenv
   
   jenv = get_jenv()
   template = jenv.get_template("walmart_mx.xml")
   
   # Context de datos
   context = {
       'invoice_number': invoice.name,
       'purchase_order': invoice.po_no,
       'vendor_number': invoice.supplier_invoice,
       # ... otros campos
   }
   
   try:
       rendered = template.render(**context)
       print("Template renderizado exitosamente")
   except Exception as e:
       print(f"Error en template: {e}")
   ```

## 📊 Problemas de Catalogos SAT

### Catalogos Desactualizados

**Síntomas:**
- Códigos SAT no encontrados
- Errores de validación por catalogos obsoletos

**Solución:**

1. **Sincronizar catalogos**:
   ```bash
   # Sincronizar todos los catalogos
   bench --site tu-sitio.local execute facturacion_mexico.catalogos_sat.sync_all_catalogs
   
   # Sincronizar catálogo específico
   bench --site tu-sitio.local execute facturacion_mexico.catalogos_sat.sync_regimen_fiscal
   ```

2. **Verificar última sincronización**:
   ```python
   from frappe.utils import get_datetime
   
   # Verificar regímenes fiscales
   last_sync = frappe.db.get_value("Regimen Fiscal SAT", 
                                  filters={}, 
                                  fieldname="modified", 
                                  order_by="modified desc")
   
   print(f"Última sincronización: {last_sync}")
   
   # Verificar cantidad de registros
   count = frappe.db.count("Regimen Fiscal SAT")
   print(f"Regímenes disponibles: {count}")
   ```

3. **Forzar descarga manual**:
   ```python
   from facturacion_mexico.catalogos_sat.downloader import download_sat_catalog
   
   # Descargar catálogo específico
   result = download_sat_catalog("regimen_fiscal")
   print(f"Descargados: {result['count']} registros")
   ```

### Items Sin Códigos SAT

**Síntomas:**
- Error: "Item code SAT not found"
- Factura no se puede timbrar

**Solución:**

1. **Configurar códigos SAT en items**:
   ```python
   # Buscar items sin código SAT
   items_without_sat = frappe.db.sql("""
       SELECT name, item_name 
       FROM `tabItem` 
       WHERE sat_item_code IS NULL OR sat_item_code = ''
       LIMIT 10
   """, as_dict=True)
   
   for item in items_without_sat:
       print(f"Item sin SAT: {item.name} - {item.item_name}")
   ```

2. **Asignar códigos SAT automáticamente**:
   ```python
   # Script para asignar códigos SAT por descripción
   def auto_assign_sat_codes():
       items = frappe.get_all("Item", 
                             filters={"sat_item_code": ["in", [None, ""]]},
                             fields=["name", "item_name", "description"])
       
       for item in items:
           # Lógica para encontrar código SAT apropiado
           sat_code = find_best_sat_code(item.item_name)
           
           if sat_code:
               frappe.db.set_value("Item", item.name, "sat_item_code", sat_code)
               print(f"Asignado {sat_code} a {item.name}")
   ```

3. **Usar código SAT genérico temporalmente**:
   ```python
   # Asignar código genérico a items problemáticos
   generic_code = "01010101"  # Código genérico SAT
   
   frappe.db.sql("""
       UPDATE `tabItem` 
       SET sat_item_code = %s 
       WHERE sat_item_code IS NULL OR sat_item_code = ''
   """, (generic_code,))
   
   print("Códigos genéricos asignados")
   ```

## 🔧 Problemas de Performance

### Timbrado Lento

**Síntomas:**
- Submit de facturas toma más de 10 segundos
- Timeouts en timbrado

**Solución:**

1. **Monitorear tiempos**:
   ```python
   import time
   from functools import wraps
   
   def time_function(func):
       @wraps(func)
       def wrapper(*args, **kwargs):
           start = time.time()
           result = func(*args, **kwargs)
           end = time.time()
           print(f"{func.__name__} tomó {end - start:.2f} segundos")
           return result
       return wrapper
   
   # Aplicar a función de timbrado
   @time_function
   def timbrar_factura(invoice):
       # Lógica de timbrado
       pass
   ```

2. **Optimizar consultas**:
   ```python
   # Verificar queries lentas
   frappe.db.debug = True
   
   # Procesar factura
   invoice.submit()
   
   # Ver log de queries
   for query in frappe.db.get_query_log():
       if query['time'] > 1.0:  # Queries > 1 segundo
           print(f"Query lenta: {query['query'][:100]}... ({query['time']:.2f}s)")
   ```

3. **Configurar cache**:
   ```python
   # Cachear catalogos SAT frecuentemente usados
   @frappe.cache.memoize()
   def get_sat_regimen_fiscal():
       return frappe.get_all("Regimen Fiscal SAT", 
                           fields=["codigo", "descripcion"])
   
   # Usar cache en lugar de query directa
   regimenes = get_sat_regimen_fiscal()
   ```

### Memoria Alta

**Síntomas:**
- Proceso Frappe consume mucha RAM
- Server se ralentiza con el tiempo

**Solución:**

1. **Monitorear uso de memoria**:
   ```python
   import psutil
   import os
   
   process = psutil.Process(os.getpid())
   memory_info = process.memory_info()
   
   print(f"RSS: {memory_info.rss / 1024 / 1024:.2f} MB")
   print(f"VMS: {memory_info.vms / 1024 / 1024:.2f} MB")
   ```

2. **Limpiar cache periódicamente**:
   ```bash
   # Limpiar cache manualmente
   bench --site tu-sitio.local clear-cache
   
   # Configurar limpieza automática
   bench --site tu-sitio.local set-config clear_cache_interval 3600  # cada hora
   ```

3. **Optimizar consultas masivas**:
   ```python
   # En lugar de cargar todos los registros
   # invoices = frappe.get_all("Sales Invoice")  # ❌ Malo
   
   # Usar paginación
   def process_invoices_batch():
       start = 0
       page_size = 100
       
       while True:
           invoices = frappe.get_all("Sales Invoice", 
                                   start=start, 
                                   page_length=page_size)
           
           if not invoices:
               break
               
           for invoice in invoices:
               process_invoice(invoice)
               
           start += page_size
   ```

## 🔍 Herramientas de Debugging

### Logs Detallados

```python
# Habilitar logging detallado
import logging

# Para módulo específico
logging.getLogger('facturacion_mexico').setLevel(logging.DEBUG)

# Para logging global
frappe.log_error("Debug info", "Debug Category")
```

### Console Commands

```bash
# Información del sistema
bench --site tu-sitio.local console
```

```python
# Commands útiles en consola
import frappe

# Ver configuración actual
print(frappe.conf)

# Ver apps instaladas
print(frappe.get_installed_apps())

# Ver site config
print(frappe.get_site_config())

# Información de la base de datos
print(f"DB: {frappe.db.db_name}")
print(f"Usuario: {frappe.session.user}")
```

### Health Check Script

```python
def system_health_check():
    """Script completo de health check."""
    
    checks = {
        "PAC Configuration": check_pac_config(),
        "Certificates": check_certificates(),
        "SAT Catalogs": check_sat_catalogs(),
        "Branches": check_branches(),
        "Templates": check_templates(),
        "Performance": check_performance()
    }
    
    print("\n=== HEALTH CHECK RESULTS ===")
    for check_name, result in checks.items():
        status = "✅ PASS" if result['status'] else "❌ FAIL"
        print(f"{check_name}: {status}")
        if not result['status']:
            print(f"  Error: {result['error']}")
    
    return all(check['status'] for check in checks.values())

# Ejecutar health check
health_ok = system_health_check()
print(f"\nSistema saludable: {'✅ Sí' if health_ok else '❌ No'}")
```

---

!!! tip "Logging Proactivo"
    Habilita logging detallado durante desarrollo para detectar problemas temprano.

!!! warning "Performance"
    Monitorea regularmente el performance del sistema, especialmente en timbrado masivo.

!!! info "Support"
    Si ninguna solución funciona, revisa los logs de sistema y contacta soporte técnico con información específica del error.