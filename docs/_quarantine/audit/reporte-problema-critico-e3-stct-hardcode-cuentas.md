# Reporte Problema Crítico E3 - STCT Hardcode Cuentas Retenciones

**Fecha:** 2025-10-08
**Severidad:** 🔴 CRÍTICA - Bloqueante para E3 Retenciones
**Contexto:** Testing E3 Retenciones - Arrendamiento y Autotransporte
**Estado:** BLOQUEADO - Requiere cambio arquitectónico

---

## 🔍 Resumen Ejecutivo

El sistema de retenciones E3 **solo funciona para Honorarios** pero **falla para Arrendamiento, Autotransporte y RESICO** debido a que el STCT tiene **cuentas contables hardcoded** específicas de Honorarios en las filas de retenciones.

ERPNext requiere **match exacto** entre cuentas del ITT y del STCT para inyectar tasas. Cuando no hay match, las tasas del ITT no se aplican y las retenciones quedan en cero.

---

## 📊 Evidencia del Problema

### ✅ Caso que FUNCIONA: Honorarios (ACC-SINV-2025-01585)

**Item:** TEST-RET-HONORARIOS-001
**ITT:** ITT ISR + IVA Ret Honorarios - _TC
**STCT:** IVA 8% Frontera - México - _TC

**Cuentas ITT Honorarios:**
```
- ISR: 09752834 - ISR Ret honorarios - _TC (-10%)
- IVA: 1538403 - iva retenido serv prof - _TC (-66.67%)
```

**Cuentas STCT (Rows 10-11):**
```
Row 10: 1538403 - iva retenido serv prof - _TC (rate: 0.0%)
Row 11: 09752834 - ISR Ret honorarios - _TC (rate: 0.0%)
```

**Resultado:**
```
✅ MATCH EXACTO → Tasas inyectadas correctamente
✅ Grand Total: $9,266.64
✅ IVA Ret: -$533.36 (2/3 de $800)
✅ ISR Ret: -$1,000 (10% de $10,000)
```

---

### ❌ Caso que FALLA: Autotransporte (ACC-SINV-2025-01588)

**Item:** TEST-RET-AUTOTRANSPORTE-001
**ITT:** ITT ISR + IVA Ret Autotransporte - _TC
**STCT:** IVA 8% Frontera - México - _TC

**Cuentas ITT Autotransporte:**
```
- ISR: 2118002 - ISR Ret Autotransporte - _TC (-4%)
- IVA: 2119002 - IVA Ret Autotransporte - _TC (-66.67%)
```

**Cuentas STCT (Rows 10-11):**
```
Row 10: 1538403 - iva retenido serv prof - _TC (rate: 0.0%)
Row 11: 09752834 - ISR Ret honorarios - _TC (rate: 0.0%)
```

**Resultado:**
```
❌ NO HAY MATCH → Tasas NO inyectadas
❌ Grand Total: $10,800.00 (debería ser $9,466.64)
❌ IVA Ret: $0.00 (debería ser -$533.36)
❌ ISR Ret: $0.00 (debería ser -$400.00)
```

**Cálculo Esperado:**
```
Subtotal:              10,000.00
+ IVA 8%:                 800.00
- Ret IVA (2/3):         -533.36
- Ret ISR (4%):          -400.00
─────────────────────────────────
Grand Total ESPERADO:  9,466.64
Grand Total ACTUAL:   10,800.00  ❌ INCORRECTO
```

---

### ❌ Caso que FALLA: Arrendamiento (ACC-SINV-2025-01587)

**Item:** TEST-RET-ARRENDAMIENTO-001
**ITT:** ITT ISR + IVA Ret Arrendamiento - _TC
**STCT:** IVA 8% Frontera - México - _TC

**Cuentas ITT Arrendamiento:**
```
- ISR: 2118001 - ISR Ret Arrendamiento - _TC (-10%)
- IVA: 2119001 - IVA Ret Arrendamiento - _TC (-66.67%)
```

