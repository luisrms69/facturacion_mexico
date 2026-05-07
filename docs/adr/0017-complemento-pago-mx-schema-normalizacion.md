# ADR 0017 — Complemento Pago MX MVP

**Fecha:** 2026-05-05 | **Última revisión:** 2026-05-06 | **Estado:** APROBADO — MVP validado en sandbox (PR #94)

---

## Arquitectura

```
Payment Entry (operativo)              Complemento Pago MX (fiscal CFDI tipo P)
─────────────────────────             ─────────────────────────────────────────
fm_complemento_pago  ──────────────→  name
fm_require_complement (flag)          payment_entry ←──────────────────────────
fm_complement_generated (flag)        status (Pendiente/Timbrado/Cancelado/...)
mode_of_payment                       forma_pago_p (mode_of_payment[:2])
                                      documentos_relacionados (child)
                                      detalles_impuestos (child)
                                      fm_ultimo_response_log → FacturAPI Response Log
```

---

## Decisiones clave

1. **Creación manual** desde botón en PE — no automática al submit
2. **PE no puede cancelarse** si `complemento.status != "Cancelado"` (`before_cancel` hook)
3. **PE se libera** (`fm_complemento_pago=""`) cuando cancelación SAT es `accepted`
4. **`mode_of_payment`** de ERPNext es la fuente de la forma de pago SAT (no campo custom)
5. **`fm_tax_regime`** del Customer es la fuente del régimen fiscal SAT (no `tax_category`)
6. **`status`** (no `complement_status`) — alineado con convención nativa Frappe (`status_field`)

---

## Campo `status` y relación con `docstatus`

| docstatus | status | Significado |
|---|---|---|
| 0 | Pendiente | Complemento creado, aún no timbrado |
| 1 | Timbrado | CFDI de pago timbrado y vigente ante SAT |
| 1 | Pendiente Cancelación | Cancelación solicitada, PAC no ha confirmado |
| 1 | Error | Error en operación PAC |
| 2 | Cancelado | CFDI cancelado fiscalmente — cancelación SAT `accepted` |

`docstatus=2` solo ocurre cuando la cancelación SAT es `accepted`. No se usa `docstatus=2` para otros estados.

---

## Flujo completo

```
1. Submit PE con SI PPD timbrada
   → botón "Crear Complemento de Pago" aparece en PE

2. Click → crear_complemento_pago_desde_pe()
   → Complemento creado (docstatus=0, status=Pendiente)
   → documentos_relacionados y detalles_impuestos llenados
   → PE.fm_complemento_pago vinculado

3. Click "Timbrar Complemento de Pago" (docstatus=0, status=Pendiente/Error)
   → timbrar_complemento_pago()
   → llama FacturAPI con payload tipo P
   → guarda campos stamp (uuid_sat, folio_fiscal, no_certificado_sat, ...)
   → doc.submit() → docstatus=1
   → status=Timbrado
   → Response Log: Timbrado Complemento Pago

4. PE bloqueado (before_cancel lanza error si status != Cancelado)
   → botón Cancel del PE oculto en JS
   → advertencia visible en dashboard del PE

5. Click "Cancelar Complemento" (solo Manager/System Manager)
   → cancelar_complemento_pago(motivo)
   → llama FacturAPI

   Respuesta accepted:
     → status=Cancelado, estatus_sat=Cancelado
     → PE liberado (fm_complemento_pago="", fm_complement_generated=0)
     → doc.cancel() → docstatus=2
     → Response Log: Cancelación Complemento Pago

   Respuesta pending:
     → status=Pendiente Cancelación
     → docstatus=1 (sin cambio)
     → PE sigue bloqueado
     → Response Log: Cancelación Complemento Pago
     → botón "Revisar Estatus Cancelación" aparece

   Respuesta rejected:
     → status=Timbrado (vuelve a estado previo)
     → docstatus=1
     → Response Log: Cancelación Complemento Pago

6. Click "Revisar Estatus Cancelación" (status=Pendiente Cancelación)
   → revisar_estatus_cancelacion_complemento()
   → consulta FacturAPI con facturapi_id
   → aplica mismas transiciones (accepted/pending/rejected)
   → Response Log: Consulta Estado Complemento Pago
```

---

## Payload FacturAPI (confirmado vs legacy facturacion_mx)

```python
{
  "type": "P",
  "customer": { "legal_name", "tax_id", "tax_system", "email", "address": {"zip"} },
  "complements": [{
    "type": "pago",
    "data": [{
      "payment_form": mode_of_payment[:2],
      "currency": "MXN",
      "exchange": 1.0,
      "date": posting_date,
      "related_documents": [{
        "uuid": FFM.fm_uuid,
        "folio_number": FFM.folio,
        "amount": imp_pagado,
        "last_balance": imp_saldo_ant,       # allocated + outstanding
        "installment": num_parcialidad,       # por pe.creation ASC (no pe.name)
        "taxability": objeto_imp_dr,
        "taxes": [{ "base", "type", "rate", "factor", "withholding" }]
      }]
    }]
  }]
}
```

---

## Response Log

`FacturAPI Response Log` — DocType compartido con FFM:
- Campo `complemento_pago_mx` — Link → Complemento Pago MX
- `operation_type`:
  - `Timbrado Complemento Pago`
  - `Cancelación Complemento Pago`
  - `Consulta Estado Complemento Pago`
- `request_id` con hash aleatorio (unique constraint)
- `fm_ultimo_response_log` en el Complemento — Link al último log

---

## DocType Complemento Pago MX — estado final

- `status_field: "status"` — Frappe colorea encabezado con `states[]` automáticamente
- `states[]`: Pendiente→Gray, Timbrado→Green, Pendiente Cancelación→Orange, Cancelado→Red, Error→Red
- Botones Submit/Cancel/Amend de Frappe ocultos en JS
- Botón "Cancelar Complemento" restringido a Manager/System Manager por `frappe.user.has_role()`
- Secciones: Cabecera Operativa / Datos SAT / Bancarios (colapsable) / Documentos / Impuestos
- `before_cancel` permite cancel programático con `flags.allow_fiscal_cancel = True`

---

## Limpieza realizada

- `Payment Tracking MX` eliminado — 0 registros, cubierto nativamente por ERPNext
- `fm_forma_pago_sat` eliminado de Payment Entry — sin uso en código
- `complement_status` renombrado a `status` — convención nativa Frappe
- `num_parcialidad`: desempate por `pe.creation` (no `pe.name`) para mismo día

---

## Validación sandbox (2026-05-06)

- Workflow completo: SI PPD → FFM → PE → Complemento timbrado → cancelado ✅
- accepted: docstatus=2, PE liberado, Response Log ✅
- pending → Revisar Estatus → aceptado: transición correcta, Response Log ✅

---

## Gaps pendientes

| Gap | Prioridad |
|---|---|
| Encabezado muestra "Cancelled" (inglés) cuando docstatus=2 — Frappe ignora `states` para docstatus=2 | Media |
| Motivo 01/sustitución no implementado | Baja |
| PDF/XML download post-timbrado no implementado | Media |
| FFM no migrada a `status` — evaluará en branch separado | Baja |
| Revisión de patches antes de release | Alta |
