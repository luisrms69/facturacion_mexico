# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-06
**Rama activa:** `fix/issue-162-clave-sat-obligatoria`
**Tarea actual:** Dos commits listos — pendiente push + PR

---

## Recuperación rápida

Esta rama contiene correcciones para los issues #162 y #161:

- **Commit 1 (`05d11bc`)** — issue #162: eliminar fallback "01010101" clave SAT en timbrado
- **Commit 2 (pendiente push)** — issue #161: eliminar inferencia forma de pago por string-slice

Objetivo inmediato: push → PR.

---

## Estado actual

### Ya cerrado
- PR #177–#180 mergeados ✅
- Issue #162: fallback "01010101" eliminado — 3 capas de defensa ✅
- Issue #161: string-slice eliminado — helper `_resolver_forma_pago_sat` ✅
- Validado en GUI (actiglobal-restore.dev:8406) ✅
- Suite completa: 1136 tests — 2 failures preexistentes no relacionados ✅

### Pendiente inmediato
1. Push + PR de esta rama
2. Decidir siguiente frente: issue #163 (limpieza técnica) o Fase 4 pagos (#153)

### No repetir
- `or "01010101"` como fallback de clave SAT — eliminado (#162)
- `[:2].strip()` como inferencia de forma de pago SAT — eliminado (#161)
- `fm_codigo_sat` / `custom_forma_pago_sat` — campos fantasma, no crear ni usar

---

## Decisiones vigentes

- Clave SAT obligatoria en flujo fiscal (no global en Item)
- Forma de pago SAT solo desde MoP del fixture con patrón `^\d{2} - .+$` + lookup en Forma Pago SAT
- MoP nativos ERPNext (Cash, Wire Transfer, etc.) deshabilitados en fixture
- Mensaje de error en español claro y accionable

---

## Archivos de esta rama

### issue #162 (commit 05d11bc)
- `timbrado_api.py` — `_validate_items_clave_sat_for_timbrado` + defensa final + sin "01010101"
- `factura_fiscal_mexico.py` — `_validate_items_clave_sat` en `validate()`
- `hooks_handlers/sales_invoice_automated_tax.py` — mensaje error mejorado
- `tests/test_issue162_clave_sat_obligatoria.py` — 9 tests

### issue #161 (commit pendiente)
- `complementos_pago/api.py` — `_resolver_forma_pago_sat` + reemplaza string-slice
- `fixtures/mode_of_payment.json` — MoP nativos con `enabled: 0`
- `complementos_pago/tests/test_resolver_forma_pago_sat.py` — 16 tests

### No tocar
- `one_offs/` — no se commitean
- `actiglobal-restore.dev` — enc_key DFP External Storage (no adjuntos)
- E-Receipts, Factura Global, CFDI Recibidos — fuera de alcance de esta rama
