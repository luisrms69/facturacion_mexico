# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-30
**Rama activa:** `docs/mkdocs-comprehensive-review`
**Tarea actual:** Fase 1 completada — esqueleto limpio de docs/

---

## Recuperación rápida

Rama de documentación exhaustiva. Fase 1 completada:
esqueleto limpio con nueva estructura acordada, cuarentena en docs/_quarantine/.

Siguiente: Fase 2 — generar referencia/ desde código con scripts/generate_docs.py.

---

## Estado actual

### Fase 1 — Completada
- docs/_quarantine/: todo el contenido previo (99 archivos, historia preservada)
- docs/usuario/: skeleton (getting-started, troubleshooting)
- docs/tecnico/: arquitectura.md con estado actual + setup skeleton
- docs/adr/: 28 ADRs existentes + índice nuevo
- docs/referencia/: skeleton (doctypes, hooks, api)
- working_docs/active/ y working_docs/archive/ creados
- mkdocs.yml: nueva nav + exclude_docs para _quarantine/
- mkdocs build --strict ✅

### Pendiente
- Fase 2: generar referencia/ automáticamente con scripts/generate_docs.py
- Fase 3: user-guide/ por flujo funcional (usuario/)
- Fase 4: development/ → docs/tecnico/ (setup.md, arquitectura actualizaciones)
- Fase 5: limpieza final, decidir destino de _quarantine/

### Estructura acordada
```
docs/ = publicable (usuario/, tecnico/, adr/, referencia/)
working_docs/ = trabajo en curso (active/, archive/)
CONTINUITY.md = estado de sesión
```

### No repetir
- No commitear en main directamente
- No incluir one_offs/ ni REPORTE_*.md en commits
- No hacer bench migrate sin autorización

---

## Archivos relevantes ahora
- `docs/_quarantine/` — contenido anterior en cuarentena
- `docs/tecnico/arquitectura.md` — estado actual del sistema
- `scripts/generate_docs.py` — para Fase 2 referencia/
- `mkdocs.yml` — estructura nueva

---

## Riesgos / cuidados
- docs/_quarantine/ tiene contenido valioso que se migrará en fases siguientes
- issue #165 (is_submittable) pendiente antes de producción
- supplier_resolver.py tiene 2 cambios pendientes de revisión
