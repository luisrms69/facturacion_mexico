# Reporte Completo: Implementación E4 - Arquitectura IEPS Cuota con ERPNext Nativo

**Fecha:** 2025-10-27
**Proyecto:** Facturación México - Sistema IEPS
**Objetivo:** Migrar cálculo IEPS de hooks manuales a cálculo 100% nativo ERPNext

---

## 1. CONTEXTO DEL PROYECTO

### 1.1 Objetivo E4
Migrar sistema de cálculo IEPS de arquitectura con hooks manuales (Pre-E4) a arquitectura que usa funcionalidad nativa de ERPNext (E4).

**Pre-E4 (Legacy):**
- STCT con `charge_type="Actual"`
- Hooks calculaban TODO manualmente
- Hooks mutaban valores post-submit
- Inestable, requería workarounds

**E4 (Target):**
- STCT con `charge_type="On Item Quantity"`
- ERPNext calcula TODO nativamente
- Sin mutaciones manuales
- Estable, determinista

### 1.2 Tipos de IEPS en México

**IEPS TASA (%):**
- Alcohol: 26.5%
- Tabaco: 160%
- Base de cálculo: monto neto del item
- Fórmula: `tax_amount = (tasa/100) × net_amount`

**IEPS CUOTA ($/unidad):**
- Bebidas azucaradas: $1.27/litro
- Combustibles: $5.49/litro (varía por tipo)
- Tabaco: $0.35/pieza (ADICIONAL a la tasa)
- Base de cálculo: cantidad del item
- Fórmula: `tax_amount = cuota × qty × conversion_factor`

---

## 2. ARQUITECTURA ACTUAL (ESTADO AL 2025-10-27)

### 2.1 STCT (Sales Taxes and Charges Template)

**Configuración:**
```
STCT: "IVA Nacional - IEPS - _TC"
  [4] IEPS Azúcar/Bebidas - Cuota (via ITT)
      charge_type: "On Item Quantity"
      rate: 0.0
      account_head: "2117002 - IEPS Azucar Bebidas - _TC"

  [6] IEPS Combustibles - Cuota (via ITT)
      charge_type: "On Item Quantity"
      rate: 0.0
      account_head: "2117003 - IEPS Combustibles - _TC"

  [10] IEPS Tabaco - Cuota (via ITT)
       charge_type: "On Item Quantity"
       rate: 0.0
       account_head: "2117005 - IEPS Tabaco Cuota - _TC"
```

**Nota:** `rate=0.0` es correcto como placeholder. Rates reales vienen de ITT o se calculan dinámicamente.

### 2.2 ITT (Item Tax Template)

**ITTs IEPS existentes:**

```
ITT IEPS Alcohol - _TC
  └─ 2117001 - IEPS Alcohol - _TC: tax_rate=26.5
     Tipo: TASA (%)
     ✅ Correcto: tasa fija 26.5%

ITT IEPS Tabaco - _TC
  └─ 2117004 - IEPS Tabaco - _TC: tax_rate=160.0
     Tipo: TASA (%)
     ✅ Correcto: tasa fija 160%

ITT IEPS Azúcar - _TC
  └─ 2117002 - IEPS Azucar Bebidas - _TC: tax_rate=0.0
     Tipo: CUOTA ($/unidad)
     ✅ Correcto: placeholder 0.0 (cuota dinámica)

ITT IEPS Combustibles - _TC
  └─ 2117003 - IEPS Combustibles - _TC: tax_rate=0.0
     Tipo: CUOTA ($/unidad)
     ✅ Correcto: placeholder 0.0 (cuota dinámica)
```

**Prioridad ERPNext nativa:**
1. Item.item_defaults[].item_tax_template (nivel item)
2. Item Group.item_group_defaults[].item_tax_template (nivel grupo)
3. STCT.rate (fallback documento)

### 2.3 Tabla IEPS Cuota SAT

