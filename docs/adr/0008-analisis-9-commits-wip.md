# ADR 0008 — ANÁLISIS DETALLADO: 9 COMMITS WIP
===============================================
Fecha: 2026-05-01
Rango: fix/ieps-tabaco-dual-campos-tax-breakup → feature/e4-ieps-on-item-quantity
Propósito: Decidir si incluir estos commits antes del primer timbrado en producción

---

## Resumen ejecutivo

| # | Hash | Título | Estado | ¿Bloquea timbrado? |
|---|------|--------|--------|:------------------:|
| 1 | 3fdb47ba | feat: 8 STCT específicos + ITT automático | Completo (Fase 1/4) | No |
| 2 | 26e8bc50 | refactor: fuente de verdad única Item Groups | Completo | No |
| 3 | 3eae7c96 | fix: carga tax rows + eliminar JS legacy | Completo | No |
| 4 | 1201bb48 | refactor: single source of truth roles fiscales | **BREAKING CHANGE** + datos pendientes | No |
| 5 | 54b6e512 | fix: lectura checkboxes generación STCT parcial | Completo | No |
| 6 | f15e46f9 | docs: sincronización JSON↔Python + tests | Solo docs/tests | No |
| 7 | dded56d2 | fix: forzar carga STCT + detectar bugs ERPNext | Parcial — 2 bugs detectados sin resolver | No |
| 8 | a125521c | fix: FIX-V1 cuotas IEPS en draft | Parcial — solo draft, submit falla | No |
| 9 | d933c851 | chore: checkpoint seguridad WIP ITT por item | **WIP EXPLÍCITO** | No |

**Conclusión anticipada:** Ninguno de los 9 commits toca `timbrado_api.py`. El flujo de timbrado es idéntico al de `fix/ieps-tabaco`. Los 9 commits resuelven (parcialmente) el problema de cuotas IEPS en Sales Invoice, que es independiente del timbrado.

---

## COMMIT 1 — `3fdb47ba`
### `feat(e1): implementar sistema 8 STCT específicos + generación automática ITT`

**Problema que resuelve:**
Los templates STCT consolidados generaban hasta 19 filas en cada Sales Invoice, la mayoría en $0. Un cliente sin IEPS veía 5 filas de IEPS en cero, más 6 de retenciones en cero. Visualmente confuso y reportes "cluttered".

**Solución:**
Reemplaza los 2 templates consolidados ("IVA 16% - México", "IVA 8% Frontera") por 8 templates específicos:
- `IVA Nacional - Básico` (1 fila: solo IVA)
- `IVA Nacional - IEPS` (6 filas: IEPS + IVA)
- `IVA Nacional - Retenciones` (3 filas: IVA + ISR + IVA Ret)
- `IVA Nacional - Total` (8 filas: todo)
- Los 4 equivalentes para Frontera

**Archivos modificados:**
- `generador_templates_fiscal.py`: reescritura completa -546 líneas → nuevo sistema `generate_8_stct_for_company()`
- `configuracion_fiscal_mexico.py/.js`: botón "Generate Templates" simplificado, eliminado "Preview"
- `mapeo_cuenta_fiscal_mexico.json`: soporte fuzzy matching nombres de cuentas
- `sales_invoice_ieps.py`: ajuste imports (sin cambios funcionales)

**¿Está completo?** Fase 1/4 completada según el plan. Fases 2-4 (autoselección inteligente + función rectora + tests E2E) quedan pendientes.

**¿Su ausencia rompe algo?** No. En `fix/ieps-tabaco` el generador sigue funcionando con la arquitectura anterior (templates consolidados). Los templates existentes siguen siendo válidos.

---

## COMMIT 2 — `26e8bc50`
### `refactor(e1): consolidar fuente de verdad única Item Groups + preparar clasificación automática`

**Problema que resuelve:**
Las constantes de Item Groups estaban dispersas en 4+ lugares: 10 constantes `IG_*`, 10 constantes `ITT_*_TITLE`, `ITEM_GROUP_ITT_MAP` manual, sin diccionario Item Group → Categoría fiscal. Cualquier cambio requería editar múltiples archivos y había riesgo de inconsistencia.

**Solución:**
Crea `TABLA_MAESTRA_GRUPOS_FISCALES` con 10 filas que auto-genera 5 constantes derivadas vía comprehensions. Elimina código fallback legacy que buscaba ITT por `title` (ahora solo busca por `name`).

**Archivos modificados:**
- `setup/item_groups.py`: consolidación constantes (+46 / -42 líneas netas)
- `utils/clasificacion_items.py`: archivo nuevo, función `clasificar_items_documento()`
- `tests/test_clasificacion_items.py`: archivo nuevo, 7 tests (0.455s, deterministas)

