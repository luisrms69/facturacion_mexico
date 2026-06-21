# Verificar estado en FacturAPI

El sistema mantiene sincronizado el estado de cada **Factura Fiscal Mexico (FFM)** con FacturAPI
de dos formas: **automáticamente** (una revisión periódica) y **manualmente** (un botón en el FFM).
En ambos casos el sistema **solo consulta** a FacturAPI: nunca timbra, cancela ni modifica la venta.

---

## Verificación manual (botón)

1. Abre la **Factura Fiscal Mexico** que quieres revisar.
2. En la barra de botones, entra al grupo **Comprobantes**.
3. Pulsa **"Verificar estado en FacturAPI"**.

El botón **solo aparece** cuando la FFM ya está **guardada** y tiene un comprobante en FacturAPI
(`facturapi_id`). Al pulsarlo, el sistema consulta el estado real en FacturAPI, actualiza la FFM si
corresponde y **recarga el documento** para mostrar el estado al día.

> El botón **no cancela la Sales Invoice**. Si la verificación confirma que el CFDI quedó
> **CANCELADO**, después puedes cancelar la Sales Invoice con el procedimiento normal.

### Resultados posibles

| Mensaje | Significa |
|---|---|
| **Sin cambios** | El estado local ya coincidía con FacturAPI. |
| **Estado actualizado** | La FFM se actualizó con el estado real del PAC. |
| **Cancelación pendiente** | La cancelación sigue en proceso (esperando al receptor). |
| **Cancelación aceptada** | El CFDI quedó cancelado. |
| **Cancelación rechazada** | El receptor rechazó la cancelación; el CFDI sigue vigente. |
| **Cancelación expirada** | La cancelación no procedió; el CFDI sigue vigente. |
| **Verificación ya en proceso** | Otra revisión (manual o automática) ya está consultando esta FFM. Espera un momento. |
| **Error de reconciliación** | No se pudo confirmar el estado (problema de conexión o de validación). Reintenta más tarde o reporta a soporte. |

---

## Verificación automática

El sistema revisa periódicamente las FFM que necesitan seguimiento (las que tienen sincronización
**pendiente** o una **cancelación en curso**) y las pone al día sin intervención. No requiere acción
del usuario.

---

## Despliegue (administradores)

La verificación automática se registra al desplegar la app:

```bash
bench --site <site> migrate
bench build --app facturacion_mexico
bench --site <site> clear-cache
```

⚠️ **Advertencia importante:**

- `migrate` **registra la tarea automática** (`hourly_long`).
- Con el **scheduler habilitado**, el motor puede **empezar a ejecutar consultas reales (GET)
  contra FacturAPI**.
- Por eso, **desplegar y habilitar el scheduler solo cuando se autorice iniciar ese tráfico** hacia
  FacturAPI.
- **No ejecutar una corrida real contra FacturAPI durante tareas de desarrollo o pruebas.**

`bench build` es necesario para que el botón **"Verificar estado en FacturAPI"** quede disponible
en la interfaz.
