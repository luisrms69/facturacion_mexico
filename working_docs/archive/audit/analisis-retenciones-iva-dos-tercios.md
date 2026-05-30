# Análisis: Retenciones IVA - Regla de Dos Tercios

**Fecha:** 2025-10-08
**Contexto:** E3 Retenciones - Validación normativa
**Investigación:** Regla 2/3 IVA retenido vs IVA trasladado

---

## 🔍 Pregunta de Investigación

**Usuario pregunta:**
1. ¿El 10.67% cambia para retenciones de IVA en algún caso?
2. ¿Tiene sentido tener ese campo si siempre es 2/3 del IVA?
3. ¿Podemos hacerlo dependiente del IVA realmente cobrado?

---

## 📚 Fundamento Legal

### Ley del IVA (LIVA)

**Artículo 1-A, Fracción II, inciso a):**
> Las personas morales que reciban servicios personales independientes, o usen o gocen temporalmente bienes, prestados u otorgados por personas físicas, **estarán obligadas a retener el impuesto que se les traslade**.

### Reglamento de la LIVA

**Artículo 3, Fracción I, inciso c):**
> La retención se hará por **las dos terceras partes del impuesto** que se traslade y haya sido efectivamente pagado.

### Alcance

**Aplica a:**
- ✅ Servicios profesionales (honorarios)
- ✅ Arrendamiento
- ✅ Autotransporte
- ✅ RESICO

**Fórmula normativa:**
```
IVA Retenido = (IVA Trasladado) × (2/3)
```

**NO es:**
```
IVA Retenido = (Subtotal) × (10.67%)  ← INCORRECTO
```

---

## 🧮 Cálculo en Diferentes Escenarios

### Escenario 1: IVA General 16%

**Operación:** Honorarios $10,000
```
Subtotal:           10,000
IVA 16%:            +1,600  (IVA trasladado)
IVA Retenido:         -1,067  (2/3 de 1,600 = 1,066.67)
ISR Retenido 10%:   -1,000
─────────────────────────
Total a pagar:       9,533
```

**Tasa efectiva sobre subtotal:** 10.67% (1,067 / 10,000)

### Escenario 2: IVA Frontera 8%

**Operación:** Honorarios $10,000 (Zona Frontera Norte)
```
Subtotal:           10,000
IVA 8%:               +800  (IVA trasladado)
IVA Retenido:         -533  (2/3 de 800 = 533.33)
ISR Retenido 10%:   -1,000
─────────────────────────
Total a pagar:       9,267
```

**Tasa efectiva sobre subtotal:** 5.33% (533 / 10,000)

### Escenario 3: IVA 0% (Exportación)

**Operación:** Honorarios $10,000 (Exportación)
```
Subtotal:           10,000
IVA 0%:                  +0  (IVA trasladado)
IVA Retenido:            -0  (2/3 de 0 = 0)
ISR Retenido 10%:   -1,000
─────────────────────────
Total a pagar:       9,000
```

**Tasa efectiva sobre subtotal:** 0%

### Escenario 4: Exento de IVA

**Operación:** Honorarios $10,000 (Servicio exento)
```
Subtotal:           10,000
IVA Exento:              +0  (no hay IVA trasladado)
IVA Retenido:            -0  (2/3 de 0 = 0)
ISR Retenido 10%:   -1,000
─────────────────────────
Total a pagar:       9,000
```

**Tasa efectiva sobre subtotal:** 0%

---

## 💡 Respuestas a las Preguntas del Usuario

### 1. ¿El 10.67% cambia para retenciones de IVA?

**SÍ, SIEMPRE CAMBIA según la tasa de IVA aplicable.**

**Tabla de tasas efectivas:**

| Tasa IVA | IVA Trasladado | IVA Retenido (2/3) | Tasa Efectiva s/Subtotal |
|----------|----------------|-------------------|-------------------------|
| 16% General | 16% | 10.67% | **10.67%** |
| 8% Frontera | 8% | 5.33% | **5.33%** |
| 0% Exportación | 0% | 0% | **0%** |
| Exento | 0% | 0% | **0%** |

**Conclusión:** El 10.67% es **SOLO válido para IVA 16%**. NO es una constante universal.

---

### 2. ¿Tiene sentido tener ese campo si siempre es 2/3 del IVA?

**NO tiene sentido como campo fijo.**

**Razones:**

**❌ Problemas con campo fijo:**
- No refleja la realidad normativa (2/3 del IVA trasladado)
- Falla en zona frontera (retiene más de lo trasladado)
- Falla en IVA 0% y Exento (debería ser 0, no 10.67%)
- Requiere mantenimiento manual por zona

**✅ Ventajas cálculo relativo:**
- Siempre correcto (2/3 del IVA real)
- Automático para cualquier tasa IVA
- Conforme a normativa SAT
- Zero-config (no requiere ajustes por zona)

**Recomendación:** **ELIMINAR campo tasa fija, calcular siempre como porcentaje del IVA trasladado.**

---

### 3. ¿Podemos hacerlo dependiente del IVA realmente cobrado?

