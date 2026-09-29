# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-09-28
**Rama activa:** `feat/cfdi-historico-compras-clasificador`
**Tarea actual:** Clasificador determinista de Items para el importador histórico de CFDI de compra.
En `/ship pr` (v1.10.0).

---

## Recuperación rápida

Estoy trabajando en:
El **clasificador determinista de Items** de `cfdi_historico_compras`: asignar `item_code` a cada
concepto XML **antes** de `build_purchase_invoice()`, usando la **taxonomía autorizada de Gastos**
(Código Agrupador SAT) — sin mecanismo de aprendizaje y **sin fallback arbitrario**.

Objetivo inmediato:
`/ship pr` hacia `main` con bump **v1.10.0** (MINOR). Tras merge: `/sync-check` + `/ship release` v1.10.0.

Criterio de avance:
PR mergeado con bump 1.10.0; luego release. Cobertura demostrada: **905/905 conceptos → item_code, 0 sin
item, 0 Items nuevos**; una clave sin mapping definido queda sin resolver → `ERROR_ITEM` (sin fallback).
**Pendiente NO bloqueante:** validación end-to-end con datos reales del apply (hoy: tests unitarios +
dry-run read-only en el site restaurado local).

---

## Estado actual (implementado en la rama)

- **`cfdi_emitidos` (importador de venta):** los CFDI **cancelados ya no se omiten** — se crean como
  Sales Invoice Draft por el mismo flujo que los vigentes (contador `cancelados` informativo).
- **`cfdi_historico_compras` (nuevo):** importador batch de CFDI de compra → Purchase Invoice Draft
  reutilizando `cfdi_recibidos` (dry-run read-only, idempotencia por `fm_cfdi_uuid`, fail-closed de
  Supplier/Item/cuenta/impuesto, CSV de proveedores faltantes). No submit, no PAC.
- **`preparacion_terceros` (nuevo, V1 solo lectura):** analiza XML y genera CSV de Customers/Suppliers
  faltantes para Data Import; no crea nada; dedupe nacional por RFC / extranjero por NumRegIdTrib.
- **`cfdi_historico_rep` (nuevo):** importa REP históricos → Payment Entry nativos + `Complemento Pago MX`
  sin PAC. Direcciones EMITIDO (Receive/Sales Invoice) y RECIBIDO (Pay/Purchase Invoice); reconciliación
  fuerte (UUID único, contraparte, MonedaDR==factura, `ImpSaldoAnt==outstanding`, Insoluto, ImpPagado,
  cuadre `Monto=Σ(ImpPagado/EquivalenciaDR)`); orden cronológico por FechaPago; cuentas explícitas por
  moneda; idempotencia por `folio_fiscal`; vigentes con PE, cancelados sin PE; **multi-Pago** (N PE + 1
  Complemento, rollback total).
- **`complementos_pago` (schema + código):** nuevo child `Complemento Pago Detalle Pago MX` + Table
  `pagos` + `pago_idx` en `Documento Relacionado Pago MX`/`Detalle Complemento Pago MX`. Validación
  `validate_documentos_relacionados` pago-aware con Decimal y **EquivalenciaDR SAT correcta**
  (`ImpPagado/EquivalenciaDR`). `tipo_cambio_p` saliente corregido (MonedaP→MXN). Payload de timbrado
  consume `pagos` (N nodos). Legacy (sin `pagos`) sigue válido sin data patch.
- `__init__.py` — bump `1.8.0 → 1.9.0` (MINOR).

Aplicado con `bench migrate` en `test-facturacion.localhost` (nuevo child + columnas). Sin data patch.

---

## Decisiones vigentes no evidentes en el código

- **Canónico vs legacy (sin data patch):** con filas `pagos`, esa tabla es la fuente de verdad; los
  escalares del padre son espejo del primer Pago. Sin `pagos` = un Pago implícito por escalares.
- **Cuentas fail-closed:** Receive→`paid_to`, Pay→`paid_from` explícitos (o mapa por moneda); nunca se
  autoselecciona caja/banco; la cuenta debe estar en MonedaP.
- **Sin PAC en históricos:** `fm_creation_source` vacío → la UI no ofrece cancelación/timbrado PAC.
- **Cancelado por señal explícita del lote** (`cancelled_marker`), nunca inferido del XML.
- **Cross-currency:** tasas derivadas de datos reales (`EquivalenciaDR × conversion_rate`); ERPNext es
  árbitro final (savepoint revierte si no puede representar). Ver ADR 0042.

### Pendientes conocidos (NO bloqueantes)
1. Validación end-to-end con datos reales de los importadores (hoy: tests unitarios; migrate verificado).
2. PE cross-currency real (mapeo nativo validado solo por unit tests + ERPNext runtime).
3. `tipo_cambio_p` saliente: quedó corregido; falta prueba de timbrado real en moneda extranjera.

---

## No commitear
- `facturacion_mexico/one_offs/*` (validaciones y análisis histórico; nunca al repo).
- `docs/audit/validation_report.md` (artefacto generado por `scripts/validate_docs.py`).
- `scripts/*` locales, `working_docs/private/`.
