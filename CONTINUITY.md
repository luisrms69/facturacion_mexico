# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-02
**Rama activa:** `feature/cfdi-recibidos-cost-center-project`
**Tarea actual:** CFDI Recibidos — Department → Cost Center / Project completado

---

## Recuperación rápida

Estoy trabajando en:
Implementación de Cost Center y Project en el flujo CFDI Recibidos.
Prueba completa exitosa: asignación en modal, propagación al PI header y líneas.

Objetivo inmediato:
PR de esta rama.

---

## Estado actual

### Ya cerrado
- Nuevos campos cost_center y project en CFDI Recibido ✅
- Modal "Asignar Departamentos" extendido con CC y Proyecto ✅
- purchase_invoice_builder propaga cost_center/project al PI y líneas ✅
- cfdi_recibido.js: set_query dinámico con company (link_filters estáticos eliminados) ✅
- Validación server-side en cfdi_recibido.py ✅
- Tests: TestPurchaseInvoiceBuilderCostCenterProject ✅
- Prueba end-to-end exitosa ✅

### Pendiente
1. PR de esta rama

### No repetir
- link_filters en JSON sobreescriben set_query JS — documentado en frappe-conventions skill
- bench clear-cache requerido después de cambios a JS de DocTypes
- is_group: 0 NO puede usarse en link_filters JSON (Frappe v16 lo rechaza)

---

## Archivos relevantes
- `facturacion_mexico/cfdi_recibidos/doctype/cfdi_recibido/cfdi_recibido.json`
- `facturacion_mexico/cfdi_recibidos/doctype/cfdi_recibido/cfdi_recibido.js`
- `facturacion_mexico/cfdi_recibidos/services/purchase_invoice_builder.py`
