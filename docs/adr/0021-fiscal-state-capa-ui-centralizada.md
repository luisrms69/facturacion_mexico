# ADR-0021 — Capa fiscal_state: UI centralizada via endpoint Python

**Fecha:** 2026-05-10
**Estado:** Implementado (PR #122)
**Branch:** feat/beta-release-fixes

---

## Contexto

Antes de este ADR, la lógica de decisión de UI (qué botones mostrar, qué mensajes emitir, qué acciones habilitar) estaba distribuida en tres capas sin coordinación:

1. **JS directo** — cada archivo `.js` consultaba campos individuales del documento y tomaba decisiones locales
2. **Múltiples llamadas async** — cada botón disparaba su propio `frappe.call` para verificar prerrequisitos
3. **`fm_require_complement`** — campo en Payment Entry calculado de forma inconsistente desde tres rutas distintas (PE creation, on_submit, en_validate)

Esto generaba:
- Inconsistencias entre lo que mostraba la UI y lo que permitía el backend
- Decisiones de roles hardcodeadas en JS (listas de nombres de roles)
- Múltiples puntos donde agregar lógica nueva requería tocar N archivos
- El bug C1: `complemento_state.py` habilitaba el botón de descarga con `has_xml/has_pdf`, pero la API lanzaba error si faltaba `facturapi_id`

---

## Decisión

Crear una capa `fiscal_state/` como **fuente única de verdad** para decisiones de UI fiscal.

### Principios

- **Read-only** — los módulos de estado solo leen, nunca modifican documentos
- **Tres capas** — `facts` (observaciones), `actions` (acciones posibles), `messages` (mensajes de UI)
- **Un solo endpoint whitelisted** — `get_fiscal_ui_state(doctype, name)` enruta a los módulos específicos
- **Sin roles hardcodeados** — permisos delegados a `frappe.model.can_cancel()` (DocPerm configurable por cliente)
- **Permission check en el gateway** — `frappe.has_permission(doctype, "read", name)` antes de cualquier cómputo

### Estructura implementada

```
facturacion_mexico/fiscal_state/
    __init__.py
    api.py                      # endpoint whitelisted
    payment_entry_state.py      # facts/actions/messages para Payment Entry
    sales_invoice_state.py      # facts/actions/messages para Sales Invoice
    ffm_state.py                # facts/actions/messages para Factura Fiscal Mexico
    complemento_state.py        # facts/actions/messages para Complemento Pago MX
```

### DocTypes migrados a fiscal_state

| DocType | Archivo JS | Qué se migró |
|---|---|---|
| Complemento Pago MX | `complemento_pago_mx.js` | Todos los botones y mensajes |
| Payment Entry | `payment_entry.js` | Botones, cancel guard, mensajes |
| Factura Fiscal Mexico | `factura_fiscal_mexico.js` | `applyFFMUi()` reemplazado por `_apply_ffm_buttons/messages()` |
| Sales Invoice | `sales_invoice.js` | Botón Timbrar, Ver Factura Fiscal, guards |

### check_ppd_requirement — implementación real

`payment_entry_validate.check_ppd_requirement()` era un no-op. Se implementó para establecer `fm_require_complement` como fuente única de verdad en BD:

- Solo aplica a PE de tipo `Receive`
- Busca SIs referenciadas con `fm_es_ppd=1` y `fm_fiscal_status=TIMBRADO`
- Usa `ignore_permissions=True` para evitar falsos negativos por permisos restringidos
- Usa `flt(allocated_amount)` para robustez ante `None`

### Gap identificado — can_register_payment

Se detectó durante la auditoría que Sales Invoice con FFM cancelada seguía mostrando el botón de registro de pago. Se agregó `can_register_payment` a `sales_invoice_state.py`:

```python
can_register_payment = is_submitted and not is_cancelled and (not has_ffm or has_active_ffm)
```

---

## Alternativas descartadas

### A) Mantener lógica en JS con más llamadas async
Descartada: amplifica el problema de N fuentes de verdad. Cada caso nuevo requiere tocar múltiples archivos.

### B) Calcular todo en `validate` y guardar en campos
Descartada: genera escrituras innecesarias en BD en cada validación, complica el historial de cambios, y mezcla preocupaciones.

### C) Un endpoint por DocType
Descartada: el gateway único `get_fiscal_ui_state` con routing interno permite evolucionar la firma sin tocar JS.

---

## Consecuencias

**Positivas:**
- Lógica fiscal centralizada y auditable en Python
- JS reducido a aplicar el estado recibido (sin decisiones)
- Roles de cancelación configurables por cliente sin tocar código
- Bug C1 corregido (can_download ahora depende de `has_facturapi_id`)
- Base para futuras features: agregar un hecho o acción nueva no requiere cambios en JS

**Negativas / Trade-offs:**
- Un `frappe.call` adicional en cada `refresh()` de los 4 doctypes
- 3 llamadas separadas en Sales Invoice refresh (SI + Opciones Fiscales + Sustituir CFDI) — pendiente consolidar (H1 CodeRabbit)
- `sales_invoice_block_cancel.js` no migrado (tiene eventos realtime — fuera de alcance)

---

## Hardening post-merge (PR #123)

CodeRabbit identificó 10 issues en PR #122, todos aplicados en `fix/coderabbit-hardening-pr122`:

| Fix | Descripción |
|---|---|
| C1 | `complemento_state` — `can_download` usa `has_facturapi_id` |
| M1 | `payment_entry_validate` — `ignore_permissions=True` |
| Q1 | `complemento_pago_mx.js` — destructuring defensivo |
| Q2 | `payment_entry_validate` — `flt(allocated_amount)` |
| Q3 | `factura_fiscal_mexico.js` — destructuring defensivo |
| Q4 | `factura_fiscal_mexico.js` — eliminar bloque if vacío |
| Q5 | `ffm_state` — `startswith` con tuple |
| Q6 | `payment_entry.js` — destructuring defensivo |
| Q8 | `si_post_fiscal_actions.js` — optional chaining |
| O1 | `factura_fiscal_mexico.js` — eliminar dead code (2 funciones sin callers) |

---

## Tests

- `facturacion_mexico.tests.test_check_ppd_requirement` — 5/5 ✅
- `facturacion_mexico.tests.test_fiscal_state_payment_entry` — suite completa ✅
- `facturacion_mexico.tests.test_refacturar_workflow` — 8/8 ✅ (regresión)
- CI primera corrida: ✅ aprobado

---

## Referencias

- PR #122: feat(fiscal-state): capa UI centralizada + migración de 4 doctypes a fiscal_state
- PR #123: fix(fiscal-state): hardening CodeRabbit PR #122 — 10 fixes
- `docs/development/fiscal-ui-state-audit.md` — auditoría previa que originó esta decisión
- `frappe-infrastructure/checkpoints/coderabbit-pr122-review.md` — análisis CodeRabbit

---

## Nota adicional — 2026-05-12 (Issue #133)

### Problema detectado post-implementación: fm_sync_status bloqueaba botón Timbrar

Durante pruebas de la rama `feature/issue129-addendas` se detectó que toda FFM nueva
quedaba con el botón "Timbrar" bloqueado hasta que el scheduler corría (hasta 5 minutos).

**Causa:** `fm_sync_status` tiene `default = "pending"` en el DocType. La lógica de
`_compute_actions` bloqueaba `can_stamp` cuando `sync_pending = True`, lo que afectaba
a **toda FFM recién creada** aunque nunca hubiera tenido una operación PAC activa.

**Corrección aplicada:**
- `can_stamp` ya no depende de `fm_sync_status` — solo depende del estado fiscal real
- El mensaje "Operación en progreso" solo aparece cuando `sync_pending=True AND (has_uuid OR facturapi_id)`
- El scheduler `bulk_sync_invoices` se mantiene activo únicamente como red de seguridad

**Hallazgo:** `FFM.on_update → update_sales_invoice_fiscal_info()` ya sincroniza SI
síncronamente. El scheduler era trabajo duplicado para el flujo normal.

**Refactor pendiente:** Ver Issue #133 para limpieza completa de `fm_sync_status`,
`bulk_sync_invoices` y el `try/except` silencioso en `update_sales_invoice_fiscal_info`.

**Análisis detallado:**
- `docs/development/REPORTE_BUG_FM_SYNC_STATUS_PENDING.md`
- `docs/development/REPORTE_FM_SYNC_STATUS_IMPLICACIONES.md`
