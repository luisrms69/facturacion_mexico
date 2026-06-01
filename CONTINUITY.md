# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-01
**Rama activa:** `feature/addenda-la-comer`
**Tarea actual:** Addenda La Comer — template Jinja2 pendiente

---

## Recuperación rápida

Estoy trabajando en:
Arquitectura addendas completada (3 commits). Todos los datos EDI viven en Customer
y Address. Pendiente: poblar Customer La Comer en BD y crear el template Jinja2.

Objetivo inmediato:
Poblar Customer La Comer con fm_seller_gln/fm_seller_id/fm_invoice_creator_gln,
luego crear el template XML Jinja2 en Addenda Type "La Comer".

---

## Estado actual

### Ya cerrado
- PR #172 + docs + eliminación Single + arquitectura addendas (3 commits ✅)
- Addenda Type = template puro, sin IDs de empresa
- Customer = fuente única de todos los IDs EDI
- Address (shipping) = fuente del GLN de tienda destino (fm_gln)
- Company primary address = fuente del CP emisor

### Pendiente inmediato
1. Poblar BD: Customer La Comer → fm_seller_gln, fm_seller_id, fm_invoice_creator_gln
2. Crear template Jinja2 en Addenda Type "La Comer"
3. Company address para emisor_cp

### No repetir
- No poner seller_gln en Addenda Type — van en Customer
- No buscar emisor_cp en Configuracion Fiscal Mexico — tabla no existe

---

## Archivos relevantes ahora
- `facturacion_mexico/addendas/generic_addenda_generator.py`
- `working_docs/active/addenda_la_comer_evidencia/` — XML ejemplo + spec

---

## Riesgos / cuidados
- Company address no configurada en site dev — emisor_cp retornará ""
- Se crea este commit de manera precautoria, dado que claude code ha demostrado ser
  un riesgo para el código no committed y resulta peligroso mantener código de manera
  local dado su comportamiento errático
