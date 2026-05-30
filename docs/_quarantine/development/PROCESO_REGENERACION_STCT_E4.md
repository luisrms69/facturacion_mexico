# Proceso Regeneración STCT Post-Migrate E4

**Proyecto:** Facturación México
**Fecha:** 2025-10-27
**Objetivo:** Regenerar 7 STCT con charge_type="On Item Quantity" después de migrate E4

---

## 📋 RESUMEN

Después de ejecutar `bench migrate` con los cambios E4, es necesario regenerar los Sales Taxes and Charges Templates (STCT) para que las filas de IEPS Cuota usen el nuevo `charge_type="On Item Quantity"` en lugar del legacy `"On Net Total"`.

---

## 🎯 PRE-REQUISITOS

### ✅ Verificar cambios migrados
```bash
# 1. Verificar que mapeo está actualizado
bench --site facturacion.dev console

# En consola Python:
from facturacion_mexico.facturacion_fiscal.setup.generador_templates_fiscal import _MAPEO_CHARGE_TYPE
print(_MAPEO_CHARGE_TYPE)
# Debe mostrar: 'cantidad': 'On Item Quantity'
```

### ✅ Verificar tabla maestra actualizada
```python
# En consola Python (continuando):
from facturacion_mexico.utils.reglas_calculo_fiscal import obtener_regla_calculo
from facturacion_mexico.utils.roles_fiscales import ROL_IEPS_AZU, ROL_IEPS_COMB, ROL_IEPS_TABQ

# Verificar 3 roles cuota
for rol in [ROL_IEPS_AZU, ROL_IEPS_COMB, ROL_IEPS_TABQ]:
    regla = obtener_regla_calculo(rol)
    print(f"{rol}: regla_base='{regla['regla_base']}'")
    # Debe mostrar: regla_base='cantidad' (no 'monto_neto')
```

### ✅ Backup obligatorio
```bash
# Crear backup antes de regenerar
bench --site facturacion.dev backup --with-files

# Renombrar para identificación
cd sites/facturacion.dev/private/backups
cp [timestamp]-facturacion_dev-database.sql.gz backup-pre-regeneracion-stct-e4-2025-10-27.sql.gz
```

---

## 🔧 PASO 1: EJECUTAR REGENERACIÓN

### Comando bench
```bash
bench --site facturacion.dev execute \
  facturacion_mexico.facturacion_fiscal.setup.generador_templates_fiscal.generate_8_stct_for_company \
  --kwargs "{'company':'Tauro Cigarettes SA de CV'}"
```

### ⚠️ IMPORTANTE
- La función **NO es idempotente** - verificará si templates existen
- Si existen STCT con mismo nombre, los **deshabilitará** y creará nuevos
- Reporta: `created`, `skipped`, `omitted_rows_por_template`, `disabled_old`

### Output esperado
```python
{
    "created": [
        "STCT - IVA Nacional 16% - Basico - TC",
        "STCT - IVA Nacional 16% - IEPS - TC",
        "STCT - IVA Nacional 16% - Retenciones - TC",
        "STCT - IVA Nacional 16% - Total - TC",
        # ... 4 más para Frontera 8%
    ],
    "skipped": [],  # Si alguno falló
    "omitted_rows_por_template": {},  # Filas omitidas por falta mapeo
    "disabled_old": true
}
```

---

## ✅ PASO 2: VERIFICACIÓN POST-REGENERACIÓN

### 2.1 Verificar charge_type en STCT
```bash
# Obtener STCT regenerados
bench --site facturacion.dev console
```

```python
# En consola Python:
import frappe

# Obtener STCT de IEPS (contiene cuotas)
stct = frappe.get_doc("Sales Taxes and Charges Template", "STCT - IVA Nacional 16% - IEPS - TC")

# Buscar filas IEPS Cuota
for tax in stct.taxes:
    if "IEPS" in tax.description and "Cuota" in tax.description:
        print(f"Fila {tax.idx}: {tax.description}")
        print(f"  charge_type: {tax.charge_type}")  # ← DEBE SER "On Item Quantity"
        print(f"  rate: {tax.rate}")
        print()

# RESULTADO ESPERADO:
# Fila X: IEPS Tabaco Cuota
#   charge_type: On Item Quantity  ← ✅ CORRECTO (no "On Net Total")
#   rate: 0.0
```

### 2.2 Verificar orden fiscal IEPS→IVA
```python
# Verificar que IEPS aparece ANTES de IVA
ieps_idx = None
iva_idx = None

for tax in stct.taxes:
    if "IEPS" in tax.description:
        ieps_idx = tax.idx
    if "IVA" in tax.description and iva_idx is None:
        iva_idx = tax.idx

print(f"IEPS en índice: {ieps_idx}")
print(f"IVA en índice: {iva_idx}")
print(f"Orden correcto: {ieps_idx < iva_idx if ieps_idx and iva_idx else 'N/A'}")
# DEBE MOSTRAR: True
```

