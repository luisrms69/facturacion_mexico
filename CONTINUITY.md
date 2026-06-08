# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-07
**Rama activa:** `feat/iva-tasa-0-exportacion-label-fix`
**Tarea actual:** Implementación site acg-v16.dev — configuración fiscal base completada, primera emisión CFDI pendiente

---

## Recuperación rápida

Estoy trabajando en:
Implementar y configurar el sitio de desarrollo `acg-v16.dev` para el cliente ACG
(Alimentos del Campo y Ganadería). El objetivo es dejar el sitio en estado listo para
hacer un restore en producción. Se sigue el instructivo `docs/usuario/getting-started.md`.

Plan que estoy siguiendo:
`docs/usuario/getting-started.md` — fases 0–5.

Objetivo inmediato:
Fase 3 — crear Customer y Item de prueba con datos fiscales, luego emitir primer CFDI
de prueba (Fase 4). Tras validar el timbrado, preparar el restore a producción.

Criterio de avance:
Primer CFDI timbrado en sandbox FacturAPI desde acg-v16.dev con UUID válido.

---

## Estado actual

### Ya completado en acg-v16.dev
- ✅ Fase 0 — Sitio creado, apps instaladas (erpnext + hrms + payments + facturacion_mexico)
- ✅ Fase 1 — CoA del SAT cargado (1077 cuentas, formato `###-##-###`)
- ✅ Fase 2.1 — Facturacion Mexico Company Settings (API Key sandbox)
- ✅ Fase 2.2 — Configuracion Fiscal Mexico: IVA tasa 0% activado, templates generados (4 STCT + 3 ITT)
- ✅ Fase 2.3 — Configuracion CFDI Recibidos: modo automático CoA SAT, formato `###-##-###`, cuenta `119-01-000`, template generado, 13 departamentos mapeados
- ✅ Fase 2.4 — Configuracion Reclasificacion Fiscal Mexico: 2 reglas Cobro + 1 Pago aplicadas

### Pendiente inmediato
1. Fase 3 — Customer con RFC + fm_tax_regime + fm_uso_cfdi_default
2. Fase 3 — Item con fm_producto_servicio_sat
3. Fase 4 — Primer CFDI de prueba (Sales Invoice → submit → timbrar)
4. Fase 5 — Validar módulos adicionales si el cliente los requiere
5. Restore a sitio de producción

### No repetir
- `bench migrate` sin `--site` afecta todos los sites del bench — siempre especificar `--site acg-v16.dev`
- El bug "entered twice in Item Tax" ocurre cuando dos roles en ITT apuntan a la misma cuenta — ya corregido con deduplicación en `_crear_o_actualizar_itt`
- inotify: límite aumentado a 2048 en `/etc/sysctl.d/99-inotify.conf` — si hay problemas de auto-reload revisarlo ahí
- Las dos reglas de Cobro en CRFM son duplicadas (mismo origen/destino) porque IVA Nacional e IVA 0% comparten cuenta `209-01-000` — es redundante pero no bloquea

---

## Datos de acg-v16.dev

- **URL dev:** `http://localhost:8407`
- **Puerto:** 8407 (entrada `acg_v16` en frappe-multisite)
- **Company:** ALIMENTOS DEL CAMPO Y GANADERIA (abbr: ACG)
- **API Key:** Sandbox FacturAPI (modo sandbox activo)
- **Cuentas IVA ventas:** 209-01-000 (origen) → 208-01-000 (destino cobro)
- **Cuentas IVA compras:** 119-01-000 (origen) → 118-01-000 (destino pago)

---

## Decisiones vigentes

- IVA tasa 0% y exportación Art. 29 comparten el mismo rol `ROL_IVA_CERO` — mismo tratamiento en CFDI
- `enable_exportacion` en Configuracion Fiscal Mexico cubre ambos casos (Art. 2-A y Art. 29 LIVA)
- Modo resolución CFDI Recibidos: `Automático CoA SAT` con formato `###-##-###`
- PR #184 (E-Receipts Fase 0) pendiente de merge — no bloquea esta rama

---

## Archivos relevantes ahora

### Leer primero
- `docs/usuario/getting-started.md` — instructivo de implementación (actualizado hoy)
- `docs/usuario/cfdi-recibidos.md` — flujo CFDI Recibidos

### Probablemente editar
- Ninguno por ahora — siguiente paso es trabajo en UI

### No tocar
- `facturacion_mexico/facturacion_fiscal/setup/generador_templates_fiscal.py` — fix de deduplicación recién commiteado
- `facturacion_mexico/one_offs/run_generador_tests.py` — no commitear (one_off)
- `working_docs/` — no commitear

---

## Riesgos / cuidados

- Las dos reglas duplicadas de Cobro en CRFM merecen investigación futura — podrían causar doble reclasificación en Payment Entry PPD
- El sitio `acg.dev` (bench v16) tiene datos históricos y una empresa — no confundir con `acg-v16.dev` que es el sitio limpio de implementación
- `frappe-multisite` en `/home/erpnext/bin/` fue sincronizado a `frappe-infrastructure/scripts/` hoy — commitear en ese repo también
