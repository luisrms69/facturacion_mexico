# Reporte: Error Retenciones en Zona Frontera (E3)

**Fecha:** 2025-10-08
**Severidad:** CRÍTICA - Cálculo fiscal incorrecto
**Contexto:** E3 Retenciones - Testing Honorarios en Zona Frontera
**Factura:** ACC-SINV-2025-01582
**Company:** _Test Company (Zona Frontera - IVA 8%)

---

## 📋 Problema Identificado

### Descripción
Facturas con retenciones (Honorarios) en zona frontera están calculando **IVA 8%** sobre el neto, pero las **retenciones de IVA se calculan sobre la tasa general del 16%**, resultando en un cálculo fiscal **INCORRECTO**.

**Situación actual en ACC-SINV-2025-01582:**
- Subtotal: 10,000
- IVA Frontera 8%: +800 ← **Aplicado sobre neto**
- IVA Retenido 10.67%: -1,067 ← **Calculado sobre base 16% (10,000 × 10.67% = 1,067)**
- ISR Retenido 10%: -1,000
- **Grand Total: 12,867**

### Impacto Fiscal
- ❌ **Retención IVA incorrecta:** Se retiene 1,067 cuando solo se trasladó 800 de IVA
- ❌ **Grand Total incorrecto:** Cliente paga más de lo debido
- ❌ **Incumplimiento normativo:** Retenciones deben ser proporcionales al IVA trasladado

---

## 🔍 Análisis Técnico Detallado

### Contexto de Zona Frontera

**Normativa SAT:**
- Zona frontera: IVA al **8%** (mitad de la tasa general 16%)
- Retenciones IVA servicios profesionales: **2/3 del IVA trasladado**
- Formula correcta: `IVA Retenido = IVA Trasladado × (2/3)`

**Cálculo correcto para zona frontera:**
```
Subtotal:           10,000
IVA 8%:             +  800  (8% de 10,000)
IVA Retenido:       -  533  (2/3 de 800 = 533.33)
ISR Retenido 10%:   -1,000  (10% de 10,000)
─────────────────────────
Grand Total:         9,267
```

**Cálculo actual (INCORRECTO):**
```
Subtotal:           10,000
IVA 8%:             +  800  (8% de 10,000)
IVA Retenido:       -1,067  (10.67% de 10,000) ← ERROR: usa tasa general 16%
ISR Retenido 10%:   -1,000  (10% de 10,000)
─────────────────────────
Grand Total:        12,867  ← INCORRECTO (retiene más IVA del que se trasladó)
```

**Diferencia:** Se retienen **267 pesos más** de IVA del que se trasladó.

---

## 🔬 Análisis de Componentes

### 1. Item Tax Template (ITT)

**ITT aplicado:** "ITT ISR + IVA Ret Honorarios - _TC"

```
Configuración actual:
- ISR Retenido (Honorarios):           10.0%   ✓ CORRECTO
- IVA Retenido (Servicios Profesionales): 10.67%  ✗ INCORRECTO para frontera
```

**Problema identificado:**
- ITT tiene tasa **fija 10.67%** (2/3 de 16%)
- No considera que en frontera el IVA es 8%
- Debería retener **5.33%** (2/3 de 8%) en zona frontera

### 2. Sales Taxes and Charges Template (STCT)

**STCT aplicado:** "IVA 8% Frontera - México - _TC"

```
Configuración actual (simplificado):
Row  Descripción                          Tipo              Rate
───────────────────────────────────────────────────────────────────
9    IVA 8% frontera base (neto)         On Net Total      8.0%   ✓
10   Retención IVA (servicios)           On Net Total      0.0%   → lee ITT
11   Retención ISR (honorarios)          On Net Total      0.0%   → lee ITT
```

**Análisis:**
- ✓ STCT aplica IVA 8% correctamente
- ✓ STCT tiene slots para retenciones (rate 0, lee ITT)
- ✗ ITT retorna tasa fija sin considerar contexto frontera

### 3. Constantes Fiscales

**Archivo:** `constantes_fiscales.py`

```python
TASAS_RETENCIONES = {
    "iva_servicios": {
        "tasa": 10.67,  # ← HARDCODED para IVA 16%
        "descripcion": "IVA Retenido Servicios Profesionales 10.67%",
        "charge_type": "On Net Total",
        "add_deduct_tax": "Deduct",
    },
}
```

**Problema:**
- Tasa hardcoded asume siempre IVA 16%
- No hay lógica para ajustar según zona frontera

