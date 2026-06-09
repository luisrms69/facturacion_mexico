# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-08
**Rama activa:** `fix/workspace-facturacion-mexico-shortcuts`
**Tarea actual:** PR abierto — fix workspace Facturación México

---

## Recuperación rápida

Estoy trabajando en:
PR con fix del workspace "Facturación México": Configuracion CFDI Recibidos
faltaba en shortcuts, más mejoras visuales (labels, colores, iconos).

Plan que estoy siguiendo:
Merge del PR → sync-check → siguiente tarea.

Objetivo inmediato:
Merge de este PR.

Criterio de avance:
main con el fix de workspace. Fresh install muestra todos los shortcuts.

---

## Estado actual

### Ya cerrado
- ✅ PR #185 — fix install + wizard + addendas
- ✅ PR #187 — fix departamentos grupo CFDI Recibidos

### En progreso
- PR fix/workspace-facturacion-mexico-shortcuts — abierto

### Pendiente inmediato
1. Merge este PR
2. Restore ACG producción (pendiente)
3. Issue #188 — Fase 2 workspace (KPIs, gráficas)

### No repetir
- Agregar DocType al workspace: actualizar shortcuts + content + links
- reload_doc(force=True) para sitios existentes restaurados desde backup

---

## Decisiones vigentes

- Workspace shortcuts: labels <20 chars, colores por sección, iconos Frappe
- Issue #186: IEPS combustibles — pendiente investigación

---

## Riesgos

- Restore ACG producción pendiente
- Issue #186: IEPS combustibles
