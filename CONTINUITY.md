# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-08-23
**Rama activa:** `fix/campaign-b-57-163-78`
**Tarea actual:** Campaña B (paquete #57 + #163 + #78) cerrado y versionado 1.4.3. Falta push + PR.

---

## Recuperación rápida

Estoy trabajando en:
Campaña B — tres bug fixes independientes entregados en UN solo branch/PR con commits separados,
un solo bump. Todos aprobados (it-tech:approved).

- **#57** (`54e3aa1`): en `api/ffm_summary.py`, `ALIASES["uuid"]` tenía alias muertos (`uuid`,
  `uuid_fiscal`, nunca campos de la FFM) → reducido a `["fm_uuid"]`. Sin cambio de comportamiento
  (verificado: 0 Custom Fields `uuid`/`uuid_fiscal`; `fm_uuid` es nativo del DocType).
- **#163** (`c00169b`): en `get_or_create_active_ffm`, la clasificación IVA/otros usaba `"IVA" in
  head` y neteaba la retención IVA (negativa) contra `si_iva`. Se extrae helper puro
  `_clasificar_iva_otros(taxes, is_return)` con normalización de signo por `is_return`. Campos
  informativos `si_iva`/`si_otros_impuestos` (NO en CFDI); no usa el mapeo fiscal (#186).
- **#78** (`f583168`): dedup de avisos del selector Método de Pago SAT. (1) guard determinista
  `_should_notify_payment_method` para el duplicado PPD (dos funciones hermanas); (2) eliminado el
  `frm.trigger("fm_payment_method_sat")` redundante del radio handler para el duplicado PUE
  "No se encontró Payment Entry" (mismo evento disparado 2×). Sin tocar PPD⇒99 ni fiscal/PAC.

Plan que estoy siguiendo:
Estrategia por campañas. Campaña A (depuración) cerrada (awaiting-decision 25→20; cerrados
#123/#111/#133). Campaña B = este paquete. Campaña C (pendiente): calidad/tests (#223 + #158 +
deuda del baseline de tests).

Objetivo inmediato:
`/ship push` → `/ship pr` (base `main`, cierra #57 #163 #78) → merge → `/ship release` v1.4.3 →
cerrar #57 #163 #78.

Criterio de avance:
CI verde (en entorno limpio la suite pasa; local arrastra 13 fallas baseline preexistentes) → merge
→ tag/Release v1.4.3.

---

## Estado actual

### Ya cerrado
- Release v1.4.2 (PR #228: #207 + #56); #207/#56 cerrados.
- Campaña A: #123, #111, #133 cerrados sin código.
- Campaña B (esta rama): #57, #163, #78 implementados, con tests, commits separados.
- Bump `1.4.2 → 1.4.3` (PATCH, vs `upstream/main`).
- Gates conjuntos: linters ✅ (ruff + prettier@2.7.1); mkdocs --strict ✅; doc-review No aplica.
- Suite: `failures=2, errors=11` = **13 fallas baseline preexistentes idénticas** a PR #228,
  **0 regresiones nuevas**; +9 tests nuevos verdes; `test_calculo_iva_combinado` corregido.

### En progreso
- Cierre del paquete: commit de versionado (bump + este CONTINUITY). Luego push/PR.

### Pendiente inmediato
1. Commit final de cierre/versionado (`__init__.py` 1.4.3 + CONTINUITY.md), `Refs #57 #163 #78`.
2. `/ship push` + preview `/ship pr` (base `main`).
3. Tras merge: `/sync-check` + `/ship release` v1.4.3 + cerrar #57 #163 #78.

### No repetir
- `bench run-tests --app X --module Y`: en v16 corre la suite completa; usar `--module` SIN `--app`.
- No incluir `scripts/*` ni `working_docs/private/` en commits (siempre `git add` explícito).
- No tocar `ffm_substitution_source_uuid`, PPD⇒99, mapeo fiscal (#186) ni PAC.
- No reutilizar el guard de #78 para el aviso "no PE" (mensaje distinto; se resolvió quitando el trigger).

---

## Decisiones vigentes
- Las 13 fallas del test site (custom fields UAE en `LEGACY_CF_ALLOWLIST`, datos residuales de
  reconciliación, setUpClass compartido) son **baseline preexistente**, NO bloquean; en CI limpio pasa.
- Gate documental de #57/#163/#78 = No aplica (bug fixes sin flujo/campo/estado nuevo).
- Campaña C tratará #223 + #158 + la deuda del baseline de tests juntos.

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/api/ffm_summary.py` (#57), `.../factura_fiscal_mexico.py` `_clasificar_iva_otros`
  y `get_or_create_active_ffm` (#163), `.../factura_fiscal_mexico.js` selector método de pago (#78).

### No tocar
- `scripts/*`, `working_docs/private/` (untracked, fuera de alcance).

---

## Riesgos / cuidados
- Al crear el PR: un solo bump por PR (ya en 1.4.3), recalculado vs `upstream/main`.
- Test site compartido con deuda baseline (Campaña C).

---

## Información faltante
- Ninguna que bloquee el cierre del paquete.
