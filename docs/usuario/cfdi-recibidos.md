# CFDI Recibidos

Módulo para cargar XMLs de facturas de proveedores, clasificarlas y generar Purchase Invoices en ERPNext.

---

## Flujo completo

```
Cargar XML → Resolver proveedor → Asignar departamento → Clasificar items → Generar PI
```

| Estado | Descripción |
|---|---|
| `Falta proveedor` | RFC del emisor no tiene Supplier en ERPNext |
| `Proveedor encontrado` | Supplier asignado |
| `Falta departamento` | Proveedor resuelto, falta asignar departamento |
| `Falta clasificación` | Departamento asignado, hay conceptos sin item_code |
| `Clasificado` | Todos los conceptos clasificados — listo para PI |
| `Convertido a PI` | Purchase Invoice Draft creada |
| `Error conversión` | Falló la conversión — revisar `error_message` |

---

## Paso 1 — Cargar XMLs

Desde el workspace **Facturación México** o desde la Lista de CFDI Recibido, clic en **"Cargar XML"**.

Selecciona la empresa receptora y los archivos XML. El sistema valida:

- Versión CFDI 4.0 (3.3 es rechazado)
- RFC receptor coincide con `Company.tax_id`
- UUID no es duplicado

Si hay un Supplier con el RFC del emisor, se asigna automáticamente. Si no existe, el sistema lo **crea automáticamente** y avanza el CFDI a `Falta departamento`.

El diálogo muestra el resultado y ofrece **"Continuar → Asignar departamento"** si algún CFDI quedó listo para ese paso.

---

## Paso 2 — Asignar departamento

En la lista, clic en **Flujo Manual > Asignar Departamentos**.

El departamento determina la familia SAT (601/602/603/604) para efectos contables. Se configura en `Configuracion CFDI Recibidos` de la empresa mediante el mapeo de departamento ↔ familia SAT.

---

## Paso 3 — Clasificar conceptos

Cada línea del XML necesita un `item_code` de ERPNext para poder generar la PI.

El sistema intenta clasificar automáticamente usando:
- **Reglas aprendidas**: si ya se clasificó ese proveedor+código anteriormente
- **Items genéricos**: GASTO-{categoría}-NNN según el grupo de gastos

Para conceptos que no se clasifiquen solos, usar el flujo guiado **"Resolver Items pendientes"** en la lista o en el formulario del CFDI.

---

## Paso 4 — Generar Purchase Invoice

Desde la lista: **Flujo Manual > Generar PIs pendientes** — procesa todos los CFDIs en estado `Clasificado` de forma automática.

O desde el formulario de un CFDI individual: botón **"Generar PI"**.

La PI se crea como Draft con:
- Líneas de items según los conceptos clasificados
- Impuestos del XML (IVA, IEPS, retenciones) como filas nativas
- `fm_cfdi_uuid` y `fm_cfdi_recibido` para trazabilidad

!!! warning "Prerequisito"
    Debe existir `Configuracion CFDI Recibidos` para la empresa, con el wizard de impuestos completado. Sin este paso la conversión falla.

---

## Configuración previa necesaria

!!! warning "Prerequisito: CoA validado"
    Antes de configurar CFDI Recibidos, el Chart of Accounts debe estar revisado y aceptado
    (ver [Fase 1 — Validación del CoA](getting-started.md#fase-1-validacion-del-chart-of-accounts)).
    Los templates de impuestos de compras y la asignación de cuentas de gasto quedan vinculados
    al CoA en el momento de crearlos. Corregir el CoA después de tener transacciones es
    significativamente más complejo.

### Items genéricos de gasto (GASTO-*)

El app instala automáticamente un catálogo de items GASTO-* para clasificar los conceptos de los XMLs recibidos. Incluye categorías contables generales alineadas al Código Agrupador SAT, más un overlay de conceptos operativos frecuentes como gasolina, hospedaje, restaurante, paquetería, comisiones bancarias y seguros específicos.

Los items GASTO-* son items de compra. El app puede cargarles la clave SAT como referencia de clasificación, pero no se usan para emitir CFDIs de venta.

Para CFDI Recibidos, lo relevante de cada item es:

- **`item_group`** — determina la categoría de gasto SAT
- **Department → familia SAT** — configurable en `Configuracion CFDI Recibidos`
- **`expense_account`** — resuelta automáticamente al generar la Purchase Invoice, según la estrategia configurada (patrón, matriz de equivalencias o manual)

### Configuracion CFDI Recibidos

Accede desde el workspace **Facturación México**.

1. Seleccionar empresa
2. Configurar reglas de impuesto (IVA acreditable, IEPS, retenciones según aplique)
3. Clic en **"Generar Template de Impuestos"**
4. Configurar mapeo de departamentos (familia SAT por departamento)

### Tolerancia de totales

En la misma configuración, sección "Validación de Totales":

- **Tolerancia absoluta**: diferencia máxima en MXN (default 1.00)
- **Tolerancia porcentual**: diferencia máxima en % (default 0.5%)

---

## Exclusiones

Para excluir un CFDI del flujo automático, marcar **`no_procesar`** en el formulario. No aparecerá en los batches de generación de PI.

---

## Preguntas frecuentes

**¿Puedo cargar el mismo XML dos veces?**
No. El sistema detecta duplicados por UUID y retorna el documento existente.

**¿El proveedor se crea automáticamente?**
Sí. Durante el upload, si no existe Supplier con el RFC del emisor, se crea automáticamente con los datos del XML.

**¿La Purchase Invoice se valida (submit) automáticamente?**
No. La PI se crea como Draft. El submit es manual.

**¿Puedo reintentar después de un error de conversión?**
Sí. Desde el estado `Error conversión` puedes reintentar una vez corregida la configuración.
