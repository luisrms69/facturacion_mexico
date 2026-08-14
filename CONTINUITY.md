# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-08-14
**Rama activa:** `feat/issue-215-fm-environment-guard`
**Tarea actual:** Issue #215 — guarda de ambiente fiscal por sitio; PR #226; corrigiendo CI (Semgrep) + lógica F-01.

---

## Recuperación rápida

Estoy trabajando en:
PR #226 (issue #215). El commit `b30c1ea` (fix F-01 con `open()`) rompió el CI (regla Semgrep
`frappe-security-file-traversal`, `pattern: open(...)`). Reimplementado sin `open()`.

Plan que estoy siguiendo:
Issue #215 + ADR-0038 + reporte CodeRabbit `frappe-infrastructure/checkpoints/coderabbit-pr226-review.md`.

Objetivo inmediato:
Commit de la corrección hecho. Siguiente paso: `/ship push` (re-dispara CI del PR #226) — con autorización.

Criterio de avance:
CI verde (incluido "Frappe Linter"/Semgrep) y tests focalizados 10/10.

---

## Estado actual

### Ya cerrado
- Guarda central `pac_environment.py` + selección de credencial por `fm_environment`.
- **F-01 (definitivo):** `get_fm_environment()` comprueba PRESENCIA de la clave en el `site_config.json`
  DEL SITIO vía `frappe.get_file_json(frappe.get_site_path("site_config.json"))` — sin `open()` en la
  app (Semgrep-safe) y sin depender de la config mergeada. Corrige el fallo lógico del enfoque por
  comparación (mismo valor en common y site ya no bloquea). Fail-closed ante error de lectura.
- Test `test_environment_read_from_site_config_presence` cubre: (a) rechazo common-only, (b) site
  define, (c) mismo valor en ambos → acepta, (d) fail-closed.
- **F-03:** JSON de ejemplo válido en la guía técnica.
- Docs: ADR-0038 + tecnico actualizados al mecanismo por presencia. Bump `__version__` = 1.4.0.
- PR #226 abierto contra `main` (no mergeado).

### Pendiente inmediato
1. `/ship push` (actualiza PR #226, re-dispara CI) — autorización aparte.
2. Merge (usuario) → `/sync-check` + `/ship release` (tag + Release v1.4.0).
3. Tarea aparte pendiente: script `set-fm-environment.sh` (infra) para fijar `fm_environment` por sitio.

### No repetir
- No usar `open()` en código de la app (regla Semgrep `frappe-security-file-traversal`). Para leer el
  site_config del sitio usar `frappe.get_file_json` + `frappe.get_site_path`.
- No usar `frappe.conf` / `frappe.get_site_config()` para el ambiente: combinan common + site.
- CI corre Semgrep además de ruff → validar ambos antes de push.

---

## Decisiones vigentes
- Fuente de verdad del ambiente = presencia de `fm_environment` en el `site_config.json` DEL SITIO.
- Guarda solo bloquea mutaciones (POST/PUT/PATCH/DELETE); GET permitido.
- F-02 (tests con registros reales) y F-04 (MD022 en plantilla CONTINUITY) → diferidos a issues.

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/facturacion_fiscal/pac_environment.py`
- `docs/adr/0038-guarda-ambiente-fiscal-fm-environment.md`

### No tocar
- `facturacion_mexico/one_offs/verificar_215.py` (diagnóstico; nunca se commitea).

---

## Riesgos / cuidados
- Validar Semgrep localmente (regla `open(...)`) además de ruff antes de cada push que toque `.py`.

---

## Información faltante
- Ninguna para cerrar el PR.
