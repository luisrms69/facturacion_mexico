# REPORTE: Migración charge_type Dinámico desde Tabla Maestra (E1)

**Fecha:** 2025-10-26
**Branch:** feature/e1-automated-tax-system
**Contexto:** Implementación IEPS Tasa + Sistema charge_type dinámico

---

## 📋 RESUMEN EJECUTIVO

Durante la implementación de IEPS Tasa rates dinámicos, se migró el sistema de generación de templates STCT de valores hardcoded a sistema dinámico basado en **tabla maestra reglas de cálculo fiscal**.

**Objetivo:** Eliminar hardcoding de `charge_type` en generador templates, leyendo valores desde tabla maestra `reglas_calculo_fiscal.py`.

**Estado:** ✅ Implementación funcional con 1 decisión pendiente (IVA cascada IEPS).

---

## 🔧 CAMBIOS REALIZADOS

### 1. ARCHIVO NUEVO: `reglas_calculo_fiscal.py`

**Ubicación:** `facturacion_mexico/utils/reglas_calculo_fiscal.py`

**Propósito:** Single Source of Truth para reglas de cálculo de impuestos.

**Estructura tabla maestra:**
```python
TABLA_MAESTRA_REGLAS_CALCULO = [
    (
        rol_fiscal,           # ROL_IVA_NAC, ROL_IEPS_ALC, etc.
        regla_base,          # monto_neto, cantidad, iva_trasladado, fila_previa_*
        regla_calculo,       # porcentual, cuota, retención
        cascada,             # Boolean
        alcance,             # por_item, fila_previa
        habilitada,          # Boolean
        fundamento_legal,    # String
        notas_calculo,       # String
        version,             # YYYY.MM
        deprecada_desde      # None si vigente
    ),
]
```

**Mapeo `regla_base` → `charge_type` ERPNext:**
```python
_MAPEO_CHARGE_TYPE = {
    "monto_neto": "On Net Total",
    "cantidad": "Actual",
    "fila_previa_monto": "On Previous Row Amount",
    "fila_previa_total": "On Previous Row Total",
    "iva_trasladado": "On Previous Row Amount",
}
```

**Configuración roles fiscales:**

| Rol Fiscal | regla_base | charge_type ERPNext |
|-----------|-----------|-------------------|
| ROL_IVA_NAC | `monto_neto` | On Net Total |
| ROL_IVA_FRO | `monto_neto` | On Net Total |
| ROL_IEPS_ALC | `monto_neto` | On Net Total |
| ROL_IEPS_TAB | `monto_neto` | On Net Total |
| ROL_IEPS_AZU | `cantidad` | Actual |
| ROL_IEPS_COMB | `cantidad` | Actual |
| ROL_IEPS_TABQ | `cantidad` | Actual |
| ROL_RET_IVA_* | `monto_neto` | On Net Total |
| ROL_RET_ISR_* | `monto_neto` | On Net Total |

**NOTA CRÍTICA - Retenciones IVA:**

Originalmente configuré retenciones IVA con `regla_base: "iva_trasladado"` (fiscalmente correcto), pero esto causaba error de row_id porque el generador NO asignaba row_id para retenciones.

**Corrección aplicada:** Cambié retenciones IVA a `regla_base: "monto_neto"` para replicar comportamiento legacy STCT viejo.

```python
# ANTES (causaba error row_id):
(ROL_RET_IVA_HON, "iva_trasladado", ...)  # → "On Previous Row Amount" → REQUIERE row_id

# DESPUÉS (correcto - legacy):
(ROL_RET_IVA_HON, "monto_neto", ...)      # → "On Net Total" → NO requiere row_id
```

---

### 2. MODIFICACIONES: `generador_templates_fiscal.py`

**Ubicación:** `facturacion_mexico/facturacion_fiscal/setup/generador_templates_fiscal.py`

#### Cambio 1: Import tabla maestra + función dinámica

**Líneas agregadas 25-67:**

