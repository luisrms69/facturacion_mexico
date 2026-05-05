# ADR 0014 — Diagnóstico Conectividad Sales Invoice ↔ Factura Fiscal Mexico

**Fecha:** 2026-05-04
**Estado:** Cerrado — diagnóstico completo. Ver sección "Acciones ejecutadas" al final.
**Autor:** Luis Montanaro Sánchez

---

> ⚠️ **Nota:** Este ADR documenta el estado observado al 2026-05-04. Muchos campos son legacy de una primera implementación donde SI y FFM eran concebidos como el mismo documento o convivían más estrechamente.

---

## Contexto histórico

En la implementación original de `facturacion_mexico`, varios campos fiscales vivían
directamente en el Sales Invoice: `fm_payment_method_sat`, `fm_lugar_expedicion`,
`fm_serie_folio`, `fm_cfdi_use`, `fm_uuid_fiscal`. En una migración posterior se
decidió mover esos campos al DocType `Factura Fiscal Mexico` (FFM) como fuente de
verdad fiscal, dejando en SI solo un link de referencia.

La migración se hizo campo por campo — los custom fields se comentaron en `hooks.py`
(evidencia: líneas con comentarios `# MIGRADO A Factura Fiscal Mexico`) pero
las secciones que los contenían no siempre se eliminaron, y se agregaron nuevos campos
de display (`fm_ffm_*`) como denormalización para evitar joins en la UI.

---

## Arquitectura actual — link bidireccional

```
Sales Invoice                    Factura Fiscal Mexico
─────────────────               ──────────────────────────
fm_factura_fiscal_mx ──────────→ name
fm_fiscal_status     (activo)   fm_fiscal_status (fuente)
fm_ffm_uuid          (MUERTO)   fm_uuid
fm_ffm_numero        (MUERTO)   fm_serie_folio
fm_ffm_fecha         (MUERTO)   fecha_timbrado
fm_ffm_estado        (MUERTO)   fm_fiscal_status
                    ←────────── sales_invoice
```

Ambos documentos se referencian mutuamente. Los links activos son:
- SI → FFM: `si.fm_factura_fiscal_mx`
- FFM → SI: `ffm.sales_invoice`

---

## Campos custom `fm_*` en Sales Invoice — clasificación completa

### Grupo 1 — Esenciales (únicos con datos reales en BD)

| Campo | Tipo | Qué hace | Quién escribe | Quién lee |
|---|---|---|---|---|
| `fm_fiscal_status` | Select | Estado fiscal: BORRADOR/TIMBRADO/CANCELADO/PENDIENTE_CANCELACION/ERROR | `timbrado_api.py`, `sales_invoice_submit.py`, `sales_invoice_cancel.py`, `revisar_estatus_cancelacion()` | Toda la lógica de cancelación, timbrado, validaciones, UI |
| `fm_factura_fiscal_mx` | Link→FFM | Referencia al documento fiscal | `sales_invoice_submit.py` al crear FFM; se limpia en cascade de sustitución | Toda la lógica fiscal, ereceipts, cancelaciones |

### Grupo 2 — Campos de display MUERTOS (NULL en 783/783 SIs) — ELIMINADOS 2026-05-04

Diseñados para ser sincronizados por `ffm_hooks.py::sync_ffm_summary_to_sales_invoice()`,
pero **esa función nunca se llamó** — `Factura Fiscal Mexico` no tiene hook `on_update`
registrado en `hooks.py`. Verificado: 0 registros con valor en toda la BD.

`sales_invoice_ffm_summary.js` tampoco los usaba — hacía `frappe.call({method: "get_ffm_summary"})`
que consultaba la FFM directamente al renderizar.

