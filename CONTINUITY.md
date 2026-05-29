# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-28
**Rama activa:** `feature/cfdi-recibidos-fase3-pi`
**Tarea actual:** Cerrar issue #152 — gaps restantes del PurchaseInvoiceBuilder

---

## Recuperación rápida

Estoy trabajando en:
Pipeline CFDI Recibidos. El botón "Generar Purchase Invoice" ya funciona — se probó
en GUI y creó ACC-PINV-2026-00001 correctamente. Tres bugs corregidos en esta sesión.

Plan que estoy siguiendo:
Issue #152 — PurchaseInvoiceBuilder, impuestos nativos y batch best-effort.

Objetivo inmediato:
Revisar ACC-PINV-2026-00001 en GUI — verificar si ERPNext exige cost_center y
expense_account por línea al intentar Submit de la PI.

Criterio de avance:
PI puede someterse (Submit) sin errores → issue #152 cerrado o gaps documentados.

---

## Estado actual

### Ya cerrado (issue #152)
- `fm_cfdi_uuid` y `fm_cfdi_recibido` en Purchase Invoice
- Idempotencia por UUID (casos A/B/C)
- IVA y retenciones en tabla nativa via TaxResolver
- Tolerancia de redondeo (0.02 hardcoded)
- bill_no: serie-folio → folio → uuid[:13]
- Motor de resolución de items + flujo guiado (commit 907a700)
- Botón "Generar PI" oculto con no_procesar=1
- posting_date y due_date usan issue_date del CFDI (no today())
- Bloqueo "Convertido a PI": frm.disable_form() + validate hook + flag in_cfdi_builder
- Deuda técnica is_submittable → issue #165

### Pendiente (issue #152)
- cost_center por línea de PI (probable error al Submit en ERPNext)
- expense_account por línea de PI (probable error al Submit en ERPNext)
- Colisión supplier+bill_no → usar UUID completo
- Tolerancia configurable desde `Facturacion Mexico Settings`
- Batch desde lista (múltiples CFDIs)

### No repetir
- No proponer commits sin que el usuario lo solicite
- No incluir one_offs/ ni REPORTE_*.md en commits
- No hacer bench migrate sin autorización
- No reiniciar servidor sin autorización (el autoreload de Werkzeug funciona)
- No usar ignore_default_payment_terms_template=1 (usuario lo rechazó)

---

## Decisiones vigentes
- posting_date = issue_date del CFDI (no today())
- due_date = issue_date del CFDI (explícito, evita type mismatch con Payment Terms)
- Bloqueo "Convertido a PI" es temporal — issue #165 registra la deuda (is_submittable)
- frappe.flags.in_cfdi_builder como bypass del validate lock para saves internos
- TaxResolver lee de `Configuracion CFDI Recibidos`, no de `Configuracion Fiscal Mexico`
- Auto-asignación en upload: SOLO nivel 5 (no_identificacion == item_code)

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/cfdi_recibidos/services/purchase_invoice_builder.py`
- `facturacion_mexico/cfdi_recibidos/services/tax_resolver.py`

### Probablemente editar
- `purchase_invoice_builder.py` — cost_center, expense_account, bill_no collision, tolerancia

### No tocar
- `facturacion_mexico/one_offs/` — nunca commitear
- `docs/development/REPORTE_*.md` — no commitear

---

## Riesgos / cuidados
- ERPNext exige cost_center y expense_account por línea al Submit de PI
- Batch no implementado — criterio de aceptación del issue aún abierto
- 30 commits adelante de upstream/main sin push ni PR
- issue #165 (is_submittable) debe hacerse antes de producción