```python
# Import para tabla maestra reglas cálculo
from facturacion_mexico.utils.reglas_calculo_fiscal import obtener_regla_calculo

# Import tasas IEPS para generación ITT
from facturacion_mexico.facturacion_fiscal.config.constantes_fiscales import TASAS_IEPS

# Mapeo regla_base → charge_type ERPNext
_MAPEO_CHARGE_TYPE = {
    "monto_neto": "On Net Total",
    "cantidad": "Actual",
    "fila_previa_monto": "On Previous Row Amount",
    "fila_previa_total": "On Previous Row Total",
    "iva_trasladado": "On Previous Row Amount",
}

def _charge_type_por_rol(rol_fiscal: str) -> str:
    """
    Obtiene charge_type de ERPNext según rol fiscal desde tabla maestra.

    Returns:
        str: charge_type de ERPNext ("On Net Total", "Actual", etc.)
    """
    reglas = obtener_regla_calculo(rol_fiscal) or {}
    base = reglas.get("regla_base", "monto_neto")
    return _MAPEO_CHARGE_TYPE.get(base, "On Net Total")
```

#### Cambio 2: Migración funciones fila_* a dinámico

**ANTES (legacy - hardcoded):**
```python
def fila_iva_base(account_head: str, zona: str, tasa_valor: float) -> dict:
    return {
        "charge_type": "On Net Total",  # ← HARDCODED
        ...
    }
```

**DESPUÉS (E1 - dinámico):**
```python
def fila_iva_base(account_head: str, zona: str, tasa_valor: float, rol_fiscal: str) -> dict:
    return {
        "charge_type": _charge_type_por_rol(rol_fiscal),  # ← DINÁMICO
        ...
    }
```

**Funciones migradas:**

1. ✅ `fila_iva_base()` - línea 270
2. ✅ `fila_ieps_tasa()` - línea 313
3. ✅ `fila_ieps_cuota()` - línea 351
4. ✅ `fila_retencion()` - línea 394

**Código legacy comentado:** Todas las versiones hardcoded comentadas arriba de cada función nueva.

#### Cambio 3: Nueva función `fila_iva_cascada_ieps()`

**Líneas 421-451:**

```python
def fila_iva_cascada_ieps(account_head: str, concepto_ieps: str, iva_rate: float, rol_fiscal: str) -> dict:
    """
    IVA cascada sobre IEPS (calcula IVA sobre el monto del IEPS anterior).

    HARDCODEA charge_type "On Previous Row Amount" porque IVA cascada sobre IEPS:
    - NO es un rol fiscal independiente (usa misma cuenta IVA)
    - SIEMPRE calcula sobre fila previa (IEPS)
    - Es lógica específica de generador templates, no de tabla maestra
    """
    return {
        "charge_type": "On Previous Row Amount",  # HARDCODE - IVA cascada siempre usa prev row
        "row_id": None,  # Se asigna después en _build_rows()
        "rate": iva_rate,
        "description": f"IVA sobre IEPS {concepto_ieps}",
        ...
    }
```

**⚠️ DECISIÓN PENDIENTE:** Esta función tiene `charge_type` hardcoded. Ver sección "Consulta ChatGPT" abajo.

#### Cambio 4: Actualizar llamadas a funciones fila_*

**Ejemplo - IVA Base (línea 497):**
```python
# ANTES:
rows.append(fila_iva_base(iva_acc, zona, iva_rate))

# DESPUÉS:
rows.append(fila_iva_base(iva_acc, zona, iva_rate, rol_iva))  # + rol_fiscal
```

**Aplicado a todas las llamadas:**
- `fila_iva_base()` → + `rol_iva`
- `fila_ieps_tasa()` → + `ROL_IEPS_ALC`/`ROL_IEPS_TAB`
- `fila_ieps_cuota()` → + `ROL_IEPS_AZU`/`ROL_IEPS_COMB`/`ROL_IEPS_TABQ`
- `fila_retencion()` → + `ROL_RET_*`

#### Cambio 5: Agregar filas IVA cascada IEPS

**Patrón implementado (ejemplo Alcohol - líneas 506-514):**

