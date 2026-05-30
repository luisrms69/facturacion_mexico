# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-30
**Rama activa:** `docs/mkdocs-comprehensive-review` → PR #169 abierto
**Tarea actual:** PR #169 pendiente de revisión y merge

---

## Recuperación rápida

Rama de documentación exhaustiva. Fases 1-4 completadas y en PR #169.
Fase 5 (_quarantine/) queda para PR separado.

---

## Estado actual

### PR #169 — en revisión
- Fase 1: nueva estructura docs/ + _quarantine/ + working_docs/
- Fase 2: scripts/generate_reference.py + docs/referencia/ auto-generada
- Fase 3: docs/usuario/ con flujos principales
- Fase 4: docs/tecnico/setup.md y arquitectura.md

### Pendiente después del merge
- Fase 5: limpieza de _quarantine/ — PR separado, revisión archivo por archivo
- issue #165: is_submittable para CFDI Recibido antes de producción
- supplier_resolver.py tiene 2 cambios pendientes de revisión

### Estructura acordada (en main tras merge)
```
docs/ = publicable (usuario/, tecnico/, adr/, referencia/)
working_docs/ = trabajo en curso (active/, archive/)
docs/_quarantine/ = contenido previo pendiente de Fase 5
referencia/ = SIEMPRE auto-generada, nunca editar manualmente
CONTINUITY.md = estado de sesión
```

### No repetir
- No commitear en main directamente
- No editar manualmente archivos en docs/referencia/
- No incluir one_offs/ ni REPORTE_*.md en commits

---

## Archivos relevantes ahora
- PR #169: https://github.com/luisrms69/facturacion_mexico/pull/169
- `docs/_quarantine/` — para Fase 5 en PR separado
- `scripts/generate_reference.py` — regenerar referencia/

---

## Riesgos / cuidados
- docs/_quarantine/ contiene contenido valioso a clasificar en Fase 5
- issue #165 (is_submittable) antes de producción
- supplier_resolver.py tiene 2 cambios pendientes de revisión