**SÍ, ES LA OPCIÓN MÁS LIMPIA Y CORRECTA.**

**Implementación técnica:**

#### Opción A: Cálculo en STCT (RECOMENDADA)

**Arquitectura:**
```
STCT Row 9:  IVA base (16% o 8% según zona)
             charge_type: "On Net Total"
             rate: 16.0 (o 8.0)
             → Resultado: IVA trasladado

STCT Row 10: Retención IVA (2/3 del IVA trasladado)
             charge_type: "On Previous Row Total"  ← Clave
             row_id: "9"
             rate: -66.67  (2/3 como porcentaje negativo)
             → Resultado: 2/3 del IVA fila anterior
```

**Ventajas:**
- ✅ Cumple normativa al 100%
- ✅ Automático para cualquier tasa IVA
- ✅ No requiere ITT para retenciones
- ✅ Feature nativo ERPNext (`On Previous Row Total`)
- ✅ Fácil de auditar (cálculo visible en STCT)

**Código propuesto:**
```python
# generador_templates_fiscal.py - STCT IVA 16%

# Fila IVA base
{
    "rol_fiscal": "IVA por Pagar (16%)",
    "charge_type": "On Net Total",
    "rate": 16.0,
    "add_deduct_tax": "Add",
    "description": "IVA 16% base (neto)",
    "idx": 9
}

# Fila Retención IVA (2/3 del IVA trasladado anterior)
{
    "rol_fiscal": "IVA Retenido (Servicios Profesionales)",
    "charge_type": "On Previous Row Total",  # ← Calcula sobre total acumulado fila anterior
    "row_id": "9",  # ← Fila del IVA base
    "rate": -66.67,  # ← 2/3 expresado como porcentaje (negativo para restar)
    "add_deduct_tax": "Deduct",
    "description": "Retención IVA (2/3 del IVA trasladado)",
    "idx": 10
}
```

**Ejemplo cálculo ERPNext:**
```
Subtotal: 10,000

Fila 9 (IVA 16%):
  Base = 10,000 (On Net Total)
  Tax = 10,000 × 16% = 1,600
  Total acumulado = 11,600

Fila 10 (Ret IVA):
  Base = 11,600 (On Previous Row Total)
  Tax = 11,600 × -66.67% = -7,733.72
  → INCORRECTO, necesitamos ajustar
```

**⚠️ CORRECCIÓN NECESARIA:**

El `On Previous Row Total` calcula sobre el **total acumulado**, no sobre el **tax amount** de la fila anterior.

**Solución correcta:**

ERPNext **NO tiene** un `charge_type` que calcule directamente sobre el tax amount de la fila anterior.

**Alternativas:**

#### Opción B: Cálculo manual en server-side hook

```python
# Override calculate_taxes_and_totals
def calculate_taxes_and_totals(doc, method=None):
    """Recalcular retenciones IVA como 2/3 del IVA trasladado."""

    # Identificar fila de IVA base
    iva_trasladado = 0
    iva_row_idx = None

    for idx, tax in enumerate(doc.taxes):
        if "IVA por Pagar" in tax.account_head and tax.add_deduct_tax == "Add":
            iva_trasladado += tax.tax_amount
            iva_row_idx = idx

    # Ajustar retención IVA
    for tax in doc.taxes:
        if "IVA Retenido" in tax.account_head:
            # Calcular 2/3 del IVA trasladado
            tax.tax_amount = -1 * (iva_trasladado * (2/3))
            tax.rate = 0  # Rate se ignora, usamos tax_amount directo
```

**Ventajas:**
- ✅ Cálculo correcto siempre
- ✅ Funciona con STCT rate=0 (placeholder)

**Desventajas:**
- ⚠️ Requiere hook personalizado
- ⚠️ Menos transparente (cálculo oculto)

#### Opción C: Custom charge_type

**Crear un charge_type personalizado:**
```python
# Nuevo charge_type: "On Previous Row Tax Amount"
# Calcula sobre tax_amount de fila anterior, no sobre total
```

**Ventajas:**
- ✅ Limpio y explícito
- ✅ Reutilizable para otros casos

**Desventajas:**
- ❌ Requiere modificar core Frappe/ERPNext
- ❌ Complejidad alta
- ❌ Puede romper con actualizaciones

---

## 🎯 Recomendación Final

### Mi Opinión Técnica

**OPCIÓN B: Cálculo server-side hook es la más práctica.**

**Razones:**

1. **Normativa SAT clara:**
   - Retención = 2/3 del IVA **trasladado** (no del subtotal)
   - No existe excepción, siempre es 2/3

2. **Campo tasa fija NO tiene sentido:**
   - 10.67% solo válido para IVA 16%
   - Falla en frontera, exportación, exento
   - Requiere mantenimiento manual

3. **Cálculo relativo es obligatorio:**
   - Única forma de cumplir normativa
   - Automático para cualquier tasa IVA
   - Zero-config

4. **Limitación ERPNext:**
   - No existe `On Previous Row Tax Amount`
   - `On Previous Row Total` calcula sobre total acumulado
   - Hook es solución práctica y mantenible

### Arquitectura Propuesta

