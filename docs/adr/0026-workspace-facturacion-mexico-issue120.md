# ADR 0026 — Workspace "Facturación México" (Issue #120)

**Fecha:** 2026-05-14
**Estado:** Parcial — secciones funcionales, pendientes documentados
**Autor:** Luis Montanaro / Claude Sonnet 4.6

---

## Contexto

Issue #120 requería exponer un workspace accesible desde el Desktop de Frappe v16
que agrupara todos los DocTypes, reportes y configuraciones de la app
`facturacion_mexico`. El Desktop de Frappe v16 usa una arquitectura de 3 niveles
que difiere significativamente de Frappe v15.

---

## Arquitectura Frappe v16 — 3 archivos obligatorios

Un workspace en una app custom requiere tres archivos distintos:

```text
<app>/<módulo>/workspace/<name>/<name>.json     ← Workspace principal
<app>/desktop_icon/<scrubbed_name>.json         ← Icono en el Desktop
<app>/workspace_sidebar/<scrubbed_name>.json    ← Sidebar de navegación
```

### Regla crítica del nombre de archivo (scrubbing)

`frappe.scrub()` convierte el nombre del workspace al nombre esperado del archivo.
Conserva acentos y caracteres especiales.

Ejemplo: `"Facturación México"` → `frappe.scrub` → `"facturación_méxico"`

Si el archivo se llama `facturacion_mexico.json` (sin acentos), la función
`remove_orphan_entities()` en `frappe/model/sync.py` elimina silenciosamente el
Desktop Icon y el Workspace Sidebar tras crearlos en `bench migrate`.

**Este es un bug silencioso** — el workspace se crea y se borra en el mismo migrate
sin ningún error visible en el log.

### Regla del campo `type`

El workspace NO debe incluir el campo `"type"` en el JSON. Si lo incluye, Frappe
lo marca internamente como `type="Custom"` y el workspace no aparece en el Desktop
automáticamente al instalar la app.

Los workspaces en `fixtures/workspace.json` siempre son importados con `type="Custom"`.
Los workspaces en el directorio del módulo son importados con `type=NULL` (correcto).

### Regla del campo `module`

`module` debe coincidir con un módulo registrado en `modules.txt`.
Para `facturacion_mexico`, el módulo es `"Facturacion Fiscal"` (sin acento en "n").
El workspace vive en `facturacion_fiscal/workspace/...`.

---

## Decisión

1. Ubicar el workspace en `facturacion_fiscal/workspace/facturacion_mexico/facturacion_mexico.json`
   con `module = "Facturacion Fiscal"` y sin campo `type`.
2. Nombrar los archivos `desktop_icon` y `workspace_sidebar` con acentos:
   `facturación_méxico.json` para que `remove_orphan_entities` no los elimine.
3. Vaciar `fixtures/workspace.json` — el workspace ya no se gestiona vía fixtures globales.
4. Remover la declaración de fixture Workspace en `hooks.py`.

---

## Estado al cierre parcial (2026-05-14)

### Funcionando

- Workspace aparece en el Desktop de Frappe v16
- 5 secciones organizadas visibles en el body:
  - Facturación Fiscal (4 DocTypes)
  - Documentos ERPNext (Sales Invoice, Payment Entry)
  - Configuración Fiscal (6 DocTypes)
  - Catálogos SAT (6 catálogos)
  - Auditoría (3 reportes + FacturAPI Response Log)
- Desktop Icon y Workspace Sidebar sobreviven `bench migrate`

### Pendiente — Issue #120 permanece abierto

- **Top bar icons:** El array `shortcuts` tiene 22 entradas pero ninguna aparece
  en la barra superior del workspace. Causa no determinada — posiblemente
  requiere el campo `"color"` o `"type"` por entrada en el array.
- **Secciones con links rotos:** Los reportes "Facturas Sin Timbrar",
  "Complementos Pendientes" y "Auditoría Fiscal" en la sección Auditoría pueden
  no existir como Report DocType — requieren validación en site.
- **Configuracion Reclasificacion Fiscal Mexico / Mapeo Cuenta Fiscal Mexico /
  Mapeo Reclasificacion Fiscal Payment Entry:** Requieren verificar existencia
  de los DocTypes en la app antes del next migrate.
- **Roles:** El workspace actualmente no tiene restricción de roles (`roles: []`).
  Pendiente agregar roles `Facturacion Mexico User` y `Facturacion Mexico Manager`.

---

## Lecciones aprendidas

1. **No usar fixtures globales para workspaces** — se importan como `type=Custom`
   y no aparecen en el Desktop automáticamente.
2. **`frappe.scrub()` preserva acentos** — diferente a `slugify`. Verificar siempre
   el nombre de archivo con `python3 -c "import frappe; print(frappe.scrub('nombre'))"`.
3. **`remove_orphan_entities()` es silenciosa** — no lanza error, simplemente borra.
   Difícil de diagnosticar sin leer el código fuente de Frappe.
4. **El campo `type` es trampa** — al incluirlo en el JSON, Frappe asume que el
   workspace es custom y lo excluye del flujo estándar de apps.
5. **Preferir nombres sin acentos** para futuros workspaces (ej: `"Facturacion Fiscal"`)
   para evitar el problema de scrubbing completamente.

---

## Referencias

- Issue: #120
- Branch: `feature/issue120-workspace`
- Commits: `92c8251`, `ab8d1aa`
- Frappe source: `frappe/model/sync.py` → `remove_orphan_entities()`
- ADR relacionado: `0024-addendas-pre-timbrado-issue129.md`
