# MÓDULO 1 — CONFIGURACIÓN FISCAL Y DATOS MAESTROS
====================================================
Fecha: 2026-05-01  
Site: facturacion-v16.dev  
Bench: /home/erpnext/frappe-bench-v16  

---

## Resultados

| # | Check | Estado | Detalle |
|---|-------|--------|---------|
| 1 | Settings configurado | ✗ | `sandbox_mode = 1` (modo pruebas activo), pero faltan campos críticos |
| 2 | API Key producción | ✗ | `api_key = NULL` — no configurada |
| 3 | API Key pruebas | ✗ | `test_api_key = NULL` — no configurada |
| 4 | RFC emisor | ✗ | `rfc_emisor = NULL` — no configurado |
| 5 | Lugar de expedición | ✗ | `lugar_expedicion = NULL` — no configurado |
| 6 | Custom fields Sales Invoice | ✓ | 37 campos registrados; 25 campos de datos tienen columna en DB |
| 7 | Custom fields Customer | ✓ | 10 campos registrados; 7 campos de datos tienen columna en DB |
| 8 | Customers con RFC | ✗ | 0 customers — base de datos sin datos maestros |
| 9 | Company con RFC | ✗ | 0 companies — sin Company creada |
| 10 | Items con código SAT | ✗ | 0 de 0 — sin items |

---

## Detalle: Facturacion Mexico Settings

| Campo | Valor |
|-------|-------|
| `sandbox_mode` | **1** (pruebas activo) |
| `api_key` | NULL |
| `test_api_key` | NULL |
| `rfc_emisor` | NULL |
| `lugar_expedicion` | NULL |
| `regimen_fiscal_default` | NULL |
| `dashboard_default_company` | NULL |
| `timeout` | 30 |
| `metodo_pago_default` | PUE |
| `ereceipt_mode_default` | Normal |
| `ereceipt_expiry_type_default` | End of Month |
| `ereceipt_expiry_days_default` | 3 |
| `customer_email_fallback` | cliente@miempresa.com |
| `download_files_default` | 1 |
| `send_email_default` | 0 |

---

## Detalle: Custom Fields Sales Invoice (37 total)

- **25 campos de datos** — todos tienen columna en `tabSales Invoice` ✓  
- **12 campos de layout** (Section Break / Column Break / HTML) — no requieren columna ✓

Campos de datos confirmados en DB:
`fm_fiscal_status`, `fm_factura_fiscal_mx`, `fm_last_status_update`, `fm_branch`,
`fm_ereceipt_mode`, `fm_addenda_required`, `fm_complementos_count`, `fm_ereceipt_expiry_type`,
`fm_addenda_status`, `fm_branch_health_status`, `fm_ereceipt_expiry_date`, `fm_addenda_xml`,
`fm_addenda_generated_date`, `fm_create_as_draft`, `fm_draft_created_date`, `fm_draft_approved_by`,
`fm_factorapi_draft_id`, `fm_draft_status`, `fm_addenda_errors`, `fm_auto_selected_branch`,
`fm_ereceipt_expiry_days`, `fm_certificate_info`, `fm_addenda_type`, `fm_folio_reserved`,
`fm_pending_amount`

---

## Detalle: Custom Fields Customer (10 total)

- **7 campos de datos** — todos tienen columna en `tabCustomer` ✓  
- **3 campos de layout** — no requieren columna ✓

Campos de datos confirmados: `fm_rfc_validated`, `fm_rfc_validation_date`, `fm_lista_69b_status`,
`fm_uso_cfdi_default`, `fm_requires_addenda`, `fm_default_addenda_type`, `fm_envio_email_cliente`

**Nota:** `fm_regimen_fiscal` no existe en Customer en v16 (el check del script asumía un campo
que fue eliminado/renombrado respecto a versiones anteriores). No es un bloqueante; el campo
de régimen fiscal en Customer no existe en el schema actual de la app.

---

## Estado de la base de datos

La base de datos es una **instalación limpia sin datos migrados**:

| Tabla | Registros |
|-------|-----------|
| `tabCompany` | 0 |
| `tabCustomer` | 0 |
| `tabItem` | 0 |
| `tabSales Invoice` | 0 |
| `tabUser` | 2 (Administrator + Guest) |
| `tabDocType` | 964 |
| `tabCustom Field` | 130 |
| `tabScheduled Job Type` | 105 |
| `tabSingles` | 1,290 |

No se han migrado datos maestros ni transaccionales desde el bench anterior.

---

## BLOQUEANTES PARA TIMBRADO

### 1. [CRÍTICO] Sin Company
No existe ninguna Company en el sistema. La Company es el emisor del CFDI — sin ella
ningún documento puede ser timbrado.

### 2. [CRÍTICO] RFC Emisor no configurado
`Facturacion Mexico Settings.rfc_emisor = NULL`. Campo obligatorio en todo CFDI 4.0.

### 3. [CRÍTICO] Lugar de Expedición no configurado
`lugar_expedicion = NULL`. Campo obligatorio en el XML del CFDI.

### 4. [CRÍTICO] Sin API Key (ni producción ni pruebas)
`api_key = NULL` y `test_api_key = NULL`. Sin credenciales del PAC no hay comunicación
posible para timbrar — ni en sandbox.

### 5. [CRÍTICO] Sin datos maestros
0 customers, 0 items. No hay receptor ni conceptos para generar facturas de prueba.
Pendiente migración o carga de datos desde bench anterior.

### 6. [FUNCIONAL] Scheduler deshabilitado
(Detectado en Módulo 0) — jobs de validación RFC, complementos y expiración de
ereceipts no se ejecutarán hasta habilitarlo.

---

## Items sin bloqueo (informativos)

- Custom fields de Sales Invoice y Customer instalados correctamente con columnas en DB ✓
- `sandbox_mode = 1` activo — correcto para entorno de pruebas
- `metodo_pago_default = PUE` configurado
- Catálogos SAT poblados (del Módulo 0): Uso CFDI 25, Forma Pago 22, Régimen Fiscal 20 ✓

---

## SIGUIENTE PASO

**Antes de cualquier prueba de timbrado, resolver en orden:**

1. Crear Company con RFC y datos fiscales completos
2. Configurar `Facturacion Mexico Settings`: `rfc_emisor`, `lugar_expedicion`, `test_api_key`
3. Habilitar scheduler: `bench --site facturacion-v16.dev scheduler enable`
4. Migrar o crear datos maestros mínimos: al menos 1 Customer con RFC, ítems con código SAT
5. Validar con una Sales Invoice de prueba en modo sandbox

Una vez resueltos → continuar con **Módulo 2: Flujo de Timbrado CFDI** (generación, envío al PAC, cancelación).