**Cuentas STCT (Rows 10-11):**
```
Row 10: 1538403 - iva retenido serv prof - _TC
Row 11: 09752834 - ISR Ret honorarios - _TC
```

**Resultado (comportamiento diferente):**
```
❌ NO HAY MATCH → ERPNext REEMPLAZA STCT completo
⚠️ Solo 2 filas aplicadas (ITT reemplaza todo el STCT)
❌ Grand Total: $2,333.00
❌ Falta IVA base (debería ser +$800)
❌ IVA Ret: -$6,667.00 (calculado sobre $10,000 en lugar de $800)
```

**Problema adicional:** En este caso ERPNext **no solo falla en inyectar tasas**, sino que **reemplaza el STCT completo**, perdiendo todas las filas (IEPS, IVA base, etc.).

---

## 🔧 Causa Raíz

### Comportamiento ERPNext Item Tax Template

ERPNext usa el siguiente algoritmo para aplicar ITT:

1. **Toma el STCT** de la transacción (13 filas en nuestro caso)
2. **Lee el ITT** del item (2 cuentas de retenciones)
3. **Por cada cuenta en el ITT:**
   - Busca **match exacto de cuenta** en el STCT
   - Si encuentra match → **inyecta la tasa** del ITT en esa fila del STCT
   - Si NO encuentra match → **comportamiento indefinido** (puede ignorar o reemplazar)

### Problema Arquitectónico

El STCT generado tiene **cuentas hardcoded específicas de Honorarios**:

**Código actual en `generador_templates_fiscal.py:193-212`:**

```python
# (4) Retenciones
# Retención IVA: 2/3 del IVA trasladado (On Previous Row Amount sobre fila IVA base)
taxes_16.append({
    "rol_fiscal": "IVA Retenido (Servicios Profesionales)",  # ← HARDCODE Honorarios
    "charge_type": "On Previous Row Amount",
    "rate": 0.0,  # ITT inyecta 66.67
    "add_deduct_tax": "Deduct",
    "description": "Retención IVA (2/3 del IVA trasladado, tasa via ITT)",
    "_row_ref_prev": idx_iva_base_16,
})

# Retención ISR: % sobre neto
taxes_16.append({
    "rol_fiscal": "ISR Retenido (Honorarios)",  # ← HARDCODE Honorarios
    "charge_type": "On Net Total",
    "rate": 0.0,  # ITT inyecta tasa ISR (10%, 4%, 1.25%)
    "add_deduct_tax": "Deduct",
    "description": "Retención ISR (tasa via ITT)",
})
```

**Resultado:**
- El campo `"rol_fiscal"` se traduce a una **cuenta contable específica** vía `Mapeo Cuenta Fiscal Mexico`
- Para Honorarios: `1538403 - iva retenido serv prof`
- Para Arrendamiento: `2119001 - IVA Ret Arrendamiento`
- Para Autotransporte: `2119002 - IVA Ret Autotransporte`

**Como las cuentas son diferentes, NO HAY MATCH.**

---

## 🎯 Impacto

### Funcionalidad Afectada

| Tipo Retención | Estado | Razón |
|----------------|--------|-------|
| **Honorarios** | ✅ Funciona | Cuentas del STCT hacen match con ITT |
| **Arrendamiento** | ❌ Bloqueado | Cuentas diferentes → No inyecta tasas O reemplaza STCT |
| **Autotransporte** | ❌ Bloqueado | Cuentas diferentes → No inyecta tasas |
| **RESICO** | ❌ Bloqueado | Cuentas diferentes → No inyecta tasas |

### Severidad

🔴 **CRÍTICA** - Bloquea completamente 3 de 4 tipos de retenciones (75% del alcance E3).

### Testing Bloqueado

- ❌ No se puede probar Arrendamiento
- ❌ No se puede probar Autotransporte
- ❌ No se puede probar RESICO
- ⏸️ Testing IVA 16% / 0% / Exento diferido hasta resolver

---

## 💡 Opciones de Solución

### Opción A: STCT Dinámico con Cuentas Genéricas (RECOMENDADA)

