# REPORTE: Arquitectura para Reglas de Cálculo Fiscal

**Fecha:** 2025-10-25
**Contexto:** FASE 3 - Función Rectora Reglas Fiscales
**Problema:** Determinar dónde almacenar reglas de cálculo (regla_base, regla_calculo, cascada, etc.)

---

## 📋 CONTEXTO DEL PROBLEMA

### Situación Actual

**Cambios unstaged:**
- Se agregaron 7 campos nuevos a `Mapeo Cuenta Fiscal Mexico` (child table)
- Campos: regla_base, regla_calculo, cascada, alcance, habilitada, fundamento_legal, notas_calculo

**Problema arquitectónico identificado:**

`Mapeo Cuenta Fiscal Mexico` es una **child table** de `Configuracion Fiscal Mexico`:

```
Configuracion Fiscal Mexico (1 doc por Company)
└── mapeo_cuentas (Table field)
    └── Mapeo Cuenta Fiscal Mexico (child table, istable: 1)
        └── Cada fila: rol_fiscal → cuenta_impuesto
```

**Problema de duplicación:**
- Las reglas de cálculo son **por rol_fiscal** (IVA Nacional, IEPS Tabaco, etc.)
- Las cuentas contables son solo el **destino contable** (no afectan cálculo)
- Si usuario tiene 3 cuentas IVA Nacional → configuraría la misma regla 3 veces
- Violación DRY (Don't Repeat Yourself)

### Requisitos del Usuario

1. **Usuario NO configura** - Desarrolladores configuramos en el app
2. **No repetición** - Cada regla una sola vez (18 roles fiscales = 18 reglas)
3. **Deployment automático** - Fixtures/constantes que migran a producción
4. **Zero-config** - Nueva instalación funciona sin configuración manual (RG-009)

---

## 🏗️ PATRONES ARQUITECTÓNICOS EXISTENTES

### Patrón A: Tablas Maestras Python (setup/ o utils/)

**Ejemplo existente:** `facturacion_mexico/setup/item_groups.py`

```python
# TABLA MAESTRA ÚNICA - FUENTE DE VERDAD
TABLA_MAESTRA_GRUPOS_FISCALES = [
    ("Item Group Name", "ITT Pattern", "Categoría Fiscal", "Tipo"),
    ("Artículos IEPS Alcohol", "ITT IEPS Alcohol - {suffix}", "Alcohol", "IEPS"),
    # ... más filas
]

# Constantes derivadas (auto-generadas)
ITEM_GROUP_ITT_MAP = {row[0]: row[1] for row in TABLA_MAESTRA_GRUPOS_FISCALES}
ITEM_GROUP_CATEGORIA = {row[0]: row[2] for row in TABLA_MAESTRA_GRUPOS_FISCALES}
CATEGORIAS_IEPS = {row[2] for row in TABLA_MAESTRA_GRUPOS_FISCALES if row[3] == "IEPS"}
```

**Ejemplo existente:** `facturacion_mexico/utils/roles_fiscales.py`

```python
# Tabla maestra: (constante, rol_fiscal_exacto, categoria, descripcion)
TABLA_MAESTRA_ROLES_FISCALES = [
    ("IVA_NAC", "IVA por Pagar (Nacional)", "IVA", "IVA Nacional"),
    ("IVA_FRO", "IVA por Pagar (Frontera)", "IVA", "IVA Frontera"),
    # ... 18 roles total
]

# Auto-generar constantes ROL_* desde tabla maestra
for const_name, rol_exacto, _, _ in TABLA_MAESTRA_ROLES_FISCALES:
    globals()[f"ROL_{const_name}"] = rol_exacto
```

**Características:**
- ✅ Single source of truth
- ✅ Versionado en git
- ✅ Performance (no queries DB en runtime)
- ✅ Inmutable (no modificable por usuario - es LO QUE QUEREMOS)
- ✅ Zero-config deployment (código se despliega automáticamente)
- ❌ Cambios requieren actualización app + migrate

### Patrón B: Fixtures JSON (fixtures/)

**Ejemplo existente:** `facturacion_mexico/fixtures/item_group_fiscal_structure.json`

```json
[
    {
        "doctype": "Item Group",
        "item_group_name": "Artículos IEPS Alcohol",
        "parent_item_group": "All Item Groups"
    }
]
```

**Características:**
- ✅ Zero-config deployment (RG-009)
- ✅ Versionado en git
- ✅ Modificable desde UI si necesario (raro)
- ❌ Queries a DB en runtime (overhead performance)
- ❌ Requiere DocType adicional

---

## 🎯 OPCIONES ARQUITECTÓNICAS PROPUESTAS

### OPCIÓN 1: Tabla Maestra Python en utils/reglas_calculo_fiscal.py

**Estructura propuesta:**

```python
"""
SINGLE SOURCE OF TRUTH - Reglas Cálculo Fiscal
===============================================
Define CÓMO se calculan los impuestos por cada rol_fiscal.

Fuente canónica: TABLA_MAESTRA_REGLAS_CALCULO
No modificar en otro archivo.
"""

from facturacion_mexico.utils.roles_fiscales import (
    ROL_IVA_NAC, ROL_IVA_FRO, ROL_IVA_CERO, ROL_IVA_EXENTO,
    ROL_IEPS_ALC, ROL_IEPS_AZU, ROL_IEPS_COMB, ROL_IEPS_TAB, ROL_IEPS_TABQ,
    ROL_RET_IVA_HON, ROL_RET_IVA_ARR, ROL_RET_IVA_AUTO, ROL_RET_IVA_RESICO,
    ROL_RET_ISR_HON, ROL_RET_ISR_ARR, ROL_RET_ISR_AUTO, ROL_RET_ISR_RESICO,
)

# Tabla maestra: (rol_fiscal, regla_base, regla_calculo, cascada, alcance, habilitada, fundamento_legal, notas)
TABLA_MAESTRA_REGLAS_CALCULO = [
    # IVA - Traslado porcentual sobre monto neto
    (ROL_IVA_NAC, "monto_neto", "porcentual", False, "por_item", True, "Ley IVA Art. 1", "16% sobre monto neto"),
    (ROL_IVA_FRO, "monto_neto", "porcentual", False, "por_item", True, "Ley IVA Art. 1", "8% zona frontera"),
    (ROL_IVA_CERO, "monto_neto", "porcentual", False, "por_item", True, "Ley IVA Art. 2-A", "0% exportación"),
    (ROL_IVA_EXENTO, "monto_neto", "porcentual", False, "por_item", True, "Ley IVA Art. 9", "Exento de IVA"),

    # IEPS Tasa - Porcentual sobre monto neto
    (ROL_IEPS_ALC, "monto_neto", "porcentual", False, "por_item", True, "LIEPS Art. 2", "IEPS Alcohol tasa"),
    (ROL_IEPS_AZU, "monto_neto", "porcentual", False, "por_item", True, "LIEPS Art. 2", "IEPS Azúcar/Bebidas"),
    (ROL_IEPS_COMB, "monto_neto", "porcentual", False, "por_item", True, "LIEPS Art. 2", "IEPS Combustibles"),
    (ROL_IEPS_TAB, "monto_neto", "porcentual", False, "por_item", True, "LIEPS Art. 2", "IEPS Tabaco tasa"),

    # IEPS Cuota - Cuota unitaria por cantidad
    (ROL_IEPS_TABQ, "cantidad", "cuota", False, "por_item", True, "LIEPS Art. 2-A", "Cuota × cantidad"),

    # Retenciones IVA - Retención sobre IVA trasladado
    (ROL_RET_IVA_HON, "iva_trasladado", "retención", False, "por_item", True, "Ley IVA Art. 1-A III", "2/3 IVA"),
    (ROL_RET_IVA_ARR, "iva_trasladado", "retención", False, "por_item", True, "Ley IVA Art. 1-A II", "10% IVA"),
    (ROL_RET_IVA_AUTO, "iva_trasladado", "retención", False, "por_item", True, "Ley IVA Art. 1-A IV", "4% IVA"),
    (ROL_RET_IVA_RESICO, "iva_trasladado", "retención", False, "por_item", True, "Ley IVA Art. 1-A", "Ret RESICO"),

    # Retenciones ISR - Retención sobre monto neto
    (ROL_RET_ISR_HON, "monto_neto", "retención", False, "por_item", True, "LISR Art. 106", "10% honorarios"),
    (ROL_RET_ISR_ARR, "monto_neto", "retención", False, "por_item", True, "LISR Art. 116", "10% arrendamiento"),
    (ROL_RET_ISR_AUTO, "monto_neto", "retención", False, "por_item", True, "LISR Art. 154", "Autotransporte"),
    (ROL_RET_ISR_RESICO, "monto_neto", "retención", False, "por_item", True, "LISR Art. 113-E", "1.25% RESICO"),
]

# Diccionarios derivados auto-generados
REGLAS_POR_ROL = {
    row[0]: {
        "regla_base": row[1],
        "regla_calculo": row[2],
        "cascada": row[3],
        "alcance": row[4],
        "habilitada": row[5],
        "fundamento_legal": row[6],
        "notas_calculo": row[7],
    }
    for row in TABLA_MAESTRA_REGLAS_CALCULO
}

def obtener_regla_calculo(rol_fiscal: str) -> dict | None:
    """
    Obtiene reglas de cálculo para un rol fiscal.

    Args:
        rol_fiscal: Nombre exacto del rol (ej: "IVA por Pagar (Nacional)")

    Returns:
        dict con reglas o None si no existe

    Example:
        >>> regla = obtener_regla_calculo(ROL_IVA_NAC)
        >>> print(regla["regla_base"])
        "monto_neto"
    """
    return REGLAS_POR_ROL.get(rol_fiscal)
```

**Uso en función rectora:**

```python
from facturacion_mexico.utils.reglas_calculo_fiscal import obtener_regla_calculo

def aplicar_reglas_calculo_impuestos(doc, tax_row, metadata):
    """Función rectora única para cálculos fiscales."""
    rol_fiscal = metadata.get("rol_fiscal")

    # Obtener reglas desde tabla maestra
    reglas = obtener_regla_calculo(rol_fiscal)
    if not reglas:
        frappe.logger().warning(f"No hay reglas definidas para {rol_fiscal}")
        return  # Bypass sin error

    if not reglas["habilitada"]:
        frappe.logger().info(f"Regla {rol_fiscal} deshabilitada, skipping")
        return

    # Aplicar lógica según reglas
    base = _obtener_base(doc, tax_row, reglas["regla_base"], reglas["alcance"])
    monto = _calcular_monto(base, tax_row, reglas["regla_calculo"])
    # ...
```

**Ventajas:**
- ✅ **Zero duplicación**: 18 roles = 18 reglas (una vez)
- ✅ **Performance**: Sin queries DB en runtime
- ✅ **Inmutable**: Usuario NO puede modificar (es LO QUE QUEREMOS)
- ✅ **Patrón establecido**: Coherente con roles_fiscales.py e item_groups.py
- ✅ **Versionado**: Git tracking completo
- ✅ **Zero-config**: Se despliega con el código automáticamente
- ✅ **Reutilizable**: Función rectora + generador templates usan misma tabla

**Desventajas:**
- ❌ Cambios requieren actualización app (pero eso es aceptable - son reglas fiscales SAT)
- ❌ No modificable desde UI (pero es LO QUE QUEREMOS - reglas fiscales no deben cambiar por usuario)

---

### OPCIÓN 2: DocType independiente "Regla Calculo Fiscal" + Fixtures

**Estructura propuesta:**

Crear DocType `Regla Calculo Fiscal` (normal, NO child table):

```json
{
  "doctype": "DocType",
  "name": "Regla Calculo Fiscal",
  "module": "Facturacion Fiscal",
  "istable": 0,
  "fields": [
    {
      "fieldname": "rol_fiscal",
      "label": "Rol Fiscal",
      "fieldtype": "Link",
      "options": "Rol Fiscal",
      "reqd": 1,
      "unique": 1
    },
    {
      "fieldname": "regla_base",
      "label": "Base de Cálculo",
      "fieldtype": "Select",
      "options": "monto_neto\ncantidad\nfila_previa_monto\nfila_previa_total\niva_trasladado",
      "default": "monto_neto"
    },
    // ... resto campos
  ]
}
```

Fixture `facturacion_mexico/fixtures/regla_calculo_fiscal.json`:

```json
[
  {
    "doctype": "Regla Calculo Fiscal",
    "rol_fiscal": "IVA por Pagar (Nacional)",
    "regla_base": "monto_neto",
    "regla_calculo": "porcentual",
    "cascada": 0,
    "alcance": "por_item",
    "habilitada": 1,
    "fundamento_legal": "Ley IVA Art. 1",
    "notas_calculo": "16% sobre monto neto"
  },
  // ... 17 más
]
```

Modificar `Mapeo Cuenta Fiscal Mexico`:
```json
{
  "fieldname": "regla_calculo_fiscal",
  "label": "Regla de Cálculo",
  "fieldtype": "Link",
  "options": "Regla Calculo Fiscal"
}
```

**Ventajas:**
- ✅ **Zero duplicación**: Link a regla única
- ✅ **Fixtures**: RG-009 compliance (zero-config)
- ✅ **UI modificable**: Si en futuro se necesita (raro)
- ✅ **Separación concerns**: Reglas fiscales separadas de mapeo contable

**Desventajas:**
- ❌ **Queries DB**: Overhead en runtime
- ❌ **DocType adicional**: Complejidad arquitectónica
- ❌ **Modificable por usuario**: Puede romper reglas fiscales (NO QUEREMOS)
- ❌ **Fixture sync**: Debe mantenerse sincronizado con código

---

### OPCIÓN 3: Mantener en Child Table con Lógica Auto-Poblamiento

**Estructura:**

Mantener los 7 campos agregados en `Mapeo Cuenta Fiscal Mexico` pero:
- Auto-poblar reglas desde tabla maestra Python
- Hook `before_save` en `Configuracion Fiscal Mexico` para sincronizar

```python
# En configuracion_fiscal_mexico.py
from facturacion_mexico.utils.reglas_calculo_fiscal import REGLAS_POR_ROL

def validate(self):
    """Auto-poblar reglas de cálculo desde tabla maestra."""
    for mapeo in self.mapeo_cuentas:
        rol_fiscal = mapeo.rol_fiscal

        # Obtener reglas desde tabla maestra
        reglas = REGLAS_POR_ROL.get(rol_fiscal)
        if not reglas:
            continue

        # Auto-poblar si no hay configuración manual
        if not mapeo.regla_base:
            mapeo.regla_base = reglas["regla_base"]
            mapeo.regla_calculo = reglas["regla_calculo"]
            mapeo.cascada = reglas["cascada"]
            mapeo.alcance = reglas["alcance"]
            mapeo.habilitada = reglas["habilitada"]
            mapeo.fundamento_legal = reglas["fundamento_legal"]
            mapeo.notas_calculo = reglas["notas_calculo"]
```

**Ventajas:**
- ✅ **Auto-poblamiento**: Usuario no configura
- ✅ **Visible en UI**: Usuario puede ver reglas aplicadas
- ✅ **Flexible**: Permite override manual si necesario

**Desventajas:**
- ❌ **Duplicación en BD**: Reglas repetidas en cada mapeo (si múltiples cuentas mismo rol)
- ❌ **Sincronización compleja**: Hook debe mantener coherencia
- ❌ **Override peligroso**: Usuario podría modificar y romper reglas fiscales
- ❌ **NO cumple requisito**: Usuario NO debe configurar (aquí podría modificar)

---

## 📊 COMPARATIVA OPCIONES

| Criterio | OPCIÓN 1 (Tabla Maestra) | OPCIÓN 2 (DocType+Fixture) | OPCIÓN 3 (Child+Auto) |
|----------|-------------------------|---------------------------|----------------------|
| **Zero duplicación** | ✅ Absoluto (18 reglas) | ✅ Link único | ❌ Repetido por cuenta |
| **Performance** | ✅ Sin queries | ❌ Query DB | ⚠️ Queries + hook |
| **Inmutabilidad** | ✅ Usuario NO modifica | ❌ Modificable UI | ❌ Override manual |
| **Zero-config (RG-009)** | ✅ Código auto-deploy | ✅ Fixtures migrate | ⚠️ Hook auto-pobla |
| **Patrón establecido** | ✅ item_groups.py, roles_fiscales.py | ⚠️ Nuevo patrón | ❌ Híbrido complejo |
| **Versionado git** | ✅ Directo | ✅ Fixtures | ⚠️ Código + datos |
| **Complejidad** | ✅ Simple (1 archivo) | ⚠️ DocType + fixture | ❌ Hook + sync logic |
| **Reutilización** | ✅ Import directo | ⚠️ frappe.get_doc() | ❌ Solo vía mapeo |
| **Requisito usuario NO configura** | ✅ Imposible modificar | ❌ Puede modificar UI | ❌ Puede override |

---

## 🎯 RECOMENDACIÓN TÉCNICA

### OPCIÓN 1: Tabla Maestra Python (utils/reglas_calculo_fiscal.py)

**Justificación:**

1. **Cumple TODOS los requisitos:**
   - ✅ Usuario NO configura (inmutable)
   - ✅ Zero duplicación (18 roles = 18 reglas)
   - ✅ Zero-config deployment (código se despliega)
   - ✅ RG-009 compliance

2. **Patrón establecido:**
   - Coherente con `roles_fiscales.py` (mismo propósito: definir reglas fiscales)
   - Coherente con `item_groups.py` (tabla maestra + constantes derivadas)
   - Mantiene consistencia arquitectónica

3. **Performance óptimo:**
   - Sin queries DB en runtime
   - Cache en memoria (diccionarios Python)
   - Función rectora ejecuta miles de veces (cada item, cada tax row)

4. **Mantenibilidad:**
   - Single source of truth absoluto
   - Cambios fiscales SAT → actualizar tabla maestra → migrate
   - Git tracking completo de cambios regulatorios

5. **Reutilización:**
   - Función rectora: `from utils.reglas_calculo_fiscal import obtener_regla_calculo`
   - Generador templates: mismo import
   - Tests unitarios: mismo import
   - Zero dependencies circulares

### Implementación Propuesta

**Paso 1:** Descartar cambios unstaged en child table
```bash
git restore facturacion_mexico/facturacion_fiscal/doctype/mapeo_cuenta_fiscal_mexico/mapeo_cuenta_fiscal_mexico.json
```

**Paso 2:** Crear tabla maestra
```bash
# Crear archivo nuevo
facturacion_mexico/utils/reglas_calculo_fiscal.py
```

**Paso 3:** Modificar `Mapeo Cuenta Fiscal Mexico` (solo si necesario UI)
- Agregar campos **read_only** para mostrar reglas aplicadas
- Poblar desde Python en `configuracion_fiscal_mexico.py`
- Solo display, NO editable

**Paso 4:** Implementar función rectora
```python
# facturacion_mexico/utils/calculo_impuestos.py
from facturacion_mexico.utils.reglas_calculo_fiscal import obtener_regla_calculo

def aplicar_reglas_calculo_impuestos(doc, tax_row, metadata):
    """Función rectora única."""
    reglas = obtener_regla_calculo(metadata["rol_fiscal"])
    # ... lógica cálculo
```

**Paso 5:** Tests
```python
# tests/test_reglas_calculo_fiscal.py
def test_todas_las_reglas_definidas():
    """Verificar que los 18 roles tienen regla."""
    from facturacion_mexico.utils.roles_fiscales import TODOS_LOS_ROLES
    from facturacion_mexico.utils.reglas_calculo_fiscal import REGLAS_POR_ROL

    for rol in TODOS_LOS_ROLES:
        assert rol in REGLAS_POR_ROL, f"Falta regla para {rol}"
```

---

## 🚨 DECISIÓN REQUERIDA

### Preguntas al Usuario:

1. **¿Aprobar OPCIÓN 1** (Tabla Maestra Python en utils/reglas_calculo_fiscal.py)?

2. **¿Descartar cambios unstaged** en `mapeo_cuenta_fiscal_mexico.json`?

3. **¿Agregar campos read_only** en child table para mostrar reglas (opcional)?
   - Ventaja: Usuario ve qué reglas se aplican
   - Complejidad: Hook para poblar desde Python
   - Alternativa: No mostrar, solo usar en función rectora

4. **¿Incluir validación sincronización** en tests (similar a `test_sync_roles_fiscales_json_python.py`)?
   - Valida que TODOS los roles tienen regla definida
   - Previene agregar rol_fiscal sin regla de cálculo

---

## 📝 PRÓXIMOS PASOS (si aprobado)

**PASO 1 CORREGIDO:** Descartar cambios child table + Crear tabla maestra (1.5h)
1. `git restore mapeo_cuenta_fiscal_mexico.json`
2. Crear `facturacion_mexico/utils/reglas_calculo_fiscal.py`
3. Definir TABLA_MAESTRA_REGLAS_CALCULO (18 filas)
4. Generar diccionarios derivados
5. Crear función `obtener_regla_calculo()`

**PASO 2:** Implementar función rectora (2h)
- Crear `facturacion_mexico/utils/calculo_impuestos.py`
- Función `aplicar_reglas_calculo_impuestos()`
- Helpers: `_calcular_porcentual()`, `_calcular_cuota()`, `_calcular_retencion()`

**PASO 3:** Tests sincronización (1h)
- `test_todas_las_reglas_definidas()`
- `test_reglas_coherentes()`
- `test_obtener_regla_calculo()`

**PASO 4:** Refactorizar hooks (1h)
- Modificar `sales_invoice_ieps.py`
- Usar función rectora en lugar de lógica hardcoded

**PASO 5:** Tests E2E (2h)
- Verificar cálculos con reglas desde tabla maestra

---

**Total estimado:** 7.5h (vs 8h original, pero arquitectura correcta)
