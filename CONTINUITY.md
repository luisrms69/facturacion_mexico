# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-01
**Rama activa:** `feature/addenda-la-comer`
**Tarea actual:** Addenda La Comer — prueba completa exitosa, pendiente PR

---

## Recuperación rápida

Estoy trabajando en:
La prueba completa de addenda La Comer fue exitosa (FFMX-2026-00034). El XML generado
coincide con la referencia en todos los campos principales. Pendiente: hacer el PR.

Objetivo inmediato:
Abrir PR con todos los commits de esta rama.

Criterio de avance:
PR abierto, CI verde.

---

## Estado actual

### Ya cerrado
- Arquitectura addendas completa: datos EDI en Customer/Address/Company ✅
- importe_letras automático con num2words ✅
- fm_customer_uom + fm_customer_description en Item Customer Detail ✅
- Fix tasa 0% ObjetoImp=02 ✅
- Fix get_decrypted_password en api_client ✅
- Fix invoice.items con SimpleNamespace ✅
- Subgrupos fiscales (38 subgrupos) ✅
- Limpieza código muerto (Addenda Configuration, Addenda Product Mapping refs) ✅
- Docs: addendas.md reescrito, getting-started.md actualizado ✅
- Prueba real exitosa: FFMX-2026-00034 ✅

### Pendiente inmediato
1. PR con todos los commits de la rama
2. Capturar fm_customer_description = "ALBAHACAR   1 PZA" en ALBAHACA-PZA (dato en GUI)

### No repetir
- No usar frappe.db.get_value para campos Password — usar get_decrypted_password
- No pasar invoice como frappe._dict al template — usar SimpleNamespace
- No usar export-fixtures sin autorización explícita
- No usar git checkout sin autorización explícita

---

## Archivos relevantes ahora
- `facturacion_mexico/addendas/generic_addenda_generator.py`
- `facturacion_mexico/facturacion_fiscal/api_client.py`

---

## Riesgos / cuidados
- Addenda Configuration y Addenda Product Mapping DocTypes siguen en repo (archivos JSON/py)
  pero sin referencias activas — eliminarlos en PR separado futuro
- shipTo.city = "CDMX" vs "MEXICO DF" — dato de Address, corregir en GUI si aplica