---

## 💡 Causa Raíz

### Arquitectura E2-E3 Actual

**Diseño actual (INCORRECTO para frontera):**
```
Item → Item Group → ITT (tasa fija) → STCT (aplica tasa del ITT)
                     └─ 10.67% siempre (asume IVA 16%)
```

**Problema fundamental:**
- ITT retenciones tiene **tasas absolutas fijas** (10.67%)
- No considera el **contexto del STCT** (IVA 16% vs 8%)
- Arquitectura asume que retenciones son siempre sobre el mismo IVA

### Diseño Correcto Requerido

**Opción 1: Tasas relativas en STCT**
```
STCT define:
- IVA 8% base
- Retención IVA = (2/3) × IVA trasladado anterior
- Retención ISR = 10% neto

No usar ITT para retenciones, calcular directamente en STCT
```

**Opción 2: ITT contextuales por zona**
```
ITT IVA Ret Honorarios (General 16%):  10.67% IVA ret
ITT IVA Ret Honorarios (Frontera 8%):   5.33% IVA ret

Item Group frontera → ITT frontera
Item Group general  → ITT general
```

**Opción 3: Cálculo dinámico en STCT**
```
STCT row retención IVA:
- charge_type: "On Previous Row Total"
- row_id: [fila del IVA trasladado]
- rate: 66.67% (2/3 expresado como porcentaje)
```

---

## 📊 Evidencia Completa

### Factura ACC-SINV-2025-01582

**Datos generales:**
```
Customer:  CONCESIONARIA VUELA COMPAÑIA DE AVIACION
Company:   _Test Company (enable_frontera=1)
STCT:      IVA 8% Frontera - México - _TC
Total:     10,000.00
Grand Total: 12,867.00 ← INCORRECTO (debería ser 9,267.00)
```

**Items:**
```
Item:              TEST-RET-HONORARIOS-001
Descripción:       Servicio Consultoría Profesional
Item Group:        sub servicios profesionales
  └─ Parent:       Servicios Profesionales (Honorarios)
ITT asignado:      ITT ISR + IVA Ret Honorarios - _TC
  └─ ISR Ret:      10.0%   ✓
  └─ IVA Ret:      10.67%  ✗ (debería ser 5.33% para frontera)
Rate:              10,000
Qty:               1
Amount:            10,000
```

**Desglose de impuestos (13 filas STCT):**
```
Row  Descripción                          Account                          Rate    Tax Amount  Total
────────────────────────────────────────────────────────────────────────────────────────────────────────
1    IEPS Alcohol                        IEPS Alcohol                     0.0%           0    10,000
2    IVA 8% sobre IEPS Alcohol          Iva 8% frontera                  8.0%           0    10,000
3    IEPS Azúcar/Bebidas                IEPS Azucar                      0.0%           0    10,000
4    IVA 8% sobre IEPS Azúcar           Iva 8% frontera                  8.0%           0    10,000
5    IEPS Combustibles                  IEPS Combustibles                0.0%           0    10,000
6    IVA 8% sobre IEPS Combustibles     Iva 8% frontera                  8.0%           0    10,000
7    IEPS Tabaco                        IEPS Tabaco                      0.0%           0    10,000
8    IVA 8% sobre IEPS Tabaco           Iva 8% frontera                  8.0%           0    10,000
9    IVA 8% frontera base (neto)        Iva 8% frontera                  8.0%         800    10,800
10   Retención IVA (servicios)          IVA retenido serv prof          0.0%      -1,067    11,867 ← ERROR
11   Retención ISR (honorarios)         ISR Ret honorarios              0.0%      -1,000    12,867
12   IVA 0% (mixto E1)                  IVA 0%                          0.0%           0    12,867
13   IVA Exento (mixto E1)              IVA exento                      0.0%           0    12,867
```

**Análisis fila 10 (problema):**
- Rate mostrado: 0.0% (lee del ITT)
- Tax Amount real: -1,067 (viene del ITT: 10,000 × 10.67%)
- **Debería ser:** -533 (2/3 del IVA trasladado: 800 × 2/3)

### Item Group Configuration

**Item Group:** Servicios Profesionales (Honorarios)
```
Parent:           All Item Groups
Is Group:         1
ITT asignado:     ITT ISR + IVA Ret Honorarios - _TC
  └─ Valid From:  2025-10-01
  └─ Asignación:  ✓ EXITOSA (código automático funcionó)
```

