# REPORTE: COMPARACIÓN SALES INVOICES vs PAC

**Fecha:** 2025-10-26
**FFM Referencia:** FFMX-2025-00169
**PAC Target:** $8,200.10

---

## TABLA COMPARATIVA SALES INVOICES

| SI Name | Estado | # Taxes | Net Total | Total Taxes | Grand Total | vs PAC | Problema |
|---------|--------|---------|-----------|-------------|-------------|--------|----------|
| **PAC FFMX-2025-00169** | Target | - | - | - | **$8,200.10** | - | - |
| **ACC-SINV-2025-01644** | PRE-FIX (Draft) | 6 | $4,935.16 | $1,143.24 | **$6,078.40** | -$2,121.70 (-25.9%) | IEPS Tasa = $0, sin IVA cascada |
| **ACC-SINV-2025-01668** | POST-FIX (Draft) | 11 | $5,240.00 | $2,780.82* | **$8,020.82*** | -$179.28 (-2.2%) | Bug ERPNext: cuotas IEPS excluidas |
| **ACC-SINV-2025-01668** | Draft (Real) | 11 | $5,240.00 | $3,015.66 | **$8,254.66** | +$54.56 (+0.7%) | Suma manual correcta (incluye cuotas) |
| **ACC-SINV-2025-01668** | SUBMITTED | 11 | $5,240.00 | $2,780.82 | **$8,020.82** | -$179.28 (-2.2%) | 🚨 Cuotas IEPS = $0 post-submit |
| **ACC-SINV-2025-01669** | Draft | 11 | $5,240.00 | $2,780.82* | **$8,020.82** | -$179.28 (-2.2%) | 3 cuotas Actual con valores |
| **ACC-SINV-2025-01669** | SUBMITTED | 11 | $5,240.00 | $2,780.82 | **$8,020.82** | -$179.28 (-2.2%) | 🚨 0 cuotas Actual, charge_type cambió |

**Notas:**
- *ERPNext excluye `charge_type: "Actual"` de totales (-$234.84)
- Cuotas IEPS: Azúcar $15.24 + Combustibles $219.60 = $234.84

---

## DESGLOSE POR SALES INVOICE

### SI ACC-SINV-2025-01644 (PRE-FIX) - 6 filas

| # | Descripción | charge_type | rate | Monto |
|---|-------------|-------------|------|------:|
| 1 | IVA Nacional - Base (Resto) | On Net Total | 16.0% | $838.40 |
| 2 | IEPS Alcohol - Tasa (via ITT) | On Net Total | 0.0% | **$0.00** |
| 3 | IEPS Azúcar/Bebidas - Cuota | Actual | Cuota | $15.24 |
| 4 | IEPS Combustibles - Cuota | Actual | Cuota | $219.60 |
| 5 | IEPS Tabaco - Tasa (via ITT) | On Net Total | 0.0% | **$0.00** |
| 6 | IEPS Tabaco - Cuota | Actual | Cuota | $70.00 |

**Totales:**
- Net Total: $4,935.16
- IVA: $838.40
- IEPS: $304.84 (solo cuota, tasa = $0)
- Total Taxes: $1,143.24
- **Grand Total: $6,078.40**

**Problema:** IEPS Tasa en $0, falta IVA cascada sobre IEPS

---

### SI ACC-SINV-2025-01668 (POST-FIX) - 11 filas

| # | Descripción | Type | Rate | Monto |
|---|-------------|------|------|------:|
| 1 | IVA Nacional - Base (Resto) | On Net Total | 16% | $838.40 |
| 2 | IEPS Alcohol - Tasa (via ITT) | On Net Total | 26.5% | $874.50 |
| 3 | IVA sobre IEPS Alcohol | On Previous Row Amount | 16% | $139.92 |
| 4 | IEPS Azúcar/Bebidas - Cuota | Actual | Cuota | $15.24 |
| 5 | IVA sobre IEPS Azúcar | On Previous Row Amount | 16% | $0.00 |
| 6 | IEPS Combustibles - Cuota | Actual | Cuota | $219.60 |
| 7 | IVA sobre IEPS Combustibles | On Previous Row Amount | 16% | $0.00 |
| 8 | IEPS Tabaco - Tasa (via ITT) | On Net Total | 160% | $800.00 |
| 9 | IVA sobre IEPS Tabaco (Tasa) | On Previous Row Amount | 16% | $128.00 |
| 10 | IEPS Tabaco - Cuota | Actual | Cuota | $0.00 |
| 11 | IVA sobre IEPS Tabaco (Cuota) | On Previous Row Amount | 16% | $0.00 |

