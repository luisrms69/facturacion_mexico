# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-04
**Rama activa:** `feature/cfdi-recibidos-simplificar-resolucion-contable`
**Tarea actual:** Simplificación resolución contable CFDI Recibidos — pendiente commit + PR

---

## Recuperación rápida

Estoy trabajando en:
Simplificación del sistema de resolución de expense_account al generar Purchase Invoice
desde CFDI Recibidos. Se reemplazaron 3 modos con fallbacks por 2 modos estrictos.

Objetivo inmediato:
Commit aprobado → push → PR.

Criterio de avance:
PR abierto, CI verde.

---

## Estado actual

### Ya cerrado
- Modo Manual: expense_account por concepto, falla estricta si falta ✅
- Modo Automatico CoA SAT: family + subcuenta + formato → busca prefijo en CoA ✅
- Eliminado DocType `Mapeo Equivalencias SAT` ✅
- Eliminados campos viejos en `Configuracion CFDI Recibidos` ✅
- Campo `expense_account` agregado a `CFDI Recibido Concepto` ✅
- `_SAT_SUBCUENTA` (81 items) + populate `fm_codigo_sufijo_sat` en `after_migrate` ✅
- bench migrate en facturacion-v16.dev + actiglobal-restore.dev ✅
- Tests: 17 resolver + 44 PI builder + 8 api = 69/69 ✅
- Test integración: falla cuenta → no PI → CFDI en "Error conversión" ✅

### Pendiente inmediato
1. Commit + push
2. PR hacia main
3. Verificación GUI completa en facturacion-v16.dev (pendiente)

### No repetir
- `Mapeo Equivalencias SAT` fue eliminado — Frappe lo detecta como huérfano en migrate
- Los tests de `test_setup_expense_item_groups` y `test_custom_fields_naming_consistency` fallan por razones pre-existentes (no relacionadas con esta rama)

---

## Decisiones vigentes
- 2 modos: Manual / Automatico CoA SAT — sin fallbacks
- Si la cuenta no resuelve → no se crea PI, CFDI = "Error conversión"
- `fm_codigo_sufijo_sat` se puebla como fixture vía `after_migrate` (81 item groups mapeados)
- El prefijo SAT se construye desde family + subcuenta + formato CoA seleccionado
- Formato CoA: Select con 3 opciones fijas (########, ###-##-###, ###.##.###)

---

## Archivos relevantes ahora

### Leer primero
- `purchase_invoice_builder.py` — lógica de resolución nueva
- `configuracion_cfdi_recibidos.json` — schema simplificado

### No tocar
- `one_offs/` — no se commitean
- `actiglobal-restore.dev` — DFP External Storage tiene problema de enc_key, no escribir
