# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-08-14
**Rama activa:** `feat/issue-215-fm-environment-guard`
**Tarea actual:** PR #226 — guarda de ambiente #215 + indicador visual #171 (ambos por-sitio, v1.4.0).

---

## Recuperación rápida

Estoy trabajando en:
PR #226. #215 (guarda PAC por `fm_environment`) ya validado y con CI verde. #171 (indicador de
ambiente en el Desk) implementado y validado visualmente; recién commiteado, falta push.

Plan que estoy siguiendo:
Issues #215 y #171 + ADR-0038 + reporte CodeRabbit `frappe-infrastructure/checkpoints/coderabbit-pr226-review.md`.

Objetivo inmediato:
`/ship push` (actualiza PR #226 y re-dispara CI) — con autorización. Luego esperar CI verde y merge.

Criterio de avance:
CI completamente verde (incluye Frappe Linter/Semgrep) tras el push.

---

## Estado actual

### Ya cerrado (en la rama)
- #215: guarda central en `FacturAPIClient` + credencial por `fm_environment` (site-only vía
  `frappe.get_file_json`). Tests 10/10. CI verde en `3f69124`.
- #171: indicador de ambiente en el Desk, por-sitio, reutilizando `get_fm_environment()`:
  - `boot.py` publica `frappe.boot.fm_environment`;
  - `public/js/fm_environment_indicator.js` añade clase `fm-env-sandbox`/`fm-env-unset` al `<body>`;
  - `public/css/fm_environment.bundle.css` (bundle con hash) → `border-bottom` 4px en `.page-head`
    (ámbar sandbox / rojo ausente-inválido); production sin cambios.
  - Validado visualmente en dev; rendimiento nulo (boot ~11-14 µs, sin BD; assets ~1.3 KB cacheados).
  - Comentario de alcance publicado en el issue #171 (reajuste per-Company → per-sitio).
- Versión `__version__` = 1.4.0 (un bump por PR; cubre #215+#171).

### Pendiente inmediato
1. `/ship push` (sube el commit de #171; CI debe quedar verde).
2. Merge (usuario) → `/sync-check` + `/ship release` v1.4.0.
3. Cierre formal del issue #171 (`/ship issue close 171`) post-merge.

### No repetir
- No usar `open()` en código de la app (Semgrep `frappe-security-file-traversal`).
- No usar includes crudos para CSS que cambie: usar bundle (`*.bundle.css`) → hash y cache-busting.
- No usar `frappe.conf`/`get_site_config()` para el ambiente (combinan common+site).
- Indicador SOLO en `.page-head` (franja); nada dentro de SI/FFM.

---

## Decisiones vigentes
- Fuente única del ambiente = `fm_environment` en el `site_config.json` DEL SITIO.
- Indicador por-sitio (no por Company, no `sandbox_mode`).
- CSS del Desk como bundle para cache-busting automático.
- F-02 (tests con registros reales) y F-04 (MD022) → diferidos a issues. JS crudo de #171: no se
  bundle-a ahora (no afecta rendimiento; se haría si alguna vez cambia).

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/boot.py`, `facturacion_mexico/public/js/fm_environment_indicator.js`,
  `facturacion_mexico/public/css/fm_environment.bundle.css`
- `facturacion_mexico/facturacion_fiscal/pac_environment.py`
- `docs/tecnico/ambiente-fiscal.md`

### No tocar
- `facturacion_mexico/one_offs/verificar_215.py` (diagnóstico; nunca se commitea).

---

## Riesgos / cuidados
- Validar Semgrep (regla `open(...)`) además de ruff antes de cada push que toque `.py`.

---

## Información faltante
- Ninguna para cerrar el PR.
