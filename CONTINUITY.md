# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-30
**Rama activa:** `docs/mkdocs-comprehensive-review`
**Tarea actual:** Fase 3 completada — docs/usuario/ con flujos principales

---

## Recuperación rápida

Rama de documentación exhaustiva. Fases 1, 2 y 3 completadas.

Siguiente: Fase 4 — docs/tecnico/setup.md desde _quarantine.
Luego Fase 5 — limpieza final de _quarantine/.

---

## Estado actual

### Fase 1 — Completada
- docs/_quarantine/: contenido previo preservado (99 archivos)
- Nueva estructura: docs/usuario/, docs/tecnico/, docs/adr/, docs/referencia/
- working_docs/active/ y working_docs/archive/ creados

### Fase 2 — Completada
- scripts/generate_reference.py: generador idempotente
- docs/referencia/: doctypes.md + hooks.md + api.md + index.md
- Regenerar: `python3 scripts/generate_reference.py`

### Fase 3 — Completada
- docs/usuario/getting-started.md — configuración inicial y primer CFDI
- docs/usuario/cfdi-recibidos.md — flujo actualizado post-PR #166/#168
- docs/usuario/cancelar-cfdi.md — motivos 01-04 y sustitución
- docs/usuario/troubleshooting.md — errores reales desde el código
- docs/usuario/addendas.md — migrada desde _quarantine (base mejorable)
- docs/usuario/multisucursal.md — migrada desde _quarantine (base mejorable)
- mkdocs.yml nav: 7 páginas bajo Guía de Usuario

### Pendiente
- Fase 4: docs/tecnico/setup.md — desde _quarantine/development/setup.md
- Fase 5: limpieza final de _quarantine/
- addendas.md y multisucursal.md pueden mejorarse en iteraciones futuras

### Estructura acordada
```
docs/ = publicable (usuario/, tecnico/, adr/, referencia/)
working_docs/ = trabajo en curso (active/, archive/)
referencia/ = SIEMPRE auto-generada, nunca editar manualmente
CONTINUITY.md = estado de sesión
```

### No repetir
- No commitear en main directamente
- No editar manualmente archivos en docs/referencia/
- No incluir one_offs/ ni REPORTE_*.md en commits

---

## Archivos relevantes ahora
- `docs/_quarantine/development/setup.md` — para Fase 4
- `scripts/generate_reference.py` — regenerar referencia/
- `docs/tecnico/arquitectura.md` — estado actual del sistema

---

## Riesgos / cuidados
- docs/_quarantine/ tiene contenido para Fase 4-5
- issue #165 (is_submittable) pendiente antes de producción
- supplier_resolver.py tiene 2 cambios pendientes de revisión