```python
if ieps["Alcohol"]:
    acc = mapeos_cache.get(ROL_IEPS_ALC) or _get_account_head_by_role(company, ROL_IEPS_ALC)
    rows.append(fila_ieps_tasa(acc, "Alcohol", ROL_IEPS_ALC))

    # IVA cascada sobre IEPS Alcohol (E1: nueva fila)
    ieps_row_idx = len(rows)  # idx será len(rows) porque se asigna en _make_stct
    fila_iva = fila_iva_cascada_ieps(iva_acc, "Alcohol", iva_rate, rol_iva)
    fila_iva["row_id"] = ieps_row_idx  # Asignar row_id explícito
    rows.append(fila_iva)
```

**Aplicado a 5 conceptos IEPS:**
1. Alcohol (Tasa)
2. Azúcar/Bebidas (Cuota)
3. Combustibles (Cuota)
4. Tabaco Tasa
5. Tabaco Cuota

**Lógica row_id:**
- Calcula `ieps_row_idx = len(rows)` después de agregar fila IEPS
- Asigna `fila_iva["row_id"] = ieps_row_idx` antes de append
- ERPNext calcula IVA sobre monto de fila previa (IEPS)

#### Cambio 6: Actualizar tasas IEPS en ITT

**Líneas 1053-1086 - ITT Generation:**

```python
# ANTES:
[{"rol_fiscal": "IEPS por Pagar (Alcohol)", "tax_rate": 0}]

# DESPUÉS:
[{"rol_fiscal": "IEPS por Pagar (Alcohol)", "tax_rate": TASAS_IEPS["alcohol"]["tasa"]}]
# Tasa desde constantes - heredada por items vía Item Group
```

**Tasas actualizadas:**
- Alcohol: 0% → 26.5%
- Tabaco: 0% → 160.0%
- Azúcar: 0% (correcto - cuota, no tasa)
- Combustibles: 0% (correcto - cuota, no tasa)

---

### 3. MODIFICACIONES: `hooks.py`

**Cambio único - Mover hook a before_save:**

**Líneas 345-349:**

```python
# ANTES:
"before_save": [
    "facturacion_mexico.hooks_handlers.sales_invoice_ieps.calcular_ieps_cuota",
    "facturacion_mexico.hooks_handlers.sales_invoice_ieps.ajustar_base_iva_combustibles",
],
"before_submit": "facturacion_mexico.hooks_handlers.sales_invoice_ieps.corregir_ieps_cuota_final",

# DESPUÉS:
"before_save": [
    "facturacion_mexico.hooks_handlers.sales_invoice_ieps.calcular_ieps_cuota",
    "facturacion_mexico.hooks_handlers.sales_invoice_ieps.ajustar_base_iva_combustibles",
    "facturacion_mexico.hooks_handlers.sales_invoice_ieps.corregir_ieps_cuota_final",  # ← MOVIDO
]
```

**Razón:** Verificar que cálculos IEPS se ejecuten antes de guardar (no solo submit).

---

## 🧪 PROCESO DE DEBUGGING

### Problema 1: Errores row_id al regenerar templates

**Error original:**
```
Message: Please specify a valid Row ID for row 2 in table Sales Taxes and Charges
Please specify a valid Row ID for row 12 in table Sales Taxes and Charges
```

**Diagnóstico paso a paso:**

1. **PASO 1 - fila_iva_base() dinámico:** ✅ Funciona
2. **PASO 2 - fila_ieps_tasa() dinámico:** ✅ Funciona
3. **PASO 3 - fila_retencion() dinámico:** ❌ ERROR row_id

**Causa raíz identificada:**

Retenciones IVA tenían `regla_base: "iva_trasladado"` en tabla maestra:
- `"iva_trasladado"` → mapea a `"On Previous Row Amount"`
- `"On Previous Row Amount"` → REQUIERE `row_id`
- Generador NO asignaba `row_id` para retenciones
- ERPNext rechazaba template

**Verificación:**
```bash
python3 -c "
from facturacion_mexico.utils.reglas_calculo_fiscal import obtener_regla_calculo
from facturacion_mexico.utils.roles_fiscales import ROL_RET_IVA_HON

reglas = obtener_regla_calculo(ROL_RET_IVA_HON) or {}
print(reglas.get('regla_base'))
"
# OUTPUT: iva_trasladado  ← CAUSA DEL ERROR
```

