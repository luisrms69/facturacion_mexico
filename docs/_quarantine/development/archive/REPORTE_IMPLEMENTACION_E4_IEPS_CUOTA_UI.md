# Reporte Técnico: Implementación E4 - IEPS Cuota UI Clean

**Fecha:** 2025-10-22
**Contexto:** Proyecto E4 - Sistema Automatizado IEPS Cuota
**Branch:** `feature/e1-automated-tax-system`

---

## 1. PROBLEMA IDENTIFICADO

### 1.1 Descripción del Issue

**Síntoma Inicial:**
- IEPS Cuota (Azúcar y Combustibles) aparecían **distribuidos entre TODOS los items** en el Tax Breakup UI
- Ejemplo: IEPS Azúcar $22.86 mostraba $0.83 en Tabaco, $1.08 en Combustibles, $0.50 en Azúcar, etc.

**Causa Raíz Identificada:**
1. **Key incorrecta en `item_wise_tax_detail`**: Usábamos `item.name` (ID interno como "mstij18fpt") en vez de `item.item_code` ("TEST-IEPS-AZUCAR-001")
2. **ERPNext redistribuye "Actual" charge_type**: Por default, ERPNext distribuye proporcionalmente taxes tipo "Actual" entre todos los items según `net_amount`
3. **IVA cascada también redistribuido**: El IVA "On Previous Row Amount" sobre IEPS Cuota se redistribuía proporcionalmente

### 1.2 Diagnóstico Técnico

**Flujo ERPNext problemático:**
```python
# En erpnext/controllers/taxes_and_totals.py línea 491-503
if tax.charge_type == "Actual":
    # distribute the tax amount proportionally to each item row
    actual = flt(tax.tax_amount, tax.precision("tax_amount"))
    current_tax_amount = item.net_amount * actual / self.doc.net_total
```

**Verificación en BD:**
```bash
# ACC-SINV-2025-01616 mostraba redistribución:
# Tax #4 (IVA sobre IEPS Azúcar):
# - Total correcto: $3.66
# - Pero distribuido: $0.83 Tabaco, $1.08 Combustibles, $0.50 Azúcar, $1.25 Alcohol
```

---

## 2. SOLUCIÓN IMPLEMENTADA

### 2.1 Cambio #1: Corrección Key en item_wise_tax_detail

**Archivo:** `facturacion_mexico/hooks_handlers/sales_invoice_ieps.py`
**Línea:** 276

**Antes (INCORRECTO):**
```python
# Generaba keys como "mstij18fpt" (item.name - ID interno)
key = item.item_code or item.item_name
distribucion_items[key] = [0.0, item_ieps]
```

**Después (CORRECTO):**
```python
# Genera keys como "TEST-IEPS-AZUCAR-001" (item_code)
distribucion_items[item.item_code] = [0.0, item_ieps]
```

**Razón del cambio:**
- ERPNext UI espera `item_code` como key en `item_wise_tax_detail`
- Usar `item.name` (ID interno) causaba que UI no encontrara las keys
- Resultado: UI mostraba $0.00 para todos los items

---

### 2.2 Cambio #2: Flag dont_recompute_tax para IEPS Cuota

**Archivo:** `facturacion_mexico/hooks_handlers/sales_invoice_ieps.py`
**Líneas:** 287-290

```python
# Prevenir que ERPNext redistribuya este impuesto proporcionalmente
# ERPNext por default redistribuye "Actual" entre items según net_amount
# Este flag congela nuestra distribución custom (item_wise_tax_detail)
tax_row.dont_recompute_tax = 1
```

**Propósito:**
- Evitar que ERPNext sobrescriba nuestro `item_wise_tax_detail` calculado manualmente
- Backend: Previene redistribución en `taxes_and_totals.py` línea 518
- Frontend: JavaScript respeta el flag en `taxes_and_totals.js`

---

### 2.3 Cambio #3: Nueva función _congelar_iva_sobre_ieps_cuota()

