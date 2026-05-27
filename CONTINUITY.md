# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-26
**Rama activa:** `feature/issue151-cfdi-recibidos-fase2`
**Tarea actual:** C.2 cerrado — flujo Upload → Proveedor → Department completo. Próximo: PR hacia main.

---

## Recuperación rápida

Estoy trabajando en:
Módulo CFDI Recibidos — flujo de recepción de facturas de proveedores.

Plan que estoy siguiendo:
`docs/development/PLAN_ACTUAL_CFDI_RECIBIDOS.md` — fuente única vigente.
**No usar ningún otro documento de `docs/development/` como guía. Todos los demás son obsoletos.**

Objetivo inmediato:
Abrir PR de `feature/issue151-cfdi-recibidos-fase2` hacia `main`.
El alcance del PR: Upload XML → Proveedor resuelto → Department asignado.

Próximo bloque (post-PR):
Creación de PI — requiere revisión arquitectónica completa de TaxResolver y PIBuilder antes de implementar.

---

## Estado actual

### Ya cerrado
- **Hito A** — Upload → Proveedor (`7c6b44f`)
- **Hito B** — Generar proveedores faltantes (`ac318a7`)
- **Hito C.1** — Configuracion CFDI Recibidos + defaults proveedor + Payment Terms (`40638d5`)
- **Item Groups gastos SAT** — 96 grupos creados, carga idempotente (`82e9849`)
- **Hito C.2** — Department assignment: campo, status, endpoints, GUI, 23 tests ✅

### En progreso
- Nada. Todo está commiteado. Pendiente abrir PR.

### Pendiente inmediato
1. Abrir PR de `feature/issue151-cfdi-recibidos-fase2` hacia `main` via `/ship pr`.

### No repetir
- No usar planes viejos de `docs/development/` — solo `PLAN_ACTUAL_CFDI_RECIBIDOS.md` es vigente
- No avanzar a creación de PI sin decisión arquitectónica explícita (TaxResolver + PIBuilder)
- No tocar `tax_resolver.py`, `purchase_invoice_builder.py` hasta revisión aprobada
- No poner campos de CFDI Recibidos en `Configuracion Fiscal Mexico` — esa config es para impuestos de ventas
- Código existente en la rama (PIBuilder, TaxResolver, clasificación) NO está validado — no mencionar como cerrado

---

## Decisiones vigentes

- Campo `default_payment_terms_supplier` vive en `Configuracion CFDI Recibidos` (no en CFM)
- `Payment Terms Template` en ERPNext no tiene campo `company` — no se puede filtrar por empresa
- `ensure_default_payment_terms()` y `ensure_cfdi_received_expense_item_groups()` se llaman en `after_install`;
  en sites existentes ejecutar manualmente con `bench execute`
- Item Groups: paraguas "Gastos" → 11 categorías padre → 84 subcategorías (sin números SAT en nombres)
- `compute_stage` evalúa: supplier → department → clasificación conceptos → Listo (en ese orden)
- Department assignment valida contra `Configuracion CFDI Recibidos.mapeo_departamentos` de la empresa
- Linters: `ruff check` + `ruff format` antes de commit; `prettier@2.7.1` exacto para JS

---

## Archivos relevantes ahora

### Leer primero
- `docs/development/PLAN_ACTUAL_CFDI_RECIBIDOS.md` — plan vigente

### Módulo CFDI Recibidos — archivos principales
- `facturacion_mexico/cfdi_recibidos/api.py` — endpoints públicos
- `facturacion_mexico/cfdi_recibidos/services/status_manager.py` — compute_stage
- `facturacion_mexico/cfdi_recibidos/doctype/cfdi_recibido/cfdi_recibido_list.js` — GUI List View
- `facturacion_mexico/cfdi_recibidos/doctype/cfdi_recibido/cfdi_recibido.json` — schema

### Tests C.2
- `facturacion_mexico/cfdi_recibidos/tests/test_department_assignment.py` — 15 tests
- `facturacion_mexico/cfdi_recibidos/tests/test_department_mapping.py` — 8 tests

### No tocar (código existe, no validado)
- `concept_classifier.py`, `tax_resolver.py`, `purchase_invoice_builder.py`
- `docs/development/` — todos los archivos excepto `PLAN_ACTUAL_CFDI_RECIBIDOS.md` son obsoletos

---

## Riesgos / cuidados
- `one_offs/` tiene ~16 scripts untracked — no commitear nunca
- `docs/development/` tiene varios REPORTE_*.md untracked — no commitear
- Código de PIBuilder y TaxResolver existe en la rama pero NO está validado; no incluir en alcance del PR actual
- `REPORTE_INVESTIGACION_SAT_CFDI_RECIBIDOS.md` documenta problemas arquitectónicos en TaxResolver — leer antes de tocar ese módulo

---

## Configuración de desarrollo

| Ítem | Valor |
|---|---|
| Bench | `/home/erpnext/frappe-bench-v16` |
| Site desarrollo | `facturacion-v16.dev` |
| Site tests | `test-facturacion.localhost` |
| Seed tests | `bench --site test-facturacion.localhost execute facturacion_mexico.tests.ci_pre_tests.run` |
| Tests C.2 dept assignment | `bench --site test-facturacion.localhost run-tests --module facturacion_mexico.cfdi_recibidos.tests.test_department_assignment --lightmode` |
| Tests C.2 dept mapping | `bench --site test-facturacion.localhost run-tests --module facturacion_mexico.cfdi_recibidos.tests.test_department_mapping --lightmode` |
| Tests C.1 supplier | `bench --site test-facturacion.localhost run-tests --module facturacion_mexico.cfdi_recibidos.tests.test_supplier_resolver --lightmode` |
| Tests Item Groups | `bench --site test-facturacion.localhost run-tests --module facturacion_mexico.tests.test_setup_expense_item_groups --lightmode` |
