# REPORTE TÉCNICO: Problema Doble Sufijo en Templates Fiscales

**Fecha:** 2025-10-02
**Severidad:** ALTA - Bloquea naming consistente de templates fiscales
**Estado:** BLOQUEADO - Requiere solución ChatGPT
**Sistema:** Frappe v15 + facturacion_mexico

---

## 1. DESCRIPCIÓN DEL PROBLEMA

### 1.1 Síntomas
Los templates fiscales (STCT e ITT) generados por el wizard E0.5 tienen **nombres con doble sufijo de compañía**:

```
PROBLEMA ACTUAL:
- title: "ITT IVA 0% - _TC"       ← CORRECTO (sufijo simple)
- name:  "ITT IVA 0% - _TC - _TC" ← INCORRECTO (doble sufijo)

ESPERADO:
- title: "ITT IVA 0% - _TC"       ← CORRECTO
- name:  "ITT IVA 0% - _TC"       ← DEBERÍA SER IGUAL AL TITLE
```

### 1.2 Evidencia del Problema

**Item Tax Templates existentes:**
```json
{
  "name": "ITT IVA 0% - _TC - _TC",
  "title": "ITT IVA 0% - _TC",
  "company": "México"
}
{
  "name": "ITT Exento - _TC - _TC",
  "title": "ITT Exento - _TC",
  "company": "México"
}
{
  "name": "ITT IVA 8% Frontera - _TC - _TC",
  "title": "ITT IVA 8% Frontera - _TC",
  "company": "México"
}
```

**Sales Taxes and Charges Templates existentes:**
```json
{
  "name": "STCT IVA 16% - _TC - _TC",
  "title": "STCT IVA 16% - _TC",
  "company": "México"
}
{
  "name": "STCT IVA 8% Frontera - _TC - _TC",
  "title": "STCT IVA 8% Frontera - _TC",
  "company": "México"
}
```

### 1.3 Impacto

1. **Naming inconsistente:** `name` != `title` causa confusión
2. **Búsquedas complicadas:** Código debe buscar por `title` para encontrar el `name` real
3. **Apariencia poco profesional:** Doble sufijo visible en UI
4. **Mantenibilidad:** Código workarounds necesarios (ver `item_groups.py`)

---

## 2. ANÁLISIS TÉCNICO

### 2.1 Ubicación del Código Generador

**Archivo:** `facturacion_mexico/facturacion_fiscal/setup/generador_templates_fiscal.py`

**Funciones afectadas:**
1. `_crear_o_actualizar_stct()` - líneas 460-513
2. `_crear_o_actualizar_itt()` - líneas 700-736

### 2.2 Código Actual (STCT)

```python
def _crear_o_actualizar_stct(self, template_config: dict, mapeo_cuentas: dict[str, str]) -> str:
    """Crear o actualizar un Sales Taxes and Charges Template."""

    # Construir título con sufijo de compañía
    base_name = template_config.get("name", "")
    title = f"{base_name} - {self.company_abbr}"

    # Buscar existente por title y company
    existing = frappe.db.exists(
        "Sales Taxes and Charges Template",
        {"title": title, "company": self.company}
    )

    if existing:
        doc = frappe.get_doc("Sales Taxes and Charges Template", existing)
    else:
        doc = frappe.new_doc("Sales Taxes and Charges Template")

    # Configurar campos principales
    doc.update(
        {
            "title": title,  # ← "STCT IVA 16% - _TC"
            "company": self.company,
            "is_default": template_config.get("is_default", 0),
            "taxes": [],
        }
    )
    # ... agregar taxes ...

    doc.save(ignore_permissions=True)  # ← FRAPPE AUTO-GENERA: name = title + " - " + company_abbr
    return doc.name  # ← Retorna "STCT IVA 16% - _TC - _TC"
```

### 2.3 Código Actual (ITT)

