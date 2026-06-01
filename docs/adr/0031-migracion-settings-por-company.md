# ADR-0031 — Migración de Settings global (Single) a configuración por Company

**Fecha:** 2026-06-01
**Estado:** Aceptado
**PR:** #172

---

## Contexto

`Facturacion Mexico Settings` era un DocType Single (instancia única global) que almacenaba
credenciales FacturAPI, defaults de e-receipts, factura global y otros parámetros operativos.

En un entorno multi-empresa (múltiples `Company` en el mismo site ERPNext), este modelo
presentaba un problema estructural: un solo set de credenciales FacturAPI para todas las
empresas. Cada empresa emisora de CFDIs necesita su propia API Key en FacturAPI.io, su
propio modo sandbox/producción y sus propios defaults operativos.

---

## Decisión

Reemplazar `Facturacion Mexico Settings` (Single) con `Facturacion Mexico Company Settings`
(DocType normal, un registro por Company).

El Single fue **eliminado completamente** del código y la base de datos.

---

## Alternativas evaluadas

**Mantener el Single con un campo Company opcional:** descartado — no resuelve el aislamiento
de credenciales y genera ambigüedad sobre qué configuración aplica cuando hay varias empresas.

**Child table en Company:** descartado — requiere modificar un DocType de ERPNext y complica
el acceso programático.

---

## Consecuencias

- Cada empresa debe tener su propio registro de `Facturacion Mexico Company Settings` antes
  de poder timbrar.
- `FacturAPIClient` recibe `company` como parámetro obligatorio y resuelve las credenciales
  en tiempo de ejecución.
- El JS de `factura_fiscal_mexico.js` y `ereceipt_handler.js` usa `frm.doc.company` para
  consultar los defaults correctos.
- Instalaciones existentes con el Single configurado deben migrar sus datos al nuevo DocType
  manualmente (crear un registro por empresa con las mismas credenciales).

---

## Campos migrados

| Campo | Origen (Single) | Destino (Company Settings) |
|---|---|---|
| API Key Producción | `api_key` | `api_key` |
| API Key Pruebas | `test_api_key` | `test_api_key` |
| Modo Sandbox | `sandbox_mode` | `sandbox_mode` |
| Método Pago Default | `metodo_pago_default` | `metodo_pago_default` |
| Enviar Email Default | `send_email_default` | `send_email_default` |
| E-Receipt defaults | varios | varios |
| Factura Global defaults | varios | varios |

Los campos `rfc_emisor`, `lugar_expedicion` y `timeout` del Single no fueron migrados —
`rfc_emisor` y `lugar_expedicion` se leen de `Company.tax_id` y la dirección principal
de la empresa respectivamente.
