# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-08-03
**Rama activa:** `fix/ffm-tipo-nc-derivado-simetrico`
**Tarea actual:** Documentación de usuario del flujo de Notas de Crédito (Descuento/Bonificación ↔ Devolución) + botones fiscales.

---

## Recuperación rápida

Estoy trabajando en:
Documentación de usuario del flujo de Notas de Crédito. El fix del botón fiscal + aviso RFC ya está commiteado (`3e22101`) y pusheado a `upstream`. Esta tarea agrega la página de usuario `docs/usuario/notas-credito.md`.

Plan que estoy siguiendo:
Instrucciones directas del usuario. El PR de la rama está preparado pero NO creado aún (pendiente de autorización).

Objetivo inmediato:
Commit documental (`docs/usuario/notas-credito.md` + `mkdocs.yml` + este CONTINUITY.md). Después, el usuario decide crear el PR (`/ship pr` ya validado: base main, versión 1.3.1 PATCH).

Criterio de avance:
`can_stamp=false` para FFM activa/timbrada Y para FFM Draft; `can_stamp=true` solo sin FFM y con condiciones normales; aviso RFC visible solo cuando `can_stamp=true`.

---

## Estado actual

### Ya cerrado
- `can_stamp` en `_compute_actions` excluye AMBAS: `has_active_ffm` (restaurada) y `has_draft_ffm` (nueva). Nuevo fact `has_draft_ffm = ffm.docstatus == 0`.
- `sales_invoice.js`: guard choke-point en `add_timbrar_button` (`frm.__fm_can_stamp`); `_check_rfc_and_show_timbrar` gatea el aviso por `can_stamp` y trata RFC vacío/no-validado con el mismo aviso.
- Tests aditivos de sesión (no se tocó ninguno previo). Validación GUI de 5 escenarios RFC/FFM + NC descuento OK.

### En progreso
- (nada abierto tras el commit)

### Pendiente inmediato
1. Esperar decisión del usuario sobre push/PR.
2. "Escenario B" (quitar la llamada ungated `_check_rfc_and_show_timbrar` en `sales_invoice_block_cancel.js`) — NO autorizado; no ejecutar sin orden explícita.
3. Versionado: el bump SemVer se valida al crear el PR (contra `upstream/main`), no en el commit.

### No repetir
- No usar `git restore/reset/revert/checkout` para deshacer trabajo.
- No reintroducir la regresión: `can_stamp` debe excluir `has_active_ffm` Y `has_draft_ffm` (no sustituir una por otra).
- No meter conocimiento de FFM dentro de la validación RFC.
- No tocar `redirect_to_fiscal_document` ni su query.

---

## Decisiones vigentes
- Fuente autoritativa de visibilidad del botón = `can_stamp` (servidor). El JS solo dibuja si `can_stamp=true` (guard en `add_timbrar_button`).
- FFM en ERROR es `docstatus=0` → cuenta como Draft → bloquea "Crear" (se reintenta abriendo la FFM). Confirmado como comportamiento deseado.
- El snapshot `Sales Invoice.fm_fiscal_status` puede quedar desincronizado; por eso `can_stamp` NO puede depender solo de `fiscal_status`, necesita `has_active_ffm`.

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/fiscal_state/sales_invoice_state.py` (`_compute_facts`, `_compute_actions`)
- `facturacion_mexico/public/js/sales_invoice.js` (`_check_rfc_and_show_timbrar`, `add_timbrar_button`, callback de `get_fiscal_ui_state`)

### Probablemente editar
- `facturacion_mexico/public/js/sales_invoice_block_cancel.js` (solo si se autoriza el "escenario B")

### No tocar
- `redirect_to_fiscal_document` y su query en `sales_invoice.js`
- tests preexistentes en `tests/test_fiscal_state_sales_invoice.py`

---

## Riesgos / cuidados
- `_check_rfc_and_show_timbrar` se llama desde `sales_invoice.js` (gateado por can_stamp) y desde `block_cancel.js` (sin gate) → la coherencia se sostiene con el guard + el gate `frm.__fm_can_stamp` dentro del `.then`.
- `clear_primary_action()` incondicional en el callback: pendiente evaluar si podría borrar acciones primarias estándar de ERPNext (riesgo señalado, no confirmado).

---

## Información faltante
- Decisión del usuario sobre push/PR y sobre el "escenario B".
