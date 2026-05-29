> **OBSOLETO**
>
> Este documento queda archivado como referencia histórica. No representa el plan vigente ni debe usarse como fuente operativa actual.

---

# PROPUESTA: ITT Específico por Item con Cuota IEPS

**Fecha:** 2025-10-29 04:00
**Contexto:** E4 implementación - Automatización actualización cuotas

---

## 1. ESTADO ACTUAL

### ✅ Lo que funciona (manual, one-off):

**Script ejecutado:** `one_offs/asignar_itt_y_actualizar_cuotas.py`

```python
# Para cada item test:
for item_code in ["TEST-IEPS-AZUCAR-001", "TEST-IEPS-COMBUSTIBLES-001", "TEST-IEPS-TABACO-001"]:
    # 1. Buscar ITT genérico para esa clave SAT
    itt_name = "ITT IEPS Azúcar - _TC"  # ITT GENÉRICO compartido

    # 2. Modificar tax_rate en ITT genérico
    itt = frappe.get_doc("Item Tax Template", itt_name)
    for tax in itt.taxes:
        if tax.tax_type == cuenta_ieps:
            tax.tax_rate = 0.762  # ← MODIFICA ITT GENÉRICO
    itt.save()

    # 3. Asignar ITT genérico al item
    item.item_defaults[0].item_tax_template = itt_name
    item.save()
```

**Resultado:**
- ✅ SI ACC-SINV-2025-01685: Grand Total $8,293.24
- ✅ Azúcar: tax_amount $15.24 (esperado $15.24) - Delta $0.00
- ✅ Combustibles: tax_amount $219.60 (esperado $219.60) - Delta $0.00

---

## 2. PROBLEMA ARQUITECTÓNICO

### ❌ Por qué modificar ITT genérico NO escala:

**Caso:** Dos items azúcar con DIFERENTE UOM

```
Item A: TEST-IEPS-AZUCAR-001
  Stock UOM: H87 - Pieza
  Conversión: 1 pieza = 0.6 litros
  Cuota SAT: $1.27/litro
  Cuota convertida: $1.27 × 0.6 = $0.762/pieza ← ESPECÍFICO ITEM A

Item B: TEST-IEPS-AZUCAR-002 (hipotético)
  Stock UOM: LTR - Litro
  Conversión: 1 litro = 1 litro
  Cuota SAT: $1.27/litro
  Cuota convertida: $1.27 × 1.0 = $1.27/litro ← ESPECÍFICO ITEM B
```

**Problema:**
- ITT genérico "ITT IEPS Azúcar - _TC" tiene tax_rate=0.762
- Item A correcto: 20 piezas × $0.762 = $15.24 ✅
- Item B INCORRECTO: 20 litros × $0.762 = $15.24 ❌ (debería ser 20 × $1.27 = $25.40)

**Conclusión:** ITT genérico NO puede tener tax_rate específico porque cada item necesita cuota diferente según su UOM.

---

## 3. SOLUCIÓN CORRECTA

### 🎯 ITT Específico por Item

**Arquitectura:**

```
Item: TEST-IEPS-AZUCAR-001
  Stock UOM: H87 - Pieza
  item_defaults[]:
    item_tax_template: "ITT IEPS Cuota - TEST-IEPS-AZUCAR-001" ← ITT ESPECÍFICO

ITT: "ITT IEPS Cuota - TEST-IEPS-AZUCAR-001"
  taxes:
    - tax_type: "2117002 - IEPS Azucar Bebidas - _TC"
      tax_rate: 0.762  ← CUOTA ESPECÍFICA PARA ESTE ITEM

---

Item: TEST-IEPS-AZUCAR-002
  Stock UOM: LTR - Litro
  item_defaults[]:
    item_tax_template: "ITT IEPS Cuota - TEST-IEPS-AZUCAR-002" ← ITT ESPECÍFICO DIFERENTE

ITT: "ITT IEPS Cuota - TEST-IEPS-AZUCAR-002"
  taxes:
    - tax_type: "2117002 - IEPS Azucar Bebidas - _TC"
      tax_rate: 1.27  ← CUOTA DIFERENTE PARA ESTE ITEM
```

