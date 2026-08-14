# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-08-14
**Rama activa:** `feat/issue-215-fm-environment-guard`
**Tarea actual:** Issue #215 — guarda de ambiente fiscal por sitio (`fm_environment`); PR #226 abierto, atendiendo CodeRabbit.

---

## Recuperación rápida

Estoy trabajando en:
PR #226 (issue #215). Ya se aplicaron los fixes de CodeRabbit F-01 y F-03; F-02 y F-04 diferidos.

Plan que estoy siguiendo:
Issue #215 + ADR-0038 + reporte CodeRabbit en
`frappe-infrastructure/checkpoints/coderabbit-pr226-review.md`.

Objetivo inmediato:
Commit de F-01/F-03 hecho en la rama. Siguiente paso: `/ship push` (actualiza PR #226) — con autorización.

Criterio de avance:
Gates verdes y tests focalizados (`test_pac_environment_guard` 10/10, `test_facturacion_mexico_company_settings` 9/9).

---

## Estado actual

### Ya cerrado
- Guarda central `pac_environment.py` en `FacturAPIClient` + selección de credencial por `fm_environment`.
- **F-01 (CodeRabbit):** `get_fm_environment()` lee el `site_config.json` DEL SITIO directamente
  (`frappe.get_site_path`), NO la config mergeada → un `fm_environment` en `common_site_config.json`
  se ignora. Test de regresión `test_common_only_environment_is_rejected`.
- **F-03 (CodeRabbit):** JSON de ejemplo válido en `docs/tecnico/ambiente-fiscal.md`.
- Docs: tecnico + ADR-0038 (con lectura site-only) + nav. Bump `__version__` = 1.4.0 (MINOR).
- PR #226 abierto contra `main` (no mergeado).

### En progreso
- Nada; commit de F-01/F-03 listo en la rama.

### Pendiente inmediato
1. `/ship push` (actualiza PR #226) — autorización aparte.
2. Merge (usuario) → luego `/sync-check` + `/ship release` (tag + Release v1.4.0).
3. Configurar `fm_environment` en `site_config.json` de producción/staging antes del deploy.

### No repetir
- No usar `frappe.conf` / `frappe.get_site_config()` para el ambiente: combinan common + site.
  El ambiente es estrictamente por-sitio (lectura directa del archivo del sitio).
- No timbrar FFM BORRADOR de fixtures (fallan por UOM/`ObjetoImp`, ajeno a #215); para probar el
  happy-path usar `one_offs/verificar_215.demo_sandbox_call`.

---

## Decisiones vigentes
- Fuente de verdad del ambiente = `fm_environment` en `site_config.json` **del sitio** (no common).
- Guarda solo bloquea mutaciones (POST/PUT/PATCH/DELETE); GET permitido.
- F-02 (tests con registros reales, RG-003) y F-04 (MD022 en plantilla CONTINUITY) → diferidos a issues.

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/facturacion_fiscal/pac_environment.py`
- `docs/adr/0038-guarda-ambiente-fiscal-fm-environment.md`
- `frappe-infrastructure/checkpoints/coderabbit-pr226-review.md`

### No tocar
- `facturacion_mexico/one_offs/verificar_215.py` (diagnóstico; nunca se commitea).

---

## Riesgos / cuidados
- Deploy: fijar `fm_environment="production"` en el `site_config.json` de producción antes de activar
  la guarda, o el timbrado legítimo se bloquea.

---

## Información faltante
- Ninguna para cerrar el PR.
