# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-08-15
**Rama activa:** `fix/171-marca-staging-css`
**Tarea actual:** Rediseño de #171 — marca visual de STAGING por bench (v1.4.1). Commit recién creado; falta push + PR.

---

## Recuperación rápida

Estoy trabajando en:
Rediseño de #171. La implementación original (boot_session + frappe.boot + JS + app_include hooks,
1.4.0) se descartó por depender de dos cachés de Frappe (`app_hooks` y `bootinfo`) que quedaban
*stale* de forma persistente y podían mostrar el ambiente equivocado. Reemplazada por una marca
estática de STAGING a nivel de bench, cargada por `common_site_config.json → app_include_css`.

Plan que estoy siguiendo:
Instrucciones del usuario en esta sesión (eliminación manual de #171 anterior + nueva arquitectura) +
ADR-0039. #215 queda intacto y separado.

Objetivo inmediato:
Esperar autorización para `/ship push`, luego `/ship pr` (base `main`).

Criterio de avance:
Push OK → PR abierto con gate de versión 1.4.1 → CI verde.

---

## Estado actual

### Ya cerrado
- Eliminación manual de #171 anterior (sin git revert/restore): borrados `boot.py`,
  `fm_environment_indicator.js`, `fm_environment.bundle.css`, `test_boot_fm_environment.py`;
  retirados `app_include_css/js` y `boot_session` de `hooks.py` (comentarios scaffold restaurados).
- Auditoría anti-residuos contra `555fe07`: sin residuos funcionales.
- Nueva marca: `public/css/fm_staging_marker.css` (franja cian `#06b6d4` en `.page-head`).
- Activación por `common_site_config.json → app_include_css` (verificado local, aparece sin refresh).
- Docs: `ambiente-fiscal.md` reescrita, `getting-started.md` (usuario), ADR-0039 + índice + mkdocs.
- Bump `__version__` 1.4.0 → 1.4.1 (PATCH).
- Commit creado en la rama (ver `git log`).

### En progreso
- Ciclo `/ship`: commit hecho, falta `push` y `pr`.

### Pendiente inmediato
1. `/ship push` (con autorización).
2. `/ship pr` contra `main` (título/cuerpo con versión 1.4.1, PATCH).
3. Tras merge: `/sync-check` + `/ship release` (tag/Release v1.4.1).

### No repetir
- No usar `boot_session`/`frappe.boot`/JS para el ambiente: quedan *stale* en `bootinfo` (hash Redis
  por usuario, sin TTL) y `app_hooks`; refresh/hard-refresh no lo corrigen.
- No alojar el CSS fuera de `facturacion_mexico` ni inventar app nueva.
- No añadir `clear-cache` al deploy como "solución" de la marca: la arquitectura nueva no lo necesita.
- Selector: usar `.page-head` (probado). `header.navbar` NO existe en el DOM del Desk v16
  (`toolbar.js` reemplaza `<header>` por `<div class="sticky-top">`).

---

## Decisiones vigentes
- **#171 ya no representa `fm_environment`.** Es una marca de bench: staging lleva la clave en
  `common_site_config.json`, producción no. Independiente de que un sitio tenga la app instalada
  (se sirve por symlink de bench en `/assets/facturacion_mexico/css/`).
- **#215 intacto** y es la única protección fiscal real (server-side, por sitio).
- El bench local (`facturacion-v16.dev`) tiene la clave `app_include_css` puesta a propósito
  (es dev/staging) — se deja como señal permanente; no se commitea (es config del bench).

---

## Archivos relevantes ahora

### Leer primero
- `docs/adr/0039-marca-visual-staging-bench.md` — decisión y contexto.
- `docs/tecnico/ambiente-fiscal.md` — sección "Marca visual de STAGING".

### Probablemente editar
- Ninguno pendiente (a la espera de push/PR).

### No tocar
- `facturacion_mexico/facturacion_fiscal/pac_environment.py`, `api_client.py`, tests de #215.

---

## Riesgos / cuidados
- Al retirar los hooks en un bench que ya recibió 1.4.0 (p. ej. staging con la franja ámbar vieja),
  el cambio de set de `app_hooks` puede exigir **una** invalidación de caché en ese deploy puntual
  (costo general de Frappe al cambiar `hooks.py`, no de la arquitectura nueva).
- `app_include_css` en `common_site_config.json` debe ser **lista** (un string rompería `desk.py`).
- Despliegue en cliente lo hace el usuario manualmente (no hay Ansible/MSP).

---

## Información faltante
- Confirmar qué apps neutrales están en el `apps.txt` del bench de staging real (no bloquea: el CSS
  vive en `facturacion_mexico`, presente en ese bench).
