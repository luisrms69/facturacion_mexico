# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-01
**Rama activa:** `feature/addenda-la-comer`
**Tarea actual:** Addenda La Comer — template Jinja2 pendiente

---

## Recuperación rápida

Estoy trabajando en:
Tab "Fiscal México" en Customer completado. Pendiente: template Jinja2 de La Comer
y poblar Company address para emisor_cp.

Objetivo inmediato:
Crear template XML Jinja2 en Addenda Type "La Comer".

---

## Estado actual

### Ya cerrado
- Tab "Fiscal México" en Customer: fm_envio_email_cliente, fm_allow_generic_rfc,
  sección Addendas (commit ✅)
- Eliminación Single Facturacion Mexico Settings (commit ✅)
- Arquitectura addendas: datos EDI en Customer/Address (commit ✅)
- Docs PR #172 (commit ✅)

### Pendiente inmediato
1. Template Jinja2 en Addenda Type "La Comer"
2. Company address en site dev para emisor_cp
3. PR con todos los commits de esta rama

### No repetir
- No correr export-fixtures sin autorización explícita
- No usar git checkout sin autorización explícita

---

## Archivos relevantes ahora
- `facturacion_mexico/addendas/generic_addenda_generator.py`
- `working_docs/active/addenda_la_comer_evidencia/` — XML ejemplo + spec

---

## Riesgos / cuidados
- Company address no configurada en site dev — emisor_cp retornará ""
