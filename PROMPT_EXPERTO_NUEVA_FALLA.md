# 🚨 CONSULTA EXPERTO FRAPPE - NUEVA FALLA CI POST-RESOLUCIÓN

## 📋 CONTEXTO COMPLETO

### ✅ PROBLEMA ANTERIOR RESUELTO EXITOSAMENTE
**Problema Original:** `frappe.exceptions.DoesNotExistError: DocType None not found`
**Causa:** Custom Field `Branch.fm_certificate_ids` tipo "Table MultiSelect" con `options = NULL`
**Solución Aplicada:** Procedimiento robusto paso a paso del experto ejecutado perfectamente:

1. ✅ **Custom Field eliminado de BD** - SQL directo confirmó eliminación
2. ✅ **Fixtures actualizados** - `bench export-fixtures` eliminó entrada automáticamente  
3. ✅ **Cache limpio** - `bench migrate` + `bench clear-cache` + `bench restart`
4. ✅ **Detector meta-efectivo:** OK - Sin campos Table/Table MultiSelect problemáticos
5. ✅ **Verificaciones:** Custom Field no existe, Property Setters vacío, fixtures limpio

**CONFIRMACIÓN:** Error original `DocType None not found` completamente eliminado.

---

## ❌ NUEVA FALLA CI POST-RESOLUCIÓN - CURRENCY MISMATCH

### 🔍 ERROR ACTUAL COMPLETO (ACTUALIZADO)
```bash
$ bench --site facturacion.dev run-tests --app facturacion_mexico

frappe.exceptions.ValidationError: Party Account <strong>_Test Payable - _TC</strong> currency (MXN) and document currency (INR) should be same

Stack trace:
  File "/home/runner/frappe-bench/apps/erpnext/erpnext/accounts/doctype/purchase_invoice/purchase_invoice.py", line 262, in validate
  File "/home/runner/frappe-bench/apps/erpnext/erpnext/controllers/accounts_controller.py", line 2363, in validate_party_account_currency
```

### 🔧 MI INTENTO DE SOLUCIÓN BOOTSTRAP
**Implementé sistema bootstrap basado en recomendación anterior:**

```python
# facturacion_mexico/tests/bootstrap.py
def _ensure_test_company():
    if not frappe.db.exists("Company", "_Test Company"):
        company = frappe.get_doc({
            "doctype": "Company",
            "company_name": "_Test Company", 
            "abbr": "_TC",
            "default_currency": "MXN",  # ← CONFIGURÉ MXN PARA MÉXICO
            "country": "Mexico"
        })
        company.insert(ignore_permissions=True)
        frappe.db.commit()
```

**Agregué a hooks.py:**
```python
before_tests = [
    "facturacion_mexico.install.before_tests",
    "facturacion_mexico.setup.testing.load_testing_fixtures", 
    "facturacion_mexico.tests.bootstrap.ensure_test_deps",
]
```

### ⚠️ RESULTADO: NUEVO ERROR CURRENCY MISMATCH
- **Error anterior:** LinkValidationError Item Tax Templates ✅ ELIMINADO
- **Error actual:** Currency mismatch MXN vs INR en Purchase Invoice validation
- **Causa:** _Test Company configurada con MXN pero ERPNext tests esperan INR

### 📊 ANÁLISIS ERROR ACTUAL 

**TIPO:** `ValidationError` - Currency mismatch en accounts validation
**UBICACIÓN:** `erpnext/controllers/accounts_controller.py` línea 2363
**CONTEXTO:** Durante validation Purchase Invoice en make_test_records
**CONFLICTO:** Party Account (_Test Payable - _TC) tiene currency MXN vs document currency INR

**DETALLE ESPECÍFICO:**
- **Account:** _Test Payable - _TC (currency: MXN)
- **Document:** Purchase Invoice test record (currency: INR)
- **Validation:** ERPNext requiere Party Account y Document tengan misma currency

