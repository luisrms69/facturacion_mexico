# ADR 0030 — Reglas de cálculo fiscal como tablas maestras Python

**Fecha:** 2025-10-25
**Estado:** Implementado — PR #83 (`78d4606`)
**Autor:** Luis Montanaro / Claude Sonnet 4.6

---

## Contexto

El sistema de impuestos requiere definir, para cada rol fiscal (IVA Nacional, IEPS Alcohol,
retenciones, etc.), dos piezas de configuración:

1. **Base de cálculo:** sobre qué se calcula el impuesto (`monto_neto`, `cantidad`, `fila_previa_monto`)
2. **`charge_type` ERPNext:** cómo lo calcula el motor nativo (`On Net Total`, `On Item Quantity`, `On Previous Row Amount`)

La primera aproximación fue agregar estos campos como columnas en `Mapeo Cuenta Fiscal Mexico`
(child table de `Configuracion Fiscal Mexico`). Esto implicaba repetir la misma regla
una vez por cada cuenta contable del rol — violación DRY y riesgo de inconsistencias.

Alternativa evaluada: DocType independiente `Regla Calculo Fiscal` con fixtures.
Requería queries a BD en runtime, nuevo DocType, y la regla seguía siendo modificable
desde la UI — precisamente lo que no se quiere (las reglas son normativa SAT, no config de usuario).

---

## Decisión

**Las reglas de cálculo fiscal se almacenan en tablas maestras Python**, no en BD ni fixtures.

Patrón establecido en el proyecto (coherente con `roles_fiscales.py` e `item_groups.py`):

```python
# facturacion_mexico/utils/reglas_calculo_fiscal.py
# Estructura: (rol_fiscal, regla_base, regla_calculo, cascada, alcance,
#              habilitada, fundamento_legal, notas_calculo, version, deprecada_desde)
TABLA_MAESTRA_REGLAS_CALCULO = [
    (ROL_IVA_NAC,    "monto_neto", "porcentual", False, "por_item", True, "Ley IVA Art. 1",   "16% sobre monto neto", "2025.01", None),
    (ROL_IVA_FRO,    "monto_neto", "porcentual", False, "por_item", True, "Ley IVA Art. 1",   "8% zona frontera",     "2025.01", None),
    (ROL_IEPS_ALC,   "monto_neto", "porcentual", False, "por_item", True, "LIEPS Art. 2 I-A", "IEPS Alcohol tasa",    "2025.01", None),
    (ROL_IEPS_AZU,   "cantidad",   "cuota",      False, "por_item", True, "LIEPS Art. 2 I-G", "IEPS Bebidas cuota",   "2025.01", None),
    (ROL_IEPS_COMB,  "cantidad",   "cuota",      False, "por_item", True, "LIEPS Art. 2-A",   "IEPS Combustibles",    "2025.01", None),
    (ROL_RET_IVA_HON,"monto_neto", "retención",  False, "por_item", True, "Ley IVA Art. 1-A", "2/3 IVA honorarios",   "2025.01", None),
    # ... 18 roles total
]
```

El `charge_type` ERPNext se deriva en tiempo de generación de templates mediante un mapeo
explícito, sin queries a BD:

```python
# facturacion_mexico/utils/mapeo_charge_type.py — constante MAPEO_CHARGE_TYPE_REGLA_BASE
MAPEO_CHARGE_TYPE_REGLA_BASE = {
    "monto_neto":        "On Net Total",
    "cantidad":          "On Item Quantity",   # E4: antes era "Actual" (ver nota abajo)
    "fila_previa_monto": "On Previous Row Amount",
    "fila_previa_total": "On Previous Row Total",
    "iva_trasladado":    "On Previous Row Amount",
}
```

> **Nota E4:** En E1 (2025-10-26), `"cantidad"` mapeaba a `"Actual"`. La migración E4
> cambió este mapeo a `"On Item Quantity"` porque `"Actual"` es inestable en el ciclo
> Draft → Submit (los valores se pierden en amend). `"On Item Quantity"` es nativo ERPNext
> y estable en todo el lifecycle.

