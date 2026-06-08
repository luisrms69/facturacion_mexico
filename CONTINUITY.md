# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-08
**Rama activa:** `feat/iva-tasa-0-exportacion-label-fix`
**Tarea actual:** Fixes de instalación listos para push/PR — acg-v16.dev configurado

---

## Recuperación rápida

Estoy trabajando en:
Implementar y configurar `acg-v16.dev` para el cliente ACG. La rama tiene 5 commits
con fixes y documentación. Próximo paso: push → PR → merge → bench update en producción.

Plan que estoy siguiendo:
`docs/usuario/getting-started.md` — fases 0–5. ACG está en fase lista para restore.

Objetivo inmediato:
Push de la rama, abrir PR, hacer merge, luego bench update en servidor de producción ACG.

Criterio de avance:
PR mergeado y bench update corriendo limpio en producción sin errores de migrate.

---

## Estado actual

### Ya completado en acg-v16.dev
- ✅ Fase 0–4 completas: site creado, CoA, config fiscal, customers, items, mapeo La Comer

### Commits en esta rama (listos para PR)
- `eebf2e8` — fix wizard fiscal IVA tasa 0% + bug ITT deduplicación + 14 tests
- `cd798be` — fix install ERPNext v16 Address + Addenda La Comer en fixtures
- `3923296` — docs addendas + arquitectura
- `(este)` — fix falsos positivos install + crash bench migrate Frappe v15

### Pendiente inmediato
1. Push → PR → merge
2. bench update en producción ACG
3. Restore del backup acg-v16.dev en sitio de producción

### No repetir
- `bench migrate` sin `--site` afecta todos los sites
- `export-fixtures` sobrescribe TODOS los fixtures — nunca usar sin filtro específico
- Los one_offs/ y working_docs/ NO se commitean
- El crash de migrate era por `frappe.log_error()` con título >140 chars en Frappe v15 — ya corregido

---

## Decisiones vigentes

- `setup_multi_sucursal_system()` eliminado de `after_install` — Multi-Sucursal no está implementado
- `is_your_company_address` es workaround de bug ERPNext 16.21.1 — remover cuando ERPNext lo declare
- Addenda La Comer está en fixtures; las 24 direcciones de sucursales son datos del cliente (no fixture)
- Backup safe point: `.../20260607_205644-acg-v16_dev-database.sql.gz` (1.2 MiB)

---

## Archivos relevantes ahora

### Leer primero
- `docs/usuario/getting-started.md` — instructivo completo actualizado

### No tocar
- `one_offs/` — no commitear
- `working_docs/` — no commitear
