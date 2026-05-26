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

Cerrado en commit: pendiente (cierre de sesión 2026-05-26)

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

## Hito siguiente

### Hito C — Diseño base: proveedores, ítems e impuestos

**Prohibición:** No avanzar a clasificación de conceptos ni Purchase Invoice hasta cerrar Hito C.

**Objetivo:**

Resolver la arquitectura antes de clasificar conceptos o crear ítems. Hito C es diseño y decisión, no implementación de flujo.

**Temas obligatorios:**

1. **Supplier Group dedicado** para proveedores creados automáticamente desde CFDI.
   - Definir nombre y propiedades del grupo (cuenta contable, términos de pago).
   - Decidir si va como fixture o como campo configurable en `Configuracion CFDI Recibidos`.

2. **Defaults para Suppliers auto-creados.**
   - Qué propiedades hereda el proveedor del grupo.
   - Qué propiedades requieren configuración posterior.

3. **Arquitectura fiscal existente.**
   - Aprovechar la lógica de STCT/ITT ya implementada en el sistema de ventas.
   - No duplicar ni contradecir la lógica actual de Items, Item Tax Templates y roles fiscales.

4. **Impuestos por concepto del XML.**
   - El XML SAT CFDI tiene impuestos a nivel CFDI (global) y a nivel concepto (por ítem).
   - Definir si el PI debe usar impuesto global o Item Tax Template por línea.
   - El campo `taxes_json` ya existe en `CFDI Recibido Concepto`.

5. **Item Group dedicado.**
   - Definir si se requiere Item Group específico para ítems creados/importados desde CFDI.
   - Misma decisión fixture vs. campo configurable que Supplier Group.

6. **Item Tax Template por concepto.**
   - Definir cómo se asignará Item Tax Template a conceptos/ítems según tasa del XML SAT.
   - Considerar: IVA 16%, IVA 0%, exento, IEPS, retenciones.

**Entregable de Hito C:**

Documento de decisiones + plan de implementación aprobado.
No hay código hasta que las decisiones estén tomadas.

---

## Prohibido en cualquier hito sin decisión explícita

- Modificar `TaxResolver`
- Modificar `PurchaseInvoiceBuilder`
- Crear lógica de clasificación de conceptos
- Crear Purchase Invoice
- Crear Payment Entry
- Usar `docs/development/` antiguos como fuente de verdad del plan actual
