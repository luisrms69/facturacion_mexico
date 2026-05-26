# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-26
**Rama activa:** `feature/cfdi-recibidos-fase3-pi`
**Último commit funcional:** `7c6b44f feat(cfdi-recibidos): Hito A — Upload → Proveedor (UX por etapas)`

---

## Recuperación rápida

Estoy trabajando en:
Hito B — Generar proveedores faltantes (CFDI Recibidos)

Plan que estoy siguiendo:
`docs/development/PLAN_ACTUAL_CFDI_RECIBIDOS.md` — fuente única vigente.
**No usar ningún otro documento de `docs/development/` como guía.**

Objetivo inmediato:
Terminar implementación de Hito B, correr tests, validar GUI, luego commit.

Criterio de avance:
Tests pasan + validación GUI completa (8 pasos del plan) + sin código funcional pendiente.

---

## Estado actual

### Ya cerrado
- **Hito A** — Upload → Proveedor (`7c6b44f`, empujado a `upstream/feature/cfdi-recibidos-fase3-pi`)
- Limpieza documental de `docs/development/` (no commiteada — pendiente decidir)

### En progreso
- **Hito B** — Generar proveedores faltantes: implementación parcialmente hecha, pendiente correr tests y fix de prettier en JS

### Pendiente inmediato
1. Corregir formato JS con `prettier@2.7.1` en `cfdi_recibido_list.js`
2. Correr tests: `bench --site test-facturacion.localhost run-tests --module facturacion_mexico.cfdi_recibidos.tests.test_supplier_resolver --lightmode`
3. Validación GUI (8 pasos del plan)
4. Commit de Hito B
5. Decidir si commitear limpieza documental en mismo commit o separado

### No repetir
- No referenciar `docs/development/cfdi-recibidos-fase-3-purchase-invoice.md` — eliminado
- No usar planes viejos de `docs/development/` para decidir flujo
- No avanzar a clasificación de conceptos en este hito
- No usar TaxResolver, PurchaseInvoiceBuilder, PI, Payment Entry en Hito B

---

## Decisiones vigentes

- Flujo por etapas: una acción por hito, no flujo automático completo
- Upload termina solo en: `XML inválido`, `Duplicado`, `No aplicable`, `Proveedor encontrado`, `Falta proveedor`
- `generate_missing_suppliers` usa `_get_default_supplier_group()` — no hardcodea, detecta dinámicamente
- `Configuracion CFDI Recibidos` no tiene `default_supplier_group` ni `default_supplier_type` — fallback dinámico en código
- Linters: `ruff check` + `ruff format` antes de commit; `prettier@2.7.1` para JS

---

## Archivos relevantes ahora

### Leer primero
- `docs/development/PLAN_ACTUAL_CFDI_RECIBIDOS.md` — plan vigente Hito B

### Probablemente editar (Hito B en curso)
- `cfdi_recibidos/services/supplier_resolver.py` — `generate_missing_suppliers` ya escrito, pendiente tests
- `cfdi_recibidos/api.py` — endpoint `generate_missing_suppliers` ya agregado
- `cfdi_recibidos/doctype/cfdi_recibido/cfdi_recibido_list.js` — botón agregado, pendiente prettier
- `cfdi_recibidos/tests/test_supplier_resolver.py` — 8 tests nuevos escritos, pendiente ejecutar

### No tocar
- `concept_classifier.py`, `tax_resolver.py`, `purchase_invoice_builder.py`
- `xml_ingestion.py` (Hito A cerrado)
- `docs/development/` archivos históricos

---

## Riesgos / cuidados
- `prettier@2.7.1` exacto — CI usa esa versión; no usar v3
- No commitear `one_offs/` (14 scripts untracked, correctos)
- La limpieza documental (no commiteada) incluye archivos rastreados — al commitear Hito B, no incluirlos accidentalmente

---

## Configuración de desarrollo

| Ítem | Valor |
|---|---|
| Bench | `/home/erpnext/frappe-bench-v16` |
| Site desarrollo | `facturacion-v16.dev` |
| Site tests | `test-facturacion.localhost` |
| Seed tests | `bench --site test-facturacion.localhost execute facturacion_mexico.tests.ci_pre_tests.run` |
| Tests Hito B | `bench --site test-facturacion.localhost run-tests --module facturacion_mexico.cfdi_recibidos.tests.test_supplier_resolver --lightmode` |
