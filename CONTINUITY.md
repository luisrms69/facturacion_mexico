# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-19
**Rama activa:** `fix/post-golive-corrections`
**Tarea actual:** Correcciones post go-live LlantasCS — PDF custom section + fixes UI

---

## Recuperación rápida

Estoy trabajando en:
Rama `fix/post-golive-corrections` con múltiples correcciones post go-live para LlantasCS.
Se está haciendo commit del feature `pdf_custom_section` ahora mismo.

Plan que estoy siguiendo:
Correcciones incrementales sin plan doc — cada fix se commitea en esta rama y al final va a PR.

Objetivo inmediato:
Commitear `pdf_custom_section` y continuar con más correcciones en la misma rama.

Criterio de avance:
Cuando no haya más correcciones pendientes, abrir PR de esta rama a main.

---

## Estado actual

### Ya cerrado (en esta rama)
- Commit `1b4f82e`: botón "Descargar PDF+XML" movido al grupo "Comprobantes" en CPMX

### En progreso
- `pdf_custom_section`: listo para commit — 17/17 tests, docs actualizados, persistencia
  solo en timbrado exitoso, sin textos hardcoded

### Pendiente inmediato
1. Commit de `pdf_custom_section` (este turno)
2. Más correcciones pendientes por definir
3. PR final de `fix/post-golive-corrections` → main

### No repetir
- NO persistir `fm_pdf_custom_section` en el build del payload — solo en `_process_timbrado_success`
- NO crear Custom Fields para `pdf_nota_pue`/`pdf_nota_ppd` — son campos nativos del DocType
- NO hardcodear textos PUE/PPD en código — la config es por empresa en Company Settings

---

## Decisiones vigentes
- `pdf_custom_section` solo para CFDI tipo I — tipos E y P quedan sin este campo
- Sin defaults en `pdf_nota_pue` y `pdf_nota_ppd` — vacío = no enviar
- Cascada de resolución: Solo Company Settings (sin Customer ni SI override)
- Template PPD validado en `validate()` de Company Settings — placeholder desconocido = error
- `_pending_pdf_custom_section` como atributo de instancia para diferir la persistencia

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_fiscal/timbrado_api.py` — funciones `_build_pdf_custom_section`, `_persist_pdf_custom_section`, bloque `_process_timbrado_success`

### Probablemente editar
- `facturacion_fiscal/doctype/facturacion_mexico_company_settings/` — si se ajustan campos

### No tocar
- `patches.txt` — vacío por diseño (RG-010b)
- `one_offs/` — no commitear

---

## Riesgos / cuidados
- `llantascs-mig.local` (8409) tiene encryption key diferente al backup — re-ingresar API keys manualmente
- `_pending_pdf_custom_section` queda como atributo de instancia si el timbrado es exitoso pero `_process_timbrado_success` falla antes de limpiar — no es crítico (el atributo se pierde con la instancia)