**Estructura:**
```sql
CREATE TABLE `tabIEPS Cuota SAT` (
  company VARCHAR(140),
  clave_prod_serv VARCHAR(8),     -- ClaveProdServ SAT
  cuenta_ieps VARCHAR(140),        -- Cuenta contable IEPS
  cuota DECIMAL(18,6),             -- Cuota en $/UOM
  uom VARCHAR(50),                 -- UOM canónica (LTR, H87, etc)
  vigencia_desde DATE,
  vigencia_hasta DATE
)
```

**Datos actuales:**
```
Clave SAT: 50202301 (Bebidas azucaradas)
  Cuenta: 2117002 - IEPS Azucar Bebidas - _TC
  Cuota: $1.270/LTR - Litro
  Vigencia: 2025-01-01

Clave SAT: 15101514 (Gasolina Magna)
  Cuenta: 2117003 - IEPS Combustibles - _TC
  Cuota: $5.490/LTR - Litro
  Vigencia: 2025-01-01

Clave SAT: 53131604 (Tabaco)
  Cuenta: 2117005 - IEPS Tabaco Cuota - _TC
  Cuota: $0.350/H87 - Pieza
  Vigencia: 2025-01-01
```

### 2.4 Items de Prueba

**Configuración actual:**
```
TEST-IEPS-AZUCAR-001
  Item Group: productos genericos azucar
  Clave SAT: 50202301
  Stock UOM: H87 - Pieza
  Conversión UOM: 1 Pieza = 0.6 Litros
  ITT asignado: NINGUNO (usa del grupo)

TEST-IEPS-COMBUSTIBLES-001
  Item Group: combustibles generic
  Clave SAT: 15101514
  Stock UOM: LTR - Litro
  Conversión UOM: 1 Litro = 1 Litro
  ITT asignado: NINGUNO (usa del grupo)

TEST-IEPS-TABACO-001
  Item Group: articulos tabaco sub
  Clave SAT: 53131604
  Stock UOM: XPA - Cajetilla
  Conversión UOM: 1 Cajetilla = 20 Piezas
  ITT asignado: NINGUNO (usa del grupo)
```

### 2.5 Hooks Actuales

**Hooks ACTIVOS:**
```python
"Sales Invoice": {
    "before_validate": "...sales_invoice_automated_tax.before_validate",
    "validate": "...sales_invoice_automated_tax.validate",
    "before_save": [
        # TODOS COMENTADOS E4
    ]
}
```

**before_validate:**
- NO manipula impuestos
- Solo setea: cost_center, branch, price_list

**validate:**
- NO manipula impuestos
- Solo valida: cost_center obligatorio, ClaveProdServ SAT

**before_save:** ❌ TODOS comentados:
- `calcular_ieps_cuota` - DISABLED
- `ajustar_base_iva_combustibles` - DISABLED
- `corregir_ieps_cuota_final` - DISABLED

---

## 3. INVESTIGACIÓN CÓDIGO FUENTE ERPNEXT

### 3.1 Flujo Nativo "On Item Quantity"

**Paso 1: Construir item_tax_map**

```python
# erpnext/stock/get_item_details.py:766
def get_item_tax_map(company, item_tax_template):
    item_tax_map = {}
    if item_tax_template:
        template = frappe.get_doc('Item Tax Template', item_tax_template)
        for d in template.taxes:
            item_tax_map[d.tax_type] = d.tax_rate  # ← LEE tax_rate del ITT
    return item_tax_map
```

**Resultado:** `{cuenta_impuesto: tax_rate}` por cada item

**Paso 2: Obtener tax_rate con prioridad**

```python
# erpnext/controllers/taxes_and_totals.py:347
def _get_tax_rate(self, tax, item_tax_map):
    if tax.account_head in item_tax_map:
        return item_tax_map[tax.account_head]  # ← PRIORIDAD 1: ITT
    else:
        return tax.rate  # ← FALLBACK: STCT
```

**Prioridad:** ITT.tax_rate > STCT.rate

**Paso 3: Calcular tax_amount**

