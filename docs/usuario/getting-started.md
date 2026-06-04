# Primeros Pasos

Guía de implementación del app en un sitio nuevo o restaurado, desde diagnóstico inicial hasta emitir el primer CFDI.

---

## Requisitos previos

- ERPNext v16 instalado
- Cuenta activa en [FacturAPI.io](https://www.facturapi.io) (sandbox para pruebas)
- RFC de la empresa emisora
- Código postal fiscal

---

## Instalación

```bash
bench get-app facturacion_mexico https://github.com/luisrms69/facturacion_mexico.git
bench --site tu-sitio.local install-app facturacion_mexico
bench --site tu-sitio.local migrate
```

---

## Fase 0 — Diagnóstico inicial del sitio

Antes de configurar cualquier cosa, confirmar el estado base del sitio.

Verificar desde el workspace de ERPNext o vía consola:

| Área | Lo que confirmar |
|---|---|
| Apps instaladas | `facturacion_mexico` aparece en la lista de apps |
| Company | Existe la Company del cliente con nombre, RFC (`Tax ID`) y moneda MXN |
| Chart of Accounts | Existe un CoA cargado (más de unas pocas cuentas) |
| Customers | Si el sitio viene de migración: clientes existentes son correctos |
| Items | Si el sitio viene de migración: items existentes son correctos |
| Transacciones | Verificar si hay Sales Invoices, GL Entries o Purchase Invoices previas |
| Config del app | Confirmar que **no existe** `Facturacion Mexico Company Settings` ni `Configuracion Fiscal Mexico` si el sitio es nuevo |

Si hay GL Entries previas, el sitio **no está limpio** — ajustar el procedimiento de implementación caso por caso antes de continuar.

---

## Fase 1 — Validación del Chart of Accounts

**Esta fase va antes de cualquier configuración fiscal.** Todos los impuestos, templates y cuentas del app se asignan contra el CoA de la empresa. Si el CoA está incompleto o es incorrecto, el error se arrastra a toda la operación.

La validación del CoA es **manual** — la realiza el contador o el implementador junto con el cliente.

### Lo que se debe confirmar

- [ ] La Company tiene `Tax ID` (RFC), `Default Currency = MXN`, `Country = Mexico`
- [ ] Existe una Address vinculada a la Company marcada como **Is Primary Address** con Código Postal fiscal correcto
- [ ] El CoA tiene cuentas de **Ventas** (Root Type = Income)
- [ ] El CoA tiene cuentas de **Compras y Gastos** (Root Type = Expense) para las categorías que el cliente factura
- [ ] El CoA tiene cuentas de **Impuestos** para IVA traslado, IVA retenido y retenciones que apliquen
- [ ] El CoA tiene cuentas de **Clientes** (Debtors / Cuentas por Cobrar)
- [ ] El CoA tiene cuentas de **Proveedores** (Creditors / Cuentas por Pagar) si se usará CFDI Recibidos
- [ ] El CoA tiene cuentas bancarias / caja si se registrará cobranza
- [ ] El CoA corresponde al catálogo objetivo del cliente — no es un CoA genérico dejado por default

Si algún punto falla, corregir el CoA **antes de continuar**. Con cero GL Entries es el único momento en que los ajustes son sin riesgo.

!!! warning "No saltar esta fase"
    No ejecutar el wizard fiscal, no generar templates de impuestos y no emitir CFDIs si el CoA no ha sido revisado y aceptado. Los templates de impuestos y las cuentas predeterminadas quedan vinculados al CoA en el momento de crearlos.

### Normalización del formato de account_number

Después de confirmar que el CoA corresponde al catálogo objetivo del cliente, puede ser necesario normalizar el **formato visible** del campo `account_number` antes de operar.

Esto aplica cuando las cuentas ya representan correctamente el concepto contable, pero el formato del número no es el deseado. Un caso común: números compactos sin separadores que se quieren legibilizar antes de operar.

Ejemplo genérico:

```
60348000  →  603-48-000
```

Este es solo un ejemplo. El formato depende del CoA objetivo de cada cliente. **No hay un formato universal obligatorio.**

**Condiciones para hacer este ajuste:**

- Las cuentas ya representan correctamente el concepto contable — solo cambia el formato del número
- El contador valida que el cambio es correcto
- No hay números de cuenta duplicados en el resultado propuesto
- La estructura contable no cambia: no se mueven cuentas, no cambian nombres, root_type, report_type ni jerarquía

!!! warning "Si ya existen GL Entries"
    Con movimientos contables registrados, cambiar `account_number` ya no es un ajuste simple. Requiere un plan de migración controlado y autorización contable explícita.

**Proceso recomendado:**

1. Generar una propuesta listando `account_number` actual y propuesto para cada cuenta
2. Revisar: sin duplicados, solo cambio de formato, sin alteración de la estructura contable
3. Documentar el formato decidido — se usará después en la configuración del app
4. Cargar el cambio en ERPNext

**Herramienta a usar según el estado del sitio:**

| Situación | Herramienta recomendada |
|---|---|
| Sitio completamente limpio: sin GL Entries, sin configuraciones de impuestos, sin datos operativos | **Chart of Accounts Importer** (`Accounting → Chart of Accounts Importer`) — reconstruye el CoA completo desde cero |
| Sitio con configuración parcial: ya tiene Tax Templates, Sales Invoices u otras configuraciones | **Data Import** (`Tools → Data Import`, DocType: Account) — actualiza solo el campo `account_number` en los registros existentes sin borrar el resto |

### Para sitios con CFDI Recibidos (opcional)

Si el cliente procesará facturas de proveedores y quiere asignación contable automática de cuentas de gasto, el formato normalizado de `account_number` determina cómo se configura la resolución:

- El formato elegido se documenta y se usa en el campo `formato_cuenta_gasto` de `Configuracion CFDI Recibidos`
- Ejemplo: si se normalizó a `603-48-000`, el formato configurado es `{f}-{s}-000`
- Si el CoA requiere ajuste de formato: hacerlo ahora, con cero GL Entries

> La compatibilidad del CoA con el Código Agrupador SAT (Anexo 24) deja base para contabilidad electrónica en el futuro, aunque esa funcionalidad no está implementada actualmente.

---

## Fase 2 — Configuración fiscal del app

Solo después de validar el CoA.

### 1. Facturacion Mexico Company Settings

Accede desde el workspace **Facturación México → Facturacion Mexico Company Settings**.

Crea un registro **por cada empresa** que emitirá CFDIs.

| Campo | Descripción |
|---|---|
| Company | Empresa emisora (Link a ERPNext Company) |
| API Key Producción | API Key de FacturAPI.io para producción |
| API Key Pruebas | API Key de FacturAPI.io para sandbox |
| Modo Sandbox | Activar para pruebas, desactivar para producción |
| Método de Pago por Defecto | PUE o PPD — se aplica al crear nuevas facturas |
| Enviar Email por Defecto | Si el sistema envía CFDI por email automáticamente |

> Los certificados SAT (.cer/.key) se gestionan en el portal de FacturAPI.io, no en ERPNext.

### 2. Configuracion Fiscal Mexico

Accede desde el workspace **Facturación México → Configuracion Fiscal Mexico → New**.

**Paso 1 — Selecciona los regímenes fiscales de la empresa:**

| Opción | Cuándo activar |
|---|---|
| IVA Exento | Productos o servicios legalmente exentos de IVA |
| Zona Fronteriza | Empresa con operaciones en franja fronteriza norte (IVA 8%) |
| Exportación | Ventas al extranjero (IVA 0% exportación) |
| IEPS Alcohol | Venta de bebidas alcohólicas |
| IEPS Azúcar | Venta de bebidas con azúcar añadida |
| IEPS Combustibles | Venta de combustibles |
| IEPS Tabaco | Venta de tabaco |
| Ret. Honorarios | Pagos a personas físicas por honorarios |
| Ret. Arrendamiento | Pagos por arrendamiento |

> **Nota para alimentos frescos:** Bajo el Art. 2-A LIVA, los vegetales no industrializados se gravan a tasa 0% de IVA — no exento, sino tasa cero. No activar IEPS. La tasa 0% se genera automáticamente.

**Paso 2 — Mapea las cuentas contables de impuestos:**

En la misma pantalla, en la sección **Cuentas de Impuestos**, asigna la cuenta contable correcta de tu Chart of Accounts para cada tipo de impuesto activado.

!!! warning "Este paso es obligatorio antes del wizard"
    Si no mapeas las cuentas, el wizard falla. Las cuentas que asignes aquí son las que quedarán vinculadas a los templates de impuestos. Si necesitas cambiarlas después, debes repetir este paso y volver a generar los templates.

#### Cuenta transitoria vs cuenta definitiva de IVA

Para ventas a crédito o PPD, el IVA trasladado normalmente se registra primero en una cuenta transitoria y después se mueve a la cuenta definitiva cuando el cliente paga.

| Momento | Cuenta (ejemplo conceptual) |
|---|---|
| Al emitir la factura | IVA trasladado no cobrado (cuenta origen) |
| Al cobrar el pago | IVA trasladado cobrado (cuenta destino) |

La nomenclatura y los números de cuenta exactos dependen del CoA de cada empresa. Lo importante es asignar aquí la **cuenta origen** — la transitoria que usas cuando facturas. La **cuenta destino** se define más adelante en `Configuracion Reclasificacion Fiscal Mexico`.

**Paso 3 — Genera los templates de impuestos:**

Clic en **"Generar Template de Impuestos"**. El sistema crea los Sales Taxes and Charges Templates (para tus facturas de venta) e Item Tax Templates (para items con tratamiento especial como IVA 0% o IEPS), y los asigna automáticamente a los Item Groups correspondientes.

> Sin este paso el timbrado falla con error de impuestos.

### 3. Configuracion Reclasificacion Fiscal Mexico

Esta configuración define cómo mover impuestos entre cuentas cuando se registra un cobro o pago. En México el IVA opera en base a flujo de efectivo: se causa cuando se cobra, no cuando se factura.

El flujo es:

1. Al emitir la factura, el IVA queda en la cuenta origen/transitoria.
2. Al registrar el cobro en Payment Entry, el sistema calcula la parte proporcional cobrada.
3. El sistema agrega automáticamente filas al Payment Entry para reclasificar ese monto:
   - carga la cuenta origen (reduce el IVA transitorio)
   - abona la cuenta destino (registra el IVA efectivamente cobrado)

Accede desde el workspace **Facturación México → Configuracion Reclasificacion Fiscal Mexico → New**.

1. Selecciona la **Company**
2. Clic en **"Cargar Reglas"** — carga reglas de Cobro (ventas, desde Configuracion Fiscal Mexico) y reglas de Pago (compras, desde Configuracion CFDI Recibidos)
3. Para cada regla, captura la **cuenta destino**
4. Clic en **"Aplicar"**

Ejemplo conceptual:

| Campo | Ejemplo |
|---|---|
| Tipo de operación | Cobro |
| Cuenta origen | IVA trasladado no cobrado |
| Cuenta destino | IVA trasladado cobrado |

!!! warning "Sin cuenta destino no hay reclasificación"
    Si una regla no tiene cuenta destino asignada, el Payment Entry mostrará advertencia y esa cuenta no será reclasificada al cobrar.

### Qué crea el app automáticamente al instalarse

Al ejecutar `bench migrate` después de instalar el app, se crean automáticamente los siguientes catálogos en ERPNext:

- **Item Groups de gasto** — árbol de categorías contables alineado al Código Agrupador SAT (familias 601–604, más gastos financieros 701/702). Sirven como base para clasificar conceptos de facturas de proveedores.
- **Items genéricos GASTO-*** — ~105 items de compra (uno por categoría hoja del árbol). No requieren `fm_producto_servicio_sat` ya que son items de compra, no de venta. Visibles en **Stock → Items** filtrando por `GASTO-`.

Estos catálogos son el punto de partida para el módulo de CFDI Recibidos. No es necesario crearlos manualmente.

---

## Fase 3 — Datos maestros mínimos

### Customer con datos fiscales

En **Selling > Customer**, llenar en la sección **Tax**:

| Campo | Descripción |
|---|---|
| `tax_id` | RFC del cliente (campo nativo ERPNext) |
| `fm_tax_regime` | Régimen fiscal SAT |
| `fm_uso_cfdi_default` | Uso CFDI por defecto |

### Item con clave SAT e Item Group fiscal

**Campo obligatorio en todos los items:**

- `fm_producto_servicio_sat` — clave del catálogo SAT. Sin esta clave el sistema bloquea el guardado de la factura.

**Cómo funciona la asignación de impuestos:**

El sistema usa dos mecanismos complementarios:

| Mecanismo | Nivel | Cuándo aplica |
|---|---|---|
| **STCT** (Sales Taxes and Charges Template) | Factura completa | Siempre. Se auto-selecciona según la composición de la factura |
| **ITT** (Item Tax Template) | Por línea | Solo para items con tratamiento fiscal especial (0%, Exento, IEPS) |

**IVA 16% estándar:** no requiere ninguna configuración especial en el item ni en su Item Group. El STCT `IVA Nacional - Básico` se aplica automáticamente a toda la factura y cubre el IVA 16% de los items sin tratamiento especial. Los items en cualquier grupo estándar funcionan correctamente para IVA 16%.

**Tratamientos especiales:** cuando un item tiene IVA 0%, está exento o tiene IEPS, debe pertenecer al Item Group correspondiente. El wizard de `Configuracion Fiscal Mexico` crea estos grupos y les asigna automáticamente su Item Tax Template (ITT):

| Item Group | Tratamiento | Cuándo usarlo |
|---|---|---|
| `Artículos con IVA al 0%` | IVA tasa 0% | Alimentos frescos, agua, medicamentos (Art. 2-A LIVA) |
| `Artículos Exentos` | Exento de IVA | Productos legalmente exentos |
| `Artículos IEPS Alcohol` | IVA + IEPS | Bebidas alcohólicas |
| `Artículos IEPS Azúcar` | IVA + IEPS cuota | Bebidas con azúcar añadida |
| `Artículos IEPS Combustibles` | IVA + IEPS cuota | Combustibles |
| `Artículos IEPS Tabaco` | IVA + IEPS | Tabaco |
| `Servicios Profesionales (Honorarios)` | IVA + retención ISR/IVA | Honorarios a personas físicas |
| `Arrendamiento` | IVA + retención ISR/IVA | Pagos por arrendamiento |

El sistema detecta automáticamente qué ITTs están presentes en las líneas de la factura y selecciona el STCT correspondiente (Básico, IEPS, Retenciones o Total). No es necesario asignar el STCT manualmente.

> No configurar el ITT directamente en cada item — siempre a través del Item Group.

---

## Fase 4 — Primera emisión CFDI

1. Crear Sales Invoice en **Selling > Sales Invoice**
2. Seleccionar el cliente (debe tener RFC en `tax_id`)
3. Agregar items con clave SAT configurada
4. Verificar que los impuestos se calculen correctamente
5. **Submit** — se crea la **Factura Fiscal Mexico** en estado `BORRADOR`
6. Clic en el botón **"Timbrar Factura"** → abre el FFM → clic en **"Timbrar con FacturAPI"**

Si el timbrado es exitoso, el FFM cambia a estado `TIMBRADO` y el Sales Invoice muestra `fm_fiscal_status = TIMBRADO`.

> Ver el flujo completo en [Emitir un CFDI](emitir-cfdi.md).

---

## Fase 5 — Módulos adicionales

Una vez que el flujo básico de emisión funciona:

- [Cancelar un CFDI](cancelar-cfdi.md)
- [Complemento de Pago PPD](complemento-pago.md)
- [Configurar Multi-sucursal](multisucursal.md)
- [Addendas para clientes corporativos](addendas.md)
- [CFDI Recibidos — registrar compras de proveedores](cfdi-recibidos.md)
- [Troubleshooting](troubleshooting.md)
