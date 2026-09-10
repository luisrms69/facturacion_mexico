# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-09-08
**Rama activa:** `chore/235-remove-auto-create-regla`
**Tarea actual:** #235 Parte A — eliminar código muerto `_auto_create_regla` (v1.4.8). Commit hecho; falta push + PR.

---

## Recuperación rápida

Estoy trabajando en:
Cleanup acotado del motor de resolución CFDI Recibidos, **solo Parte A** del issue #235: eliminar la
función `_auto_create_regla` (sin llamador desde v1.4.7) y su comentario obsoleto en `api.py`, y
corregir la referencia en `docs/tecnico/arquitectura.md`.

Plan que estoy siguiendo:
Decisión del propietario en #235 (alcance reducido a Parte A). Partes B y C **conservadas fuera de
alcance** por seguir funcionales; no se abren issues nuevos por ellas en este ciclo.

Objetivo inmediato:
`/ship push` (rama) y luego `/ship pr` hacia `main`, con autorización explícita por paso.

Criterio de avance:
PR mergeado con bump 1.4.8; tras merge `/sync-check` + `/ship release` v1.4.8; luego cerrar #235
como `completed`.

---

## Estado actual

### Ya cerrado
- Eliminada `_auto_create_regla` + comentario obsoleto (`api.py`); referencia corregida en
  `arquitectura.md`. Bump 1.4.7 → 1.4.8 (PATCH).
- #235 reformulado a Parte A; label `it-tech:approved`.
- Tests focalizados verdes: api 8/8, item_resolution_history 22, item_resolution_engine 24
  (0 llamadores → sin cambio de comportamiento).
- Commit creado en la rama.

### En progreso
- Cierre del ciclo `/ship`: falta push + PR.

### Pendiente inmediato
1. `/ship push` de la rama (con autorización explícita).
2. `/ship pr` hacia `main` (con autorización explícita).
3. Tras merge: `/sync-check` + `/ship release` v1.4.8 → cerrar #235 como `completed`.

### No repetir
- No tocar Partes B (`CFDI Concepto Mapping` + `item_resolver` + APIs) ni C (reglas `Auto:` nivel 4):
  conservadas a propósito, siguen funcionales.
- No modificar el ADR 0040 (registro histórico inmutable).
- No commitear `scripts/*` ni `working_docs/private/`.

---

## Decisiones vigentes
- `_auto_create_regla` eliminado; la memoria del resolver es el historial de conceptos (ADR 0040).
- B y C se conservan: superficie activa / participan en sugerencias del resolver.
- Bump 1.4.8 = PATCH (cleanup de código muerto, sin cambio de comportamiento).

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/cfdi_recibidos/api.py` (donde estaba `_auto_create_regla`)
- `docs/tecnico/arquitectura.md` (referencia corregida)

### No tocar
- `CFDI Concepto Mapping`, `item_resolver`, reglas `Auto:` (fuera de alcance conservado)
- `docs/adr/0040-*.md` (inmutable)

---

## Riesgos / cuidados
- `bench run-tests --app` = 345 tests (dato oficial); flake de concurrencia preexistente
  `test_sis_distintas_no_se_bloquean` puede aparecer en suite completa (ajeno a este cambio).

---

## Información faltante
- Ninguna para continuar. Solo faltan las autorizaciones de push/PR.