**STCT (placeholder para retenciones):**
```python
# Retención IVA - Rate 0 (se calcula en hook)
{
    "rol_fiscal": "IVA Retenido (Servicios Profesionales)",
    "charge_type": "On Net Total",
    "rate": 0.0,  # ← Placeholder, hook calcula el tax_amount
    "add_deduct_tax": "Deduct",
    "description": "Retención IVA (2/3 del IVA trasladado, calculado automáticamente)",
}
```

**Hook calculate_taxes_and_totals:**
```python
def calculate_retenciones_iva(doc, method=None):
    """
    Ajustar retenciones IVA para que sean exactamente 2/3 del IVA trasladado.
    Cumple con Art. 1-A LIVA y Art. 3 Reglamento LIVA.
    """
    if doc.doctype != "Sales Invoice":
        return

    # 1. Sumar todo el IVA trasladado (puede haber múltiples filas IVA)
    iva_trasladado_total = 0
    for tax in doc.taxes:
        # Identificar filas de IVA por rol fiscal
        if tax.account_head and frappe.db.get_value("Account", tax.account_head, "fm_rol_fiscal"):
            rol = frappe.db.get_value("Account", tax.account_head, "fm_rol_fiscal")
            if "IVA por Pagar" in rol and tax.add_deduct_tax == "Add":
                iva_trasladado_total += tax.tax_amount

    # 2. Ajustar retenciones IVA a 2/3 del IVA trasladado
    for tax in doc.taxes:
        if tax.account_head and frappe.db.get_value("Account", tax.account_head, "fm_rol_fiscal"):
            rol = frappe.db.get_value("Account", tax.account_head, "fm_rol_fiscal")
            if "IVA Retenido" in rol:
                # Calcular 2/3 del IVA trasladado
                retencion_correcta = iva_trasladado_total * (2.0 / 3.0)
                tax.tax_amount = -1 * retencion_correcta
                tax.rate = 0  # Rate es placeholder, usamos tax_amount directo
```

**Ubicación del hook:**
```python
# hooks.py
doc_events = {
    "Sales Invoice": {
        "before_save": "facturacion_mexico.hooks_retenciones.calculate_retenciones_iva",
    }
}
```

---

## 📊 Validación de Casos

### Caso 1: IVA 16% General

**Input:**
- Subtotal: 10,000
- STCT: IVA 16% - México - _TC

**Cálculo hook:**
```
IVA trasladado = 10,000 × 16% = 1,600
IVA retenido = 1,600 × (2/3) = 1,067
ISR retenido = 10,000 × 10% = 1,000
```

**Output:**
```
Subtotal:         10,000
IVA 16%:          +1,600
IVA Ret:          -1,067  ✓
ISR Ret:          -1,000
─────────────────────
Grand Total:      10,533
```

### Caso 2: IVA 8% Frontera

**Input:**
- Subtotal: 10,000
- STCT: IVA 8% Frontera - México - _TC

**Cálculo hook:**
```
IVA trasladado = 10,000 × 8% = 800
IVA retenido = 800 × (2/3) = 533
ISR retenido = 10,000 × 10% = 1,000
```

**Output:**
```
Subtotal:         10,000
IVA 8%:             +800
IVA Ret:            -533  ✓ CORRECTO (vs -1,067 actual)
ISR Ret:          -1,000
─────────────────────
Grand Total:       9,267
```

### Caso 3: IVA 0% Exportación

**Input:**
- Subtotal: 10,000
- Item con ITT IVA 0%

**Cálculo hook:**
```
IVA trasladado = 0 (ITT neutraliza IVA)
IVA retenido = 0 × (2/3) = 0
ISR retenido = 10,000 × 10% = 1,000
```

**Output:**
```
Subtotal:         10,000
IVA 0%:                0
IVA Ret:               0  ✓
ISR Ret:          -1,000
─────────────────────
Grand Total:       9,000
```

---

## ✅ Conclusiones

### Respuesta a Preguntas del Usuario

1. **¿El 10.67% cambia?**
   - ✅ **SÍ**, cambia según tasa IVA: 16%→10.67%, 8%→5.33%, 0%→0%

2. **¿Tiene sentido tener ese campo?**
   - ❌ **NO**, debe ser cálculo relativo (2/3 del IVA trasladado)

3. **¿Hacerlo dependiente del IVA cobrado?**
   - ✅ **SÍ, ES LA OPCIÓN MÁS LIMPIA** y la única normativamente correcta

### Acción Requerida

**ELIMINAR:**
- Campo tasa fija `10.67%` en constantes_fiscales.py
- ITT para retenciones IVA (innecesarios)

**AGREGAR:**
- Hook `calculate_retenciones_iva()` en `before_save` Sales Invoice
- Cálculo dinámico: IVA Retenido = IVA Trasladado × (2/3)

**MANTENER:**
- STCT con rate=0 para retenciones (placeholder)
- ITT para IEPS (funcionan correctamente)
- ISR retenciones (tasa fija 10% correcta)

---

**Generado:** 2025-10-08
**Autor:** Claude Code
**Versión:** 1.0
