# ADR 0015 — Arquitectura Relación Sales Invoice ↔ Factura Fiscal Mexico

**Fecha:** 2026-05-04
**Estado:** REVISADO 2026-05-05 — tests automatizados agregados
**Autor:** Luis Montanaro Sánchez

---

## Contexto

Sales Invoice (SI) es el documento operativo nativo de ERPNext.
Factura Fiscal Mexico (FFM) es el documento fiscal propio, fuente de
verdad para todo lo relacionado con el CFDI.

En la implementación original se intentó denormalizar datos de FFM hacia SI
mediante campos `fm_ffm_*`. Esa sincronización nunca se implementó.
Verificado en BD: 783 SIs, 100% de campos `fm_ffm_*` con valor NULL.
**Los campos `fm_ffm_*` fueron eliminados el 2026-05-04.**

---

## Decisión

**Modelo híbrido: FFM como fuente fiscal + widget en SI para display + flag operativo para PPD.**

El widget `fm_ffm_summary_html` + `sales_invoice_ffm_summary.js` cubre la necesidad
de display en tiempo real sin persistir datos en SI. Lee FFM via `get_ffm_summary` API
y muestra: Estado CFDI, Serie y Folio, UUID, Fecha Timbrado, Estado PAC.

Para el módulo PPD se necesitará un campo flag en SI para detección sin joins.
Ese campo se crea cuando el módulo PPD se implemente — no antes.

---

## Campos en Sales Invoice — estado final

### Activos (ya existen, sin cambio)

| Campo | Comportamiento |
|---|---|
| `fm_fiscal_status` | Estado fiscal — se actualiza en cada transición |
| `fm_factura_fiscal_mx` | Link a FFM — se escribe al crear FFM en submit |

### Display — cubierto por widget (sin campos persistentes en SI)

El widget `fm_ffm_summary_html` muestra en tiempo real desde FFM:

| Dato mostrado | Origen en FFM | Campo SI descartado |
|---|---|---|
| Estado CFDI | `ffm.fm_fiscal_status` | ~~`fm_uuid` propuesto~~ — no necesario |
| Serie y Folio | `ffm.fm_serie_folio` | ~~`fm_folio_fiscal` propuesto~~ — no necesario |
| UUID | `ffm.fm_uuid` | ~~`fm_uuid` propuesto~~ — no necesario |
| Fecha Timbrado | `ffm.fecha_timbrado` | ~~`fm_fecha_timbrado` propuesto~~ — no necesario |
| Estado PAC | `ffm.fm_sync_error` | — |

### Campo `fm_es_ppd` — implementado (2026-05-05)

`fm_es_ppd` (Check, `read_only`, `allow_on_submit=1`, `default=0`) fue creado en SI.
Se escribe al timbrar en `timbrado_api.py`: `1` si `FFM.fm_payment_method_sat == PPD`, `0` si PUE.
Ubicación visual: después de `fm_factura_fiscal_mx`, antes del widget.

### Eliminados — muertos confirmados en BD

Todos eliminados el 2026-05-04:
- `fm_ffm_estado`, `fm_ffm_uuid`, `fm_ffm_numero`, `fm_ffm_fecha`, `fm_ffm_pac_msg`
- `fm_ffm_col_break`, `fm_ffm_open_btn`
- `fm_last_status_update`, `fm_timbrado_section`

---

## Reglas arquitectónicas

1. **FFM es la referencia para operaciones fiscales** — XML, UUID, datos SAT, motivo cancelación
2. **SI es el índice para operación diaria** — `fm_fiscal_status` para estados, `fm_factura_fiscal_mx` para link
3. **El widget no persiste datos en SI** — lee FFM en tiempo real, no contamina el doc
4. **No sync genérico automático** `on_update FFM → SI` — el hook `sync_ffm_summary` fue eliminado
5. **Nuevos campos snapshot en SI solo si hay necesidad operativa real** — no anticipar

---

## Tests automatizados (2026-05-05)

`facturacion_fiscal/tests/test_si_ffm_cleanup.py` — 11 tests:

| Test | Qué verifica |
|---|---|
| `test_fm_ffm_*_eliminado` (×5) | Campos `fm_ffm_uuid`, `fm_ffm_numero`, `fm_ffm_fecha`, `fm_ffm_estado`, `fm_ffm_pac_msg` no existen en SI |
| `test_fm_ffm_section_eliminada` | Sección `fm_ffm_section` no existe |
| `test_fm_column_break_fiscal_eliminado` | `fm_column_break_fiscal` no existe |
| `test_fm_es_ppd_existe` | Custom Field presente |
| `test_fm_es_ppd_es_check` | `fieldtype = Check` |
| `test_fm_es_ppd_default_cero` | `default = 0` |
| `test_fm_es_ppd_allow_on_submit` | `allow_on_submit = 1` |
| `test_fm_es_ppd_insert_after_fm_factura_fiscal_mx` | Posición visual correcta |
| `test_fm_fiscal_status_existe` | Campo esencial sigue presente |
| `test_fm_factura_fiscal_mx_existe` | Campo esencial sigue presente |
| `test_fm_ffm_summary_html_existe` | Widget presente |

---

## Pendiente de limpieza

| Item | Archivo | Acción |
|---|---|---|
| Draft fields (`fm_draft_*`) | `hooks.py`, `custom_field.json`, `sales_invoice_addenda_fields.py` | Diferido — decidir futuro del módulo draft |
| `fm_pending_amount`, `fm_complementos_count` | Fixtures, código | Diferido — módulo PPD |

---

## Alternativas descartadas

### Opción A — Link puro
Solo `fm_fiscal_status` + `fm_factura_fiscal_mx`. Todo lo demás via join a FFM.
**Estado:** Parcialmente adoptada — el widget implementa esto para display.

### Opción B — Snapshot inmutable con campos nuevos en SI
Crear `fm_uuid`, `fm_folio_fiscal`, `fm_fecha_timbrado`, `fm_es_ppd` en SI.
**Descartada para display** — el widget ya cubre uuid/folio/fecha sin duplicar datos.
**`fm_es_ppd` diferido** — se creará solo cuando el módulo PPD lo necesite.

### Opción C — Denormalización con sync permanente
Mantener `fm_ffm_*` y activar `sync_ffm_summary_to_sales_invoice()` en `on_update` FFM.
**Descartada** — generaba doble fuente de verdad con sync que históricamente produjo bugs
silenciosos. Los campos nunca tuvieron datos en BD (783/783 NULL).

---

## Módulo PPD — impacto futuro

Cuando se implemente el módulo PPD, el campo `fm_es_ppd` permitirá:

```python
# payment_entry_submit.py
def _requires_ppd_complement(si):
    return (
        si.get("fm_es_ppd") == 1 and
        si.get("fm_fiscal_status") == "TIMBRADO"
    )
```

Punto de escritura cuando se cree: `timbrado_api.py` — en el mismo `db_set`
que escribe `fm_fiscal_status = TIMBRADO`.

---

## Referencias

- ADR 0014 — Diagnóstico conectividad SI ↔ FFM
- `facturacion_mexico/public/js/sales_invoice_ffm_summary.js` — widget activo
- `facturacion_mexico/api/ffm_summary.py` — API que alimenta el widget
- `facturacion_mexico/facturacion_fiscal/timbrado_api.py` — punto de escritura fiscal
- `facturacion_mexico/facturacion_fiscal/api/ffm_hooks.py` — función neutralizada
