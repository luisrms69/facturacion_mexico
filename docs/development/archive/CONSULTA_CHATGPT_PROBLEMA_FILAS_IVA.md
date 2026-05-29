# CONSULTA TÉCNICA: PÉRDIDA FILAS IVA CON MÚLTIPLES ITEMS EN SALES INVOICE

**Fecha:** 2025-10-26
**Branch:** feature/e1-automated-tax-system
**Contexto:** Implementación IEPS Tasa desde constantes fiscales
**Framework:** ERPNext/Frappe v15

---

## 📋 RESUMEN EJECUTIVO

### **Problema:**
Después de implementar tasas IEPS correctas (Alcohol 26.5%, Tabaco 160%), Sales Invoices con **múltiples items** pierden todas las filas IVA, manteniendo solo filas IEPS.

### **Impacto:**
- ✅ IEPS Tasa calcula correctamente: +$1,674.50
- ❌ IVA Base se pierde: -$838.40
- ❌ IVA Cascada se pierde: -$48.78
- **Resultado:** Grand Total = $7,149.34 (falta $1,050.76 vs PAC esperado $8,200.10)

### **Comportamiento:**
- **1 item con ITT:** 11 filas taxes se mantienen ✅
- **2+ items con ITT:** Solo filas IEPS (4 filas), sin IVA ❌

---

## 🎯 OBJETIVO

Lograr que Sales Invoice con **múltiples items** mantenga la estructura completa del STCT:
- IVA Base (16% sobre neto)
- IEPS (via ITT por item)
- IVA Cascada (16% sobre cada IEPS)

**Target:** Grand Total = $8,200.10 (según PAC validación)

---

## 📚 ANTECEDENTES

### **Sistema Anterior (FUNCIONABA):**
- **STCT consolidado:** "IVA 16% - México" con **19 filas**
- Incluía: IEPS + Retenciones + IVA base + Neutralizadores E1
- **Característica clave:** IVA base estaba en **fila 9** (AL FINAL, después de todos los IEPS)
- **Estado actual:** DESHABILITADO desde refactorización

### **Sistema Actual (PROBLEMA):**
- **STCT específico:** "IVA Nacional - IEPS" con **11 filas**
- Incluye solo: IVA base + IEPS con cascada
- **Característica clave:** IVA base está en **fila 1** (AL INICIO, antes de IEPS)
- **Estado actual:** HABILITADO

### **Refactorización Implementada:**
- Migración de 2 templates consolidados (19 filas) → 8 templates específicos (1-14 filas)
- Objetivo: eliminar filas en $0 en facturas
- Arquitectura: Nacional/Frontera × Básico/IEPS/Retenciones/Total

---

## 🔬 COMPORTAMIENTO OBSERVADO

### **Test 1: SI con 1 item (ACC-SINV-2025-01651)**
```
Items: 1 (Alcohol)
STCT asignado: "IVA Nacional - IEPS - _TC" (11 filas)

RESULTADO: ✅ 11 filas taxes mantenidas
1. IVA Nacional - Base (Resto) - $0.00 (item no aplica)
2. IEPS Alcohol - Tasa (via ITT) - $874.50
3. IVA sobre IEPS Alcohol - $139.92
4-11. (resto en $0.00, item no aplica)

Grand Total: Correcto
```

### **Test 2: SI con 2 items (ACC-SINV-2025-01652)**
```
Items: 2 (Alcohol + Tabaco)
STCT asignado: "IVA Nacional - IEPS - _TC" (11 filas)

RESULTADO: ❌ Solo 4 filas taxes
1. 2117001 - IEPS Alcohol - _TC
2. 2117004 - IEPS Tabaco - _TC
[FALTAN: todas las filas IVA - base y cascada]

Grand Total: Incorrecto (falta IVA)
```

### **Test 3: SI con 4 items (ACC-SINV-2025-01649)**
```
Items: 4 (Alcohol x2 + Tabaco x2)
STCT asignado: "IVA Nacional - IEPS - _TC" (11 filas)

RESULTADO: ❌ Solo 4 filas taxes
1. 2117001 - IEPS Alcohol - _TC - $874.50
2. 2117002 - IEPS Azúcar - _TC - $0.00
3. 2117004 - IEPS Tabaco - _TC - $800.00
4. 2117005 - IEPS Tabaco Cuota - _TC - $0.00

[FALTAN: IVA Base $838.40 + IVA Cascada $267.92]
Grand Total: $7,149.34 (faltan $1,050.76)
```

