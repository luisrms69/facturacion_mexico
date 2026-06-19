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

Crea un registro **por cada empresa** que emitirá CFDIs. El nombre del documento se genera automáticamente como `FMCS-{Company}`.

---

#### Sección: General del Sistema

| Campo | Descripción |
|---|---|
| **Company** | Empresa emisora. Requerido. Único por empresa — no puede haber dos registros para la misma Company. |
| **Modo Sandbox** | Controla qué API Key usa el sistema al conectarse con FacturAPI. Ver explicación abajo. |
| **API Key Producción** | API Key de producción de FacturAPI.io. Solo se usa cuando Modo Sandbox está **desactivado**. |
| **API Key Pruebas** | API Key de sandbox de FacturAPI.io. Solo se usa cuando Modo Sandbox está **activado**. |
| **Modo Facturación por Defecto** | `Normal` = las nuevas Sales Invoices timbran directamente. `E-Receipt` = las nuevas Sales Invoices generan un recibo para autofacturación posterior. Se puede cambiar por factura individual. |

**Modo Sandbox — qué hace exactamente:**

El modo Sandbox determina cuál de las dos API Keys se envía a FacturAPI en cada petición. No cambia la URL del servicio — FacturAPI usa la misma URL (`https://www.facturapi.io/v2`) para ambos entornos; la diferencia entre sandbox y producción la determina la propia key.

| Modo Sandbox | API Key usada | Efecto |
|---|---|---|
| ✅ Activado (default) | API Key Pruebas | Timbrado en sandbox FacturAPI — CFDIs no tienen validez fiscal |
| ☐ Desactivado | API Key Producción | Timbrado real ante el SAT — CFDIs con validez fiscal |

**Cuando tienes ambas API Keys guardadas:**

Puedes guardar ambas keys desde el principio. El sistema selecciona automáticamente la correcta según el estado del checkbox. Para pasar de pruebas a producción basta con desmarcar Modo Sandbox — sin necesidad de modificar las keys.

!!! warning "Nunca timbrar en producción durante implementación"
    Asegúrate de que Modo Sandbox esté activado mientras configuras y pruebas el sistema. Desactívalo únicamente cuando el cliente esté listo para operar en producción y los certificados SAT estén cargados en el portal FacturAPI.

> Los certificados SAT (.cer/.key) se gestionan en el portal de FacturAPI.io, no en ERPNext.

---

#### Sección: Facturas

| Campo | Descripción |
|---|---|
| **Método de Pago por Defecto** | `PUE` (Pago en Una Exhibición) o `PPD` (Pago en Parcialidades o Diferido). Se asigna automáticamente a nuevas Facturas Fiscales Mexico. |
| **Enviar Email por Defecto** | Si está activado, el sistema envía automáticamente el PDF y XML del CFDI al cliente al timbrar. El cliente puede tener una preferencia distinta en su perfil. |
| **Descargar PDF/XML automáticamente** | Si está activado, el PDF y XML se descargan y adjuntan al documento (FFM y Complemento Pago MX) inmediatamente al timbrar. |
| **Email Fallback Cliente** | Email que se usa como destinatario si el cliente no tiene email configurado. Si está vacío, no se envía email cuando el cliente no tiene email. |

---

#### Sección: E-Receipts

| Campo | Descripción |
|---|---|
| **Tipo Vencimiento por Defecto** | `Fixed Days` = vence a los N días configurados. `End of Month` = vence al fin del mes en curso. `Custom Date` = el usuario elige la fecha al crear el recibo. |
| **Días Vencimiento por Defecto** | Número de días para vencer cuando el tipo es `Fixed Days`. Default: 3 días. |
| **Forma de Pago E-Receipt por Defecto** | Código SAT de forma de pago para E-Receipts cuando no se puede obtener del Payment Entry. `28`=Tarjeta débito, `04`=Tarjeta crédito, `01`=Efectivo, `03`=Transferencia. |
| **Email Notificaciones E-Receipt** | Email que recibe notificaciones de E-Receipts próximos a vencer o sin convertir. |
| **Mensaje Portal Autofactura** | Texto que ve el cliente en el portal de autofacturación. Default incluido; se puede personalizar. |

---

#### Sección: Factura Global

Solo relevante si el cliente emite Facturas Globales (agrupa E-Receipts de ventas mostrador sin RFC específico).

| Campo | Descripción |
|---|---|
| **Customer Público en General** | Customer configurado con RFC genérico `XAXX010101000` y régimen 616. Receptor de todas las facturas globales de esta Company. |
| **Item Concepto Factura Global** | Item que representa las ventas agrupadas. Debe tener clave SAT y unidad SAT configuradas. |
| **Forma de Pago Global por Defecto** | Código SAT de forma de pago para facturas globales cuando no hay forma clara de los receipts. `01`=Efectivo. |
| **Notificar al Timbrar Factura Global** | Si está activado, envía notificación por email al generar una Factura Global. |
| **Emails de Notificación Factura Global** | Emails separados por coma que reciben la notificación. El usuario creador siempre se incluye. |

---

#### Sección: Contenido PDF del CFDI

