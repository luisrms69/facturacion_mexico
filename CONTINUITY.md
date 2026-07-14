# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-07-13
**Rama activa:** `fix/customer-docname-safe-lookups`
**Tarea actual:** Fix — lookups de Customer en JS fallan cuando el docname tiene caracteres especiales (comillas)

---

## Recuperación rápida

Estoy trabajando en:
Corrección del defecto reportado en LlantasCS: el cliente `"LOGISTICA Y TRANSPORTE MAXMEX"`
(RFC LTM220809E5A) — con comillas dobles como parte del docname — no permitía timbrar la SI,
mostrando falsamente "el RFC del cliente no está validado con SAT" aunque `fm_rfc_validated=1`.
Causa raíz: el JS leía Customer con `frappe.db.get_value("Customer", frm.doc.customer, …)`
pasando el docname como string suelto; en el servidor `get_safe_filters`/orjson interpreta el
nombre entre comillas como JSON y le quita las comillas → no encuentra al cliente. Fix: filtro
explícito `{ name: … }`.

Plan que estoy siguiendo:
Fix de defecto + eliminación de duplicación JS (instrucción del usuario: no limitar a las 3
llamadas; barrer toda la app, consolidar lógica duplicada, agregar tests de regresión).

Objetivo inmediato:
Commit hecho en esta rama (solo commit; sin push). Siguiente paso lo decide el usuario
(push / PR).

Criterio de avance:
Tests verdes (10/10) + linters limpios + diff sin cambios funcionales colaterales.

---

## Estado actual

### Ya cerrado
- Diagnóstico probado: `get_safe_filters`/orjson mutila docnames JSON-parseables (envueltos
  en comillas). Verificado contra `llantascs-v16.dev` (docname real con comillas, `fm_rfc_validated=1`).
- App afectada confirmada: `facturacion_mexico` (provee el JS vía `doctype_js`). `facturacion_mx`
  NO afectada (hooks JS comentados, sin el código) — no se toca.
- 6 call-sites vulnerables corregidos a filtro `{ name }` (2 en `factura_fiscal_mexico.js`,
  4 en `sales_invoice.js`).
- Consolidación JS: 2 handlers `customer` duplicados → `apply_customer_defaults(frm)`;
  eliminado `has_customer_rfc` (doble round-trip); `_check_rfc_and_show_timbrar` hace 1 sola
  lectura `{name}` de `tax_id`+`fm_rfc_validated`; eliminado handler `cost_center` duplicado
  redundante (CC-B); alerta roja de error preservada; `.catch` de paridad.
- 2 tests nuevos: dinámico (borde servidor `frappe.client.get_value`) 6/6 + estático (guarda
  del código JS contra reintroducir string suelto) 4/4.
- Linters: prettier@2.7.1 (versión del CI — v3 mete trailing commas espurias), eslint 8.44.0,
  ruff — todos limpios. `git diff --check` OK.

### En progreso
- Commit en `fix/customer-docname-safe-lookups`.

### Pendiente inmediato
1. Decisión del usuario: push / PR.
2. Validación GUI del botón Timbrar con el cliente de comillas (los tests NO cubren el JS en
   navegador — solo el borde servidor y la forma del código fuente).

### No repetir
- NO usar `npx prettier` sin fijar `@2.7.1` — la v3 reformatea trailing commas y ensucia el diff.
- NO correr `bench run-tests --app … --module …`: el combo ignora el filtro y corre la suite
  completa. Usar solo `--module` (sin `--app`).
- NO correr tests de este app sin el seed `facturacion_mexico.tests.ci_pre_tests.run` + `--lightmode`.
- NO tocar `facturacion_mx` — no está afectada.

---

## Decisiones vigentes
- Todo lookup de Customer desde JS debe usar filtro dict `{ name: customer }`, nunca el docname
  como string suelto. La API Python `frappe.db.get_value` es inmune (param-binding); el defecto
  es exclusivo del borde HTTP `frappe.client.get_value` (que pasa por `get_safe_filters`/orjson).
- El servidor mantiene su validación fiscal independiente e inmune a comillas (usa
  `getattr(customer_doc,…)` y SQL parametrizado).
- Consolidación permitida solo donde había duplicación real de lógica de negocio; no crear
  abstracción genérica que envuelva `get_value`.

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/public/js/sales_invoice.js` — `apply_customer_defaults`,
  `_check_rfc_and_show_timbrar`, handler `cost_center` (CC-A).
- `facturacion_mexico/facturacion_fiscal/doctype/factura_fiscal_mexico/factura_fiscal_mexico.js`
  — lookups `fm_uso_cfdi_default`, `fm_allow_generic_rfc`.

### Probablemente editar
- (ninguno — fix cerrado, salvo feedback de revisión/PR)

### No tocar
- `facturacion_mexico/one_offs/*` — nunca commitear
- `working_docs/active/*` — no van en este fix
- `facturacion_mx` (otra app) — no afectada

---

## Riesgos / cuidados
- Los tests dinámicos requieren las instancias Redis del bench (13001 cache / 11001 queue) y el
  seed `ci_pre_tests.run`; sin Redis fallan en el bootstrap de test-records de erpnext.
- La cobertura de tests NO incluye el JS en navegador: si alguien revierte el JS a string suelto,
  el test dinámico seguiría verde — por eso existe el test estático que sí lo detecta.
