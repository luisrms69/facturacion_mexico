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

## Indicador visual en el Desk (issue #171)

Para que el ambiente sea perceptible sin competir con los avisos fiscales de Sales Invoice / Factura
Fiscal Mexico, el Desk muestra **solo una franja inferior en la navbar global**, alimentada por la
misma fuente (`get_fm_environment()`, publicada en `frappe.boot.fm_environment` vía `boot_session`):

| `fm_environment` | Navbar del Desk | Resto de la UI |
|---|---|---|
| `production` | sin cambios | sin cambios |
| `sandbox` | franja inferior **ámbar** | sin cambios |
| ausente / inválido | franja inferior **roja** | sin cambios |

No añade badges, mensajes flotantes, indicadores dentro de formularios, alerts ni dialogs; no usa
`sandbox_mode`, ni lógica por Company, ni polling, ni llamadas al servidor (el valor viaja en el
boot). El estilo solo aplica un `border-bottom` de 4px al `.page-head` de la página **activa** (via
`app_include_css`); los `.page-head` de páginas inactivas no se pintan porque Frappe los mantiene en
un contenedor `display:none`. Funciona en tema claro/oscuro.

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
