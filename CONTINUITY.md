# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-31
**Rama activa:** `feat/multi-company-facturapi-settings`
**Tarea actual:** PR #172 abierto — pendiente de merge

---

## Recuperación rápida

Estoy trabajando en:
PR #172 abierto con la migración completa de Facturacion Mexico Settings a
Facturacion Mexico Company Settings (multi-company). Pendiente revisión y merge.

Plan que estoy siguiendo:
`working_docs/active/PLAN_MULTI_COMPANY_FACTURAPI_SETTINGS.md`

Objetivo inmediato:
Merge de PR #172

Criterio de avance:
PR mergeado + main actualizado + bench migrate en sites de producción

---

## Estado actual

### Ya cerrado
- PR #170: reestructuración documental (Fases 5–7)
- PR #172 abierto: Facturacion Mexico Company Settings completo (4 commits)

### Pendiente inmediato
1. Merge PR #172
2. bench migrate en LlantasCS y demás sites post-merge
3. Crear Facturacion Mexico Company Settings para cada Company existente
4. issue #165: is_submittable CFDI Recibido
5. issue #171: indicador visual sandbox (futura implementación)

### No repetir
- No commitear en main directamente
- instalaciones existentes NECESITAN crear Company Settings para timbrar

---

## Decisiones vigentes
- `Facturacion Mexico Settings` (Single) intacto como legacy
- `FacturAPIClient(company=None)` lanza ValidationError — intencional
- issue #171 creado, no implementar en esta rama

---

## Riesgos / cuidados
- LlantasCS, ACG y demás sites necesitan bench migrate + crear Company Settings post-merge
- issue #165 (is_submittable) antes de poner CFDI Recibidos en producción
