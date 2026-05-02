# REPORTE TÉCNICO: FRACASO IMPLEMENTACIÓN FIX-V2 IEPS CUOTA

**Fecha:** 2025-10-27
**Sistema:** ERPNext + Facturación México
**Objetivo:** Prevenir pérdida cuotas IEPS en Sales Invoice submit
**Resultado:** ❌ **FRACASO COMPLETO - IMPLEMENTACIÓN RECHAZADA**

---

## RESUMEN EJECUTIVO

Se implementó solución completa (8 pasos) basada en propuesta ChatGPT para prevenir que ERPNext pierda las cuotas IEPS al hacer submit de Sales Invoice.

**Resultado:**
- ✅ Draft: Cuotas IEPS presentes ($234.84)
- ❌ Submitted: Cuotas IEPS perdidas ($0.00)
- ❌ Regresión total: Mismo estado que pre-fix
- ❌ Problemas adicionales: STCT desapareció, Outstanding Amount discrepancia

**Decisión:** Implementación NO autorizada - Rollback requerido

---

## ~~🚨 PROBLEMA CRÍTICO #0: OUTSTANDING AMOUNT $8,293 vs $8,021~~ ✅ RESUELTO

### ~~Hallazgo Más Crítico~~ → CONFIRMADO: Era Cache del Browser

**Descripción Original:** Usuario reportó que UI mostraba Outstanding Amount $8,293.00 pero queries directos a la base de datos mostraban $8,021.00.

**ACTUALIZACIÓN:** Usuario confirmó que después de refresh, el UI ahora muestra **$8,021.00** correctamente. El valor $8,293 era cache temporal del momento del submit.

**Evidencia del Usuario:**

```
SCREENSHOT (UI - Captura usuario):
  Outstanding Amount [MXN]: $8,293.00  ← Valor reportado en pantalla

DATABASE (Query SQL directo):
  outstanding_amount:       $8,021.00  ← Valor actual en DB
  grand_total:              $8,020.82
  rounded_total:            $8,021.00
  payment_schedule[0].outstanding: $8,021.00

DISCREPANCIA REPORTADA: $272.00
```

### Investigación Completa

**Timeline del Submit (evidencia Version Document bsgndoa9pm):**

```
18:34:59  DRAFT CREADO
          outstanding_amount: $8,374.00
          grand_total:        $8,374.44
          Cuotas IEPS:        $234.84 (3 filas Actual)

18:42:53  SUBMIT INICIA
          before_submit hook ejecuta:
          - taxes_and_charges → "" (vacío)
          - fm_original_stct_template → "IVA Nacional - IEPS - _TC"

18:42:54  SUBMIT COMPLETA (Version Document captura)
          outstanding_amount: $8,293.00  ← VALOR INTERMEDIO
          grand_total:        $8,020.82
          Cuotas IEPS:        $0.00 (3 filas perdidas)
          docstatus:          1

DESPUÉS   RECALCULO SILENCIOSO (sin Version tracking)
          outstanding_amount: $8,021.00  ← VALOR CORRECTO FINAL
          [No hay Version posterior - cambio no tracked]
```

**Evidencia Version Document:**
- Solo existe 1 Version document (bsgndoa9pm)
- Capturó: `outstanding_amount: "$ 8,374.00" → "$ 8,293.00"`
- El cambio $8,293 → $8,021 NO fue registrado
- Indica recalculo silencioso del sistema post-submit

### Análisis de la Discrepancia $272

**Cuotas IEPS Removidas (según Version Document):**

| Row | Descripción | Draft (OLD) | Submit (NEW) | Perdido |
|-----|-------------|-------------|--------------|---------|
| 4 | IEPS Azúcar - Cuota | charge_type="Actual"<br>tax_amount=$15.24 | charge_type="On Net Total"<br>tax_amount="" (vacío) | -$15.24 |
| 6 | IEPS Combustibles - Cuota | charge_type="Actual"<br>tax_amount=$219.60 | charge_type="On Net Total"<br>tax_amount="" (vacío) | -$219.60 |
| 10 | IEPS Tabaco - Cuota | charge_type="Actual"<br>tax_amount=""<br>after_discount=$70.00 | charge_type="On Net Total"<br>tax_amount=""<br>after_discount="" | -$0.00* |