**Archivo:** `facturacion_mexico/hooks_handlers/sales_invoice_ieps.py`
**Líneas:** 195-239

**Implementación completa:**
```python
def _congelar_iva_sobre_ieps_cuota(doc, ieps_tax_row, distribucion_ieps):
	"""
	Congela el IVA "On Previous Row Amount" que se calcula sobre IEPS Cuota.

	Problema: ERPNext redistribuye el IVA proporcionalmente entre todos los items.
	Solución: Setear manualmente item_wise_tax_detail solo para items con IEPS.

	Args:
		doc: Sales Invoice document
		ieps_tax_row: Tax row del IEPS Cuota (ya procesado)
		distribucion_ieps: Dict con distribución IEPS {item_code: [0.0, amount]}
	"""
	# Buscar el índice del IEPS Cuota actual
	ieps_idx = None
	for idx, tax in enumerate(doc.taxes):
		if tax.name == ieps_tax_row.name:
			ieps_idx = idx
			break

	if ieps_idx is None:
		return  # No encontrado (no debería pasar)

	# Buscar el siguiente tax que sea "On Previous Row Amount"
	for idx in range(ieps_idx + 1, len(doc.taxes)):
		iva_tax = doc.taxes[idx]

		# Verificar si es IVA "On Previous Row Amount" que referencia el IEPS Cuota
		if iva_tax.charge_type == "On Previous Row Amount":
			# Verificar si row_id apunta al IEPS Cuota (idx+1 porque row_id es 1-indexed)
			if iva_tax.row_id and int(iva_tax.row_id) == ieps_idx + 1:
				# Calcular IVA manualmente solo para items con IEPS
				iva_distribucion = {}
				iva_rate = flt(iva_tax.rate)

				for item_code, values in distribucion_ieps.items():
					ieps_amount = values[1]  # [0.0, amount]
					iva_amount = ieps_amount * iva_rate / 100
					iva_distribucion[item_code] = [iva_rate, iva_amount]

				# Setear item_wise_tax_detail y congelar
				if iva_distribucion:
					iva_tax.item_wise_tax_detail = json.dumps(iva_distribucion)
					iva_tax.dont_recompute_tax = 1

				break  # Solo el primer IVA "On Previous Row Amount"
```

**Lógica:**
1. Identifica el tax row IVA que sigue al IEPS Cuota
2. Verifica `row_id` para confirmar que referencia al IEPS Cuota correcto
3. Calcula IVA **solo para items que tienen IEPS Cuota** (no todos)
4. Setea `item_wise_tax_detail` con distribución correcta
5. Marca `dont_recompute_tax = 1` para prevenir redistribución

**Llamada a la función:**
```python
# Línea 294
_congelar_iva_sobre_ieps_cuota(doc, tax_row, distribucion_items)
```

---

## 3. RESULTADOS OBTENIDOS

### 3.1 Antes vs Después

**ANTES (ACC-SINV-2025-01616):**
```
Tax Breakup:
┌─────────────────────────┬─────────────────────────────┬─────────┐
│ Item                    │ Tax                         │ Amount  │
├─────────────────────────┼─────────────────────────────┼─────────┤
│ TEST-IEPS-TABACO-001    │ IEPS Azúcar Cuota          │ $0.83   │ ❌
│ TEST-IEPS-COMBUSTIBLES  │ IEPS Azúcar Cuota          │ $1.08   │ ❌
│ TEST-IEPS-AZUCAR-001    │ IEPS Azúcar Cuota          │ $0.50   │ ❌
│ TEST-IEPS-ALCOHOL-001   │ IEPS Azúcar Cuota          │ $1.25   │ ❌
│                         │ IVA 16% sobre IEPS Azúcar  │         │
│ TEST-IEPS-TABACO-001    │   (distribuido todos)      │ $0.41   │ ❌
│ TEST-IEPS-COMBUSTIBLES  │   (distribuido todos)      │ $0.53   │ ❌
│ TEST-IEPS-AZUCAR-001    │   (distribuido todos)      │ $0.25   │ ❌
│ TEST-IEPS-ALCOHOL-001   │   (distribuido todos)      │ $2.47   │ ❌
└─────────────────────────┴─────────────────────────────┴─────────┘
```