**Solución aplicada:**

Cambié tabla maestra `reglas_calculo_fiscal.py` líneas 193-246:

```python
# ANTES (incorrecto - causaba error):
(ROL_RET_IVA_HON, "iva_trasladado", ...)

# DESPUÉS (correcto - replica legacy):
(ROL_RET_IVA_HON, "monto_neto", ...)
```

**Resultado:** ✅ Templates regeneran sin error.

**4. PASO 4 - fila_ieps_cuota() dinámico:** ✅ Funciona

Tabla maestra configurada con `regla_base: "cantidad"` → `charge_type: "Actual"` (correcto).

---

## ⚠️ DECISIÓN PENDIENTE: IVA Cascada IEPS

### Contexto

La función `fila_iva_cascada_ieps()` actualmente tiene **hardcoding**:

```python
def fila_iva_cascada_ieps(...):
    return {
        "charge_type": "On Previous Row Amount",  # ← HARDCODED
        ...
    }
```

### Problema

**IVA cascada sobre IEPS NO es un rol fiscal independiente:**
- Usa misma cuenta contable que IVA Nacional/Frontera
- Solo difiere en `charge_type` y `row_id`
- Calcula IVA sobre monto IEPS en vez de monto neto

**Si uso dinámico `_charge_type_por_rol(rol_iva)`:**
- `rol_iva` = ROL_IVA_NAC o ROL_IVA_FRO
- Tabla maestra: `regla_base: "monto_neto"` → `charge_type: "On Net Total"`
- **INCORRECTO:** Necesitamos "On Previous Row Amount"

### Opciones

**A) Mantener hardcode "On Previous Row Amount"**

✅ **PRO:**
- Lógica específica generador templates
- No contamina tabla maestra con variantes técnicas
- Claridad en código (explícito = IVA cascada)

❌ **CON:**
- Único hardcode restante en generador

**B) Crear rol fiscal nuevo "IVA Cascada IEPS"**

Agregar a `roles_fiscales.py`:
```python
ROL_IVA_CASCADA_IEPS = "IVA Cascada sobre IEPS"
```

Agregar a `reglas_calculo_fiscal.py`:
```python
(
    ROL_IVA_CASCADA_IEPS,
    "fila_previa_monto",  # → "On Previous Row Amount"
    "porcentual",
    True,  # cascada=True
    "fila_previa",
    True,
    "Ley IVA Art. 1 + LIEPS Art. 4",
    "IVA sobre IEPS trasladado. Base = monto IEPS fila previa.",
    "2025.01",
    None,
)
```

✅ **PRO:**
- Sistema completamente dinámico (0% hardcode)
- Rol fiscal explícito para auditoría
- Fundamento legal documentado

❌ **CON:**
- Rol artificial (no existe en catálogo SAT)
- IVA cascada es lógica cálculo, no tipo impuesto
- Complejidad adicional tabla maestra

**C) Pasar `charge_type` como parámetro explícito**

```python
def fila_iva_cascada_ieps(account_head, concepto_ieps, iva_rate, charge_type="On Previous Row Amount"):
    return {
        "charge_type": charge_type,
        ...
    }
```

✅ **PRO:**
- Flexibilidad futura
- Sin hardcode interno función

❌ **CON:**
- Hardcode se mueve a caller (mismo problema)

---

## 🤔 CONSULTA PARA CHATGPT

### Pregunta

En un sistema de facturación fiscal mexicano, tenemos:

**Contexto técnico:**
- ERPNext con Sales Taxes and Charges Template (STCT)
- Migración de valores hardcoded → sistema dinámico basado en tabla maestra
- Tabla maestra mapea `rol_fiscal` → `regla_base` → `charge_type` ERPNext

**Roles fiscales en catálogo SAT:**
- IVA por Pagar (Nacional) - 16%
- IVA por Pagar (Frontera) - 8%
- IEPS por Pagar (Alcohol) - 26.5%
- IEPS por Pagar (Tabaco) - 160%
- Etc.