---

## 🔍 HALLAZGOS TÉCNICOS

### **A) CAUSA RAÍZ IDENTIFICADA:**
**ERPNext Setting:** `add_taxes_from_item_tax_template = 1` (ACTIVADO)

**Comportamiento documentado ERPNext:**
Cuando múltiples items tienen ITT diferentes, ERPNext:
1. Limpia el array `doc.taxes` completo
2. Reconstruye taxes SOLO desde los ITT de los items
3. **Ignora completamente** las filas del STCT que no vienen de ITT

**Evidencia código ERPNext:**
```python
# sales_invoice_automated_tax.py línea 212-215
doc.set("taxes", [])  # ← Limpia taxes del STCT
tax_rows = get_taxes_and_charges("Sales Taxes and Charges Template", stct)
doc.extend("taxes", tax_rows)  # ← Carga desde template
# PERO: si items tienen ITT, ERPNext los reemplaza con solo filas ITT
```

### **B) COMPARACIÓN ESTRUCTURAS STCT**

#### **STCT VIEJO (19 filas - FUNCIONABA):**
```
Idx  Descripción                                  Type                   Rate
---  -------------------------------------------  ---------------------  ------
1    IEPS Alcohol - tasa via ITT                  On Net Total           0%
2    IVA 16% sobre IEPS Alcohol                   On Previous Row Amt    16%
3    IEPS Azúcar/Bebidas - tasa via ITT           On Net Total           0%
4    IVA 16% sobre IEPS Azúcar/Bebidas            On Previous Row Amt    16%
5    IEPS Combustibles - tasa via ITT             On Net Total           0%
6    IEPS Tabaco - tasa via ITT                   On Net Total           0%
7    IEPS Tabaco Cuota - tasa via ITT             On Net Total           0%
8    IVA 16% sobre IEPS Tabaco (Tasa + Cuota)     On Previous Row Total  16%
9    IVA 16% base (neto)                          On Net Total           16% ← AL FINAL
10-17 Retenciones (IVA + ISR × 4 tipos)          Various                Various
18   IVA 0% - neutraliza IVA por ítem             On Net Total           0%
19   IVA Exento - neutraliza IVA por ítem         On Net Total           0%
```

**Características clave:**
- ✅ IVA base en **fila 9** (AL FINAL, después de IEPS)
- ✅ Todas descripciones: "**tasa via ITT**"
- ✅ IEPS Combustibles: "On Net Total" con rate 0%
- ✅ Template consolidado (todo en uno)

#### **STCT NUEVO (11 filas - PROBLEMA):**
```
Idx  Descripción                                  Type                   Rate
---  -------------------------------------------  ---------------------  ------
1    IVA Nacional - Base (Resto)                  On Net Total           16% ← AL INICIO
2    IEPS Alcohol - Tasa (via ITT)                On Net Total           0%
3    IVA sobre IEPS Alcohol                       On Previous Row Amt    16%
4    IEPS Azúcar/Bebidas - Cuota (via ITT)        Actual                 N/A
5    IVA sobre IEPS Azúcar/Bebidas                On Previous Row Amt    16%
6    IEPS Combustibles - Cuota (via ITT)          Actual                 N/A
7    IVA sobre IEPS Combustibles                  On Previous Row Amt    16%
8    IEPS Tabaco - Tasa (via ITT)                 On Net Total           0%
9    IVA sobre IEPS Tabaco (Tasa)                 On Previous Row Amt    16%
10   IEPS Tabaco - Cuota (via ITT)                Actual                 N/A
11   IVA sobre IEPS Tabaco (Cuota)                On Previous Row Amt    16%
```

**Características clave:**
- ❌ IVA base en **fila 1** (AL INICIO, antes de IEPS)
- ❌ Descripciones: solo "(via ITT)" sin "tasa"
- ❌ IEPS Combustibles: "**Actual**" (cálculo dinámico hook)
- ❌ Template específico (solo IEPS)

