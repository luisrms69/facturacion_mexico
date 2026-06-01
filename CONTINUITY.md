# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-01
**Rama activa:** `feature/addenda-la-comer`
**Tarea actual:** Eliminando Facturacion Mexico Settings Single + arquitectura addendas

---

## Recuperación rápida

Estoy trabajando en:
Tres commits en curso. Commit 1 (docs PR #172) hecho. Pendientes commit 2
(eliminación Single) y commit 3 (arquitectura addendas Customer/Address).

Plan que estoy siguiendo:
Rama `feature/addenda-la-comer`. Trabajo directo en rama.

Objetivo inmediato:
Completar commits 2 y 3, luego retomar template Jinja2 de La Comer.

Criterio de avance:
3 commits limpios en rama. Tests pasan.

---

## Estado actual

### Ya cerrado
- PR #172: Facturacion Mexico Company Settings
- Docs PR #172: arquitectura.md, getting-started.md, ADR-0031 (commit 1 ✅)

### Pendiente inmediato
1. Commit 2: eliminación Facturacion Mexico Settings Single
2. Commit 3: arquitectura addendas (Customer/Address como fuente de datos EDI)
3. Poblar Customer La Comer con fm_seller_gln, fm_seller_id, fm_invoice_creator_gln
4. Template Jinja2 en Addenda Type "La Comer"

### No repetir
- No buscar datos en Facturacion Mexico Settings — eliminado
- No poner seller_gln en Addenda Type — van en Customer

---

## Archivos relevantes ahora
- `facturacion_mexico/addendas/generic_addenda_generator.py`
- `facturacion_mexico/fixtures/custom_field.json`

---

## Riesgos / cuidados
- Commit 2 y 3 pendientes — no hacer PR hasta tener los 3 commits
- Company address no configurada en site dev — emisor_cp retornará ""