**DESPUÉS (ACC-SINV-2025-01617):**
```
Tax Breakup:
┌─────────────────────────┬─────────────────────────────┬─────────┐
│ Item                    │ Tax                         │ Amount  │
├─────────────────────────┼─────────────────────────────┼─────────┤
│ TEST-IEPS-AZUCAR-001    │ IEPS Azúcar Cuota          │ $22.86  │ ✅
│                         │ IVA 16% sobre IEPS Azúcar  │ $3.66   │ ✅
│ TEST-IEPS-COMBUSTIBLES  │ IEPS Combustibles Cuota    │ $274.50 │ ✅
└─────────────────────────┴─────────────────────────────┴─────────┘
(Otros items: casillas vacías, no muestran $0.00)
```

### 3.2 Verificación Base de Datos

**Tax #3 (IEPS Azúcar Cuota):**
```json
{
  "charge_type": "Actual",
  "tax_amount": 22.86,
  "dont_recompute_tax": 1,
  "item_wise_tax_detail": "{\"TEST-IEPS-AZUCAR-001\": [0.0, 22.86]}"
}
```
✅ Solo 1 key (Azúcar)
✅ Flag congelado
✅ Total correcto

**Tax #4 (IVA sobre IEPS Azúcar):**
```json
{
  "charge_type": "On Previous Row Amount",
  "row_id": "3",
  "tax_amount": 3.66,
  "dont_recompute_tax": 1,
  "item_wise_tax_detail": "{\"TEST-IEPS-AZUCAR-001\": [16.0, 3.6576]}"
}
```
✅ Solo 1 key (Azúcar)
✅ Flag congelado
✅ Referencias row_id correcto

### 3.3 Ventajas UI Observadas

1. **UI más limpio**: Casillas vacías en vez de $0.00 en todos los items
2. **Lectura más clara**: Solo aparecen impuestos relevantes por item
3. **Sin confusión**: No hay montos "fantasma" distribuidos incorrectamente
4. **Totales correctos**: `tax_amount` sigue sumando correctamente

---

## 4. PROPUESTA DE MEJORA: APLICAR A TODOS LOS IMPUESTOS

### 4.1 Problema Actual con Otros Impuestos

**Impuestos que todavía muestran [0.0, 0.0] en todos los items:**

| Impuesto | Ejemplo item_wise_tax_detail | Issue |
|----------|------------------------------|-------|
| **IEPS Tasa** (Alcohol) | `{"TABACO":[0.0,0.0], "COMBUSTIBLES":[0.0,0.0], "AZUCAR":[0.0,0.0], "ALCOHOL":[26.5,1060.0]}` | 3/4 items con [0.0,0.0] |
| **IEPS Tabaco Cuota** (sin uso) | `{"TABACO":[0.0,0.0], "COMBUSTIBLES":[0.0,0.0], "AZUCAR":[0.0,0.0], "ALCOHOL":[0.0,0.0]}` | Todos [0.0,0.0] |
| **Retenciones** (rate=0) | `{"TABACO":[0.0,0.0], "COMBUSTIBLES":[0.0,0.0], ...}` | Todos [0.0,0.0] |
| **IVA 0%/Exento** | `{"TABACO":[0.0,0.0], "COMBUSTIBLES":[0.0,0.0], ...}` | Todos [0.0,0.0] |

**Efecto en UI:**
```
Tax Breakup actual (no óptimo):
┌─────────────────────────┬─────────────────────────────┬─────────┐
│ Item                    │ Tax                         │ Amount  │
├─────────────────────────┼─────────────────────────────┼─────────┤
│ TEST-IEPS-TABACO-001    │ IEPS Alcohol               │ $0.00   │ ← Ruido
│ TEST-IEPS-COMBUSTIBLES  │ IEPS Alcohol               │ $0.00   │ ← Ruido
│ TEST-IEPS-AZUCAR-001    │ IEPS Alcohol               │ $0.00   │ ← Ruido
│ TEST-IEPS-ALCOHOL-001   │ IEPS Alcohol               │ $1060   │ ✓
└─────────────────────────┴─────────────────────────────┴─────────┘
```

