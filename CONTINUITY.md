# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-11-15
**Rama activa:** `fix/custom-field-module-facturacion-fiscal`
**Tarea actual:** Corrección del error de migración `LinkValidationError: Could not find Module
(for export): Facturacion Mexico`. En `/ship pr` (v1.10.2).

---

## Recuperación rápida

Estoy trabajando en:
El fix del error de `bench migrate` en staging (`erpstagingacti.buzola.mx`) provocado por el patch de
ERPNext `restrict_company_address_flag`. Causa raíz: el fixture `custom_field.json` administraba
`Address-is_your_company_address` (campo **propiedad de ERPNext**) y, además, 18 custom fields apuntaban
al módulo **inexistente** `Facturacion Mexico` (renombrado a `Facturacion Fiscal` en 2025).

Objetivo inmediato:
`/ship pr` hacia `main` con bump **v1.10.2** (PATCH). Detenido en el gate `pr-ready` por indicación del
usuario (sin push ni PR todavía).

Criterio de avance:
PR mergeado con bump 1.10.2; luego `/sync-check` + `/ship release` v1.10.2. **Pendiente de autorización
aparte:** corrección SQL en staging (opción B) para desbloquear la migración del dato ya escrito.

---

## Estado actual (implementado en la rama)

- **`hooks.py` + `fixtures/custom_field.json`:** se retira `Address-is_your_company_address` del filtro
  de fixtures y del JSON (es de ERPNext; `install.py` solo le asigna `0`, no lo administra).
- **`fixtures/custom_field.json`:** `module "Facturacion Mexico" → "Facturacion Fiscal"` en los 17 custom
  fields propios restantes. Ningún campo del fixture referencia ya un módulo inexistente.
- **`tests/test_fixtures_module_integrity.py` (nuevo):** guarda de regresión (5 tests) — campo de ERPNext
  ausente de fixtures/hooks, sin módulo obsoleto, módulos ⊆ `modules.txt`, prefijo `fm_` en funcionales.
- **Docs:** `arquitectura.md`, `campos-fiscales.md` y `CLAUDE.md` actualizados (campo es de ERPNext;
  conteo de custom fields 97 → 96; Address 2 → 1).
- `__init__.py` — bump `1.10.1 → 1.10.2` (PATCH).

Validado en `test-facturacion.localhost`: 5/5 integridad · `test_customfield_prefix` · `test_layer1_custom_fields` 8/8 · `test_layer1_branch_custom_fields` 11/11. Ruff lint/format OK. JSON válido.

---

## Decisiones vigentes no evidentes en el código

- **`Address-is_your_company_address` es de ERPNext**, no de esta app. No se declara en fixtures. Prohibido
  volver a asignarle nuestro módulo. `install.py` conserva `address.is_your_company_address = 0` (asigna,
  no administra) para evitar el AttributeError histórico de ERPNext v16.21.1.
- **Fix en dos capas:** app (fixtures/hooks/módulo) + dato en staging. El SQL (opción B) corrige el dato ya
  escrito: 17 propios → `Facturacion Fiscal`, `Address-is_your_company_address` → `module = NULL` (valor
  canónico de ERPNext, que no asigna module al crear el campo). SQL **no ejecutado**, requiere autorización.

### Pendientes conocidos (NO bloqueantes del PR)
1. Ejecución del SQL en staging (opción B): preparado, pendiente de autorización explícita del usuario.
2. El `sync_fixtures` del próximo `bench migrate` ya aplicaría la corrección de módulo desde el fixture;
   el SQL es el desbloqueo inmediato porque los patches corren antes que los fixtures.

---

## No commitear
- `facturacion_mexico/one_offs/*` (validaciones y análisis histórico; nunca al repo).
- `docs/audit/*` (artefactos de auditoría generados localmente).
- `scripts/*` locales, `working_docs/private/`.
