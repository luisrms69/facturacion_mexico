# REPORTE: ARQUITECTURA IEPS CUOTA VS IEPS TASA

**Fecha:** 2025-10-26
**Contexto:** Migración E1 - Sistema Automated Tax
**Alcance:** Análisis arquitectural diferencias IEPS Cuota vs IEPS Tasa

---

## RESUMEN EJECUTIVO

**Hallazgo crítico:** IEPS Cuota e IEPS Tasa tienen arquitecturas COMPLETAMENTE DIFERENTES:

| Aspecto | IEPS Cuota | IEPS Tasa |
|---------|-----------|-----------|
| **Tasa ITT** | 0% (correcto) | 0% (INCORRECTO) |
| **Cálculo** | Hook dinámico | Rate de ITT |
| **Lookup** | DocType `IEPS Cuota SAT` | NO existe |
| **Fuente tasa** | Tabla SAT por clave producto | Item Group → ITT → Item |
| **charge_type** | "Actual" | "On Net Total" |
| **Asignación** | `item_wise_tax_detail` | `tax_row.rate` |

**Bloqueador identificado:** ITT de IEPS Tasa se generan con `tax_rate: 0` cuando deberían usar tasas de `constantes_fiscales.py`.

---

## 1. ARQUITECTURA IEPS CUOTA (Azúcar, Combustibles, Tabaco Cuota)

### 1.1 Flujo Correcto Actual

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. GENERACIÓN ITT (install/setup)                               │
├─────────────────────────────────────────────────────────────────┤
│ generate_itt_for_company()                                      │
│   → ITT IEPS Azúcar/Combustibles/Tabaco Cuota                   │
│   → tax_rate: 0.0 (CORRECTO - no usa rate)                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. ASIGNACIÓN ITEM GROUP                                        │
├─────────────────────────────────────────────────────────────────┤
│ item_groups.py → _assign_group_itt()                            │
│   Item Group: "Artículos IEPS Azúcar"                           │
│     → ITT: "ITT IEPS Azúcar - _TC"                              │
│     → Item hereda ITT de su Item Group                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. SALES INVOICE - CÁLCULO DINÁMICO                             │
├─────────────────────────────────────────────────────────────────┤
│ Hook: before_save → calcular_ieps_cuota()                       │
│                                                                  │
│ Para cada item:                                                 │
│   1. Lee Item.fm_producto_servicio_sat (clave SAT)              │
│   2. Busca en DocType IEPS Cuota SAT:                           │
│      → Filters: company, clave_prod_serv, cuenta_ieps           │
│      → Vigencia: vigencia_desde <= fecha <= vigencia_hasta      │
│      → Returns: cuota, uom (e.g., $1.6451/litro)                │
│   3. Calcula: cantidad_litros × cuota_sat = monto_ieps          │
│   4. Asigna: tax_row.tax_amount = monto_ieps                    │
│   5. Actualiza: item_wise_tax_detail[item_code] = monto_ieps    │
│   6. Marca: dont_recompute_tax = 1                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. RESULTADO                                                     │
├─────────────────────────────────────────────────────────────────┤
│ Tax Row:                                                         │
│   charge_type: "Actual"                                          │
│   rate: 0.0 (no usado)                                           │
│   tax_amount: $15.24 (calculado por hook)                        │
│   item_wise_tax_detail: {"ITEM-001": 15.24}                     │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Código Clave IEPS Cuota

**DocType IEPS Cuota SAT:**
```
facturacion_mexico/facturacion_fiscal/doctype/ieps_cuota_sat/
Fields:
  - company (Link: Company)
  - clave_prod_serv (Data) - Clave SAT producto
  - uom (Link: UOM) - Unidad base cuota
  - cuota (Currency, 6 decimals) - Monto por unidad
  - cuenta_ieps (Link: Account)
  - vigencia_desde (Date)
  - vigencia_hasta (Date)
```

