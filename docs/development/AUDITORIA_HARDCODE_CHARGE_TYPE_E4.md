# Auditoría Hardcode charge_type para E4

**Proyecto:** Facturación México
**Fecha:** 2025-10-27
**Objetivo:** Identificar todo hardcode de charge_type en el app para migración E4

---

## 📊 RESUMEN EJECUTIVO

**Total archivos con hardcode:** 3
**Total ocurrencias críticas:** 5

### Clasificación por prioridad:

1. **🔴 CRÍTICO** - Bloquea E4: 3 ocurrencias
2. **🟡 ADVERTENCIA** - Comentarios deprecados: 2 ocurrencias

---

## 🔴 HARDCODE CRÍTICO (BLOQUEA E4)

### 1. Mapeo charge_type hardcodeado

**Archivo:** `facturacion_mexico/facturacion_fiscal/setup/generador_templates_fiscal.py`
**Líneas:** 36-42

```python
_MAPEO_CHARGE_TYPE = {
    "monto_neto": "On Net Total",
    "cantidad": "Actual",  # ← PROBLEMA: Debe ser "On Item Quantity" en E4
    "fila_previa_monto": "On Previous Row Amount",
    "fila_previa_total": "On Previous Row Total",
}
```

**Impacto:**
- ✅ Funciona: Lee de tabla maestra `reglas_calculo_fiscal.py`
- ❌ Problema: Mapeo hardcodeado en diccionario Python
- ❌ No extensible: Agregar nuevos charge_types requiere cambio código

**Solución E4:**
1. **Corto plazo:** Cambiar `"cantidad": "Actual"` → `"cantidad": "On Item Quantity"`
2. **Largo plazo:** Migrar a tabla BD configurable (DocType "Mapeo Charge Type")

**Código corregido E4:**
```python
_MAPEO_CHARGE_TYPE = {
    "monto_neto": "On Net Total",
    "cantidad": "On Item Quantity",  # ← E4: Cambio para IEPS cuotas
    "fila_previa_monto": "On Previous Row Amount",
    "fila_previa_total": "On Previous Row Total",
}
```

---

### 2. Hook hardcode charge_type="Actual" (IVA cascada)

**Archivo:** `facturacion_mexico/hooks_handlers/sales_invoice_ieps.py`
**Línea:** 249

```python
# Cambiar a Actual y sincronizar tax_amount (fix discrepancia PAC)
iva_tax.charge_type = "Actual"
iva_tax.row_id = None  # Actual no puede tener row_id
iva_tax.rate = 0  # Actual no usa tasa porcentual
```

**Contexto:** Función `_calcular_y_distribuir_iva_sobre_ieps_cuota()`

**Impacto:**
- ⚠️ Hook muta charge_type de IVA cascada a "Actual"
- ❌ En E4: IVA cascada debe permanecer "On Previous Row Amount"
- ❌ Este código ROMPE arquitectura E4

**Solución E4:**
- **ELIMINAR** esta línea completamente
- IVA cascada debe conservar "On Previous Row Amount" del STCT
- ERPNext calcula correctamente con charge_type nativo

**Acción:** DEPRECAR función completa - No necesaria en E4

---

### 3. Hook hardcode charge_type="Actual" (IEPS cuota)

**Archivo:** `facturacion_mexico/hooks_handlers/sales_invoice_ieps.py`
**Línea:** 346

```python
# Actualizar tax row
tax_row.charge_type = "Actual"
tax_row.rate = None  # No aplica para Actual
tax_row.tax_amount = flt(total_ieps, 2)
```

**Contexto:** Función `calcular_ieps_cuota()`

**Impacto:**
- ⚠️ Hook muta charge_type de cuota IEPS a "Actual"
- ❌ En E4: Cuotas deben permanecer "On Item Quantity"
- ❌ Este código ROMPE arquitectura E4

**Solución E4:**
- **ELIMINAR** asignación de charge_type
- STCT ya genera con "On Item Quantity" (desde tabla maestra)
- Hook solo debe calcular `tax_amount` si necesario

**Código corregido E4:**
```python
# NO mutar charge_type - ya viene correcto de STCT
# tax_row.charge_type = "On Item Quantity"  # ← ELIMINADO
tax_row.rate = cuota_unitaria  # Cuota por unidad canónica
tax_row.tax_amount = flt(total_ieps, 2)  # ERPNext calcula automático
```

