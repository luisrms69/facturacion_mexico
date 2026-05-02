# ADR 0010 — VERIFICACIÓN ESTADO POST-CANCELACIÓN
===================================================
Fecha: 2026-05-02
Site: facturacion-v16.dev
Documentos verificados: FFMX-2026-00002 / ACC-SINV-2026-00001

---

## Estado en DB post-cancelación PAC

### Factura Fiscal Mexico — FFMX-2026-00002

| Campo | Valor | Esperado (ADR 0009) | Estado |
|-------|-------|---------------------|--------|
| `fm_fiscal_status` | `CANCELADO` | `CANCELADO` | ✅ |
| `docstatus` | `1` (submitted) | `2` (cancelado Frappe) | ⚠️ Paso pendiente |
| `cancellation_reason` | `02 - Comprobantes emitidos con errores sin relación` | poblado | ✅ |
| `cancellation_date` | `2026-05-02 14:00:02` | poblado | ✅ |

### Sales Invoice — ACC-SINV-2026-00001

| Campo | Valor | Esperado (ADR 0009) | Estado |
|-------|-------|---------------------|--------|
| `fm_fiscal_status` | `CANCELADO` | `CANCELADO` | ✅ |
| `docstatus` | `1` (submitted) | `2` si se completó | ⚠️ Paso pendiente |
| `status` | `Unpaid` | — | Correcto (aún submitted) |
| `fm_factura_fiscal_mx` | `FFMX-2026-00002` | — | ✅ Vínculo intacto |

### FacturAPI Response Log

| Log | operation_type | success | status_code |
|-----|---------------|---------|-------------|
| FAPI-LOG-2026-00003 | Solicitud Cancelación | ✅ 1 | 200 |
| FAPI-LOG-2026-00002 | Timbrado | ✅ 1 | 200 |

---

## Interpretación del estado

El sistema está en el **estado intermedio correcto** del flujo de cancelación de 3 pasos:

```
Paso 1 ✅  Cancelar en PAC     → FFM.fm_fiscal_status = CANCELADO
                                  Response Log HTTP 200 success=1

Paso 2 ⏳  Cancelar FFM Frappe → FFM.docstatus = 2   ← PENDIENTE
Paso 3 ⏳  Cancelar SI         → SI.docstatus = 2    ← PENDIENTE
```

El CFDI está cancelado ante el SAT. Los DocTypes de Frappe aún están en `docstatus=1`
(submitted) — esto es correcto: el sistema no cancela automáticamente los documentos
Frappe tras la cancelación PAC. El usuario debe ejecutar los pasos 2 y 3 manualmente.

### ¿Puede cancelarse la SI ahora?

Sí — según `sales_invoice_cancel_guard.py`:
- La FFM vinculada tiene `fm_fiscal_status = CANCELADO`
- Este estado está en `ALLOWED_FFM_CANCELLED_STATES`
- → `allowed = True`

El botón Cancel en SI debería estar visible. Si el usuario abre la SI ahora,
`refresh` disparará `can_cancel_sales_invoice()` que retornará `allowed: true`.

---

## Contrastación con checklist ADR 0009

### Checklist post-cancelación (ADR 0009)

| Item | Estado actual | Resultado |
|------|--------------|-----------|
| `FFM.fm_fiscal_status = CANCELADO` | ✅ CANCELADO | ✅ |
| `FFM.docstatus = 2` | ❌ docstatus=1 | ⚠️ Pasos 2-3 pendientes |
| `FFM.cancellation_reason` poblado | ✅ "02 - Comprobantes…" | ✅ |
| Response Log Cancelación success=1 | ✅ FAPI-LOG-2026-00003 | ✅ |
| `SI.fm_fiscal_status = CANCELADO` | ✅ CANCELADO | ✅ |
| Botón Cancel en SI: visible | ✅ (guard retorna allowed=true) | ✅ |
| `SI.docstatus = 2` | ❌ docstatus=1 | ⚠️ Paso 3 pendiente |

