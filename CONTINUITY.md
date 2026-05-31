# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-31
**Rama activa:** `feat/multi-company-facturapi-settings`
**Tarea actual:** Migración multi-company — E-Receipts y Factura Global committed, campos pendientes por revisar

---

## Recuperación rápida

Estoy trabajando en:
Migración campo por campo de `Facturacion Mexico Settings` (Single) a `Facturacion Mexico Company Settings`.
Sección básica, E-Receipts y Factura Global ya committed. Quedan referencias al Single sin resolver.

Plan que estoy siguiendo:
`working_docs/active/PLAN_MULTI_COMPANY_FACTURAPI_SETTINGS.md`

Objetivo inmediato:
Resolver referencias restantes al Single detectadas en grep exhaustivo (Grupos A-D).

Criterio de avance:
Cero llamadas activas a `frappe.get_single("Facturacion Mexico Settings")` fuera del
propio DocType y archivos de inicialización.

---

## Estado actual

### Ya committed en esta rama
- cb5cf42: DocType base + sección básica (campos 1-12)
- este commit: E-Receipts (campos 13-18) + Factura Global (campos 19-21)

### Pendiente — referencias activas al Single sin resolver
| Archivo | Campo/uso | Decisión pendiente |
|---|---|---|
| `install.py:1919-1923` | Diagnóstico: `pac_name`, `pac_api_key`, `pac_test_mode` — phantom | Eliminar líneas |
| `facturas_globales/hooks_handlers/factura_global_submit.py:119-126` | `notify_global_generation`, `global_notification_emails` | Eliminar (feature no implementada) |
| `multi_sucursal/branch_manager.py:368-378` | `api_key`, `sandbox_mode`, etc. | Actualizar a Company Settings |
| `sales_invoice_cancel.py:122` | `auto_cancel_fiscal` — phantom | Eliminar check |
| `validaciones/api.py:1441` | `daily_rfc_validation_limit` — custom field | ¿Migrar? ¿Constante? |
| `sat_validation_cache.py:23` | `rfc_cache_days` — phantom | ¿Migrar? ¿Constante? |
| `addendas/addenda_auto_detector.py:219` | `addenda_detection_rules` — phantom | Eliminar check |
| `dashboard_fiscal/...` | `global_invoice_monthly_limit`, `ereceipt_monthly_limit` | Eliminar (dashboard roto) |
| `sales_invoice_validate.py:33` | `db.exists(Settings)` como guard | Reemplazar por check Company Settings |

### No repetir
- No hacer fallback al Single para campos ya migrados
- No commitear en main directamente
- No hacer bench migrate sin autorización

---

## Decisiones vigentes
- `Facturacion Mexico Settings` (Single) intacto — ningún campo eliminado
- `FacturAPIClient(company=None)` lanza ValidationError — intencional
- E-Receipts: payment_form desde Payment Entry → Company Settings → "28"
- Factura Global: use="S01", payment_method="PUE", objeto "global" con periodicity/months/year

---

## Riesgos / cuidados
- issue #165 (is_submittable CFDI Recibido) sigue pendiente
- Instalaciones existentes necesitan crear Company Settings para funcionar
