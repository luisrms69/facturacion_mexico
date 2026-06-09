# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-08
**Rama activa:** `fix/workspace-facturacion-mexico-shortcuts`
**Tarea actual:** Workspace Facturación México — fix shortcuts + visual fase 1

---

## Recuperación rápida

Estoy trabajando en:
Mejoras al workspace "Facturación México": fix de Configuracion CFDI Recibidos
faltante en shortcuts, labels cortos, colores por sección e iconos.

Plan que estoy siguiendo:
Commit pendiente del workspace JSON. Issue #188 para Fase 2 (KPIs + gráficas).

Objetivo inmediato:
Merge de este PR.

Criterio de avance:
Workspace visible con shortcuts completos en cualquier fresh install.

---

## Estado actual

### Ya cerrado
- ✅ PR #185 — fix install + wizard + addendas
- ✅ PR #187 — fix departamentos grupo CFDI Recibidos

### En progreso
- fix/workspace-facturacion-mexico-shortcuts — listo para commit

### Pendiente inmediato
1. Commit + PR de este workspace fix
2. Fase 2 workspace: Issue #188 (KPIs, gráficas)
3. Restore ACG en producción (pendiente)

### No repetir
- Agregar DocType al workspace requiere actualizar shortcuts + content + links
- reload_doc(force=True) necesario en sitios restaurados desde backup

---

## Decisiones vigentes

- Workspace shortcuts: labels cortos (<20 chars), colores por sección, iconos Frappe
- reload_doc(force=True) es el mecanismo para actualizar workspaces en sitios existentes
- Issue #188 para la versión completa del tablero operativo

---

## Riesgos

- Issue #186: IEPS combustibles — pendiente
- Restore ACG producción: pendiente