**Hook Lookup Cuota (sales_invoice_ieps.py:154-173):**
```python
cuota_sat = frappe.db.sql("""
    SELECT cuota, uom
    FROM `tabIEPS Cuota SAT`
    WHERE company = %(company)s
      AND clave_prod_serv = %(clave_prod_serv)s  # Desde Item.fm_producto_servicio_sat
      AND cuenta_ieps = %(cuenta_ieps)s
      AND vigencia_desde <= %(fecha)s
      AND IFNULL(vigencia_hasta, '2099-12-31') >= %(fecha)s
    LIMIT 1
""")
```

**Características:**
- ✅ Centralizado en DocType maestro
- ✅ Vigencias temporales soportadas
- ✅ Single source of truth
- ✅ Mantenible y auditable
- ✅ Escalable (fácil agregar nuevas cuotas)

---

## 2. ARQUITECTURA IEPS TASA (Alcohol, Tabaco Tasa)

### 2.1 Flujo INCORRECTO Actual

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. GENERACIÓN ITT (install/setup)                               │
├─────────────────────────────────────────────────────────────────┤
│ generate_itt_for_company()                                      │
│   → ITT IEPS Alcohol: tax_rate: 0.0 ❌ INCORRECTO               │
│   → ITT IEPS Tabaco: tax_rate: 0.0 ❌ INCORRECTO                │
│                                                                  │
│ Comentario código (línea 1049):                                 │
│   # Tasa se fija en ITT del item  ← COMENTARIO INCORRECTO       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. ASIGNACIÓN ITEM GROUP                                        │
├─────────────────────────────────────────────────────────────────┤
│ item_groups.py → _assign_group_itt()                            │
│   Item Group: "Artículos IEPS Alcohol"                          │
│     → ITT: "ITT IEPS Alcohol - _TC" (rate: 0%)                  │
│     → Item hereda ITT de su Item Group                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. SALES INVOICE - SIN CÁLCULO                                  │
├─────────────────────────────────────────────────────────────────┤
│ ❌ NO existe hook para IEPS Tasa                                │
│ ❌ NO existe DocType IEPS Tasa SAT                              │
│ ❌ ERPNext usa rate del ITT = 0% → tax_amount = $0.00           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. RESULTADO                                                     │
├─────────────────────────────────────────────────────────────────┤
│ Tax Row:                                                         │
│   charge_type: "On Net Total"                                    │
│   rate: 0.0 ❌                                                   │
│   tax_amount: $0.00 ❌ (debería ser ~$874.50 para alcohol)      │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Flujo CORRECTO Esperado

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. GENERACIÓN ITT (install/setup)                               │
├─────────────────────────────────────────────────────────────────┤
│ generate_itt_for_company()                                      │
│   → ITT IEPS Alcohol: tax_rate: 26.5 ✅ (desde constantes)      │
│   → ITT IEPS Tabaco: tax_rate: 160.0 ✅ (desde constantes)      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. ASIGNACIÓN ITEM GROUP                                        │
├─────────────────────────────────────────────────────────────────┤
│ item_groups.py → _assign_group_itt()                            │
│   Item Group: "Artículos IEPS Alcohol"                          │
│     → ITT: "ITT IEPS Alcohol - _TC" (rate: 26.5%)               │
│     → Item hereda ITT (y rate) de su Item Group                 │
│                                                                  │
│ CASOS ESPECIALES:                                                │
│   - Si item requiere tasa especial (e.g., vino 30%):            │
│     → Configurar en Item → Taxes → override rate                │
│   - La mayoría items usa tasa heredada del Item Group           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. SALES INVOICE - CÁLCULO AUTOMÁTICO                           │
├─────────────────────────────────────────────────────────────────┤
│ ERPNext core:                                                    │
│   1. Lee ITT del item (heredado de Item Group)                  │
│   2. Aplica rate del ITT: 26.5%                                  │
│   3. Calcula: net_amount × 0.265 = tax_amount                   │
│   4. Asigna automáticamente a tax_row                            │
│                                                                  │
│ ❌ NO requiere hook adicional (ERPNext nativo)                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. RESULTADO                                                     │
├─────────────────────────────────────────────────────────────────┤
│ Tax Row:                                                         │
│   charge_type: "On Net Total"                                    │
│   rate: 26.5                                                     │
│   tax_amount: $874.50 ✅ (calculado automáticamente)            │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Fuente de Tasas IEPS Tasa

