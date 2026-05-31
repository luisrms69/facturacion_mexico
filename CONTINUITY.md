# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-31
**Rama activa:** `feat/multi-company-facturapi-settings`
**Tarea actual:** Migración multi-company — sección básica committed, continuar campos 13-21

---

## Recuperación rápida

Estoy trabajando en:
Migración campo por campo de `Facturacion Mexico Settings` (Single) al nuevo DocType
`Facturacion Mexico Company Settings`. Sección básica (campos 1-12) ya committed.

Plan que estoy siguiendo:
`working_docs/active/PLAN_MULTI_COMPANY_FACTURAPI_SETTINGS.md`

Objetivo inmediato:
Revisar campos 13-21 (enable_ereceipts, ereceipts, global invoices) y decidir
si se migran o se marcan para eliminar en PR de limpieza.

Criterio de avance:
Todos los campos de `Facturacion Mexico Settings` clasificados y
`Facturacion Mexico Company Settings` completo con los campos que aplican.

---

## Estado actual

### Ya cerrado
- Campos 1-12 migrados o clasificados como constantes/redundantes
- DocType `Facturacion Mexico Company Settings` creado con campos 1-10
- bench migrate en test-facturacion.localhost y facturacion-v16.dev ✅
- 1054 tests — cero fallas nuestras ✅

### Campos migrados en este commit
| Campo | Destino |
|---|---|
| sandbox_mode | Company Settings |
| api_key | Company Settings |
| test_api_key | Company Settings |
| rfc_emisor | No migrar — redundante con Company.tax_id |
| lugar_expedicion | No migrar — redundante con Branch.fm_lugar_expedicion |
| timeout | Constante `_DEFAULT_TIMEOUT = 30` |
| metodo_pago_default | Company Settings |
| send_email_default | Company Settings |
| download_files_default | Company Settings |
| customer_email_fallback | Company Settings |
| log_retention_days | Constante `90` en tasks.py |

### Pendiente inmediato
1. Revisar campos 13-21 (e-receipts y facturas globales — no implementados)
2. Completar bitácora `BITACORA_ADDENDA_LA_COMER_ACG.md` con el GAP detectado
3. Prueba GUI en facturacion-v16.dev con Company ACG

### No repetir
- No hacer fallback al Single para campos ya migrados
- No correr tests sin `ci_pre_tests.run` primero
- No hacer bench migrate sin autorización

---

## Decisiones vigentes
- `Facturacion Mexico Settings` (Single) intacto — ningún campo eliminado todavía
- `FacturAPIClient(company=None)` lanza ValidationError — es intencional
- Campos e-receipts/factura global: probablemente eliminar en PR de limpieza
- `working_docs/active/PLAN_MULTI_COMPANY_FACTURAPI_SETTINGS.md` es el plan activo

---

## Archivos relevantes ahora
- `facturacion_mexico/facturacion_fiscal/doctype/facturacion_mexico_company_settings/`
- `facturacion_mexico/facturacion_fiscal/api_client.py`
- `working_docs/active/PLAN_MULTI_COMPANY_FACTURAPI_SETTINGS.md`

---

## Riesgos / cuidados
- Instalaciones existentes (LlantasCS) necesitan crear `Facturacion Mexico Company Settings`
  para funcionar — sin ese registro el timbrado lanza error
- issue #165 (is_submittable CFDI Recibido) sigue pendiente — fuera de alcance aquí
