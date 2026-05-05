# ADR 0015 — Arquitectura Relación Sales Invoice ↔ Factura Fiscal Mexico

**Fecha:** 2026-05-04 | **Última revisión:** 2026-05-06 | **Estado:** VIGENTE

---

## Decisión

FFM es fuente de verdad fiscal. SI conserva solo campos operativos mínimos.
Widget `fm_ffm_summary_html` lee FFM en tiempo real — sin denormalización.

---

## Campos en Sales Invoice

| Campo | Tipo | Cuándo se escribe |
|---|---|---|
| `fm_fiscal_status` | Select | Cada transición (BORRADOR→TIMBRADO→CANCELADO) |
| `fm_factura_fiscal_mx` | Link → FFM | Al crear FFM en submit de SI |
| `fm_es_ppd` | Check | Al timbrar: 1 si PPD, 0 si PUE |

### fm_es_ppd — lógica

```python
es_ppd = 1 if FFM.fm_payment_method_sat == "PPD" else 0
# escrito en timbrado_api.py junto con fm_fiscal_status = TIMBRADO
```

### Sección fiscal consolidada

```
fm_fiscal_section → fm_fiscal_status → fm_factura_fiscal_mx → fm_es_ppd → fm_ffm_summary_html
```

---

## Campos eliminados (2026-05-04)

`fm_ffm_estado`, `fm_ffm_uuid`, `fm_ffm_numero`, `fm_ffm_fecha`, `fm_ffm_pac_msg`,
`fm_ffm_col_break`, `fm_ffm_open_btn`, `fm_ffm_section`,
`fm_last_status_update`, `fm_timbrado_section`, `fm_quick_status`, `fm_column_break_fiscal`

---

## Tests

`facturacion_fiscal/tests/test_si_ffm_cleanup.py` — 11 tests verifican
campos eliminados, `fm_es_ppd` configurado, campos esenciales presentes.

---

## Incidente recuperación (2026-05-06)

Bisect manual recreó campos `fm_ffm_*` en BD via bench migrate en commits antiguos.
Restaurado desde backup. Hook `on_submit` SI ausente desde PR #80 — diagnosticado,
fix pendiente como tarea separada.

---

## Gaps pendientes

- `Sales Invoice.on_submit` hook ausente — fix pendiente
- Draft fields (`fm_draft_*`) — diferido
- `fm_pending_amount`, `fm_complementos_count` — diferido (módulo PPD)
