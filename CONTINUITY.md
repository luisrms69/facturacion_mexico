# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-07-30
**Rama activa:** `feat/nc-descuento-inventario-reversion`
**Tarea actual:** Robustez de la Nota de Crédito por descuento en la Sales Invoice Return (puntos 1-3). Listo para commit; falta autorización de commit + push + PR.

---

## Recuperación rápida

Estoy trabajando en:
Endurecimiento del flujo de **Nota de Crédito por descuento/bonificación**, acotado a la **Sales Invoice Return en borrador** (la FFM no participa). Tres cambios: (1) al «Aplicar como Descuento» se fuerza `update_stock = 0` (reversible desde `return_against.update_stock`); (2) guard que bloquea la conversión si `Enable Discount Accounting = ON`, sin apagar el setting global; (3) acción inversa «Revertir a Devolución de mercancía» que restaura `income_account`/`description`/`update_stock` **exactos desde el origen** (vía `sales_invoice_item`), fail-closed si una línea no mapea, y solo en borrador.

Plan que estoy siguiendo:
Puntos 1-3 de la revisión GUI post-#220. ADR `docs/adr/0025-notas-credito-cfdi-tipo-e-issue116.md`, sección «Robustez operativa descuento ⇄ devolución en SI Return».

Objetivo inmediato:
`/ship commit` → `/ship push` → `/ship pr` (base `main`), con autorización explícita en cada paso.

Criterio de avance:
Tests focalizados verdes (13 nuevos + acción/reversión) + ruff/prettier/mkdocs `--strict` limpios + diff contra `upstream/main` solo con archivos en alcance + bump `1.3.0`.

---

## Estado actual

### Ya cerrado
- Puntos 1-3 implementados (4 archivos: `api/nota_credito.py`, JS del botón, tests, ADR 0025).
- Bump `__version__` `1.2.0 → 1.3.0` (MINOR: nueva acción de reversión + endpoints).
- Rama `feat/nc-descuento-inventario-reversion` creada **desde `upstream/main`** (PR #220 ya mergeado; la rama vieja quedó obsoleta).
- PR #221 abierto (base `main`), CI verde.
- **CodeRabbit #221 #1/#2/#4 atendidos**: #1 ADR lista el guard Enable Discount Accounting; #2 `check_permission` en endpoints whitelisted (write en aplicar/revertir, read en estado y sobre el origen); #4 JS quita ambos botones antes de agregar el actual. + tests de permisos.

### En progreso
- Ninguna edición de código pendiente en este PR.

### Pendiente inmediato
1. Merge de PR #221 (lo hace el usuario) — tag `v1.3.0` + Release tras merge (con autorización).
2. PR independiente de puntos 4-5 (FFM).

### No repetir
- **NO** reutilizar la rama vieja `feat/nota-credito-descuento-relacion-01` (PR #220 ya mergeado por squash; PR desde ahí saldría sucio).
- **NO** tocar FFM en este PR: `fm_tipo_nota_credito`, derivación fiscal, visibilidad/textos → PR independiente de puntos 4-5.
- **NO** usar `discount_account` para la NC de descuento (invierte/infla el asiento).
- **NO** commitear `one_offs/` ni `working_docs/`.

---

## Decisiones vigentes
- La reversión descuento ⇄ devolución vive **solo en la SI Return en borrador**; la FFM no participa.
- El estado de la nota (qué botón mostrar) se decide por el **estado contable real** (`income_account == cuenta_descuentos`), no por la descripción.
- Reversión **fail-closed**: sin vínculo `sales_invoice_item` exacto → bloquea sin modificar.
- Precondición `Enable Discount Accounting = OFF` ahora **protegida por guard** en la acción (antes solo documentada).
- **FormaPago `15 - Condonación` (PUE)** para la NC de descuento está **confirmada por el contador** (ADR 0025). No es un pendiente. Lo que permanece abierto en #136 son otros escenarios tipo E (p. ej. `outstanding=0` que hereda `99`), no el de descuento.

---

## Archivos relevantes ahora

### Leer primero
- `docs/adr/0025-notas-credito-cfdi-tipo-e-issue116.md` (sección «Robustez operativa descuento ⇄ devolución»).

### Probablemente editar
- (ninguno; puntos 1-3 cerrados salvo hallazgos en review/CI).

### No tocar
- `facturacion_fiscal/timbrado_api.py`, `factura_fiscal_mexico.py`/`.js` (pertenecen al PR de puntos 4-5).

---

## Riesgos / cuidados
- **CodeRabbit #221 pendientes deliberados:** #3 (no mockear `frappe.get_doc` en tests — deuda RG-003; no se cambian firmas de código productivo solo por el mock) y #5 (helper DRY de botones JS — bajo valor).
- Pendientes para el PR independiente de puntos 4-5 (del review de #220): forzar TipoRelación 03 en `_set_tipo_from_context`, JS `fm_tipo_nota_credito` editable en `docstatus==2`, y `-> None` en `_set_tipo_from_context`.
- Fuera por bajo valor/alcance: #1 (rename RG-001), #3 (test integración del guard), #6 (IDs de mocks in-memory).

---

## Información faltante
- Confirmación normativa de otros escenarios FormaPago tipo E del Issue #136 (escenario `outstanding=0 → 99`). No aplica al flujo de descuento (ya confirmado) ni bloquea este PR.
