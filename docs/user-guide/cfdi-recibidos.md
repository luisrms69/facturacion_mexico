# CFDI Recibidos

Guía para registrar y clasificar comprobantes fiscales recibidos de proveedores.

---

## ¿Qué es un CFDI Recibido?

Un CFDI Recibido es el XML que emite un proveedor cuando te vende un bien o servicio. Este módulo permite cargar esos XMLs a ERPNext, validarlos contra el SAT, identificar al proveedor automáticamente y clasificar cada concepto para facilitar el registro contable.

---

## Flujo de trabajo

```
1. Cargar XML  →  2. Resolver proveedor  →  3. Clasificar conceptos  →  4. Listo
   (upload_xml)    (resolve_supplier)        (classify_concepts)
```

Cada paso avanza el estado del documento:

| Estado | Significado |
|---|---|
| `Parseado` | XML cargado y válido, proveedor pendiente |
| `Falta proveedor` | No se encontró Supplier con el RFC del emisor |
| `Falta clasif.` | Proveedor asignado, pero hay conceptos sin regla |
| `Listo` | Todos los conceptos clasificados — listo para registro contable |
| `Error` | El RFC receptor del CFDI no corresponde a la empresa, o XML inválido |

---

## Paso 1 — Cargar el XML

Desde la API o desde la interfaz, carga el XML del CFDI recibido indicando la empresa receptora.

El sistema valida automáticamente:

- Que el XML sea **CFDI versión 4.0** (los CFDI 3.3 son rechazados)
- Que el **RFC receptor** en el XML coincida con el RFC configurado en la empresa de ERPNext
- Que el UUID no sea **duplicado** (si ya existe, retorna el documento existente)

Si la validación pasa, se crea el documento `CFDI Recibido` con todos los datos del comprobante y el XML adjunto de forma privada.

---

## Paso 2 — Resolver proveedor

El sistema busca automáticamente un `Supplier` en ERPNext cuyo campo **Tax ID** coincida con el RFC emisor del CFDI.

!!! info "Vinculación automática"
    Si encuentras que el proveedor no se resuelve automáticamente, verifica que el campo `Tax ID` del `Supplier` esté configurado con el RFC correcto.

**Si el proveedor no existe en ERPNext:**

El documento queda en estado `Falta proveedor`. Tienes dos opciones:

1. **Crear el proveedor** en ERPNext con el RFC correcto en `Tax ID`, y luego ejecutar `resolve_supplier` nuevamente.
2. **Vinculación manual**: llamar a `resolve_supplier` con el parámetro `supplier` para asignar directamente un Supplier aunque el RFC no coincida.

!!! warning "Este módulo no autocrea proveedores"
    Por diseño, el sistema no crea Suppliers automáticamente. Es necesario que el proveedor ya exista en ERPNext.

---

## Paso 3 — Clasificar conceptos

Cada línea del CFDI (concepto) necesita una **regla de clasificación** que indique a qué Item o cuenta de gasto de ERPNext corresponde.

Las reglas se configuran en el DocType **CFDI Concepto Mapping**.

### Crear reglas de clasificación

Puedes crear reglas desde el Desk (DocType `CFDI Concepto Mapping`) o via la API `save_mapping_rule`.

Una regla define:

- **¿A qué empresa aplica?** — vacío significa que aplica a todas las empresas
- **¿A qué proveedor aplica?** — por RFC, o vacío para cualquier proveedor
- **¿A qué clave SAT aplica?** — la clave del producto/servicio, o vacío para cualquier clave
- **¿A qué destino mapea?** — un `Item` de ERPNext o una cuenta de `Gastos`

### Niveles de especificidad

Cuando se clasifica un concepto, el sistema busca la regla más específica disponible:

| Nivel | Qué aplica |
|---|---|
| **1 — Exacto** | Empresa + RFC proveedor + clave SAT exactos |
| **2 — Proveedor** | Empresa + RFC proveedor (cualquier clave SAT) |
| **3 — Clave SAT** | Empresa + clave SAT (cualquier proveedor) |

Si ninguna regla aplica, el concepto queda sin clasificar y el CFDI pasa a `Falta clasif.`

### Ejemplo de configuración de reglas

**Caso típico: proveedor de software con clave SAT 43231500**
```
Empresa:          Mi Empresa S.A. de C.V.
RFC proveedor:    SOFT901011AAA
Clave SAT:        43231500
Tipo destino:     Cuenta de Gasto
Cuenta:           Gastos de Software - MX
```

**Fallback genérico para gastos varios (cualquier proveedor, cualquier clave)**
```
Empresa:          Mi Empresa S.A. de C.V.
RFC proveedor:    (vacío)
Clave SAT:        (vacío)
Tipo destino:     Cuenta de Gasto
Cuenta:           Gastos Generales - MX
```

!!! tip "Estrategia recomendada"
    Empieza con reglas genéricas (fallbacks) y agrega reglas específicas conforme identifiques proveedores frecuentes. El sistema siempre usa la regla más específica disponible.

---

## Preguntas frecuentes

**¿Qué pasa si cargo el mismo XML dos veces?**
El sistema detecta el duplicado por UUID y retorna el documento existente sin crear uno nuevo.

**¿Puedo cargar CFDIs de versión 3.3?**
No. Este módulo solo soporta CFDI 4.0. Los XMLs de versión 3.3 son rechazados con un mensaje de error explícito.

**¿El RFC del CFDI debe coincidir exactamente con el RFC de la empresa?**
Sí. Si el RFC receptor en el XML no coincide con `Company.tax_id` en ERPNext, el CFDI queda en estado `Error`. Verifica que el RFC de la empresa esté correctamente configurado en ERPNext.

**¿Qué es una regla global?**
Una regla con `company` vacío aplica a todas las empresas del sistema. Útil para configuraciones comunes entre múltiples empresas.

**¿Puedo desactivar una regla sin borrarla?**
Sí. Cada regla en `CFDI Concepto Mapping` tiene el campo `is_active`. Las reglas inactivas no participan en el proceso de clasificación.