### **C) DIFERENCIAS CRÍTICAS VIEJO vs NUEVO:**

| Aspecto | VIEJO (funcionaba) | NUEVO (problema) |
|---------|-------------------|------------------|
| **Posición IVA base** | Fila 9 (AL FINAL) | Fila 1 (AL INICIO) |
| **Descripción IEPS** | "tasa via ITT" | "(via ITT)" |
| **IEPS Combustibles** | On Net Total (rate 0%) | Actual (hook dinámico) |
| **IEPS Azúcar** | On Net Total (rate 0%) | Actual (hook dinámico) |
| **Completitud** | 19 filas (todo incluido) | 11 filas (solo IEPS) |
| **Retenciones** | Incluidas (filas 10-17) | NO incluidas |
| **Neutralizadores E1** | Incluidos (filas 18-19) | NO incluidos |

---

## 🔧 INTENTOS REALIZADOS

### **Intento 1: Regenerar ITT con tasas correctas**
```
Acción: Modificar generador_templates_fiscal.py para leer TASAS_IEPS
Script: regenerar_itt_tasas_ieps.py

Resultado:
✅ ITT IEPS Alcohol: 0% → 26.5%
✅ ITT IEPS Tabaco: 0% → 160%
✅ IEPS Tasa calcula: +$1,674.50
❌ Problema persiste: múltiples items pierden IVA
```

### **Intento 2: Mover hook a before_submit**
```
Acción: Mover corregir_ieps_cuota_final de before_save → before_submit
Hipótesis: Hook podría estar interfiriendo

Resultado:
❌ Mismo problema
✅ Confirmado: NO es el hook la causa
```

### **Intento 3: Desactivar setting ERPNext (REVERTIDO)**
```
Acción: frappe.db.set_single_value("Accounts Settings",
                                    "add_taxes_from_item_tax_template", 0)

Resultado:
❌ REVERTIDO INMEDIATAMENTE
Razón:
  - Cambio NO migrable
  - Viola RC-009 (Zero-config deployment)
  - No se replica en otros sites
```

### **Intento 4: Investigar STCT original**
```
Acción: Analizar STCT consolidado viejo de 19 filas
Script: buscar_stct_consolidado_viejo.py + comparar_stct_viejo_nuevo.py

Resultado:
✅ Encontrado: "IVA 16% - México - _TC" (19 filas, DISABLED)
✅ Identificadas diferencias estructurales clave (ver tabla arriba)
🤔 Hipótesis: orden de filas podría ser relevante
```

---

## 📊 DATOS TÉCNICOS ADICIONALES

### **ITT Configurados (Item Tax Templates):**

**ITT IEPS Alcohol - _TC:**
```json
{
  "taxes": [
    {
      "tax_type": "2117001 - IEPS por Pagar (Alcohol) - _TC",
      "tax_rate": 26.5
    }
  ]
}
```

**ITT IEPS Tabaco - _TC:**
```json
{
  "taxes": [
    {
      "tax_type": "2117004 - IEPS por Pagar (Tabaco) - _TC",
      "tax_rate": 160.0
    }
  ]
}
```

### **Item Groups y Asignación ITT:**
```
Item Group: "Bebidas Alcohólicas"
  → ITT: "ITT IEPS Alcohol - _TC"
  → Heredado por: Item "Vino Tinto Reserva 750ml"

Item Group: "Productos Tabaco"
  → ITT: "ITT IEPS Tabaco - _TC"
  → Heredado por: Item "Cigarros Premium Caja 20"
```

### **Arquitectura IEPS:**

**IEPS Tasa (Alcohol, Tabaco Tasa):**
- Tasas fijas en constantes_fiscales.py
- ITT hereda tasa desde Item Group
- ERPNext calcula: `net_amount × rate`
- `charge_type: "On Net Total"`

**IEPS Cuota (Azúcar, Combustibles, Tabaco Cuota):**
- Cuotas variables en DocType "IEPS Cuota SAT"
- Hook `calcular_ieps_cuota()` calcula dinámicamente
- ITT con `rate: 0` (correcto - hook asigna monto)
- `charge_type: "Actual"`

