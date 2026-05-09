# ADR-0019: Primera implementación Release Candidates v0.1

**Fecha:** 2026-05-08 / 2026-05-09  
**Estado:** En progreso  
**Contexto:** Cierre del MVP y validación de instalación limpia

---

## Contexto

Después de completar el MVP funcional (PPD, Complemento Pago MX, FFM status, Settings mínimos), se inició el proceso de preparación para el primer release (v0.1.0) con tres etapas:

- **RC0** — Baseline funcional antes de limpieza (tag `v0.1.0-rc0`)
- **RC1** — Correcciones de fixtures/filter sin eliminar patches (tag `v0.1.0-rc1`)
- **RC2** — Patches desactivados; instalación sin migraciones históricas (tag `v0.1.0-rc2`)
- **v0.1.0** — Release final taggeado

---

## Proceso seguido

### Auditorías realizadas

1. **Auditoría de patches** — Se clasificaron los 9 patches canónicos. Conclusión: todos son idempotentes en instalación limpia. Para RC2 se comentaron todos.

2. **Auditoría DB vs schema/fixtures** — Se comparó BD existente vs `custom_field.json` vs hooks filter. Se encontraron discrepancias importantes.

3. **Validación instalación limpia** — Se creó sitio `test-fm-v010.localhost` con ERPNext v16 limpio y se instaló `facturacion_mexico v0.1.0`.

---

## Problemas encontrados y resolución

### P1 — Desincronía hooks filter vs custom_field.json

**Problema:** El filter de fixtures en `hooks.py` no coincidía con los campos en `custom_field.json`. Campos en JSON pero no en filter serían eliminados en próximo `bench export-fixtures`. Campos en filter pero no en JSON son referencias muertas.

**Resolución (RC1):** Se alinearon filter y JSON a 75 campos exactos. Se eliminaron 3 referencias muertas (`fm_regimen_fiscal`, `fm_column_break_fiscal_customer`, `fm_informacion_fiscal_mx_section`). Se agregaron campos faltantes al filter.

**PR:** #106

---

### P2 — Branch-fm_certificate_ids no existía en fixture

**Problema:** El campo `Branch-fm_certificate_ids` estaba en el hooks filter y era referenciado en código (`multi_sucursal/utils.py`, `branch_fiscal_fields.py`) pero no tenía definición en `custom_field.json` ni existía en BD.

**Resolución:** Se agregó la definición completa al fixture JSON.

---

### P3 — Customer-fm_tax_regime apuntaba a DocType incorrecto

**Problema:** El campo `Customer-fm_tax_regime` (Link field) tenía `options: "Tax Category"` en el fixture, apuntando al DocType nativo vacío de ERPNext en lugar de `Regimen Fiscal SAT` (el catálogo propio con 20 registros). El dropdown aparecía vacío.

**Resolución:** Se corrigió `options` en `custom_field.json` a `"Regimen Fiscal SAT"`.

**Causa raíz:** El campo fue creado como reemplazo de `tax_category` y heredó el mismo `options` sin actualizarlo.

---

### P4 — Branch: layout desordenado por idx=0 en custom fields

**Problema:** Los Custom Fields de Branch aparecían en desorden en la UI del formulario. Las secciones (Gestión de Folios, Gestión de Certificados, Estadísticas) no existían en el fixture. Los campos que referenciaban esas secciones como `insert_after` obtenían `idx=0` porque el target no existía en BD al momento de la importación del fixture.

**Causa técnica identificada:**
- `frappe.get_meta(dt, cached=False)` en `Custom Field.before_save()` usa la meta completa (nativos + custom) para calcular `idx`
- `company` NO es campo nativo de Branch en v16 — es un Custom Field de ERPNext. En el site de prueba no existía como Custom Field antes de importar nuestros fixtures
- Por tanto `insert_after: "company"` no encontraba el campo → `idx=0`
- Frappe procesa el fixture JSON en orden, pero si el target del `insert_after` no existe aún en BD, el campo queda en `idx=0` y el orden visual se rompe

**Resolución:**
1. Se agregaron los 6 campos estructurales faltantes al fixture: `folio_management_section`, `column_break_folios_1`, `column_break_folios_2`, `certificate_management_section`, `statistics_section`, `column_break_stats_1`
2. Se cambió `fm_fiscal_configuration_section.insert_after` de `"company"` a `"branch"` — único campo nativo que SÍ existe en la meta de Branch
3. Se reordenaron todos los campos Branch en el JSON siguiendo orden topológico para que cada `insert_after` sea procesado después de su target
4. Se eliminaron 2 campos de prueba sin uso: `fm_enable_fiscal_test`, `fm_test_field_unique_2025`

**Regla aprendida:** Para fixtures de Custom Fields en DocTypes nativos de ERPNext/Frappe:
- Verificar que el campo referenciado en `insert_after` SÍ existe como campo nativo del DocType (en `tabDocField`, no solo en `tabCustom Field`)
- Si `insert_after` apunta a un campo nativo que no existe → `idx=0` → layout roto
- Solo un campo debe anclarse a campo nativo. Los demás deben encadenarse entre sí.

