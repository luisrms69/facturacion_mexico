# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-30
**Rama activa:** `docs/mkdocs-comprehensive-review`
**Tarea actual:** Fase 4 completada — docs/tecnico/ con setup real

---

## Recuperación rápida

Rama de documentación exhaustiva. Fases 1-4 completadas.

Siguiente: Fase 5 — limpieza final de _quarantine/.

---

## Estado actual

### Fase 1 — Completada
- docs/_quarantine/: contenido previo preservado (99 archivos)
- Nueva estructura: docs/usuario/, docs/tecnico/, docs/adr/, docs/referencia/

### Fase 2 — Completada
- scripts/generate_reference.py: generador idempotente
- docs/referencia/: doctypes.md + hooks.md + api.md + index.md
- Regenerar: `python3 scripts/generate_reference.py`

### Fase 3 — Completada
- docs/usuario/: getting-started, cfdi-recibidos, cancelar-cfdi, troubleshooting, addendas, multisucursal

### Fase 4 — Completada
- docs/tecnico/setup.md: reescrito con realidad actual (Frappe v16, FacturAPI, ruff+prettier)
- docs/tecnico/index.md: actualizado con links a arquitectura, setup, ADRs
- mkdocs build --strict ✅

### Pendiente
- Fase 5: limpieza final de _quarantine/
  - Decidir destino de cada subdirectorio
  - Mover contenido valioso a working_docs/ o docs/
  - Eliminar lo que ya no sirve

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
- `docs/_quarantine/` — contenido para decisión en Fase 5
- `scripts/generate_reference.py` — regenerar referencia/
- `docs/tecnico/arquitectura.md` — estado actual del sistema

---

## Riesgos / cuidados
- docs/_quarantine/ tiene contenido valioso a decidir en Fase 5
- issue #165 (is_submittable) pendiente antes de producción
- supplier_resolver.py tiene 2 cambios pendientes de revisión