**Ventaja:** Cada item tiene su ITT con cuota convertida correcta para su UOM.

---

## 4. IMPLEMENTACIÓN PROPUESTA

### 4.1 Reutilizar Función Existente

**Función actual en generador_templates_fiscal.py:**

```python
def _crear_o_actualizar_itt(
    company: str,
    abbr: str,
    title: str,
    taxes_config: list[dict],
    mapeo_cuentas: dict
) -> str:
    """Crear o actualizar Item Tax Template."""
    full_title = f"{title} - {abbr}"

    # Buscar existente
    existing = frappe.db.exists("Item Tax Template", {"title": full_title, "company": company})

    if existing:
        doc = frappe.get_doc("Item Tax Template", existing)
        doc.taxes = []  # limpiar para rearmar
    else:
        doc = frappe.new_doc("Item Tax Template")
        doc.title = full_title
        doc.company = company

    # Reconstruir taxes
    for idx, tax_config in enumerate(taxes_config, start=1):
        rol_fiscal = tax_config["rol_fiscal"]
        cuenta_impuesto = mapeo_cuentas.get(rol_fiscal)
        if not cuenta_impuesto:
            continue
        doc.append("taxes", {
            "tax_type": cuenta_impuesto,
            "tax_rate": tax_config.get("tax_rate", 0.0),
            "idx": idx,
        })

    # Guardar
    if existing:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)

    frappe.db.commit()
    return doc.name
```

**Esta función YA hace lo que necesitamos:**
- Crea ITT si no existe
- Actualiza ITT si existe
- Configura taxes con tax_rate específico

### 4.2 Nueva Función Helper

**Ubicación:** `facturacion_mexico/utils/itt_management.py` (nuevo archivo)

```python
"""Utilidades para gestión automática de ITT específicos por item."""

import frappe
from erpnext.stock.get_item_details import get_conversion_factor


def crear_o_actualizar_itt_item_cuota(
    item_code: str,
    company: str,
    cuenta_ieps: str,
    cuota_convertida: float
) -> str:
    """
    Crear o actualizar ITT específico para item con cuota IEPS.

    Reutiliza función _crear_o_actualizar_itt() del generador templates.

    Args:
        item_code: Código del item (ej: "TEST-IEPS-AZUCAR-001")
        company: Company name
        cuenta_ieps: Cuenta contable IEPS completa
        cuota_convertida: Cuota ya convertida a UOM del item

    Returns:
        str: Nombre del ITT creado/actualizado

    Example:
        >>> itt_name = crear_o_actualizar_itt_item_cuota(
        ...     "TEST-IEPS-AZUCAR-001",
        ...     "_Test Company",
        ...     "2117002 - IEPS Azucar Bebidas - _TC",
        ...     0.762
        ... )
        >>> print(itt_name)
        'ITT IEPS Cuota - TEST-IEPS-AZUCAR-001 - _TC'
    """
    from facturacion_mexico.facturacion_fiscal.setup.generador_templates_fiscal import (
        _crear_o_actualizar_itt,
    )

    # Obtener company abbr
    abbr = frappe.db.get_value("Company", company, "abbr")

    # Título ITT específico por item
    title = f"ITT IEPS Cuota - {item_code}"

    # Configuración taxes: solo la cuenta IEPS con cuota convertida
    taxes_config = [
        {
            "rol_fiscal": None,  # No usamos rol_fiscal, pasamos cuenta directamente
            "tax_rate": cuota_convertida,
        }
    ]

    # Mapeo directo (bypass rol_fiscal)
    # Modificamos temporalmente para pasar cuenta directa
    mapeo_cuentas = {None: cuenta_ieps}

    # Reutilizar función del generador
    itt_name = _crear_o_actualizar_itt(
        company=company,
        abbr=abbr,
        title=title,
        taxes_config=taxes_config,
        mapeo_cuentas=mapeo_cuentas,
    )

    return itt_name


def asignar_itt_a_item(item_code: str, company: str, itt_name: str):
    """
    Asignar ITT específico al item en item_defaults.

    Args:
        item_code: Código del item
        company: Company name
        itt_name: Nombre del ITT a asignar
    """
    item = frappe.get_doc("Item", item_code)

    # Buscar item_default para esta company
    for default in item.item_defaults:
        if default.company == company:
            default.item_tax_template = itt_name
            item.save(ignore_permissions=True)
            frappe.db.commit()
            return

    # Si no existe item_default para esta company, crear
    item.append("item_defaults", {
        "company": company,
        "item_tax_template": itt_name,
    })
    item.save(ignore_permissions=True)
    frappe.db.commit()
```