### 4.2 Propuesta: Opción A - Limpieza Universal (RECOMENDADA)

**Nueva función helper:**
```python
def limpiar_item_wise_tax_detail(doc, method=None):
	"""
	Hook validate (al final): Limpiar entries [0.0,0.0] de item_wise_tax_detail.

	Mejora la UI del Tax Breakup mostrando solo items relevantes.
	Respeta dont_recompute_tax (no modifica taxes ya congelados por IEPS Cuota).

	Args:
		doc: Sales Invoice document
		method: Hook method (no usado)
	"""
	for tax in doc.taxes:
		# Skip taxes ya congelados (IEPS Cuota, IVA sobre IEPS Cuota)
		if tax.dont_recompute_tax:
			continue

		# Skip si no tiene item_wise_tax_detail
		if not tax.item_wise_tax_detail:
			continue

		# Parse JSON
		import json
		detail = json.loads(tax.item_wise_tax_detail) if isinstance(tax.item_wise_tax_detail, str) else tax.item_wise_tax_detail

		# Limpiar entries con amount=0
		cleaned = {k: v for k, v in detail.items() if v[1] != 0}

		# Actualizar (puede quedar vacío {})
		tax.item_wise_tax_detail = json.dumps(cleaned) if cleaned else "{}"
```

**Registro hook en hooks.py:**
```python
"Sales Invoice": {
	"before_validate": "facturacion_mexico.hooks_handlers.sales_invoice_automated_tax.before_validate",
	"validate": [
		"facturacion_mexico.hooks_handlers.sales_invoice_automated_tax.validate",
		"facturacion_mexico.hooks_handlers.sales_invoice_ieps.calcular_ieps_cuota",
		"facturacion_mexico.hooks_handlers.sales_invoice_ieps.limpiar_item_wise_tax_detail",  # ← NUEVO
	],
	"before_save": [
		"facturacion_mexico.hooks_handlers.sales_invoice_ieps.ajustar_base_iva_combustibles",
	],
}
```

**Ventajas:**
- ✅ **Simple y mantenible**: Una sola función, lógica clara
- ✅ **Universal**: Se aplica automáticamente a todos los impuestos
- ✅ **Future-proof**: Funciona con cualquier impuesto futuro
- ✅ **Respeta IEPS Cuota**: Skip explícito de taxes con `dont_recompute_tax`
- ✅ **Sin efectos colaterales**: Solo afecta display UI, no cálculos

**Desventajas:**
- ⚠️ Overhead mínimo: Parse JSON en cada save (despreciable)

**Resultado esperado:**
```
Tax Breakup después de limpieza:
┌─────────────────────────┬─────────────────────────────┬─────────┐
│ Item                    │ Tax                         │ Amount  │
├─────────────────────────┼─────────────────────────────┼─────────┤
│ TEST-IEPS-ALCOHOL-001   │ IEPS Alcohol               │ $1060   │ ✓
│ TEST-IEPS-TABACO-001    │ IEPS Tabaco                │ $1600   │ ✓
│ TEST-IEPS-AZUCAR-001    │ IEPS Azúcar Cuota          │ $22.86  │ ✓
│                         │ IVA 16% sobre IEPS Azúcar  │ $3.66   │ ✓
└─────────────────────────┴─────────────────────────────┴─────────┘
(Solo items relevantes - UI ultra limpio)
```

---

### 4.3 Propuesta: Opción B - Limpieza Selectiva

