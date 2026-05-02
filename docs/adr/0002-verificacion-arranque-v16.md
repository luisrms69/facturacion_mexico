# MÓDULO 0 — VERIFICACIÓN DE ARRANQUE
=====================================
Fecha: 2026-05-01  
Site: facturacion-v16.dev  
Bench: /home/erpnext/frappe-bench-v16  

---

## Resultados

| # | Check | Estado | Detalle |
|---|-------|--------|---------|
| 1 | Site responde HTTP | ✗ | HTTP 000 — `Could not resolve host: facturacion-v16.dev` (DNS no configurado en este entorno) |
| 2 | App instalada | ✓ | frappe 16.2.1, erpnext 16.1.0, hrms 16.1.0, payments 0.0.1, facturacion_mexico 0.0.1 |
| 3 | Error Log limpio | ✓ | 2 entradas; ninguna crítica (ver detalle abajo) |
| 4 | make_autoname | ✓ | Existe en frappe v16 |
| 5 | get_address_display | ✓ | `frappe.contacts.doctype.address.address.get_address_display` importa OK |
| 6 | Custom fields críticos | ✓ | Los 3 campos existen: `Sales Invoice-fm_fiscal_status`, `Customer-fm_rfc_validated`, `Sales Invoice-fm_branch` |
| 7 | Catálogos SAT | ✓ | Uso CFDI SAT: 25 · Forma Pago SAT: 22 · Regimen Fiscal SAT: 20 |
| 8 | Scheduler | ✗ | **DISABLED** — `Scheduler is disabled for site facturacion-v16.dev` |
| 9 | Jobs registrados | ✓ | 11 jobs de facturacion_mexico registrados (stopped=0 en todos) |

---

## Detalle de Error Log (últimas 2 entradas)

```
2026-05-02 03:16:45 | Configuración de Facturación México actualizada por Administrator
  → "Facturacion Mexico Settings Updated"  [INFORMATIVO — no es un error]

2026-05-02 03:12:19 | frappe.model.delete_doc.delete_dynamic_links
  → MySQLdb.OperationalError: (1412, 'Table definition has changed, please retry transaction')
  → update tabCommunication set reference_doctype=NULL, reference_name=NULL
    where reference_doctype='Property Setter' and reference_name='Sales Order-tax_id-print_hide'
  [TRANSITORIO — ocurrió durante migración/instalación, no se repite]
```

---

## Jobs de facturacion_mexico registrados (11 total)

| Método | Frecuencia | Stopped |
|--------|-----------|---------|
| facturacion_mexico.complementos_pago.api.reconcile_payment_tracking | Weekly | No |
| facturacion_mexico.ereceipts.doctype.ereceipt_mx.ereceipt_mx.bulk_expire_ereceipts | Daily | No |
| facturacion_mexico.validaciones.doctype.sat_validation_cache.sat_validation_cache.cleanup_expired_cache | Daily | No |
| facturacion_mexico.validaciones.api.bulk_validate_customers | Daily | No |
| facturacion_mexico.ereceipts.api.expire_ereceipts | Hourly | No |
| facturacion_mexico.complementos_pago.api.process_pending_complements | Hourly | No |
| facturacion_mexico.facturacion_fiscal.tasks.cleanup_old_logs | Cron | No |
| facturacion_mexico.validaciones.api.run_nightly_rfc_validation | Cron | No |
| facturacion_mexico.facturacion_fiscal.tasks.process_sync_errors | Cron | No |
| facturacion_mexico.facturacion_fiscal.tasks.process_bulk_sync | Cron | No |
| facturacion_mexico.facturacion_fiscal.tasks.process_timeout_recovery | Cron | No |

---

## BLOQUEANTES ENCONTRADOS

### 1. [BLOQUEANTE FUNCIONAL] Scheduler deshabilitado
- **Problema**: `bench scheduler status` reporta "Scheduler is disabled for site facturacion-v16.dev"
- **Impacto**: Ningún job programado se ejecutará (validaciones RFC, expiración de ereceipts, complementos de pago, limpieza de caché)
- **Resolución**: `bench --site facturacion-v16.dev scheduler enable`

### 2. [BLOQUEANTE DE ACCESO WEB] DNS no resuelve facturacion-v16.dev
- **Problema**: `Could not resolve host: facturacion-v16.dev` — el hostname no existe en DNS público/local
- **Impacto**: El site no es accesible vía browser ni API HTTP desde el servidor actual
- **Posibles causas**:
  - Falta entrada en `/etc/hosts` (si es entorno local/dev)
  - Falta configuración DNS externa (si debe ser accesible en red)
  - Nginx no está corriendo o no tiene el virtualhost configurado
- **Resolución**: Verificar nginx (`bench setup nginx && sudo service nginx reload`) y/o agregar entrada en `/etc/hosts`

---

## Items sin bloqueo (informativos)

- **Error Log (1412 Table definition)**: Error transitorio de MariaDB durante migración. No se repite — ignorar.
- **Error Log (Settings Updated)**: Entrada informativa, no es error real.

---

## SIGUIENTE PASO

**Prioridad 1** — Habilitar scheduler:
```bash
bench --site facturacion-v16.dev scheduler enable
bench --site facturacion-v16.dev scheduler status   # verificar
```

**Prioridad 2** — Resolver acceso web:
```bash
bench setup nginx
sudo service nginx status
sudo service nginx reload
# Si es entorno dev, agregar a /etc/hosts:
# 127.0.0.1 facturacion-v16.dev
```

**Una vez resueltos los bloqueantes** → Continuar con **Módulo 1: Verificación de Facturación Fiscal** (timbrado, PAC, flujo de CFDI).
