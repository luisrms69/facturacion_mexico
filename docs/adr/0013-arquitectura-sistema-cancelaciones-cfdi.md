# ADR 0013 — Arquitectura del Sistema de Cancelaciones CFDI

**Fecha:** 2026-05-04
**Estado:** Implementado
**Autor:** Luis Montanaro Sánchez

---

## Contexto

El SAT define 4 motivos de cancelación para CFDI 4.0. La migración a v16 requirió
verificar y corregir el flujo completo de cancelaciones, incluyendo escenarios que
nunca habían sido probados en producción (motivo 01 con sustitución) y estados
intermedios que no tenían mecanismo de resolución (PENDIENTE_CANCELACION).

Verificaciones realizadas en `facturacion-v16.dev` contra sandbox de FacturAPI.

---

## Los 4 motivos SAT y su implementación

### Motivo 02 — Comprobantes emitidos con errores sin relación

**Cuándo usar:** Error en el CFDI que no tiene un documento sustituto.

**Flujo:**
```
FFM (TIMBRADO) → Cancelar en FacturAPI → botón "Cancelar en FacturAPI" → diálogo motivos
→ usuario selecciona 02 → cancelar_factura(motivo="02") → PAC → CANCELADO
```

**Requiere UUID sustituto:** No.
**Estado final FFM:** CANCELADO. **Estado final SI:** CANCELADO (fm_fiscal_status).
**Verificado:** sesión 2026-05-01.

---

### Motivo 03 — No se llevó a cabo la operación

**Cuándo usar:** La operación comercial no ocurrió.

**Flujo:** idéntico a motivo 02 salvo el código enviado al PAC.

**Requiere UUID sustituto:** No.
**Verificado:** FFMX-2026-00010, 2026-05-04.

---

### Motivo 04 — Operación nominativa relacionada en factura global

**Cuándo usar:** La operación fue incluida en una Factura Global.

**Flujo:** idéntico a motivos 02/03.

**Requiere UUID sustituto:** No.
**Verificado:** FFMX-2026-00011, 2026-05-04.

---

### Motivo 01 — Comprobantes emitidos con errores con relación (sustitución)

**Cuándo usar:** El CFDI tiene errores y será reemplazado por uno nuevo.

**Flujo completo:**
```
SI original (TIMBRADO)
  → botón "🔄 Sustituir CFDI (01)" en "Acciones Fiscales" (si_post_fiscal_actions.js)
  → create_substitution_si(si_name)  [timbrado_api.py]
      → frappe.copy_doc(SI original)
      → limpia campos fiscales (fm_factura_fiscal_mx, fm_fiscal_status)
      → guarda ffm_substitution_source_uuid = UUID del CFDI original
      → inserta SI sustituto como borrador
  → usuario corrige datos en SI borrador
  → usuario timbra SI sustituto
      → al timbrar detecta ffm_substitution_source_uuid
      → inyecta TipoRelación "04" en el CFDI nuevo (relación con UUID original)
      → _cascade_cancel_previous_after_substitute() en background:
          1. Cancelar CFDI original en PAC con motivo "01" (referenciando UUID del nuevo)
          2. Hardening preventivo: limpiar links SI↔FFM antes de cancel()
          3. Restaurar link sales_invoice en FFM original post-cancel (fix v16)
          4. Cancelar SI original (docstatus=2)
          5. Cancelar FFM original (docstatus=2)
```

**Requiere UUID sustituto:** Sí — el UUID del nuevo CFDI.
**Guard backend:** `_guard_motive_01_only_from_substitution()` bloquea si no viene `substitution_uuid`.
**Guard UI:** motivo 01 filtrado del selector de cancelación directa desde FFM.
**Verificado:** FFMX-2026-00012 y FFMX-2026-00014, 2026-05-04.

**Nota UX:** El diálogo de confirmación menciona "TipoRelación 04" (no motivo 01) porque
describe lo que sucede en el CFDI **nuevo**, no el motivo de cancelación del original.
Son conceptos SAT distintos que operan en paralelo en el mismo flujo.

---

## Estado PENDIENTE_CANCELACION y su resolución

### Cuándo ocurre

El SAT requiere que ciertos receptores (grandes empresas) acepten explícitamente
la cancelación antes de que surta efecto. FacturAPI devuelve `cancellation_status: "pending"`.

También ocurre como fallback conservador si la respuesta del PAC es inesperada.

### Tres rutas hacia PENDIENTE_CANCELACION

| Origen | Llama PAC |
|---|---|
| PAC responde `cancellation_status: "pending"` | Sí |
| PAC responde con status inesperado (fallback) | Sí |
| Hook SI native cancel (`sales_invoice_cancel.py`) | No — solo setea estado |

### Resolución — botón "Revisar Estatus Cancelación"