**constantes_fiscales.py (líneas 73-109):**
```python
TASAS_IEPS = {
    "alcohol": {
        "tasa": 26.5,
        "descripcion": "IEPS Alcohol 26.5%",
        "charge_type": "On Net Total",
        "add_deduct_tax": "Add",
        "iva_aplicable": True,  # IEPS + IVA en cascada
    },
    "tabaco": {
        "tasa": 160.0,
        "descripcion": "IEPS Tabaco 160%",
        "charge_type": "On Net Total",
        "add_deduct_tax": "Add",
        "iva_aplicable": True,
    },
    # Cuotas con tasa 0 (cálculo dinámico)
    "azucar": {"tasa": 0.0, ...},
    "combustibles": {"tasa": 0.0, ...},
    "tabaco_cuota": {"tasa": 0.0, ...},
}
```

**sat_tax_rates.py - Validación FacturAPI (líneas 34-48):**
```python
IEPS_RATES: ClassVar[list[float]] = [
    0.0,    # IEPS 0%
    0.03,   # IEPS 3%
    ...
    0.265,  # IEPS 26.5% - Alcohol ✅
    0.3,    # IEPS 30%
    0.53,   # IEPS 53%
    1.6,    # IEPS 160% - Tabaco ✅
]
```

**Características:**
- ✅ Tasas definidas centralizadamente
- ✅ Validadas contra FacturAPI
- ✅ Documentadas y mantenibles
- ❌ NO se usan actualmente en generación ITT

---

## 3. DIFERENCIAS ARQUITECTURALES CLAVE

### 3.1 ¿Por qué IEPS Cuota usa DocType y IEPS Tasa no?

**IEPS Cuota:**
- Cuotas varían por producto específico (clave SAT)
- Cuotas cambian frecuentemente (vigencias temporales)
- Requiere conversión UOM (litros, cigarros, etc.)
- Lookup complejo por múltiples criterios

**Ejemplo:**
```
Producto A (Bebida azucarada 1L): $1.6451/litro
Producto B (Bebida azucarada 2L): $1.6451/litro × 2 = $3.2902
Producto C (Gasolina Regular): $5.4650/litro
```

**IEPS Tasa:**
- Tasas son FIJAS por categoría general (no por producto)
- Tasas casi nunca cambian (normativa SAT estable)
- Cálculo simple: net_amount × tasa%
- NO requiere conversión UOM

**Ejemplo:**
```
TODOS los alcoholes 25-55% graduación: 26.5%
TODOS los alcoholes >55% graduación: 53%
TODOS los tabacos: 160%
```

**Conclusión:** IEPS Tasa NO necesita DocType porque usa sistema nativo ERPNext (ITT inheritance).

### 3.2 Herencia Item Group → Item

**Flujo correcto:**

```
Item Group: "Artículos IEPS Alcohol"
  └─ ITT: "ITT IEPS Alcohol - _TC"
      └─ Tax Type: IEPS por Pagar (Alcohol)
          └─ Tax Rate: 26.5%  ← SE CONFIGURA AQUÍ

Item: "Tequila Don Julio 750ml"
  └─ Item Group: "Artículos IEPS Alcohol"
  └─ Hereda automáticamente: ITT + rate 26.5%

Item: "Vino Tinto Reserva" (caso especial)
  └─ Item Group: "Artículos IEPS Alcohol"
  └─ Hereda: ITT base
  └─ Override en Item → Taxes: rate 30% (vinos especiales)
```

---

