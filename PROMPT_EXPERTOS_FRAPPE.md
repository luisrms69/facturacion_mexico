# 🚨 CONSULTA EXPERTOS FRAPPE - Test Runner Error "DocType None not found"

## **CONTEXTO DEL PROBLEMA**

Tengo un error crítico en el test runner de Frappe que aparece consistentemente en CI/CD pero que no puedo identificar después de investigación exhaustiva. El error comenzó después de eliminar un DocType legacy ("Fiscal Event MX") de una app custom llamada `facturacion_mexico`.

## **ERROR ESPECÍFICO**
```
frappe.exceptions.DoesNotExistError: DocType None not found

Traceback:
File "/home/runner/frappe-bench/apps/frappe/frappe/test_runner.py", line 365, in get_dependencies
    link_fields.extend(frappe.get_meta(df.options).get_link_fields())
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^
# df.options es None → frappe.get_meta(None) → Error
```

## **ARQUITECTURA Y CONTEXTO**

### **App Custom Details:**
- **App Name:** `facturacion_mexico`
- **Module:** `Facturacion Mexico` 
- **Frappe Version:** v15
- **Environment:** Development site (facturacion.dev)

### **DocType Eliminado (Root Cause Sospechoso):**
- **Name:** `Fiscal Event MX`
- **Module:** `Facturacion Fiscal`
- **Eliminated:** Commit b0746a0 - Archivos + 176 registros DB + registro tabDocType
- **Usage:** Era usado para event sourcing, tenía Link fields a otros DocTypes

### **Timeline Error:**
- ✅ **Commit 678e331** - Tests funcionaban perfectamente
- ❌ **Commit 7251e8e** - Creación 3 DocTypes nuevos (Control Panel Admin)
- ❌ **Commit b0746a0** - Eliminación FiscalEventMX - ERROR PERSISTE
- ❌ **Commit 6152ff3** - Correcciones adicionales - ERROR PERSISTE

## **SÍNTOMAS ESPECÍFICOS**

### **Comportamiento Error:**
```bash
# ✅ PASA SIN PROBLEMA
bench --site facturacion.dev run-tests --module facturacion_mexico
RESULTADO: NO TESTS RAN (0 tests)

# ❌ FALLA CON ERROR
bench --site facturacion.dev run-tests --app facturacion_mexico  
RESULTADO: DocType None not found en test_runner.py:365
```

### **Stack Trace Completo:**
El error ocurre en la función `get_dependencies()` del test runner cuando intenta procesar dependencias de DocTypes para crear test records. Específicamente falla cuando encuentra un Table field cuyo `df.options` es `None` y hace `frappe.get_meta(None)`.

## **INVESTIGACIÓN EXHAUSTIVA REALIZADA**

### **1. Verificaciones SQL (Todos Negativos):**
```sql
-- Buscar Table fields con options problemáticos
SELECT parent, fieldname, options FROM tabDocField 
WHERE fieldtype = 'Table' AND parent IN (DocTypes del módulo)
RESULTADO: 0 registros

-- Buscar Link fields con options NULL/empty  
SELECT parent, fieldname, options FROM tabDocField 
WHERE fieldtype = 'Link' AND (options IS NULL OR options = '')
RESULTADO: 0 registros

-- Verificar Custom Fields problemáticos
SELECT dt, fieldname, options FROM tabCustom Field
WHERE module = 'Facturacion Mexico' AND fieldtype IN ('Table', 'Link')
RESULTADO: Solo Link fields válidos
```

### **2. DocTypes del Módulo (Todos Verificados):**
- `Control Panel Settings` - Sin Table fields
- `System Health Monitor` - Sin Table fields  
- `Recovery Operations` - Sin Table fields
- `Fiscal Recovery Task` - Link fields válidos
- `Factura Fiscal Mexico` - Sin Table fields problemáticos
- Plus ~10 DocTypes más - Ninguno con Table fields

### **3. Limpieza Realizada:**
- ✅ Eliminado directorio completo `fiscal_event_mx/`
- ✅ Eliminado registro `DELETE FROM tabDocType WHERE name = 'Fiscal Event MX'`
- ✅ Eliminado registros `DELETE FROM tabFiscal Event MX` (176 registros)
- ✅ Limpiado imports en 4 hooks handlers
- ✅ Verificado 0 Custom Fields o DocFields referencian DocType eliminado

