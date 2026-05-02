# ADR 0007 — ANÁLISIS DE RIESGO: CHECKOUT A feature/e4-ieps-on-item-quantity
==============================================================================
Fecha: 2026-05-01
Site analizado: facturacion-v16.dev (datos reales migrados)
Branch actual: main
Branch objetivo: feature/e4-ieps-on-item-quantity (42 commits sobre main)

---

## VEREDICTO RÁPIDO

| Pregunta | Respuesta |
|----------|-----------|
| ¿Riesgo de pérdida de datos? | **NO** — ningún cambio sobreescribe ni elimina datos existentes |
| ¿Riesgo operativo al editar SIs? | **SÍ** — validate hook nuevo bloquea SIs con items sin código SAT |
| ¿Checkout a e4 completo es seguro? | **CONDICIONAL** — los 9 commits WIP incluyen refactoring incompleto |
| ¿Recomendación? | **Usar `fix/ieps-tabaco-dual-campos-tax-breakup` (commit 33)** |

---

## 1. PATCH DE MIGRACIÓN

**Archivo:** `patches/v1_0/migrate_customer_tax_category_to_fm_tax_regime.py`

### ¿Es idempotente?
**Sí, explícitamente diseñado para ello.** El patch tiene tres casos mutuamente excluyentes:

| Caso | Condición | Acción |
|------|-----------|--------|
| Ya migrado | `tax_category == fm_tax_regime` | No hace nada (`already_equal += 1`) |
| Migrar | `fm_tax_regime` vacío | Copia sin sobreescribir |
| Conflicto | Ambos tienen valores distintos | **No toca nada**, reporta `mismatch` |

La Fase 2 (limpieza) solo vacía `tax_category` cuando el destino quedó idéntico. Si se ejecuta dos veces, en la segunda pasada todos los registros caen en Caso 1 → cero operaciones.

### ¿Puede romper datos?
**No.** El único escenario problemático es el Caso 3 (conflicto): un Customer que ya tenía `fm_tax_regime` con un valor distinto a `tax_category` queda sin migrar y el patch lo reporta. No hay sobreescritura silenciosa.

### Precondición crítica
El patch verifica con `_exists_custom_field("Customer", "fm_tax_regime")` antes de hacer cualquier cosa. Si el fixture no aplicó el campo, el patch aborta limpiamente con `frappe.throw`. No puede correrse en vacío.

**Con el site actual (19 customers con RFC):** el patch correrá en lotes de 500, verificará si algún Customer tiene `tax_category` poblado, y migrará o reportará conflicto. Tiempo estimado: bajo un segundo.

---

## 2. NUEVOS DOCTYPES

### Configuracion Fiscal Mexico
- **autoname:** `format:CFM-{company}` → un registro por empresa
- **No es Single:** tabla separada creada vacía en el migrate
- **Campo obligatorio real:** `company` (Link) y `mapeo_cuentas` (Table child)
- **¿Toca datos existentes al crearse?** No. La tabla `tabConfiguracion Fiscal Mexico` se crea vacía.
- **Dependencia en código:** `sales_invoice_ieps.py` la consulta con `frappe.db.exists(...)` — si no existe el doc, retorna `False` y el código decide si continúa o falla. **PERO** todos los hooks de `sales_invoice_ieps.py` están comentados en `e4` (ver sección 3), así que nunca se llega a ese código en esta rama.

### Ieps Cuota SAT
- **No Single**, autoname por naming_series
- Tabla vacía al crear. Campos requeridos: `company`, `clave_prod_serv`, `cuota`, `vigencia_desde`
- No tiene ningún hook ni evento que se dispare sobre datos existentes
- Se usaría cuando el usuario registre cuotas IEPS (tabaco, combustibles, etc.)

### Mapeo Cuenta Fiscal Mexico
- Child table de `Configuracion Fiscal Mexico`
- Se crea vacío con el migrate
- Sin impacto en datos existentes

**Conclusión sobre DocTypes nuevos:** Los 3 crean tablas vacías. Zero impacto destructivo.

---

## 3. DIFERENCIAS EN HOOKS.PY

### Lo que cambia entre main y e4

**`after_migrate` — diferencia crítica:**

| | main | e4 |
|-|------|----|
| `after_migrate` | solo `apply_customization` | `apply_customization` + **`assign_itt_to_groups`** |

`assign_itt_to_groups` se ejecuta **automáticamente** en cada `bench migrate`. Con los 21 Item Groups del site y los 37 items existentes, este job asigna ITT (Item Tax Templates) a grupos de items automáticamente. **Riesgo:** puede modificar las plantillas de impuestos en los Item Groups/Items existentes.

**`doc_events["Sales Invoice"]` — diferencia importante:**

