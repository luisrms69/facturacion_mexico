# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-29
**Rama activa:** `fix/xml-ingestion-paso7-restore`
**Tarea actual:** Restaurar Paso 7 de xml_ingestion + actualizar tests

---

## Recuperación rápida

Rama de fix para restaurar el auto-creado de proveedor en upload (Paso 7),
eliminado incorrectamente en commit 500a683 para pasar tests.
Tests actualizados para reflejar comportamiento correcto.

Pendiente: PR → merge a main.

---

## Estado actual

### Completado en esta sesión
- Paso 7 restaurado en xml_ingestion.py con compute_stage para avanzar pipeline
- 5 tests actualizados en test_xml_ingestion.py
- test-guard.md actualizado en frappe-infrastructure con regla absoluta
- sync-check.md actualizado con 3 reglas nuevas

### Pendiente
- PR de fix/xml-ingestion-paso7-restore → main
- Issue #165: is_submittable para CFDI Recibido
- 6 docs pendientes de verificación ADR en docs/development/
- 2 cambios en supplier_resolver.py aún no restaurados:
  - generate_missing_suppliers: "Proveedor encontrado" en lugar de "Falta departamento"
  - _assign_supplier: compute_supplier_stage en lugar de compute_stage
  (mitigados por el compute_stage al final de xml_ingestion, pero Hito B sigue diferente)

### No repetir
- NUNCA modificar comportamiento del app para pasar tests
- No incluir one_offs/ ni REPORTE_*.md en commits
- No hacer bench migrate sin autorización
- No commitear en main directamente

---

## Decisiones vigentes
- Paso 7 en xml_ingestion: auto-crear proveedor + compute_stage → "Falta departamento"
- item_resolution options canónicos con acentos correctos
- tax_resolver valida cuenta_impuesto no vacía
- classify_all_concepts solo auto-asigna "Código proveedor"

---

## Archivos relevantes ahora
- `facturacion_mexico/cfdi_recibidos/services/xml_ingestion.py` — Paso 7 restaurado
- `facturacion_mexico/cfdi_recibidos/tests/test_xml_ingestion.py` — tests actualizados
- frappe-infrastructure: test-guard.md y sync-check.md actualizados

---

## Riesgos / cuidados
- supplier_resolver.py tiene 2 cambios que afectan Hito B (List View "Generar proveedores faltantes")
- issue #165 (is_submittable) antes de producción
- api_backup.py escribe en /tmp/ — defecto pre-existente
