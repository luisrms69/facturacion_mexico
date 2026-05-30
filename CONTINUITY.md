# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-30
**Rama activa:** `docs/mkdocs-comprehensive-review`
**Tarea actual:** Fase 2 completada — referencia/ generada desde código

---

## Recuperación rápida

Rama de documentación exhaustiva. Fases 1 y 2 completadas.

Siguiente: Fase 3 — docs/usuario/ con getting-started y how-to por flujo funcional.

---

## Estado actual

### Fase 1 — Completada
- docs/_quarantine/: todo el contenido previo (99 archivos, historia preservada)
- Nueva estructura: docs/usuario/, docs/tecnico/, docs/adr/, docs/referencia/
- working_docs/active/ y working_docs/archive/ creados
- mkdocs.yml: nueva nav + exclude_docs

### Fase 2 — Completada
- scripts/generate_reference.py: generador idempotente y replicable
  - 54 DocTypes desde JSONs → docs/referencia/doctypes.md
  - 16 doc_event handlers + after_migrate → docs/referencia/hooks.md
  - 198 funciones @frappe.whitelist() → docs/referencia/api.md
- Comando: `python3 scripts/generate_reference.py`
- Verificar: `python3 scripts/generate_reference.py --verify`
- mkdocs build --strict ✅

### Pendiente
- Fase 3: docs/usuario/ — getting-started y how-to por flujo funcional
- Fase 4: docs/tecnico/setup.md — migrar desde _quarantine/development/setup.md
- Fase 5: limpieza final de _quarantine/

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
- No hacer bench migrate sin autorización

---

## Archivos relevantes ahora
- `scripts/generate_reference.py` — regenerar referencia/
- `docs/_quarantine/` — contenido en cuarentena para migrar en Fases 3-5
- `docs/tecnico/arquitectura.md` — estado actual del sistema
- `docs/adr/` — 28 ADRs permanentes

---

## Riesgos / cuidados
- docs/_quarantine/ tiene contenido valioso (user-guide, development/setup) para Fases 3-4
- issue #165 (is_submittable) pendiente antes de producción
- supplier_resolver.py tiene 2 cambios pendientes de revisión
