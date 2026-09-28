# Importador histórico de REP → Payment Entry (`cfdi_historico_rep`)

Importa CFDI de pago (REP 2.0, tipo `P`) históricos como **Payment Entry nativos** + un
**Complemento Pago MX** por CFDI (representación fiscal), **sin llamar al PAC**.

## Workflow normal (existente, saliente) vs histórico

- **Normal (saliente):** Payment Entry (Receive) → `crear_complemento_pago_desde_pe()` construye el
  Complemento desde el PE + Sales Invoice → `timbrar_complemento_pago()` → FacturAPI/PAC → UUID.
  El `on_submit` del PE **no** genera el complemento automáticamente (creación manual/whitelisted).
- **Histórico (este módulo):** parte del XML del REP ya timbrado; reconstruye el/los Payment Entry y
  registra el Complemento como evidencia fiscal. **Sin PAC.**

## Direcciones

- **EMITIDO** (`emisor == Company`): contraparte = **Customer** (receptor) → Payment Entry **Receive**
  → referencias a **Sales Invoice** (por `fm_folio_fiscal` / FFM `fm_uuid`).
- **RECIBIDO** (`receptor == Company`): contraparte = **Supplier** (emisor) → Payment Entry **Pay** →
  referencias a **Purchase Invoice** (por `fm_cfdi_uuid`).

## Modelo canónico multi-Pago

Un CFDI REP =
- **un solo `Complemento Pago MX`** (un solo `folio_fiscal`/UUID),
- **N filas en la tabla `pagos`** (child `Complemento Pago Detalle Pago MX`) — una por nodo
  `pago20:Pago`, con su fecha, forma, moneda, tipo de cambio, monto, cuentas de cadena de pago y su
  **`payment_entry`**,
- **N Payment Entry** (uno por Pago, creados en orden `FechaPago`),
- documentos relacionados e impuestos **agrupados por `pago_idx`**.

No se colapsan Pagos ni se parte el UUID en varios Complementos.

### Compatibilidad legacy (sin data patch)

- Registros **sin** filas `pagos` (legacy) → los campos escalares del padre se interpretan como un
  **Pago único implícito**.
- Registros **nuevos** → `pagos` es la **fuente de verdad**; los escalares del padre son **espejo del
  primer Pago** (compatibilidad/UI), no la representación canónica.
- `validate_documentos_relacionados` valida el cuadre **por nodo Pago** (agrupando por `pago_idx`)
  cuando hay `pagos`; si no, por escalares.

## Idempotencia

A nivel CFDI, por **`Complemento Pago MX.folio_fiscal`** (`unique`) == UUID real del REP. Si ya existe
→ `EXISTING`, no se recrea.

## Reconciliación fuerte (por `DoctoRelacionado`)

- factura **única** por UUID (0 → `ERROR_DOC_NOT_FOUND`, >1 → ambiguo);
- **contraparte** de la factura coincide con Customer/Supplier del REP;
- `MonedaDR == moneda de la factura`;
- **`ImpSaldoAnt == outstanding real previo`** — si difiere, `ERROR_SALDO_ANT` (falta una parcialidad
  previa; no se esconden pagos faltantes);
- `ImpSaldoInsoluto == ImpSaldoAnt − ImpPagado`;
- `ImpPagado ≤ ImpSaldoAnt`;
- cuadre del pago con **Decimal**: `Monto ≈ Σ(ImpPagado / EquivalenciaDR)`.

### Orden cronológico y parcialidades

Los nodos Pago se procesan por **`FechaPago`** ascendente. Un `outstanding_map` simula la secuencia de
saldos, de modo que la parcialidad N solo pasa si 1..N−1 ya se aplicaron. **No** se exige que todas las
parcialidades estén en el mismo lote: basta que el outstanding real coincida con `ImpSaldoAnt`.

## Monedas — EquivalenciaDR y TipoCambioP

- **`EquivalenciaDR`** (SAT) = unidades de **MonedaDR por 1 de MonedaP** ⇒ `importe_MonedaP =
  ImpPagado / EquivalenciaDR`. Si `MonedaDR == MonedaP` ⇒ 1.
