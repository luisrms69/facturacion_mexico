# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-28
**Rama activa:** `feature/cfdi-recibidos-fase3-pi`
**Tarea actual:** Issue #152 — tolerancia configurable completada; decidir si batch bloquea el cierre

---

## Recuperación rápida

Estoy trabajando en:
Pipeline CFDI Recibidos. El botón "Generar Purchase Invoice" funciona en GUI.
La tolerancia configurable (absoluta + porcentual) fue implementada y testeada (34/34).

Plan que estoy siguiendo:
Issue #152 — PurchaseInvoiceBuilder, impuestos nativos y batch best-effort.

Objetivo inmediato:
Decidir si el criterio "Batch" de #152 se cierra en issue separado o bloquea el issue.
Pendiente: bench migrate en facturacion-v16.dev para activar columnas de tolerancia en dev.

Criterio de avance:
#152 cerrado o batch separado → rama lista para PR.

---

## Estado actual

### Ya cerrado (issue #152)
- `fm_cfdi_uuid` y `fm_cfdi_recibido` en Purchase Invoice
- Idempotencia por UUID (casos A/B/C)
- IVA y retenciones en tabla nativa via TaxResolver
- Tolerancia configurable: absoluta (MXN) y porcentual (%) en Configuracion CFDI Recibidos
- bill_no: serie-folio → folio → uuid[:13]
- Motor de resolución de items + flujo guiado
- Botón "Generar PI" oculto con no_procesar=1
- posting_date y due_date usan issue_date del CFDI
- Bloqueo "Convertido a PI": frm.disable_form() + validate hook + flag in_cfdi_builder
- cost_center y bill_no collision: **eliminados definitivamente del alcance**

### Pendiente
- Batch desde lista (múltiples CFDIs) — criterio de #152 aún abierto
- Deuda técnica is_submittable → issue #165

### No repetir
- No proponer commits sin que el usuario lo solicite
- No incluir one_offs/ ni REPORTE_*.md en commits
- No hacer bench migrate sin autorización
- No reiniciar servidor sin autorización
- No usar ignore_default_payment_terms_template=1
- **No volver a incluir cost_center ni bill_no collision en pendientes de #152**

---

## Decisiones vigentes
- Tolerancia: abs=1.00 MXN y pct=0.5% en Configuracion CFDI Recibidos por empresa
- Aceptable si cumple cualquiera: diff ≤ tol_abs OR diff ≤ total_xml × (tol_pct/100)
- tol_pct=0 desactiva la tolerancia porcentual
- posting_date = issue_date del CFDI (no today())
- due_date = issue_date del CFDI (explícito, evita type mismatch con Payment Terms)
- Bloqueo "Convertido a PI" es temporal — issue #165 registra la deuda (is_submittable)
- frappe.flags.in_cfdi_builder como bypass del validate lock para saves internos
- TaxResolver lee de `Configuracion CFDI Recibidos`, no de `Configuracion Fiscal Mexico`

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/cfdi_recibidos/services/purchase_invoice_builder.py`
- `facturacion_mexico/cfdi_recibidos/doctype/configuracion_cfdi_recibidos/configuracion_cfdi_recibidos.json`

### Probablemente editar
- Ninguno inmediato — pendiente decisión sobre batch

### No tocar
- `facturacion_mexico/one_offs/` — nunca commitear
- `docs/development/REPORTE_*.md` — no commitear

---

## Riesgos / cuidados
- `bench migrate` pendiente en `facturacion-v16.dev` para activar columnas de tolerancia en dev
- Batch no implementado — criterio de aceptación del issue #152 aún abierto
- 30 commits adelante de upstream/main sin push ni PR
- issue #165 (is_submittable) debe hacerse antes de producción
