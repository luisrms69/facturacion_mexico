# ADR 0024 — Addendas CFDI pre-timbrado (Issue #129)

**Fecha:** 2026-05-12
**Estado:** Implementado — BUG MAYOR PENDIENTE
**Autor:** Luis Montanaro / Claude Sonnet 4.6

---

## Contexto

Issue #129 requería activar el flujo de addendas CFDI en el sistema. Los campos
`fm_requires_addenda` y `fm_default_addenda_type` en Customer, y sus contrapartes
en Sales Invoice, existían en fixtures pero estaban completamente desconectados del
flujo de timbrado.

---

## Decisión

Implementar addendas en modo **pre-timbrado**: la addenda se envía en el payload de
`create_invoice` de FacturAPI, antes de sellar el CFDI. El XML devuelto por FacturAPI
ya incluye `<cfdi:Addenda>` integrada después de `<cfdi:Complemento>`.

### Fases implementadas

**Fase 1 — Validación FacturAPI (sandbox)**
- Confirmado: `create_invoice` acepta `addenda: string<xml>` y `namespaces: [{prefix, uri}]`
- Formato exacto: array de objetos con `prefix` y `uri` — sin `name` ni `schemaLocation`
- XML timbrado contiene `<cfdi:Addenda>` correctamente posicionada

**Fase 2 — AddendaService neutral**
- `facturacion_mexico/addendas/addenda_service.py`
- `render()` retorna `None` si no requiere addenda — payload no se modifica
- `render()` lanza `frappe.throw` si requiere pero config incompleta — bloquea timbrado
- 19 tests

**Fase 3 — Propagación Customer → Sales Invoice**
- Hook `Sales Invoice.validate` propaga `fm_requires_addenda` y `fm_default_addenda_type`
- Solo propaga si el campo en SI está vacío (respeta overrides manuales)
- No bloquea guardado de draft
- 10 tests

**Fase 3 UI — Campos editables en draft**
- `fm_addenda_section`: visible cuando hay customer (no solo en submitted)
- `fm_addenda_required` y `fm_addenda_type`: editables en draft, read-only en submit
- Fixture: `read_only=0`, `allow_on_submit=0`, `read_only_depends_on=eval:doc.docstatus != 0`

**Fase 4 — Pre-timbrado en payload**
- `_prepare_facturapi_data()` en `timbrado_api.py`
- Si `render()` retorna `None`: payload intacto, sin llaves `addenda` ni `namespaces`
- Si `render()` retorna dict: agrega `addenda` y opcionalmente `namespaces`
- 8 tests

---

## Validación realizada

| Prueba | Resultado |
|---|---|
| Customer con addenda → SI propaga flags | PASS |
| Override manual en SI draft | PASS |
| Timbrado con addenda (Liverpool, Ecoeficiencia) | PASS — `<cfdi:Addenda>` en XML |
| Timbrado sin addenda (VENTA MOSTRADOR) | PASS — XML limpio, sin `<Addenda>` |

---

## ⚠️ BUG MAYOR — Pendiente de diagnóstico

### Descripción

Durante las pruebas de validación GUI post-Fase 4, se detectó el siguiente
comportamiento anómalo en el flujo principal de timbrado:

1. **Botón "Timbrar Factura" desaparece en FFM** después de navegar desde SI.
   Solo reaparece navegando varias veces entre SI y FFM. Comportamiento intermitente.

2. **SI submitted aparece como editable** después de un timbrado. El botón
   "Timbrar Factura" reaparece en SI (no debería — ya está timbrada).

3. **Error "Field not permitted in query: fm_fiscal_status"** al intentar
   timbrar de nuevo desde SI en ese estado.

4. **FFM queda en "Operación en Progreso"** — el timbrado inicia pero
   `_process_timbrado_success` falla o no completa correctamente.

### Origen probable

El bug se originó en **Fase 3 UI o Fase 4**, confirmado por el usuario.
Candidatos probables:

- `fm_addenda_required` y `fm_addenda_type` con `read_only=0, allow_on_submit=0`
  en SI submitted pueden causar que Frappe trate el documento como editable,
  interfiriendo con la lógica del fiscal_state y el botón timbrar.

- La llamada a `AddendaService().render(sales_invoice)` en `_prepare_facturapi_data()`
  podría tener un side effect no anticipado sobre el estado del documento.

### Impacto

**CRÍTICO** — Afecta el flujo principal de timbrado del sistema.
FFM puede quedar en estado "Operación en Progreso" (bloqueada) sin completar.

### Estado

**Sin resolver.** Se documenta aquí para trazabilidad.
No avanzar a Fase 5 ni a producción sin resolver este bug.

### Hipótesis a investigar

1. `allow_on_submit=0` + `read_only=0` en campos addenda → Frappe trata SI como
   editable después de submit → interfiere con `get_fiscal_ui_state()`.

2. Error en `_process_timbrado_success` al actualizar SI con `frappe.set_value`
   cuando la SI está en estado "pseudo-editable" por los campos addenda.

3. Race condition en JS: `get_fiscal_ui_state` retorna estado incorrecto en primera
   carga de FFM.

---

## Consecuencias

- Addendas pre-timbrado funcionan correctamente en condiciones normales
- El bug de campos addenda (`allow_on_submit`) debe resolverse antes de despliegue
- Issue #132 (campos legacy `fm_addenda_status/xml/errors/date`) sigue pendiente de análisis
