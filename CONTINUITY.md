# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-08-22
**Rama activa:** `fix/207-venta-mostrador-address-display`
**Tarea actual:** Rama con DOS issues: #207 (ya commiteado `6639c89`) y #56 (validado; commit en curso). Falta push + PR.

---

## Recuperación rápida

Estoy trabajando en:
Cierre de #56 en la misma rama de #207. #56: el botón "Cerrar" del modal de éxito de timbrado era un
`primary_action` con `client_action: "frappe.hide_msgprint()"` (Frappe lo resuelve como ruta de
propiedades → no-op). Fix mínimo: eliminar solo ese `primary_action` roto; el cierre nativo (X/Escape)
ya funcionaba. NO se tocó el `try/except` de la FASE 3.

Plan que estoy siguiendo:
Issues #207 y #56 (ambos `it-tech:approved`) + instrucciones humanas explícitas de esta sesión.

Objetivo inmediato:
Cerrar `/ship commit` de #56 (commit SEPARADO encima de `6639c89`, sin squash). Luego esperar
autorización para `/ship push` y `/ship pr` (base `main`).

Criterio de avance:
Commit de #56 con sus 2 archivos + CONTINUITY.md → push OK → PR con bump SemVer (alcance combinado
#207+#56, recalculado vs `upstream/main`) → CI.

---

## Estado actual

### Ya cerrado
- #207: commit `6639c89` (display de dirección venta mostrador; baseline confirmado; test real).
- #56: causa raíz confirmada en código (`timbrado_api.py:548-552`, única ocurrencia). Fix mínimo
  aplicado (−5 líneas), sin alterar el `try/except` de FASE 3 (try:500 / except:591 / ERROR:611).
- #56: test estructural `test_timbrado_success_modal_close.py` (3 tests, verde) — modal de éxito se
  conserva y sin `primary_action`/`client_action`/`hide_msgprint`.
- #56: **validación funcional real en sandbox** (`facturacion-v16.dev`, `fm_environment=sandbox`).
  Evidencia (por IDs de documento, sin datos de cliente):
    · FFM `FFMX-2026-00055` → status TIMBRADO, UUID presente (prefijo c15788ae).
    · SI `ACC-SINV-2026-00070` → `fm_fiscal_status = TIMBRADO`, sin transición posterior a ERROR.
    · Modal "Timbrado Exitoso" mostrado; botón "Cerrar" roto AUSENTE; cierre nativo por X confirmado.
- Linters limpios (`ruff check` + `ruff format`).

### En progreso
- `/ship commit` de #56: gates OK, esperando confirmación del mensaje para commitear.

### Pendiente inmediato
1. Commit de #56 (2 archivos + CONTINUITY.md).
2. `/ship push` (con autorización).
3. `/ship pr` contra `main` con bump `__version__` del alcance combinado (recalcular vs `upstream/main`).

### No repetir
- `bench run-tests --app X --module Y --lightmode`: en v16 el combo `--app`+`--module` corre la suite
  completa. Para un módulo aislado: `--module` SIN `--app`.
- No decir "riesgo nulo" en campos/rutas fiscales sin comprobar payload/PAC/XML/CFDI.
- No incluir en commits `scripts/*` ni `working_docs/private/` (siempre `git add` explícito).
- No timbrar fuera de sandbox; confirmar `fm_environment=sandbox` antes (guard #215 bloquea `sk_live_`).

---

## Decisiones vigentes
- Suite global del test site arrastra 13 fallas preexistentes/ambientales (custom fields UAE,
  datos residuales) — NO bloquean estos commits (baseline confirmado quitando solo #207).
- Gate documental de #207 y #56 = **No aplica** (bug fixes de comportamiento existente, sin nuevo
  flujo/modelo/integración; tests puros). Commits sin docs autorizados por el usuario.
- La rama lleva #207 + #56 → el PR será mixto; el bump SemVer se calcula por el alcance combinado.

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/facturacion_fiscal/timbrado_api.py` — msgprint de éxito (~536-553) dentro del
  `try` de FASE 3 (500). El fix quitó el `primary_action`.

### Probablemente editar
- Ninguno pendiente (a la espera de push/PR).

### No tocar
- `try/except` de FASE 3 en `timbrado_api.py` (fuera del alcance de #56).
- `scripts/*`, `working_docs/private/` (untracked, fuera de alcance).

---

## Riesgos / cuidados
- Test site `test-facturacion.localhost` compartido (deuda de entorno, issue aparte si se decide).
- CFDI de prueba de #56 quedó timbrado en SANDBOX (dato de prueba, sin efecto real).
- Al crear el PR: un solo bump por PR, recalculado vs `upstream/main` (no doble incremento).

---

## Información faltante
- Ninguna que bloquee #207 o #56.