Configura el texto adicional que aparece en el PDF generado por FacturAPI para los CFDIs de tipo **Ingreso (I)**. No afecta el XML ni el timbrado fiscal.

| Campo | Descripción |
|---|---|
| **Incluir Orden de Compra** | Si está activado, agrega el número de orden de compra del cliente (`po_no` de la Sales Invoice) al PDF, cuando existe. |
| **Incluir Observaciones** | Si está activado, agrega el campo Observaciones (`remarks`) de la Sales Invoice al PDF, si tiene contenido relevante. |
| **Leyenda PUE** | Texto que aparece al final del PDF para facturas con Método de Pago `PUE`. Dejar vacío para omitir. |
| **Leyenda PPD** | Texto que aparece al final del PDF para facturas con Método de Pago `PPD`. Admite tres variables: `{company}`, `{total}`, `{due_date}`. Dejar vacío para omitir. |

!!! note "Alcance del contenido adicional"
    El contenido configurado no convierte el CFDI en un pagaré ni sustituye un contrato,
    pagaré u otro documento firmado que formalice la obligación de pago.

### 2. Configuracion Fiscal Mexico

Accede desde el workspace **Facturación México → Configuracion Fiscal Mexico → New**.

**Paso 1 — Selecciona los regímenes fiscales de la empresa:**

| Opción | Cuándo activar |
|---|---|
| **IVA Exento** | Actívalo si la empresa vende productos o servicios legalmente exentos de IVA (medicamentos con receta, libros, etc.). Los ítems exentos no causan IVA en el CFDI — el nodo de impuesto no aparece. No confundir con tasa 0%: exento no es lo mismo que 0%. |
| **Zona Fronteriza** | Actívalo si la empresa tiene operaciones en la franja fronteriza norte (Baja California, Sonora, Chihuahua, Coahuila, Nuevo León, Tamaulipas — ciudades específicas según decreto). Genera templates de IVA 8% adicionales a los de 16%. |
| **IVA tasa 0% / Exportación** | Actívalo si la empresa vende productos gravados a tasa 0%: alimentos y vegetales no industrializados (Art. 2-A LIVA), agua no gaseosa, medicamentos sin receta, o si realiza exportaciones (Art. 29 LIVA). Ambos casos producen en el CFDI un nodo IVA 002 con `TipoFactor=Tasa` y `TasaOCuota=0.000000`. El fundamento legal es distinto pero el tratamiento en CFDI es idéntico. |
| **IEPS Alcohol** | Actívalo si la empresa vende bebidas alcohólicas (cervezas, vinos, destilados). Genera templates con IEPS a tasa variable sobre precio + IVA 16%. |
| **IEPS Azúcar/Bebidas** | Actívalo si la empresa vende bebidas saborizadas con azúcar añadida (refrescos, jugos con azúcar, energizantes). Genera templates con IEPS cuota fija por litro + IVA 16%. |
| **IEPS Combustibles** | Actívalo si la empresa vende combustibles (gasolina, diésel, gas). Genera templates con IEPS cuota fija por litro + IVA 16%. Nota: el IEPS de combustibles **no integra la base del IVA** (LIEPS Art. 2-A). |
| **IEPS Tabaco** | Actívalo si la empresa vende productos de tabaco. Genera templates con IEPS tasa sobre precio + cuota adicional por cigarro + IVA 16%. |
| **Retenciones Honorarios** | Actívalo si la empresa paga a personas físicas por servicios profesionales (honorarios). Genera templates con retención ISR (10%) + retención IVA (10.67%) aplicables al emitir CFDI de egreso o al recibir factura de honorarios. |
| **Retenciones Arrendamiento** | Actívalo si la empresa paga arrendamiento de inmuebles a personas físicas. Genera templates con retención ISR (10%) + retención IVA (10.67%). |
| **Retenciones Autotransporte** | Actívalo si la empresa contrata servicios de autotransporte terrestre de carga federal. Genera template con retención IVA 4% (no retiene ISR). |
| **Retenciones RESICO** | Actívalo si la empresa paga a personas físicas inscritas en RESICO. La tasa ISR es configurable (default 1.25%). Genera templates con retención ISR variable + retención IVA 6%.|

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

**Paso 3 — Configura la política de precios (opcional):**

Si la lista de precios de tu empresa ya incluye IVA (precio capturado = precio final con impuesto), activa el campo **"Precios de venta incluyen impuestos"** antes de generar los templates.

| Campo | Descripción |
|---|---|
| `Precios de venta incluyen impuestos` | Cuando está activo, los STCT de venta generados por la app marcan el IVA como incluido en el precio capturado (`included_in_print_rate = 1`). ERPNext calcula automáticamente la base gravable y el IVA a partir del precio ingresado. |

Ejemplo con precio 750 y este campo activo:

- Precio capturado: $750.00
- Base (sin IVA): $646.55
- IVA 16%: $103.45
- Total CFDI: $750.00

**Importante:**

- No modifica Items, ITT, facturas existentes ni STCT manuales.
- Si cambias este campo después de haber generado los templates, debes volver a ejecutar el paso siguiente para que los STCT se regeneren.

