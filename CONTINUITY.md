# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-28
**Rama activa:** `feature/cfdi-recibidos-fase3-pi`
**Tarea actual:** Issue #152 — todos los criterios implementados; pendiente cierre explícito del issue y PR

---

## Recuperación rápida

Estoy trabajando en:
Pipeline CFDI Recibidos. PurchaseInvoiceBuilder completo, validado en GUI.
Batch "Generar PIs pendientes" implementado y probado: 4/4 exitosos en dev.

Plan que estoy siguiendo:
Issue #152 — PurchaseInvoiceBuilder, impuestos nativos y batch best-effort.

Objetivo inmediato:
El usuario decide cuándo cerrar issue #152 y cuándo abrir el PR de la rama.

Criterio de avance:
Issue #152 cerrado por el usuario → PR de la rama → merge a main.

---

## Estado actual

### Ya cerrado (issue #152 — todos los criterios)
- `fm_cfdi_uuid` y `fm_cfdi_recibido` en Purchase Invoice
- Idempotencia por UUID (casos A/B/C)
- IVA y retenciones en tabla nativa via TaxResolver
- Tolerancia configurable: absoluta (MXN) y porcentual (%) en Configuracion CFDI Recibidos
- bill_no: serie-folio → folio → uuid[:13]
- Motor de resolución de items + flujo guiado
- Botón "Generar PI" individual (form view), oculto con no_procesar=1
- Botón "Generar PIs pendientes" (list view) — batch best-effort
- posting_date y due_date usan issue_date del CFDI
- Bloqueo "Convertido a PI": frm.disable_form() + validate hook + flag in_cfdi_builder
- cost_center y bill_no collision: eliminados definitivamente del alcance

### Pendiente
- Cierre explícito de issue #152 (solo el usuario lo cierra)
- PR de la rama feature/cfdi-recibidos-fase3-pi → main
- Deuda técnica is_submittable → issue #165

### No repetir
- No proponer commits sin que el usuario lo solicite
- No incluir one_offs/ ni REPORTE_*.md en commits
- No hacer bench migrate sin autorización
- No reiniciar servidor sin autorización
- No usar ignore_default_payment_terms_template=1
- No volver a incluir cost_center ni bill_no collision en pendientes de #152
- No usar "closes/fixes/resolves #152" en commits ni PRs — el issue lo cierra el usuario

---

## Decisiones vigentes
- Tolerancia: abs=1.00 MXN y pct=0.5% en Configuracion CFDI Recibidos por empresa
- Aceptable si cumple cualquiera: diff ≤ tol_abs OR diff ≤ total_xml × (tol_pct/100)
- posting_date = issue_date del CFDI (no today())
- due_date = issue_date del CFDI (explícito, evita type mismatch con Payment Terms)
- Bloqueo "Convertido a PI" es temporal — issue #165 registra la deuda (is_submittable)
- frappe.flags.in_cfdi_builder como bypass del validate lock para saves internos
- TaxResolver lee de `Configuracion CFDI Recibidos`, no de `Configuracion Fiscal Mexico`
- Batch consulta internamente elegibles; no acepta lista seleccionada por usuario

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/cfdi_recibidos/api.py` — endpoint batch recién agregado
- `facturacion_mexico/cfdi_recibidos/doctype/cfdi_recibido/cfdi_recibido_list.js`

### Probablemente editar
- Ninguno — trabajo del issue #152 completo

### No tocar
- `facturacion_mexico/one_offs/` — nunca commitear
- `docs/development/REPORTE_*.md` — no commitear

---

## Riesgos / cuidados
- 32 commits adelante de upstream/main sin push ni PR
- issue #165 (is_submittable) debe hacerse antes de producción
- bench migrate ejecutado en test-facturacion.localhost y facturacion-v16.dev
  (columnas de tolerancia activas en ambos sites)