### 4.3 Hook en IEPS Cuota SAT

**Archivo nuevo:** `facturacion_mexico/hooks_handlers/ieps_cuota_sat.py`

```python
"""Hooks para DocType IEPS Cuota SAT."""

import frappe
from facturacion_mexico.utils.itt_management import (
    crear_o_actualizar_itt_item_cuota,
    asignar_itt_a_item,
)
from erpnext.stock.get_item_details import get_conversion_factor


def after_save(doc, method=None):
    """
    Hook ejecutado al crear/actualizar cuota IEPS.

    Para cada item que use esta clave_prod_serv:
    1. Crear/actualizar ITT específico con cuota convertida
    2. Asignar ese ITT al item
    """
    if doc.docstatus == 2:  # Cancelled
        return

    # Buscar items con esta clave_prod_serv
    items = frappe.get_all(
        "Item",
        filters={"fm_producto_servicio_sat": doc.clave_prod_serv},
        fields=["name", "stock_uom"]
    )

    if not items:
        frappe.msgprint(
            f"No se encontraron items con ClaveProdServ {doc.clave_prod_serv}",
            indicator="yellow"
        )
        return

    updated_items = []

    for item_data in items:
        item_code = item_data.name
        item_uom = item_data.stock_uom

        # Convertir cuota a UOM del item
        if item_uom != doc.uom:
            try:
                conversion_data = get_conversion_factor(item_code, doc.uom)
                factor = conversion_data.get("conversion_factor", 0)

                if factor <= 0:
                    frappe.log_error(
                        f"Item {item_code}: Falta conversión {item_uom} → {doc.uom}",
                        "IEPS Cuota SAT - Conversión UOM"
                    )
                    continue

                cuota_convertida = doc.cuota * factor
            except Exception as e:
                frappe.log_error(
                    f"Error conversión UOM para {item_code}: {str(e)}",
                    "IEPS Cuota SAT - Conversión UOM"
                )
                continue
        else:
            cuota_convertida = doc.cuota

        # Crear/actualizar ITT específico para este item
        itt_name = crear_o_actualizar_itt_item_cuota(
            item_code=item_code,
            company=doc.company,
            cuenta_ieps=doc.cuenta_ieps,
            cuota_convertida=cuota_convertida,
        )

        # Asignar ITT al item
        asignar_itt_a_item(item_code, doc.company, itt_name)

        updated_items.append(f"{item_code} → {itt_name} (${cuota_convertida:.3f})")

    if updated_items:
        frappe.msgprint(
            f"ITT actualizado para {len(updated_items)} items:<br>" +
            "<br>".join(updated_items),
            title="IEPS Cuota - ITT Actualizados",
            indicator="green"
        )
```

### 4.4 Registrar Hook

**Ubicación:** `facturacion_mexico/hooks.py`

```python
doc_events = {
    # ... otros hooks ...
    "IEPS Cuota SAT": {
        "after_insert": "facturacion_mexico.hooks_handlers.ieps_cuota_sat.after_save",
        "on_update": "facturacion_mexico.hooks_handlers.ieps_cuota_sat.after_save",
    },
}
```

---

## 5. FLUJO COMPLETO

### Workflow Automático:

```
1. Usuario crea/modifica cuota en "IEPS Cuota SAT"
   - Clave SAT: 50202301
   - Cuenta: 2117002 - IEPS Azucar Bebidas - _TC
   - Cuota: $1.27/litro
   - UOM: LTR

2. Hook after_save se ejecuta
   ↓
3. Busca items con clave_prod_serv = 50202301
   - Encuentra: TEST-IEPS-AZUCAR-001 (UOM: H87 - Pieza)
   ↓
4. Convierte cuota a UOM del item
   - Factor: 0.6 litros/pieza
   - Cuota convertida: $1.27 × 0.6 = $0.762/pieza
   ↓
5. Crea ITT específico "ITT IEPS Cuota - TEST-IEPS-AZUCAR-001"
   - Usando _crear_o_actualizar_itt() del generador
   - tax_rate: 0.762
   ↓
6. Asigna ITT al item en item_defaults
   ↓
7. Usuario crea SI → ERPNext calcula nativamente ✅
```