---

## 🟡 COMENTARIOS DEPRECADOS

### 4. Comentario regla_base="monto_neto" (deprecado)

**Archivo:** `facturacion_mexico/utils/reglas_calculo_fiscal.py`
**Líneas:** 158-161

```python
# NOTA E1: Aunque fiscalmente IEPS Cuota se calcula por cantidad, usamos "monto_neto"
# como regla_base para generar charge_type="On Net Total" en STCT. Esto evita que
# ERPNext reemplace filas STCT cuando items tienen ITT (add_taxes_from_item_tax_template=1).
# El hook calcular_ieps_cuota() setea charge_type="Actual" + tax_amount dinámicamente.
```

**Impacto:**
- ⚠️ Comentario describe arquitectura PRE-E4
- ❌ Confuso para mantenimiento futuro
- ⚠️ Indica regla_base incorrecta en tabla maestra

**Solución E4:**
- **ACTUALIZAR** comentario explicando nueva arquitectura
- **CAMBIAR** regla_base de cuotas IEPS: `"monto_neto"` → `"cantidad"`

**Comentario actualizado E4:**
```python
# NOTA E4: IEPS Cuota se calcula por cantidad (cuota unitaria × UOM canónica).
# regla_base="cantidad" mapea a charge_type="On Item Quantity" en STCT.
# ERPNext calcula automáticamente: rate × qty (sin hooks).
```

---

### 5. Comentario charge_type="Actual" (ERPNext redistribuye)

**Archivo:** `facturacion_mexico/hooks_handlers/sales_invoice_ieps.py`
**Líneas:** 448-450

```python
# ERPNext redistribuye automáticamente los impuestos con charge_type="Actual"
# de forma proporcional entre todos los items. Este hook corrige ese
# comportamiento para IEPS Cuota, restaurando la asignación correcta por item.
```

**Contexto:** Función `corregir_distribucion_ieps_cuota_post_submit()`

**Impacto:**
- ⚠️ Comentario describe workaround para "Actual"
- ✅ Con "On Item Quantity" este hook NO es necesario
- ❌ Función completa debe DEPRECARSE en E4

**Solución E4:**
- **DEPRECAR** función `corregir_distribucion_ieps_cuota_post_submit()`
- **ELIMINAR** hook `on_submit` que llama esta función
- ERPNext maneja `item_wise_tax_detail` correctamente con "On Item Quantity"

---

## 📋 TABLA MAESTRA REGLAS - CAMBIOS E4

### Roles IEPS Cuota (3 roles)

| Rol Fiscal | regla_base ACTUAL | regla_base E4 | Línea |
|------------|-------------------|---------------|-------|
| `ROL_IEPS_AZU` (Azúcar/Bebidas) | `"monto_neto"` ❌ | `"cantidad"` ✅ | 164 |
| `ROL_IEPS_COMB` (Combustibles) | `"monto_neto"` ❌ | `"cantidad"` ✅ | 177 |
| `ROL_IEPS_TABQ` (Tabaco Cuota) | `"monto_neto"` ❌ | `"cantidad"` ✅ | 189 |

**Cambios necesarios:**

```python
# ANTES (Pre-E4)
(
    ROL_IEPS_AZU,
    "monto_neto",  # ← INCORRECTO
    "cuota",
    ...
)

# DESPUÉS (E4)
(
    ROL_IEPS_AZU,
    "cantidad",  # ← CORRECTO
    "cuota",
    ...
)
```

---

## 🎯 PLAN DE ACCIÓN E4

### Fase 1: Cambios Críticos (OBLIGATORIOS)

#### 1.1 Actualizar mapeo charge_type
**Archivo:** `generador_templates_fiscal.py:38`
```python
"cantidad": "On Item Quantity",  # Cambio E4
```

#### 1.2 Actualizar tabla maestra (3 roles cuota)
**Archivo:** `reglas_calculo_fiscal.py:164,177,189`
```python
# Cambiar regla_base de "monto_neto" → "cantidad"
(ROL_IEPS_AZU, "cantidad", "cuota", ...)
(ROL_IEPS_COMB, "cantidad", "cuota", ...)
(ROL_IEPS_TABQ, "cantidad", "cuota", ...)
```

