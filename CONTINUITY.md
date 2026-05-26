# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-26
**Rama activa:** `feature/cfdi-recibidos-fase3-pi`
**Tarea actual:** C.1 + Item Groups commiteados — pendiente validación GUI antes de PR

---

## Recuperación rápida

Estoy trabajando en:
Módulo CFDI Recibidos — flujo de recepción de facturas de proveedores.

Plan que estoy siguiendo:
`docs/development/PLAN_ACTUAL_CFDI_RECIBIDOS.md` — fuente única vigente.
**No usar ningún otro documento de `docs/development/` como guía. Todos los demás son obsoletos.**
⚠️ Este archivo necesita actualización pronto — refleja Hito B como último cerrado; ya están cerrados C.1 e Item Groups.

Objetivo inmediato:
Validación GUI de C.1 e Item Groups → abrir PR → diseño Hito C.2.

Criterio de avance:
GUI validada (PT asignado, banner visible, Item Groups visibles) → PR abierto → recién entonces C.2.

---

## Estado actual

### Ya cerrado
- **Hito A** — Upload → Proveedor (`7c6b44f`)
- **Hito B** — Generar proveedores faltantes (`ac318a7`)
- **Hito C.1** — Defaults de proveedor y Payment Terms FM (`40638d5`)
- **Item Groups gastos SAT** — 96 grupos creados, carga idempotente (`82e9849`)

### En progreso
- Nada. Todos los hitos están commiteados.

### Pendiente inmediato
1. Actualizar `docs/development/PLAN_ACTUAL_CFDI_RECIBIDOS.md` — refleja estado desactualizado (Hito B como último).
2. Validación GUI de C.1: configurar template en `Configuracion CFDI Recibidos`,
   subir XML, generar proveedor, confirmar PT asignado y banner visible.
3. Validación GUI de Item Groups: verificar árbol "Gastos" en `facturacion-v16.dev`.
4. Abrir PR de `feature/cfdi-recibidos-fase3-pi` hacia `main`.
5. Diseño Hito C.2: decisiones sobre Supplier Group, asignación de Item Group a ítems/proveedores,
   Item Tax Template por concepto.

### No repetir
- No usar planes viejos de `docs/development/` — solo `PLAN_ACTUAL_CFDI_RECIBIDOS.md` es vigente
- No avanzar a clasificación de conceptos ni Purchase Invoice sin decisión explícita de Hito C
- No tocar TaxResolver, PurchaseInvoiceBuilder, Items
- No poner campos de CFDI Recibidos en `Configuracion Fiscal Mexico` — esa config es para impuestos de ventas

---

## Decisiones vigentes

- Campo `default_payment_terms_supplier` vive en `Configuracion CFDI Recibidos` (no en CFM)
- `Payment Terms Template` en ERPNext no tiene campo `company` — no se puede filtrar por empresa
- `ensure_default_payment_terms()` y `ensure_cfdi_received_expense_item_groups()` se llaman en `after_install`;
  en sites existentes ejecutar manualmente con `bench execute`
- Item Groups: paraguas "Gastos" → 11 categorías padre → 84 subcategorías (sin números SAT en nombres)
- Linters: `ruff check` + `ruff format` antes de commit; `prettier@2.7.1` exacto para JS

---

## Archivos relevantes ahora

### Leer primero
- `docs/development/PLAN_ACTUAL_CFDI_RECIBIDOS.md` — plan vigente, pero desactualizado (ver arriba)

### Probablemente editar (próximo hito)
- A definir en Hito C.2 — no hay archivos activos hasta que haya decisión

### No tocar
- `concept_classifier.py`, `tax_resolver.py`, `purchase_invoice_builder.py`
- `docs/development/` — todos los archivos excepto `PLAN_ACTUAL_CFDI_RECIBIDOS.md` son obsoletos

---

## Riesgos / cuidados
- `one_offs/` tiene ~16 scripts untracked — no commitear nunca
- `docs/development/` tiene varios REPORTE_*.md untracked — no commitear
- Validación GUI de C.1 e Item Groups no completada todavía (pendiente del usuario)
- Hito C prohíbe explícitamente código hasta tener decisiones de diseño aprobadas

---

## Configuración de desarrollo

| Ítem | Valor |
|---|---|
| Bench | `/home/erpnext/frappe-bench-v16` |
| Site desarrollo | `facturacion-v16.dev` |
| Site tests | `test-facturacion.localhost` |
| Seed tests | `bench --site test-facturacion.localhost execute facturacion_mexico.tests.ci_pre_tests.run` |
| Tests C.1 | `bench --site test-facturacion.localhost run-tests --module facturacion_mexico.cfdi_recibidos.tests.test_supplier_resolver --lightmode` |
| Tests setup | `bench --site test-facturacion.localhost run-tests --module facturacion_mexico.tests.test_setup_payment_terms --lightmode` |
| Tests Item Groups | `bench --site test-facturacion.localhost run-tests --module facturacion_mexico.tests.test_setup_expense_item_groups --lightmode` |