---

## 6. VENTAJAS

### ✅ Reutilización de código:
- Usa función `_crear_o_actualizar_itt()` existente
- NO duplica lógica de generación templates

### ✅ Escalable:
- Múltiples items con misma clave SAT pero diferente UOM
- Cada item tiene cuota correcta

### ✅ Automático:
- Usuario solo crea/modifica cuota
- ITT se actualiza automáticamente

### ✅ Preserva generación genérica:
- "Generate Templates" sigue creando ITT genéricos (tax_rate=0)
- ITT específicos son independientes

---

## 7. CONSIDERACIONES

### ⚠️ Performance:
- Hook se ejecuta por cada cuota guardada
- Si hay muchos items con misma clave SAT, puede ser lento
- **Solución:** Ejecutar en background job para cuotas con >10 items

### ⚠️ Nomenclatura ITT:
- Nombre: "ITT IEPS Cuota - {item_code} - {abbr}"
- Puede ser largo si item_code es largo
- **Alternativa:** "ITT Cuota - {item_code} - {abbr}"

### ⚠️ Limpieza:
- Si item se elimina, ITT específico queda huérfano
- **Solución:** Hook on_trash en Item para eliminar ITT específico

---

## 8. TESTING

### Caso prueba 1: Crear cuota nueva

```python
# Crear cuota para producto nuevo
cuota = frappe.new_doc("IEPS Cuota SAT")
cuota.company = "_Test Company"
cuota.clave_prod_serv = "50202301"
cuota.cuenta_ieps = "2117002 - IEPS Azucar Bebidas - _TC"
cuota.cuota = 1.50  # Nueva cuota
cuota.uom = "LTR - Litro"
cuota.vigencia_desde = "2025-11-01"
cuota.insert()

# Verificar:
# 1. ITT "ITT IEPS Cuota - TEST-IEPS-AZUCAR-001" creado
# 2. tax_rate = 1.50 × 0.6 = 0.90
# 3. Item tiene ese ITT asignado
# 4. Nuevo SI calcula: 20 × 0.90 = $18.00
```

### Caso prueba 2: Modificar cuota existente

```python
# Modificar cuota
cuota = frappe.get_doc("IEPS Cuota SAT", "existing-cuota")
cuota.cuota = 2.00  # Cambio de $1.27 → $2.00
cuota.save()

# Verificar:
# 1. ITT actualizado con tax_rate = 2.00 × 0.6 = 1.20
# 2. Nuevo SI calcula: 20 × 1.20 = $24.00
```

---

## 9. PREGUNTAS PARA DISCUSIÓN

### Q1: Nomenclatura ITT
¿"ITT IEPS Cuota - {item_code}" o más corto?

### Q2: Background job
¿Ejecutar hook en background para cuotas con >N items?

### Q3: Limpieza ITT huérfanos
¿Hook on_trash en Item para eliminar ITT específico?

### Q4: Modificación _crear_o_actualizar_itt()
¿Necesita modificarse para soportar pasar cuenta directa sin rol_fiscal?

### Q5: Productos con TASA + CUOTA (ej: Tabaco)

**Caso:** Tabaco tiene AMBOS:
- IEPS Tasa: 160% (cuenta 2117004)
- IEPS Cuota: $0.35/pieza (cuenta 2117005)

**Arquitectura propuesta:**

ITT específico debe tener AMBAS tax rows:

```python
ITT: "ITT IEPS Cuota - TEST-IEPS-TABACO-001"
  taxes:
    [0] tax_type: "2117004 - IEPS Tabaco - _TC"
        tax_rate: 160.0  ← TASA desde TASAS_IEPS (single source of truth)

    [1] tax_type: "2117005 - IEPS Tabaco Cuota - _TC"
        tax_rate: 7.00   ← CUOTA convertida (0.35 × 20 piezas/cajetilla)
```