| Campo | Valor en toda la BD | Estado |
|---|---|---|
| `fm_ffm_estado` | **NULL en 783/783** | ✅ Eliminado 2026-05-04 |
| `fm_ffm_uuid` | **NULL en 783/783** | ✅ Eliminado 2026-05-04 |
| `fm_ffm_numero` | **NULL en 783/783** | ✅ Eliminado 2026-05-04 |
| `fm_ffm_fecha` | **NULL en 783/783** | ✅ Eliminado 2026-05-04 |
| `fm_ffm_pac_msg` | **NULL en 783/783** | ✅ Eliminado 2026-05-04 |
| `fm_ffm_col_break` | Column Break layout | ✅ Eliminado 2026-05-04 |
| `fm_ffm_open_btn` | Botón duplicado (ya existe en toolbar) | ✅ Eliminado 2026-05-04 |

### Grupo 3 — Módulos activos con campos propios en SI

| Módulo | Campos | Estado |
|---|---|---|
| Multi-sucursal | `fm_branch`, `fm_branch_health_status`, `fm_certificate_info`, `fm_auto_selected_branch`, `fm_original_stct_template` | ✅ Activos |
| Addendas | `fm_addenda_type`, `fm_addenda_required`, `fm_addenda_status`, `fm_addenda_xml`, `fm_addenda_errors`, `fm_addenda_generated_date` | ✅ Activos |
| E-Receipts | `fm_ereceipt_mode`, `fm_ereceipt_expiry_type/days/date` | ✅ Activos |

### Grupo 4 — Campos legacy sin uso activo confirmado

| Campo(s) | Origen | Estado real en BD | Decisión |
|---|---|---|---|
| `fm_draft_status`, `fm_draft_created_date`, `fm_draft_approved_by`, `fm_factorapi_draft_id`, `fm_create_as_draft` | Draft Management — TODO MOCK | `""`, `NULL`, `0` en toda la BD | Diferido — eliminar cuando se decida el futuro del módulo draft |
| `fm_pending_amount`, `fm_complementos_count` | PPD/Complementos — hook roto | `0.0`, `0` en toda la BD | Diferido — los necesitará el módulo PPD |
| `fm_folio_reserved` | Multi-sucursal | `0` en toda la BD | Conservar — activo en `multi_sucursal/sales_invoice_fields.py` |
| `fm_last_status_update` | Auditoría timestamp | `NULL` en toda la BD | ✅ Eliminado 2026-05-04 |
| `fm_timbrado_section` | Sección "Historial de Timbrado" vacía | Solo layout | ✅ Eliminado 2026-05-04 |
| `fm_quick_status` | HTML display badge | Sin uso real — widget lo reemplaza | Pendiente eliminar |

### Grupo 5 — Campos migrados a FFM (eliminados de SI)

```python
# hooks.py:
# "Sales Invoice-fm_payment_method_sat"         # MIGRADO A Factura Fiscal Mexico
# "Sales Invoice-fm_lugar_expedicion"            # MIGRADO A Factura Fiscal Mexico
# "Sales Invoice-fm_serie_folio"                 # MIGRADO A Factura Fiscal Mexico
# "Sales Invoice-fm_cfdi_use"                    # MIGRADO A Factura Fiscal Mexico
# "Sales Invoice-fm_uuid_fiscal"                 # ELIMINADO — usar get_invoice_uuid()
# "Sales Invoice-fm_informacion_fiscal_section"  # ELIMINADO — sección vacía
```

---

## Ciclo de vida real de los campos en SI (verificado en BD)

### Al crear/submit Sales Invoice

```
SI.on_submit hook
  → crear FFM en estado BORRADOR
  → frappe.db.set_value(SI, "fm_fiscal_status", "BORRADOR")
  → frappe.db.set_value(SI, "fm_factura_fiscal_mx", ffm.name)
```

### Al timbrar

```
TimbradoAPI.timbrar()
  → PAC responde OK
  → frappe.set_value(SI, {"fm_fiscal_status": "TIMBRADO"})
  ← SOLO ESO. Los fm_ffm_* nunca se escribieron (confirmado BD).
```

### Al cancelar

