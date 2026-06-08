# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-08
**Rama activa:** `feat/iva-tasa-0-exportacion-label-fix`
**Tarea actual:** Configuración completa acg-v16.dev para cliente ACG — en progreso

---

## Recuperación rápida

Estoy trabajando en:
Implementar y configurar el sitio `acg-v16.dev` para el cliente ACG (Alimentos del Campo
y Ganadería). El objetivo es dejar el sitio listo para restore en producción.
Se sigue `docs/usuario/getting-started.md`.

Plan que estoy siguiendo:
`docs/usuario/getting-started.md` — fases 0–5.

Objetivo inmediato:
Commit pendiente (fixtures + install.py fix) → revisión y actualización completa de docs
(addendas.md + arquitectura.md + getting-started) → Fase 3/4: Items + primer CFDI de prueba.

Criterio de avance:
Primer CFDI timbrado en sandbox FacturAPI desde acg-v16.dev con UUID válido.

---

## Estado actual

### Ya completado en acg-v16.dev
- ✅ Fase 0 — Sitio acg-v16.dev creado, apps instaladas, puerto 8407
- ✅ Fase 1 — CoA SAT cargado (1077 cuentas, formato `###-##-###`)
- ✅ Fase 2.1 — Facturacion Mexico Company Settings (API Key sandbox)
- ✅ Fase 2.2 — Configuracion Fiscal Mexico: IVA tasa 0% activado, 4 STCT + 3 ITT generados
- ✅ Fase 2.3 — Configuracion CFDI Recibidos: modo automático CoA SAT, 13 departamentos, template generado
- ✅ Fase 2.4 — Configuracion Reclasificacion Fiscal Mexico: 3 reglas (2 Cobro + 1 Pago)
- ✅ Customers: VENTA MOSTRADOR, PUBLICO EN GENERAL, COMERCIAL CITY FRESKO (RFC CCF121101KQ4, EDI completo, 24 addresses)
- ✅ Addenda La Comer en BD y en fixtures

### Pendiente inmediato
1. Commit 2: `fix(install)` — fixtures/addenda_fixtures + custom_field + hooks + install.py
2. Commit 3: docs — arquitectura.md + addendas.md (revisión completa pendiente)
3. Fase 3 — Items con clave SAT para prueba de timbrado
4. Fase 4 — Primera Sales Invoice → submit → timbrar

### No repetir
- El bug `is_your_company_address` ya está corregido con Custom Field Address — no volver a depurar
- Las dos reglas de Cobro en CRFM son duplicadas (misma cuenta 209-01 para NAC e IVA 0%) — es redundante pero no bloquea
- El bug ITT "entered twice" ya está corregido en `generador_templates_fiscal.py` con deduplicación
- `bench migrate` sin `--site` afecta todos los sites — siempre especificar `--site acg-v16.dev`
- `one_offs/` y `working_docs/` NO se commitean

---

## Decisiones vigentes

- `enable_exportacion` en Configuracion Fiscal Mexico cubre Art. 2-A (alimentos) Y Art. 29 (exportación)
- `is_your_company_address` se agrega como Custom Field de facturacion_mexico como workaround de bug ERPNext 16.21.1
- Addenda La Comer es fixture del app (genérico), las direcciones de sucursales son datos del cliente (no fixture)
- Docs de arquitectura.md y addendas.md tienen gaps — revisión completa pendiente en commit separado
- facturacion-v16.dev y llantascs-v16.dev también necesitan `bench migrate` para el fix de `is_your_company_address`

---

## Archivos relevantes ahora

### Leer primero
- `docs/usuario/getting-started.md` — instructivo de implementación (actualizado)
- `docs/usuario/addendas.md` — pendiente revisión completa

### Probablemente editar en próximo commit
- `docs/tecnico/arquitectura.md` — ya editado, pendiente commit
- `docs/usuario/addendas.md` — revisión completa pendiente

### No tocar
- `one_offs/` — scripts temporales, no commitear
- `working_docs/` — archivos del cliente ACG, no commitear

---

## Riesgos / cuidados

- Las dos reglas Cobro duplicadas en CRFM podrían causar doble reclasificación en Payment Entry PPD — investigar en Fase 5
- `acg.dev` (site antiguo) tiene datos históricos — no confundir con `acg-v16.dev` (site limpio)
- facturacion-v16.dev y llantascs-v16.dev aún tienen el bug `is_your_company_address` activo hasta hacer migrate
