# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-07-30
**Rama activa:** `feat/nota-credito-descuento-relacion-01`
**Tarea actual:** Nota de Crédito por descuento/bonificación (CFDI E, TipoRelación 01). Feature completa y validada end-to-end en sandbox; commit hecho, **falta push + PR**.

---

## Recuperación rápida

Estoy trabajando en:
El flujo de Nota de Crédito por **descuento/bonificación** (distinto de devolución física). El operador ejecuta el botón **«Aplicar como Descuento / Bonificación»** en una Sales Invoice Return en borrador → se fija `income_account = cuenta de descuentos configurada por empresa` y `description = "Descuento - <descripción original>"` (conserva Item y ClaveProdServ del origen). Tras el Submit, la FFM detecta el descuento por la cuenta contable y deriva **E / 01 / G02 / PUE / 15 - Condonación**, con UUID relacionado desde `return_against`.

Plan que estoy siguiendo:
Issue #137 (TipoRelación 01) + ADR `docs/adr/0025-notas-credito-cfdi-tipo-e-issue116.md` (única fuente de la arquitectura y decisiones).

Objetivo inmediato:
`/ship push` → `/ship pr` (base `main`), con autorización explícita en cada paso.

Criterio de avance:
Tests verdes (49 en `test_nota_credito_descuento_relacion_01` + regresión CFDI E 6 / complemento 24 / issue162 9) + ruff/prettier/mkdocs limpios. Experimento sandbox en sitio dev confirmó GL y XML correctos con `Enable Discount Accounting = OFF`.

---

## Estado actual

### Ya cerrado
- Feature implementada (12 archivos) y **commiteada** en esta rama. Bump `1.1.0 → 1.2.0`.
- Experimento end-to-end en sitio dev (sandbox): 2 ventas (lista / 10% abajo) + 2 NC de descuento, todos timbrados; GL y XML validados con Discount Accounting OFF.
- ADR 0025 actualizado (arquitectura final + precondición Discount Accounting OFF).

### En progreso
- Ninguna edición de código pendiente.

### Pendiente inmediato
1. `/ship push` (con autorización).
2. `/ship pr` hacia `main` (con autorización).
3. Tras merge (lo hace el usuario): tag `v1.2.0` + Release.

### No repetir
- **NO** usar `discount_account` nativo para la NC de descuento: invierte e infla el asiento ("descuento del 90%"). La solución es `Enable Discount Accounting = OFF` por empresa (config, no código).
- **NO** cambiar `item_code` a un Item "Descuento" (ERPNext `validate_returned_items` lo rechaza en returns con `return_against`).
- **NO** alinear `price_list_rate = rate` en la acción (se intentó y descartó; el usuario lo revirtió).
- **NO** commitear `one_offs/` ni `working_docs/`.

---

## Decisiones vigentes
- **Precondición por empresa:** `Selling Settings.Enable Discount Accounting = OFF` para operar NC de descuento (documentado en ADR 0025). No es regla universal del app.
- El descuento queda integrado en el `ValorUnitario` del CFDI (payload usa `net_rate`, `discount=0`); **nunca** se emite nodo `Descuento` en el XML.
- Cuenta de descuentos: config por empresa en `Facturacion Mexico Company Settings.cuenta_descuentos` (no hardcode; se aplica como `income_account`).
- Devolución física conserva comportamiento histórico (TipoRelación 03).

---

## Archivos relevantes ahora

### Leer primero
- `docs/adr/0025-notas-credito-cfdi-tipo-e-issue116.md`

### Probablemente editar
- (ninguno; feature cerrada salvo hallazgos en review/CI)

### No tocar
- `facturacion_fiscal/timbrado_api.py` fórmula del REP (`allocated_amount / si.grand_total`).

---

## Riesgos / cuidados
- El sitio dev de prueba tiene el setting `Enable Discount Accounting = OFF` (dejado así como solución). Documentos de prueba conservados para auditoría.
- Al abrir PR: el gate documental mapea `public/js` → `docs/usuario`; se acordó que ADR 0025 cubre el flujo (no se creó página de usuario).

---

## Información faltante
- Confirmación del contador/ChatGPT sobre el cierre fiscal del escenario (pendiente formal, no bloquea el commit).
