# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-08
**Rama activa:** `feat/iva-tasa-0-exportacion-label-fix`
**Tarea actual:** PR abierto — pendiente merge y bench update en producción

---

## Recuperación rápida

Estoy trabajando en:
PR con 4 fixes surgidos de la implementación del sitio acg-v16.dev (cliente ACG).
El PR está abierto. Después del merge: bench update en servidor de producción ACG
y restore del backup de acg-v16.dev.

Plan que estoy siguiendo:
`docs/usuario/getting-started.md` — ACG completó Fases 0-4 en acg-v16.dev.

Objetivo inmediato:
Merge del PR → bench update en producción → restore del backup acg-v16.dev.

Criterio de avance:
bench update limpio en producción (sin crash de migrate).

---

## Estado actual

### Ya completado
- ✅ acg-v16.dev configurado completamente (CoA, fiscal, items, La Comer)
- ✅ PR abierto con 4 commits

### Pendiente inmediato
1. Esperar CodeRabbit y hacer merge del PR
2. bench update en servidor de producción ACG
3. Restore backup `20260607_205644-acg-v16_dev-database.sql.gz` en producción
4. bench migrate post-restore en producción

### No repetir
- `is_your_company_address` ya está como Custom Field — no volver a depurar
- El crash de migrate (CharacterLengthExceededError) estaba en enforce_sat_uom.py — ya corregido
- Los TEST_GENERIC/AUTOMOTIVE/RETAIL fueron eliminados de install.py — no recrear
- Antes del merge: correr /update-continuity y commitear el resultado final a la rama

---

## Decisiones vigentes

- `is_your_company_address` workaround temporal ERPNext 16.21.1 — remover cuando ERPNext lo declare
- Addenda La Comer está en fixtures (se aplica en bench migrate)
- Las 24 direcciones de sucursales La Comer son datos del cliente, no fixture
- Multi-Sucursal NO está implementado — el código muerto fue eliminado en este PR

---

## Backup para restore a producción

- DB: `/home/erpnext/frappe-bench-v16/sites/acg-v16.dev/private/backups/20260607_205644-acg-v16_dev-database.sql.gz`
- Files public: `.../20260607_205644-acg-v16_dev-files.tar`
- Files private: `.../20260607_205644-acg-v16_dev-private-files.tar`

---

## Riesgos

- facturacion-v16.dev y llantascs-v16.dev necesitan `bench migrate` para fix de Address
- 2 reglas Cobro duplicadas en CRFM (209-01) — investigar post-PR