**¿Está completo?** Sí. Los 7 tests pasan. Es prerequisito arquitectónico para la autoselección STCT.

**¿Su ausencia rompe algo?** No en `fix/ieps-tabaco`. Pero es necesario si se usa el `before_validate` hook de `sales_invoice_automated_tax.py` que llama `clasificar_items_documento()`.

---

## COMMIT 3 — `3eae7c96`
### `fix(e1): corregir generación templates + carga tax rows + eliminar código JS legacy`

**Problema que resuelve:**
Los 8 templates STCT del commit 1 aparecían en el selector de Sales Invoice pero la tabla `taxes` quedaba vacía. Root cause: el generador pre-establecía el campo `name` en los child records, impidiendo la inicialización normal de Frappe. Además, el hook Python solo asignaba `taxes_and_charges` pero no cargaba las filas.

**Tres sub-fixes:**
1. **Generador:** eliminar `"name": title` al crear templates → Frappe gestiona el autonaming
2. **Hook Python** (`sales_invoice_automated_tax.py`): agrega carga de tax rows via `get_taxes_and_charges()` nativo de ERPNext, limpia tabla taxes y la repuebla
3. **JS legacy** (`sales_invoice.js`): elimina función `_fm_apply_branch_tax_template()` (68 líneas) que buscaba templates viejos `like '%IVA 16%'` — reemplazada por stub vacío

**¿Está completo?** Sí. Fix verificado en UI, workflow final documentado en el commit.

**¿Su ausencia rompe algo?** Si se usa el commit 1 sin este fix, los STCT aparecen en el selector pero la tabla de impuestos queda vacía. El hook del commit 3 es el que realmente hace funcionar la autoselección.

---

## COMMIT 4 — `1201bb48`
### `refactor(fiscal): consolidar single source of truth roles fiscales + completar constantes 18 roles`

**Problema que resuelve:**
Los nombres de roles fiscales estaban hardcodeados con porcentajes ("IVA por Pagar (16%)", "IVA por Pagar (8%)") en 134+ lugares del código. Esto viola el principio de que las tasas pueden cambiar por normativa/región.

**Solución:**
Crea `utils/roles_fiscales.py` con `TABLA_MAESTRA_ROLES_FISCALES` (18 roles). Los nombres cambian a semánticos sin porcentajes:
- `"IVA por Pagar (16%)"` → `"IVA por Pagar (Nacional)"`
- `"IVA por Pagar (8%)"` → `"IVA por Pagar (Frontera)"`

Migra 134+ referencias en `constantes_fiscales.py`, `sat_tipo_factor.py`, `configuracion_fiscal_mexico.py` y 3 archivos de tests.

**⚠️ BREAKING CHANGE explícito en el commit:**
> "Bases de datos existentes requieren migración de datos: Campo `rol_fiscal` en tabla `Mapeo Cuenta Fiscal Mexico`. Valores actuales: 'IVA por Pagar (16%)' → Valores nuevos: 'IVA por Pagar (Nacional)'. **Migración datos será commit separado (NO incluido en este refactor código).**"

**¿Afecta al site actual?** **NO** — `tabMapeo Cuenta Fiscal Mexico` no existe en el site actual (está en una rama que aún no se ha mergeado a main). La tabla se crea vacía en el migrate. No hay datos que migrar.

**¿Está completo?** Para código: sí. La migración de datos está documentada como pendiente pero no es necesaria en un site limpio.

**¿Su ausencia rompe algo?** No directamente. Pero el commit 5 usa las nuevas constantes del `rol_fiscal`.

---

## COMMIT 5 — `54b6e512`
### `fix(generador): corregir lectura checkboxes en generación parcial templates STCT`

**Problema que resuelve:**
El generador de templates ignoraba completamente los checkboxes `enable_ieps_*` de `Configuracion Fiscal Mexico`. Aunque el usuario desmarcara "Habilitar IEPS Azúcar", el template STCT seguía incluyendo esa fila.

**Solución:**
Agrega helper `_disponible(checkbox_enabled, rol)` que retorna `True` solo si el checkbox está activado **y** el mapeo de cuenta existe. Aplicado a IEPS y Retenciones.

**Archivos modificados:**
- `generador_templates_fiscal.py`: lógica checkboxes (+476 / -86 líneas)
- `sales_invoice_automated_tax.py`: mejora mensaje fallback cuando no encuentra STCT específico
- `tests/test_sync_roles_fiscales_json_python.py`: archivo nuevo, valida sincronización JSON↔Python

**¿Está completo?** Sí. Verificado con 3 escenarios (IEPS parcial, sin IEPS/Retenciones, con ITT en uso).

**¿Su ausencia rompe algo?** No. En `fix/ieps-tabaco` no hay `Configuracion Fiscal Mexico` y el generador viejo no conoce checkboxes. Impacto solo visible cuando se usa la UI de configuración.