**Paso 4 — Genera los templates de impuestos:**

Clic en **"Generar Template de Impuestos"**. El sistema crea los Sales Taxes and Charges Templates (para tus facturas de venta) e Item Tax Templates (para items con tratamiento especial como IVA 0% o IEPS), y los asigna automáticamente a los Item Groups correspondientes.

> Sin este paso el timbrado falla con error de impuestos.

### 3. Configuracion CFDI Recibidos — Template de impuestos de compras

!!! warning "Prerequisito para Configuracion Reclasificacion Fiscal Mexico"
    Este paso debe completarse **antes** de ejecutar el paso 4. Si no se genera el template de impuestos de compras, el botón "Cargar Reglas" en CRFM solo cargará reglas de Cobro (ventas) — las reglas de Pago (compras/IVA acreditable) no aparecerán.

Accede desde el workspace **Facturación México → Configuracion CFDI Recibidos**.

Si no existe el registro para la empresa, créalo. Luego:

1. Selecciona la **Company**
2. **Modo de resolución contable** — `Manual` o `Automático CoA SAT`
   - `Manual`: el usuario asigna la cuenta de gasto en cada concepto del XML
   - `Automático CoA SAT`: el sistema la resuelve por prefijo del CoA combinando familia SAT del departamento + código SAT del grupo de gasto
3. Si modo Automático: seleccionar **Formato CoA** (`########`, `###-##-###` o `###.##.###`) según el formato del Chart of Accounts de la empresa
4. En la sección **Reglas de Impuesto**: configurar las cuentas de IVA acreditable (y retenciones si aplica) de las facturas de proveedores
5. Clic en **"Generar Template de Impuestos"** — crea el Purchase Taxes and Charges Template que se usará al convertir XMLs a Purchase Invoices
6. En la sección **Mapeo de Departamentos**: asignar familia SAT (601/602/603/604) a cada departamento de la empresa. Al guardar, el sistema agrega automáticamente todos los departamentos activos aún no mapeados.

> Ver flujo completo de operación en [CFDI Recibidos](cfdi-recibidos.md).

### 4. Configuracion Reclasificacion Fiscal Mexico

Esta configuración define cómo mover impuestos entre cuentas cuando se registra un cobro o pago. En México el IVA opera en base a flujo de efectivo: se causa cuando se cobra, no cuando se factura.

El flujo es:

1. Al emitir la factura, el IVA queda en la cuenta origen/transitoria.
2. Al registrar el cobro en Payment Entry, el sistema calcula la parte proporcional cobrada.
3. El sistema agrega automáticamente filas al Payment Entry para reclasificar ese monto:
   - carga la cuenta origen (reduce el IVA transitorio)
   - abona la cuenta destino (registra el IVA efectivamente cobrado)

Accede desde el workspace **Facturación México → Configuracion Reclasificacion Fiscal Mexico → New**.

1. Selecciona la **Company**
2. Clic en **"Cargar Reglas"** — carga reglas de Cobro (ventas, desde Configuracion Fiscal Mexico) y reglas de Pago (compras, desde Configuracion CFDI Recibidos). **Si el paso 3 no se completó, las reglas de Pago no aparecerán.**
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

Los items de venta en México requieren tres campos fiscales obligatorios. Sin ellos el sistema bloquea el submit de la Sales Invoice.

**En Stock → Item → New:**

| Campo | Dónde | Descripción |
|---|---|---|
| `fm_producto_servicio_sat` | Pestaña Fiscal México | Clave del catálogo SAT `c_ClaveProdServ`. Obligatorio — sin esta clave el sistema bloquea el guardado de la factura. |
| `fm_unidad_sat` | Pestaña Fiscal México | Clave de unidad SAT `c_ClaveUnidad` (ej: `H87 - Pieza`, `KGM - Kilogramo`, `GRM - Gramo`). Debe coincidir con la unidad real del producto. |
| **Item Group** | Datos generales | El grupo determina el tratamiento de impuestos — ver tabla abajo. |

**Nota sobre el catálogo SAT:** el campo `fm_producto_servicio_sat` es un Link a `SAT Producto Servicio`. Si la clave SAT que necesitas no existe en ese catálogo, debes crearla primero en **Facturación México → SAT Producto Servicio → New** con el código y descripción correctos del catálogo SAT vigente.

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

**Mapeo de cliente (para addendas EDI):**

Si el cliente requiere addenda (ej: La Comer, Liverpool), cada item necesita un mapeo en la pestaña **Sales → Customer Details**:

| Campo | Descripción |
|---|---|
| **Customer Name** | El cliente con addenda (ej: COMERCIAL CITY FRESKO) |
| **Ref Code** | Código / GTIN que el cliente asigna a este producto en su sistema |
| **fm_customer_uom** | Código de unidad que el cliente espera en la addenda (ej: `H87`, `KGM`) |
| **fm_customer_description** | Descripción del producto según catálogo del cliente |

Sin este mapeo, la addenda generará el GTIN vacío y el cliente rechazará el CFDI en su sistema EDI.

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