| | main | e4 |
|-|------|----|
| Sales Invoice hooks | No existe (comentado) | `before_validate` + `validate` activos |

En main no hay hooks de Sales Invoice. En e4, cada vez que se edita o guarda una SI, se ejecutan:

```python
# before_validate:
sales_invoice_automated_tax.before_validate(doc)
  → detecta branch, asigna STCT automáticamente
  → llama _find_stct_by_variant() que busca Item Tax Templates por nombre
  → si no encuentra STCT → frappe.throw() [ver riesgo abajo]

# validate:
sales_invoice_automated_tax.validate(doc)
  → verifica que cada item tenga fm_producto_servicio_sat
  → si algún item no tiene código SAT → frappe.throw("Línea N sin código SAT...")
```

**`before_save` — todos los hooks IEPS están comentados:**
```python
"before_save": [
    # E4 DISABLED: "facturacion_mexico.hooks_handlers.sales_invoice_ieps.calcular_ieps_cuota",
    # E4 DISABLED: "facturacion_mexico.hooks_handlers.sales_invoice_ieps.ajustar_base_iva_combustibles",
    # E4 DISABLED: "facturacion_mexico.hooks_handlers.sales_invoice_ieps.corregir_ieps_cuota_final",
],
```

Los hooks de IEPS cuota están deliberadamente desactivados en e4 (`# E4 DISABLED`). El sistema de IEPS manual fue reemplazado por el enfoque nativo de ERPNext con `charge_type="On Item Quantity"`.

---

## 4. LOS 9 COMMITS WIP

**Commits entre `fix/ieps-tabaco` (commit 33) y `e4` (commit 42):**

| # | Commit | Estado |
|---|--------|--------|
| 34 | `feat(e1): implementar sistema 8 STCT específicos + generación automática ITT` | Funcional |
| 35 | `refactor(e1): consolidar fuente de verdad única Item Groups` | Refactoring |
| 36 | `fix(e1): corregir generación templates + carga tax rows + eliminar código JS legacy` | Fix |
| 37 | `refactor(fiscal): consolidar single source of truth roles fiscales + 18 roles` | Refactoring |
| 38 | `fix(generador): corregir lectura checkboxes en generación parcial templates STCT` | Fix |
| 39 | `docs(e1): documentar sincronización JSON-Python roles fiscales + tests autoselección` | Docs/tests |
| 40 | `fix(e1): forzar carga STCT taxes siempre + detectar bugs ERPNext cuotas/totals` | Fix activo |
| 41 | `fix(e1): implementar FIX-V1 para preservar cuotas IEPS en draft` | Fix parcial |
| 42 | `chore(e4): checkpoint de seguridad - preservar estado trabajo en progreso ITT específico por item` | **WIP EXPLÍCITO** |

**Archivos de código tocados por los 9 commits WIP** (excluyendo docs):
- `config/sat_tipo_factor.py`
- `facturacion_fiscal/config/constantes_fiscales.py`
- `facturacion_fiscal/doctype/configuracion_fiscal_mexico/configuracion_fiscal_mexico.js/.py`
- `facturacion_fiscal/doctype/mapeo_cuenta_fiscal_mexico/mapeo_cuenta_fiscal_mexico.json`
- `facturacion_fiscal/setup/generador_templates_fiscal.py`
- `hooks.py`
- `hooks_handlers/sales_invoice_automated_tax.py` ← **el validate hook activo**
- `hooks_handlers/sales_invoice_ieps.py` ← comentado en hooks, no se ejecuta
- `public/js/sales_invoice.js`
- `setup/item_groups.py` ← ejecutado en `after_migrate`
- Tests varios

**`timbrado_api.py` NO aparece en los 9 WIP.** El timbrado no cambió en esta fase.

### Riesgo del commit 42 (WIP ITT específico por item)

El commit 42 preserva trabajo en progreso del sistema ITT específico por item. El hook `sales_invoice_automated_tax.validate` en este commit puede tener validaciones que busquen STCT por nombre de variante (`IVA_GENERAL`, `IVA_FRONTERA`, `RESICO_GENERAL`, etc.). Si esos templates no existen en el site, el validate puede lanzar `frappe.throw()` al intentar guardar cualquier SI.

---

## 5. TIMBRADO_API.PY

`timbrado_api.py` fue modificado antes del commit 33 (en la fase e1-e4 del sistema de impuestos). Los 9 WIP **no lo tocan**. Dado que `test_connection()` respondió exitosamente en el módulo 2 con la versión actual (main), y que `timbrado_api.py` en e4 incorpora mejoras al puente SI→PAC pero sin cambiar el flujo de timbrado base, el riesgo de regresión en timbrado es bajo.