```python
# erpnext/controllers/taxes_and_totals.py:516
elif tax.charge_type == 'On Item Quantity':
    current_tax_amount = tax_rate × item.qty  # ← FÓRMULA NATIVA
```

**IMPORTANTE:** NO usa `conversion_factor` automáticamente. El `tax_rate` debe estar ya en la UOM del item en el SI.

### 3.2 Cómo ERPNext Lee item_tax_rate (JSON)

ERPNext puede leer rates desde 2 fuentes:

**Fuente 1: ITT Document (persistente)**
```python
Item.item_tax_template → "ITT IEPS Azúcar - _TC"
ITT.taxes[0].tax_rate = 1.27  # ← Persiste en DB
```

**Fuente 2: item.item_tax_rate (JSON temporal)**
```python
item.item_tax_rate = '{"2117002 - IEPS Azucar Bebidas - _TC": 1.27}'
# ← JSON temporal en SI, NO persiste en Item
```

**Prioridad:** `item.item_tax_rate` (JSON) > ITT Document

### 3.3 update_item_tax_map()

```python
# erpnext/controllers/taxes_and_totals.py:143
def update_item_tax_map(self):
    for item in self._items:
        item.item_tax_rate = get_item_tax_map(
            self.doc.company,
            item.item_tax_template,
            as_json=True
        )
```

Esta función se ejecuta AUTOMÁTICAMENTE en el lifecycle:
- `validate()` → `calculate_taxes_and_totals()` → `update_item_tax_map()`

Construye `item.item_tax_rate` desde ITT del item.

---

## 4. PROBLEMA ACTUAL

### 4.1 Síntoma

**SI creado con items IEPS:**
```
SI: ACC-SINV-2025-01682
Items:
  - TEST-IEPS-AZUCAR-001: 20 piezas × $20 = $400
  - TEST-IEPS-COMBUSTIBLES-001: 40 litros × $26 = $1,040
  - TEST-IEPS-TABACO-001: 10 cajetillas × $50 = $500

Tax rows IEPS Cuota:
  [4] IEPS Azúcar: charge_type="On Item Quantity", rate=0.0, tax_amount=$0.00 ❌
  [6] IEPS Combustibles: charge_type="On Item Quantity", rate=0.0, tax_amount=$0.00 ❌
  [10] IEPS Tabaco Cuota: charge_type="On Item Quantity", rate=0.0, tax_amount=$0.00 ❌

Grand Total: $8,020.82
ESPERADO: $8,255.66 (falta $234.84 de cuotas)
```

### 4.2 Causa Raíz

**Trazabilidad del rate=0.0:**

```
PASO 1: STCT
  Template "IVA Nacional - IEPS - _TC"
  Fila IEPS Azúcar: rate = 0.0 (placeholder)

PASO 2: ITT
  Item tiene: item_tax_template = "ITT IEPS Azúcar - _TC"
  ITT.tax_rate = 0.0 (placeholder)
  ← SOBRESCRIBE rate del STCT

PASO 3: get_item_tax_map()
  Construye: {"2117002 - IEPS Azucar Bebidas - _TC": 0.0}
  item.item_tax_rate = JSON con rate=0.0

PASO 4: ERPNext calcula
  tax_rate = _get_tax_rate() = 0.0 (viene de ITT)
  tax_amount = 0.0 × 20 qty = $0.00 ❌
```

**Problema:** ITT tiene `tax_rate=0.0` hardcoded, cuando debería tener cuota vigente de tabla IEPS Cuota SAT.

### 4.3 Por Qué NO se Puede Hardcodear en ITT

**Cuotas son DINÁMICAS:**
- Cambian por vigencia (SAT actualiza anualmente)
- Ejemplo: $1.27/litro hoy, puede ser $1.35/litro en 2026
- No se puede hardcodear valor fijo en ITT

**Tasas son ESTÁTICAS:**
- Alcohol: 26.5% (no cambia frecuentemente)
- Tabaco: 160% (no cambia frecuentemente)
- Sí se puede hardcodear en ITT ✅

---