---

### P5 — Configuracion Fiscal Mexico: rol_fiscal con nombre obsoleto

**Problema:** La función JS `add_base_roles()` en el wizard de Configuracion Fiscal Mexico inicializaba la tabla con `"IVA por Pagar (16%)"`, nombre que ya no coincide con las opciones del Select field (`"IVA por Pagar (Nacional)"`). El wizard fallaba al guardar.

**Causa raíz:** La función JS fue escrita con el nombre antiguo antes de la migración a nomenclatura semántica (sin porcentajes) y nunca se actualizó cuando se cambió el DocType JSON.

**Resolución:** Se eliminó la función `add_base_roles()` del JS. La inicialización ahora delega completamente al servidor vía `sincronizar_tabla_con_alcance()` que usa las constantes correctas de `roles_fiscales.py`.

**Problema secundario detectado:** `enable_exportacion` tenía `default: "1"`, haciendo que Exportación (IVA 0%) apareciera requerida por defecto en todos los negocios aunque no la necesiten. Se cambió a `default: "0"`.

---

### P6 — Campos SI con idx=0 (pendiente de resolver)

**Problema identificado, NO resuelto aún:**

Los siguientes Custom Fields de Sales Invoice tienen `idx=0` porque su `insert_after` apunta a campos que fueron migrados a Factura Fiscal Mexico y ya no existen en SI:

| Campo | insert_after roto | Causa |
|---|---|---|
| `fm_multi_sucursal_section` | `fm_requires_stamp` | Migrado a FFM |
| `fm_addenda_section` | `fm_section_break_cfdi` | Migrado a FFM |
| `fm_ereceipt_section` | `fm_payment_method_sat` | Migrado a FFM |
| `fm_folio_reserved` | `fm_serie_folio` | Migrado a FFM |
| `fm_last_status_update` | `fm_column_break_fiscal` | Desaparecido |
| `fm_pending_amount` | `fm_payment_status` | Desaparecido |

**Impacto:** Los 3 Section Breaks con `idx=0` se renderizan al inicio del formulario SI, desplazando el layout nativo y causando que el campo nativo `title` quede visible. El campo `title` no tiene `hidden=1` en el DocType nativo de ERPNext.

**Pendiente:** Identificar anclas correctas en el SI actual y corregir `insert_after` en fixture.

---

### P7 — Problemas conocidos del wizard Configuracion Fiscal Mexico (pendiente)

1. La columna "Cuenta de Impuestos" lista grupos de cuentas además de cuentas hoja (falta filtro `is_group=0` en `set_query`)
2. No valida consistencia entre forma de pago de la FFM y la del Complemento Pago MX

---

## Estado al momento de este ADR

### Resuelto en esta sesión
- RC0, RC1, RC2 taggeados (`v0.1.0-rc0`, `v0.1.0-rc1`, `v0.1.0-rc2`)
- Tag `v0.1.0` creado
- Fixture/filter de Branch corregido (layout funcional)
- `Customer-fm_tax_regime` apunta a DocType correcto
- Configuracion Fiscal Mexico wizard: nombres de roles correctos, `enable_exportacion` default=0
- Campos de prueba Branch eliminados

### Pendiente de resolver antes de primera instalación productiva
1. SI custom fields con `idx=0` (6 campos con `insert_after` roto)
2. Validaciones pendientes del wizard Configuracion Fiscal Mexico
3. Flujo completo de Sales Invoice en sitio nuevo (STCT automático via Branch)
4. Mapeo Reclasificacion Fiscal Payment Entry: mejorar UX y validación
5. Pruebas de timbrado en sitio nuevo con credenciales sandbox
6. Issues abiertos: #108, #109, #110, #111, #112

---

## Lecciones aprendidas

1. **Fixtures de Custom Fields requieren orden topológico estricto** — El `insert_after` debe apuntar a un campo que ya exista en la meta del DocType al momento de importación. Si el target es un Custom Field de otro fixture o app, puede no existir aún.

2. **`company` en Branch no es campo nativo en ERPNext v16** — En bench v16, `company` en Branch es un Custom Field de ERPNext, no nativo. Anclar a `"company"` falla en instalaciones limpias donde ese campo no existe antes de nuestros fixtures.

3. **export-fixtures después de correcciones manuales** — Cualquier corrección de `insert_after` en el JSON requiere verificación de que el orden topológico sea correcto. El orden en el JSON SÍ importa.

4. **Diagnóstico primero, implementar con autorización** — El flujo obligatorio (diagnosticar → reportar → esperar autorización → implementar) debe respetarse siempre. Las correcciones sin autorización generan deuda técnica y pérdida de confianza.

5. **Correcciones deben ser universales** — Todo fix debe funcionar en todos los sites del app, no solo en el site de prueba actual. Fixes de BD directos no son aceptables como solución final.
