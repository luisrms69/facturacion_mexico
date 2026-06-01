# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-31
**Rama activa:** `feat/multi-company-facturapi-settings`
**Tarea actual:** Migración multi-company — lista para PR

---

## Recuperación rápida

Estoy trabajando en:
Migración completa de `Facturacion Mexico Settings` (Single) a `Facturacion Mexico Company Settings` (por Company). Todos los campos y referencias resueltos. Lista para correr tests completos y abrir PR.

Plan que estoy siguiendo:
`working_docs/active/PLAN_MULTI_COMPANY_FACTURAPI_SETTINGS.md`

Objetivo inmediato:
Correr tests completos → bench migrate en test site → PR

Criterio de avance:
Tests pasan sin fallas nuevas + PR abierto.

---

## Estado actual

### Commits en esta rama
- cb5cf42: DocType base + sección básica (campos 1-12)
- fb41aa2: E-Receipts + Factura Global migrados
- 4b7d01f: eliminación referencias al Single (Grupos A-D)
- este commit: ajustes cosméticos + workspace + install.py

### DocType Facturacion Mexico Company Settings — completo
**General del Sistema:** sandbox_mode, api_key, test_api_key, ereceipt_mode_default
**Facturas:** metodo_pago_default, send_email_default, download_files_default, customer_email_fallback
**E-Receipts:** ereceipt_expiry_type_default/days/payment_form, ereceipt_notification_email, ereceipt_self_invoice_message
**Factura Global:** global_customer, global_item, global_payment_form_default, notify_global_generation, global_notification_emails

### Issues creados
- #171: indicador visual sandbox por usuario (Opción D — futura implementación)

### Pendiente
1. Tests completos via /test-guard
2. bench migrate en test-facturacion.localhost
3. PR

### No repetir
- No hacer fallback al Single para campos migrados
- No commitear en main

---

## Decisiones vigentes
- `Facturacion Mexico Settings` (Single) intacto — ningún campo eliminado del JSON
- Cero llamadas activas al Single fuera del propio DocType y archivos de instalación
- Cancelación fiscal siempre manual (auto_cancel_fiscal eliminado)
- issue #171 creado para sandbox indicator — no implementar en esta rama

---

## Riesgos / cuidados
- Instalaciones existentes necesitan crear Company Settings para que funcione el timbrado
- issue #165 (is_submittable CFDI Recibido) sigue pendiente