**Total Cuotas Perdidas:** $234.84
**IVA sobre cuotas (16%):** $37.57
**TOTAL IMPACTO:** $272.41 ≈ $272.00

*Nota: IEPS Tabaco Cuota tenía amount en `after_discount` pero no en `tax_amount`

### Root Cause

**El valor $8,293 es un VALOR INTERMEDIO INCORRECTO que ERPNext calculó durante el submit:**

```
1. Durante submit: ERPNext recalcula taxes
   - Cuotas IEPS → $0.00
   - Grand Total: $8,374.44 → $8,020.82

2. Durante submit: ERPNext calcula outstanding_amount
   - Usa algún valor INTERMEDIO con cuotas parciales
   - Resultado: $8,293.00 (incluye fantasma $272)
   - Version document CAPTURA este valor

3. Post-submit: Sistema recalcula silenciosamente
   - outstanding_amount: $8,293.00 → $8,021.00
   - Cambio NO tracked por Version system
   - DB queda con valor correcto
```

**Fórmula del valor fantasma:**
```
$8,021.00 (Grand Total correcto)
+  $234.84 (Cuotas IEPS que ya no existen)
+   $37.57 (IVA sobre cuotas que ya no existe)
-----------
$8,293.41 → $8,293.00 (valor intermedio capturado)
```

### Diagnóstico: ¿Por qué el usuario VE $8,293?

**3 Posibilidades:**

#### A) CACHE DEL BROWSER (MÁS PROBABLE)
- Browser cargó la página inmediatamente después del submit
- UI mostró el valor $8,293 del momento exacto del Version
- Browser no ha refrescado desde entonces
- **Solución:** Hard refresh (Ctrl+Shift+R) o recargar página

#### B) FRAPPE FORM EN MEMORIA
- Form JavaScript tiene el valor viejo cached
- Form se renderizó ANTES del recalculo silencioso
- **Solución:** Cerrar y reabrir el documento

#### C) BUG JAVASCRIPT CLIENT-SIDE (MENOS PROBABLE)
- JavaScript calculando outstanding con taxes[] array viejo
- Form usando HTML table "Taxes Calculation" con cuotas fantasma
- Bug persistente en cómo Frappe renderiza el campo
- **Esto sería CRÍTICO** - requiere fix en Frappe core

### Scripts de Diagnóstico Ejecutados

**Script 1: Búsqueda exhaustiva $8,293**
```bash
bench --site facturacion.dev execute "facturacion_mexico.one_offs.buscar_8293_todos_campos.run"
```
**Resultado:** ❌ NINGÚN campo en database contiene 8293

**Script 2: Payment Schedule**
```bash
bench --site facturacion.dev execute "facturacion_mexico.one_offs.analizar_payment_schedule.run"
```
**Resultado:** Payment Schedule outstanding = $8,021.00 (correcto)

**Script 3: Version Documents**
```bash
bench --site facturacion.dev execute "facturacion_mexico.one_offs.listar_versiones_01675.run"
```
**Resultado:** Solo 1 Version (bsgndoa9pm), cambio $8,293→$8,021 no tracked

**Script 4: Investigación final**
```bash
bench --site facturacion.dev execute "facturacion_mexico.one_offs.investigacion_final_outstanding.run"
```
**Resultado:** Timeline completa + teoría valor intermedio confirmada

### Impacto Real

**SI el valor $8,293 es CACHE (Escenario A o B):**
- ✅ Impacto: BAJO - Solo problema visual temporal
- ✅ Solución: Hard refresh resuelve el problema
- ✅ DB tiene valor correcto ($8,021)
- ✅ Payment Entries funcionarán correctamente
- ⚠️ Confusión temporal del usuario al ver valores inconsistentes

**SI el valor $8,293 es BUG PERSISTENTE (Escenario C):**
- 🚨 Impacto: CRÍTICO - Bug en Frappe Form rendering
- 🚨 Usuario SIEMPRE verá valor incorrecto
- 🚨 Afecta toma de decisiones de cobro
- 🚨 Requiere fix en código JavaScript client-side
- 🚨 Indica problema profundo en lifecycle UI-DB