**Problema específico - IVA sobre IEPS:**

Según Ley IEPS Art. 4, el IVA se calcula sobre:
```
Base IVA = Precio + IEPS
```

Implementé filas STCT:
1. Fila N: IEPS Alcohol ($874.50) - charge_type: "On Net Total"
2. Fila N+1: IVA sobre IEPS Alcohol ($139.92) - charge_type: "On Previous Row Amount", row_id: N

**La fila N+1 NO es un rol fiscal independiente:**
- Usa misma cuenta contable que "IVA por Pagar (Nacional)"
- Solo difiere en charge_type y row_id (calcula sobre fila previa)
- Es lógica de cálculo específica, no tipo impuesto diferente

**Opciones evaluadas:**

**A) Hardcodear "On Previous Row Amount" en función generadora:**
```python
def fila_iva_cascada_ieps(...):
    return {"charge_type": "On Previous Row Amount", ...}
```

**B) Crear rol fiscal artificial "IVA Cascada sobre IEPS":**
- Agregar a tabla maestra con regla_base: "fila_previa_monto"
- Rol NO existe en catálogo SAT
- Contamina tabla maestra con variante técnica

**C) Usar rol IVA Nacional dinámico pero falla:**
- Tabla maestra IVA Nacional: regla_base: "monto_neto" → charge_type: "On Net Total"
- Necesitamos "On Previous Row Amount" para cascada

### Pregunta concreta

**¿Cuál es la mejor práctica arquitectónica?**

1. ¿Hardcode aceptable para lógica específica generador templates?
2. ¿Crear rol fiscal artificial para completitud sistema dinámico?
3. ¿Otra solución que mantenga Single Source of Truth sin contaminar modelo fiscal?

**Consideraciones:**
- Prioridad: correctitud fiscal sobre pureza arquitectónica
- Tabla maestra debe reflejar catálogo SAT real
- Sistema debe ser mantenible largo plazo

---

## 📊 RESUMEN CAMBIOS POR ARCHIVO

| Archivo | Tipo | Líneas modificadas | Funciones afectadas |
|---------|------|-------------------|---------------------|
| `reglas_calculo_fiscal.py` | NUEVO | 446 | `obtener_regla_calculo()`, tabla maestra completa |
| `generador_templates_fiscal.py` | MODIFICADO | ~441 diff | `_charge_type_por_rol()`, `fila_*()`, `_build_rows()`, ITT generation |
| `hooks.py` | MODIFICADO | 5 | Reordenar hooks Sales Invoice |

**Total líneas código nuevo:** ~900 líneas (incluyendo docstrings y comentarios)

---

## ✅ VALIDACIÓN FUNCIONAL

**Templates regenerados exitosamente:**
- ✅ IVA Nacional - Básico - _TC
- ✅ IVA Nacional - IEPS - _TC
- ✅ IVA Nacional - Retenciones - _TC
- ✅ IVA Nacional - Total - _TC
- ✅ IVA Frontera - Básico - _TC
- ✅ IVA Frontera - IEPS - _TC
- ✅ IVA Frontera - Retenciones - _TC
- ✅ IVA Frontera - Total - _TC

**ITT actualizados con tasas:**
- ✅ ITT IEPS Alcohol: 0% → 26.5%
- ✅ ITT IEPS Tabaco: 0% → 160%

**Sistema dinámico funcionando:**
- ✅ Todas las funciones `fila_*()` usan `_charge_type_por_rol()`
- ✅ Tabla maestra controla charge_type
- ⚠️ 1 hardcode pendiente decisión: `fila_iva_cascada_ieps()`

---

## 🎯 SIGUIENTE PASO

**Esperar respuesta ChatGPT sobre IVA cascada IEPS** antes de:

1. Decidir si mantener hardcode o crear rol fiscal artificial
2. Hacer commit final
3. Crear SI test con múltiples items para verificar 11 filas + cálculos correctos
4. Validar Grand Total vs PAC esperado ($8,200.10)

---

**Generado:** 2025-10-26
**Branch:** feature/e1-automated-tax-system
**Sesión:** Continuación implementación IEPS Tasa E1
