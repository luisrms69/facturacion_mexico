# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-09-07
**Rama activa:** `feat/cfdi-item-history-resolution`
**Tarea actual:** Feature "aprendizaje por historial" en resolución de Items CFDI Recibido (v1.4.7). PR #234 abierto; pendiente merge (usuario) + release v1.4.7.

---

## Recuperación rápida

Estoy trabajando en:
Nueva fuente de resolución `_resolve_by_history` en `item_resolution_engine.py`: reutiliza las
clasificaciones humanas previas por `(company, supplier_rfc, sat_product_key)` para proponer —y,
con evidencia fuerte, autoasignar— el `item_code` de un concepto. Diseño colaborativo (auditoría
UX), no proviene de un issue abierto.

Plan que estoy siguiendo:
Diseño acordado en conversación + [ADR 0040](docs/adr/0040-aprendizaje-historial-clasificacion-cfdi-recibido.md).
V1 cerrada en alcance; cleanup de legacy (`_auto_create_regla`, `CFDI Concepto Mapping`,
`item_resolver`, reglas `Auto:`) queda para un issue separado (fuera de alcance).

Objetivo inmediato:
Usuario hace Squash & Merge de PR #234 en GitHub. Después: `/sync-check` + `/ship release` v1.4.7.

Criterio de avance:
PR #234 mergeado en `main` y release v1.4.7 (tag + GitHub Release) alineados.

---

## Estado actual

### Ya cerrado
- Implementación V1 completa: `_resolve_by_history`, reorden de precedencia, split `_resolve_by_rules`
  (manual vs `Auto:`), gate (≥2 previos, ≥80%), anti-refuerzo, scope company, conversión
  confirmación→`Manual`, retiro del caller `_auto_create_regla`, opción `Historial` en el DocType.
- Ajuste: `auto_assignable=False` cuando el historial queda como alternativa.
- Docs: ADR 0040, `docs/usuario/cfdi-recibidos.md` (Paso 3), `docs/tecnico/arquitectura.md`, índice
  ADR y `mkdocs.yml` nav.
- Tests: 22 nuevos (unit + IntegrationTestCase). Módulo historial 22/22, motor 24/24.
- `bench migrate` aplicado en `test-facturacion.localhost` y `facturacion-v16.dev` (opción `Historial`).
- Commit creado en la rama (bump 1.4.6 → 1.4.7).

### En progreso
- PR #234 abierto contra `main`. Esperando Squash & Merge del usuario (Claude no mergea).

### Pendiente inmediato
1. Usuario: Squash & Merge de PR #234 en GitHub.
2. Tras merge: `/sync-check` (detecta drift de release) + `/ship release` v1.4.7.
3. (opcional) crear el issue de cleanup legacy que quedó fuera de alcance.

### No repetir
- No volver a decir "suite de 1700 tests": la suite real de `bench run-tests --app` es **345**.
- No re-verificar el flake `test_sis_distintas_no_se_bloquean`: ya se confirmó preexistente en
  `main@72893a8` (reproducido 1/3 con worktree). Es deuda separada; no estabilizar dentro de esta V1.
- No crear un issue retroactivo solo para vincular este commit.
- No commitear `scripts/*` ni `working_docs/private/` (temporales/privados).

---

## Decisiones vigentes
- La memoria del sistema es el **historial de conceptos clasificados**, no reglas `Auto:`
  materializadas. `_auto_create_regla` se conserva sin llamador (legacy).
- Confirmar una sugerencia de historial se guarda como `Manual` (no `Historial`) para alimentar el
  aprendizaje sin auto-refuerzo. La query excluye `item_resolution='Historial'` y `no_procesar=1`.
- Gate calibrado con auditoría real: precisión ≈0.94, cobertura auto ≈0.56.
- Bump 1.4.7 = PATCH (mantener cadencia 1.4.x para features acotadas de CFDI Recibidos).

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/cfdi_recibidos/services/item_resolution_engine.py` (`_resolve_by_history`, orden)
- `facturacion_mexico/cfdi_recibidos/api.py` (`classify_all_concepts`, `assign_item_to_concepto`)
- `docs/adr/0040-aprendizaje-historial-clasificacion-cfdi-recibido.md`

### Probablemente editar
- (ninguno pendiente en V1 — próximos pasos son git: push/PR)

### No tocar
- `_auto_create_regla`, `CFDI Concepto Mapping`, `item_resolver` (cleanup = issue separado)

---

## Riesgos / cuidados
- Flake de concurrencia preexistente (`test_sis_distintas_no_se_bloquean`) puede aparecer en corridas
  de suite completa; no es de esta feature.
- `bench run-tests --app` = 345 tests (dato oficial).

---

## Información faltante
- Ninguna para continuar. Solo faltan las autorizaciones de push/PR.