### Conclusión Final - PROBLEMA RESUELTO ✅

**Hallazgo Principal:**
El valor $8,293 fue un **valor intermedio incorrecto** que ERPNext calculó durante el submit (evidenciado por Version document), pero que el sistema recalculó silenciosamente a $8,021 (valor correcto en DB).

**Confirmación Usuario:**
- ✅ **Después de refresh:** UI muestra $8,021.00 (CORRECTO)
- ✅ **Confirmado:** Era **Escenario A (Cache del Browser)**
- ✅ **Impacto:** BAJO - Solo fue problema visual temporal
- ✅ **Resolución:** Simple refresh de página resolvió el problema

**Estado Final:**
- ✅ **Base de datos:** $8,021.00 (CORRECTO)
- ✅ **UI del usuario:** $8,021.00 (CORRECTO)
- ✅ **Payment Schedule:** $8,021.00 (CORRECTO)

**Discrepancia Rounding $0.18 (NORMAL):**
```
Grand Total:        $8,020.82
Outstanding Amount: $8,021.00
Diferencia:         $0.18 (rounding_adjustment)
```
Esta discrepancia de $0.18 es **COMPORTAMIENTO NORMAL** de ERPNext que usa `rounded_total` para calcular `outstanding_amount`. No es un bug.

**Criticidad Final:**
- ⚪ **NULA** - Problema resuelto completamente
- ✅ No afecta operaciones de cobro
- ✅ No hay bug JavaScript persistente
- ✅ Sistema funcionando correctamente

**Relación con FIX-V2:**
Este problema del outstanding_amount fue **INDEPENDIENTE** del problema de las cuotas IEPS y ya está RESUELTO. El problema REAL que persiste es la pérdida de cuotas IEPS durante el submit, el cual NO fue resuelto por el FIX-V2.

**Lección Aprendida:**
El Version document captura snapshots en momentos específicos del lifecycle. Los valores pueden cambiar después del submit sin ser tracked. Importante verificar siempre el estado FINAL en la DB, no solo el Version document.

---

## CONTEXTO DEL PROBLEMA

### Problema Original

**Bug ERPNext:** Al hacer submit de Sales Invoice con IEPS Cuota (`charge_type="Actual"`), ERPNext recalcula taxes y:
1. Cambia `charge_type` de "Actual" a "On Net Total"
2. Pone monto de cuotas en $0.00
3. Pierde IVA sobre cuotas
4. Grand Total regresa a valor incorrecto

**Impacto Fiscal:**
- Pérdida cuotas IEPS: -$234.84
- Pérdida IVA sobre cuotas: -$48.78
- Total pérdida: -$283.62
- Discrepancia vs PAC: -$179.28

### Comportamiento Observado

| Estado | Cuotas IEPS | Grand Total | vs PAC |
|--------|-------------|-------------|--------|
| Draft | 3 cuotas = $234.84 | $8,374.44 | +$174.34 |
| **Submit** | **0 cuotas = $0.00** | **$8,020.82** | **-$179.28** |

---

## SOLUCIÓN PROPUESTA (CHATGPT)

### Estrategia: "Opción C - Hybrid Minimal"

**Enfoque:**
1. Neutralizar `taxes_and_charges` en `before_submit` para prevenir reload template
2. Guardar STCT original en campo custom `fm_original_stct_template`
3. Congelar cuotas con `dont_recompute_tax=1`
4. Validar `item_wise_tax_detail` completo
5. Restaurar STCT en `before_validate` para amend/copy

**Guardas ChatGPT aplicadas:**
- Early-exit 99% facturas sin cuotas
- No afectar devoluciones (`is_return`)
- Idempotencia (skip si ya procesado)
- Fallback robusto limitado a IEPS
- Cache request-scoped
- Precisión dinámica

---

## IMPLEMENTACIÓN COMPLETA (8 PASOS)

### PASO 1: Custom Field

**Archivo:** `fixtures/custom_fields_sales_invoice.json`

```json
{
  "fieldname": "fm_original_stct_template",
  "label": "STCT Original (Sistema)",
  "fieldtype": "Data",
  "insert_after": "taxes_and_charges",
  "read_only": 1,
  "no_copy": 0,
  "print_hide": 1,
  "hidden": 0
}
```

