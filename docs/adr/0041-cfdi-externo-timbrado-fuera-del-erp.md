# ADR 0041 — CFDI externo: representar un timbrado ocurrido fuera de este ERP

**Estado:** Aceptado
**Fecha:** 2026-09-23

## Contexto

Necesitamos representar en ERPNext un CFDI **ya timbrado en otro sistema/PAC** (cargas históricas de
ventas, migraciones): la Sales Invoice y su `Factura Fiscal Mexico` (FFM) deben conservar la realidad
fiscal real (UUID, serie, folio, fecha de timbrado, XML, estado vigente/cancelado) **sin** volver a
timbrar, **sin** llamar a FacturAPI y **sin** inventar actividad del PAC.

El obstáculo es el lifecycle actual: `calculate_fiscal_status_from_logs()` corre en cada `on_update`
de la FFM y **deriva `status` exclusivamente de `FacturAPI Response Log`** (`Timbrado`/`Confirmación
Cancelación` con `success=1`). Sin ese log, cualquier FFM marcada `TIMBRADO` a mano vuelve a
`BORRADOR`. Se evaluaron y descartaron dos atajos:

- **V1 — `db_set`/SQL** saltando el ORM para fijar `TIMBRADO`: frágil (un `.save()` posterior lo revierte).
- **V2 — `FacturAPI Response Log` sintético**: contamina el sistema de auditoría del PAC con eventos
  que nunca ocurrieron en FacturAPI.

## Decisión

Se agrega soporte **genérico** (no específico de ningún cliente) para "CFDI externo" con el **mínimo**
cambio de esquema: **un único valor nuevo** en `Factura Fiscal Mexico.fm_creation_source` →
`"CFDI externo"`. No se crean campos nuevos. `FFM.status` sigue siendo el estado fiscal canónico.

1. **Fuente de verdad dual del estado.** `calculate_fiscal_status_from_logs()` hace *early-return*
   cuando `fm_creation_source == "CFDI externo"`: para esos documentos el estado NO se deriva de
   Response Logs; lo fija la primitiva desde la evidencia externa. El flujo FacturAPI queda intacto.
2. **Evidencia mínima** exigida antes de aceptar `TIMBRADO`/`CANCELADO` externo: `fm_uuid` con formato
   válido, `fecha_timbrado`, XML adjunto en `xml_file`, `facturapi_id` vacío y ausencia de Response Log
   de `Timbrado`. En `BORRADOR` (construcción) la validación no exige evidencia todavía, para permitir
   el orden crear-FFM → adjuntar-XML → poblar → fijar estado.
3. **State machine acotada** para externos: `BORRADOR→TIMBRADO/CANCELADO`, `TIMBRADO→CANCELADO`; se
   bloquean los estados del ciclo PAC (`PROCESANDO`/`ERROR`/`PENDIENTE_CANCELACION`). `CANCELADO` es
   terminal.
4. **Primitiva de dominio interna** `registrar_cfdi_externo(sales_invoice, uuid, xml_content, ...)`
   (no whitelisted). Crea o reutiliza la FFM (vía `get_or_create_active_ffm`), adjunta el XML, puebla
   la evidencia y fija el estado. Es **idempotente** por `(sales_invoice, uuid)` y **fail-closed** ante
   conflictos (mismo UUID en otra SI, UUID distinto en la misma SI, o FFM ya timbrada por FacturAPI).
5. **Guards de acciones FacturAPI** en UI y servidor: `timbrar_factura`, `cancelar_factura`,
   `descargar_archivos_cfdi`, `create_substitution_si` y `revisar_estatus_cancelacion` rechazan un CFDI
   externo. La reconciliación programada (`run_auto_reconciliation`/`reconcile_ffm`) ya los omite por
   `facturapi_id` vacío.
6. **`CANCELADO` externo no cascada:** fija `FFM.status = CANCELADO` como dato; **no** cancela la Sales
   Invoice (docstatus) ni genera reversión contable. El tratamiento contable de históricos cancelados
   se decide por separado.

## Consecuencias

- Backward-compatible y aditivo: toda FFM existente tiene `fm_creation_source != "CFDI externo"` → se
  comporta exactamente igual que hoy. **Sin patch de datos.**
- PPD/complementos siguen funcionando: una FFM externa `TIMBRADO` con UUID + snapshots de SI cumple los
  requisitos del flujo de complemento (que usa `FFM.fm_uuid`, no Response Logs).
- La lógica específica de la carga histórica (mapeos, importador) vive en `acti_customs`, que consume
  `registrar_cfdi_externo` sin manipular internals de la FFM. `facturacion_mexico` permanece genérico.

## Alternativas descartadas

- **V1 (db_set/SQL)** y **V2 (Response Log sintético)**: ver Contexto.
- **Campos nuevos `fm_fiscal_source` + `fm_external_fiscal_status`**: se evaluó separar "procedencia de
  creación" de "autoridad fiscal", pero no hay caso real en el código que lo requiera; `fm_creation_source`
  + `status` + evidencia bastan de forma inequívoca (el valor explícito `CFDI externo` evita la
  ambigüedad de `Manual`, y el estado solo asciende con evidencia presente).