---

## 🎯 PREGUNTA PARA CHATGPT

**Dado el contexto anterior, ¿cuál es la mejor solución arquitectural para mantener las filas IVA del STCT cuando hay múltiples items con ITT en Sales Invoice?**

### **Opciones consideradas:**

**A) Modificar ITT para incluir IVA + IEPS combinados**
- Pros: ERPNext maneja todo nativamente
- Contras: Duplicación lógica, más ITT complejos, pierde granularidad

**B) Hook restaurador después de ERPNext**
- Pros: Mantiene STCT como fuente verdad
- Contras: Complejo, posibles conflictos con lógica ERPNext

**C) Restaurar orden STCT viejo (IVA base al final)**
- Pros: Podría resolver si orden importa a ERPNext
- Contras: No claro por qué orden afectaría behavior

**D) Modificar descripción filas STCT (agregar "tasa via ITT")**
- Pros: Simple si ERPNext usa descripción para match
- Contras: No claro si descripción es relevante

**E) Cambiar IEPS Cuota de "Actual" a "On Net Total"**
- Pros: Uniformidad con IEPS Tasa
- Contras: Perdemos cálculo dinámico (cuotas variables)

**F) Otra solución arquitectural**
- ¿Hay algún approach que no hayamos considerado?

### **Restricciones:**

1. **Zero-config deployment:** Solución debe ser migrable (no cambios manuales BD)
2. **Mantener arquitectura IEPS Cuota:** Hook dinámico con DocType lookup
3. **Mantener arquitectura IEPS Tasa:** ITT heredan tasas desde constantes
4. **8 STCT específicos:** No volver a templates consolidados de 19 filas
5. **Compatibilidad ERPNext v15:** Solución debe funcionar con framework nativo

### **Información adicional que podría ayudar:**

- ¿Por qué el STCT viejo de 19 filas funcionaba con múltiples items?
- ¿El orden de las filas en STCT afecta cómo ERPNext las procesa?
- ¿La descripción de la fila ("tasa via ITT") tiene algún significado especial?
- ¿Hay algún flag/setting en STCT que controle este comportamiento?
- ¿Existe alguna forma de "proteger" ciertas filas del STCT para que no sean reemplazadas?

---

## 📁 ARCHIVOS MODIFICADOS (BRANCH feature/e1-automated-tax-system)

### **Código:**
- `facturacion_mexico/facturacion_fiscal/doctype/configuracion_fiscal_mexico/generador_templates_fiscal.py`
  - Líneas 28-29: Import TASAS_IEPS
  - Línea 1052: ITT Alcohol rate → TASAS_IEPS["alcohol"]["tasa"]
  - Línea 1085: ITT Tabaco rate → TASAS_IEPS["tabaco"]["tasa"]

- `facturacion_mexico/hooks.py`
  - Línea 348: Hook corregir_ieps_cuota_final en before_save

### **Documentación:**
- `docs/development/REPORTE_IMPLEMENTACION_TASAS_IEPS_E1.md` (390 líneas)
- `docs/development/CONSULTA_CHATGPT_PROBLEMA_FILAS_IVA.md` (este archivo)

### **Scripts One-off (no commiteados):**
- `one_offs/regenerar_itt_tasas_ieps.py`
- `one_offs/buscar_stct_consolidado_viejo.py`
- `one_offs/comparar_stct_viejo_nuevo.py`
- `one_offs/test_stct_sin_items.py`
- `one_offs/test_stct_dos_items.py`
- Y 10+ scripts más de testing/investigación

---

## 🎬 PRÓXIMOS PASOS

Una vez que ChatGPT recomiende la solución:

1. ✅ Implementar cambios necesarios
2. ✅ Testing exhaustivo (1 item, 2 items, 4 items)
3. ✅ Validar Grand Total alcanza PAC target ($8,200.10)
4. ✅ Documentar solución implementada
5. ✅ Actualizar CHANGELOG.md
6. ✅ Commit con mensaje descriptivo
7. ✅ Continuar con resto de E1

---

**🤖 Generated with [Claude Code](https://claude.com/claude-code)**

**Co-Authored-By: Claude <noreply@anthropic.com>**
