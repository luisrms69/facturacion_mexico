# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-08
**Rama activa:** `fix/cfdi-recibidos-department-grupos`
**Tarea actual:** PR #187 listo para merge — fix departamentos grupo CFDI Recibidos

---

## Recuperación rápida

Estoy trabajando en:
PR #187 revisado por CodeRabbit (solo comentarios sobre CONTINUITY.md, ignorables).
Listo para Squash and Merge.

Plan que estoy siguiendo:
Merge PR #187 → bench update en producción actiglobal → validar con cliente.

Objetivo inmediato:
Hacer merge del PR #187.

Criterio de avance:
main sincronizado con el fix. Producción actualizada con migrate + build.

---

## Estado actual

### Ya cerrado
- ✅ PR #185 mergeado — fix install + wizard fiscal IVA 0% + addendas
- ✅ PR #187 abierto — fix departamentos grupo CFDI Recibidos (CodeRabbit OK)

### Pendiente inmediato
1. Merge PR #187
2. bench update + migrate + build en producción (actiglobal)
3. Restore ACG en producción (pendiente)

### No repetir
- Había 5 puntos con is_group=0 para Department — todos corregidos en este PR
- cost_center, item_group, account, supplier_group mantienen is_group=0

---

## Decisiones vigentes

- Department en CFDI Recibidos es llave interna para 601-604, NO se traslada a PI
- PI recibe solo cuentas contables hoja válidas
- Resolución 601-604 por coincidencia exacta sin fallback a padre

---

## Riesgos

- Requiere bench migrate + bench build al deployar en producción
- Issue #186: IEPS combustibles — pendiente investigación