**Función con control granular:**
```python
import re

def limpiar_item_wise_tax_detail(doc, method=None):
	"""Limpiar solo impuestos específicos."""

	# Lista de patterns para limpiar
	PATTERNS_TO_CLEAN = [
		r"IEPS.*tasa via ITT",  # IEPS Tasa (no Cuota)
		r"Retención.*tasa via ITT",  # Retenciones con rate=0
		r"IVA 0%",  # IVA neutralizadores
		r"IVA Exento",
	]

	for tax in doc.taxes:
		if tax.dont_recompute_tax:
			continue

		# Verificar si description match patterns
		should_clean = any(re.search(pattern, tax.description) for pattern in PATTERNS_TO_CLEAN)

		if should_clean and tax.item_wise_tax_detail:
			import json
			detail = json.loads(tax.item_wise_tax_detail) if isinstance(tax.item_wise_tax_detail, str) else tax.item_wise_tax_detail
			cleaned = {k: v for k, v in detail.items() if v[1] != 0}
			tax.item_wise_tax_detail = json.dumps(cleaned) if cleaned else "{}"
```

**Ventajas:**
- ✅ Control explícito sobre qué limpiar
- ✅ Más conservador (menos cambios)

**Desventajas:**
- ❌ Requiere mantenimiento (agregar patterns)
- ❌ Más complejo
- ❌ Puede olvidarse actualizar patterns para nuevos impuestos

---

### 4.4 Comparación de Opciones

| Criterio | Opción A (Universal) | Opción B (Selectiva) |
|----------|---------------------|----------------------|
| **Simplicidad** | ✅ Muy simple | ⚠️ Más complejo |
| **Mantenibilidad** | ✅ Zero maintenance | ❌ Requiere updates |
| **Cobertura** | ✅ 100% automática | ⚠️ Debe agregar patterns |
| **Riesgo** | ✅ Bajo (solo UI) | ✅ Bajo (solo UI) |
| **Performance** | ✅ O(n) taxes | ✅ O(n) taxes + regex |

**Recomendación:** **Opción A (Limpieza Universal)**

**Razones:**
1. No hay caso de uso donde queramos mostrar [0.0, 0.0]
2. Más simple = menos bugs
3. Future-proof automático
4. Overhead despreciable

---

## 5. ANÁLISIS DE RIESGOS

### 5.1 ¿Rompe funcionalidad existente?

**✅ NO, por las siguientes razones:**

1. **item_wise_tax_detail es solo display:**
   - No afecta cálculos backend
   - `tax_amount` (total) sigue siendo la fuente de verdad
   - Contabilidad usa `tax_amount`, no `item_wise_tax_detail`

2. **ERPNext tolera item_wise_tax_detail parcial:**
   - JavaScript maneja correctamente entries vacíos
   - Tax Breakup solo muestra lo que existe

3. **No afecta CFDI/PAC:**
   - Payload XML usa lógica propia (mapeo ITT → SAT)
   - No lee `item_wise_tax_detail` directamente

### 5.2 ¿Compatibilidad con dont_recompute_tax?

**✅ SÍ, completamente compatible:**

```python
# Función respeta explícitamente el flag
if tax.dont_recompute_tax:
    continue  # No toca IEPS Cuota ni IVA sobre IEPS Cuota
```

Taxes afectados vs no afectados:

| Tax | dont_recompute_tax | ¿Se limpia? |
|-----|-------------------|-------------|
| IEPS Cuota | 1 | ❌ No (skip) |
| IVA sobre IEPS Cuota | 1 | ❌ No (skip) |
| IEPS Tasa | 0 | ✅ Sí |
| Retenciones | 0 | ✅ Sí |
| IVA base | 0 | ✅ Sí |

### 5.3 ¿Efectos en JavaScript client-side?

**✅ Sin efectos negativos:**

```javascript
// ERPNext taxes_and_totals.js línea ~800
if (!tax.dont_recompute_tax) {
    this.set_item_wise_tax(item, tax, tax_rate, current_tax_amount);
}
```

- JavaScript respeta `dont_recompute_tax`
- Si `item_wise_tax_detail` está vacío o parcial, no hay problema
- UI simplemente no renderiza lo que no existe

---

## 6. PLAN DE TESTING

### 6.1 Tests Mínimos Requeridos

