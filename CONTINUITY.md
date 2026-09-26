# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-09-25
**Rama activa:** `feat/ventas-extranjeras-fiscal-receptor`
**Tarea actual:** Bloque fiscal 1 de ventas extranjeras — representación correcta del **receptor extranjero** (identidad), sin tocar IVA/ObjetoImp/Leyendas. Implementación + tests + validación funcional; en `/ship pr`.

---

## Recuperación rápida

Estoy trabajando en:
El primer sub-bloque fiscal de ventas a receptores extranjeros, correcto **independientemente** de si
una operación futura califica a tasa 0%. Cubre solo la **identidad del receptor extranjero** en el CFDI
y la **protección del histórico**, no el tratamiento de IVA.

Plan que estoy siguiendo:
Consenso Claude + ChatGPT contra LIVA/RLIVA/RMF 2026/Anexo 20 + XML históricos reales de receptores
extranjeros del entorno. Evidencia real: todos los CFDI extranjeros usaron `Rfc=XEXX010101000`,
`Exportacion=01`, `ObjetoImp=01`, **sin impuestos**, **sin complementos** además del TimbreFiscalDigital;
`NumRegIdTrib`/`ResidenciaFiscal` **condicionales** (unos receptores sí los llevan, otros no). Por eso este
bloque NO toca IVA/ObjetoImp ni implementa Complemento Leyendas Fiscales (Art. 29-IV-i queda fuera hasta
demostrar que aplica).

Objetivo inmediato:
`/ship pr` hacia `main`. Tras merge: `/sync-check` + `/ship release` v1.8.0.

Criterio de avance:
PR mergeado con bump 1.8.0; luego release. **Pendiente antes de dar por cerrado el modelo del receptor:**
prueba de timbrado en **sandbox FacturAPI** (confirmar que `tax_id=<TIN>` + `country` producen
`Rfc=XEXX`/`NumRegIdTrib`/`ResidenciaFiscal`).

---

## Estado actual

Implementado en la rama:

- **`Customer.fm_num_reg_id_trib`** (Data, opcional) — hogar del NumRegIdTrib extranjero, separado del
  RFC/XEXX. `depends_on: eval:doc.tax_id=="XEXX010101000"` (visible solo para receptor genérico extranjero).
  Fixture + registro en `hooks.py`.
- **`timbrado_api.py`** — `es_receptor_extranjero(si)` (reutiliza la clasificación v1.7.0) +
  `receptor_tax_id_payload(customer, es_extranjera)`: nacional → RFC; extranjero → `fm_num_reg_id_trib`
  o se **omite** (FacturAPI coloca XEXX). **Nunca** se envía XEXX como `tax_id`.
- **Guard del importador** en `_set_stct_by_branch`: señal **transitoria específica**
  `doc.flags.fm_from_cfdi_emitidos` (la setea el importador en `build_si`) → solo ese flujo evita que el
  STCT nacional pise los impuestos del XML. El flujo normal (nuevo) sigue recibiendo su STCT (16%).
- **`_resolve_customer_extranjero`** — resuelve el TIN primero contra `fm_num_reg_id_trib`, fallback a `tax_id`.
- Tests: `ventas_extranjeras/tests/test_receptor_extranjero.py` (10) + `test_resolve_customer_extranjero.py`
  (14). Validación funcional en `test-fm-v010.localhost`: guard específico (solo flujo importador evita
  STCT) y mapeo receptor (omite XEXX / usa TIN) — con datos reales.
- `__init__.py` — bump `1.7.0 → 1.8.0` (MINOR).

---

## Decisiones vigentes no evidentes en el código

- **NO se toca IVA/ObjetoImp/STCT del flujo normal:** una venta extranjera nueva sigue a 16% salvo
  determinación fiscal positiva (no implementada). Extranjero ≠ 0% automático.
- **Complemento Leyendas Fiscales / Art. 29-IV-i: FUERA de alcance** — los XML reales no lo usaron.
- Señal de histórico = flag transitorio del importador (`fm_from_cfdi_emitidos`), **no** `fm_folio_fiscal`
  (que también existe en el flujo normal timbrado).
- `depends_on` UI usa solo `tax_id==XEXX` (Address.country no es accesible en el form del Customer).

### Pendientes conocidos (NO bloqueantes)
1. Prueba de timbrado en sandbox FacturAPI del receptor extranjero (cierre del modelo).
2. Determinación fiscal del servicio real (Art. 29-IV-a/-i o ninguno) → define si algún día se implementa
   el camino 0% + Leyendas. Depende de la naturaleza real del servicio, no de la ClaveProdServ.

---

## No commitear
- `facturacion_mexico/one_offs/*` (validaciones y análisis histórico; nunca al repo).
- `scripts/*`, `working_docs/private/`.