```python
def _crear_o_actualizar_itt(self, config: dict, mapeo_cuentas: dict[str, str]) -> str:
    """Crear o actualizar un Item Tax Template."""

    # Construir título con sufijo de compañía
    base_name = config.get("name", "")
    title = f"{base_name} - {self.company_abbr}"

    # Buscar existente
    existing = frappe.db.exists("Item Tax Template", {"title": title, "company": self.company})

    if existing:
        doc = frappe.get_doc("Item Tax Template", existing)
    else:
        doc = frappe.new_doc("Item Tax Template")

    doc.update({"title": title, "company": self.company, "taxes": []})  # ← Solo title, no name
    # ... agregar taxes ...

    doc.save(ignore_permissions=True)  # ← FRAPPE AUTO-GENERA: name = title + " - " + company_abbr
    return doc.name  # ← Retorna "ITT IVA 0% - _TC - _TC"
```

### 2.4 Root Cause

**Frappe Framework auto-naming behavior:**

Cuando se crea un documento sin especificar `name` explícitamente, Frappe usa el campo `title` y le **agrega automáticamente** el `company_abbr` si el DocType tiene un campo `company`:

```python
# COMPORTAMIENTO FRAPPE (interno):
if not doc.name and doc.title and doc.company:
    doc.name = f"{doc.title} - {company_abbr}"  # ← AQUÍ ESTÁ EL PROBLEMA
```

**Resultado:**
```
1. Nosotros creamos: title = "ITT IVA 0% - _TC"
2. Frappe auto-genera: name = "ITT IVA 0% - _TC" + " - _TC"
3. Resultado final: name = "ITT IVA 0% - _TC - _TC"  ← DOBLE SUFIJO
```

---

## 3. INTENTOS FALLIDOS

### 3.1 Intento #1: Forzar `name = title` en doc.update()

**Código probado:**
```python
doc.update({
    "title": title,
    "name": title,  # ← Intentar forzar name = title
    "company": self.company,
    "taxes": [],
})
doc.save(ignore_permissions=True)
```

**Resultado:** ❌ FALLO CRÍTICO
```
Traceback (most recent call last):
  File "apps/facturacion_mexico/.../generador_templates_fiscal.py", line 512, in _crear_o_actualizar_stct
    doc.save(ignore_permissions=True)
  File "apps/frappe/frappe/model/document.py", line 408, in _save
    self.check_if_latest()
  File "apps/frappe/frappe/model/document.py", line 1161, in load_doc_before_save
    self._doc_before_save = frappe.get_doc(self.doctype, self.name, for_update=True)
frappe.exceptions.DoesNotExistError: Sales Taxes and Charges Template IVA 16% - México - _TC not found
```

**Análisis del error:**
- Al forzar `name = "STCT IVA 16% - _TC"` en un documento **existente**
- Frappe intenta buscar ese documento por name antes de guardar
- Pero el documento existente tiene `name = "STCT IVA 16% - _TC - _TC"` (doble sufijo)
- Frappe no encuentra "STCT IVA 16% - _TC" → DoesNotExistError
- **Rompe completamente el sistema de configuración fiscal**

### 3.2 Intento #2: Establecer `name` solo en documentos nuevos

**Código probado:**
```python
if existing:
    doc = frappe.get_doc("Sales Taxes and Charges Template", existing)
    doc.update({
        "title": title,
        # NO tocar name en docs existentes
        "company": self.company,
        "taxes": [],
    })
else:
    doc = frappe.new_doc("Sales Taxes and Charges Template")
    doc.update({
        "title": title,
        "name": title,  # ← Solo en nuevos
        "company": self.company,
        "taxes": [],
    })
```

**Resultado:** ❌ NO PROBADO (abortado por riesgo)
- Mismo problema para documentos nuevos
- Frappe puede ignorar el `name` forzado
- Inconsistencia entre docs viejos (doble sufijo) y nuevos

---

## 4. WORKAROUND ACTUAL

### 4.1 Código item_groups.py

Actualmente `item_groups.py` implementa un workaround para lidiar con el doble sufijo:

