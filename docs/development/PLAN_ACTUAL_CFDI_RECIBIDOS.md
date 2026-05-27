# Plan actual CFDI Recibidos

## Estado

Este documento es la única fuente vigente para continuar CFDI Recibidos.

Los documentos anteriores en `docs/development/` se consideran históricos u obsoletos para el trabajo activo, aunque sigan físicamente en el repositorio.

No usar planes viejos de `docs/development/` para decidir el flujo actual.

---

## Hitos cerrados

### Hito A — Upload → Proveedor

Cerrado en commit:

`7c6b44f feat(cfdi-recibidos): Hito A — Upload → Proveedor`

Resultado:

- El usuario sube XML desde GUI.
- El sistema valida XML.
- Detecta duplicado.
- Detecta CFDI no aplicable.
- Crea CFDI Recibido cuando aplica.
- Resuelve Supplier existente por RFC.
- Termina solo en etapa de proveedor.

Estados/resultados permitidos al terminar upload:

- `XML inválido`
- `Duplicado`
- `No aplicable`
- `Proveedor encontrado`
- `Falta proveedor`

El upload NO debe:

- crear proveedores
- clasificar conceptos
- generar Purchase Invoice
- tocar TaxResolver
- tocar PurchaseInvoiceBuilder
- crear Payment Entry

---

### Hito B — Generar proveedores faltantes

Cerrado en commit: `ac318a7`

Resultado:

- Acción "Generar proveedores faltantes" disponible en List View de CFDI Recibido.
- Crea Supplier para CFDIs en estado "Falta proveedor" usando RFC del emisor.
- Asigna Supplier al CFDI Recibido.
- Cambia estado a "Proveedor encontrado".
- Idempotente: no duplica Suppliers si ya existen.
- Procesa selección o todos los candidatos.
- Devuelve resumen: creados, ya_existian_y_asignados, omitidos, errores.
- Tests automatizados: 15/15 OK.
- Validación GUI: completa.

El Hito B NO toca:

- clasificación de conceptos
- TaxResolver
- PurchaseInvoiceBuilder
- Purchase Invoice
- Payment Entry

---

### Hito C.1 — Configuracion CFDI Recibidos + defaults proveedor + Item Groups

Cerrado en commits: `40638d5` (C.1), `82e9849` (Item Groups)

Resultado:

- DocType `Configuracion CFDI Recibidos` — singleton por empresa, config de defaults.
- Campo `default_payment_terms_supplier` — Payment Terms heredado por proveedores auto-creados.
- Child table `Mapeo Departamento CFDI Recibido` con campo `department` (Link → Department).
- `ensure_default_payment_terms()` en `after_install`.
- Item Groups SAT: árbol "Gastos" → 11 padres → 84 hijos (96 total). Idempotente.
- Tests: suite de supplier_resolver + setup_payment_terms + setup_expense_item_groups.

---

### Hito C.2 — Department assignment

Cerrado en sesión 2026-05-26.

Resultado:

- Campo `department` (Link → Department) en `CFDI Recibido`.
- Estado "Falta departamento" en el flujo: supplier → **department** → clasificación → Listo.
- `compute_stage(doc)` evalúa en orden correcto: supplier → department → conceptos → Listo.
- Endpoint `get_department_candidates` — CFDIs con supplier pero sin dept, no terminales.
- Endpoint `assign_departments` — asignación en lote, valida contra `mapeo_departamentos` de la empresa.
- Botón "Asignar Departamentos" en List View + diálogo con tabla de candidatos.
- Tests: 15 tests en `test_department_assignment.py` + 8 en `test_department_mapping.py` (23 total OK).
- Validación GUI: completa.

El flujo Upload → Proveedor → Department está **completo y cerrado**.

---

## Hito siguiente

### Hito D — Creación de Purchase Invoice

**Prohibición:** No implementar hasta completar revisión arquitectónica de TaxResolver y PIBuilder.

**Contexto:**

El código de `purchase_invoice_builder.py` y `tax_resolver.py` existe en la rama pero **no está validado**.
El PIBuilder original (Issue #152) falló en GUI al paso ~2 de 20+.
`REPORTE_INVESTIGACION_SAT_CFDI_RECIBIDOS.md` documenta problemas arquitectónicos en TaxResolver:
necesita reescritura para leer desde `Configuracion CFDI Recibidos` en lugar de `Configuracion Fiscal Mexico`.

**Antes de implementar Hito D:**

1. Revisión completa de `tax_resolver.py` y `purchase_invoice_builder.py`.
2. Decisión explícita sobre manejo de retenciones (requiere XML real de honorarios).
3. Decisión sobre impuesto por línea vs. impuesto global del CFDI.
4. Plan de implementación aprobado.

**No hay código nuevo hasta que el plan esté aprobado.**

---

## Prohibido en cualquier hito sin decisión explícita

- Modificar `TaxResolver`
- Modificar `PurchaseInvoiceBuilder`
- Crear lógica de clasificación de conceptos
- Crear Purchase Invoice
- Crear Payment Entry
- Usar `docs/development/` antiguos como fuente de verdad del plan actual