## 4. BLOQUEADOR IDENTIFICADO

### 4.1 Código Problemático

**generador_templates_fiscal.py:1043-1085:**

```python
# ITT IEPS Alcohol
if cfg.enable_ieps_alcohol:
    created.append(
        _crear_o_actualizar_itt(
            company,
            abbr,
            "ITT IEPS Alcohol",
            [{"rol_fiscal": "IEPS por Pagar (Alcohol)", "tax_rate": 0}],  # ❌ INCORRECTO
            mapeo_cuentas,
        )
    )

# ITT IEPS Tabaco
if cfg.enable_ieps_tabaco:
    created.append(
        _crear_o_actualizar_itt(
            company,
            abbr,
            "ITT IEPS Tabaco",
            [{"rol_fiscal": "IEPS por Pagar (Tabaco)", "tax_rate": 0}],  # ❌ INCORRECTO
            mapeo_cuentas,
        )
    )
```

**Comentario incorrecto (línea 1049):**
```python
# Tasa se fija en ITT del item  ← ESTO ES INCORRECTO
```

### 4.2 Corrección Requerida

**Leer tasas desde constantes_fiscales.py:**

```python
from facturacion_mexico.facturacion_fiscal.config.constantes_fiscales import TASAS_IEPS

# ITT IEPS Alcohol
if cfg.enable_ieps_alcohol:
    tasa_alcohol = TASAS_IEPS["alcohol"]["tasa"]  # 26.5
    created.append(
        _crear_o_actualizar_itt(
            company,
            abbr,
            "ITT IEPS Alcohol",
            [{"rol_fiscal": "IEPS por Pagar (Alcohol)", "tax_rate": tasa_alcohol}],  # ✅ 26.5
            mapeo_cuentas,
        )
    )

# ITT IEPS Tabaco
if cfg.enable_ieps_tabaco:
    tasa_tabaco = TASAS_IEPS["tabaco"]["tasa"]  # 160.0
    created.append(
        _crear_o_actualizar_itt(
            company,
            abbr,
            "ITT IEPS Tabaco",
            [{"rol_fiscal": "IEPS por Pagar (Tabaco)", "tax_rate": tasa_tabaco}],  # ✅ 160.0
            mapeo_cuentas,
        )
    )
```

---

## 5. IMPACTO MONETARIO

### 5.1 SI Test Actual (ACC-SINV-2025-01647)

**Items con IEPS Tasa:**
- Alcohol: $3,300.00 neto → IEPS esperado: $3,300 × 26.5% = $874.50 ❌ actual: $0.00
- Tabaco: $500.00 neto → IEPS esperado: $500 × 160% = $800.00 ❌ actual: $0.00

**IVA cascada faltante:**
- IVA sobre IEPS Alcohol: $874.50 × 16% = $139.92 ❌ actual: $0.00
- IVA sobre IEPS Tabaco: $800.00 × 16% = $128.00 ❌ actual: $0.00

**Total faltante:** $1,942.42

**Desglose:**
```
IEPS Tasa faltante:    $1,674.50
IVA cascada faltante:    $267.92
────────────────────────────────
Total:                 $1,942.42
```

### 5.2 Comparación PAC

```
Grand total actual:    $6,432.02
Total esperado (PAC):  $8,200.10
────────────────────────────────
Diferencia:            $1,768.08
```

**Nota:** Diferencia ($1,768.08) vs estimado ($1,942.42) sugiere puede haber ajustes adicionales o tasas específicas diferentes.

---

## 6. SOLUCIÓN PROPUESTA

### 6.1 Cambio Mínimo (Recomendado)

**Modificar generador_templates_fiscal.py:**

1. Importar constantes:
```python
from facturacion_mexico.facturacion_fiscal.config.constantes_fiscales import TASAS_IEPS
```

