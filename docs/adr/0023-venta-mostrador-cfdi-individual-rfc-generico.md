# ADR-0023 — Venta Mostrador: CFDI Individual con RFC Genérico XAXX010101000

**Fecha:** 2026-05-12
**Estado:** Implementado (Fase 1 — PR #131)
**Issue:** #73 — Soporte para facturación a Público General (RFC genérico)

---

## Contexto

Clientes que no tienen RFC o que no desean facturar a su nombre requieren un
CFDI individual que les sirva para deducción de gastos personales o control
interno. El SAT permite el RFC genérico XAXX010101000 para este caso.

Sin embargo, XAXX010101000 tiene dos usos distintos en CFDI 4.0:

1. **CFDI individual con nombre operativo** — no requiere `InformacionGlobal`
2. **Factura Global / PUBLICO EN GENERAL** — requiere `InformacionGlobal` con periodicidad, meses y año

El sistema rechazaba completamente el RFC XAXX010101000 en el validador de Customer,
y no existía mecanismo para emitir CFDI individuales con ese RFC.

---

## Decisión

Implementar el flujo de **Venta Mostrador** para CFDI individual:

- El receptor fiscal del CFDI usa RFC XAXX010101000 con nombre operativo "VENTA MOSTRADOR"
- El nombre "VENTA MOSTRADOR" (no "PUBLICO EN GENERAL") evita el trigger de `InformacionGlobal` en el PAC
- El customer ERPNext real se conserva para cobros, cobranza y CRM
- La Factura Global (PUBLICO EN GENERAL + InformacionGlobal) queda como Fase 2

**Dos customer templates instalados:**
- `VENTA MOSTRADOR` — para CFDI individual (este PR)
- `PUBLICO EN GENERAL` — reservado para futura Factura Global

---

## Arquitectura implementada

### Customer templates

```
VENTA MOSTRADOR
  tax_id = XAXX010101000
  fm_allow_generic_rfc = 1
  fm_tax_regime = 616
  fm_uso_cfdi_default = S01
  Dirección con CP del emisor (configurable post-instalación)

PUBLICO EN GENERAL
  tax_id = XAXX010101000
  fm_allow_generic_rfc = 1
  fm_tax_regime = 616
  fm_uso_cfdi_default = S01
  Reservado — no usar para CFDI individual
```

### Custom Fields

```
Customer.fm_allow_generic_rfc (Check, default 0)
  → Permite a ese customer usar RFC genérico XAXX/XEXX
  → Solo activo en templates VENTA MOSTRADOR y PUBLICO EN GENERAL

Customer.fm_facturar_venta_mostrador (no existe — control es por checkbox en FFM)

Factura Fiscal Mexico.fm_facturar_venta_mostrador (Check, default 0)
  → Visible solo si el customer de la SI tiene fm_allow_generic_rfc=1
  → Al activarse: timbrado usa VENTA MOSTRADOR como receptor fiscal
```

### Flujo de timbrado

```
SI → FFM
  Si fm_facturar_venta_mostrador = 1:
    receptor CFDI = VENTA MOSTRADOR (XAXX010101000, 616, S01)
    customer ERPNext = cliente real (para cobros)
  Si fm_facturar_venta_mostrador = 0:
    receptor CFDI = customer normal (flujo estándar)
```

### Flujo de Complemento PPD

```
PE → Complemento Pago MX
  Verifica fm_facturar_venta_mostrador en las FFMs de las SIs
  Si todas = 1 → receptor complemento = VENTA MOSTRADOR
  Si todas = 0 → receptor complemento = customer normal
  Si mezcla → bloquea con error
```

---

## Archivos modificados

| Archivo | Cambio |
|---|---|
| `install.py` | Crea VENTA MOSTRADOR y PUBLICO EN GENERAL en after_install |
| `fixtures/custom_field.json` | `fm_allow_generic_rfc` en Customer |
| `hooks.py` | Registro del nuevo custom field |
| `validaciones/hooks_handlers/customer_validate.py` | Permite XAXX/XEXX si `fm_allow_generic_rfc=1` |
| `factura_fiscal_mexico.json` | Campo `fm_facturar_venta_mostrador` (Check) |
| `factura_fiscal_mexico.py` | `populate_billing_data` y `_get_emisor_postal_code` |
| `factura_fiscal_mexico.js` | Visibilidad condicional del checkbox, trigger al cambiar |
| `timbrado_api.py` | Resolver receptor fiscal desde checkbox |
| `complementos_pago/api.py` | Heredar receptor Venta Mostrador en PPD |
| `validations.py` + `validaciones/api.py` | tax_system desde fm_tax_regime (sin hardcodes) |
| `tests/test_venta_mostrador.py` | Suite 17 tests |

---

## Validaciones realizadas

- Timbrado FFM con XAXX010101000 en site real: **UUID generado, sin error InformacionGlobal**
- Complemento PPD con receptor VENTA MOSTRADOR: **XAXX010101000, 616, CP 96400**
- Tests: **17/17 PASS** en test-facturacion.localhost

---

## Alternativas descartadas

**Usar "PUBLICO EN GENERAL" como nombre para CFDI individual:**
Rechazado — el PAC detecta el nombre exacto y exige `InformacionGlobal`,
lo que corresponde al flujo de Factura Global, no de CFDI individual.

**Hardcodear RFC en timbrado_api:**
Rechazado — toda la información debe venir del customer template configurado,
sin hardcodes en el código de timbrado.

**Opción A (checkbox en Customer):**
Descartada para esta fase — el checkbox por factura (en FFM) es más flexible
y permite que el mismo cliente a veces use RFC propio y a veces Venta Mostrador.

---

## Consecuencias

**Positivas:**
- CFDI individual con XAXX010101000 funcional, sin InformacionGlobal
- Complemento PPD hereda el receptor correcto automáticamente
- Bloqueo explícito si se mezclan receptores distintos en un PE
- PUBLICO EN GENERAL queda disponible para Factura Global en Fase 2

**Pendientes:**
- CP del customer VENTA MOSTRADOR debe configurarse manualmente post-instalación
- Campo huérfano `fm_facturar_publico_general` en BD (columna anterior, no causa problemas)
- Fase 2: Factura Global con InformacionGlobal — issue #73 seguirá abierto hasta completar

---

## Referencias

- Issue #73: https://github.com/luisrms69/facturacion_mexico/issues/73
- PR #131: feat(venta-mostrador): CFDI individual con RFC genérico
- `docs/development/PLAN_IMPLEMENTACION_ISSUE73_PUBLICO_GENERAL.md`
- `docs/development/REPORTE_ISSUE73_PUBLICO_GENERAL.md`