**Totales (ERPNext):**
- Net Total: $5,240.00
- Total Taxes: $2,780.82 (excluye cuotas)
- **Grand Total: $8,020.82**

**Totales (Suma Manual):**
```
  $838.40  (IVA Base)
+ $874.50  (IEPS Alcohol Tasa)
+ $139.92  (IVA sobre Alcohol)
+ $15.24   (IEPS Azúcar Cuota)
+ $0.00    (IVA sobre Azúcar)
+ $219.60  (IEPS Combustibles Cuota)
+ $0.00    (IVA sobre Combustibles)
+ $800.00  (IEPS Tabaco Tasa)
+ $128.00  (IVA sobre Tabaco Tasa)
+ $0.00    (IEPS Tabaco Cuota)
+ $0.00    (IVA sobre Tabaco Cuota)
─────────
= $3,015.66  Total Taxes Real
+ $5,240.00  Net Total
─────────
= $8,254.66  Grand Total Real
```

**Discrepancia:**
- ERPNext total_taxes: $2,780.82
- Suma manual taxes: $3,015.66
- **Diferencia: $234.84** (las 2 cuotas IEPS)

**Bug ERPNext:** charge_type "Actual" excluido de totales

---

### SI ACC-SINV-2025-01668 (SUBMITTED) - 11 filas

**🚨 PROBLEMA CRÍTICO DETECTADO: Cuotas IEPS se volvieron $0 al hacer submit**

| # | Descripción | Type | Rate | Monto DRAFT | Monto SUBMITTED | Cambio |
|---|-------------|------|------|------------:|----------------:|--------|
| 1 | IVA Nacional - Base (Resto) | On Net Total | 16% | $838.40 | $838.40 | = |
| 2 | IEPS Alcohol - Tasa (via ITT) | On Net Total | 26.5% | $874.50 | $874.50 | = |
| 3 | IVA sobre IEPS Alcohol | On Previous Row Amount | 16% | $139.92 | $139.92 | = |
| 4 | IEPS Azúcar/Bebidas - Cuota | On Net Total | Cuota | **$15.24** | **$0.00** | **-$15.24** ❌ |
| 5 | IVA sobre IEPS Azúcar | On Previous Row Amount | 16% | $0.00 | $0.00 | = |
| 6 | IEPS Combustibles - Cuota | On Net Total | Cuota | **$219.60** | **$0.00** | **-$219.60** ❌ |
| 7 | IVA sobre IEPS Combustibles | On Previous Row Amount | 16% | $0.00 | $0.00 | = |
| 8 | IEPS Tabaco - Tasa (via ITT) | On Net Total | 160% | $800.00 | $800.00 | = |
| 9 | IVA sobre IEPS Tabaco (Tasa) | On Previous Row Amount | 16% | $128.00 | $128.00 | = |
| 10 | IEPS Tabaco - Cuota | Actual | Cuota | $0.00 | $0.00 | = |
| 11 | IVA sobre IEPS Tabaco (Cuota) | On Previous Row Amount | 16% | $0.00 | $0.00 | = |

**Totales SUBMITTED:**
- Net Total: $5,240.00
- Total Taxes: $2,780.82
- **Grand Total: $8,020.82**