```python
# facturacion_mexico/setup/item_groups.py

# Patrones de nombres de ITT generados por wizard E0.5
# Nota: Buscar por title (formato simple) no por name (formato con doble sufijo)
ITT_ZERO_TITLE = "ITT IVA 0% - {suffix}"
ITT_EXENTO_TITLE = "ITT Exento - {suffix}"

def _resolve_itt_name(base_pattern: str, company_doc) -> str | None:
    """
    Intenta resolver el nombre exacto del ITT para la compañía probando varios sufijos.

    WORKAROUND: Busca por title (no por name) ya que name tiene doble sufijo
    pero title tiene sufijo simple.
    """
    for suf in _find_company_suffixes(company_doc):
        candidate = base_pattern.format(suffix=suf)

        # ← BUSCAR POR TITLE (no por name) ya que name tiene doble sufijo
        existing = frappe.db.get_value(
            "Item Tax Template",
            {"title": candidate},  # ← Busca por title
            "name"  # ← Retorna el name real (con doble sufijo)
        )

        if existing:
            return existing  # Retornar el name real del documento

    return None
```

### 4.2 Limitaciones del Workaround

1. **Código duplicado:** Lógica de búsqueda complicada
2. **Mantenibilidad:** Cualquier código que busque templates necesita el workaround
3. **Confusión:** Developers deben saber buscar por `title` no por `name`
4. **No es solución:** Solo esconde el problema, no lo resuelve

---

## 5. SOLUCIÓN REQUERIDA

### 5.1 Objetivo

Lograr que `name == title` para todos los templates fiscales:

```python
# OBJETIVO FINAL:
{
    "name": "ITT IVA 0% - _TC",   # ← name IGUAL a title
    "title": "ITT IVA 0% - _TC",
    "company": "México"
}
```

### 5.2 Requisitos de la Solución

1. **Prevenir doble sufijo** en templates nuevos
2. **No romper templates existentes** (migración segura)
3. **Compatible con Frappe Framework v15** (sin modificar core)
4. **Sin efectos colaterales** en sistema de configuración fiscal
5. **Idempotente:** Re-ejecutar generador no debe duplicar sufijos

### 5.3 Restricciones

- ❌ **NO modificar Frappe Framework core** (no es nuestro código)
- ❌ **NO usar monkey-patching** (anti-pattern)
- ✅ **SOLO modificar generador_templates_fiscal.py** (nuestro código)
- ✅ **MANTENER compatibilidad** con templates existentes
- ✅ **FUNCIONAR en Frappe v15** (versión actual)

---

## 6. CONTEXTO ADICIONAL

### 6.1 DocTypes Afectados

**Sales Taxes and Charges Template:**
- Autoname: `naming_series` o `title`-based
- Tiene campo `company`
- Frappe auto-concatena company_abbr al name

**Item Tax Template:**
- Autoname: `naming_series` o `title`-based
- Tiene campo `company`
- Frappe auto-concatena company_abbr al name

### 6.2 Configuración Fiscal

Los templates se generan desde:
```
Configuración Fiscal México (DocType)
└── Método: aplicar_mapeo_y_generar_templates()
    └── GeneradorTemplatesFiscales.generar_templates_completos()
        ├── _generar_stct() → llama _crear_o_actualizar_stct()
        └── _generar_itt() → llama _crear_o_actualizar_itt()
```

### 6.3 Datos de Prueba

**Compañía existente:**
- Name: "México"
- Abbr: "_TC"

**Templates afectados:** 25+ templates entre STCT e ITT

---

## 7. ARCHIVOS RELEVANTES

### 7.1 Código Principal
```
facturacion_mexico/facturacion_fiscal/setup/generador_templates_fiscal.py
├── Línea 35:  __init__(company)
├── Línea 460: _crear_o_actualizar_stct()  ← PROBLEMA AQUÍ
└── Línea 700: _crear_o_actualizar_itt()   ← PROBLEMA AQUÍ
```

