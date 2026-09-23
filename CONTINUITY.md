# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-09-23
**Rama activa:** `feat/cfdi-externo-v3`
**Tarea actual:** V3 — soporte genérico para CFDI timbrado externamente (fuera del ERP/PAC) en Factura Fiscal Mexico. Implementación + tests + docs completos; commit en curso.

---

## Recuperación rápida

Estoy trabajando en:
Representar en ERPNext un CFDI **ya timbrado en otro sistema/PAC** como `Factura Fiscal Mexico`
autoritativa, sin llamar al PAC ni fabricar `FacturAPI Response Log`. Es la base fiscal genérica de la
carga histórica de ventas de un cliente; el **importador** (mapeos, XML) vivirá en la app `acti_customs`,
que consumirá la primitiva `registrar_cfdi_externo()` — NO en `facturacion_mexico`.

Plan que estoy siguiendo:
Diseño V3 cerrado con el propietario (ver ADR 0041). Cero campos nuevos: solo se agrega el valor
`"CFDI externo"` a `fm_creation_source`. `FFM.status` sigue siendo canónico; para externos,
`calculate_fiscal_status_from_logs` NO recalcula desde logs (early-return) y el estado se puebla desde
evidencia (UUID + fecha_timbrado + XML). Guards UI+servidor bloquean acciones FacturAPI; el motor de
reconciliación es seguro por `facturapi_id` vacío. Flujo FacturAPI normal intacto y backward-compatible.

Objetivo inmediato:
`/ship commit` (este) → `/ship push` → `/ship pr` hacia `main`, con autorización explícita por paso.
Tras merge: `/sync-check` + `/ship release` v1.5.0.

Criterio de avance:
PR mergeado con bump 1.5.0; luego, en `acti_customs`, construir el DocType de staging `Acti CFDI Historico`
y el dry-run del primer mes (Vigentes) contra un site no productivo.

---

## Estado actual

Implementado en la rama (código/tests + docs + bump):

- `factura_fiscal_mexico.py` — constante `CFDI_EXTERNO`; guard en `calculate_fiscal_status_from_logs`;
  rama externa en `validate_status_transitions`; `_validate_cfdi_externo`; **`registrar_cfdi_externo()`**
  (dominio interna, no whitelisted; idempotente por SI+UUID; fail-closed) + `_es_uuid_valido`.
- `factura_fiscal_mexico.json` — `+1` opción `CFDI externo` en `fm_creation_source`.
- `factura_fiscal_mexico.js` — gate de botones FacturAPI para externos (servidor y fallback).
- `timbrado_api.py` — guards `_guard_no_externo_*` en `timbrar_factura`, `cancelar_factura`,
  `descargar_archivos_cfdi`, `create_substitution_si`, `revisar_estatus_cancelacion`.
- `tests/test_cfdi_externo.py` — 9 tests (verdes en test-facturacion.localhost).
- Docs: ADR 0041 + `docs/tecnico/arquitectura.md` (sección "CFDI externo") + índice ADR + nav mkdocs.
- `__init__.py` — bump `1.4.10 → 1.5.0` (MINOR).

Verificación de protección servidor (contra código final): timbrar/cancelar/descargar/sustituir/
verificar-estado → **bloqueados por guard explícito**; motor `reconcile_ffm` (scheduler y directo) →
**seguro por `facturapi_id` vacío** (skip antes del GET al PAC).

Sin regresión: `get_or_create_active_ffm` (24), `ffm_reconciliation` (51),
`estado_fiscal_independiente_log` (7), `unico_ffm_activo` (16). `mkdocs build --strict` → EXIT=0.

### Pendiente inmediato
1. `/ship commit` (este).
2. `/ship push` de la rama (autorización explícita).
3. `/ship pr` hacia `main` (autorización explícita).
4. Tras merge: `/sync-check` + `/ship release` v1.5.0.

---

## Decisiones vigentes no evidentes en el código

- No se usaron los atajos V1 (`db_set`/SQL) ni V2 (Response Log sintético); se eligió V3 (modelo explícito).
  Ver ADR 0041 (alternativas descartadas).
- Un `CANCELADO` externo **no** cancela la Sales Invoice ni genera reversión contable; el tratamiento
  contable de históricos cancelados se decide por separado (los ~45 cancelados: falta fecha de cancelación
  para clasificar mismo-mes vs mes-posterior — pendiente de fuente: acuses SAT o sistema anterior).
- El importador histórico fija `rate` = valor del XML; nunca re-precia desde catálogo.

---

## No commitear
- `facturacion_mexico/one_offs/analisis_hist_actiglobal.py` (one_off de análisis, excluido).
- `scripts/*`, `working_docs/private/`.