### 2.3 Contar STCT generados
```python
# Contar templates activos nuevos
stct_nuevos = frappe.get_all(
    "Sales Taxes and Charges Template",
    filters={"disabled": 0},
    fields=["name", "creation"]
)

print(f"Total STCT activos: {len(stct_nuevos)}")
# DEBE SER: 8 (o 7 si Frontera no aplica)
```

---

## 🧪 PASO 3: TESTING FUNCIONAL

### 3.1 Crear Sales Invoice de prueba
```python
# En consola Python:
import frappe
from frappe.utils import nowdate

# Crear SI con item IEPS Cuota
si = frappe.new_doc("Sales Invoice")
si.customer = "TEST-CUSTOMER-001"
si.company = "Tauro Cigarettes SA de CV"
si.posting_date = nowdate()

# Agregar item con IEPS Cuota
si.append("items", {
    "item_code": "TEST-IEPS-TABACO-001",
    "qty": 10,  # 10 cajetillas
    "rate": 50.00
})

# Asignar STCT con IEPS
si.taxes_and_charges = "STCT - IVA Nacional 16% - IEPS - TC"

# Guardar DRAFT (no submit aún)
si.insert()
print(f"SI creada: {si.name}")
```

### 3.2 Verificar charge_type persiste en Draft
```python
# Recargar SI y verificar taxes
si.reload()

for tax in si.taxes:
    if "IEPS" in tax.description and "Cuota" in tax.description:
        print(f"DRAFT - {tax.description}")
        print(f"  charge_type: {tax.charge_type}")  # ← DEBE SER "On Item Quantity"
        print(f"  tax_amount: {tax.tax_amount}")
```

### 3.3 Submit y verificar estabilidad
```python
# Submit SI
si.submit()
print(f"SI submitted: {si.name}")

# Recargar y verificar que charge_type NO cambió
si.reload()

for tax in si.taxes:
    if "IEPS" in tax.description and "Cuota" in tax.description:
        print(f"SUBMIT - {tax.description}")
        print(f"  charge_type: {tax.charge_type}")  # ← DEBE SEGUIR "On Item Quantity"
        print(f"  tax_amount: {tax.tax_amount}")

# CRITERIO ÉXITO:
# charge_type permanece "On Item Quantity" en Draft Y Submit
# tax_amount NO cambió entre Draft y Submit
```

---

## 🚨 ROLLBACK (SI FALLA)

### Escenario A: Regeneración falló parcialmente
```bash
# 1. Restaurar backup
cd sites/facturacion.dev/private/backups
bench --site facturacion.dev restore backup-pre-regeneracion-stct-e4-2025-10-27.sql.gz

# 2. Revertir cambios código
git checkout HEAD~1  # Volver commit anterior

# 3. Migrate a versión anterior
bench --site facturacion.dev migrate
```

### Escenario B: STCT generados incorrectos
```python
# En consola Python:
import frappe

# Deshabilitar STCT nuevos (no borrar - conservar historial)
stct_nuevos = frappe.get_all("Sales Taxes and Charges Template",
                              filters={"disabled": 0})

for stct in stct_nuevos:
    doc = frappe.get_doc("Sales Taxes and Charges Template", stct.name)
    doc.disabled = 1
    doc.save()
    print(f"Deshabilitado: {stct.name}")

frappe.db.commit()

# Reactivar STCT viejos (si los deshabilitó el generador)
# (requiere identificar nombres viejos en backup)
```

---

## 📊 CRITERIOS ÉXITO

### ✅ Regeneración exitosa si:
1. 7-8 STCT creados (según company tenga Frontera o no)
2. Filas IEPS Cuota tienen `charge_type="On Item Quantity"`
3. Orden fiscal: IEPS antes de IVA
4. STCT viejos deshabilitados (no borrados)
5. No hay errores en logs durante generación

### ✅ Testing funcional exitoso si:
1. SI Draft: charge_type permanece "On Item Quantity"
2. SI Submit: charge_type NO cambia a "Actual" (problema Pre-E4)
3. tax_amount idéntico Draft vs Submit (±$0.05 tolerancia)
4. item_wise_tax_detail preservado correctamente

---

## 🔗 SIGUIENTE PASO

Una vez verificados todos los criterios de éxito, proceder con:

**PASO 7: Refactorizar mapeo a tabla constantes**
- Crear `facturacion_mexico/utils/mapeo_charge_type.py`
- Migrar diccionario `_MAPEO_CHARGE_TYPE` a constantes
- Actualizar imports en `generador_templates_fiscal.py`
- Testing regeneración con nueva arquitectura

---

**Fecha:** 2025-10-27
**Estado:** Documentado - Pendiente ejecución
**Siguiente:** Ejecutar migrate + regeneración + testing
