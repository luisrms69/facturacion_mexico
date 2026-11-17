# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-11-17
**Rama activa:** `fix/fixture-duplicado-sales-invoice-module`
**Tarea actual:** Elimina el fixture duplicado `custom_fields_sales_invoice.json` que revertía el
módulo de 3 campos de Sales Invoice en cada `bench migrate`. En `/ship pr` (v1.10.3).

---

## Recuperación rápida

Estoy trabajando en:
La causa raíz de que `module="Facturacion Mexico"` reapareciera tras corregir el dato: Frappe importa
**todos** los `.json` de `fixtures/` (`os.listdir`, orden alfabético), no solo los de `hooks.py`.
`custom_fields_sales_invoice.json` (residuo de PR #51) se importaba **después** de `custom_field.json`
y sobrescribía los 3 campos de SI con módulo obsoleto + opciones de `fm_fiscal_status` sin
`E-RECEIPT`/`E-RECEIPT-FACTURADO`.

Objetivo inmediato:
`/ship pr` hacia `main` con bump **v1.10.3** (PATCH). Sin merge (lo hace el usuario).

Criterio de avance:
PR con el residuo eliminado + test ampliado; tras merge: `/sync-check` + `/ship release` v1.10.3.
Validación post-despliegue en staging: `bench migrate` y confirmar que los 3 campos conservan
`module=Facturacion Fiscal` y las opciones completas de E-Receipt. (No re-ejecutar SQL
preventivamente — con el residuo eliminado, migrate re-estampa desde `custom_field.json`.)

---

## Estado actual (implementado en la rama)

- **Eliminado** `facturacion_mexico/fixtures/custom_fields_sales_invoice.json` (residuo de #51). Los 3
  campos (`fm_fiscal_section`, `fm_fiscal_status`, `fm_factura_fiscal_mx`) quedan definidos de forma
  canónica y completa en `custom_field.json` (module=Facturacion Fiscal, opciones completas).
- **`tests/test_fixtures_module_integrity.py` ampliado:** escanea TODOS los `fixtures/*.json` —
  guarda contra módulos fuera de `modules.txt` (en cualquier fixture) y contra Custom Fields
  duplicados entre archivos. Simulación confirmó que ambas guardas disparan con el residuo presente.
- `__init__.py` — bump `1.10.2 → 1.10.3` (PATCH).

Validado en `test-facturacion.localhost`: 7/7 del test de integridad; ruff OK.

---

## Decisiones vigentes no evidentes en el código

- Frappe importa fixtures por **carpeta** (`import_fixtures` → `os.listdir(fixtures/)`), no por la lista
  `fixtures` de `hooks.py` (esa lista solo rige el export). → cualquier `.json` en `fixtures/` se
  importa; dos archivos con el mismo Custom Field `name` se sobrescriben (último alfabético gana).
- Los roles "Facturacion Mexico User/Manager/System Manager" (`role.json`/`docperm.json`) son nombres
  de rol legítimos, **no** referencias de módulo.

### Pendientes conocidos (NO bloqueantes del PR)
1. Tras merge + despliegue: `bench migrate` en staging y verificar los 3 campos.
2. Observación relacionada (fuera de alcance): `test_records.json` también se importa en cada migrate
   por el mismo mecanismo de carpeta; revisar aparte si procede.

---

## No commitear
- `facturacion_mexico/one_offs/*` · `docs/audit/*` · `scripts/*` locales · `working_docs/private/`.
