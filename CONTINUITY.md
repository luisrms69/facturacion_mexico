# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-08
**Rama activa:** `fix/cfdi-recibidos-department-grupos`
**Tarea actual:** PR abierto — fix departamentos grupo en CFDI Recibidos

---

## Recuperación rápida

Estoy trabajando en:
Fix de 5 filtros `is_group=0` que impedían seleccionar departamentos grupo
en el módulo CFDI Recibidos. PR abierto para revisión y merge.

Plan que estoy siguiendo:
Issue surgido en reunión con cliente — departamentos RRHH tipo grupo deben
poder mapearse en Configuración CFDI Recibidos.

Objetivo inmediato:
Merge del PR → bench update en producción → validar con cliente.

Criterio de avance:
Departamentos grupo visibles en Configuración CFDI Recibidos y en modal
"Asignar Departamentos" en lista de CFDI Recibidos.

---

## Estado actual

### Ya cerrado
- ✅ PR #185 mergeado — fix install + wizard IVA 0% + addendas + crash migrate
- ✅ acg-v16.dev configurado completo (CoA, fiscal, 119 items, La Comer)

### En progreso
- PR fix/cfdi-recibidos-department-grupos — 1 commit, abierto

### Pendiente inmediato
1. Merge del PR
2. bench update + migrate + build en producción (actiglobal)
3. Restore ACG en producción (pendiente desde sesión anterior)

### No repetir
- Había 5 puntos con is_group=0 para Department — todos corregidos
- cost_center, item_group, account, supplier_group mantienen is_group=0

---

## Decisiones vigentes

- Department en CFDI Recibidos es llave interna para 601-604, NO se traslada a PI
- PI recibe solo cuentas contables hoja válidas
- Resolución 601-604 por coincidencia exacta sin fallback a padre
- is_your_company_address workaround ERPNext 16.21.1 — mantener hasta que ERPNext lo declare

---

## Riesgos

- bench migrate requerido post-merge (mapeo_departamento_cfdi_recibido.json cambió)
- bench build requerido post-merge (cfdi_recibido.js y cfdi_recibido_list.js cambiaron)
- Issue #186: IEPS combustibles — aún pendiente