**Propósito:** Guardar template original antes de neutralizar `taxes_and_charges`

**Estado:** ✅ Creado y migrado

### PASO 2: Cache Mapeos

**Archivo:** `hooks_handlers/sales_invoice_ieps.py`
**Función:** `_get_mapeos_cache(company: str) -> dict`

```python
def _get_mapeos_cache(company: str) -> dict:
    """Cache request-scoped de mapeos fiscales."""
    if not hasattr(frappe.local, "fm_mapeos_cache"):
        frappe.local.fm_mapeos_cache = {}

    if company not in frappe.local.fm_mapeos_cache:
        config = _obtener_config_fiscal(company)
        cache = {}
        if config:
            for mapeo in config.mapeo_cuentas:
                cache[mapeo.cuenta_impuesto] = {
                    "tipo_factor": mapeo.get("tipo_factor", "Tasa"),
                    "integra_base_iva": bool(mapeo.get("integra_base_iva", 1)),
                    "rol_fiscal": mapeo.rol_fiscal,
                }
        frappe.local.fm_mapeos_cache[company] = cache

    return frappe.local.fm_mapeos_cache[company]
```

**Propósito:** Reducir N queries en loops de tax rows

**Estado:** ✅ Implementado

### PASO 3: Detección Temprana (Early-Exit)

**Función:** `_si_tiene_ieps_cuotas(doc) -> bool`

```python
def _si_tiene_ieps_cuotas(doc) -> bool:
    """Detectar si SI tiene cuotas IEPS."""
    if not doc.taxes:
        return False

    mcache = _get_mapeos_cache(doc.company)

    for tax_row in doc.taxes:
        metadata = mcache.get(tax_row.account_head)

        # Validación dual con fallback acotado a IEPS
        es_cuota_ieps = (
            (metadata and metadata["tipo_factor"] == "Cuota") or
            (tax_row.charge_type == "Actual" and
             metadata and
             metadata.get("rol_fiscal", "").startswith("IEPS"))
        )

        if es_cuota_ieps:
            return True

    return False
```

**Propósito:** Early-exit para 99% facturas sin cuotas (zero overhead)

**Estado:** ✅ Implementado

### PASO 4: Construir item_wise_tax_detail

**Función:** `_construir_item_wise_tax_detail_cuota(doc, tax_row)`

```python
def _construir_item_wise_tax_detail_cuota(doc, tax_row):
    """Construir item_wise_tax_detail JSON válido para cuota IEPS."""
    item_wise = {}
    prec_amount = doc.precision("tax_amount") or 2

    for item in doc.items:
        if _item_contribuye_a_cuenta_ieps(item, tax_row.account_head):
            cuota_data = _get_cuota_prioridad(item, tax_row.account_head, doc)
            if cuota_data:
                cuota_unitaria = cuota_data["cuota"]
                amount_item = flt(item.qty * cuota_unitaria, prec_amount)
                item_wise[item.item_code] = [0.0, amount_item]
            else:
                item_wise[item.item_code] = [0.0, 0.0]
        else:
            item_wise[item.item_code] = [0.0, 0.0]

    tax_row.item_wise_tax_detail = json.dumps(item_wise)
```

**Propósito:** Prevenir recalc tardío con distribución completa por item

**Estado:** ✅ Implementado

### PASO 5: Hook before_submit (CRÍTICO)

**Función:** `congelar_ieps_cuota_submit(doc, method=None)`

