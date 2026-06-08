# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-08
**Rama activa:** `main`
**Tarea actual:** Post-merge PR #185 — próximo: restore backup ACG en producción

---

## Recuperación rápida

Estoy trabajando en:
PR #185 mergeado y main sincronizado. El sitio acg-v16.dev está completamente
configurado para el cliente ACG. El siguiente paso es restaurar el backup en
el servidor de producción ACG y correr bench migrate.

Plan que estoy siguiendo:
`docs/usuario/getting-started.md` — ACG en Fase lista para producción.

Objetivo inmediato:
Restore del backup acg-v16.dev en servidor de producción del cliente ACG.

Criterio de avance:
bench migrate limpio en producción + primer CFDI de prueba timbrado.

---

## Estado actual

### Ya cerrado
- ✅ PR #185 mergeado — fix install + wizard IVA 0% + addendas + crash bench migrate
- ✅ acg-v16.dev configurado completo (CoA, fiscal, 119 items, La Comer, 24 sucursales)
- ✅ Issue #186 abierto — revisión templates IEPS por variante

### Pendiente inmediato
1. Restore backup en producción ACG
2. bench migrate post-restore
3. Prueba de timbrado CFDI con sandbox FacturAPI

### No repetir
- `is_your_company_address` sin prefijo fm_* es excepción documentada — no cambiar
- Los one_offs de ACG ya fueron ejecutados y eliminados
- bench migrate sin --site afecta todos los sites del bench

---

## Decisiones vigentes

- `is_your_company_address` workaround ERPNext 16.21.1 — remover cuando ERPNext lo declare
- Addenda La Comer en fixtures — se aplica automáticamente en bench migrate
- Issue #186: revisión IEPS combustibles — no urgente para ACG

---

## Backup para restore a producción

- DB: `/home/erpnext/frappe-bench-v16/sites/acg-v16.dev/private/backups/20260607_205644-acg-v16_dev-database.sql.gz`
- Public: `.../20260607_205644-acg-v16_dev-files.tar`
- Private: `.../20260607_205644-acg-v16_dev-private-files.tar`
- Checkpoint: `frappe-infrastructure/checkpoints/20260607-205635-facturacion_mexico-acg-v16.dev/`

---

## Riesgos

- C5 pendiente: escape XML en template La Comer (|e en campos de texto libre)
- Issue #186: IEPS combustibles — pendiente investigación