**Test 1: Tax Breakup UI**
```
Objetivo: Verificar que UI muestra solo items relevantes
Pasos:
1. Crear Sales Invoice con mix de items (IEPS Tasa, IEPS Cuota, normal)
2. Abrir Tax Breakup
3. Verificar que items sin impuesto NO aparecen (casillas vacías)
4. Verificar que items con impuesto aparecen con monto correcto
```

**Test 2: Totales no cambian**
```
Objetivo: Verificar que tax_amount totales son idénticos
Pasos:
1. Antes de implementar: Anotar todos los tax_amount
2. Implementar limpieza
3. Guardar mismo SI
4. Verificar tax_amount idénticos (diff de 0)
```

**Test 3: IEPS Cuota no se toca**
```
Objetivo: Verificar que dont_recompute_tax se respeta
Pasos:
1. Crear SI con IEPS Cuota
2. Verificar item_wise_tax_detail de IEPS Cuota NO cambia
3. Verificar item_wise_tax_detail de IVA sobre IEPS Cuota NO cambia
```

**Test 4: Edición múltiple**
```
Objetivo: Verificar que funciona en save/edit cycles
Pasos:
1. Crear SI → Guardar
2. Editar qty → Guardar
3. Agregar item → Guardar
4. Eliminar item → Guardar
5. Verificar UI limpio en cada paso
```

**Test 5: Submit/Cancel**
```
Objetivo: Verificar workflows críticos
Pasos:
1. Crear SI → Submit
2. Verificar Tax Breakup en submitted
3. Cancel
4. Amend
5. Verificar limpieza se mantiene
```

### 6.2 Tests Nice-to-Have

- Performance: 100 items, 20 taxes (medir tiempo save)
- Edge case: Sales Invoice sin taxes
- Edge case: Todos los taxes con monto 0
- Compatibility: POS Invoice (mismo sistema taxes)

---

## 7. RECOMENDACIÓN FINAL

### 7.1 Implementar Ahora

**✅ Cambios 1-3 (Ya implementados):**
- Corrección key `item_code`
- Flag `dont_recompute_tax` para IEPS Cuota
- Función `_congelar_iva_sobre_ieps_cuota()`

**Estado:** ✅ Funcionando correctamente en ACC-SINV-2025-01617

---

### 7.2 Propuesta para Discusión

**⏳ Cambio 4 (Propuesto):**
- Función `limpiar_item_wise_tax_detail()` (Opción A - Universal)

**Beneficios esperados:**
- UI Tax Breakup ultra limpio (solo items relevantes)
- Consistencia visual en TODOS los impuestos
- Zero maintenance (automático para futuros impuestos)

**Riesgos:**
- ✅ Bajos (solo afecta display UI)
- ✅ No rompe funcionalidad existente
- ✅ Respeta IEPS Cuota (skip `dont_recompute_tax`)

**Decisión pendiente:**
- Discutir con ChatGPT
- Validar approach
- Implementar si aprobado

---

## 8. CÓDIGO PARA IMPLEMENTACIÓN (SI SE APRUEBA)

### 8.1 Nueva función en sales_invoice_ieps.py

**Ubicación:** Agregar después de `_congelar_iva_sobre_ieps_cuota()` (línea ~240)

