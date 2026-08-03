# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-08-03
**Rama activa:** `fix/ffm-tipo-nc-derivado-simetrico`
**Tarea actual:** PR #222 — corrección de permisos de cancelación de Sales Invoice (estado inválido `cancel=1, submit=0`) detectada durante instalación de HRMS.

---

## Recuperación rápida

Estoy trabajando en:

Cierre de la revisión de CodeRabbit del PR #222. Se corrigen los comentarios #2 (doc), #3/#4 (CONTINUITY/MD022) y #5 (`NoReturn`). El comentario #1 (test que mockea `frappe.get_doc`) se difirió al issue #223.

Plan que estoy siguiendo:

Instrucciones directas del usuario para cerrar la revisión. PR #222 abierto; merge lo hace el usuario.

Objetivo inmediato:

Commit de las correcciones de revisión → push para actualizar el PR #222 → re-ejecutar `/ship coderabbit`.

Criterio de avance:

CodeRabbit sin comentarios accionables pendientes salvo el #1 (que vive en el issue #223); suite en verde; docs consistente con el código.

---

## Estado actual

### Ya cerrado

- PR **#222** abierto (base `main`), rama publicada en `upstream`. Versión objetivo `1.3.1` (PATCH).
- Botón fiscal + aviso RFC: `can_stamp` excluye `has_active_ffm` **y** `has_draft_ffm`; guard `frm.__fm_can_stamp` en `add_timbrar_button`; aviso RFC gateado por `can_stamp`.
- Doc de usuario `docs/usuario/notas-credito.md` (en nav de MkDocs).
- CodeRabbit revisado (reporte en `frappe-infrastructure/checkpoints/coderabbit-pr222-review.md`).
- CodeRabbit #2/#3/#4/#5 atendidos y commiteados (`e856671`); #1 diferido al issue #223.

### En progreso

- Permisos Sales Invoice: `Facturacion Mexico Manager` y `System Manager` pasan a `submit=1, cancel=1`
  (antes `cancel=1, submit=0`, inválido en Frappe). Corregido en `fixtures/docperm.json` y en la
  segunda fuente `api/fiscal_operations.py::assign_facturacion_permissions()`. Test de fixture
  agregado (`test_docperm_sales_invoice_permissions.py`). La lógica de cancelación no cambia.

### Pendiente inmediato

1. Commit + push de las correcciones → actualizar PR #222.
2. Re-ejecutar `/ship coderabbit` para confirmar el estado.
3. Merge: lo realiza el usuario (Squash & Merge). No lo hace Claude.

### No repetir

- No usar `git restore/reset/revert/checkout` para deshacer trabajo.
- No reintroducir la regresión: `can_stamp` debe excluir `has_active_ffm` Y `has_draft_ffm`.
- No meter conocimiento de FFM dentro de la validación RFC.
- No tocar `redirect_to_fiscal_document` ni su query.
- No atender el comentario #1 dentro del PR #222 (vive en el issue #223): no tocar `_derivar`, sus mocks ni la carga por `frappe.get_doc`, ni añadir costura de pruebas a producción.

---

## Decisiones vigentes

- El comentario #1 de CodeRabbit (mock de `frappe.get_doc` en `TestClasificacionNotaCredito`) se difiere al issue **#223**: `_classify_nota_credito` carga la SI/origen con `frappe.get_doc` directo; no se añade costura productiva ni infraestructura pesada dentro de este PR.
- El flujo de descuento **conserva el `item_code` original** (ERPNext `validate_returned_items` lo exige); solo cambia `description` («Descuento - \<original\>»), `income_account` y `update_stock=0`. La doc se corrigió acorde.
- Fuente autoritativa de visibilidad del botón = `can_stamp` (servidor).

---

## Archivos relevantes ahora

### Leer primero

- `docs/usuario/notas-credito.md` (corrección #2)
- `facturacion_mexico/facturacion_fiscal/doctype/factura_fiscal_mexico/factura_fiscal_mexico.py` (`NoReturn`, #5)

### No tocar

- `facturacion_mexico/facturacion_fiscal/tests/test_nota_credito_descuento_relacion_01.py` (`TestClasificacionNotaCredito._derivar`) → reservado al issue #223.
- `redirect_to_fiscal_document` y su query en `sales_invoice.js`.

---

## Riesgos / cuidados

- `NoReturn` debe ser el único cambio en Python de esta ronda (sin tocar lógica ni mensajes).
- Mantener `docperm.json` limpio y no incluir untracked de `one_offs/` / `working_docs/`.

---

## Información faltante

- Ninguna pendiente para esta ronda; tras el push, confirmar la nueva revisión de CodeRabbit.