## **PREGUNTAS ESPECÍFICAS PARA EXPERTOS**

### **1. Identificación Test Culpable:**
**¿Cómo puedo identificar exactamente qué test o DocType específico está causando que `get_dependencies()` llame `frappe.get_meta(None)`?**

¿Existe algún flag de debug o logging que me permita ver:
- Qué DocType está siendo procesado cuando falla
- Qué Table field específico tiene `df.options = None`
- Si el problema viene de fixtures, test records, o meta cache

### **2. Tests Legacy vs Nuevos:**
Los tests en esta app son **históricos/legacy** - fueron creados cuando se desarrolló el sistema original con el DocType "Fiscal Event MX". No son tests nuevos creados recientemente.

**¿Es posible que exista algún test legacy que:**
- Haga referencia hardcodeada al DocType eliminado
- Tenga fixtures que incluyan el DocType eliminado  
- Esté definido en algún archivo `.txt` o `test_records.json`
- Cache corrupto de meta information del DocType eliminado

### **3. Diferencia Module vs App Testing:**
**¿Por qué `--module facturacion_mexico` pasa pero `--app facturacion_mexico` falla?**

¿La diferencia está en:
- Scope de DocTypes procesados (solo del module vs todos de la app)
- Orden de procesamiento de dependencias
- Test discovery methodology
- Cache/fixtures loading differences

### **4. Table Fields Investigation:**
**¿Dónde más podría estar el Table field problemático que no estoy viendo?**

¿Debería revisar:
- DocTypes en otros modules de la misma app
- DocTypes que heredan/extend DocTypes del módulo
- Child DocTypes o Table DocTypes específicos
- Property Setters que modifiquen field options
- Fixtures que sobrescriban field definitions

### **5. Debugging Strategies:**
**¿Cuál es la mejor estrategia para hacer debug del test runner?**

- Monkey patch `frappe.get_meta()` para capturar cuándo recibe None
- Modificar temporalmente `get_dependencies()` con logging detallado
- Usar pdb/debugger en test runner execution
- Revisar frappe logs durante test execution

## **ARCHIVOS ESPECÍFICOS PARA REVISAR**

### **Estructura App:**
```
facturacion_mexico/
├── facturacion_mexico/
│   ├── hooks.py                    # Doc events, scheduler
│   ├── fixtures/                   # Fixtures potencialmente problemáticos
│   ├── facturacion_fiscal/         # Module principal
│   │   ├── doctype/               # DocTypes del módulo
│   │   └── hooks_handlers/        # Hooks donde se eliminó FiscalEventMX
│   └── tests/                     # Test files
└── tests/                         # Más test files
```

### **Test Files Existentes:**
```bash
find . -name "test_*.py"
./tests/test_layer4_performance.py
./tests/test_layer1_basic_infrastructure.py  
./facturacion_mexico/tests/test_layer2_cross_module_validation.py
./facturacion_mexico/tests/test_layer1_double_facturation_prevention.py
# Plus varios más...
```

## **INFORMACIÓN ADICIONAL**

### **Environment Details:**
- **Frappe Framework:** v15  
- **Site Type:** Single development site
- **Database:** MariaDB
- **OS:** Linux (GitHub Actions environment)

### **Recent Changes:**
- Sistema en proceso de migración a nueva arquitectura resiliente
- Eliminación de DocType legacy como parte de cleanup P6.1
- Creación de nuevos DocTypes para Control Panel Admin
- No hay cambios en core Frappe framework

### **Impact:**
- CI/CD completamente bloqueado
- Desarrollo local funcional (solo testing afectado)
- Sistema en producción no afectado

---

**¿Podrían ayudarme a identificar la estrategia correcta para encontrar el test o DocType específico que está causando `frappe.get_meta(None)` en el test runner?**

**¿Existe alguna herramienta, comando, o técnica específica de Frappe que use para debugging este tipo de problemas en el test runner?**

**¿Es común que la eliminación de DocTypes cause este tipo de problemas cached/legacy en tests, y cuál es la estrategia estándar para limpiarlos?**

Agradecería enormemente cualquier orientación o estrategia específica para resolver este problema.