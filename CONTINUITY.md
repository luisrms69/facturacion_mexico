# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-01
**Rama activa:** `feature/addenda-la-comer`
**Tarea actual:** Arquitectura addendas — datos EDI en Customer/Address

---

## Recuperación rápida

Estoy trabajando en:
Single Facturacion Mexico Settings eliminado (commit 2 ✅). Pendiente commit 3:
arquitectura addendas con Customer/Address como fuente de datos EDI.

Objetivo inmediato:
Commit 3 de arquitectura addendas, luego poblar Customer La Comer y crear template Jinja2.

---

## Estado actual

### Ya cerrado
- PR #172 + docs (commits 1 y 2 ✅)
- Facturacion Mexico Settings Single: eliminado de código y BD

### Pendiente inmediato
1. Commit 3: arquitectura addendas
2. Poblar Customer La Comer: fm_seller_gln, fm_seller_id, fm_invoice_creator_gln
3. Template Jinja2 en Addenda Type "La Comer"

### No repetir
- No buscar datos en Facturacion Mexico Settings — eliminado completamente

---

## Archivos relevantes ahora
- `facturacion_mexico/addendas/generic_addenda_generator.py`
- `facturacion_mexico/fixtures/custom_field.json`

---

## Riesgos / cuidados
- Commit 3 pendiente — no hacer PR hasta tenerlo
- Company address no configurada en site dev — emisor_cp retornará ""
