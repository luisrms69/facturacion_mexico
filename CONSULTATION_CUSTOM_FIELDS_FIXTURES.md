# 🤖 CONSULTA TÉCNICA: Custom Fields Fixtures en Frappe Framework

## **CONTEXTO DEL PROBLEMA**

Estoy trabajando en una aplicación Frappe v15 llamada `facturacion_mexico` donde necesito agregar custom fields al DocType `Customer` siguiendo las mejores prácticas de Frappe. **Recientemente completé la migración Issue #31 donde eliminé TODAS las funciones manuales `create_custom_fields()` para usar exclusivamente fixtures**.

## **SITUACIÓN ACTUAL**

### **✅ LO QUE FUNCIONA:**
- Tengo 64 custom fields existentes funcionando correctamente via fixtures
- El archivo `hooks.py` define correctamente la lista de campos en fixtures
- Campos existentes se cargan sin problemas durante `bench install-app`

### **❌ EL PROBLEMA:**
- Agregué nuevos campos Customer al `custom_field.json` manualmente
- Los fixtures se ven correctos (mismo formato que campos funcionando)
- Pero no se aplican/crean en la base de datos
- Error: `Skipping fixture syncing from the file custom_field.json. Reason: DocType None not found`

## **ARCHIVOS RELEVANTES**

### **hooks.py (fragmento):**
```python
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            [
                "name",
                "in",
                [
                    # Customer custom fields (12 campos)
                    "Customer-fm_addenda_info_section",          # ✅ Funciona
                    "Customer-fm_informacion_fiscal_mx_section", # ❌ Nuevo - no se crea
                    "Customer-fm_rfc",                           # ❌ Ya existe pero referencia mal
                    "Customer-fm_regimen_fiscal",                # ❌ Nuevo - no se crea  
                    "Customer-fm_uso_cfdi_default",              # ❌ Nuevo - no se crea
                    # ... más campos
                ]
            ]
        ]
    }
]
```

### **custom_field.json (ejemplo de campo nuevo):**
```json
{
  "allow_in_quick_entry": 0,
  "allow_on_submit": 0,
  "bold": 0,
  "collapsible": 1,
  "doctype": "Custom Field",
  "dt": "Customer",
  "fieldname": "fm_informacion_fiscal_mx_section",
  "fieldtype": "Section Break",
  "label": "Información Fiscal México",
  "insert_after": "more_info",
  "name": "Customer-fm_informacion_fiscal_mx_section",
  // ... más propiedades estándar
}
```

## **COMANDOS EJECUTADOS**

```bash
# 1. Agregué campos al JSON manualmente
# 2. Actualicé hooks.py con nuevos nombres
bench --site facturacion.dev migrate                    # ✅ Sin errores
bench --site facturacion.dev clear-cache               # ✅ Ejecutado
bench --site facturacion.dev install-app facturacion_mexico --force  # ⚠️ "DocType None not found"
bench --site facturacion.dev export-fixtures --app facturacion_mexico # ✅ Ve los campos
```

## **ANÁLISIS TÉCNICO REALIZADO**

1. **Formato JSON:** ✅ Correcto (igual a campos funcionando)
2. **Sintaxis hooks.py:** ✅ Correcto (misma estructura)
3. **Nombres campos:** ✅ Siguen convención `Customer-fm_*`
4. **insert_after:** ✅ Corregido a campos existentes (`more_info`)

## **PREGUNTAS ESPECÍFICAS PARA EXPERTOS**

### **PREGUNTA PRINCIPAL:**
**¿Cuál es el método CORRECTO en Frappe v15 para agregar nuevos custom fields via fixtures sin usar funciones `create_custom_fields()`?**

### **PREGUNTAS DETALLADAS:**

1. **Fixtures vs Manual Creation:**
   - ¿Es correcto agregar campos directamente al `custom_field.json`?
   - ¿O debo crearlos primero via UI/API y luego exportar fixtures?
   - ¿Cuál es el workflow oficial recomendado?

2. **Error "DocType None not found":**
   - ¿Qué causa este error específicamente?
   - ¿Cómo puedo debuggear qué campo está causando el problema?
   - ¿Hay algún campo obligatorio que pueda estar faltando?

3. **Orden de Operaciones:**
   - ¿Debo actualizar `hooks.py` antes o después de agregar al JSON?
   - ¿Requiero `bench migrate` después de cambios en fixtures?
   - ¿Hay algún comando específico para forzar recarga de fixtures?

4. **Mejores Prácticas:**
   - ¿Qué commands son necesarios después de cambiar fixtures?
   - ¿Cómo valido que los fixtures están correctos antes de aplicar?
   - ¿Hay algún linter o validator para fixtures JSON?

## **RESTRICCIONES IMPORTANTES**

- ❌ **NO puedo usar** `create_custom_fields()` (violé Issue #31)
- ❌ **NO puedo usar** patches con funciones manuales
- ✅ **DEBO usar** fixtures exclusivamente (Frappe best practices)
- ✅ **DEBO seguir** el patrón ya establecido en la app

## **RESULTADO ESPERADO**

Instrucciones paso a paso para:
1. Agregar correctamente nuevos custom fields via fixtures
2. Resolver el error "DocType None not found"
3. Hacer que los campos aparezcan en Customer → Tax tab
4. Mantener las mejores prácticas de Frappe v15

## **INFORMACIÓN ADICIONAL**

- **Framework:** Frappe v15
- **App Name:** facturacion_mexico  
- **Site:** facturacion.dev
- **DocType Target:** Customer
- **Objetivo:** Mover campos fiscales a Tax tab y unificar secciones

**¿Cuál es la solución correcta siguiendo las mejores prácticas oficiales de Frappe?**