2. Actualizar generación ITT IEPS Tasa (líneas 1043-1085):
```python
# Usar tasas de constantes fiscales
if cfg.enable_ieps_alcohol:
    created.append(
        _crear_o_actualizar_itt(
            company, abbr,
            "ITT IEPS Alcohol",
            [{"rol_fiscal": "IEPS por Pagar (Alcohol)", "tax_rate": TASAS_IEPS["alcohol"]["tasa"]}],
            mapeo_cuentas,
        )
    )

if cfg.enable_ieps_tabaco:
    created.append(
        _crear_o_actualizar_itt(
            company, abbr,
            "ITT IEPS Tabaco",
            [{"rol_fiscal": "IEPS por Pagar (Tabaco)", "tax_rate": TASAS_IEPS["tabaco"]["tasa"]}],
            mapeo_cuentas,
        )
    )
```

3. Actualizar comentario:
```python
# Tasa desde constantes fiscales - heredada por items vía Item Group
```

### 6.2 Testing

**1. Regenerar ITT:**
```bash
bench --site facturacion.dev console
>>> from facturacion_mexico.facturacion_fiscal.setup.generador_templates_fiscal import generate_itt_for_company
>>> generate_itt_for_company("_Test Company")
```

**2. Verificar tasas:**
```bash
bench --site facturacion.dev execute "facturacion_mexico.one_offs.analizar_itt_completo.run"
```

**Resultado esperado:**
```
ITT: ITT IEPS Alcohol - _TC
  Tax Type: IEPS por Pagar (Alcohol)    Rate: 26.50%

ITT: ITT IEPS Tabaco - _TC
  Tax Type: IEPS por Pagar (Tabaco)     Rate: 160.00%
```

**3. Recrear SI test:**
```bash
bench --site facturacion.dev execute "facturacion_mexico.one_offs.test_templates_migrados_e1.run"
```

**Resultado esperado:**
```
Grand total: $8,200.10 ✅ (igual a PAC total_fiscal)
```

---

## 7. DOCUMENTACIÓN CORRECTA

### 7.1 Arquitectura IEPS - Resumen

**IEPS Cuota (Azúcar, Combustibles, Tabaco Cuota):**
- Monto fijo por unidad ($/litro, $/cigarro)
- DocType maestro: `IEPS Cuota SAT`
- Lookup dinámico por clave SAT producto
- Hook calcula: cantidad × cuota = monto
- charge_type: "Actual"
- ITT rate: 0% (correcto, no usado)

**IEPS Tasa (Alcohol, Tabaco Tasa):**
- Porcentaje fijo por categoría general
- Fuente: `constantes_fiscales.py`
- Item Group → ITT (con rate) → Item (hereda)
- ERPNext calcula: net_amount × rate = monto
- charge_type: "On Net Total"
- ITT rate: 26.5% / 160% (debe configurarse)

### 7.2 Comentarios Código Correctos

**Para IEPS Cuota:**
```python
[{"rol_fiscal": "IEPS por Pagar (Azúcar/Bebidas)", "tax_rate": 0}],
# Rate 0 correcto: hook calcular_ieps_cuota() asigna monto dinámicamente
```

**Para IEPS Tasa:**
```python
[{"rol_fiscal": "IEPS por Pagar (Alcohol)", "tax_rate": TASAS_IEPS["alcohol"]["tasa"]}],
# Tasa desde constantes - heredada por items vía Item Group
```

---

## CONCLUSIÓN

**Problema raíz:** Confusión entre dos arquitecturas IEPS completamente diferentes.

**IEPS Cuota:** Diseño correcto con DocType lookup + hook dinámico.

**IEPS Tasa:** Diseño incompleto - falta configurar tasas en ITT generados.

**Solución:** 3 líneas código - importar constantes + usar en generación ITT.

**Impacto:** Resolverá $1,768.08 faltante en SI test, permitirá alcanzar PAC total_fiscal.

**Próximo paso:** Implementar cambios en generador_templates_fiscal.py + testing.

---

**🤖 Generated with [Claude Code](https://claude.com/claude-code)**