**Child Group:** sub servicios profesionales
```
Parent:           Servicios Profesionales (Honorarios)
Is Group:         0
ITT asignado:     None (hereda del parent) ✓ CORRECTO
```

### ITT Configuration

**ITT:** ITT ISR + IVA Ret Honorarios - _TC
```
Title:    ITT ISR + IVA Ret Honorarios - _TC
Company:  _Test Company
Taxes:
  1. ISR Ret honorarios:        10.0%   ✓ CORRECTO (no depende de IVA)
  2. IVA retenido serv prof:   10.67%   ✗ INCORRECTO (asume IVA 16%)
```

**Origen de la tasa 10.67%:**
```python
# constantes_fiscales.py línea 99-104
"iva_servicios": {
    "tasa": 10.67,  # ← 2/3 de 16% = 10.6666...
    "descripcion": "IVA Retenido Servicios Profesionales 10.67%",
    "charge_type": "On Net Total",
    "add_deduct_tax": "Deduct",
},
```

---

## 🎯 Recomendaciones

### Opción A: Retenciones Relativas en STCT (RECOMENDADA)

**Ventajas:**
- ✅ Cálculo correcto automático (retención siempre proporcional al IVA trasladado)
- ✅ Funciona para cualquier tasa IVA (16%, 8%, 0%)
- ✅ Un solo STCT maneja todos los casos
- ✅ No requiere ITT diferentes por zona

**Desventajas:**
- ⚠️ Cambio arquitectónico significativo
- ⚠️ STCT más complejo (cálculos sobre filas previas)

**Implementación:**
```python
# STCT "IVA 8% Frontera - México - _TC"
# Fila 9: IVA 8% base
{
    "charge_type": "On Net Total",
    "rate": 8.0,
    "add_deduct_tax": "Add",
    "idx": 9
}

# Fila 10: Retención IVA (2/3 del IVA trasladado)
{
    "charge_type": "On Previous Row Total",  # ← Clave: calcula sobre fila anterior
    "row_id": "9",                            # ← Referencia a fila IVA 8%
    "rate": -66.67,                           # ← 2/3 expresado como % negativo
    "add_deduct_tax": "Deduct",
    "idx": 10
}
```

**Resultado esperado:**
```
Fila 9:  IVA 8% base = 10,000 × 8% = 800 → Total acumulado: 10,800
Fila 10: Ret IVA = 800 × 66.67% = 533 (Deduct) → Total acumulado: 10,267
```

---

### Opción B: ITT Duplicados por Zona

**Ventajas:**
- ✅ Mantiene arquitectura actual ITT
- ✅ Explícito y claro (cada zona su ITT)

**Desventajas:**
- ❌ Duplicación de ITT (x2 por cada tipo retención)
- ❌ Item Groups deben saber su zona
- ❌ Mantenimiento complejo (2 conjuntos ITT)

**Implementación:**
```python
# Crear ITT específicos por zona
ITT_RET_HONORARIOS_GENERAL = {
    "title": "ITT ISR + IVA Ret Honorarios (General 16%)",
    "taxes": [
        {"rol_fiscal": "ISR Retenido (Honorarios)", "tax_rate": 10.0},
        {"rol_fiscal": "IVA Retenido (Servicios Profesionales)", "tax_rate": 10.67},
    ]
}

ITT_RET_HONORARIOS_FRONTERA = {
    "title": "ITT ISR + IVA Ret Honorarios (Frontera 8%)",
    "taxes": [
        {"rol_fiscal": "ISR Retenido (Honorarios)", "tax_rate": 10.0},
        {"rol_fiscal": "IVA Retenido (Servicios Profesionales)", "tax_rate": 5.33},  # ← 2/3 de 8%
    ]
}

# Crear Item Groups diferentes
ITEM_GROUP_ITT_MAP = {
    "Servicios Profesionales (Honorarios)": ITT_RET_HONORARIOS_GENERAL,
    "Servicios Profesionales Frontera (Honorarios)": ITT_RET_HONORARIOS_FRONTERA,
}
```

---

### Opción C: Cálculo Dinámico en Runtime (COMPLEJA)

**Ventajas:**
- ✅ Un solo ITT para todas las zonas
- ✅ Flexible y automático

**Desventajas:**
- ❌ Requiere override de lógica core ERPNext
- ❌ Muy complejo de mantener
- ❌ Puede romper con actualizaciones framework

**NO RECOMENDADA**

---

## 🔧 Comparativa de Opciones

