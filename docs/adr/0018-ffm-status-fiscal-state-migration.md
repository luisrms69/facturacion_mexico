# ADR 0018 — Migración de estado fiscal FFM a status

**Fecha:** 2026-05-07 | **Estado:** APROBADO — Etapa 1 implementada

---

## Contexto

Factura Fiscal Mexico tenía dos campos relacionados con estado:

- `status`
- `fm_fiscal_status`

El campo `status` existía pero estaba roto/inconsistente:
- options antiguas: `Draft / Submitted / Cancelled`
- el código escribía valores no declarados como `draft`, `stamped`, `cancelled`, `pending_cancellation`
- en BD había registros TIMBRADO con `status=draft`
- el campo aparecía en list view mostrando información incorrecta

El campo `fm_fiscal_status` era la fuente real del estado fiscal SAT.

---

## Decisión

Usar `FFM.status` como estado fiscal SAT del DocType Factura Fiscal Mexico.

**Estados fiscales válidos:**
- `BORRADOR`
- `PROCESANDO`
- `TIMBRADO`
- `ERROR`
- `CANCELADO`
- `PENDIENTE_CANCELACION`
- `ARCHIVADO`

Mantener temporalmente `FFM.fm_fiscal_status` como campo legacy sincronizado durante Etapa 1.

**Sales Invoice NO se migra.**
`Sales Invoice.fm_fiscal_status` se conserva como snapshot fiscal custom.
No se toca `status`/`docstatus` nativo de Sales Invoice.

---

## Etapa 1 — PR actual

- `status` se configura con valores fiscales SAT
- `status_field = status`
- `states[]` configurados para indicador visual nativo Frappe
- Datos existentes migrados:
  - `status = fm_fiscal_status`
  - `FAILED → ERROR`
  - `PENDIENTE → BORRADOR`
- Escritura dual activa en todos los puntos de transición:
  - `FFM.status`
  - `FFM.fm_fiscal_status`
- 0 divergencias permitidas entre ambos campos
- Archivos con escritura dual: `timbrado_api.py`, `factura_fiscal_mexico.py`, `utils.py`, `api/__init__.py`, `hooks_handlers/sales_invoice_submit.py`
- Método muerto `calculate_status_from_fiscal_status()` eliminado

---

## Etapa 2 — PR siguiente

Eliminar modo dual:

- FFM usa solo `status` como fuente interna de estado fiscal
- Eliminar `FFM.fm_fiscal_status` del DocType y del código
- Mantener `SI.fm_fiscal_status` si sigue siendo necesario como snapshot operativo
- Cambiar lecturas/escrituras internas de FFM a `status`
- Validar timbrado, cancelación, widget SI, bloqueo SI y PPD

---

## Consecuencias

**Positivas:**
- FFM usa convención Frappe para estado funcional (`status_field`)
- List view y encabezado muestran estado fiscal correcto nativamente
- Se elimina campo `status` inconsistente con valores fuera de opciones
- Se prepara limpieza futura de `fm_fiscal_status`

**Riesgos:**
- Timbrado y cancelación dependen fuertemente del estado fiscal
- Por eso Etapa 1 mantiene compatibilidad dual
- Etapa 2 debe hacerse en PR separado con backup previo

---

## Validaciones Etapa 1

- 0 divergencias `status != fm_fiscal_status`
- 0 valores fuera de options
- GUI validada: BORRADOR → TIMBRADO → CANCELADO
- Encabezado FFM muestra estado correcto
- `SI.fm_fiscal_status` sigue funcionando como snapshot
- PPD sigue leyendo `SI.fm_fiscal_status`
