# ADR 0017 — Complemento Pago MX MVP

**Fecha:** 2026-05-05 | **Última revisión:** 2026-05-06 | **Estado:** APROBADO — MVP funcional en sandbox

---

## Arquitectura

```
Payment Entry (operativo)          Complemento Pago MX (fiscal)
─────────────────────────         ─────────────────────────────
fm_complemento_pago  ────────────→ name
fm_require_complement (flag)       payment_entry ←────────────
fm_complement_generated (flag)     complement_status
mode_of_payment                    forma_pago_p ([:2] del mode_of_payment)
                                   documentos_relacionados (child)
                                   detalles_impuestos (child)
```

---

## Decisiones clave

1. **Creación manual** desde botón en PE — no automática al submit
2. **PE no puede cancelarse** si complemento no está Cancelado (`before_cancel` hook)
3. **Vínculo PE↔Complemento se conserva** post-cancelación (trazabilidad)
4. **`mode_of_payment`** de ERPNext es la fuente de la forma de pago SAT (no campo custom)
5. **`fm_tax_regime`** del Customer es la fuente del régimen fiscal SAT (no `tax_category` de ERPNext)

---

## Campos en Complemento Pago MX

Campos agregados (2026-05-05):
- `payment_entry` — Link → Payment Entry
- `company` — Link → Company
- `customer` — Link → Customer
- `complement_status` — Select: Pendiente / Timbrado / Pendiente Cancelación / Cancelado / Error
- `facturapi_id` — ID interno FacturAPI (para cancelación)

---

## Flujo completo

```
1. Submit PE con SI PPD → botón "Crear Complemento de Pago" aparece
2. Click → crear_complemento_pago_desde_pe() → Complemento Pendiente
3. Complemento llena: cabecera + documentos_relacionados + detalles_impuestos
4. Click "Timbrar" → timbrar_complemento_pago() → llama FacturAPI
5. FacturAPI responde → UUID guardado → complement_status = Timbrado
6. PE.fm_complemento_pago queda ligado
7. Cancelación: cancelar_complemento_pago() → PAC → Cancelado/Pendiente Cancelación
8. Si Cancelado → PE puede cancelarse
```

---

## Payload FacturAPI (confirmado vs legacy facturacion_mx)

```python
{
  "type": "P",
  "customer": { legal_name, tax_id, tax_system, email, address.zip },
  "complements": [{
    "type": "pago",
    "data": [{
      "payment_form": mode_of_payment[:2],   # "03" etc.
      "currency": "MXN",
      "exchange": 1,
      "date": posting_date,
      "related_documents": [{
        "uuid": FFM.fm_uuid,
        "folio_number": FFM.folio,
        "amount": imp_pagado,
        "last_balance": imp_saldo_ant,        # allocated + outstanding
        "installment": num_parcialidad,
        "taxability": objeto_imp_dr,
        "taxes": [{ base, type, rate, factor, withholding }]
      }]
    }]
  }]
}
```

---

## Response Log

`FacturAPI Response Log` actualizado:
- Campo `complemento_pago_mx` — Link → Complemento Pago MX
- `operation_type` opciones: `Timbrado Complemento Pago`, `Cancelación Complemento Pago`

---

## Prueba sandbox (2026-05-05/06)

- Complemento creado, timbrado y cancelado contra FacturAPI sandbox ✅
- UUID guardado en `uuid_sat` y `folio_fiscal` ✅
- PE bloqueado mientras complemento activo ✅
- PE desbloqueado al cancelar complemento ✅

---

## Gaps pendientes (Bloque 3D+)

- `documentos_relacionados` y `detalles_impuestos` usan esquema legacy — pendiente alinear con esquema actual
- Campos custom `fm_forma_pago_sat` en PE — innecesarios, pendiente eliminar del fixture
- Download PDF/XML post-timbrado — no implementado
- Cancelación con motivo 01 (sustitución) — no implementado

---

## Nota incidente (2026-05-06)

Recuperación exitosa del flujo SI→FFM→Complemento→Timbrado tras incidente de bisect manual.
Timezone del site corregido (Asia/Kolkata → America/Mexico_City) para resolver errores de fechas.
Branch `_Test Branch` creado en `_Test Company` y mapeado a `Main - _TC` para activar automated_tax.
