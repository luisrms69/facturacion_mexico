# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-08-14
**Rama activa:** `feat/issue-215-fm-environment-guard`
**Tarea actual:** Issue #215 — guarda de ambiente fiscal por sitio (`fm_environment`) para el PAC.

---

## Recuperación rápida

Estoy trabajando en:
La implementación del issue #215: evitar que un entorno no productivo (p. ej. restaurado desde
producción) emita CFDIs reales contra FacturAPI.

Plan que estoy siguiendo:
Issue #215 + ADR-0038 (`docs/adr/0038-guarda-ambiente-fiscal-fm-environment.md`).

Objetivo inmediato:
Commit hecho en la rama. Siguiente paso concreto: `/ship push` (con autorización) y luego `/ship pr`.

Criterio de avance:
Gates verdes (datos-cliente, documental, ruff, mkdocs --strict) y tests de la guarda 9/9 OK.

---

## Estado actual

### Ya cerrado
- Guarda central en `FacturAPIClient` (`_make_request` / `_make_request_silent`) + módulo
  `pac_environment.py`. Credencial seleccionada por `fm_environment` (site_config.json).
- `sandbox_mode` pasa a valor derivado (compat). Sin fallback entre credenciales.
- Docs: `docs/tecnico/ambiente-fiscal.md` + ADR-0038 + nav MkDocs.
- Tests: `test_pac_environment_guard` (9/9) + `test_facturacion_mexico_company_settings` (actualizado, 9/9).
- Validación local: sandbox real (`sk_test_`) POST permitido con `livemode=false`; bloqueo con
  `fm_environment` ausente y con `sk_live_` en sandbox. Sin datos de cliente alterados.
- Bump `__version__` 1.3.2 → 1.4.0 (MINOR).

### En progreso
- Nada; commit de la rama listo.

### Pendiente inmediato
1. `/ship push` (autorización aparte).
2. `/ship pr` contra `main` (base upstream/main 1.3.2 → objetivo 1.4.0).
3. Configurar `fm_environment` en `site_config.json` de producción/staging antes del deploy.

### No repetir
- No intentar el timbrado sandbox sobre FFM BORRADOR de fixtures: fallan por validaciones locales
  (UOM fuera de `c_ClaveUnidad`, `ObjetoImp=02` sin impuestos) ajenas a #215. Para probar el
  happy-path usar `one_offs/verificar_215.demo_sandbox_call` (POST directo a sandbox).

---

## Decisiones vigentes
- Fuente de verdad del ambiente = `fm_environment` en `site_config.json` (a prueba de restore).
- Guarda solo bloquea mutaciones (POST/PUT/PATCH/DELETE); GET permitido.
- `fm_environment` debe fijarse en TODOS los sitios que timbran (prod=`production`, dev=`sandbox`),
  antes de activar la guarda (orden de despliegue crítico).

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/facturacion_fiscal/pac_environment.py`
- `facturacion_mexico/facturacion_fiscal/api_client.py`
- `docs/adr/0038-guarda-ambiente-fiscal-fm-environment.md`

### Probablemente editar
- (ninguno pendiente)

### No tocar
- `facturacion_mexico/one_offs/verificar_215.py` (diagnóstico; nunca se commitea).

---

## Riesgos / cuidados
- Deploy: si se activa la guarda sin `fm_environment="production"` en producción, se bloquea el
  timbrado legítimo. Fijar la variable primero.

---

## Información faltante
- Ninguna para cerrar el PR.