### Caso especial: retenciones IVA usan `monto_neto`, no `iva_trasladado`

Fiscalmente, la base correcta para retenciones IVA sería `iva_trasladado`
(retener sobre el IVA que se cobra). Sin embargo, `"iva_trasladado"` mapea a
`"On Previous Row Amount"`, que requiere `row_id` explícito. El generador de
templates STCT no asignaba `row_id` para filas de retención, causando error:

```
"Please specify a valid Row ID for row N in table Sales Taxes and Charges"
```

**Decisión:** retenciones IVA usan `regla_base: "monto_neto"` → `"On Net Total"`.
Esto replica el comportamiento del STCT legacy y es compatible con el generador.
La base de retención calculada difiere marginalmente del IVA exacto, dentro de
la tolerancia fiscal.

### Caso especial: IVA cascada sobre IEPS

El IVA que se calcula sobre el monto de IEPS (no sobre el neto del ítem) no es un
rol fiscal independiente — usa la misma cuenta IVA pero con `charge_type: "On Previous Row Amount"`
apuntando a la fila IEPS. Este `charge_type` se deja **hardcodeado** en la función
`fila_iva_cascada_ieps()` del generador de templates. No se introduce como rol artificial
en la tabla maestra porque contaminaría el catálogo con una variante técnica de ERPNext,
no con un tipo fiscal SAT.

---

## Consecuencias

### Ventajas

- **Sin queries DB en runtime:** las reglas son diccionarios Python en memoria.
- **Inmutabilidad:** el usuario no puede modificar reglas fiscales desde la UI.
- **Single source of truth:** 18 roles, 18 filas — sin duplicación por empresa o cuenta contable.
- **Zero-config:** el código se despliega automáticamente; ninguna instalación requiere
  configuración manual de reglas (cumple RG-009).
- **Patrón coherente** con `roles_fiscales.py` e `item_groups.py` ya existentes.
- **Git tracking** completo de cambios regulatorios (modificación de tasa SAT → commit visible).

### Restricción

Cambiar una regla fiscal requiere actualizar el archivo Python y ejecutar
`bench migrate` (para que el generador de templates use las nuevas reglas al regenerar).
Esto es aceptable: las reglas son normativa SAT, no configuración de usuario.

### Alternativas descartadas

| Alternativa | Motivo de descarte |
|---|---|
| Child table `Mapeo Cuenta Fiscal Mexico` con los 7 campos | Repite la misma regla N veces (una por cuenta contable del rol) |
| DocType `Regla Calculo Fiscal` + fixtures | Query DB en runtime; modificable desde UI; nuevo DocType sin beneficio real |
| Auto-poblamiento desde Python en `before_save` | Duplicación en BD; riesgo de override manual; sincronización frágil |

---

## Implementación

**Archivos:**

- `facturacion_mexico/utils/reglas_calculo_fiscal.py` — tabla maestra + `obtener_regla_calculo()`
- `facturacion_mexico/utils/mapeo_charge_type.py` — `MAPEO_CHARGE_TYPE_REGLA_BASE` + `obtener_charge_type()`
- `facturacion_mexico/facturacion_fiscal/setup/generador_templates_fiscal.py` — consume la tabla maestra

**PR:** #83 — `feat(fiscal): sistema automatizado impuestos E0-E4 + fix timbrado v16`
commit `78d4606` (squash merge)

---

## Guía de extensión

Para agregar un nuevo rol fiscal con su regla de cálculo:

1. Agregar constante en `utils/roles_fiscales.py`
2. Agregar fila en `TABLA_MAESTRA_REGLAS_CALCULO` en `utils/reglas_calculo_fiscal.py`
3. Si el rol necesita fila en STCT, agregar lógica en `generador_templates_fiscal.py`
4. `bench --site <site> execute "...regenerar_templates_fiscal.run"` para actualizar templates existentes