---

## COMMIT 6 — `f15e46f9`
### `docs(e1): documentar sincronización JSON-Python roles fiscales + tests autoselección STCT`

**Qué contiene:**
Puramente documentación y tests. Ningún cambio funcional.

- `utils/roles_fiscales.py`: +20 líneas de comentarios explicando la limitación de Frappe (Select fields en JSON no puede importar constantes Python → requiere sincronización manual)
- `tests/test_autoseleccion_stct.py`: archivo nuevo, 7 tests para `_determinar_variante_stct()` y `_find_stct_by_variant()`
- `CLAUDE.md`: regla sobre `docs/instructions/`

**¿Está completo?** Sí (solo docs/tests).

**¿Su ausencia rompe algo?** No.

---

## COMMIT 7 — `dded56d2`
### `fix(e1): forzar carga STCT taxes siempre + detectar bugs ERPNext cuotas/totals`

**Problema que resuelve:**
Hook `_set_stct_by_branch()` solo cargaba tax rows si el campo `taxes_and_charges` **cambiaba**. Al recargar una SI que ya tenía el STCT asignado, el hook no recargaba las filas y ERPNext priorizaba el ITT del item, perdiendo las filas IVA. Resultado: Grand Total incorrecto ($6,078 en lugar de $8,020).

**Solución:**
Mueve la carga de `taxes` fuera del condicional. Agrega flag `doc.flags.__stct_applied` para evitar duplicados en el mismo request. Siempre ejecuta `doc.set("taxes", []) + doc.extend("taxes", tax_rows)`.

**También agrega:**
- `utils/calculo_impuestos.py`: función rectora `aplicar_reglas_calculo_impuestos()` (392 líneas)
- `utils/reglas_calculo_fiscal.py`: tabla maestra reglas cálculo 17 roles (453 líneas)
- `hooks.py`: mueve `corregir_ieps_cuota_final` de `before_submit` → `before_save`

**⚠️ Documenta 2 bugs de ERPNext sin resolver:**
1. `charge_type="Actual"` (cuotas IEPS fijas) excluido de `total_taxes_and_charges` → Grand Total incompleto
2. **Cuotas IEPS se vuelven $0 al hacer submit** (CRÍTICO) — los hooks de ERPNext recalculan y el ITT sobrescribe las cuotas con $0

**¿Está completo?** Parcial. El fix del hook está completo. Los 2 bugs ERPNext son conocidos y pendientes de resolver.

**¿Su ausencia rompe algo?** No en timbrado. Pero sin este fix, las SIs con STCT ya asignado no recargaban correctamente las filas de impuestos al re-abrir.

---

## COMMIT 8 — `a125521c`
### `fix(e1): implementar FIX-V1 para preservar cuotas IEPS en draft + documentar incidente git checkout`

**Problema que resuelve:**
El Bug #1 del commit 7: `charge_type="Actual"` (cuotas IEPS) excluido de `grand_total` en draft. Grand Total mostraba $8,020.82 cuando el correcto era $8,374.44 (diferencia de $353.62 de cuotas IEPS).

**Solución FIX-V1:**
Agrega `doc.calculate_taxes_and_totals()` al final de `calcular_ieps_cuota()` en `sales_invoice_ieps.py` (4 líneas). Fuerza a ERPNext a sumar las cuotas `Actual` al grand total.

**Estado post-FIX-V1 documentado:**
```
✅ Draft correcto:   $8,374.44
❌ Submit aún falla: cuotas se vuelven $0 al hacer submit (Bug #2 sin resolver)
```

**Tabla historial de pruebas (del commit):**
| SI | Estado | Grand Total | Resultado |
|----|--------|-------------|-----------|
| ACC-SINV-01668 | POST-FIX Draft | $8,020.82 | ❌ Bug ERPNext |
| ACC-SINV-01674 | FIX-V1 Draft | $8,374.44 | ✅ Correcto |
| ACC-SINV-01674 | FIX-V1 Submit | $8,020.82 | ❌ Before_submit no funcionó |
| ACC-SINV-01675 | FIX-V2 Draft | $8,374.44 | ✅ |
| ACC-SINV-01675 | FIX-V2 Submit | $8,020.82 | ❌ FRACASO + STCT desapareció |

**Importante:** `sales_invoice_ieps.py` está **COMENTADO** en `hooks.py` de e4 (`# E4 DISABLED`). El FIX-V1 existe en el archivo pero no se ejecuta porque el hook no está activo.

**¿Está completo?** Parcial. Draft resuelto. Submit sigue fallando. El autor docuemnta explícitamente el Bug #2 como bloqueante pendiente.