**Análisis del problema:**
```
DRAFT (antes submit):
  IEPS Azúcar Cuota:        $15.24
  IEPS Combustibles Cuota: $219.60
                           ────────
  Total cuotas:            $234.84

SUBMITTED (después submit):
  IEPS Azúcar Cuota:        $0.00  ❌
  IEPS Combustibles Cuota:  $0.00  ❌
                           ────────
  Total cuotas:             $0.00  ❌

PÉRDIDA AL HACER SUBMIT:   -$234.84
```

**Observaciones:**
1. Las filas 4 y 6 cambiaron `charge_type` de "Actual" a "On Net Total"
2. Los montos de cuotas se volvieron $0.00
3. El `description` ahora muestra "(via ITT)" indicando que ITT sobrescribió
4. La suma manual ahora coincide con ERPNext ($2,780.82) porque las cuotas desaparecieron

**Conclusión:**
- ❌ Al hacer submit, hooks `before_submit` o `on_submit` recalculan taxes
- ❌ ITT sobrescribe completamente las filas de cuotas IEPS
- ❌ Se pierden los valores calculados por hooks `before_save` (corregir_ieps_cuota_final)
- 🚨 **Grand Total post-submit aún más lejos del PAC: -$179.28 + pérdida de $234.84**

---

## PROBLEMA IDENTIFICADO Y FIX IMPLEMENTADO

### Root Cause

**Archivo:** `sales_invoice_automated_tax.py`
**Función:** `_set_stct_by_branch()`
**Línea problemática:** 206 (versión pre-fix)

```python
# CÓDIGO PROBLEMÁTICO (antes del fix):
if getattr(doc, "taxes_and_charges", None) != stct:  # ← CONDICIÓN RESTRICTIVA
    doc.taxes_and_charges = stct
    doc.set("taxes", [])          # ← Solo si cambia
    tax_rows = get_taxes_and_charges("Sales Taxes and Charges Template", stct)
    doc.extend("taxes", tax_rows)
```

**Problema:** Solo cargaba taxes del STCT cuando `taxes_and_charges` **cambiaba** de valor.

### Secuencia del Fallo

1. Usuario crea SI → Hook autoselecciona "IVA Nacional - IEPS - _TC"
2. `doc.taxes_and_charges` cambia → Condición TRUE → Carga 11 taxes ✓
3. Usuario guarda y **recarga** SI
4. Hook ejecuta nuevamente → `doc.taxes_and_charges` YA ES "IVA Nacional - IEPS - _TC"
5. Condición FALSE → **NO recarga** taxes
6. ERPNext prioriza ITT → **Limpia STCT y solo carga ITT**
7. Resultado: **4 filas solo IEPS, sin IVA** ❌

### Solución Implementada

**Archivo:** `sales_invoice_automated_tax.py`
**Función:** `_set_stct_by_branch()`
**Líneas modificadas:** 207-226

```python
# CÓDIGO CORREGIDO (después del fix):
if stct:
    # Flag para evitar múltiples cargas en mismo request
    if getattr(doc.flags, "__stct_applied", False):
        return

    # Asignar STCT encontrado
    if getattr(doc, "taxes_and_charges", None) != stct:
        doc.taxes_and_charges = stct

    # FORZAR carga de taxes desde STCT (incluso si ya estaba asignado)
    # Esto replica comportamiento "STCT disabled → enabled" que funciona correctamente
    from erpnext.controllers.accounts_controller import get_taxes_and_charges

    doc.set("taxes", [])          # ← SIEMPRE limpia
    tax_rows = get_taxes_and_charges("Sales Taxes and Charges Template", stct)
    doc.extend("taxes", tax_rows) # ← SIEMPRE carga

    # Marcar que ya aplicamos STCT en este request
    doc.flags.__stct_applied = True
```

**Cambios clave:**
1. Flag `__stct_applied` para evitar duplicados en mismo request
2. Carga de taxes FUERA del if condicional → **SIEMPRE ejecuta**
3. Replica comportamiento "STCT disabled → enabled" sin necesitar disabled

---

## CÓDIGO MODIFICADO - RENGLÓN POR RENGLÓN

### Contexto del Cambio