## 5. RESTRICCIÓN IMPORTANTE: CUOTA POR PRODUCTO

### 5.1 Problema

**Configuración actual:** Busca cuota por `clave_prod_serv` (ClaveProdServ SAT)

```sql
SELECT cuota FROM `tabIEPS Cuota SAT`
WHERE clave_prod_serv = '15101514'  -- Gasolina Magna
```

**PERO:** Aunque claves SAT son únicas por tipo de combustible:
- Gasolina Magna: 15101514
- Gasolina Premium: 15101515
- Diesel: 15101505

**Necesitamos cuota a nivel PRODUCTO**, no solo ClaveProdServ, por:

1. **Control granular:** Cada producto tiene configuración específica
2. **Histórico:** Rastrear cambios por producto
3. **Auditoría:** Trazabilidad detallada
4. **Flexibilidad:** Posibles variaciones regionales/comerciales

### 5.2 Caso Tabaco

**Tabaco tiene AMBOS:**
- IEPS Tasa: 160% del monto neto (fijo en ITT)
- IEPS Cuota: $0.35/pieza (dinámico de tabla)

**Necesitamos:** Sistema que maneje AMBOS tipos en mismo producto.

---

## 6. OPCIONES DE SOLUCIÓN

### 6.1 OPCIÓN A: Hook Actualiza item.item_tax_rate (JSON) ⭐ RECOMENDADA

**Arquitectura:**
```python
# Hook: before_validate (ANTES de calculate_taxes_and_totals)
for item in doc.items:
    if not item.fm_producto_servicio_sat:
        continue

    # Leer cuota vigente de tabla IEPS Cuota SAT
    cuotas = frappe.db.sql("""
        SELECT cuenta_ieps, cuota, uom
        FROM `tabIEPS Cuota SAT`
        WHERE company = %s
          AND clave_prod_serv = %s
          AND vigencia_desde <= %s
          AND (vigencia_hasta IS NULL OR vigencia_hasta >= %s)
    """, (doc.company, item.fm_producto_servicio_sat, doc.posting_date, doc.posting_date))

    # Construir/actualizar JSON item_tax_rate
    tax_map = json.loads(item.item_tax_rate or '{}')

    for cuota_row in cuotas:
        cuenta = cuota_row.cuenta_ieps
        cuota = cuota_row.cuota
        uom_base = cuota_row.uom

        # Aplicar conversión UOM si necesario
        if item.uom != uom_base:
            conversion_data = get_conversion_factor(item.item_code, uom_base)
            cuota_converted = cuota * conversion_data.conversion_factor
        else:
            cuota_converted = cuota

        # Actualizar JSON con cuota convertida
        tax_map[cuenta] = cuota_converted

    item.item_tax_rate = json.dumps(tax_map)

# ERPNext usa ese JSON para calcular TODO nativamente
# No llamar calculate_taxes_and_totals() - ERPNext lo hace automático
```

**Ventajas:**
- ✅ No crea/modifica ITT documents
- ✅ Cuota dinámica (se recalcula cada SI)
- ✅ ERPNext calcula nativamente
- ✅ Soporta TASA y CUOTA simultáneas (tabaco)
- ✅ Conversión UOM correcta
- ✅ Consistente con arquitectura actual

**Desventajas:**
- ⚠️ JSON temporal se pierde si usuario recarga (debe recalcular)
- ⚠️ Hook necesario (pero MÍNIMO, solo actualiza JSON)

### 6.2 OPCIÓN B: ITT Específico por Producto

**Arquitectura:**
- Crear ITT único por cada producto con IEPS
- Ejemplo: "ITT IEPS - TEST-IEPS-AZUCAR-001"
- Actualizar tax_rate cuando cambia vigencia

**Ventajas:**
- ✅ ITT persiste
- ✅ Visible en UI

**Desventajas:**
- ❌ Muchos ITTs (uno por producto)
- ❌ Difícil mantener actualizaciones vigencia
- ❌ No escala

### 6.3 OPCIÓN C: Custom Field en Item

