# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-31
**Rama activa:** `feat/multi-company-facturapi-settings`
**Tarea actual:** Migración multi-company — referencias al Single eliminadas, DocType completo

---

## Recuperación rápida

Estoy trabajando en:
Migración campo por campo de `Facturacion Mexico Settings` (Single) a `Facturacion Mexico Company Settings`.
Todos los grupos A-D procesados. Cero llamadas activas al Single fuera del propio DocType.

Plan que estoy siguiendo:
`working_docs/active/PLAN_MULTI_COMPANY_FACTURAPI_SETTINGS.md`

Objetivo inmediato:
Correr tests completos, preparar PR.

Criterio de avance:
Tests pasan + PR abierto.

---

## Estado actual

### Ya committed en esta rama
- cb5cf42: DocType base + sección básica (campos 1-12)
- fb41aa2: E-Receipts + Factura Global migrados
- este commit: eliminación de referencias al Single (Grupos A-D)

### Campos en Company Settings
**Sección API:** sandbox_mode, api_key, test_api_key
**Sección Operativa:** metodo_pago_default, send_email_default, download_files_default, customer_email_fallback
**Sección E-Receipts:** ereceipt_mode_default, ereceipt_expiry_type_default, ereceipt_expiry_days_default, ereceipt_payment_form_default, ereceipt_notification_email, ereceipt_self_invoice_message
**Sección Factura Global:** global_customer, global_item, global_payment_form_default, notify_global_generation, global_notification_emails

### Pendiente
1. Tests completos via /test-guard antes de PR
2. bench migrate en test-facturacion.localhost
3. PR

### No repetir
- No hacer fallback al Single para campos migrados
- No commitear en main

---

## Decisiones vigentes
- `Facturacion Mexico Settings` (Single) intacto — ningún campo eliminado del JSON
- Cero llamadas activas al Single fuera del propio DocType y archivos de instalación
- E-Receipts: siempre activos (enable_ereceipts eliminado)
- Factura Global: siempre disponible (enable_global_invoices eliminado)
- Cancelación fiscal: siempre manual (auto_cancel_fiscal eliminado)

---

## Riesgos / cuidados
- Instalaciones existentes necesitan crear Company Settings para que funcione el timbrado
- issue #165 (is_submittable CFDI Recibido) sigue pendiente