**Single Source of Truth para TASAS:**

```python
# facturacion_mexico/facturacion_fiscal/setup/generador_templates_fiscal.py
# Líneas 4-14

TASAS_IEPS = {
    "alcohol": {"tasa": 26.5},   # 26.5% Art. 2-I-A LIEPS
    "tabaco": {"tasa": 160.0},   # 160% Art. 2-I-C LIEPS
}
```

**Función debe:**
1. Leer TASA desde `TASAS_IEPS` (NO hardcodear)
2. Leer CUOTA desde doc IEPS Cuota SAT
3. Crear ITT con AMBAS tax rows

**Ejemplo código:**

```python
def crear_o_actualizar_itt_item_cuota(item_code, company, cuota_data):
    """
    Args:
        cuota_data: {
            "cuenta_ieps": "2117005 - IEPS Tabaco Cuota - _TC",
            "cuota_convertida": 7.00,
            "tiene_tasa": True,  # ← Flag
            "cuenta_tasa": "2117004 - IEPS Tabaco - _TC",  # Si tiene_tasa
            "tipo_ieps": "tabaco",  # Para leer TASAS_IEPS
        }
    """
    from facturacion_mexico.facturacion_fiscal.setup.generador_templates_fiscal import TASAS_IEPS

    taxes_config = []

    # Si tiene tasa, agregar primero (desde TASAS_IEPS)
    if cuota_data.get("tiene_tasa"):
        tipo = cuota_data["tipo_ieps"]
        tasa = TASAS_IEPS[tipo]["tasa"]  # ← Single source of truth
        taxes_config.append({
            "cuenta": cuota_data["cuenta_tasa"],
            "tax_rate": tasa,
        })

    # Agregar cuota
    taxes_config.append({
        "cuenta": cuota_data["cuenta_ieps"],
        "tax_rate": cuota_data["cuota_convertida"],
    })

    # Crear ITT con ambas rows...
```

**⚠️ IMPORTANTE:** NUNCA hardcodear tasas (26.5%, 160%) en el hook. SIEMPRE leer de `TASAS_IEPS`.

---

## 10. PRÓXIMOS PASOS

1. ✅ Revisar propuesta con ChatGPT
2. ⏳ Decidir nomenclatura y ajustes
3. ⏳ Implementar funciones en `utils/itt_management.py`
4. ⏳ Implementar hook en `hooks_handlers/ieps_cuota_sat.py`
5. ⏳ Registrar hook en `hooks.py`
6. ⏳ Testing con casos prueba
7. ⏳ Documentar en CHANGELOG.md

---

## 11. INVESTIGACIÓN ALTERNATIVAS (2025-10-29 05:00)

### 🔍 Objetivo
Agotar todas las alternativas para asignar `tax_rate` "on-the-fly" antes de implementar ITT específico por item.

### ✅ Script Ejecutado
`one_offs/investigar_alternativas_tax_rate_runtime_v2.py`

### 📊 Resultados por Opción

#### OPCIÓN 1: item.item_tax_rate JSON
**Estado actual en SI ACC-SINV-2025-01685:**
```
TEST-IEPS-AZUCAR-001: item_tax_rate = {"2117002 - IEPS Azucar Bebidas - _TC": 0.762}
TEST-IEPS-COMBUSTIBLES-001: item_tax_rate = {"2117003 - IEPS Combustibles - _TC": 5.49}
TEST-IEPS-TABACO-001: item_tax_rate = {"2117004 - IEPS Tabaco - _TC": 160.0}
```

**Análisis:**
- ✅ Campo existe y ERPNext lo usa (prioridad: item_tax_rate > ITT > STCT)
- ✅ Valores correctos presentes en SI actual
- ⚠️ **PROBLEMA:** `update_item_tax_map()` sobrescribe durante validate
- ⚠️ Requeriría hook DESPUÉS de update_item_tax_map() - muy frágil
- ❌ Depende de orden ejecución interno ERPNext
- ❌ Puede romperse con updates framework

**Veredicto:** ❌ Frágil, NO recomendado

---

#### OPCIÓN 2: Custom Field en Item
**Estado:**
- ❌ Custom field `fm_ieps_tax_rate` NO existe