**Archivo:** `facturacion_mexico/hooks_handlers/sales_invoice_automated_tax.py`
**Función:** `_set_stct_by_branch(doc, branch)`
**Hook:** `before_validate` en Sales Invoice
**Total cambios:** +7 líneas, 3 movidas

### Código Anotado

#### Líneas 207-210: Guard Clause con Flag

```python
207  if stct:  # STCT encontrado (específico o fallback)
208      # Flag para evitar múltiples cargas en mismo request
209      if getattr(doc.flags, "__stct_applied", False):
210          return
```

**Línea 209: NEW - Verificar flag de control**
- `doc.flags`: Objeto transitorio que NO persiste en DB
- `__stct_applied`: Flag privado (doble underscore)
- `getattr(..., False)`: Retorna False si no existe (primera vez)
- **Razón:** Hook puede ejecutar varias veces en mismo request

**Línea 210: Salida temprana**
- Si flag = True → Ya cargamos taxes → Salir sin recargar
- **Beneficio:** Performance + evita duplicados

#### Líneas 213-214: Asignación Condicional (Sin cambios)

```python
213      if getattr(doc, "taxes_and_charges", None) != stct:
214          doc.taxes_and_charges = stct
```

**Sin cambios del fix**
- Solo asigna si cambió (evita triggerar onChange innecesario)

#### Líneas 216-218: Comentarios Explicativos del Fix

```python
216      # FORZAR carga de taxes desde STCT (incluso si ya estaba asignado)
217      # Esto replica comportamiento "STCT disabled → enabled" que funciona correctamente
218      from erpnext.controllers.accounts_controller import get_taxes_and_charges
```

**Líneas 216-217: NEW - Documentación del fix**
- Explica QUÉ hace (forzar carga siempre)
- Explica POR QUÉ funciona (replica disabled→enabled)

**Línea 218: Import función nativa ERPNext**
- **Crítico:** NO modificamos ERPNext, usamos su función
- `get_taxes_and_charges()` copia TODOS los campos del template
- Import local (lazy loading)

#### Líneas 221-223: Carga INCONDICIONAL (FIX CRÍTICO)

```python
221      doc.set("taxes", [])
222      tax_rows = get_taxes_and_charges("Sales Taxes and Charges Template", stct)
223      doc.extend("taxes", tax_rows)
```

**Línea 221: MOVED - SIEMPRE limpia**
- **ANTES:** Dentro del if línea 213 → Solo si cambiaba
- **DESPUÉS:** FUERA del if → **SIEMPRE ejecuta**
- **Efecto:** Limpia taxes existentes antes de cargar fresh

**Línea 222: MOVED - SIEMPRE carga**
- **ANTES:** Dentro del if → Solo si cambiaba
- **DESPUÉS:** FUERA del if → **SIEMPRE ejecuta**
- **Retorna:** List[dict] con 11 tax rows del STCT

**Línea 223: MOVED - SIEMPRE agrega**
- **ANTES:** Dentro del if → Solo si cambiaba
- **DESPUÉS:** FUERA del if → **SIEMPRE ejecuta**
- **Efecto:** Agrega 11 filas a `doc.taxes`

**⚠️ ESTE ES EL FIX:** Carga taxes SIEMPRE, no solo cuando cambia.

#### Líneas 225-226: Marcar Flag

```python
225      # Marcar que ya aplicamos STCT en este request
226      doc.flags.__stct_applied = True
```

**Línea 226: NEW - Establecer flag**
- Coordina con guard clause línea 209
- **Efecto:** Próxima ejecución en MISMO request saldrá temprano
- **Transitorio:** No persiste entre requests (cada request recarga fresh)

### Resumen Lógica del Fix

**ANTES (Problemático):**
```python
if stct:
    if doc.taxes_and_charges != stct:  # ← Solo si cambia
        doc.taxes_and_charges = stct
        doc.set("taxes", [])           # ← Solo si cambia
        tax_rows = get_taxes_and_charges(...)
        doc.extend("taxes", tax_rows)
```

