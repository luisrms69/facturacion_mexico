# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-30
**Rama activa:** `chore/quarantine-fase5-partial`
**Tarea actual:** Guía de usuario docs — committed, rama pendiente de PR

---

## Recuperación rápida

Estoy trabajando en:
Documentación de usuario completa para facturacion_mexico. La rama acumula
Fases 5, 6 y la guía de usuario (timbrado + cancelación).

Plan que estoy siguiendo:
`working_docs/active/PLAN_MKDOCS_SETUP_ECOSISTEMA.md`

Objetivo inmediato:
PR de la rama `chore/quarantine-fase5-partial` a main

Criterio de avance:
PR mergeado con todos los commits de la rama

---

## Estado actual

### Ya cerrado
- Fases 1–4 (PR #169): estructura docs/usuario/, docs/tecnico/, docs/adr/, docs/referencia/
- Fase 5 (commit `5e56188`): 93 archivos _quarantine → destinos permanentes
- Fase 6 (commit `0fe91e1`): ADR 0029 + ADR 0030
- Fase 7 (este commit): guía de usuario — portada, emitir-cfdi, cancelar-cfdi, getting-started

### Pendiente inmediato
1. PR de `chore/quarantine-fase5-partial` a main
2. issue #165: is_submittable para CFDI Recibido antes de producción
3. supplier_resolver.py: 2 cambios pendientes de revisión

### No repetir
- No commitear en main directamente
- No editar manualmente docs/referencia/ — regenerar con script
- No incluir one_offs/ en commits
- No sugerir push sin que el usuario lo pida

---

## Decisiones vigentes
- docs/_quarantine/ solo retiene instructions/ — no tocar
- PLAN_MKDOCS_SETUP_ECOSISTEMA.md (untracked) — no incluir en commits

---

## Archivos relevantes ahora

### Leer primero
- `docs/usuario/emitir-cfdi.md` — flujo principal documentado
- `docs/usuario/cancelar-cfdi.md` — dos caminos de cancelación

### No tocar
- `docs/instructions/` — solo el usuario puede crear archivos ahí
- `docs/_quarantine/` — solo queda instructions/

---

## Riesgos / cuidados
- issue #165 (is_submittable) antes de poner CFDI Recibidos en producción
- api_backup.py escribe en /tmp/ — defecto conocido