```python
def congelar_ieps_cuota_submit(doc, method=None):
    """Hook before_submit: Congelar cuotas IEPS para evitar recálculo."""

    # GUARDA 1: No afectar devoluciones
    if doc.is_return:
        return

    # GUARDA 2: Idempotencia
    if not doc.taxes_and_charges and doc.fm_original_stct_template:
        return

    # EARLY EXIT: 99% facturas sin cuotas
    if not _si_tiene_ieps_cuotas(doc):
        return

    # PASO 1: Guardar template original
    if doc.taxes_and_charges:
        doc.fm_original_stct_template = doc.taxes_and_charges
        doc.taxes_and_charges = ""  # ← NEUTRALIZAR

    # PASO 2: Congelar cuotas
    mcache = _get_mapeos_cache(doc.company)

    for tax_row in doc.taxes:
        metadata = mcache.get(tax_row.account_head)

        es_cuota_ieps = (
            (metadata and metadata["tipo_factor"] == "Cuota") or
            (tax_row.charge_type == "Actual" and
             metadata and
             metadata.get("rol_fiscal", "").startswith("IEPS"))
        )

        if not es_cuota_ieps:
            continue

        # GUARDA 3: No tocar IVA cascada
        if tax_row.charge_type not in ["Actual", "On Net Total"]:
            continue

        # Congelar cuota
        if tax_row.dont_recompute_tax != 1:
            tax_row.dont_recompute_tax = 1
            tax_row.included_in_print_rate = 0

        # Validar item_wise_tax_detail
        if not tax_row.item_wise_tax_detail or tax_row.item_wise_tax_detail == "{}":
            _construir_item_wise_tax_detail_cuota(doc, tax_row)
```

**Propósito:** Prevenir pérdida cuotas en submit

**Estado:** ✅ Implementado, ❌ **NO FUNCIONA**

### PASO 6: Hook before_validate

**Función:** `restaurar_stct_original(doc, method=None)`

```python
def restaurar_stct_original(doc, method=None):
    """Hook before_validate: Restaurar taxes_and_charges desde fm_original_stct_template."""
    if doc.is_return:
        return

    if doc.fm_original_stct_template and not doc.taxes_and_charges:
        doc.taxes_and_charges = doc.fm_original_stct_template
```

**Propósito:** Restaurar STCT en amend/copy para UI consistente

**Estado:** ✅ Implementado

### PASO 7: Registrar Hooks

**Archivo:** `hooks.py`

```python
"Sales Invoice": {
    "before_validate": [
        "facturacion_mexico.hooks_handlers.sales_invoice_ieps.restaurar_stct_original",  # PRIMERO
        "facturacion_mexico.hooks_handlers.sales_invoice_automated_tax.before_validate",  # SEGUNDO
    ],
    "validate": "facturacion_mexico.hooks_handlers.sales_invoice_automated_tax.validate",
    "before_save": [
        "facturacion_mexico.hooks_handlers.sales_invoice_ieps.calcular_ieps_cuota",
        "facturacion_mexico.hooks_handlers.sales_invoice_ieps.ajustar_base_iva_combustibles",
        "facturacion_mexico.hooks_handlers.sales_invoice_ieps.corregir_ieps_cuota_final",
    ],
    "before_submit": "facturacion_mexico.hooks_handlers.sales_invoice_ieps.congelar_ieps_cuota_submit",
},
```

**Estado:** ✅ Registrado

### PASO 8: Precisión Dinámica

**Cambios:** 4 ubicaciones reemplazando `flt(..., 2)` por `flt(..., prec)`

**Ubicaciones:**
1. `calcular_ieps_cuota()` - tax_amount
2. `calcular_ieps_cuota()` - distribucion_items
3. `corregir_ieps_cuota_final()` - tax_amount
4. `corregir_ieps_cuota_final()` - distribucion_correcta

**Estado:** ✅ Implementado

---

## RESULTADOS TESTING

### Test Case: ACC-SINV-2025-01675

**Setup:**
- 4 items (Alcohol, Azúcar/Bebidas, Combustibles, Tabaco)
- 3 cuotas IEPS (Azúcar, Combustibles, Tabaco)
- STCT: "IVA Nacional - IEPS - _TC"

### Draft (On Save) - ✅ FUNCIONA

**Totales:**
```
Net Total:     $5,240.00
Total Taxes:   $3,134.44
Grand Total:   $8,374.44
vs PAC:        +$174.34 (+2.1%)
```

**Cuotas IEPS:**
```
✅ IEPS Azúcar/Bebidas:  $15.24   (charge_type="Actual", dont_recompute_tax=1)
✅ IEPS Combustibles:    $219.60  (charge_type="Actual", dont_recompute_tax=1)
✅ IEPS Tabaco:          $0.00    (charge_type="Actual", dont_recompute_tax=1)

Total Cuotas: $234.84
```