**Concepto:** El STCT debe tener filas de retenciones con **cuentas que hagan match** con cualquier ITT.

**Enfoque 1: Cuenta "Comodín" (Account Wildcard)**

Crear una **cuenta genérica de retenciones** que sirva de placeholder:

```
- 2100000 - Retenciones Fiscales por Pagar (Genérica)
```

**STCT generado:**
```python
taxes_16.append({
    "rol_fiscal": "Retenciones Fiscales (Genérica)",  # ← Cuenta comodín
    "charge_type": "On Previous Row Amount",
    "rate": 0.0,
    "description": "Retención IVA (tasa via ITT)",
})
```

**Problema:** ERPNext probablemente requiere **match exacto de cuenta** específica, no comodín.

---

**Enfoque 2: Múltiples STCT (uno por tipo de retención)**

Generar **4 STCT diferentes**:

```
- IVA 8% Frontera - México (Honorarios) - _TC
- IVA 8% Frontera - México (Arrendamiento) - _TC
- IVA 8% Frontera - México (Autotransporte) - _TC
- IVA 8% Frontera - México (RESICO) - _TC
```

Cada uno con las cuentas específicas de su tipo.

**Ventajas:**
- ✅ Garantiza match exacto cuenta ITT ↔ STCT
- ✅ No requiere cambios arquitectónicos complejos
- ✅ Compatible con modelo actual ERPNext

**Desventajas:**
- ❌ Multiplicación de templates (4× STCT por cada zona/tasa)
- ❌ Mantenimiento complejo (cambios en 4 lugares)
- ❌ Explosión combinatoria: 4 tipos × 2 zonas × 2 tasas = 16 STCT solo para retenciones

---

**Enfoque 3: STCT sin Retenciones + ITT Completo**

El STCT **NO incluye** filas de retenciones (solo IEPS + IVA base).

El ITT tiene **todas las filas necesarias** (IVA base + retenciones).

**STCT generado (9 filas):**
```python
# Solo IEPS + IVA base + E1 neutralizadores
# SIN filas de retenciones
```

**ITT Honorarios (4 filas):**
```python
# Fila 1: IVA 16% base (para inyectar en fila vacía del STCT)
# Fila 2: Ret IVA -66.67% (nueva fila que se agrega)
# Fila 3: Ret ISR -10% (nueva fila que se agrega)
```

**Problema:** Requiere investigar si ERPNext permite que el ITT **agregue nuevas filas** al STCT o solo inyecta tasas en filas existentes.

---

### Opción B: Hooks Server-Side para Inyección Dinámica

**Concepto:** El STCT tiene filas placeholder genéricas. Un hook server-side **reescribe las cuentas** dinámicamente según el ITT aplicado.

**Hook `before_save` Sales Invoice:**

```python
def inject_retencion_accounts(doc, method=None):
    """
    Reescribe cuentas de retenciones en STCT según ITT del item.
    """
    if doc.doctype != "Sales Invoice":
        return

    # Identificar ITT del primer item (asumir single-ITT por factura)
    if not doc.items or not doc.items[0].item_tax_template:
        return

    itt = frappe.get_doc("Item Tax Template", doc.items[0].item_tax_template)

    # Mapeo ITT → Cuentas de retenciones
    itt_accounts = {tax.tax_type: tax.tax_rate for tax in itt.taxes}

    # Reescribir filas 10-11 del STCT con cuentas del ITT
    for tax_row in doc.taxes:
        if "Retención IVA" in (tax_row.description or ""):
            # Buscar cuenta IVA Ret en ITT
            for account, rate in itt_accounts.items():
                if "IVA Ret" in account:
                    tax_row.account_head = account
                    tax_row.rate = rate

        elif "Retención ISR" in (tax_row.description or ""):
            # Buscar cuenta ISR Ret en ITT
            for account, rate in itt_accounts.items():
                if "ISR Ret" in account:
                    tax_row.account_head = account
                    tax_row.rate = rate
```

**Ventajas:**
- ✅ STCT único, no multiplicación
- ✅ Cuentas dinámicas según ITT
- ✅ Flexible para agregar nuevos tipos