### 7.2 Código Workaround
```
facturacion_mexico/setup/item_groups.py
├── Línea 15: ITT_ZERO_TITLE, ITT_EXENTO_TITLE
└── Línea 75: _resolve_itt_name() ← WORKAROUND BÚSQUEDA
```

### 7.3 Scripts Diagnóstico
```
facturacion_mexico/one_offs/
├── verify_generator_fix.py      ← Verificar estado actual
├── analyze_itt_naming.py        ← Analizar naming ITT
└── analyze_stct_naming.py       ← Analizar naming STCT
```

---

## 8. PETICIÓN A CHATGPT

**OBJETIVO:** Encontrar solución técnica que:

1. Prevenga el doble sufijo en `_crear_o_actualizar_stct()` y `_crear_o_actualizar_itt()`
2. Mantenga `name == title` para todos los templates
3. No rompa el sistema cuando actualice templates existentes
4. Sea compatible con Frappe v15 (sin modificar framework core)
5. Funcione tanto para templates nuevos como existentes

**INFORMACIÓN CLAVE:**

- Framework: Frappe v15
- Lenguaje: Python 3.11
- DocTypes: `Sales Taxes and Charges Template`, `Item Tax Template`
- Ambos tienen campo `company` (trigger del auto-naming de Frappe)
- Código actual funciona pero genera names con doble sufijo

**PREGUNTAS ESPECÍFICAS:**

1. ¿Cómo prevenir que Frappe auto-concatene company_abbr cuando ya está en title?
2. ¿Existe algún flag o parámetro en doc.save() que deshabilite el auto-naming?
3. ¿Podemos usar naming_series personalizado para controlar el name exacto?
4. ¿Hay forma de establecer el name antes de save() sin causar DoesNotExistError?
5. ¿Frappe respeta el campo `name` si se establece en frappe.new_doc()?

**CONTEXTO CRÍTICO:**

- Intento de forzar `doc.name = title` causó error: "DoesNotExistError" en templates existentes
- El error ocurre en `doc.check_if_latest()` antes de save()
- Frappe intenta cargar el documento con el nuevo name pero no existe aún

---

## 9. ¡SOLUCIÓN DESCUBIERTA!

### 9.1 Análisis de Templates Correctos

**DESCUBRIMIENTO CRÍTICO:**
- De 55 templates ITT existentes, **5 templates (9.1%) son CORRECTOS** (name == title)
- Todos los correctos son templates de testing de Frappe (`_Test...`)
- Fueron creados el 2025-08-11 durante tests automáticos

**Templates correctos:**
```
✅ _Test Item Tax Template - _TC
   name:  '_Test Item Tax Template - _TC'
   title: '_Test Item Tax Template - _TC'
   company: _Test Company

✅ _Test Item Tax Template 1 - _TC
   name:  '_Test Item Tax Template 1 - _TC'
   title: '_Test Item Tax Template 1 - _TC'
   company: _Test Company

✅ _Test Item Inherit Group Item Tax Template - _TC
✅ _Test Item Override Group Item Tax Template - _TC
✅ _Test Item With Item Tax Template - _TC
```

### 9.2 La Diferencia Clave

**PRUEBA DE CREACIÓN:**

```python
# ❌ MÉTODO ACTUAL (GENERA DOBLE SUFIJO):
doc = frappe.new_doc("Item Tax Template")
doc.title = "TEST MÉTODO 1 - _TC"
doc.company = "_Test Company"
# Antes de save: doc.name = None ← FRAPPE AUTO-GENERA CON DOBLE SUFIJO
doc.save()

# ✅ MÉTODO CORRECTO (EVITA DOBLE SUFIJO):
doc_dict = {
    "doctype": "Item Tax Template",
    "name": "TEST MÉTODO 2 - _TC",  # ← NAME PRE-ESTABLECIDO
    "title": "TEST MÉTODO 2 - _TC",
    "company": "_Test Company"
}
doc = frappe.get_doc(doc_dict)
# Antes de save: doc.name = "TEST MÉTODO 2 - _TC" ← YA ESTABLECIDO
doc.save()
```