```
cancelar_factura() / revisar_estatus_cancelacion()
  → frappe.set_value(SI, {"fm_fiscal_status": "CANCELADO"})
```

### En cascade de sustitución (motivo 01)

```
_cascade_cancel_previous_after_substitute()
  → orig_si.db_set("fm_factura_fiscal_mx", "")    ← limpiado
  → orig_ffm.db_set("sales_invoice", "")           ← limpiado
  → orig_ffm.db_set("sales_invoice", orig_si_name) ← restaurado post-cancel
```

---

## Verificación de integridad BD (2026-05-04)

Consultas directas sobre `facturacion-v16.dev` — 783 SIs, 170+ FFMs.

| Verificación | Resultado |
|---|---|
| Campos `fm_ffm_*` poblados en alguna SI | **0/783** — muertos confirmados |
| SIs TIMBRADO sin FFM | **0** — integridad OK |
| FFMs TIMBRADO sin SI válida | **0** — integridad OK |
| Links rotos SI → FFM | **0** — integridad OK |
| Múltiples FFM TIMBRADO por misma SI | **0** — integridad OK |
| Múltiples FFM cualquier estado por misma SI | **9 casos** — todos CANCELADO o BORRADOR |

---

## Bugs identificados

### Bug 1 — Indicador "Ya Timbrada" duplicado en Stats — CORREGIDO 2026-05-04

`sales_invoice.js` llamaba `add_view_fiscal_button(frm)` desde dos paths del refresh.
Cada llamada agregaba `frm.dashboard.add_indicator("Ya Timbrada", "green")`.
**Corrección:** eliminado el indicador completamente — el widget HTML ya muestra el estado.

### Bug 2 — sync_ffm_summary nunca registrada — RESUELTO 2026-05-04

`ffm_hooks.py` definía `sync_ffm_summary_to_sales_invoice()` pero no estaba en `hooks.py`.
Los campos `fm_ffm_*` en SI nunca se poblaron.
**Resolución:** función neutralizada (stub), campos `fm_ffm_*` eliminados de BD y fixtures.

---

## Acciones ejecutadas (2026-05-04)

### Campos eliminados de BD, fixtures y código

**Grupo 2 completo:**
- `fm_ffm_estado`, `fm_ffm_uuid`, `fm_ffm_numero`, `fm_ffm_fecha`, `fm_ffm_pac_msg`
- `fm_ffm_col_break`, `fm_ffm_open_btn`
- Removidos de: `setup/customize_sales_invoice.py` (que corre en `after_migrate`)

**Grupo 4 parcial:**
- `fm_last_status_update` — removido de fixtures, `utils.py`, `timbrado_api.py`
- `fm_timbrado_section` — sección "Historial de Timbrado" eliminada

**Código limpiado:**
- `ffm_hooks.py` → función neutralizada con `pass`
- `utils_testing.py` → referencias a `fm_ffm_uuid` eliminadas
- `sales_invoice.js` → indicador "Ya Timbrada" eliminado de `add_view_fiscal_button`

### Widget como sustituto de denormalización

`sales_invoice_ffm_summary.js` + `fm_ffm_summary_html` es el patrón correcto:
lee FFM en tiempo real vía `get_ffm_summary` API, sin persistir datos en SI.
Muestra: Estado CFDI, Serie y Folio, UUID, Fecha Timbrado, Estado PAC.

### Dead code pendiente

- `sales_invoice_ffm_summary.js` aún referencia `fm_ffm_open_btn` (ya eliminado) — limpiar

---

## Referencias

- `facturacion_mexico/facturacion_fiscal/api/ffm_hooks.py` — función neutralizada
- `facturacion_mexico/facturacion_fiscal/hooks_handlers/sales_invoice_submit.py`
- `facturacion_mexico/facturacion_fiscal/timbrado_api.py`
- `facturacion_mexico/public/js/sales_invoice.js`
- `facturacion_mexico/public/js/sales_invoice_ffm_summary.js`
- `facturacion_mexico/hooks.py` líneas 168-215