**Desventajas:**
- ❌ Lógica compleja en hook
- ❌ Posibles efectos colaterales con cálculo taxes ERPNext
- ❌ Difícil debugging (cambios no visibles en STCT)

---

### Opción C: Custom DocType "Tax Template Compositor"

**Concepto:** Crear un DocType intermedio que **compone dinámicamente** el STCT final combinando:
- STCT base (IEPS + IVA)
- ITT del item (retenciones)

**Arquitectura:**
```
Item (con ITT) → Tax Compositor → STCT Final Dinámico
```

**Ventajas:**
- ✅ Máxima flexibilidad
- ✅ Lógica centralizada
- ✅ Auditable (log de composición)

**Desventajas:**
- ❌ Complejidad alta
- ❌ Modificación profunda del flujo ERPNext
- ❌ Posibles conflictos con updates ERPNext

---

## 🎯 Recomendación

### Solución Recomendada: **Opción A - Enfoque 2 (Múltiples STCT)**

**Razón:**
1. **Menor riesgo** - No modifica comportamiento core ERPNext
2. **Garantiza funcionamiento** - Match exacto cuentas
3. **Implementación directa** - Modificar solo generador STCT
4. **Testing inmediato** - No requiere research adicional

**Mitigación explosión combinatoria:**
- Generar STCT programáticamente (ya se hace)
- Naming convention clara: `IVA {tasa} {zona} - México ({tipo_ret}) - {suffix}`
- Ejemplos:
  - `IVA 8% Frontera - México (Honorarios) - _TC`
  - `IVA 8% Frontera - México (Arrendamiento) - _TC`
  - `IVA 16% - México (Honorarios) - _TC`
  - `IVA 16% - México (Autotransporte) - _TC`

**Mantenimiento:**
- Cambios fiscales (tasas, cuentas) → Regenerar templates desde UI
- No requiere code changes para nuevos tipos (solo configuración)

---

## 📋 Plan de Implementación Propuesto

### Fase 1: Modificar Generador STCT (2-3 horas)

**Archivo:** `generador_templates_fiscal.py`

**Cambios:**

1. **Función `_obtener_stct_opcion_b()` - Parametrizar tipo retención**

```python
def _obtener_stct_opcion_b(self, tipo_retencion: str | None = None) -> dict:
    """
    Generar STCT con retenciones específicas por tipo.

    Args:
        tipo_retencion: "honorarios", "arrendamiento", "autotransporte", "resico", None
    """
    # ... código existente IEPS ...

    # (4) Retenciones - Dinámicas según tipo
    if tipo_retencion:
        cfg = RETENCIONES_CONFIG[tipo_retencion]

        taxes_16.append({
            "rol_fiscal": cfg["rol_iva"],  # Dinámico: IVA Ret (Servicios) o (Arrendamiento) etc
            "charge_type": "On Previous Row Amount",
            "rate": 0.0,
            "_row_ref_prev": idx_iva_base_16,
        })

        taxes_16.append({
            "rol_fiscal": cfg["rol_isr"],  # Dinámico: ISR Ret Honorarios o Arrendamiento etc
            "charge_type": "On Net Total",
            "rate": 0.0,
        })
    else:
        # STCT sin retenciones (para items sin ITT retenciones)
        pass
```

2. **Función `generar_templates_completos()` - Generar múltiples STCT**

```python
def generar_templates_completos(self):
    # ... código existente ...

    # STCT base (sin retenciones)
    stct_base = self._crear_o_actualizar_stct(
        self._obtener_stct_opcion_b(tipo_retencion=None),
        suffix_extra=""
    )

    # STCT con retenciones por tipo (solo si están habilitadas)
    tipos_habilitados = []
    if self.config_fiscal.enable_ret_honorarios:
        tipos_habilitados.append("honorarios")
    if self.config_fiscal.enable_ret_arrendamiento:
        tipos_habilitados.append("arrendamiento")
    if self.config_fiscal.enable_ret_autotransporte:
        tipos_habilitados.append("autotransporte")
    if self.config_fiscal.enable_ret_resico:
        tipos_habilitados.append("resico")

    for tipo in tipos_habilitados:
        for zona in ["16%", "8% Frontera"]:
            stct_ret = self._crear_o_actualizar_stct(
                self._obtener_stct_opcion_b(tipo_retencion=tipo),
                suffix_extra=f" ({tipo.title()})",
                base_name=f"IVA {zona} - México"
            )
```

