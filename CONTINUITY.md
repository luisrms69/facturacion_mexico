# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-02
**Rama activa:** `feature/cfdi-recibidos-cost-center-project`
**Tarea actual:** CFDI Recibidos — plan CoA SAT comprometido, implementación pendiente

---

## Recuperación rápida

Estoy trabajando en:
El módulo CFDI Recibidos ya tiene Department, Cost Center y Project funcionando
(commit cc8910c). El siguiente paso es la asignación automática de `expense_account`
en el Purchase Invoice, basada en el Código Agrupador SAT.

Plan rector aprobado en `working_docs/active/PLAN_CFDI_RECIBIDOS_COA_SAT_NORMALIZATION.md`.

Objetivo inmediato:
Implementar los cambios del plan: campo `modo_resolucion_cuenta_gasto` y
`formato_cuenta_gasto` en `Configuracion CFDI Recibidos`, campo `codigo_sufijo_sat`
en Item Group, y lógica en `purchase_invoice_builder`.

---

## Estado actual

### Ya cerrado en esta rama
- cost_center y project en CFDI Recibido (campos directos) ✅
- Modal "Asignar Departamentos" con CC y Proyecto ✅
- purchase_invoice_builder propaga cost_center/project al PI y líneas ✅
- link_filters estáticos eliminados del JSON (causa raíz del filtro JS) ✅
- Validación server-side en cfdi_recibido.py ✅
- Plan técnico CoA SAT aprobado ✅

### Pendiente inmediato
1. Implementar campo `codigo_sufijo_sat` en Item Group (Custom Field via fixture)
2. Implementar campos `modo_resolucion_cuenta_gasto` + `formato_cuenta_gasto` en `Configuracion CFDI Recibidos`
3. Implementar lógica de resolución en `purchase_invoice_builder._append_item()`
4. Tests para las tres estrategias de resolución
5. PR de esta rama

### No repetir
- link_filters en JSON del DocType sobreescriben set_query JS (frappe-conventions skill)
- account_number NO debe ser forzado a formato SAT — es número operativo de la empresa
- bench clear-cache requerido después de cambios a JS de DocTypes

---

## Decisiones ya tomadas (ver plan)
- Tres estrategias: `patron`, `matriz_equivalencias`, `manual_asistido`
- `account_number` es número operativo, no código SAT
- Sin fallback silencioso a item_defaults
- Formato recomendado para clientes nuevos: `{f}-{s}-000` (ej: `603-48-000`)

---

## Archivos relevantes
- `working_docs/active/PLAN_CFDI_RECIBIDOS_COA_SAT_NORMALIZATION.md`
- `facturacion_mexico/cfdi_recibidos/services/purchase_invoice_builder.py`
- `facturacion_mexico/cfdi_recibidos/doctype/configuracion_cfdi_recibidos/`
