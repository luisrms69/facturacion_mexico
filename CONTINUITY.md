# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-08
**Rama activa:** `feat/iva-tasa-0-exportacion-label-fix`
**Tarea actual:** Configuración completa acg-v16.dev — docs actualizados, pendiente Items + primer CFDI

---

## Recuperación rápida

Estoy trabajando en:
Implementar y configurar `acg-v16.dev` para el cliente ACG (Alimentos del Campo y Ganadería).
El objetivo es dejar el sitio listo para restore en producción.
Se sigue `docs/usuario/getting-started.md`.

Plan que estoy siguiendo:
`docs/usuario/getting-started.md` — fases 0–5.

Objetivo inmediato:
Fase 3 — Items con clave SAT → Fase 4 — Primera Sales Invoice → submit → timbrar.

Criterio de avance:
Primer CFDI timbrado en sandbox FacturAPI desde acg-v16.dev con UUID válido.

---

## Estado actual

### Ya completado en acg-v16.dev
- ✅ Fase 0 — Sitio creado, apps instaladas, puerto 8407
- ✅ Fase 1 — CoA SAT cargado (1077 cuentas, formato `###-##-###`)
- ✅ Fase 2.1 — Facturacion Mexico Company Settings (API Key sandbox)
- ✅ Fase 2.2 — Configuracion Fiscal Mexico: IVA tasa 0% activado, 4 STCT + 3 ITT generados
- ✅ Fase 2.3 — Configuracion CFDI Recibidos: modo automático CoA SAT, 13 departamentos, template generado
- ✅ Fase 2.4 — Configuracion Reclasificacion Fiscal Mexico: 3 reglas (2 Cobro + 1 Pago)
- ✅ Customers: VENTA MOSTRADOR, PUBLICO EN GENERAL, COMERCIAL CITY FRESKO (RFC CCF121101KQ4, EDI completo, 24 addresses)
- ✅ Addenda La Comer en BD y en fixtures

### Ya commiteado en esta rama
- `eebf2e8` — fix wizard fiscal IVA tasa 0% + bug ITT deduplicación + 14 tests + getting-started.md
- `cd798be` — fix install ERPNext v16 Address + Addenda La Comer en fixtures + arquitectura.md
- Commit docs (este) — addendas.md revisión completa + arquitectura.md DocTypes

### Pendiente inmediato
1. Fase 3 — Items con clave SAT para prueba de timbrado
2. Fase 4 — Primera Sales Invoice → submit → timbrar con addenda La Comer
3. /ship pr — cuando esté todo listo

### No repetir
- Bug `is_your_company_address` — corregido con Custom Field, no volver a depurar
- Bug ITT "entered twice" — corregido con deduplicación en generador_templates_fiscal.py
- `bench migrate` sin `--site` afecta todos los sites
- `one_offs/` y `working_docs/` NO se commitean

---

## Decisiones vigentes

- `enable_exportacion` cubre Art. 2-A (alimentos) Y Art. 29 (exportación)
- `is_your_company_address` es workaround de bug ERPNext 16.21.1 — remover cuando ERPNext lo declare nativamente
- Addenda La Comer es fixture del app; las 24 direcciones de sucursales son datos del cliente (no fixture)
- Las dos reglas Cobro duplicadas en CRFM (misma cuenta 209-01) son redundantes pero no bloquean — investigar en Fase 5
- facturacion-v16.dev y llantascs-v16.dev también necesitan `bench migrate` para el fix de `is_your_company_address`

---

## Archivos relevantes ahora

### Leer primero
- `docs/usuario/getting-started.md` — instructivo de implementación
- `docs/usuario/addendas.md` — revisado hoy, completo

### No tocar
- `one_offs/` — scripts temporales, no commitear
- `working_docs/` — archivos del cliente ACG, no commitear

---

## Riesgos / cuidados

- Las dos reglas Cobro duplicadas en CRFM podrían causar doble reclasificación en Payment Entry PPD
- `acg.dev` (site antiguo) tiene datos históricos — no confundir con `acg-v16.dev`
- facturacion-v16.dev y llantascs-v16.dev tienen bug `is_your_company_address` activo hasta que se migre
