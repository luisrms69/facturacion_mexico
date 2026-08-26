# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-08-23
**Rama activa:** `chore/57-limpieza-alias-uuid-ffm-summary`
**Tarea actual:** Campaña B (ejecución de aprobados). #57 implementado; commit en curso. Falta bump + push + PR.

---

## Recuperación rápida

Estoy trabajando en:
Issue #57 (aprobado, quick win). Alcance reformulado y mínimo: en `api/ffm_summary.py`, `ALIASES["uuid"]`
tenía alias muertos (`uuid`, `uuid_fiscal`) que nunca fueron campos de la FFM → `doc.get(...)` siempre
`None`. Se reduce a `["fm_uuid"]`. Comportamiento idéntico (verificado: 0 Custom Fields `uuid`/`uuid_fiscal`
en ambos sites; `fm_uuid` es nativo del DocType).

Plan que estoy siguiendo:
Estrategia por campañas. Campaña A (depuración) cerrada: awaiting-decision 25→20; cerrados #123/#111/#133.
Campaña B (aprobados, PR independiente c/u): **#57 → #163 → #78**, en ese orden.

Objetivo inmediato:
Commit de #57 → luego bump PATCH (1.4.2→1.4.3) → `/ship push` → `/ship pr` → merge → release → close #57.

Criterio de avance:
CI verde → merge → tag/Release v1.4.3 → #57 cerrado. Después #163, luego #78.

---

## Estado actual

### Ya cerrado
- Release v1.4.2 completo (PR #228: #207 + #56), tag+Release alineados; #207/#56 cerrados.
- Campaña A: #123, #111, #133 cerrados sin código (dup/obsoletos/absorbido).
- Labels: `approved` = #57(en curso), #78, #163; `changes-requested` = #176; #205 ampliado (absorbe defecto de #133).
- #57: cambio de 1 línea en `api/ffm_summary.py` + test de regresión `test_uuid_desde_fm_uuid`. Linters + 4/4 tests OK.

### En progreso
- `/ship commit` de #57 (3 archivos: ffm_summary.py + test + CONTINUITY.md).

### Pendiente inmediato
1. Bump `__version__` 1.4.2 → 1.4.3 (PATCH) antes del PR.
2. `/ship push` + `/ship pr` (base `main`) + merge + `/ship release` v1.4.3 + close #57.
3. Siguientes de Campaña B: **#163** (string-matching IVA vivo `factura_fiscal_mexico.py:1567-1574`), luego **#78** (dedup notificación JS).

### No repetir
- No tocar `ffm_substitution_source_uuid` (activo en sustituciones TipoRelación 04).
- No tocar columnas huérfanas por site (`fm_uuid_fiscal` aún existe en BD) ni `install.py` debug → fuera de alcance de #57.
- `bench run-tests --app X --module Y`: en v16 corre suite completa; usar `--module` SIN `--app`.
- No incluir `scripts/*` ni `working_docs/private/` en commits.

---

## Decisiones vigentes
- Campaña C (calidad/tests) pendiente: analizar juntos **#223 + #158 + deuda del baseline de tests** (13 fallas locales: allowlist UAE en `LEGACY_CF_ALLOWLIST` + aislamiento de `test_ffm_reconciliation` + setUpClass compartido). CI en entorno limpio SÍ pasa (verificado en PR #228).
- Gate documental de #57 = No aplica (limpieza de código muerto, sin cambio de comportamiento). Autorizado sin docs.
- Clúster de cancelación (#224→#205→#101, satélites #110/#201) se ataca como campaña aparte, no piecemeal.

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/api/ffm_summary.py` — `ALIASES["uuid"]` y `get_ffm_summary`.

### No tocar
- `ffm_substitution_source_uuid` (cualquier archivo), `scripts/*`, `working_docs/private/`.

---

## Riesgos / cuidados
- Al crear el PR de #57: bump SemVer una sola vez, recalculado vs `upstream/main` (1.4.2 → 1.4.3, PATCH).
- Test site compartido con 13 fallas baseline (deuda de Campaña C); usar `--module` aislado para validar.

---

## Información faltante
- Ninguna que bloquee #57.