El diff de `timbrado_api.py` no pudo obtenerse vía API (posiblemente por tamaño), pero el hecho de que esté incluido en commits 27-33 (E4: puente SI→PAC read-only) y no en los 9 WIP confirma que la versión estable está en el commit 33.

---

## 6. RIESGO OPERATIVO PRINCIPAL

### Validate hook sobre Sales Invoices con items sin código SAT

Con el checkout a cualquier rama >= e1, el hook `validate` de Sales Invoice ejecuta:

```python
sat_field = frappe.db.get_value("Item", row.item_code, "fm_producto_servicio_sat")
if not sat_field:
    frappe.throw(f"Línea {i} sin código SAT...")
```

El site tiene **21 de 37 items sin `fm_producto_servicio_sat`**. Esto significa:

- Las 762 SIs existentes submitted/cancelled **no se ven afectadas** (el hook solo corre en `validate`, no sobre documentos ya submitted)
- Cualquier SI en estado **Draft** que use esos 21 items **no podrá guardarse** hasta que se configure el código SAT
- Las SIs nuevas con esos items también fallarán en la primera guardada

**Este es el bloqueante operativo más importante.** Antes de hacer checkout, deben configurarse los 21 items con código SAT, o la operación quedará parcialmente paralizada.

### assign_itt_to_groups en after_migrate

En cada `bench migrate`, `setup/item_groups.py` asignará ITT a los Item Groups automáticamente. Sin `Configuracion Fiscal Mexico` configurada y sin los STCTs existentes en el site, esta función puede:
- Crear Item Tax Templates nuevos (no destructivo)
- O fallar silenciosamente si no encuentra la configuración fiscal

---

## 7. RESUMEN DE RIESGOS

| Riesgo | Nivel | Causa | Consecuencia |
|--------|-------|-------|--------------|
| Pérdida de datos en migrate | **NINGUNO** | Nuevos DocTypes = tablas vacías | — |
| Patch rompe Customers | **NINGUNO** | Patch es idempotente y conservador | — |
| SI en draft con items sin SAT | **ALTO** | Validate hook nuevo + 21 items sin código | SI no puede guardarse |
| assign_itt_to_groups en migrate | **MEDIO** | after_migrate nuevo, sin config previa | Puede modificar Item Groups |
| ITT específico por item WIP | **MEDIO** | Commit 42 en progreso | Validate puede buscar STCT que no existen |
| Timbrado regresión | **BAJO** | timbrado_api.py no tocado en WIP | Sin cambio en flujo de timbrado |

---

## 8. RECOMENDACIÓN

### Opción A — Checkout a `fix/ieps-tabaco-dual-campos-tax-breakup` (commit 33) ✅ RECOMENDADA

- 33 commits estables, sin WIP explícito
- Incluye: migración tax_category, nuevos DocTypes, IEPS cuota fix, puente SI→PAC
- **No incluye:** sistema 8 STCT específicos (WIP), FIX-V1 cuotas draft (parcial)
- El validate hook es la versión estable anterior al refactoring STCT

### Opción B — Checkout a `feature/e4-ieps-on-item-quantity` completo (commit 42) ⚠️

- 42 commits, los últimos 9 en progreso
- El validate hook puede fallar en SIs con STCT no configurados
- Última salvaguarda antes de checkout: verificar que `_find_stct_by_variant()` tiene fallback

---

## 9. ORDEN CORRECTO DE OPERACIONES

Independientemente de la opción elegida:

```
ANTES DEL CHECKOUT
──────────────────
1. Backup completo de la base de datos
   mysqldump -u _516552b8cbcbc35c -pYkedgj5MpEdlGnYc _516552b8cbcbc35c > backup_pre_e4_$(date +%Y%m%d_%H%M%S).sql

2. Configurar los 21 items sin código SAT
   (evita que el validate hook bloquee SIs existentes en draft)

CHECKOUT Y MIGRATE
──────────────────
3. git checkout fix/ieps-tabaco-dual-campos-tax-breakup   (o e4 si se acepta el riesgo)
4. bench --site facturacion-v16.dev migrate
   → Crea tablas: tabConfiguracion Fiscal Mexico, tabIeps Cuota SAT, tabMapeo Cuenta Fiscal Mexico
   → Ejecuta patch: migrate_customer_tax_category_to_fm_tax_regime (19 customers)
   → Ejecuta after_migrate: apply_customization + assign_itt_to_groups

POST-MIGRATE
────────────
5. Verificar que los 3 nuevos DocTypes existen
6. Verificar resultado del patch en patch log (bench --site ... console: frappe.get_all("Patch Log", ...))
7. Verificar que assign_itt_to_groups no rompió Item Groups
8. Crear Configuracion Fiscal Mexico para la Company principal
9. Probar guardado de una SI con item que SÍ tiene código SAT
10. Probar timbrado con timbrar_factura()
```