**Campos:**
```
taxes_and_charges:         "IVA Nacional - IEPS - _TC" ✅
fm_original_stct_template: (vacío) ✅
```

### Submitted (Post Submit) - ❌ FRACASO TOTAL

**Totales:**
```
Net Total:           $5,240.00
Total Taxes:         $2,780.82  ← Perdió $353.62 ❌
Grand Total:         $8,020.82  ← Regresión total ❌
Outstanding Amount:  $8,021.00  ← Discrepancia +$0.18 ⚠️
vs PAC:              -$179.28   ← Fuera tolerancia ❌
```

**Cuotas IEPS:**
```
❌ IEPS Azúcar/Bebidas:  $0.00    (charge_type="On Net Total" - cambió)
❌ IEPS Combustibles:    $0.00    (charge_type="On Net Total" - cambió)
❌ IEPS Tabaco:          $0.00    (charge_type="On Net Total" - cambió)

Total Cuotas: $0.00  ← PÉRDIDA TOTAL -$234.84
```

**Campos:**
```
taxes_and_charges:         (VACÍO) ❌ Desapareció
fm_original_stct_template: "IVA Nacional - IEPS - _TC" ✅
```

### Comparación Draft → Submitted

| Métrica | Draft | Submitted | Cambio |
|---------|-------|-----------|--------|
| Total Taxes | $3,134.44 | $2,780.82 | **-$353.62** ❌ |
| Grand Total | $8,374.44 | $8,020.82 | **-$353.62** ❌ |
| Cuotas | 3 ($234.84) | 0 ($0.00) | **-3 cuotas** 🚨 |
| IVA sobre cuotas | $48.78 | $0.00 | **-$48.78** ❌ |
| taxes_and_charges | Presente | **VACÍO** | Desapareció ❌ |

---

## ANÁLISIS ROOT CAUSE

### Por qué falló la implementación

**1. Hook before_submit SÍ se ejecutó:**

Evidencia:
- `taxes_and_charges` → vacío (línea 926 ejecutada)
- `fm_original_stct_template` → guardado (línea 925 ejecutada)

**2. PERO ERPNext recalculó DESPUÉS:**

Orden de ejecución real en Frappe:
```python
# frappe/model/document.py líneas 1142-1144
elif self._action == "submit":
    self.run_method("validate")      # ← Ejecuta DESPUÉS de before_submit
    self.run_method("before_submit") # ← Nuestro hook (ejecuta primero)
```

**PROBLEMA:** ERPNext ejecuta hooks en orden:
```
1. before_submit   ← Nuestro hook congela cuotas
2. validate()      ← ERPNext core RECALCULA TODO
3. on_submit       ← Demasiado tarde
```

**3. ERPNext `validate()` sobrescribe TODO:**

En `validate()` ERPNext llama:
- `calculate_taxes_and_totals()` → Recalcula taxes
- `set_taxes_and_charges()` → Reload desde template (PERO está vacío)
- ITT override → Sobrescribe values

**4. dont_recompute_tax=1 fue IGNORADO:**

ERPNext recalcula taxes independientemente de `dont_recompute_tax` durante:
- `calculate_taxes_and_totals()`
- ITT (Item Tax Template) override
- `charge_type` redistribution

**5. taxes_and_charges vacío causó problemas adicionales:**

- STCT desapareció de UI
- Usuario pierde trazabilidad
- Inconsistencia con ERPNext UX estándar

---

## PROBLEMAS CRÍTICOS IDENTIFICADOS

### PROBLEMA #1: Outstanding Amount Discrepancia

**Síntoma:**
```
Grand Total UI:      $8,020.82
Outstanding Amount:  $8,021.00
Diferencia:          $0.18
```

**Causa:**
- ERPNext aplicó `rounding_adjustment` automático
- `rounded_total` = $8,021.00
- `outstanding_amount` usa `rounded_total`
- UI muestra `grand_total` (sin rounding)

**GL Entries confirma:**
```
Total Credit: $8,021.00  (usa rounded_total)
```

**Implicación:**
- MISMO DOCUMENTO con DOS totales diferentes
- Inconsistencia contable inadmisible
- Confusión usuario

### PROBLEMA #2: Hooks Inefectivos

