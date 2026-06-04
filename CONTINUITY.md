# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-04
**Rama activa:** `feature/expense-account-coa-sat-resolution`
**Tarea actual:** commit listo para ejecutar — feature expense_account + catálogo GASTO-* + docs Fase 2

---

## Recuperación rápida

Estoy trabajando en:
Feature de resolución automática de expense_account en CFDI Recibidos + catálogo de items
de gasto + documentación completa de Fase 2 (configuración fiscal del app).

Plan que estoy siguiendo:
`working_docs/active/PLAN_CFDI_RECIBIDOS_COA_SAT_NORMALIZATION.md`

Objetivo inmediato:
Commit aprobado → push → PR. Luego: Fase 3 en actiglobal-restore.dev (Customer + Item para primera emisión).

Criterio de avance:
PR abierto, CI verde.

---

## Estado actual

### Ya cerrado
- expense_account resolution: modo patron/matriz_equivalencias/manual_asistido ✅
- Nuevo DocType Mapeo Equivalencias SAT ✅
- Configuracion CFDI Recibidos: 4 campos nuevos ✅
- Custom Field Item Group-fm_codigo_sufijo_sat ✅
- Item Groups familias 701 y 702 (gastos financieros, productos financieros) ✅
- 105 items GASTO-* (84 base + 21 overlay operativo) ✅
- Fixture sat_claves_gastos_comunes.json (55 claves SAT) ✅
- Tests: 30/30 test_expense_account_resolver ✅
- Docs getting-started.md: Fase 2 completa (wizard + cuentas IVA + reclasificación) ✅
- Docs cfdi-recibidos.md: items GASTO-* corregido ✅
- actiglobal-restore.dev: sitio restaurado, CoA normalizado ###-##-###, Fase 2 configurada ✅

### Pendiente inmediato
1. Commit (aprobado, listo para ejecutar)
2. Push + PR
3. Fase 3 actiglobal-restore.dev: configurar 1 Customer + 1 Item para primera emisión CFDI

### No repetir
- `cls.project = proj_name` → usar `proj.name` (naming series ERPNext)
- link_filters en JSON sobreescriben set_query JS
- No documentar basándose en código — pensar desde la perspectiva del usuario
- `account_number` es número operativo de la empresa, NO el Código Agrupador SAT

---

## Decisiones vigentes
- Tres modos de resolución expense_account: patron (default {f}{s}000), matriz_equivalencias, manual_asistido
- CoA Actiglobal Cloud Experts: patrón {f}{s}000 → validado 100% de 500 cuentas hoja
- items GASTO-* son de compra: fm_producto_servicio_sat no es requerido para PI
- Overlay de 21 items: subclasificaciones frecuentes, NO reemplazan los 84 base
- GASTO-FIN-* prefix aprobado para familia 701

---

## Archivos relevantes ahora

### Leer primero
- `working_docs/active/PLAN_CFDI_RECIBIDOS_COA_SAT_NORMALIZATION.md`

### Probablemente editar (próxima fase)
- `facturacion_mexico/cfdi_recibidos/services/purchase_invoice_builder.py`
- `facturacion_mexico/cfdi_recibidos/doctype/configuracion_cfdi_recibidos/`

### No tocar
- `patches.txt` — vacío por diseño
- `working_docs/active/addenda_la_comer_evidencia/` — evidencias cliente, NO commitear

---

## Riesgos / cuidados
- one_offs/ no van en el commit
- bench update de otras apps aún pendiente (wiki, erpnext_proposals con cambios sin commit)
- Evidencias La Comer respaldadas: `/home/erpnext/Developer/frappe-infrastructure/checkpoints/addenda_la_comer_evidencia_backup_20260602`