**5 de 7 ítems correctos.** Los 2 restantes son los pasos de cancelación de DocTypes
Frappe que el usuario debe ejecutar manualmente — no son errores del sistema.

---

## Análisis del mecanismo de refresh/realtime

### Qué sí existe

**FFM form → `handle_cancel_success()` → `frm.reload_doc()`**

Después de una cancelación PAC exitosa desde el formulario FFM:
```javascript
// factura_fiscal_mexico.js:1050
function handle_cancel_success(frm, msg) {
    if (msg && (msg.ok || msg.success)) {
        frappe.show_alert({ message: "✅ Factura cancelada exitosamente" });
        frappe.msgprint({ ... detalle de estado ... });
        frm.reload_doc();   // ← recarga SOLO el formulario FFM
    }
}
```

**SI form → `fm_fiscal_status` field handler → re-evalúa botones**

Si el formulario de SI está abierto y el campo `fm_fiscal_status` cambia en memoria:
```javascript
// si_post_fiscal_actions.js:199
fm_fiscal_status: function (frm) {
    add_post_fiscal_actions(frm);
    add_fiscal_status_indicator(frm);
    hide_native_cancel_conditionally(frm);  // re-evalúa botón Cancel
}
```

**SI form → `refresh` → `can_cancel_sales_invoice()`**

Cada vez que se recarga el formulario SI, `sales_invoice_block_cancel.js`
llama al endpoint y decide si mostrar/ocultar el botón Cancel.

### Qué NO existe — gap identificado

**No hay `frappe.publish_realtime()` en `cancelar_factura()`.**

```python
# timbrado_api.py — cancelar_factura() FASE 3 (líneas ~1183-1260)
frappe.set_value("Factura Fiscal Mexico", ...)
frappe.set_value("Sales Invoice", ...)
frappe.db.commit()
# FIN — sin publish_realtime
return { "ok": True, "status_ffm": fiscal_status, ... }
```

El backend actualiza `fm_fiscal_status` en la SI via `frappe.set_value()`, pero
**no emite ningún evento Frappe realtime** (`frappe.publish_realtime()`, `frappe.publish_doc()`)
que notifique al formulario SI si está abierto en otro tab.

### Consecuencia práctica

| Escenario | ¿El botón Cancel aparece? |
|-----------|--------------------------|
| Usuario inicia cancelación desde FFM y navega manualmente a SI | ✅ Sí — el `refresh` del form lo detecta |
| Usuario tenía SI abierta en otro tab cuando se canceló desde FFM | ❌ No automáticamente — necesita recargar la página |
| Usuario recarga SI manualmente (F5 o navegar) | ✅ Sí — `refresh` dispara `can_cancel_sales_invoice()` |
| FFM form completa cancelación → muestra detalle → `frm.reload_doc()` | ✅ FFM se actualiza; SI no |

### Recomendación (para implementar en el futuro)

Agregar `frappe.publish_realtime()` al final de `cancelar_factura()` éxitosa:

```python
# En timbrado_api.py, después del frappe.db.commit():
frappe.publish_realtime(
    event="fiscal_status_changed",
    message={
        "sales_invoice": sales_invoice_name,
        "fm_fiscal_status": fiscal_status,
        "ffm": factura_fiscal.name,
    },
    doctype="Sales Invoice",
    docname=sales_invoice_name,
)
```

Y en `si_post_fiscal_actions.js` suscribirse a ese evento para refrescar
el formulario SI automáticamente cuando esté abierto.

Esto es una mejora de UX, no un bug bloqueante — la protección del servidor
funciona correctamente independientemente del estado del botón en UI.

---

## Siguiente acción manual requerida

Para completar el flujo de cancelación en Frappe:

```
1. Abrir FFMX-2026-00002 → botón "Cancel" → confirmar
   → FFM.docstatus = 2

2. Abrir ACC-SINV-2026-00001 → botón "Cancel" → confirmar
   → SI.docstatus = 2

Estado final esperado: ambos documentos con docstatus=2, fm_fiscal_status=CANCELADO
```
