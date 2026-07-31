# ADR 0025 — Notas de Crédito CFDI tipo E (Issue #116)

**Fecha:** 2026-05-13
**Estado:** Implementado — #137 implementado (2026-07-29); #136 resuelto para descuento con pago previo
**Autor:** Luis Montanaro / Claude Sonnet 4.6

> **Actualización 2026-07-29:** Ver sección *«Descuento / Bonificación (TipoRelación 01)»*.
> Se implementó el flujo de nota de crédito por descuento (Issue #137) y se cerró el criterio de
> FormaPago del escenario de descuento con pago previo (Issue #136).
>
> **Actualización 2026-07-30:** Ver sección *«Robustez operativa descuento ⇄ devolución en SI
> Return»*: inventario, guard de Discount Accounting y reversión determinista (puntos 1–3). Los
> puntos 4–5 (FFM: `fm_tipo_nota_credito` derivado, visibilidad/textos) quedan para rama/PR aparte.

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

## Descuento / Bonificación (TipoRelación 01) — Issue #137 (2026-07-29)

Se implementa el segundo motivo de nota de crédito, distinto de la devolución física.
La distinción entre ambos casos queda **explícita** y sin habilitar edición libre de campos SAT.

### Distinción final por intención de negocio

| Motivo (negocio) | TipoRelación | UsoCFDI | MetodoPago | FormaPago | Concepto |
|---|---|---|---|---|---|
| **Devolución de mercancía** | `03` | (default cliente) | PUE | según outstanding origen | descripción del ítem |
| **Descuento / Bonificación** | `01` | `G02` | PUE | `15 - Condonación` | `Descuento - <descripción origen>` |

### Arquitectura (Opción X — señal por la cuenta contable)

El motivo de la nota se **decide antes del Submit** mediante la cuenta contable nativa, y la FFM lo
**deriva y valida** después — sin adelantar el ciclo de vida de la FFM ni tocar Sales Invoice.

- **Config por empresa:** `Facturacion Mexico Company Settings.cuenta_descuentos` (Link a *Account*).
  Para este cliente se configura `501-005 - Descuentos y bonificaciones`. **No** se hardcodea.
- **Restricción nativa de ERPNext (decisiva):** en una Sales Invoice Return con `return_against`,
  ERPNext valida (core `validate_returned_items`) que el `item_code` de cada línea exista en la factura
  origen. Por eso **NO se sustituye el Item** por uno `Descuento` (rompería esa validación) y **no se
  desactiva ni sobreescribe** ninguna validación core. Se **conserva el Item original**.
- **El descuento se expresa por descripción + cuenta:** la acción, server-side, en cada línea fija
  `description = "Descuento - <descripción original>"` (idempotente; sin partida identificable →
  `Descuento`) y `income_account = cuenta_descuentos`. Conserva `item_code`, cantidad, precio, UOM e
  impuestos. **No** hay Item maestro `Descuento`, ni clave técnica, ni campos nuevos en `Sales Invoice`.
- **ClaveProdServ del CFDI = la del Item/línea original:** al conservarse el `item_code`, el payload
  obtiene la ClaveProdServ normalmente de `Item.fm_producto_servicio_sat` de la mercancía. Con una línea
  por partida (estructura nativa del Return), distintas ClaveProdServ / tasas / exentos / IEPS quedan en
  líneas separadas (no se colapsan).
- **Acción de negocio (UX):** en la Credit Note en borrador (`is_return=1`, `docstatus=0`,
  `return_against`) el operador ejecuta el botón **«Aplicar como Descuento / Bonificación»**
  (`facturacion_mexico.facturacion_fiscal.api.nota_credito.aplicar_como_descuento`). Server-side aplica
  lo anterior y guarda; el documento muestra ya `Descuento - <origen>` antes del Submit. Guards del
  servidor: es Return, en borrador, `return_against` presente, cuenta de descuentos configurada. El
  operador **no** selecciona Item, cuenta ni códigos SAT. Si **no** ejecuta la acción, la nota conserva
  sus cuentas normales → devolución física (relación 03).
- **Al crearse la FFM** (mismo `on_submit` de siempre): `_detect_nota_credito_motivo()` detecta si
  **todas** las líneas están contabilizadas contra `cuenta_descuentos` y, de ser así, **preselecciona**
  `fm_tipo_nota_credito = Descuento / Bonificación` (solo si el campo está vacío). La señal es la
  **cuenta contable**, no el `item_code`. Si no coinciden, no infiere → devolución física (`03`).
- Nuevo campo **en la propia FFM** (no Custom Field en Sales Invoice): `fm_tipo_nota_credito` (Select:
  *Devolución de mercancía* / *Descuento / Bonificación*), visible en CFDI tipo E para que el usuario
  **verifique** la clasificación antes del timbrado; editable en borrador, bloqueado tras submit.
- Al quedar *Descuento / Bonificación*, `_set_tipo_from_context()` deriva automáticamente
  `E / 01 / G02 / PUE / 15 - Condonación`. El UUID relacionado se resuelve como hasta ahora desde
  `return_against` → FFM origen → `fm_uuid` (exclusivo de la factura origen).
- El concepto fiscal en el payload es `Descuento - <origen>` (`resolve_concepto_description`,
  idempotente), **conservando** el Item original, su ClaveProdServ SAT y los impuestos proporcionales.
- **Guard pre-timbrado (`_validate_invoice_for_timbrado`):** si la FFM está marcada como
  *Descuento / Bonificación*, se exige que las líneas estén contabilizadas contra `cuenta_descuentos`;
  si no coinciden (o la cuenta no está configurada), se **bloquea el timbrado** con mensaje claro. El GL
  **no** se corrige después del Submit: si es necesario, cancelar y rehacer la nota.

### FormaPago 15 — decisión final del contador (Issue #136)

`FormaPago = 15 - Condonación` con `MetodoPago = PUE` es el criterio **confirmado por el contador**
para este escenario, **incluso cuando el 90% ya fue recibido previamente por transferencia**: el CFDI
de Egreso documenta **exclusivamente la extinción del 10% que nunca será cobrado**. El 90%
efectivamente recibido se documenta después en el **REP** con `FormaPago = 03 - Transferencia
electrónica de fondos` y la fecha real de recepción bancaria. `15` ya **no** es un supuesto
provisional para este caso.

### Aplicación contable / outstanding

- **Se descarta** modificar `update_outstanding_for_self = 0` automáticamente. Se mantiene el
  comportamiento nativo: crear/submit de la NC → timbrar → **conciliar** la NC contra la factura
  origen con el flujo nativo (Payment Reconciliation / Journal Entry) → registrar el Payment Entry →
  generar el REP. La conciliación posterior es un paso operativo aceptado.
- El REP debe generarse **después** de que la conciliación haya reducido el outstanding de la factura.
- Cuenta de descuentos (p. ej. `501-005 Descuentos y bonificaciones`): se configura por empresa en
  `Facturacion Mexico Company Settings.cuenta_descuentos` y se aplica vía `income_account` de las líneas
  de la Credit Note (mecanismo nativo). **No** se hardcodea la cuenta ni se crea un Item genérico
  "Descuento". Flujo completo: NC nativa → cuenta correcta antes del Submit → FFM deriva/valida la
  intención → timbrado → conciliación → Payment Entry → REP.

### REP

Sin cambios: `proporcion = allocated_amount / si.grand_total` (grand_total **original** del CFDI). El
importe de la Nota de Crédito **no** se trata como efectivo en el REP. Se descarta el gap G-4.

### Enable Discount Accounting — precondición operativa por sitio (no regla universal)

**Precondición operativa para empresas/sitios que usen este flujo de descuento:**
**`Selling Settings.Enable Discount Accounting = OFF`** en la empresa.

- Con `ON`, ERPNext exige `discount_account` por línea cuando `discount_amount > 0`, y su
  `make_discount_gl_entries` postea `discount_amount × qty` a `discount_account`. En una **nota de
  crédito** (qty negativa) esto **invierte e infla** el asiento (la cuenta de descuento queda
  *acreditada* por el hueco completo contra el precio de lista, no por el descuento real), rompiendo
  el GL. Verificado empíricamente: una NC de −20.41 (divisa) generaba un asiento ~17× mayor con la
  cuenta de descuento acreditada por el ~90% del precio de lista.
- Con `OFF`, la NC contabiliza correctamente: `income_account` (cuenta de descuentos) **debitado** por
  la base real, IVA revertido proporcionalmente, Clientes acreditado por el total. La venta normal no
  se altera y el CFDI/XML tampoco (el payload usa `net_rate`; nunca emite nodo `Descuento`).
- **No** es una regla universal de `facturacion_mexico`: es una **configuración por empresa** que se
  adopta si se van a operar notas de crédito por descuento. Empresas que **no** usen descuento de línea
  (`rate = price_list_rate` siempre) no pierden funcionalidad al apagarlo.
- Evidencia: experimento end-to-end en un sitio de desarrollo (sandbox) con 4 CFDIs — 2 ventas
  (a precio de lista / 10% abajo) y 2 notas de crédito de descuento (TipoRelación 01), GL y XML
  validados con `Enable Discount Accounting = OFF`.

### Estado de pendientes

- **Issue #137:** implementado (TipoRelación 01 + G02 + concepto `Descuento`).
- **Issue #136:** el escenario de descuento con pago previo queda **resuelto** con `FormaPago 15`. Si
  el issue conserva otros escenarios de FormaPago tipo E (p. ej. escenario D: `outstanding=0` que
  hereda `99`), **permanece abierto** para esos; este caso se marca resuelto.

---

## Robustez operativa descuento ⇄ devolución en SI Return (2026-07-30)

Endurecimiento del flujo tras validación GUI en producción. Los cambios se acotan a la **Sales
Invoice Return en borrador** y a la acción de negocio; **no** se toca la derivación de códigos SAT ni
el timbrado.

### Implementado (puntos 1–3)

1. **Inventario en descuento.** Al «Aplicar como Descuento / Bonificación», la acción fuerza
   `update_stock = 0` (un descuento no es devolución física → no mueve inventario). Es **reversible**:
   el valor correcto de una devolución es `return_against.update_stock`, y la acción inversa lo
   restaura desde el origen (determinista, 0 o 1). Antes la NC podía heredar `update_stock = 1` del
   origen y afectar inventario.

2. **Guard de Enable Discount Accounting.** La conversión a descuento **se bloquea antes de modificar
   la nota** si `Selling Settings.Enable Discount Accounting = ON`, con mensaje claro. **No** se apaga
   el setting global automáticamente (afectaría otros procesos): la precondición documentada arriba
   pasa de "manual" a **protegida por guard** en la acción (`preparar_como_descuento`). El mecanismo
   sigue usando `cuenta_descuentos` como `income_account`; nunca `discount_account`.

3. **Reversión determinista descuento ⇄ devolución (solo SI Return en Draft).**
   - Botón **«Revertir a Devolución de mercancía»**, simétrico a «Aplicar como Descuento».
   - Restaura **exacto desde el origen**: por cada línea usa el vínculo nativo `sales_invoice_item`
     (poblado por `make_return_doc`) para leer su renglón en `return_against` y restaurar
     `income_account` y `description`; restaura `update_stock` desde `return_against.update_stock`.
   - **Fail-closed:** si alguna línea no tiene vínculo con su renglón de origen (o no se encuentra),
     **bloquea sin modificar** la nota y lista las líneas afectadas — no adivina cuentas contables.
   - **Ninguna acción disponible tras el Submit** (ambas exigen `docstatus = 0`).
   - La UX elige qué botón mostrar según el **estado contable real** (`income_account ==
     cuenta_descuentos`), no según la descripción (editable).

**La reversión vive exclusivamente en la SI Return en borrador. La FFM no participa en la reversión.**

### Pendiente — rama/PR independiente (puntos 4–5)

No se implementan en esta rama:

- **`fm_tipo_nota_credito` como dato derivado/no editable en FFM.** Hoy es editable en borrador pero su
  cambio manual no re-deriva de forma simétrica los códigos SAT (la rama devolución conserva valores
  del descuento por el `or` y por no resetear `fm_cfdi_use`/`fm_forma_pago_timbrado`) → «parece
  editable pero no hace nada». Propuesta: derivarlo autoritativamente desde el estado contable y
  volverlo read-only permanente. **No** hay caso legítimo de cambio manual en FFM (la intención se
  decide y revierte en la SI Return).
- **Visibilidad / textos de campos FFM** (`fm_tipo_nota_credito`, `fm_tipo_relacion_sat`,
  `fm_uuid_relacionado`): sin bug de visibilidad activo (solo aparecen en tipo E); pendiente acortar el
  `description` largo de `fm_tipo_nota_credito` (UX) y evaluar gating por existencia real de UUID.
- **UsoCFDI en devolución:** hoy no se fuerza a `G02` (queda al default del cliente); confirmar con el
  contador si debe ser `G02` como en descuento.

### Propuesta futura — bandera explícita en la SI Return como fuente de verdad

Sustituir la **inferencia por cuenta contable** (`income_account == cuenta_descuentos`) por una
**bandera explícita en la Sales Invoice Return** (p. ej. un campo booleano/estado «modo descuento»)
que registre la intención de forma inequívoca. Motivos: (a) evita falsos positivos si una devolución
legítima usara la misma cuenta; (b) define comportamiento claro si unas líneas están en la cuenta de
descuentos y otras no; (c) da a la FFM una fuente de verdad estable en lugar de inferir. **No se
implementa aquí** — queda para la rama/PR de los puntos 4–5.

---

## Referencias

- Issue #116 — feat(tipo-e): Notas de crédito CFDI tipo E
- Issue #136 — validación normativa SAT pendiente para CFDI tipo E
- Issue #137 — flujo nota de crédito TipoRelación 01
- Issue #135 — refactor FFM JS
- ADR 0024 — addendas pre-timbrado (contexto del FFM)
- `docs/development/REPORTE_NORMATIVA_NOTA_CREDITO_PENDIENTES.md`
