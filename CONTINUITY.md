# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-19
**Rama activa:** `fix/ffm-cancel-permissions`
**Tarea actual:** Correcciones post go-live — permisos cancelación + cleanup 403/417

---

## Recuperación rápida

Estoy trabajando en:
Dos correcciones post go-live LlantasCS en la misma rama: (1) permisos de cancelación
FFM restringidos a 3 roles; (2) cleanup de errores 403/417 al refrescar FFM.

Plan que estoy siguiendo:
Correcciones post go-live LlantasCS. Multi-sucursal fiscal documentado en issue #196.

Objetivo inmediato:
Push + PR de esta rama.

Criterio de avance:
PR mergeado y cambios en producción vía bench migrate + bench build.

---

## Estado actual

### Ya cerrado
- PR #195 mergeado: fix pdf_custom_section + CodeRabbit
- PR #193 mergeado: fixes post go-live timbrado + CPMX email
- PR #192 mergeado: migración Fase 2 FFM + CPMX
- Issue #196 creado: habilitación explícita multi-sucursal fiscal por Company

### En progreso
- Rama `fix/ffm-cancel-permissions` (2 commits):
  - 1452ed5: permisos cancelación FFM (3 roles)
  - (en curso): cleanup 403/417 JS + prueba estática

### Pendiente inmediato
1. Push de esta rama
2. Abrir PR
3. Deploy en producción: `bench migrate` + `bench build`
4. Configurar textos PUE/PPD en Company Settings de LlantasCS en producción
5. Ejecutar `fix_fm_tax_regime_from_tax_category.py` en producción cuando esté listo
6. Multi-sucursal fiscal (issue #196) — implementación fin de semana

### No repetir
- NO persistir fm_pdf_custom_section en el payload — solo en _process_timbrado_success
- NO mergear chore/track-working-docs-archive directo — tiene código obsoleto mezclado
- NO conectar fm_branch al timbrado en esta rama — eso es trabajo del issue #196
- NO tocar series/folios/lugar_expedicion/payload en esta rama

### No repetir (multi-sucursal — para #196)
- El timbrado lee `branch` (campo inexistente en SI); SI usa `fm_branch`
- La serie siempre cae en "F" (timbrado_api.py:698)
- BranchFolioManager y Configuracion Fiscal Sucursal desconectados del timbrado
- El indicador debe ser explícito por Company: `multisucursal_fiscal_enabled`

---

## Decisiones vigentes
- Solo 3 roles cancelan FFM: System Manager, Facturacion Mexico Manager, Facturacion Mexico System Manager
- `control_multisucursal_field_visibility` solo oculta campos localmente (sin llamadas servidor)
- `pdf_custom_section` solo para CFDI tipo I

---

## Archivos relevantes ahora

### No tocar
- `patches.txt` — vacío por diseño (RG-010b)
- `one_offs/fix_fm_tax_regime_from_tax_category.py` — pendiente ejecución producción
- `timbrado_api.py` — NO modificar en esta rama (es trabajo de #196)

---

## Riesgos / cuidados
- Producción necesita `bench migrate` + `bench build` para activar permisos y JS nuevos
- `chore/track-working-docs-archive` tiene código obsoleto — no mergear sin cherry-pick