**Arquitectura:**
- Agregar: `Item.fm_ieps_cuota_vigente = 5.49`
- Leer en hook y poner en item_tax_rate

**Ventajas:**
- ✅ Datos en Item directamente

**Desventajas:**
- ❌ No mantiene histórico vigencias
- ❌ Duplica info de tabla IEPS Cuota SAT
- ❌ Difícil actualizar masivamente

---

## 7. FLUJO PROPUESTO (OPCIÓN A)

### 7.1 Diagrama de Secuencia

```
Usuario crea SI
  ↓
ERPNext: before_validate
  ↓
HOOK: before_validate
  Para cada item:
    - Leer Item.fm_producto_servicio_sat
    - Buscar cuotas en tabla IEPS Cuota SAT
    - Aplicar conversión UOM si necesario
    - Actualizar item.item_tax_rate JSON
  ↓
ERPNext: validate → calculate_taxes_and_totals()
  ↓
ERPNext: update_item_tax_map()
  - Lee item.item_tax_rate (ya actualizado por hook)
  - Construye item_tax_map
  ↓
ERPNext: Calcula impuestos nativamente
  - Para "On Item Quantity":
    tax_amount = tax_rate × item.qty
  ↓
SI Draft con impuestos correctos ✅
```

### 7.2 Pseudocódigo Hook

```python
def before_validate(doc, method=None):
    """
    Hook MÍNIMO: Actualiza item.item_tax_rate con cuotas vigentes.
    ERPNext calcula TODO lo demás nativamente.
    """
    if doc.doctype != "Sales Invoice":
        return

    if not doc.items or not doc.taxes:
        return

    for item in doc.items:
        # Skip si no tiene Clave SAT
        if not item.get("fm_producto_servicio_sat"):
            continue

        # Leer cuotas vigentes de tabla IEPS Cuota SAT
        cuotas = obtener_cuotas_vigentes(
            company=doc.company,
            clave_sat=item.fm_producto_servicio_sat,
            fecha=doc.posting_date
        )

        if not cuotas:
            continue

        # Construir/actualizar JSON item_tax_rate
        tax_map = json.loads(item.item_tax_rate or '{}')

        for cuota_row in cuotas:
            cuenta = cuota_row.cuenta_ieps
            cuota = cuota_row.cuota
            uom_base = cuota_row.uom

            # Aplicar conversión UOM
            cuota_converted = convertir_cuota_a_uom_item(
                cuota=cuota,
                uom_base=uom_base,
                item_code=item.item_code,
                item_uom=item.uom
            )

            # Actualizar JSON
            tax_map[cuenta] = cuota_converted

        # Guardar JSON actualizado
        item.item_tax_rate = json.dumps(tax_map)

    # NO llamar calculate_taxes_and_totals()
    # ERPNext lo hace automáticamente en validate()
```

### 7.3 Funciones Helper

```python
def obtener_cuotas_vigentes(company, clave_sat, fecha):
    """Obtener cuotas IEPS vigentes de tabla."""
    return frappe.db.sql("""
        SELECT
            cuenta_ieps,
            cuota,
            uom
        FROM `tabIEPS Cuota SAT`
        WHERE company = %s
          AND clave_prod_serv = %s
          AND vigencia_desde <= %s
          AND (vigencia_hasta IS NULL OR vigencia_hasta >= %s)
          AND docstatus < 2
    """, (company, clave_sat, fecha, fecha), as_dict=True)


def convertir_cuota_a_uom_item(cuota, uom_base, item_code, item_uom):
    """Convertir cuota de UOM base a UOM del item en SI."""
    if uom_base == item_uom:
        return cuota

    # Obtener factor conversión
    conversion_data = get_conversion_factor(item_code, uom_base)
    factor = conversion_data.get("conversion_factor", 0)

    if factor <= 0:
        frappe.throw(
            f"Item {item_code}: Falta conversión UOM '{item_uom}' → '{uom_base}'"
        )

    # Convertir cuota
    return cuota * factor
```

---

