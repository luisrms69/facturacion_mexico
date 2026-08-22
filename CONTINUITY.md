# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-08-22
**Rama activa:** `fix/207-venta-mostrador-address-display`
**Tarea actual:** Fix #207 — coherencia de dirección display/link en venta mostrador. Commit en curso (incluye este CONTINUITY.md); falta push + PR.

---

## Recuperación rápida

Estoy trabajando en:
Issue #207. En `FacturaFiscalMexico.populate_billing_data()`, rama de venta mostrador
(`fm_facturar_venta_mostrador = 1`), `fm_direccion_principal_link` se resolvía desde el Customer
plantilla (`VENTA MOSTRADOR`) pero `fm_direccion_principal_display` se recalculaba vía `self.customer`
(cliente real), dejando link y display inconsistentes. Fix mínimo: `_get_primary_address_display()`
ahora acepta la `Address` ya resuelta y se le pasa `primary_address`.

Plan que estoy siguiendo:
Issue #207 (label `it-tech:approved`) + Assessment Package del issue. Autorización humana explícita en
esta sesión para el commit tras confirmar baseline.

Objetivo inmediato:
Cerrar `/ship commit` de #207. Luego esperar autorización para `/ship push` y `/ship pr` (base `main`).

Criterio de avance:
Commit con los 2 archivos + CONTINUITY.md → push OK → PR con bump de versión (PATCH) → CI.

---

## Estado actual

### Ya cerrado
- Causa raíz confirmada (demostrada, no inferida): link (plantilla) vs display (cliente real).
- Verificación fiscal: `fm_direccion_principal_display` es SOLO presentación — 0 referencias en
  `timbrado_api.py`/`api_client.py`/payload/XML/CFDI. Riesgo residual: muy bajo.
- Fix aplicado: `_get_primary_address_display(self, address=None)` + call site en venta mostrador.
  Caso normal sin cambio (allí `primary_address` == lo que devuelve el helper).
- Test de regresión `test_venta_mostrador_address_display.py` que ejerce `populate_billing_data()`
  real; falla si se retira el fix; idempotente (rollback, cero residuo).
- Linters limpios (`ruff check` + `ruff format`).
- Baseline confirmado: `main` limpio (a6aa652, sin #207) reproduce EXACTAMENTE las mismas 2 failures
  + 11 errors (`failures=2, errors=11, skipped=178`). Son preexistentes/ambientales, ajenas a #207.

### En progreso
- Ciclo `/ship`: ejecutando `commit` (2 archivos + CONTINUITY.md). Falta `push` y `pr`.

### Pendiente inmediato
1. `/ship push` (con autorización).
2. `/ship pr` contra `main` con bump `__version__` (PATCH, calcular vs `upstream/main`).
3. Validación GUI opcional: abrir una FFM venta mostrador y ver que el panel "Datos de Facturación"
   muestra la dirección de la plantilla coherente con el link.

### No repetir
- No usar `bench run-tests --app X --module Y --lightmode`: en Frappe v16 el combo `--app` + `--module`
  ignora el filtro y corre la suite completa (1659 tests). Para un módulo aislado: `--module` SIN `--app`.
- No declarar "riesgo nulo" en campos fiscales sin comprobar payload/XML/CFDI — aquí se comprobó.
- No incluir en el commit `scripts/*` ni `working_docs/private/` (fuera de alcance; siempre `git add` explícito).

---

## Decisiones vigentes
- Las 13 fallas de la suite (`test_custom_fields_naming_consistency` por campos UAE/VAT sin `fm_`;
  `test_ffm_reconciliation.test_lote_un_fallo_no_detiene` por datos residuales; `test_refacturar_workflow`,
  `test_check_ppd_requirement`, `test_setup_expense_item_groups`) son **baseline preexistente** del
  test site compartido, NO bloquean el commit de #207 (autorizado explícitamente por el usuario).
- Gate documental de #207 = **No aplica** (bug fix que restaura comportamiento previsto de un campo de
  presentación; test puro). Commit sin docs autorizado. Sin trailer `Co-Authored-By`.

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/facturacion_fiscal/doctype/factura_fiscal_mexico/factura_fiscal_mexico.py`
  — `populate_billing_data()` (rama venta mostrador) y `_get_primary_address_display()`.

### Probablemente editar
- Ninguno pendiente (a la espera de push/PR).

### No tocar
- `scripts/*`, `working_docs/private/` (untracked, fuera de alcance).

---

## Riesgos / cuidados
- El test site `test-facturacion.localhost` es compartido y arrastra datos residuales + custom fields
  regionales UAE → suite global con 13 fallas preexistentes (deuda de entorno, issue aparte si se decide).
- Al crear el PR: recalcular el bump SemVer contra `upstream/main` (una sola versión por PR).

---

## Información faltante
- Ninguna que bloquee #207. (Las 13 fallas ambientales de la suite quedan como deuda de test site,
  separada de este fix.)