**Síntoma:**
- Hook `congelar_ieps_cuota_submit()` SÍ se ejecutó
- Cuotas SÍ fueron congeladas con `dont_recompute_tax=1`
- PERO cuotas se perdieron después de submit

**Causa:**
- ERPNext `validate()` corre DESPUÉS de `before_submit`
- `calculate_taxes_and_totals()` ignora `dont_recompute_tax`
- ITT sobrescribe todo

**Implicación:**
- Hooks `before_submit` NO pueden prevenir recálculo
- Necesitamos hook DESPUÉS de `validate()`
- No existe tal hook en ERPNext estándar

### PROBLEMA #3: STCT Desapareció

**Síntoma:**
- Campo `taxes_and_charges` vacío en submitted
- Usuario no puede ver qué template se usó

**Causa:**
- Neutralizamos `taxes_and_charges` para prevenir reload
- `fm_original_stct_template` guardó el valor PERO:
  - Campo oculto/técnico
  - No visible en form estándar

**Implicación:**
- Pérdida trazabilidad fiscal
- Inconsistencia con UX ERPNext
- Usuario confundido

### PROBLEMA #4: Regresión Total

**Síntoma:**
- FIX-V2 Submitted = FIX-V1 Submitted = Estado Pre-Fix
- CERO mejora

**Causa:**
- Hooks no previenen recálculo ERPNext
- ERPNext sobrescribe todos nuestros cambios

**Implicación:**
- Implementación completa INÚTIL
- 8 pasos de código sin beneficio
- Problemas adicionales introducidos

---

## CONCLUSIONES TÉCNICAS

### Lo que SÍ funciona

1. ✅ **Draft (on save):**
   - `doc.calculate_taxes_and_totals()` incluye cuotas
   - `dont_recompute_tax=1` funciona
   - `charge_type="Actual"` preservado

2. ✅ **Hooks ejecutan:**
   - `congelar_ieps_cuota_submit()` SÍ corre
   - `taxes_and_charges` SÍ se neutraliza
   - `fm_original_stct_template` SÍ se guarda

3. ✅ **Early-exit:**
   - 99% facturas sin cuotas: zero overhead
   - Performance óptima

### Lo que NO funciona

1. ❌ **Hook before_submit inefectivo:**
   - ERPNext recalcula DESPUÉS del hook
   - `dont_recompute_tax=1` ignorado
   - Cuotas se pierden

2. ❌ **Neutralizar taxes_and_charges problemático:**
   - STCT desaparece de UI
   - Pérdida trazabilidad
   - Inconsistencia UX

3. ❌ **Outstanding Amount discrepancia:**
   - Rounding inconsistente
   - Dos totales diferentes
   - Problema contable

### Por qué la solución ChatGPT falló

**Asunciones incorrectas:**

1. **"Hook before_submit previene recálculo"**
   - FALSO: ERPNext ejecuta `validate()` DESPUÉS
   - `validate()` sobrescribe todo

2. **"dont_recompute_tax=1 congela tax row"**
   - PARCIALMENTE FALSO: Solo en draft
   - En submit, ERPNext ignora flag

3. **"taxes_and_charges vacío previene reload"**
   - CIERTO: Previene reload
   - PERO causa problemas UI y trazabilidad

4. **"Solución minimal sin modificar core"**
   - FALSO: Modificamos comportamiento visible
   - STCT desapareció - inaceptable

---

## ALTERNATIVAS NO EXPLORADAS

### Opción A: Hook on_submit (Post-Submit Fix)

**Enfoque:**
- No prevenir recálculo, CORREGIR después
- En `on_submit`, recalcular cuotas y actualizar doc
- Usar `db_set()` para persistir cambios

**Pros:**
- Corre DESPUÉS de todos los recálculos
- No modifica comportamiento visible

**Contras:**
- Posible desincronización con GL Entries
- Requiere recalcular GL Entries también
- Más complejo

### Opción B: Override Sales Invoice.submit()

**Enfoque:**
- Clase Python override de Sales Invoice
- Interceptar método `submit()` completo
- Inyectar lógica después de `validate()`

**Pros:**
- Control total del flujo
- Puede prevenir recálculo

**Contras:**
- Altamente invasivo
- Riesgo alto de breaking changes
- Mantenimiento complejo

