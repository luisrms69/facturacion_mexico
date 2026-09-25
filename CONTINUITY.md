# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-09-25
**Rama activa:** `feat/ventas-extranjeras`
**Tarea actual:** Ruteo contable de ventas extranjeras → `Sales Invoice Item.income_account`. Implementación + tests + docs + bump completos; en gate `pr-ready`.

---

## Recuperación rápida

Estoy trabajando en:
Enrutar el `income_account` de una `Sales Invoice` a una **cuenta de ingreso de exportación** cuando el
receptor es extranjero, conservando la resolución nativa de ERPNext para ventas nacionales. Aplica por
igual al flujo normal de operación y al importador `cfdi_emitidos`, sin lógica contable paralela.

Plan que estoy siguiendo:
Diseño cerrado con el propietario. **Único schema nuevo:** campo `cuenta_ingreso_venta_extranjera`
(Link Account) en `Configuracion Fiscal Mexico` (por empresa). Clasificación territorial nativa
(XEXX > Address.country vs Company.country > Territory "Rest Of The World" > INDETERMINADO), sin Customer
Group / currency / fm_tax_regime / Tax Category. Two-phase (`before_validate`/`validate`) evita
contaminación de `Item Default`. Precedencia por línea: `cuenta_descuentos` > routing extranjero > nativo.
Fail-closed en submit si es EXTRANJERA y falta/está inválida la cuenta. `cfdi_emitidos` aporta evidencia
del XML vía `doc.flags.fm_cfdi_territorial` (transitorio) y reutiliza el mismo `ruteo_ingreso`.

Objetivo inmediato:
`/ship pr` hacia `main` (gate `pr-ready` → autorización push + PR). Tras merge: `/sync-check` +
`/ship release` v1.7.0.

Criterio de avance:
PR mergeado con bump 1.7.0; luego release v1.7.0.

---

## Estado actual

Implementado en la rama (commit `dc67bfd` + bump/CONTINUITY):

- **Nuevo paquete** `facturacion_mexico/ventas_extranjeras/`:
  - `clasificacion.py` — `clasificar_territorialidad(doc)` + `clasificar_desde_cfdi(evidencia)` (precedencia XML).
  - `ruteo_ingreso.py` — two-phase (`before_validate`/`validate`), `get_cuenta_ingreso_extranjera`,
    `_cuenta_valida`, precedencia `cuenta_descuentos`, fail-closed.
  - `tests/` — `test_clasificacion.py` (15) + `test_ruteo_ingreso.py` (26).
- `configuracion_fiscal_mexico.json` — campo `cuenta_ingreso_venta_extranjera` + sección.
- `configuracion_fiscal_mexico.py` — `_validar_cuenta_ingreso_extranjera` (misma empresa / root_type Income / no grupo / habilitada).
- `hooks.py` — cableado two-phase en doc_events de Sales Invoice (Fase 1 en `before_validate`, Fase 2 al final de `validate`).
- `cfdi_emitidos/importer.py` — inyección de `doc.flags.fm_cfdi_territorial` (sin schema persistente).
- `pyproject.toml` — exclude interrogate del nuevo tests dir.
- Docs: `docs/tecnico/ventas-extranjeras-ingreso.md` + nav mkdocs.
- `__init__.py` — bump `1.6.0 → 1.7.0` (MINOR).

Validación funcional real en `test-fm-v010.localhost` (Company "test company 1"): nacional → income nativo;
extranjera (XEXX y por Address) → cuenta de exportación configurada; INDETERMINADO → nativo, submit no
bloqueado; fail-closed en submit sin cuenta; Item Default intacto antes/después; GL real verificado.
Sitio de prueba quedó limpio (masters/SIs de prueba borrados).

Sin regresión: `ventas_extranjeras` (15+26), `cfdi_emitidos` `test_importer_pricing` (3),
`test_resolve_customer_extranjero` (13), `test_attachments` (11). Ruff check + format limpios.

### Pendiente inmediato
1. `/ship pr` — gate `pr-ready` (autorización push + PR).
2. Tras merge: `/sync-check` + `/ship release` v1.7.0.

---

## Decisiones vigentes no evidentes en el código

- Único schema nuevo permitido: el campo en `Configuracion Fiscal Mexico` (NO campo en Customer/Sales
  Invoice, NO booleano `fm_es_venta_extranjera`, NO Company Settings, NO child table, NO mezclar en el
  `Mapeo Cuenta Fiscal Mexico` que valida `account_type == "Tax"`).
- `INDETERMINADO` es decisión consciente: conserva resolución nativa (no se infiere extranjero) para no
  romper cientos de Customers sin evidencia territorial. No bloquea submit.
- Precedencia por línea: `cuenta_descuentos` > routing extranjero > nativo (preserva Motivo/TipoRelación 01).

### Pendientes conocidos (NO bloqueantes, documentados)
1. E2E real de NC extranjera por descuento en sitio con `Facturacion Mexico Company Settings` +
   `cuenta_descuentos` reales (validado por unit/integration + prueba funcional con sustitución del resolver).
2. Tratamiento fiscal de ventas extranjeras como bloque separado: IVA / tasa 0 / no objeto, ObjetoImp,
   CFDI Exportacion, ResidenciaFiscal / NumRegIdTrib, STCT/ITT. Este bloque cubre SOLO el `income_account`.

---

## No commitear
- `facturacion_mexico/one_offs/validacion_ventas_extranjeras.py` (campaña de validación, one_off).
- `facturacion_mexico/one_offs/analisis_hist_actiglobal.py` (análisis, one_off).
- `scripts/*`, `working_docs/private/`.
