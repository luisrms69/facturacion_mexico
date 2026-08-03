# Notas de Crédito

Guía para emitir una Nota de Crédito (CFDI tipo **E - Egreso**) a partir de una devolución de venta,
y para elegir entre **Devolución de mercancía** y **Descuento / Bonificación**.

Una Nota de Crédito nace de un **Sales Invoice Return** (devolución) vinculado a una factura de origen.
Mientras la devolución esté en **Borrador (Draft)** puedes decidir con qué tratamiento fiscal se
emitirá; el sistema deriva el resto de los datos fiscales automáticamente.

---

## Punto de partida

1. Crea el **Sales Invoice Return** contra la factura de origen (campo *Return Against*).
2. **Guárdalo** (queda en Borrador).

En una devolución guardada, en Borrador y con factura de origen, aparece —en el menú **Acciones**—
**uno** de estos botones, según el estado actual del documento:

- **Aplicar como Descuento / Bonificación** — si la devolución está tratada como devolución de mercancía.
- **Revertir a Devolución de mercancía** — si la devolución ya está tratada como descuento.

Solo se muestra un botón a la vez: el que te lleva al **otro** tratamiento.

---

## Aplicar como Descuento / Bonificación

En el menú **Acciones**, pulsa **Aplicar como Descuento / Bonificación**.

El sistema:

- Cambia la línea al Item real **Descuento**.
- Deja de afectar inventario (**update_stock = 0**).
- Construye la descripción del descuento con referencia a la línea original.
- Usa la **Cuenta de Descuentos y Bonificaciones** configurada para la empresa.
- Conserva los vínculos con la factura y la línea original.

Confirma con el mensaje: *"Nota de crédito preparada como Descuento / Bonificación."*

Al **crear la Factura Fiscal** desde esta devolución, el sistema deriva automáticamente:

| Dato fiscal | Valor derivado |
|---|---|
| Tipo de Nota de Crédito | **Descuento / Bonificación** |
| TipoRelación SAT | **01** |
| Uso CFDI | **G02** |
| Forma de Pago | **15** |

---

## Revertir a Devolución de mercancía

Mientras la devolución siga en **Borrador**, en el menú **Acciones** pulsa
**Revertir a Devolución de mercancía**.

El sistema:

- Restaura el Item original.
- Restaura la descripción original.
- Restaura la cuenta de ingresos original.
- Restaura el comportamiento de inventario original.
- Conserva los vínculos con la factura de origen.

Confirma con el mensaje: *"Nota de crédito revertida a Devolución de mercancía."*

Al **crear la Factura Fiscal**, el sistema deriva:

| Dato fiscal | Valor derivado |
|---|---|
| Tipo de Nota de Crédito | **Devolución de mercancía** |
| TipoRelación SAT | **03** |
| Uso CFDI | **G02** |
| Forma de Pago | Conforme a la lógica normal aplicable |

---

## Alternar antes de guardar / enviar

Mientras el documento permanezca en **Borrador**, puedes alternar entre ambas opciones tantas veces
como necesites antes de guardar o enviar.

El tipo fiscal que finalmente usa la Factura Fiscal **depende del estado real** en que quede la
devolución: si la dejas como descuento, se emite como Descuento / Bonificación; si la dejas como
devolución de mercancía, se emite como Devolución.

---

## Configuración requerida

Cada empresa debe tener configurada la **Cuenta de Descuentos y Bonificaciones** en
**Facturacion Mexico Company Settings**.

Si falta esa cuenta, el sistema **bloquea la conversión a descuento** y muestra el mensaje
correspondiente. Configúrala antes de usar *Aplicar como Descuento / Bonificación*.

---

## UUID relacionado

Una Nota de Crédito requiere el **UUID fiscal real** del CFDI de la factura de origen. Al crear la
Factura Fiscal se solicita cuando no puede obtenerse automáticamente.

Usa siempre el UUID verdadero del comprobante origen. No uses UUID arbitrarios fuera de ambientes de
prueba.

---

## Botones fiscales en la devolución

El botón fiscal que ves en la devolución depende de su estado:

- **Sin Factura Fiscal**, con condiciones fiscales y RFC válidos → **Crear Factura Fiscal**.
- **Con Factura Fiscal ya creada** (en Borrador o Timbrada) → **Abrir Factura Fiscal**.

No se crea una segunda Factura Fiscal desde la misma devolución: si ya existe una, se abre la
existente.

> Si el RFC del cliente está vacío o no validado, el botón **Crear Factura Fiscal** no aparece y se
> muestra un aviso indicando que debe validarse el RFC antes de crear la Factura Fiscal.
