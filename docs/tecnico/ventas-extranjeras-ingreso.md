# Ventas extranjeras — cuenta de ingreso

Enruta el `income_account` de una `Sales Invoice` a una cuenta de ingreso de exportación
cuando el receptor es **extranjero**, conservando la resolución nativa de ERPNext para
ventas nacionales. Aplica por igual al flujo normal de operación y al importador
`cfdi_emitidos`, sin lógica contable paralela.

## Configuración requerida

Un único campo nuevo, por empresa, en **Configuracion Fiscal Mexico**:

- `cuenta_ingreso_venta_extranjera` (Link → Account).

Validación al guardar la configuración: la cuenta debe ser de la **misma empresa**,
`root_type = Income`, **no** ser grupo y estar **habilitada**. El campo es opcional a
nivel de configuración; el bloqueo ocurre al enviar una venta extranjera (ver *fail-closed*).

No se usa nombre ni número de cuenta hardcodeado: la cuenta sale del Chart of Accounts real.

## Clasificación territorial

Resultado: `NACIONAL`, `EXTRANJERA` o `INDETERMINADO`. Solo señales **fuertes**,
nativas y auditables (prioridad):

1. Evidencia del CFDI histórico si está presente en `doc.flags.fm_cfdi_territorial`
   (transitoria, sin schema persistente) — autoritativa para `cfdi_emitidos`.
2. `Customer.tax_id == XEXX010101000` (RFC genérico de residentes en el extranjero).
3. País de la dirección (`Sales Invoice.customer_address` → dirección primaria del
   Customer) comparado contra `Company.country` (≠ → EXTRANJERA; == → NACIONAL).
4. Sin evidencia suficiente → `INDETERMINADO`.

**`Customer.territory` NO es fuente de clasificación:** `Rest Of The World` es un
catch-all estándar de ERPNext y clasificar por él generaría falsos positivos que
bloquearían/redirigirían ventas nacionales existentes. Tampoco se usa Customer Group,
currency, `fm_tax_regime` ni Tax Category.

## Comportamiento contable

| Clasificación | `income_account` |
|---|---|
| `NACIONAL` | Resolución nativa ERPNext (Item → Item Group → Brand → Company) |
| `EXTRANJERA` | `cuenta_ingreso_venta_extranjera` configurada |
| `INDETERMINADO` | Resolución nativa ERPNext (no se infiere extranjero) |

La **CxC** (`debit_to`) siempre se resuelve con **Party Account nativo**; este bloque no
la toca.

**Precedencia por línea:** `cuenta_descuentos` > routing extranjero > resolución nativa.
Una nota de crédito por descuento marca sus líneas con `income_account = cuenta_descuentos`
(ver `facturacion_fiscal.utils`); esas líneas se preservan y no se reemplazan por la cuenta
extranjera. Si todas las líneas son de descuento, no hay routing ni fail-closed.

## Two-phase (anti-contaminación de Item Default)

`SellingController.validate` persiste en el `Item Default` cualquier `income_account` de
línea distinto al default de la empresa. Para evitarlo:

- **Fase 1** (`before_validate`, antes del controller): blanquea `income_account` de las
  líneas extranjeras (excepto descuento) → el controller resuelve nativo sin contaminar.
- **Fase 2** (`validate`, después del controller): reaplica la cuenta extranjera a las
  líneas correspondientes.

Verificado en Draft, Save, Reload+Save y Submit: el `Item Default` permanece intacto.

## Fail-closed

Si la operación es **inequívocamente `EXTRANJERA`** y la cuenta configurada falta o es
inválida, el **Submit se bloquea** con un mensaje claro. El Draft sí puede existir.
`INDETERMINADO` **no** se bloquea (conserva resolución nativa).

## cfdi_emitidos

El importador **no** selecciona `income_account`. Solo inyecta la evidencia del XML en
`doc.flags.fm_cfdi_territorial` y reutiliza exactamente el mismo `ruteo_ingreso` que una
Sales Invoice normal. El XML histórico prevalece sobre datos maestros actuales que lo
contradigan.

## Pendientes conocidos (no bloqueantes)

1. **E2E de NC extranjera por descuento**: ejecutar la prueba end-to-end completa en un
   sitio con `Facturacion Mexico Company Settings` real y `cuenta_descuentos` configurada
   (validado por unit/integration y prueba funcional con sustitución controlada del resolver).
2. **Tratamiento fiscal de ventas extranjeras** (bloque separado): IVA / tasa 0 / no objeto
   según operación, `ObjetoImp` contextual, CFDI `Exportacion`, `ResidenciaFiscal` /
   `NumRegIdTrib` e interacción STCT/ITT. Este bloque cubre **solo** el `income_account`.
