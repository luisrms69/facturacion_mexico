# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-19
**Rama activa:** `fix/ffm-cancel-permissions`
**Tarea actual:** Restricción de permisos de cancelación FFM — commit en curso

---

## Recuperación rápida

Estoy trabajando en:
Fix de permisos para cancelación de Factura Fiscal Mexico — solo 3 roles autorizados.

Plan que estoy siguiendo:
Correcciones post go-live LlantasCS — permisos y flujo de cancelación.

Objetivo inmediato:
Commit + push + PR de este fix.

Criterio de avance:
PR mergeado y cambios en producción vía bench migrate.

---

## Estado actual

### Ya cerrado
- PR #195 mergeado: fix pdf_custom_section + CodeRabbit
- PR #193 mergeado: fixes post go-live timbrado + CPMX email
- PR #192 mergeado: migración Fase 2 FFM + CPMX

### En progreso
- Rama `fix/ffm-cancel-permissions`: permisos cancelación FFM

### Pendiente inmediato
1. Push de esta rama
2. Abrir PR
3. Deploy en producción: `bench migrate` + `bench build`
4. Configurar textos PUE/PPD en Company Settings de LlantasCS en producción
5. Ejecutar `fix_fm_tax_regime_from_tax_category.py` en producción cuando esté listo
6. Reporte pendientes migración entregado al cliente (93 casos + 21 SIs adicionales)

### No repetir
- NO persistir fm_pdf_custom_section en el payload — solo en _process_timbrado_success
- NO mergear chore/track-working-docs-archive directo — tiene código obsoleto mezclado
- Bug `frappe.utils.get_site_config` en factura_fiscal_mexico.js pendiente — no urgente

---

## Decisiones vigentes
- Solo 3 roles pueden cancelar FFM: System Manager, Facturacion Mexico Manager, Facturacion Mexico System Manager
- Accounts Manager y Accounts User: cancel=0 explícito en DocPerm
- `pdf_custom_section` solo para CFDI tipo I
- Solo Company Settings (sin Customer ni SI override)

---

## Archivos relevantes ahora

### Probablemente editar
- `facturacion_mexico/facturacion_fiscal/doctype/factura_fiscal_mexico/factura_fiscal_mexico.py`
- `facturacion_mexico/facturacion_fiscal/doctype/factura_fiscal_mexico/factura_fiscal_mexico.json`

### No tocar
- `patches.txt` — vacío por diseño (RG-010b)
- `one_offs/fix_fm_tax_regime_from_tax_category.py` — pendiente ejecución producción

---

## Riesgos / cuidados
- Producción necesita `bench migrate` para activar permisos nuevos en FFM
- `chore/track-working-docs-archive` tiene código obsoleto — no mergear sin cherry-pick
- Bug `frappe.utils.get_site_config` en JS genera ruido en consola pero no bloquea funcionalidad
