# ADR 0039 — Marca visual de STAGING a nivel de bench (rediseño de #171)

**Estado:** Aceptado
**Issue:** #171
**Fecha:** 2026-08-15
**Relacionado:** [0038](0038-guarda-ambiente-fiscal-fm-environment.md) (#215)

## Contexto

La primera implementación de #171 (commit `555fe07`, v1.4.0) mostraba el ambiente fiscal en el Desk
leyendo `get_fm_environment()` y publicándolo en `frappe.boot.fm_environment` vía `boot_session`, con
un JS que asignaba una clase al `<body>` y un CSS con franja ámbar/roja según el ambiente.

Se demostró experimentalmente (servidor `erp.buzola.mx`) que esa arquitectura es **poco confiable**
por dos cachés de Frappe independientes:

1. **`app_hooks`** (caché de hooks): tras `bench update`, los hooks nuevos (`app_include_css/js`,
   `boot_session`) podían quedar *stale* hasta un `clear-cache` manual, por una carrera de
   repoblación de workers viejos (los hooks son *code-derived*). Afecta a cualquier `hooks.py` nuevo.
2. **`bootinfo`** (caché de sesión, hash Redis por usuario, sin TTL): `boot_session` corre **solo en
   cache miss**, así que su salida queda horneada en el `bootinfo` cacheado. Al cambiar
   `fm_environment` en `site_config.json`, el servidor devolvía el valor nuevo de inmediato, pero el
   navegador seguía mostrando el viejo tras refresh y hard refresh; solo `clear-cache` (o un login
   real) lo corregía.

El riesgo crítico: el indicador podía mostrar **un ambiente incorrecto de forma persistente y no
evidente** (p. ej. franja de "pruebas" en un servidor productivo), ocultando la discrepancia que
pretendía señalar. Una señal de seguridad incorrecta es peor que no tener señal.

## Decisión

#171 deja de representar dinámicamente `fm_environment`. Se convierte en una **marca visual estática
a nivel de bench/servidor** que solo distingue STAGING de producción:

1. **Producción** → sin marca visual.
2. **STAGING** → una franja **cian** en la navbar global del Desk, cargada por bench mediante
   `app_include_css` en `common_site_config.json`:

   ```json
   { "app_include_css": ["/assets/facturacion_mexico/css/fm_staging_marker.css"] }
   ```

Frappe (`frappe/www/desk.py`) concatena `frappe.conf.get("app_include_css")` con los hooks de apps,
por lo que esta ruta **no** pasa por la caché `app_hooks` ni por `bootinfo`. La configuración se lee
con un cache en memoria por proceso de **TTL 60 s** (`config.py`, `site_cache`), así que un cambio se
refleja en ≤60 s sin `clear-cache` ni restart.

- El CSS vive en `facturacion_mexico/public/css/fm_staging_marker.css` y se sirve en
  `/assets/facturacion_mexico/css/fm_staging_marker.css`. Como `/assets/<app>/…` es un symlink de
  bench, se sirve para **todos los sitios del bench** aunque un sitio no tenga la app instalada.
- Sin JS, sin `frappe.boot`, sin `boot_session`, sin `extend_bootinfo`, sin AJAX, sin polling, sin
  BD, sin lógica por Company, sin lectura dinámica de `fm_environment`.
- El CSS solo aplica un `border-bottom` cian al encabezado de página del Desk (`.page-head`, el
  elemento realmente presente en el DOM del Desk v16); no toca fondos, formularios, badges, alerts ni
  dialogs.

**#215 queda intacto.** `fm_environment` (por sitio, en `site_config.json`) sigue siendo la única
protección fiscal real, server-side, y no depende de esta marca.

## Consecuencias

- La marca es fiable: no puede quedar *stale* de forma persistente ni mostrar un ambiente equivocado,
  porque no lee un valor por-sitio cacheado — es una marca fija del bench de staging. Producción,
  otro bench, simplemente no la declara.
- La confiabilidad ya no depende de disciplina manual de caché.
- La marca es **por bench**, no por-sitio: distingue servidor de staging vs producción, no el
  `fm_environment` de cada sitio. Es una capa de aviso operativo, no una guarda fiscal.
- Persiste el costo de una-sola-vez de activación de `app_hooks` **solo** al retirar/agregar hooks en
  un deploy puntual (general de Frappe); no afecta el runtime de la marca nueva.

## Alternativa descartada

- **Mantener el indicador por `boot_session`/`frappe.boot`:** descartado por el *staleness* de
  `bootinfo` (persistente, sin TTL, no corregido por refresh/hard refresh).
- **Moverlo a `extend_bootinfo`** (corre en cada boot, evita el *staleness* de valor): descartado
  frente a la opción por `common_site_config`, que además elimina el JS y el boot por completo y no
  requiere que `facturacion_mexico` esté instalada.
- **Alojar el CSS en otra app / infraestructura:** descartado; se mantiene en `facturacion_mexico` y
  el servido por bench cubre todos los sitios.
- **Modal al login:** descartado como señal principal por no ser persistente (una sesión reanudada no
  lo ve).