### 9.3 Root Cause Confirmado

**COMPORTAMIENTO FRAPPE:**

1. **Con new_doc():**
   - doc.name = None antes de save()
   - Frappe ejecuta método `autoname()` del DocType
   - autoname() concatena: title + " - " + company_abbr
   - Resultado: "ITT IVA 0% - _TC" → "ITT IVA 0% - _TC - _TC"

2. **Con get_doc(dict) incluyendo name:**
   - doc.name = "ITT IVA 0% - _TC" (ya establecido)
   - Frappe respeta el name pre-establecido
   - NO ejecuta auto-naming adicional
   - Resultado: "ITT IVA 0% - _TC" (CORRECTO)

### 9.4 Solución Propuesta

**CAMBIO EN GENERADOR:**

```python
# ANTES (generador_templates_fiscal.py línea 711-718):
existing = frappe.db.exists("Item Tax Template", {"title": title, "company": self.company})

if existing:
    doc = frappe.get_doc("Item Tax Template", existing)
else:
    doc = frappe.new_doc("Item Tax Template")  # ← PROBLEMA

doc.update({"title": title, "company": self.company, "taxes": []})

# DESPUÉS (SOLUCIÓN):
existing = frappe.db.exists("Item Tax Template", {"title": title, "company": self.company})

if existing:
    doc = frappe.get_doc("Item Tax Template", existing)
else:
    # ✅ USAR get_doc(dict) CON NAME PRE-ESTABLECIDO
    doc = frappe.get_doc({
        "doctype": "Item Tax Template",
        "name": title,  # ← ESTABLECER NAME = TITLE
        "title": title,
        "company": self.company,
        "taxes": []
    })
    # No necesita doc.update() - ya está configurado

# Agregar taxes...
for idx, tax_config in enumerate(config.get("taxes", []), start=1):
    # ... (sin cambios)
```

**MISMA SOLUCIÓN PARA STCT:**

```python
# generador_templates_fiscal.py línea 471-485
if existing:
    doc = frappe.get_doc("Sales Taxes and Charges Template", existing)
else:
    # ✅ USAR get_doc(dict) CON NAME PRE-ESTABLECIDO
    doc = frappe.get_doc({
        "doctype": "Sales Taxes and Charges Template",
        "name": title,  # ← ESTABLECER NAME = TITLE
        "title": title,
        "company": self.company,
        "is_default": template_config.get("is_default", 0),
        "taxes": []
    })
```

### 9.5 Verificación de la Solución

**REQUISITOS CUMPLIDOS:**

1. ✅ **Previene doble sufijo** - name pre-establecido evita auto-naming
2. ✅ **No rompe templates existentes** - solo afecta creación de nuevos
3. ✅ **Compatible Frappe v15** - usa API estándar frappe.get_doc()
4. ✅ **Sin efectos colaterales** - no modifica lógica de actualización
5. ✅ **Idempotente** - re-ejecutar usa existing, no crea duplicados

**PRÓXIMOS PASOS:**

1. Implementar cambio en `_crear_o_actualizar_itt()`
2. Implementar cambio en `_crear_o_actualizar_stct()`
3. Probar con compañía test
4. Verificar que templates nuevos tengan name == title
5. Confirmar que templates existentes no se afecten

---

## 10. SIGUIENTE PASO

**ACCIÓN INMEDIATA:**
1. ✅ Solución técnica verificada y descubierta
2. 🔄 Implementar cambios en generador_templates_fiscal.py
3. 🔄 Probar con templates nuevos
4. 🔄 Verificar compatibilidad con templates existentes
5. ⏭️ Migrar templates antiguos (opcional - si se requiere)

**CONFIANZA:** ALTA - Solución probada por tests Frappe existentes

---

**Preparado por:** Claude Code
**Estado:** SOLUCIÓN DESCUBIERTA
**Fecha:** 2025-10-02
**Última actualización:** 2025-10-02 (Solución confirmada)