Implementado en PR #90 (2026-05-04). Visible solo cuando `fm_fiscal_status = PENDIENTE_CANCELACION`.

**Backend:** `revisar_estatus_cancelacion(ffm_name)` en `timbrado_api.py`:
- `GET /v2/invoices/{facturapi_id}` a FacturAPI
- Lee `cancellation_status` de la respuesta
- Transiciona según respuesta:

| Respuesta PAC | Estado resultante |
|---|---|
| `status: "canceled"` o `cancellation_status: "accepted"` | CANCELADO |
| `cancellation_status: "rejected"` | TIMBRADO (receptor rechazó) |
| `cancellation_status: "pending"` | PENDIENTE_CANCELACION (sin cambio) |

- Registra en `FacturAPI Response Log` con `operation_type: "Consulta Estado"` para trazabilidad

**Recovery Worker:** `process_timeout_recovery()` en `tasks.py` llama `query_pac_status()`
(implementada en `api_client.py`) cada 5 minutos via scheduler. Resuelve cancelaciones
pendientes automáticamente si la función de recuperación lo permite.

---

## Bloqueo de Amend en SI con historial fiscal

**Problema:** Frappe permite "Amend" en cualquier documento cancelado (docstatus=2).
Una SI cancelada como parte de una sustitución CFDI no debe poder ser enmendada —
crearía un documento que bypasea el proceso fiscal.

**Implementación** (`si_post_fiscal_actions.js`):
```javascript
if (frm.doc.docstatus === 2 && frm.doc.fm_fiscal_status === "CANCELADO") {
    frm.perm[0].amend = 0;
    frm.page.clear_primary_action(); // retira botón ya renderizado por Frappe
}
```

**Alcance:** solo SIs con `fm_fiscal_status = "CANCELADO"`. SIs canceladas nativamente
sin CFDI (`fm_fiscal_status` vacío) no se ven afectadas.

La FFM ya tenía doble protección preexistente (Python en `overrides.py` + JS).

---

## Gaps encontrados y resueltos

### Bug: `sales_invoice` vacío en FFM original post-sustitución

**Causa:** El "hardening preventivo" en `_cascade_cancel_previous_after_substitute`
limpiaba `orig_ffm.sales_invoice = ""` antes de llamar `orig_si.cancel()` para evitar
`LinkExistsError`. El link nunca se restauraba.

**Fix:** Después de `orig_si.cancel()`, se restaura:
```python
orig_ffm.db_set("sales_invoice", orig_si_name)
```

### Bug: `query_pac_status` devolvía None en todos los campos

**Causa:** `client.get_invoice()` devuelve un wrapper `{success, status_code, raw_response}`.
`query_pac_status` leía `response.get("status")` del wrapper en lugar de
`response["raw_response"].get("status")`. Todos los campos de la factura devolvían `None`.

**Fix:** Extraer `invoice = wrapper.get("raw_response") or {}` antes de leer campos.

### Bug: comment stale bloqueaba Recovery Worker

**Causa:** `tasks.py` tenía un `except ImportError` que atrapaba el import de
`query_pac_status` y retornaba failure con mensaje "no está implementado aún".
La función SÍ existía en `api_client.py`.

**Fix:** Eliminado el bloque `except ImportError`.

### Bug: Cost Center con `fm_mapped_branch` apuntando a Branch eliminado

**Causa:** El Cost Center `"Main - _TC"` tenía `fm_mapped_branch = "Test Branch Addenda"`.
El hook `before_validate` del SI re-asignaba este valor inválido en cada SI nuevo,
incluyendo los SIs creados por `create_substitution_si`. La limpieza masiva de SIs
no resolvió el problema porque el hook lo re-aplicaba en cada nuevo documento.

**Fix:** `frappe.db.set_value("Cost Center", "Main - _TC", "fm_mapped_branch", None)`

---

## Trazabilidad de operaciones

Todas las operaciones de cancelación y consulta de estado quedan registradas en
`FacturAPI Response Log`:

| operation_type (label) | Cuándo |
|---|---|
| Timbrado | Al crear el CFDI |
| Solicitud Cancelación | Al cancelar con cualquier motivo |
| Consulta Estado | Al usar botón "Revisar Estatus Cancelación" |

---

## Referencias

- PR #90 — implementación completa del sistema de cancelaciones v16
- `facturacion_mexico/facturacion_fiscal/timbrado_api.py` — lógica principal
- `facturacion_mexico/public/js/si_post_fiscal_actions.js` — UI sustitución y bloqueo Amend
- `facturacion_mexico/facturacion_fiscal/doctype/factura_fiscal_mexico/factura_fiscal_mexico.js` — botón Revisar Estatus
- `facturacion_mexico/config/sat_cancellation_motives.py` — enum oficial motivos SAT
