# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-30
**Rama activa:** `chore/quarantine-fase5-partial`
**Tarea actual:** Fase 5 docs quarantine — committed, pendiente push + PR

---

## Recuperación rápida

Estoy trabajando en:
Limpieza de docs/_quarantine/ — Fase 5 del plan de reestructuración documental.
Fase 5 está completada y commiteada. Falta push y PR a main.

Plan que estoy siguiendo:
`working_docs/active/PLAN_MKDOCS_SETUP_ECOSISTEMA.md` (Fase 5 → Fase 6 ADRs)

Objetivo inmediato:
Push de `chore/quarantine-fase5-partial` → crear PR a main

Criterio de avance:
PR mergeado + docs/_quarantine/development/ queda solo con 3 candidatos ADR

---

## Estado actual

### Ya cerrado
- Fases 1–4 (PR #169): estructura docs/usuario/, docs/tecnico/, docs/adr/, docs/referencia/
- Fase 5: 93 archivos movidos de _quarantine/ a destinos permanentes — commiteado

### En progreso
- PR `chore/quarantine-fase5-partial` → pendiente push y apertura

### Pendiente inmediato
1. Push `chore/quarantine-fase5-partial` → abrir PR a main
2. Fase 6 (PR separado): escribir 2 ADRs desde _quarantine/development/:
   - ADR urgente: FacturAPI multiplica base × cantidad; enviar base unitaria
     (fuente: SOLUCION-IEPS-CUOTA-FACTURAPI.md, implementado en timbrado_api.py:533)
   - ADR combinado: reglas fiscales como tablas maestras Python + mapeo dinámico charge_type
     (fuente: REPORTE_ARQUITECTURA_REGLAS_CALCULO.md + REPORTE_MIGRACION_CHARGE_TYPE_DINAMICO_E1.md)
3. issue #165: is_submittable para CFDI Recibido antes de producción
4. supplier_resolver.py: 2 cambios pendientes de revisión

### No repetir
- No commitear en main directamente
- No editar manualmente docs/referencia/ — regenerar con script
- No incluir one_offs/ en commits
- No hacer bench migrate sin autorización
- No convertir candidatos ADR sin verificar implementación + PR correspondiente

---

## Decisiones vigentes
- docs/_quarantine/development/ retiene exactamente 3 candidatos ADR para Fase 6;
  no mover ni eliminar sin escribir el ADR primero
- PLAN_MKDOCS_SETUP_ECOSISTEMA.md (untracked) queda fuera de este PR — no incluir

---

## Archivos relevantes ahora

### Leer primero
- `working_docs/active/PLAN_MKDOCS_SETUP_ECOSISTEMA.md` — plan activo Fases 5–6
- `docs/_quarantine/development/SOLUCION-IEPS-CUOTA-FACTURAPI.md` — ADR urgente Fase 6
- `docs/_quarantine/development/REPORTE_ARQUITECTURA_REGLAS_CALCULO.md` — ADR combinado Fase 6
- `docs/_quarantine/development/REPORTE_MIGRACION_CHARGE_TYPE_DINAMICO_E1.md` — ADR combinado Fase 6

### Probablemente editar
- `docs/adr/` — donde irán los nuevos ADRs en Fase 6
- `mkdocs.yml` — agregar entradas nav cuando se creen los ADRs

### No tocar
- `docs/instructions/` — solo el usuario puede crear archivos ahí
- `docs/_quarantine/development/` (los 3 candidatos ADR) — no mover hasta escribir ADR

---

## Riesgos / cuidados
- Fase 6 (ADRs): verificar que SOLUCION-IEPS-CUOTA-FACTURAPI corresponde exactamente
  a timbrado_api.py:533 antes de escribir el ADR (ya verificado: FIX E4.1 presente)
- issue #165 (is_submittable) antes de poner CFDI Recibidos en producción
- api_backup.py escribe en /tmp/ — defecto conocido, no tocar sin plan