3. **Actualizar Item Groups para usar STCT específico**

Modificar `item_groups.py` para que cada grupo de retenciones use su STCT correspondiente:

```python
ITEM_GROUP_STCT_MAP = {
    "sub servicios profesionales": "IVA {tasa} - México (Honorarios) - {suffix}",
    "sub arrendamiento": "IVA {tasa} - México (Arrendamiento) - {suffix}",
    "sub autotransporte": "IVA {tasa} - México (Autotransporte) - {suffix}",
    "sub resico": "IVA {tasa} - México (RESICO) - {suffix}",
}
```

### Fase 2: Testing (1-2 horas)

1. Regenerar templates desde UI
2. Verificar creación de STCT específicos
3. Crear facturas prueba (4 tipos × 2 zonas = 8 facturas)
4. Validar cálculos correctos

### Fase 3: Documentación (30 min)

- Actualizar CHANGELOG.md
- Documentar naming convention STCT
- Agregar ejemplos uso

---

## 🚨 Riesgos y Mitigaciones

### Riesgo 1: Explosión de STCT

**Problema:** 4 tipos × 2 zonas × 2 templates (STCT/ITT) = 16 templates solo retenciones

**Mitigación:**
- Generación automática (no manual)
- Naming convention clara
- Filtros UI por tipo/zona
- Documentación navegación

### Riesgo 2: Mantenimiento Complejidad

**Problema:** Cambios fiscales requieren actualizar múltiples STCT

**Mitigación:**
- Regeneración desde UI (1 click)
- Código centralizado (RETENCIONES_CONFIG)
- Testing automatizado (detecta inconsistencias)

### Riesgo 3: Confusión Usuario

**Problema:** Usuario debe seleccionar STCT correcto por tipo

**Mitigación:**
- STCT se asigna **automáticamente** por Item Group
- Usuario no selecciona manualmente
- Validación UI si STCT/ITT incompatibles

---

## ✅ Criterios de Éxito

1. **4 tipos de retenciones funcionan:**
   - ✅ Honorarios
   - ✅ Arrendamiento
   - ✅ Autotransporte
   - ✅ RESICO

2. **2 zonas fiscales funcionan:**
   - ✅ IVA 16% General
   - ✅ IVA 8% Frontera

3. **Cálculos correctos:**
   - ✅ IVA Retenido = 2/3 del IVA trasladado (proporcional)
   - ✅ ISR Retenido = % del neto (10%, 4%, 1.25%)
   - ✅ Signos negativos (restan del total)
   - ✅ Grand Total correcto

4. **Zero-config:**
   - ✅ Templates auto-generados desde UI
   - ✅ ITT auto-asignado por Item Group
   - ✅ STCT auto-asignado por Item Group
   - ✅ No configuración manual requerida

---

## 📊 Facturas de Evidencia

| Factura | Tipo | Estado | Grand Total Actual | Grand Total Esperado |
|---------|------|--------|-------------------|---------------------|
| ACC-SINV-2025-01585 | Honorarios 8% | ✅ OK | $9,266.64 | $9,266.64 |
| ACC-SINV-2025-01587 | Arrendamiento 8% | ❌ FALLA | $2,333.00 | $9,266.64 |
| ACC-SINV-2025-01588 | Autotransporte 8% | ❌ FALLA | $10,800.00 | $9,466.64 |
| (Pendiente) | RESICO 8% | ⏸️ No probado | - | $9,666.64 |

---

**Generado:** 2025-10-08
**Autor:** Claude Code
**Versión:** 1.0
**Estado:** Requiere Autorización Usuario para Implementar
