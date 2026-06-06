# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-06
**Rama activa:** `feature/160-factura-global-hardcodes`
**Tarea actual:** Issue #160 — eliminar hardcodes fiscales en Factura Global / EReceipt MX

---

## Recuperación rápida

Estoy trabajando en:
Issue #160: valores fiscales hardcodeados en `cfdi_global_builder.py`. Commit hecho en
esta rama, pendiente de push y PR hacia `main`.

Plan que estoy siguiendo:
GitHub issue #160 — "feat: prerequisitos fiscales requeridos antes de activar Factura Global MX"

Objetivo inmediato:
Push + PR de esta rama a `main`.

Criterio de avance:
PR creado, CI verde, merge autorizado por el usuario.

---

## Estado actual

### Ya cerrado
- PR #181 mergeado ✅ — issues #161 y #162 cerrados
- Issue #182 creado ✅ — modelo line-level IEPS para EReceipt MX / Factura Global

### En progreso
- Rama `feature/160-factura-global-hardcodes`: commit hecho, push pendiente

### Pendiente inmediato
1. Push de `feature/160-factura-global-hardcodes` → upstream
2. Crear PR → `main`
3. Revisión + merge

### No repetir
- `\n` dentro de `_()` dispara `frappe-translation-python-splitting`
- `tax_rate` en EReceipt MX es modelo **transitorio** — el definitivo es issue #182 (line-level)
- "no IVA rows" ≠ exento — `extract_iva_info_from_si_taxes` retorna `None`, no `0.0`
- Test runner falla pre-existente (`_Test Item is not a stock Item`) — ERPNext, no causado por este PR

---

## Decisiones vigentes

- `tax_rate` + `has_ieps` en EReceipt MX son campos transitorios (doc en el JSON del doctype)
- `extract_iva_info_from_si_taxes`: sin default 16, sin asunción de exento, bloquea si indeterminado
- IEPS en Factura Global: bloqueado con error explícito referenciando issue #182
- `frappe.flags.in_test` guard en `sales_invoice_automated_tax.py` — test records de ERPNext no tienen SAT key
- Clave SAT obligatoria en flujo fiscal (3 capas de defensa) — heredado de main
- main nunca es rama de trabajo

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/facturas_globales/processors/cfdi_global_builder.py`
- `facturacion_mexico/utils/calculo_impuestos.py` (nueva función `extract_iva_info_from_si_taxes`)

### Probablemente editar en próximos issues
- `facturacion_mexico/ereceipts/doctype/ereceipt_mx/ereceipt_mx.json` (issue #182)
- `facturacion_mexico/facturas_globales/processors/ereceipt_aggregator.py` (issue #182)

### No tocar
- `working_docs/active/addenda_la_comer_evidencia/` — evidencia de epic distinto
- `facturacion_mexico/one_offs/verificar_issue_160.py` — no commitear

---

## Riesgos / cuidados

- EReceipts existentes sin `tax_rate`: al incluirlos en Factura Global → `ValidationError` claro (correcto por diseño)
- Company Settings sin `global_payment_form_default`: bloquea al timbrar Factura Global (correcto)
- Issue #182 (IEPS line-level) debe hacerse antes de activar Factura Global en producción con productos IEPS
