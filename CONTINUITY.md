# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-06-02
**Rama activa:** `feature/cfdi-recibidos-cost-center-project`
**Tarea actual:** CI fixes — rama protegida en GitHub, PR draft abierto

---

## Recuperación rápida

Estoy trabajando en:
Proteger trabajo antes de bench update. Rama pusheada, PR draft #174 abierto.
CI fallaba por dos bugs de tests — corregidos.

Objetivo inmediato:
Esperar que CI pase, luego continuar con las demás apps antes del bench update.

---

## Estado actual

### Ya cerrado en esta rama
- cost_center y project en CFDI Recibido ✅
- purchase_invoice_builder propaga al PI ✅
- Plan CoA SAT committed ✅
- Rama pusheada a GitHub ✅
- PR draft #174 abierto ✅
- Evidencias La Comer copiadas fuera del repo ✅
- CI fixes: ruff format + test bug proyecto naming series ✅

### Pendiente
1. CI verde en PR #174
2. Completar auditoría de otras apps (condominium_management, erpnext_proposals, wiki)
3. Bench update
4. Restaurar sitio Actiglobal

### No repetir
- `cls.project = proj_name` cuando ERPNext usa naming series — usar `proj.name`
- link_filters en JSON sobreescriben set_query JS

---

## Archivos relevantes
- `working_docs/active/PLAN_CFDI_RECIBIDOS_COA_SAT_NORMALIZATION.md`
- Evidencias cliente: `/home/erpnext/Developer/frappe-infrastructure/checkpoints/addenda_la_comer_evidencia_backup_20260602`