### Opción C: Modificar ITT (Item Tax Template)

**Enfoque:**
- Investigar por qué ITT sobrescribe cuotas
- Modificar lógica ITT para respetar cuotas

**Pros:**
- Ataca root cause
- Solución más limpia

**Contras:**
- Requiere investigación profunda ERPNext core
- Posible modificación core ERPNext

### Opción D: Custom DocType para Cuotas

**Enfoque:**
- Crear DocType separado "IEPS Cuota"
- No usar `taxes` child table
- Calcular Grand Total manualmente

**Pros:**
- Independiente de lógica ERPNext taxes
- Control total

**Contras:**
- Rompe integración ERPNext
- Requiere reescribir mucha lógica
- GL Entries complejos

---

## RECOMENDACIONES

### Inmediato

1. **ROLLBACK de FIX-V2:**
   - Revertir cambios en `sales_invoice_ieps.py`
   - Revertir cambios en `hooks.py`
   - Eliminar custom field `fm_original_stct_template`
   - Regresar a estado pre-FIX-V2

2. **Investigación Profunda:**
   - Analizar ERPNext `calculate_taxes_and_totals()` source
   - Identificar DÓNDE y CUÁNDO cuotas se pierden
   - Revisar ITT (Item Tax Template) logic

3. **Consulta ERPNext Community:**
   - Reportar bug en Frappe/ERPNext GitHub
   - Buscar si otros tienen mismo problema
   - Revisar si existe workaround oficial

### Mediano Plazo

1. **Evaluar Opción A (on_submit):**
   - Prototipar solución post-submit fix
   - Verificar compatibilidad GL Entries
   - Testing exhaustivo

2. **Evaluar Opción C (ITT investigation):**
   - Deep dive ERPNext ITT logic
   - Identificar si modificable sin fork
   - Proponer patch upstream si posible

### Largo Plazo

1. **Considerar Custom DocType:**
   - Si ninguna solución hooks funciona
   - Diseñar arquitectura alternativa
   - Evaluar costo/beneficio vs ERPNext fork

---

## ARCHIVOS MODIFICADOS (REQUIEREN ROLLBACK)

```
facturacion_mexico/fixtures/custom_fields_sales_invoice.json  (líneas 109-128)
facturacion_mexico/hooks_handlers/sales_invoice_ieps.py       (líneas 64-982)
facturacion_mexico/hooks.py                                   (líneas 343-353)
```

---

## LECCIONES APRENDIDAS

1. **Hooks before_submit NO previenen recálculo ERPNext:**
   - Orden ejecución: before_submit → validate() → on_submit
   - Recálculo ocurre en `validate()` DESPUÉS de before_submit

2. **dont_recompute_tax no es absoluto:**
   - Solo funciona en draft/save
   - ERPNext ignora en submit bajo ciertas condiciones

3. **Modificar campos core (taxes_and_charges) tiene consecuencias:**
   - UI inconsistente
   - Pérdida trazabilidad
   - Usuario confundido

4. **Soluciones "minimal" pueden no ser minimal:**
   - Parece simple neutralizar campo
   - PERO tiene efectos colaterales

5. **Testing Draft NO predice Submit:**
   - Draft funcionó perfecto
   - Submit falló totalmente
   - Necesitamos tests E2E completos

---

## DECISIÓN FINAL USUARIO

**❌ IMPLEMENTACIÓN RECHAZADA**

**Razones:**
1. Hooks NO previenen pérdida cuotas (objetivo principal fallido)
2. Modificación comportamiento ERPNext inaceptable (STCT desapareció)
3. Discrepancia Outstanding Amount inadmisible (problema contable)
4. Regresión total sin mejora vs estado inicial
5. Introduce nuevos problemas sin resolver original

**Status:** ROLLBACK REQUERIDO

**Próximos Pasos:**
1. Discutir reporte técnico con ChatGPT
2. Explorar alternativas (Opción A, C, D)
3. Considerar consulta ERPNext community
4. Evaluar costo/beneficio soluciones complejas

---

**Preparado por:** Claude (Sonnet 4.5)
**Para discusión con:** ChatGPT
**Fecha:** 2025-10-27
