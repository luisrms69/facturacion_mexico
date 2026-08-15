# Ambiente fiscal del sitio (`fm_environment`)

La emisión real de CFDIs depende de una variable **explícita por sitio**, no de la base de datos.
Esto evita que una copia restaurada de producción (staging/dev) timbre CFDIs reales por accidente.

## Variable

- **Nombre:** `fm_environment`
- **Ubicación:** `site_config.json` del sitio (no en la BD, no en `common_site_config.json`).
- **Valores permitidos:** `"production"` o `"sandbox"`.

Ejemplo del archivo `sites/<sitio>/site_config.json`:

```json
{
  "fm_environment": "production"
}
```

> **Estrictamente por-sitio.** El código comprueba la **presencia** de la clave `fm_environment` en el
> `site_config.json` **del propio sitio** (vía `frappe.get_file_json` sobre
> `frappe.get_site_path("site_config.json")`), **no** en la configuración mergeada (`frappe.conf` /
> `frappe.get_site_config()`, que combinan common + site). Por tanto, un `fm_environment` puesto en
> `common_site_config.json` **se ignora**; y un sitio que la declara explícitamente siempre cuenta,
> aunque el valor coincida con uno de common. Si el archivo no se puede leer, se bloquea (fail-closed).

## Comportamiento

| `fm_environment` | Credencial usada | Operación mutante al PAC |
|---|---|---|
| `"production"` | `api_key` (obligatoria) | Permitida si hay `api_key` |
| `"sandbox"` | `test_api_key` (obligatoria) | Permitida si hay `test_api_key` |
| ausente / valor inválido | ninguna | **Bloqueada (fail-closed)** |

Reglas adicionales:

- **Sin fallback** entre `api_key` y `test_api_key`: si falta la credencial del ambiente, se bloquea.
- **Protección extra:** si la credencial efectiva empieza con `sk_live_` y el ambiente **no** es
  `production`, se bloquea (protege contra una llave productiva colocada por error en `test_api_key`).
- **Solo se bloquean mutaciones** (POST/PUT/PATCH/DELETE: timbrar, cancelar, complementos, E-Receipts,
  Factura Global). Los **GET** (reconciliación, verificación de estado, validación de RFC) siguen
  permitidos.
- El bloqueo ocurre en el punto central `FacturAPIClient` **antes** de contactar a FacturAPI; el
  mensaje indica explícitamente que **no se contactó al PAC**. En background jobs, la excepción queda
  registrada en **Error Log** por el comportamiento estándar de Frappe.

`sandbox_mode` (campo de BD) **ya no decide** la credencial; se conserva como valor derivado
(`sandbox_mode = fm_environment == "sandbox"`) por compatibilidad de UI.

## Marca visual de STAGING en el Desk (issue #171)

> **Independiente de `fm_environment`.** Esta marca **no** representa el ambiente fiscal ni lo lee.
> Es una señal **a nivel de bench/servidor** que solo distingue el servidor de STAGING del de
> producción. La protección fiscal real la da la guarda de #215 descrita arriba, no esta franja.

El Desk de un servidor de STAGING muestra una **franja cian** en el borde inferior de la navbar
global. Producción **no** muestra ninguna franja.

### Cómo se activa

Se activa por **bench**, mediante `app_include_css` en `common_site_config.json` (soporte nativo de
Frappe: `frappe/www/desk.py` concatena `frappe.conf.get("app_include_css")` con los hooks de apps).
**No** usa `hooks.py`, `boot_session`, `frappe.boot`, JS, AJAX, polling, BD ni lógica por Company.

- **Servidor de STAGING** → `common_site_config.json` incluye la clave:

  ```json
  {
    "app_include_css": ["/assets/facturacion_mexico/css/fm_staging_marker.css"]
  }
  ```

- **Servidor de PRODUCCIÓN** → **no** se agrega esa clave. Sin franja.

El valor debe ser una **lista**. El cambio se refleja en ≤60 s (TTL del cache en memoria de la config
por proceso), sin `clear-cache` ni restart. No depende de `app_hooks` ni de `bootinfo`.

### Dónde vive el CSS

`facturacion_mexico/public/css/fm_staging_marker.css`, servido en
`/assets/facturacion_mexico/css/fm_staging_marker.css`. Como `/assets/<app>/…` es un symlink a nivel
de bench, el archivo se sirve para **todos los sitios del bench** aunque un sitio no tenga la app
instalada, siempre que los assets estén construidos (`bench build`). El CSS solo aplica un
`border-bottom` cian al encabezado de página del Desk (`.page-head`); no toca fondos, formularios,
badges, alerts ni dialogs.

## Por qué es a prueba de restore

`bench restore` restaura **la base de datos**, no `site_config.json`. Una copia restaurada desde
producción conserva su propio `site_config.json`; por tanto **no hereda** el `fm_environment` de
producción. Si la copia no declara el ambiente, queda **bloqueada** para emitir.

## Configuración requerida por sitio

Todo sitio que timbre debe declarar `fm_environment`:

- **Producción:** `"production"`.
- **Staging / desarrollo:** `"sandbox"`.

> **Importante (orden de despliegue):** fija `fm_environment` en el `site_config.json` de cada sitio
> **antes** de desplegar esta guarda. Si producción no lo declara al activarse la guarda, su timbrado
> legítimo quedaría bloqueado.
