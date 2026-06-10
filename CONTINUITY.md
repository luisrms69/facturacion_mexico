# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-10
**Rama activa:** `fix/uom-legacy-y-precios-iva-incluido`
**Tarea actual:** PR abierto — UOM legacy + precios IVA incluido

---

## Recuperación rápida

Estoy trabajando en:
PR con dos fixes críticos para migración de sitios desde facturacion_mx:
1. Normalización de UOM legacy (H87 Pieza → H87) en payload fiscal
2. Soporte configurable para precios de venta con IVA incluido

Plan que estoy siguiendo:
Merge del PR → sync-check → continuar con configuración LlantasCS.

Objetivo inmediato:
Merge de este PR. Los dos cambios ya están probados en llantascs-v16.dev.

Criterio de avance:
main con ambos fixes. Timbrado funciona en sitios legacy y con precios IVA incluido.

---

## Estado actual

### Ya cerrado
- ✅ PR #185 — fix install + wizard + addendas
- ✅ PR #187 — fix departamentos grupo CFDI Recibidos
- ✅ PR #189 — fix workspace shortcuts + visual

### En progreso
- PR fix/uom-legacy-y-precios-iva-incluido — abierto

### Pendiente inmediato
1. Merge este PR
2. Configurar Cost Centers/Branches restantes en llantascs-v16.dev
3. Restore ACG producción (pendiente)
4. Issue #188 — Fase 2 workspace (KPIs, gráficas)

### No repetir
- UOM del payload usa net_rate (no rate) — correcto para ambos casos (con/sin IVA incluido)
- base_iva_unitaria también debe usar net_rate
- sales_prices_include_tax vive en Configuracion Fiscal Mexico, no en STCT directamente

---

## Decisiones vigentes

- Normalización UOM: primera fila antes de " - " o antes de espacio → código SAT
- "Pieza" sin prefijo código SAT falla (correcto — no es un código SAT válido)
- net_rate es siempre el valor correcto para el CFDI independientemente de included_in_print_rate

---

## Riesgos

- llantascs-v16.dev: Cost Centers sin Branch mapeado en otras sucursales (pendiente configurar)
- Issue #186: IEPS combustibles — pendiente investigación
