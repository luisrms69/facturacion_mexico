# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-01
**Rama activa:** `feature/addenda-la-comer`
**Tarea actual:** PR #173 abierto — esperando merge

---

## Recuperación rápida

Estoy trabajando en:
PR #173 abierto con soporte completo de addendas EDI + eliminación Single Settings.
Prueba real exitosa (FFMX-00032, 00033, 00034). Esperando CI y merge.

Objetivo inmediato:
Merge PR #173. Después: issue para eliminar Addenda Configuration y Addenda
Product Mapping DocTypes.

---

## Estado actual

### Ya cerrado en esta rama
- Arquitectura addendas: Customer/Address/Company como fuente de datos ✅
- importe_letras automático (num2words) ✅
- fm_customer_uom + fm_customer_description en Item Customer Detail ✅
- Fix tasa 0% ObjetoImp=02 ✅
- Fix get_decrypted_password + fallback company default ✅
- Fix invoice.items con SimpleNamespace ✅
- Tab "Fiscal México" en Customer ✅
- 38 subgrupos fiscales idempotentes ✅
- Eliminación Facturacion Mexico Settings Single ✅
- Limpieza código muerto (api.py, hooks_handlers) ✅
- Docs: addendas.md, getting-started.md, arquitectura.md, ADR-0031 ✅
- PR #173 abierto ✅

### Pendiente post-merge
1. Abrir issue: eliminar DocTypes Addenda Configuration y Addenda Product Mapping
2. Capturar fm_customer_description = "ALBAHACAR   1 PZA" en ALBAHACA-PZA (dato GUI)

### No repetir
- No usar frappe.db.get_value para campos Password — usar get_decrypted_password
- No pasar invoice como frappe._dict al template Jinja2 — usar SimpleNamespace
- No usar export-fixtures sin autorización explícita
- No usar git checkout sin autorización explícita

---

## Riesgos / cuidados
- Addenda Configuration y Addenda Product Mapping DocTypes siguen en repo
  sin referencias — eliminar en PR separado
- bench migrate requerido en todos los sites