## 8. PRUEBAS Y VALIDACIÓN

### 8.1 Caso de Prueba 1: Azúcar (Solo Cuota)

**Input:**
```
Item: TEST-IEPS-AZUCAR-001
  Qty: 20 piezas (H87)
  Rate: $20/pieza
  Clave SAT: 50202301

Tabla IEPS Cuota SAT:
  Cuota: $1.27/litro (LTR)

Conversión UOM:
  1 pieza = 0.6 litros
```

**Cálculo esperado:**
```
Cuota convertida = $1.27 × 0.6 = $0.762/pieza
tax_amount = $0.762 × 20 piezas = $15.24
```

**Resultado esperado:**
```
SI taxes:
  IEPS Azúcar Cuota: $15.24 ✅
  IVA sobre IEPS Azúcar: $2.44 ✅
Grand Total incluye $15.24 ✅
```

### 8.2 Caso de Prueba 2: Tabaco (Tasa + Cuota)

**Input:**
```
Item: TEST-IEPS-TABACO-001
  Qty: 10 cajetillas (XPA)
  Rate: $50/cajetilla
  Net Amount: $500
  Clave SAT: 53131604

ITT IEPS Tabaco:
  IEPS Tasa: 160% (en ITT)

Tabla IEPS Cuota SAT:
  Cuota: $0.35/pieza (H87)

Conversión UOM:
  1 cajetilla = 20 piezas
```

**Cálculo esperado:**
```
IEPS Tasa = $500 × 160% = $800.00
Cuota convertida = $0.35/pieza × 20 piezas/cajetilla = $7.00/cajetilla
IEPS Cuota = $7.00 × 10 cajetillas = $70.00
Total IEPS Tabaco = $800.00 + $70.00 = $870.00
```

**Resultado esperado:**
```
SI taxes:
  IEPS Tabaco Tasa: $800.00 ✅
  IEPS Tabaco Cuota: $70.00 ✅
  IVA sobre IEPS Tabaco: $139.20 ✅ ($870 × 16%)
Grand Total incluye ambos IEPS ✅
```

### 8.3 Caso de Prueba 3: Combustibles (Solo Cuota)

**Input:**
```
Item: TEST-IEPS-COMBUSTIBLES-001
  Qty: 40 litros (LTR)
  Rate: $26/litro
  Clave SAT: 15101514

Tabla IEPS Cuota SAT:
  Cuota: $5.49/litro (LTR)

Conversión UOM:
  1 litro = 1 litro (sin conversión)
```

**Cálculo esperado:**
```
Cuota convertida = $5.49 (sin conversión)
tax_amount = $5.49 × 40 litros = $219.60
```

**Resultado esperado:**
```
SI taxes:
  IEPS Combustibles Cuota: $219.60 ✅
  IVA sobre IEPS: $0.00 (combustibles NO integran base IVA) ✅
Grand Total incluye $219.60 ✅
```

---

## 9. PREGUNTAS PARA DECISIÓN

### 9.1 Arquitectura

**Q1:** ¿Estamos de acuerdo con OPCIÓN A (Hook actualiza item.item_tax_rate)?
- Alternativa: OPCIÓN B (ITT por producto)
- Alternativa: OPCIÓN C (Custom field en Item)

**Q2:** ¿Hook en `before_validate` o en `validate`?
- before_validate: Se ejecuta ANTES de validaciones ERPNext
- validate: Se ejecuta DESPUÉS de validaciones básicas

### 9.2 Conversión UOM

**Q3:** ¿Cómo manejar UOM cuando no hay conversión configurada?
- Opción A: Throw error (obliga configurar)
- Opción B: Asumir factor 1.0 (permisivo)
- Opción C: Skip item (silencioso)

**Q4:** ¿Validar que UOM base de cuota coincide con UOM del item?
- Si hay desajuste, ¿error o intentar convertir?

### 9.3 Tabla IEPS Cuota SAT

**Q5:** ¿Es suficiente buscar por `clave_prod_serv`?
- O necesitamos campo adicional `item_code` para granularidad producto