- **`TipoCambioP`** = tipo de cambio de **MonedaP respecto a MXN** (depende solo de MonedaP; `None`
  si MonedaP == MXN). En el flujo saliente Receive = `PE.target_exchange_rate`.
- Soporta MXN/MXN, USD/USD y **MonedaP ≠ MonedaDR** (cruzada) con tasas **derivadas de datos reales**:
  `MonedaP→MXN = EquivalenciaDR × conversion_rate` de la factura (no se inventan tasas). Se exige tasa
  `MonedaP→MXN` uniforme por Pago; si no → `ERROR_MULTIMONEDA_CRUZADA`.
- Distintos nodos Pago del mismo REP pueden tener **monedas/tasas diferentes**; cada uno se procesa
  independiente con su propia cuenta.

## Cuentas explícitas por moneda (fail-closed)

- **Receive** exige `paid_to` explícito; **Pay** exige `paid_from`. Nunca se autoselecciona caja/banco.
- La cuenta debe estar en **MonedaP**. Manifest: cuenta única (`paid_to_account`/`paid_from_account`)
  o **mapa por moneda** (`paid_to_accounts`/`paid_from_accounts`, p. ej. `{"USD": "...", "MXN": "..."}`).
- Si no hay cuenta inequívoca para la MonedaP del Pago → `ERROR_CUENTA`.

## REP vigente vs cancelado

- **Vigente:** N Payment Entry `submit()` (reconstruyen GL + Payment Ledger + outstanding; la
  reclasificación fiscal PPD existente opera normal) + Complemento (`estatus_sat=Vigente`).
- **Cancelado** (señal **explícita** del lote — `cancelled_marker` en el nombre, **no** se infiere del
  XML): Complemento histórico `estatus_sat=Cancelado` que conserva **todos** los Pagos + documentos +
  impuestos, **SIN** Payment Entry (no aplica un pago cancelado).

**Rollback TOTAL** del REP si falla cualquier Pago (no hay importación parcial). Si ERPNext no puede
representar un pago (p. ej. multimoneda que no cuadra), el savepoint revierte → fail-closed.

## Sin PAC / UI

`fm_creation_source` se deja **vacío** (no "Timbrado directo"): la UI (gobernada por `fiscal_state`) no
ofrece cancelación PAC ni descarga/timbrado para un REP no timbrado por el ERP. El botón "Ver Payment
Entry" (payment_entry legacy) solo aparece con ≤1 Pago; con multi-Pago cada PE se ve en la tabla `pagos`.

## Estados

`CREADA_VIGENTE` · `REGISTRADO_CANCELADO` · `EXISTING` · `SKIP_NO_APLICABLE` · `ERROR_PARSE` ·
`ERROR_COMPANY_RFC` · `ERROR_AMBIGUO` · `ERROR_CONTRAPARTE` · `ERROR_DOC_NOT_FOUND` · `ERROR_MONEDA` ·
`ERROR_MULTIMONEDA_CRUZADA` · `ERROR_SALDO_ANT` · `ERROR_SALDO_INSOLUTO` · `ERROR_IMPPAGADO` ·
`ERROR_MONTO` · `ERROR_CATALOGO` · `ERROR_CUENTA` · `ERROR_OTHER`.

## Ejecución

```bash
bench --site <site> execute facturacion_mexico.cfdi_historico_rep.importer.run \
  --kwargs "{'source_dir': '<ruta>', 'manifest': '<manifest.json>', 'dry_run': 1}"
```

## Estado de validación

Cubierto por **tests unitarios** (parser REP 2.0, reconciliación fuerte, EMITIDO/RECIBIDO, multi-Pago
→ N PE + 1 Complemento, monedas cruzadas, rollback total, cancelado multi-Pago, idempotencia). La
construcción cross-currency del Payment Entry usa tasas derivadas y ERPNext como árbitro final; **no**
está validada end-to-end con datos reales todavía.
