# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-30
**Rama activa:** `chore/adr-fase6`
**Tarea actual:** Fase 6 ADRs — committed, pendiente push + PR

---

## Recuperación rápida

Estoy trabajando en:
Fase 6: escritura y commit de ADRs 0029 y 0030. Committed en `chore/adr-fase6`.
Falta push y PR a main (stacked sobre `chore/quarantine-fase5-partial`).

Plan que estoy siguiendo:
`working_docs/active/PLAN_MKDOCS_SETUP_ECOSISTEMA.md`

Objetivo inmediato:
Push ambas ramas (`chore/quarantine-fase5-partial` y `chore/adr-fase6`) → PRs a main

Criterio de avance:
Ambos PRs mergeados + `docs/_quarantine/development/` vacía + 30 ADRs en repo

---

## Estado actual

### Ya cerrado
- Fases 1–4 (PR #169): estructura docs/usuario/, docs/tecnico/, docs/adr/, docs/referencia/
- Fase 5 (commit `5e56188`): 93 archivos de _quarantine → destinos permanentes
- Fase 6 (este commit): ADR 0029 + ADR 0030 — _quarantine/development/ vacía

### En progreso
- PRs pendientes: `chore/quarantine-fase5-partial` y `chore/adr-fase6` → push + PR

### Pendiente inmediato
1. Push `chore/quarantine-fase5-partial` + PR a main
2. Push `chore/adr-fase6` + PR a main (base: Fase 5)
3. issue #165: is_submittable para CFDI Recibido antes de producción
4. supplier_resolver.py: 2 cambios pendientes de revisión

### No repetir
- No commitear en main directamente
- No editar manualmente docs/referencia/ — regenerar con script
- No incluir one_offs/ en commits
- No hacer bench migrate sin autorización

---

## Decisiones vigentes
- docs/_quarantine/ solo retiene instructions/ — no tocar
- PLAN_MKDOCS_SETUP_ECOSISTEMA.md (untracked) — decidir si commitearlo en tercer PR
- Las ramas Fase 5 y Fase 6 están stacked — mergear Fase 5 primero

---

## Archivos relevantes ahora

### Leer primero
- `docs/adr/0029-facturapi-base-unitaria-ieps-cuota.md`
- `docs/adr/0030-tablas-maestras-python-reglas-fiscales.md`
- `working_docs/active/PLAN_MKDOCS_SETUP_ECOSISTEMA.md`

### No tocar
- `docs/instructions/` — solo el usuario puede crear archivos ahí
- `docs/_quarantine/` — solo queda instructions/, no tocar

---

## Riesgos / cuidados
- PRs stacked: Fase 6 tiene Fase 5 como base — mergear en orden
- issue #165 (is_submittable) antes de poner CFDI Recibidos en producción
- api_backup.py escribe en /tmp/ — defecto conocido