| Criterio | Opción A (Relativas STCT) | Opción B (ITT Duplicados) | Opción C (Runtime) |
|----------|---------------------------|---------------------------|--------------------|
| **Corrección fiscal** | ✅ 100% | ✅ 100% | ✅ 100% |
| **Simplicidad usuario** | ✅ Transparente | ⚠️ Debe elegir zone | ✅ Transparente |
| **Mantenibilidad** | ✅ Alta | ⚠️ Media | ❌ Baja |
| **Escalabilidad** | ✅ Alta | ⚠️ Baja (crece x zonas) | ⚠️ Media |
| **Compatibilidad** | ✅ Estándar ERPNext | ✅ Estándar ERPNext | ❌ Overrides core |
| **Esfuerzo implementación** | ⚠️ Medio | ✅ Bajo | ❌ Alto |
| **Riesgo** | ✅ Bajo | ✅ Bajo | ❌ Alto |

---

## 📝 Mi Opinión Técnica

### Problema Fundamental

El diseño E2-E3 actual **NO es compatible con zona frontera para retenciones**. La arquitectura asume que:
1. ITT define tasas **absolutas fijas**
2. Retenciones siempre se calculan sobre **IVA 16%**

Esta asunción es **INCORRECTA** para México, donde:
- IVA puede ser 16%, 8%, o 0%
- Retenciones IVA deben ser **proporcionales al IVA trasladado**

### Recomendación Final

**OPCIÓN A: Retenciones Relativas en STCT**

**Razones:**
1. **Corrección normativa:** Retenciones siempre proporcionales al IVA trasladado
2. **Escalabilidad:** Funciona para cualquier tasa IVA futura
3. **Simplicidad usuario:** Un solo flujo, sin duplicar Item Groups
4. **Mantenibilidad:** Lógica centralizada en STCT
5. **Estándar ERPNext:** Usa "On Previous Row Total" (feature nativa)

**Arquitectura propuesta:**
```
STCT consolidado (Opción B actual):
├─ IVA base (16% o 8% según zona)
├─ Retención IVA: On Previous Row Total, rate -66.67% (2/3)
├─ Retención ISR: On Net Total, rate -10%
└─ Mixto E1 (0%, Exento)

ITT solo para IEPS (no para retenciones):
├─ ITT IEPS Alcohol: 26.5%
├─ ITT IEPS Azúcar: 1.0%
└─ [retenciones se calculan en STCT, no ITT]
```

**Cambios requeridos:**
1. **STCT:** Modificar filas retenciones IVA a `charge_type: "On Previous Row Total"`
2. **ITT:** Eliminar ITT retenciones (STCT maneja todo)
3. **Item Groups:** Mantener como están (solo para IEPS)
4. **Constantes:** Documentar que retenciones IVA son relativas

---

## ⚠️ Implicaciones de NO Corregir

**Impacto legal:**
- ❌ Retenciones incorrectas en CFDI
- ❌ Rechazo por SAT en validación
- ❌ Multas por declaraciones incorrectas

**Impacto operativo:**
- ❌ Clientes zona frontera pagan de más
- ❌ Descuadres contables
- ❌ Pérdida de confianza en el sistema

**Urgencia:** **CRÍTICA** - Bloquea uso en producción para zona frontera

---

## 🔗 Archivos Involucrados

1. **`constantes_fiscales.py`** (línea 99-104)
   - Define tasa fija IVA ret servicios: 10.67%
   - Requiere cambio o eliminación

2. **`generador_templates_fiscal.py`** (línea 129-304)
   - Función `_obtener_stct_opcion_b()`
   - Genera filas retenciones con rate 0 (lee ITT)
   - Requiere cambio a `charge_type: "On Previous Row Total"`

3. **`item_groups.py`** (línea 25-28)
   - Define mapeo ITT retenciones
   - Posible eliminación si Opción A

4. **Fixtures Item Groups**
   - `item_group_fiscal_structure.json`
   - Mantener como están (solo nombres)

---

## 📋 Próximos Pasos

1. **Decisión:** Usuario decide entre Opción A, B, o alternativa
2. **Diseño detallado:** Especificar cambios exactos código
3. **Implementación:** Modificar generador STCT
4. **Testing:** Validar 4 escenarios:
   - Retenciones General 16%
   - Retenciones Frontera 8%
   - IEPS + Retenciones General
   - IEPS + Retenciones Frontera
5. **Documentación:** Actualizar arquitectura E2-E3

---

**Generado:** 2025-10-08
**Autor:** Claude Code
**Versión:** 1.0