---

## 🔧 INVESTIGACIÓN REALIZADA

### 📁 BOOTSTRAP IMPLEMENTADO EXITOSAMENTE
**Creé `/apps/facturacion_mexico/facturacion_mexico/tests/bootstrap.py`:**
```python
def ensure_test_deps():
    _ensure_test_company()
    _ensure_item_tax_template("_Test Account Excise Duty @ 10 - _TC", 10)
    _ensure_item_tax_template("_Test Account Excise Duty @ 12 - _TC", 12)
```

**✅ ÉXITO:** LinkValidationError Item Tax Templates eliminado completamente

### ⚠️ DILEMA CURRENCY CONFIGURATION
**Configuré MXN para México** pero ERPNext test framework espera INR por defecto.
**Resultado:** Currency mismatch entre accounts (MXN) y documents (INR) en testing.

---

## 🎯 PREGUNTAS ESPECÍFICAS PARA EL EXPERTO

### A) DILEMA CURRENCY CONFIGURATION
**¿Cuál es el enfoque correcto para testing en app México?**

**OPCIÓN 1:** Cambiar _Test Company a INR (compatible con ERPNext)
```python
"default_currency": "INR",
"country": "India"  # Compatible con ERPNext test framework
```

**OPCIÓN 2:** Mantener MXN pero configurar accounts/documents compatibles
```python 
# Crear accounts MXN y forzar documents MXN también
```

**OPCIÓN 3:** Setup dual MXN/INR según contexto de testing

**OPCIÓN 4:** Otro enfoque completamente diferente

### B) BEST PRACTICE TESTING FRAPPE APPS
**¿Es estándar usar currency del país de la app o mantener INR?**
1. Apps internacionales (no-India) ¿usan INR en testing?
2. ¿Hay método estándar para handle currency en custom apps?
3. ¿ERPNext testing framework flexible para otras currencies?

### C) IMPACTO CAMBIO CURRENCY
**Si cambio a INR, ¿afectará functionality real del app?**
1. ¿Testing currency afecta production currency logic?
2. ¿_Test Company es SOLO para testing o se usa en otros contextos?
3. ¿Cambio a INR podría ocultar bugs específicos de MXN?

---

## 📋 INFORMACIÓN TÉCNICA ADICIONAL

### 🖥️ ENTORNO
- **Sitio:** facturacion.dev (único sitio desarrollo)
- **Frappe:** v15
- **ERPNext:** Instalado
- **Comando falla:** `bench --site facturacion.dev run-tests --app facturacion_mexico`

### 📊 EVIDENCIA ERROR CAMBIÓ
- ❌ **Antes:** `DocType None not found` (Custom Field problema)
- ✅ **Después:** `LinkValidationError` (Test records problema)
- **Confirmación:** El problema original está 100% resuelto

### 🔍 STACK TRACE CLAVE
```python
make_test_records_for_doctype() → 
make_test_objects() → 
d.insert(ignore_if_duplicate=True) → 
self._validate_links() → 
LinkValidationError
```

---

## 🙏 SOLICITUD AL EXPERTO

**PREGUNTA DIRECTA:** ¿Cuál es la recomendación del experto?

### 🎯 DECISIÓN REQUERIDA
1. **¿Cambiar _Test Company a INR?** (Solución rápida, compatible ERPNext)
2. **¿Mantener MXN y configurar testing apropiado?** (Más complejo pero específico México)
3. **¿Otro enfoque?**

### 📝 CONTEXTO PARA DECISIÓN
- ✅ Bootstrap approach funciona (LinkValidationError eliminado)
- ✅ Metodología experta funcionando perfectamente
- ❌ Solo currency mismatch bloquea CI
- 🎯 Necesito dirección específica para continuar

**Claude implementó bootstrap exitosamente pero está indeciso sobre currency configuration approach. Necesita recomendación directa del experto para proceder correctamente.**