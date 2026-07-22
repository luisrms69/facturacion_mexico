# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-07-21
**Rama activa:** `fix/ffm-nace-error-fiscal-event-fallback`
**Tarea actual:** Dos fixes en una sola rama: (1) FFM ya no nace en `ERROR` (commit `a08c65b`); (2) soporte de moneda extranjera en el CFDI (este segundo commit). Ambos validados en GUI/sandbox.

---

## Recuperación rápida

Estoy trabajando en:
Dos correcciones fiscales, cada una en su propio commit dentro de la **misma** rama:

1. **FFM nace en ERROR** (`a08c65b`, ya commiteado): los eventos de ciclo de vida de la FFM se
   escribían vía fallback como respuestas PAC fallidas (`success=0` → "Consulta Estado"/500), y
   `calculate_fiscal_status_from_logs` marcaba `ERROR` ante cualquier `success=0`. Se retiró el
   fallback (Capa 1) y se acotó la derivación de `ERROR` a un `Timbrado` fallido (Capa 2).

2. **Moneda extranjera en el CFDI** (este commit): el payload a FacturAPI **no** declaraba
   `currency` ni `exchange` → FacturAPI asumía MXN y una factura en USD quedaba bloqueada por
   "Moneda Inconsistente". Se agregó `resolve_cfdi_currency_exchange` (deriva moneda/tipo de cambio
   de la Sales Invoice: MXN → exchange 1; divisa → `conversion_rate`) y se cableó `currency`/
   `exchange` en `_prepare_facturapi_data`. Los importes ya iban en moneda de transacción
   (`net_rate`); no se tocaron precios ni impuestos.

Plan que estoy siguiendo:
Fix mínimo por feature, commits separados en la misma rama. Se hizo explícita y fail-closed la
suposición de **moneda base MXN** (emitir en divisa desde empresa con base ≠ MXN se bloquea:
`conversion_rate` solo equivale a "pesos por unidad" con base MXN, y la app no lo garantiza).

Objetivo inmediato:
Segundo commit (moneda) en la rama. Después: flujo normal paso a paso (push → PR → merge →
`/sync-check`) con autorización explícita en cada paso. Al cierre: revisión de tags/releases y crear
el release correspondiente.

Criterio de avance:
Tests verdes (`test_cfdi_moneda_extranjera` 10/10, `test_ffm_nace_error_fiscal_event` 5/5,
regresión `test_cancelacion_integridad` 37 / `test_e4_puente_si_pac` 17) + `ruff` + `mkdocs
--strict` limpios + validación GUI/sandbox (USD `FFMX-2026-00299`: `Moneda=USD`,
`TipoCambio=17.3943`, subtotal/IVA/total en USD, `livemode=false`).

---

## Estado actual

### Ya cerrado (en esta rama)

- **Commit `a08c65b`** — FFM nace en ERROR: retiro del fallback (`after_insert`, bloque
  `create_fiscal_event` de `on_update`, métodos `create_fiscal_event` / `_log_event_to_response_log`)
  + `calculate_fiscal_status_from_logs` deriva `ERROR` solo de `Timbrado` fallido. Test
  `test_ffm_nace_error_fiscal_event` (5). Docs: arquitectura + troubleshooting.
- **Commit moneda (este)** — `resolve_cfdi_currency_exchange` + cableo `currency`/`exchange` en el
  payload + guard fail-closed de base MXN. Test `test_cfdi_moneda_extranjera` (10: helper + payload
  real MXN/USD, guard base, verificación de no-uso de `base_net_rate`). Docs: arquitectura
  (Moneda del CFDI) + troubleshooting (factura en divisa).

### Siguiente paso concreto

1. (Hecho) `/ship commit` del fix de moneda. **Sin push ni PR** hasta autorización.
2. Flujo normal paso a paso: `/ship push` → `/ship pr` → (merge lo hace el usuario) → `/sync-check`.
3. **Al cierre:** revisión de tags/releases y crear el release correspondiente.

### Fuera de este trabajo (sin commitear)

- `one_offs/verificar_payload_moneda.py` — verificador de payload solo-lectura (queda fuera del commit).
- Issues abiertos aparte: #215 (guards de ambiente FacturAPI multi-capa), #216 (validación fiscal
  temprana ObjetoImp=02 sin impuestos en Sales Invoice).

---

## Decisiones vigentes no reflejadas en código

- **`fm_sync_status` / `fm_sync_error`:** capa distinta con su propia derivación; no se tocan.
- **Moneda base MXN:** la app no la garantiza (solo la recomienda en `install.py`). Emitir CFDI en
  divisa exige base MXN; en caso contrario se bloquea. La FFM no guarda copia de moneda/tipo de
  cambio: siempre se derivan de la Sales Invoice.
- **Config FacturAPI de `llantascs-v16.dev`:** saneada a sandbox (`sandbox_mode=1`, `sk_live` borrada;
  el usuario cargó la `sk_test`). Prevención universal en issue #215.