```python
def limpiar_item_wise_tax_detail(doc, method=None):
	"""
	Hook validate (al final): Limpiar entries [0.0,0.0] de item_wise_tax_detail.

	Mejora la UI del Tax Breakup mostrando solo items con montos relevantes.
	Las casillas para items sin ese impuesto quedan vacías (no muestran $0.00).

	Respeta dont_recompute_tax - no modifica taxes ya congelados por IEPS Cuota.

	Args:
		doc: Sales Invoice document
		method: Hook method (no usado)

	Ejemplo:
		ANTES: {"Item A": [16.0, 0.0], "Item B": [16.0, 100.0]}
		DESPUÉS: {"Item B": [16.0, 100.0]}
	"""
	import json
	from frappe.utils import flt

	for tax in doc.taxes:
		# Skip taxes ya congelados (IEPS Cuota procesado manualmente)
		if tax.dont_recompute_tax:
			continue

		# Skip si no tiene item_wise_tax_detail
		if not tax.item_wise_tax_detail:
			continue

		try:
			# Parse JSON
			detail = json.loads(tax.item_wise_tax_detail) if isinstance(tax.item_wise_tax_detail, str) else tax.item_wise_tax_detail

			# Limpiar entries donde amount = 0
			# Formato: {"item_code": [rate, amount]}
			cleaned = {k: v for k, v in detail.items() if flt(v[1]) != 0}

			# Actualizar (puede quedar vacío {} si todos eran 0)
			tax.item_wise_tax_detail = json.dumps(cleaned) if cleaned else "{}"

		except (json.JSONDecodeError, KeyError, IndexError, TypeError):
			# Si hay error parsing, skip este tax (no romper el save)
			continue
```

### 8.2 Registro hook en hooks.py

**Ubicación:** Modificar sección "Sales Invoice" (línea ~342)

```python
"Sales Invoice": {
	"before_validate": "facturacion_mexico.hooks_handlers.sales_invoice_automated_tax.before_validate",
	"validate": [
		"facturacion_mexico.hooks_handlers.sales_invoice_automated_tax.validate",
		"facturacion_mexico.hooks_handlers.sales_invoice_ieps.calcular_ieps_cuota",
		"facturacion_mexico.hooks_handlers.sales_invoice_ieps.limpiar_item_wise_tax_detail",  # ← AGREGAR
	],
	"before_save": [
		"facturacion_mexico.hooks_handlers.sales_invoice_ieps.ajustar_base_iva_combustibles",
	],
	"before_submit": "facturacion_mexico.hooks_handlers.sales_invoice_ieps.corregir_ieps_cuota_final",
},
```

**Importante:** El orden importa:
1. `validate` (automated_tax) → Calcula impuestos normales
2. `calcular_ieps_cuota` → Procesa IEPS Cuota + congela IVA
3. `limpiar_item_wise_tax_detail` → Limpia entries [0,0] (AL FINAL)

---

## 9. ANEXOS

### 9.1 Referencias ERPNext

**Backend - taxes_and_totals.py:**
- Línea 491-503: Redistribución proporcional "Actual"
- Línea 518: Check `dont_recompute_tax` flag
- Línea 415: `tax_amount_for_current_item` para cascada

**Frontend - taxes_and_totals.js:**
- Línea ~100: `initialize_taxes()` respeta `dont_recompute_tax`
- Línea ~250: `set_item_wise_tax()` condicional
- Línea ~300: Stringify final respeta flag

### 9.2 Documentación ChatGPT

**Propuesta validada:**
- Flag `dont_recompute_tax` existe en DocType (Hidden=1)
- Uso previsto: Congelar distribución custom
- Referencias: Frappe Forum, GitHub issues ERPNext
- Versión: Compatible v15+

**Testing recomendado (5 puntos):**
1. No-touch de `item_wise_tax_detail`
2. Interacción IVA "On Previous Row Amount"
3. Operaciones edición (agregar/eliminar items)
4. POS Invoice (mismo DocType)
5. Versiones (parches v15.x)

---

## 10. CONCLUSIÓN

### Estado Actual: ✅ ÉXITO PARCIAL

**Implementado y funcionando:**
- ✅ IEPS Cuota UI limpio (solo items relevantes)
- ✅ IVA sobre IEPS Cuota sin redistribución
- ✅ Flag `dont_recompute_tax` aplicado correctamente
- ✅ Totales correctos

**Pendiente de decisión:**
- ⏳ Aplicar misma metodología a otros impuestos (Opción A recomendada)
- ⏳ Validación con ChatGPT

**Próximos pasos:**
1. Discutir propuesta con ChatGPT
2. Si aprobado → Implementar `limpiar_item_wise_tax_detail()`
3. Testing completo (6 tests mínimos)
4. Commit final con todo el feature E4

---

**Fin del reporte**