**¿Su ausencia rompe algo?** No directamente — el hook que contiene el FIX-V1 está comentado en e4.

---

## COMMIT 9 — `d933c851`
### `chore(e4): checkpoint de seguridad - preservar estado trabajo en progreso ITT específico por item`

**Qué contiene:**
Explícitamente declarado como checkpoint de seguridad sin implementación funcional completa.

**Archivos de código modificados:**
- `hooks.py`: reorganización de hooks IEPS comentados (+9/-3) — todos los hooks IEPS siguen comentados
- `sales_invoice_automated_tax.py`: +93 líneas (estado de investigación para ITT por item)
- `hooks_handlers/sales_invoice_ieps.py`: +37/-63 (refactoring parcial)
- `utils/mapeo_charge_type.py`: archivo nuevo, **"no probado aún"** según el commit
- `utils/reglas_calculo_fiscal.py`: +12/-10 (ajustes menores)
- `generador_templates_fiscal.py`: +9/-3

**Trabajo pendiente explícito (del commit body):**
1. Implementar `utils/itt_management.py` → **NO EXISTE**
2. Implementar `hooks_handlers/ieps_cuota_sat.py` after_save → **NO EXISTE**
3. Testing completo 3 items
4. Validar productos TASA + CUOTA (tabaco)

**Estado al momento del checkpoint:**
- La solución de ITT específico por item está investigada (5 alternativas evaluadas, 4 descartadas)
- La alternativa elegida está validada empíricamente en ACC-SINV-2025-01685
- La implementación está pendiente

**¿Su ausencia rompe algo?** No. Todos los hooks IEPS siguen comentados. El único riesgo es `mapeo_charge_type.py` (nuevo, no probado) siendo importado desde algún lugar.

---

## ANÁLISIS TRANSVERSAL

### ¿Qué problemática resuelven los 9 commits en conjunto?

El sistema de IEPS Cuota (impuesto fijo por cantidad — tabaco, alcohol, combustibles) en ERPNext tiene dos bugs:
1. En **Draft**: `charge_type="Actual"` excluido de totales → resuelto parcialmente con FIX-V1 (commit 8)
2. En **Submit**: las cuotas se vuelven $0 → **sin resolver** en el último commit

Los 9 commits son el intento de resolver esto sin hackear ERPNext core, construyendo un sistema de 8 STCT específicos y ITT por item. El trabajo está al 60% — la generación de templates funciona, la autoselección funciona para casos básicos, pero las cuotas al submit siguen fallando.

### Impacto real en el site actual (facturacion-v16.dev)

| Aspecto | Impacto |
|---------|---------|
| Timbrado | **NINGUNO** — `timbrado_api.py` no se modifica |
| SIs ya submitted/cancelled | **NINGUNO** — validate hook no se dispara sobre docs submitted |
| Edición de SIs en Draft | **POTENCIAL** — validate busca STCT por variante y puede fallar si no los encuentra |
| Items sin SAT code | El validate hook (activo desde e1, commit 33) sigue lanzando `throw` |
| IEPS Cuota en Submit | **SIGUE FALLANDO** — Bug #2 sin resolver en commit 9 |

### ¿Hay algún commit de los 9 que sea peligroso incluir?

**Commit 9 (d933c851) es el único con riesgo real:**
- `sales_invoice_automated_tax.py` tiene +93 líneas no documentadas en detalle (estado de investigación)
- `mapeo_charge_type.py` existe pero "no probado aún"
- El sistema ITT por item está incompleto: `itt_management.py` no existe, el hook `after_save` de IEPS Cuota SAT no existe

Si alguna de esas 93 líneas en `sales_invoice_automated_tax.py` tiene un `frappe.throw()` en condición alcanzable, puede bloquear la edición de SIs sin warning previo.

### Recomendación final sobre los 9 commits

**Opción A — Incluir commits 1-8, excluir el 9:**
Los commits 1-8 son un conjunto coherente y mayormente completo. El generador de 8 STCT funciona, la autoselección funciona, el validate hook funciona. El único problema conocido es Bug #2 (cuotas IEPS en submit) que está documentado pero no resuelto — y los hooks IEPS están comentados de todos modos.

Para hacer esto: hay que crear una rama desde el commit `a125521c` (commit 8).

**Opción B — Usar solo `fix/ieps-tabaco` (commit 33):**
La opción más conservadora. Evita completamente el sistema de 8 STCT y la autoselección. Los templates consolidados siguen funcionando. Las cuotas IEPS en draft y submit tienen sus bugs conocidos del commit 33.

**Para el objetivo inmediato (primer timbrado):** La Opción B es suficiente. El timbrado no depende de ninguno de estos 9 commits. Se puede mergear e4 completo (o hasta el commit 8) cuando el sistema de IEPS Cuota en submit esté resuelto.
