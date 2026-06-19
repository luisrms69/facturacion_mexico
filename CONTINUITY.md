# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-19
**Rama activa:** `fix/post-golive-corrections`
**Tarea actual:** PR abierto — fix/post-golive-corrections → main

---

## Recuperación rápida

Estoy trabajando en:
PR de correcciones post go-live LlantasCS — UI CPMX y pdf_custom_section configurable.

Plan que estoy siguiendo:
PR #195 (o el número asignado) — esperando review de CodeRabbit y merge.

Objetivo inmediato:
Merge del PR y deploy en producción (erpstar.llantascs.com).

Criterio de avance:
PR mergeado, bench migrate en producción, textos PPD/PUE configurados en Company Settings de LlantasCS.

---

## Estado actual

### Ya cerrado (en esta rama)
- `1b4f82e` fix(cpmx): botón "Descargar PDF+XML" movido al grupo "Comprobantes"
- `5cedd69` feat(timbrado): pdf_custom_section configurable por empresa (17/17 tests)
- `5ac431b` docs(usuario): sección "Contenido PDF del CFDI" en getting-started
- `ca5bb73` docs(usuario): corrección — sin textos prescriptivos ni recomendados

### En progreso
- PR abierto — esperando CodeRabbit y autorización de merge

### Pendiente inmediato
1. Merge del PR
2. Deploy: `bench migrate` en erpstar.llantascs.com
3. Configurar manualmente textos PUE/PPD en Company Settings de LlantasCS

### No repetir
- NO persistir `fm_pdf_custom_section` en el payload — solo en `_process_timbrado_success`
- NO incluir textos específicos del cliente en docs generales del app
- NO hardcodear leyendas PUE/PPD en código

---

## Decisiones vigentes
- `pdf_custom_section` solo para CFDI tipo I
- Sin defaults en pdf_nota_pue/ppd — vacío = no enviar
- Solo Company Settings (sin Customer ni SI override)
- Template PPD validado al guardar (placeholder desconocido = ValidationError)
- Persistencia solo en timbrado exitoso

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_fiscal/timbrado_api.py` — `_build_pdf_custom_section`, `_process_timbrado_success`
- `docs/usuario/getting-started.md` — sección "Contenido PDF del CFDI"

### No tocar
- `patches.txt` — vacío por diseño (RG-010b)
- `one_offs/` — no commitear

---

## Riesgos / cuidados
- Requiere `bench migrate` en producción al deployar — sin esto los campos no existen en BD
- LlantasCS debe configurar manualmente sus textos PPD/PUE en Company Settings
- `llantascs-mig.local` (8409) tiene encryption key distinta — API keys deben re-ingresarse
