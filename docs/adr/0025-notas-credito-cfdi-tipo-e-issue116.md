# ADR 0025 — Notas de Crédito CFDI tipo E (Issue #116)

**Fecha:** 2026-05-13
**Estado:** Implementado — pendientes normativos documentados (#136, #137)
**Autor:** Luis Montanaro / Claude Sonnet 4.6

---

## Contexto

Issue #116 requería implementar el flujo completo de emisión de Notas de Crédito
(CFDI tipo E — Egreso) desde ERPNext. El único camino actualmente soportado es desde
una Sales Invoice de devolución (`is_return=True`), que representa devolución física
de mercancía.

---

## Decisión

Implementar el flujo mínimo necesario para que las notas de crédito timbren
correctamente como CFDI tipo E, partiendo de la infraestructura existente en
`Factura Fiscal Mexico` (mismo DocType que tipo I).

**Nota:** El uso del mismo DocType introduce complejidad. Se ha documentado como
deuda técnica (Issue #135 — refactor FFM JS) y la complejidad creció durante esta
implementación. Se recomienda evaluar DocType separado para tipo E en versiones futuras.

---

## Cambios implementados

### 1. UUID relacionado obligatorio

Guard bloqueante en `_prepare_facturapi_data()` antes de enviar a FacturAPI:

```python
if invoice_data.get("type") == "E" and not uuid_relacionado:
    frappe.throw("No se puede timbrar la Nota de Crédito: falta el UUID del CFDI origen relacionado.")
```

`related_documents` se garantiza siempre — no se omite silenciosamente.

### 2. Resolución automática de UUID origen — `_find_uuid_cfdi_origen()`

Dos rutas:
1. `Sales Invoice.fm_factura_fiscal_mx` → `Factura Fiscal Mexico.fm_uuid` (ruta rápida)
2. Query directa en `Factura Fiscal Mexico` por `sales_invoice=return_against` y `status=TIMBRADO` (fallback)

### 3. TipoRelación 03 para devoluciones físicas

Toda nota de crédito generada desde Sales Invoice `is_return=True` usa `TipoRelación = 03`
(Devolución de mercancía sobre facturas o traslados previos).

TipoRelación 01 (descuentos, bonificaciones) es un flujo distinto — Issue #137.

### 4. FormaPago automática — `_auto_populate_forma_pago_tipo_e()` *(provisional)*

Fuente única de verdad para FormaPago en tipo E, basada en `outstanding_amount` de la SI origen:

```python
if nota_total <= outstanding_origen:   # factura no pagada
    forma_pago = "15 - Condonación"
elif outstanding_origen == 0:          # factura pagada
    forma_pago = hereda de FFM origen  # proxy; pendiente Issue #136
else:                                  # caso mixto
    forma_pago = "15 - Condonación"   # safe default
```

**Provisional:** el caso `outstanding=0` puede representar "saldo a favor" (sin reembolso real)
o reembolso efectivo. La distinción requiere validación con despacho contable. Ver Issue #136.

### 5. Herencia de campos fiscales desde FFM origen — `_get_origin_ffm()`

- `fm_facturar_venta_mostrador` heredado del origen — sin override manual
- `fm_payment_method_sat` del origen usado para determinar FormaPago

### 6. Campos fiscales read-only en tipo E — `_lock_egreso_fields()`

JS bloquea en cada refresh:
`sales_invoice`, `company`, `fm_payment_method_sat`, `fm_forma_pago_timbrado`,
`fm_facturar_venta_mostrador`, `fm_tipo_relacion_sat`, `fm_uuid_relacionado`.

El operador no puede customizar datos fiscales en una nota de crédito.

### 7. Sin addenda en tipo E

`AddendaService.render()` se salta para CFDI tipo E. La propagación de addenda
también se excluye para Sales Invoice `is_return=True`.

### 8. Montos absolutos en validación de discrepancias

`_validate_amount_discrepancies()` usa `abs()` en totales ERPNext para manejar
las cantidades negativas propias de las SIs de devolución.

---

## Validación realizada

| Caso | Origen MetodoPago | outstanding origen | FormaPago resultante | TipoRelación | Timbrado |
|---|---|---|---|---|---|
| FFMX-2026-00025 | PPD / no pagada | > 0 | 15 - Condonación | 03 | ✅ sandbox |
| FFMX-2026-00027 | PPD / no pagada | > 0 | 15 - Condonación | 03 | ✅ sandbox |
| FFMX-2026-00028 | PPD / no pagada | > 0 | 15 - Condonación | 03 | ✅ sandbox |
| FFMX-2026-00003 | PPD / pagada con complemento | 0 | **99 - Por definir** ⚠️ | 03 | ✅ sandbox |

**Nota FFMX-2026-00003 (2026-05-17):** La factura origen (ACC-SINV-2026-02362) era PPD y fue
liquidada con un complemento de pago. Al momento de crear la nota de crédito, `outstanding=0`.
El sistema heredó `FormaPago=99` de la FFM origen (que era PPD → siempre "99"). FacturAPI
timbró sin rechazo. La validez normativa de `MetodoPago=PUE + FormaPago=99` en tipo E está
pendiente de confirmación contable — ver Issue #136.

---

## Matriz de escenarios FormaPago — todos los casos identificados

| # | Origen MetodoPago | outstanding origen | nota_total vs outstanding | FormaPago actual | ¿Validado? | Pendiente |
|---|---|---|---|---|---|---|
| A | PUE | 0 (pagada) | cualquiera | Hereda forma origen (ej. "03") | ⚠️ No probado | Confirmar si herencia es correcta |
| B | PPD | > 0 (no pagada) | nota ≤ outstanding | 15 - Condonación | ✅ Timbrado | Confirmar con contador |
| C | PPD | > 0 (no pagada) | nota > outstanding (mixto) | 15 - Condonación (safe default) | ⚠️ No probado | Política de negocio |
| D | PPD | 0 (pagada con complemento) | cualquiera | **99 - Por definir** (hereda FFM origen) | ✅ Timbró pero ⚠️ normativa | **Issue #136 — consulta contable urgente** |
| E | Descuento / bonificación | N/A | N/A | Sin flujo implementado | ❌ No existe | Issue #137 — TipoRelación 01 |

**Escenario D es el más crítico:** `MetodoPago=PUE + FormaPago=99` puede ser inválido ante el SAT
según la guía de llenado CFDI 4.0 (FormaPago=99 solo permitido con PPD). FacturAPI no lo rechazó
pero eso no garantiza validez ante SAT en auditoría.

---

## Pendientes normativos — NO declarar el flujo como cerrado

### Issue #136 — Validación normativa completa tipo E

- **FormaPago cuando outstanding=0:** ¿"saldo a favor" usa 15 o la forma real del reembolso?
  Pendiente validación con despacho contable.
- **Pagos parciales mezclados:** nota que excede outstanding parcialmente — requiere
  política de negocio explícita.
- **Addenda en tipo E por cliente:** actualmente excluida globalmente. ¿Algunos clientes
  (Liverpool, Walmart) la requieren?

### Issue #137 — Flujo TipoRelación 01

Descuentos, bonificaciones y ajustes comerciales sin devolución física → TipoRelación 01.
No existe flujo en ERPNext para este caso actualmente.

---

## Deuda técnica

- El FFM fue diseñado para tipo I. Tipo E se implementó como excepción en múltiples
  puntos del código (guards dispersos en JS, Python y validaciones). Un DocType
  separado para notas de crédito sería más limpio. Issue #135.
- `_auto_populate_forma_pago_tipo_e()` es provisional hasta resolver Issue #136.
- Los guards JS en `_lock_egreso_fields()` son necesarios porque otras funciones
  del refresh sobreescriben los `read_only`. Síntoma del diseño acumulativo del FFM.

---

## Consecuencias

- Notas de crédito por devolución física timbran correctamente como CFDI tipo E
- UUID relacionado y `related_documents` garantizados normativamente
- FormaPago determinada automáticamente (regla provisional)
- Campos fiscales inmutables en tipo E desde UI
- Issue #116 cerrado funcionalmente — pendientes normativos en #136 y #137

---

## Referencias

- Issue #116 — feat(tipo-e): Notas de crédito CFDI tipo E
- Issue #136 — validación normativa SAT pendiente para CFDI tipo E
- Issue #137 — flujo nota de crédito TipoRelación 01
- Issue #135 — refactor FFM JS
- ADR 0024 — addendas pre-timbrado (contexto del FFM)
- `docs/development/REPORTE_NORMATIVA_NOTA_CREDITO_PENDIENTES.md`
