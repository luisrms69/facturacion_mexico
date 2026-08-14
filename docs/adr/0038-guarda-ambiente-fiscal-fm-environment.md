# ADR 0038 — Guarda de ambiente fiscal por sitio (`fm_environment`) para el PAC

**Estado:** Aceptado
**Issue:** #215
**Fecha:** 2026-08-14

## Contexto

La selección de credencial de FacturAPI dependía exclusivamente del campo `sandbox_mode`
almacenado en la **base de datos** (`Facturacion Mexico Company Settings`). El cliente elegía
`test_api_key` o `api_key` según ese flag, contra la misma URL de FacturAPI (el ambiente real
lo determina el prefijo de la Secret Key: `sk_live_` vs `sk_test_`).

`bench restore` restaura la **BD** pero no sanea las credenciales fiscales. Un sitio de
desarrollo restaurado desde producción hereda `sandbox_mode` y `api_key` productivos; con
`sandbox_mode=0` + `api_key` `sk_live_`, cualquier timbrado desde ese entorno emitiría un
**CFDI real ante el SAT**. La única condición para facturar en real vivía en la BD — justo lo
que el restore sobreescribe.

## Decisión

La fuente de verdad del ambiente fiscal pasa a ser una variable **explícita por sitio** en
`site_config.json`: `fm_environment` con valores `"production"` o `"sandbox"`.

1. La credencial se elige por `fm_environment` (`production` → `api_key`, `sandbox` →
   `test_api_key`), **sin fallback** entre campos. `sandbox_mode` deja de decidir la credencial
   y se conserva solo como valor **derivado** (`sandbox_mode == (fm_environment == "sandbox")`)
   por compatibilidad de UI.
2. Una **guarda central** en el único chokepoint (`FacturAPIClient._make_request` y
   `_make_request_silent`) bloquea las operaciones **mutantes** (POST/PUT/PATCH/DELETE) antes de
   contactar al PAC cuando:
   - falta `fm_environment` o su valor es inválido (fail-closed);
   - la credencial del ambiente no existe;
   - la credencial efectiva empieza con `sk_live_` y `fm_environment != "production"`.
   Los **GET** (reconciliación, verificación de estado, validación de RFC) siguen permitidos.
3. El bloqueo usa `frappe.throw` con mensaje explícito ("no se contactó a FacturAPI"); en
   background jobs, Frappe registra la excepción en Error Log (sin infraestructura de alertas
   adicional).

`site_config.json` es a prueba de restore (no se copia con la BD) y es un mecanismo estándar
de Frappe (`frappe.conf`).

## Consecuencias

- Un entorno restaurado desde producción queda **incapaz de emitir CFDIs reales** salvo que su
  `site_config.json` declare explícitamente `fm_environment="production"` **y** tenga `api_key`
  `sk_live_`.
- **Todos** los sitios que timbran deben declarar `fm_environment` (producción → `production`;
  staging/desarrollo → `sandbox`); si falta, las mutaciones quedan bloqueadas (fail-closed).
- **Orden de despliegue crítico:** fijar `fm_environment="production"` en el `site_config.json`
  de producción **antes** de activar la guarda, o el timbrado legítimo de producción quedaría
  bloqueado.
- El ambiente fiscal pasa a ser **por sitio**, no por Company: un mismo sitio es todo
  `production` o todo `sandbox`. No hay cambios en la lógica fiscal, cálculo ni payload.

## Alternativa descartada

Se evaluó un esquema de **defensa en profundidad** con múltiples capas (autorizador server-side
por filesystem, allowlist por IP/identidad de red, saneo automático post-restore vía
`after_migrate`, e indicador visual). Se descartó por ser innecesariamente complejo y frágil
(las IP cambian; el saneo automático corre en cada migrate) frente al objetivo. Como todo el
tráfico mutante pasa por un **único chokepoint**, una sola guarda explícita basada en
`site_config.json` cumple el objetivo fail-closed con cambios mínimos. El indicador visual y el
saneo se remiten a issues separados (p. ej. #171).