#### 1.3 Deprecar hooks que mutan charge_type
**Archivo:** `sales_invoice_ieps.py`

**Funciones a deprecar:**
- `_calcular_y_distribuir_iva_sobre_ieps_cuota()` (líneas ~200-280)
- `corregir_distribucion_ieps_cuota_post_submit()` (líneas ~430-580)

**Hooks a eliminar:**
- `on_save` hook para calcular_ieps_cuota() (parcial - solo charge_type)
- `on_submit` hook para corregir distribución

---

### Fase 2: Mejoras Arquitectónicas (RECOMENDADAS)

#### 2.1 Migrar mapeo a BD (extensibilidad)

**Crear DocType:** "Mapeo Charge Type Fiscal"

**Campos:**
- `regla_base` (Select): monto_neto, cantidad, fila_previa_monto, etc.
- `charge_type_erpnext` (Select): On Net Total, On Item Quantity, etc.
- `habilitado` (Check): Para deprecar sin borrar
- `version` (Data): Control versión SAT
- `notas` (Text): Documentación

**Ventajas:**
- ✅ Configurable vía UI (sin cambios código)
- ✅ Extensible para nuevos charge_types
- ✅ Auditable (track_changes=1)
- ✅ Versionable (rollback configuraciones)

#### 2.2 Centralizar lógica charge_type

**Crear módulo:** `facturacion_mexico/utils/mapeo_charge_type.py`

```python
def obtener_charge_type(regla_base: str) -> str:
    """
    Obtiene charge_type ERPNext desde regla_base.

    Prioridad:
    1. Mapeo en BD (DocType "Mapeo Charge Type Fiscal")
    2. Fallback a diccionario por defecto

    Args:
        regla_base: Regla base desde tabla maestra

    Returns:
        str: charge_type ERPNext
    """
    # Intentar BD primero
    mapeo = frappe.db.get_value(
        "Mapeo Charge Type Fiscal",
        {"regla_base": regla_base, "habilitado": 1},
        "charge_type_erpnext"
    )

    if mapeo:
        return mapeo

    # Fallback a diccionario
    return _MAPEO_CHARGE_TYPE_DEFAULT.get(regla_base, "On Net Total")
```

---

## ✅ CHECKLIST IMPLEMENTACIÓN E4

### Pre-implementación
- [x] Auditoría hardcode completada
- [ ] Backup BD creado
- [ ] Feature branch creado

### Cambios código
- [ ] Actualizar mapeo: "cantidad" → "On Item Quantity"
- [ ] Actualizar tabla maestra: 3 roles cuota
- [ ] Deprecar hooks que mutan charge_type
- [ ] Actualizar comentarios deprecados
- [ ] Regenerar 7 STCT con nueva configuración

### Testing
- [ ] Test unitario: mapeo charge_type correcto
- [ ] Test integración: STCT genera "On Item Quantity"
- [ ] Test funcional: SI con cuotas IEPS (Draft = Submit)
- [ ] Test regresión: IVA cascada permanece "On Previous Row Amount"

### Documentación
- [ ] Actualizar ARQUITECTURA_E4_ON_ITEM_QUANTITY.md
- [ ] Actualizar CHANGELOG.md
- [ ] Crear migration notes (BREAKING CHANGE)

---

## 🚨 RIESGOS IDENTIFICADOS

### Riesgo 1: Incompatibilidad con STCT legacy
**Impacto:** STCT viejos con "On Net Total" no funcionarán
**Mitigación:** Regeneración obligatoria de STCT (7 templates)

### Riesgo 2: Hooks deprecados causan conflictos
**Impacto:** Hooks activos mutan charge_type a "Actual"
**Mitigación:** Deprecar hooks ANTES de regenerar STCT

### Riesgo 3: ITT con cuotas no bloqueadas
**Impacto:** ITT pueden seguir teniendo cuotas IEPS
**Mitigación:** Implementar validador duro (Paso siguiente)

---

**Fecha auditoría:** 2025-10-27
**Estado:** ✅ COMPLETADA
**Siguiente paso:** Implementar cambios Fase 1