**Análisis:**
- ✅ Se PODRÍA crear custom field limpio
- ⚠️ Mismo problema OPCIÓN 1 - necesita hook para aplicarlo a item_tax_rate
- ⚠️ Sufriría sobrescritura de update_item_tax_map()

**Veredicto:** ❌ Mismo problema que OPCIÓN 1

---

#### OPCIÓN 3: Override calculate_taxes_and_totals
**Análisis:**
- ✅ Control total sobre cálculo
- ✅ Frappe permite override vía `doc_events`
- ❌ Complejidad ALTA - copiar/mantener lógica ERPNext completa
- ❌ Frágil ante updates ERPNext (v15→v16)
- ❌ Anti-pattern arquitectónico

**Veredicto:** ❌ Anti-pattern, NO recomendado

---

#### OPCIÓN 4: Modificar tax rows post-calculate
**Observación crítica en SI ACC-SINV-2025-01685:**
```
[3] IEPS Azúcar/Bebidas - Cuota (via ITT)
    charge_type: On Item Quantity
    rate: 0.0              ← rate SIEMPRE 0.0
    tax_amount: $15.24     ← Pero tax_amount CORRECTO
```

**Análisis:**
- ⚠️ **HALLAZGO:** Para "On Item Quantity", ERPNext NO usa `tax.rate`
- ⚠️ ERPNext lee de `item.item_tax_rate`, NO de tax row
- ⚠️ Modificar `tax.rate` manualmente NO tendría efecto
- ⚠️ Necesitaríamos recalcular `tax_amount` y `grand_total` manualmente
- ❌ Depende de internals ERPNext - muy frágil

**Veredicto:** ❌ No resuelve el problema

---

#### OPCIÓN 5: item_wise_tax_detail
**Estado actual en SI ACC-SINV-2025-01685:**
```
IEPS Azúcar/Bebidas - Cuota:
  TEST-IEPS-AZUCAR-001: rate=0.762, amount=$15.24

IEPS Combustibles - Cuota:
  TEST-IEPS-COMBUSTIBLES-001: rate=5.49, amount=$219.60
```

**Análisis:**
- ✅ Muestra valores correctos por item
- ❌ Es OUTPUT del cálculo, NO input
- ❌ ERPNext lo sobrescribe en `_calculate_item_wise_tax()`
- ❌ No se puede usar para pasar tax_rate

**Veredicto:** ❌ Es output, no input

---

### 🎯 CONCLUSIÓN FINAL

**✅ ITT Específico por Item es la ÚNICA solución viable**

**Razones confirmadas:**

1. **Arquitectura nativa ERPNext**
   - `ITT.tax_rate` es el mecanismo diseñado por framework
   - ERPNext lo lee correctamente (confirmado en item_wise_tax_detail)

2. **Prioridad correcta**
   - ERPNext usa: `item.item_tax_rate` > `ITT.tax_rate` > `STCT.rate`
   - item_tax_rate se construye desde ITT asignado al item

3. **Para "On Item Quantity"**
   - `tax_rate` ES la cuota convertida
   - tax_amount = tax_rate × qty (ERPNext nativo)

4. **Sin fragilidad**
   - No depende de hooks runtime
   - No depende de orden ejecución
   - No se rompe con updates ERPNext

5. **Escalable**
   - Cada item tiene su configuración independiente
   - Múltiples items con mismo ClaveProdServ pero diferentes UOMs ✅

6. **Compatible E4**
   - 100% ERPNext nativo
   - charge_type="On Item Quantity" funciona correctamente
   - Sin hooks manuales de cálculo

---

**Fecha investigación:** 2025-10-29 05:00
**Script:** `one_offs/investigar_alternativas_tax_rate_runtime_v2.py`
**Estado:** ✅ Investigación completa - ITT específico CONFIRMADO

---

**Fecha:** 2025-10-29 05:10
**Status:** ✅ Investigación alternativas completada - Listo para implementación
**Archivos involucrados:**
- `facturacion_mexico/utils/itt_management.py` (nuevo)
- `facturacion_mexico/hooks_handlers/ieps_cuota_sat.py` (nuevo)
- `facturacion_mexico/hooks.py` (modificar)