**DESPUÉS (Correcto):**
```python
if stct:
    if getattr(doc.flags, "__stct_applied", False):  # ← NEW: Guard
        return

    if doc.taxes_and_charges != stct:
        doc.taxes_and_charges = stct

    doc.set("taxes", [])               # ← MOVED: SIEMPRE
    tax_rows = get_taxes_and_charges(...)
    doc.extend("taxes", tax_rows)
    doc.flags.__stct_applied = True   # ← NEW: Marcar
```

**Por qué funciona:**

1. **Flag evita duplicados:** Guard clause previene múltiples cargas en mismo request
2. **Carga SIEMPRE:** Limpia + carga ejecuta incluso si STCT ya estaba asignado
3. **Replica disabled→enabled:** Proceso ERPNext que funcionaba se replica sin necesitar disabled
4. **Taxes antes de cálculo:** STCT taxes presentes ANTES de que ERPNext ejecute su flujo
5. **ITT actualiza:** ITT actualiza tasas sobre estructura existente del STCT
6. **Resultado:** 11 filas (STCT structure + ITT rates) ✅

---

## ANÁLISIS BUGS ERPNEXT

### Bug #1: charge_type "Actual" excluido de totales (Draft)

**Problema:** ERPNext excluye `charge_type: "Actual"` del cálculo `total_taxes_and_charges`

**Evidencia (Draft):**
- IEPS Azúcar Cuota (Actual): $15.24 ← No sumado
- IEPS Combustibles Cuota (Actual): $219.60 ← No sumado
- **Total excluido: $234.84**

**Impacto Draft:**
- Suma manual taxes: $3,015.66
- ERPNext total_taxes: $2,780.82
- Grand Total ERPNext: $8,020.82 (falta $234.84)
- Grand Total Real: $8,254.66

### Bug #2: Cuotas IEPS se vuelven $0 al hacer submit (CRÍTICO)

**Problema:** Al hacer submit, hooks recalculan taxes y ITT sobrescribe cuotas IEPS con $0

**Evidencia (Submit):**
```
DRAFT → SUBMITTED:
  IEPS Azúcar Cuota:        $15.24 → $0.00  (-$15.24) ❌
  IEPS Combustibles Cuota: $219.60 → $0.00  (-$219.60) ❌
                           ────────────────────────────
  Total perdido:           $234.84
```

**Root Cause:**
1. Hooks `before_submit` o `on_submit` recalculan taxes
2. ITT sobrescribe completamente las filas de cuotas
3. Valores calculados por `corregir_ieps_cuota_final` se pierden
4. charge_type cambia de "Actual" a "On Net Total"

**Impacto Submit:**
- Draft Grand Total: $8,020.82 (ya incorrecto por Bug #1)
- Submitted Grand Total: $8,020.82 (mismo, pero ahora cuotas = $0)
- **Cuotas IEPS completamente perdidas en documento submitted**

### Comparación vs PAC

| Estado | Grand Total | vs PAC Target ($8,200.10) |
|--------|-------------|---------------------------|
| Draft (Real suma manual) | $8,254.66 | +$54.56 (+0.7%) |
| Draft (ERPNext bug) | $8,020.82 | -$179.28 (-2.2%) |
| **Submitted (cuotas = $0)** | **$8,020.82** | **-$179.28 (-2.2%)** ❌ |

**Impacto Fiscal:**
- ❌ Grand Total incorrecto en documento submitted
- ❌ FFM usará valor incorrecto para timbrado
- ❌ No coincidirá con cálculo correcto del PAC
- 🚨 **BLOQUEANTE para commit E1**

---

## PRÓXIMOS PASOS

**CRÍTICO:**
1. Investigar código ERPNext (`erpnext/controllers/taxes_and_totals.py`)
2. Implementar workaround en hook `before_save` para sumar cuotas manualmente
3. Validar grand_total correcto

**Pendiente:**
1. Validar con items exactos de FFM FFMX-2025-00169
2. Ajustar diferencia residual +$54.56 si necesario
3. Tests y commit E1