**Q6:** ¿Cómo manejar múltiples vigencias?
- Usar fecha SI para determinar cuota vigente ✅
- ¿Permitir override manual?

### 9.4 Integración IVA

**Q7:** ¿Hook debe manejar IVA sobre IEPS Cuota?
- Opción A: ERPNext calcula nativamente (filas "On Previous Row Amount")
- Opción B: Hook también configura IVA

**Q8:** ¿Hook debe manejar ajuste base IVA combustibles?
- (IEPS combustibles NO integra base IVA por LIEPS Art. 2-A)

---

## 10. ARCHIVOS RELEVANTES

### 10.1 Código Fuente ERPNext
```
erpnext/controllers/taxes_and_totals.py
  - Línea 347: _get_tax_rate()
  - Línea 516: Cálculo "On Item Quantity"
  - Línea 143: update_item_tax_map()

erpnext/stock/get_item_details.py
  - Línea 766: get_item_tax_map()
```

### 10.2 Código App Facturación México
```
facturacion_mexico/hooks.py
  - Línea 342-358: doc_events Sales Invoice

facturacion_mexico/hooks_handlers/sales_invoice_automated_tax.py
  - before_validate() - Setea cost_center, branch, price_list
  - validate() - Validaciones obligatorias

facturacion_mexico/hooks_handlers/sales_invoice_ieps.py
  - calcular_ieps_cuota() - COMENTADO E4
  - ajustar_base_iva_combustibles() - COMENTADO E4
  - corregir_ieps_cuota_final() - COMENTADO E4
```

### 10.3 Documentos Relevantes
```
docs/development/REPORTE_COMPARACION_SI_TEST_VS_PAC.md
  - Historial completo investigación E4
  - Debugging hook legacy

docs/development/REPORTE_FINAL_IMPLEMENTACION_E4.md
  - Cambios implementados STCT/ITT
  - Verificación templates
```

---

## 11. ESTADO ACTUAL Y SIGUIENTE PASO

### 11.1 Estado

**✅ Completado:**
- STCT con charge_type="On Item Quantity"
- ITT con tax_rate correcto para TASA (Alcohol, Tabaco)
- ITT con tax_rate=0.0 placeholder para CUOTA (Azúcar, Combustibles)
- Tabla IEPS Cuota SAT con cuotas vigentes
- Items test con conversión UOM correcta
- Hooks manuales COMENTADOS
- Investigación código fuente ERPNext completa

**❌ Pendiente:**
- Implementar hook mínimo que actualiza item.item_tax_rate
- Testing funcional con SI draft
- Testing funcional con SI submitted
- Comparación vs PAC (delta ≤ $0.05)

### 11.2 Siguiente Paso

**DECISIÓN REQUERIDA:**
1. Aprobar OPCIÓN A (Hook actualiza item.item_tax_rate)
2. Responder preguntas sección 9
3. Implementar hook mínimo
4. Testing funcional

---

## 12. ANEXOS

### 12.1 Claves ClaveProdServ SAT Relevantes

```
Bebidas azucaradas: 50202301
Gasolina Magna: 15101514
Gasolina Premium: 15101515
Diesel: 15101505
Tabaco: 53131604
Alcohol: 24111501 (Cerveza), etc.
```

### 12.2 Cuentas Contables IEPS

```
2117001 - IEPS Alcohol - _TC
2117002 - IEPS Azucar Bebidas - _TC
2117003 - IEPS Combustibles - _TC
2117004 - IEPS Tabaco - _TC (Tasa)
2117005 - IEPS Tabaco Cuota - _TC (Cuota)
```

### 12.3 UOMs Canónicas SAT

```
LTR - Litro (Bebidas, Combustibles)
H87 - Pieza (Tabaco, otros)
XPA - Cajetilla (Tabaco - unidad comercial)
```

---

**Fecha reporte:** 2025-10-27 23:30
**Versión:** 1.0
**Preparado por:** Claude Code
**Status:** Esperando decisión arquitectónica
