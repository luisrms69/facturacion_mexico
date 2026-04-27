# ADR 0000: Estado Real de la App — Pre-Migración

- **Fecha:** 2026-04-25
- **Estado:** Registro histórico
- **App auditada:** `facturacion_mexico` (publicador: Buzola)
- **Contexto:** Auditoría completa del código antes de cualquier refactor o migración de arquitectura

---

## 1. Doctypes Custom en el Código

La app define aproximadamente **48 doctypes** distribuidos en 10 submódulos funcionales.

### Submittables (flujo fiscal principal)
| Doctype | Submódulo | Propósito |
|---|---|---|
| `Factura Fiscal Mexico` | facturacion_fiscal | CFDI tipo I/E/N via FacturAPI. DocType central. Tiene clase override. |
| `Complemento Pago MX` | complementos_pago | CFDI tipo P (PPD). Se puede generar automáticamente desde Payment Entry. |
| `EReceipt MX` | ereceipts | Recibo digital para autofacturación por el cliente. |
| `Factura Global MX` | facturas_globales | Agrupa E-Receipts en CFDI global. Bien implementado. |

### Child Tables
| Doctype | Usado en |
|---|---|
| `FacturAPI Response Item` | `Factura Fiscal Mexico` |
| `Documento Relacionado Pago MX` | `Complemento Pago MX` |
| `Detalle Complemento Pago MX` | `Complemento Pago MX` |
| `Factura Global Detail` | `Factura Global MX` |
| `Addenda Field Definition` | `Addenda Template` |
| `Addenda Field Value` | `Addenda Configuration` |
| `Addenda Product Mapping` | `Addenda Configuration` |
| `Rule Action` | `Fiscal Validation Rule` |
| `Rule Condition` | `Fiscal Validation Rule` |
| `Fiscal Alert Notify Role` | `Fiscal Alert Rule` |
| `Fiscal Alert Notify User` | `Fiscal Alert Rule` |
| `Dashboard Widget Allowed Role` | `Dashboard Widget Config` |

### Catálogos SAT (maestros de solo lectura)
`Uso CFDI SAT`, `Forma Pago SAT`, `Metodo Pago SAT`, `Regimen Fiscal SAT`, `Moneda SAT`, `Impuesto SAT`, `SAT Producto Servicio`

### Singles (configuración)
| Doctype | Propósito |
|---|---|
| `Facturacion Mexico Settings` | Credenciales FacturAPI (sandbox/live), configuración global |
| `Configuracion Fiscal Mexico` | Configuración fiscal de la empresa |
| `Control Panel Settings` | Panel de control general |
| `Fiscal Dashboard Config` | Configuración del dashboard fiscal |

### Doctypes de operación y trazabilidad
`FacturAPI Response Log`, `Fiscal Attempt Log`, `Fiscal Recovery Task`, `Recovery Operations`, `System Health Monitor`, `IEPS Cuota SAT`, `Mapeo Cuenta Fiscal Mexico`, `Rule Execution Log`, `SAT Validation Cache`, `Payment Tracking MX`, `Dashboard User Preference`, `Dashboard Widget Config`, `Fiscal Alert Rule`, `Fiscal Health Score`, `Fiscal Health Factor`, `Fiscal Health Recommendation`

### Multi-sucursal
`Configuracion Fiscal Sucursal` — configuración fiscal por sucursal (Branch) con folios, serie, certificados independientes.

### Addendas
`Addenda Configuration`, `Addenda Template`, `Addenda Type` — sistema genérico configurable de addendas por cliente/tipo.

---

## 2. Fixtures: Exportados vs Realidad

### Configurado en `hooks.py`
A diferencia de `facturacion_mx`, esta app **sí tiene fixtures correctamente declarados**:

```python
fixtures = [
    {"dt": "Custom Field", "filters": [["module", "=", "Facturacion Mexico"]]},
    {"dt": "Mode of Payment", "filters": [["name", "like", "%-%"]]},
    {"dt": "UOM", "filters": [["uom_name", "like", "% - %"]]},
    {"dt": "Role", "filters": [...]},   # 3 roles
    {"dt": "DocPerm", "filters": [...]} # permisos para Factura Fiscal Mexico y Sales Invoice
]
```

### Custom Fields exportados (~75 campos en 5 doctypes estándar de ERPNext)

**Branch** (14 campos — multi-sucursal fiscal):
`fm_enable_fiscal`, `fm_lugar_expedicion`, `fm_serie_pattern`, `fm_folio_start/current/end`, `fm_folio_warning_threshold`, `fm_certificate_ids`, `fm_share_certificates`, `fm_last_invoice_date`, `fm_monthly_average`, `fm_enable_fiscal_test`

**Customer** (12 campos):
`fm_regimen_fiscal`, `fm_uso_cfdi_default`, `fm_rfc_validated`, `fm_rfc_validation_date`, `fm_lista_69b_status`, `fm_requires_addenda`, `fm_default_addenda_type`, `fm_envio_email_cliente` + secciones/column breaks

**Item** (3 campos):
`fm_producto_servicio_sat` (Link a `SAT Producto Servicio`), secciones

**Payment Entry** (5 campos):
`fm_forma_pago_sat`, `fm_require_complement`, `fm_complemento_pago`, `fm_complement_generated`, sección fiscal

**Sales Invoice** (40 campos — el más impactado):
- Sección Multi-Sucursal: `fm_branch`, `fm_auto_selected_branch`
- Sección Fiscal: `fm_fiscal_status`, `fm_factura_fiscal_mx`, `fm_folio_reserved`, `fm_quick_status`, `fm_last_status_update`, `fm_pending_amount`, `fm_certificate_info`, `fm_branch_health_status`
- Sección Timbrado: `fm_complementos_count`
- Sección Addenda: `fm_addenda_type/status/required/xml/errors/generated_date`
- Sección Draft: `fm_create_as_draft`, `fm_draft_status/created_date/approved_by`
- Sección EReceipt: `fm_ereceipt_mode/expiry_type/expiry_days/expiry_date`, `fm_factorapi_draft_id`
- Otros: `ffm_substitution_source_uuid`

### Fixture files en disco (`facturacion_mexico/fixtures/`)
| Archivo | Registros | ¿En hooks.py? |
|---|---|---|
| `sat_uso_cfdi.json` | 26 | Pendiente verificar |
| `sat_forma_pago.json` | 22 | Pendiente verificar |
| `sat_regimen_fiscal.json` | 20 | Pendiente verificar |

Los catálogos SAT doctypes (`Uso CFDI SAT`, `Forma Pago SAT`, `Regimen Fiscal SAT`) son propios de esta app (no reutilizan los de ERPNext), por lo que su población puede hacerse via `after_install`.

---

## 3. Lógica de Negocio Implementada

### Flujo principal: Timbrado de factura
La app se integra con **FacturAPI.io** como PAC. La ruta crítica es:
```
Sales Invoice (submit) → doc_events hooks → Factura Fiscal Mexico → api_client.py → FacturAPI → SAT
```

### Hooks activos (doc_events)
| DocType | Evento | Handler | Estado |
|---|---|---|---|
| `Customer` | validate / before_save | `validate_rfc_format` | Funcional |
| `Customer` | after_insert | `schedule_rfc_validation` | Funcional |
| `Sales Invoice` | before_validate / validate | `sales_invoice_automated_tax` | Funcional |
| `Branch` | validate / after_insert / on_update | `branch_fiscal_fields` | Funcional |
| `Payment Entry` | validate | `check_ppd_requirement` | Funcional |
| `Payment Entry` | on_submit | `create_complement_if_required` | Funcional (auto-crea complemento PPD) |
| `Payment Entry` | on_cancel | `cancel_related_complement` | Funcional |
| `Complemento Pago MX` | validate / before_save / after_insert / on_submit | handlers varios | Funcional |
| `EReceipt MX` | before_save / after_insert | handlers varios | Funcional |

### Scheduler events activos
| Frecuencia | Task | Estado |
|---|---|---|
| Cada 5 min | `process_timeout_recovery` | Funcional |
| Cada 5 min | `process_bulk_sync` | Funcional |
| Cada 10 min | `process_sync_errors` | Funcional |
| Cada hora | `process_pending_complements` | Funcional |
| Cada hora | `expire_ereceipts` | Funcional |
| 2:00 AM diario | `run_nightly_rfc_validation`, `cleanup_old_logs` | Funcional |
| Diario | `bulk_validate_customers`, `cleanup_expired_cache`, `bulk_expire_ereceipts` | Funcional |
| Semanal | `reconcile_payment_tracking` | Funcional |

### Funcionalidades implementadas y funcionales
- **Timbrado CFDI** (tipos I, E, N) via FacturAPI — funcional
- **Complementos de pago PPD** — funcional, con generación automática en submit de Payment Entry
- **E-Receipts** con fechas de vencimiento configurables — funcional
- **Facturas globales** agrupando E-Receipts — funcional y bien estructurado
- **Cancelación** de CFDIs — funcional
- **Sistema multi-sucursal** con folios y series independientes por Branch — funcional
- **Addendas** genéricas (sistema configurable por tipo) — funcional, con validación XSD
- **Validación RFC** contra SAT con caché — funcional
- **Dashboard fiscal** con KPIs, reportes y sistema de alertas — parcialmente funcional
- **Motor de reglas** configurable para validaciones fiscales — parcialmente implementado
- **Sistema de recovery** para respuestas PAC fallidas — funcional pero con defecto crítico (ver sección 5)
- **Draft management** — MOCK, no funcional en producción

### after_install / after_migrate
```
after_install: "facturacion_mexico.install.after_install"
after_migrate: [
    "facturacion_mexico.setup.customize_sales_invoice.apply_customization",
    "facturacion_mexico.setup.item_groups.assign_itt_to_groups"
]
```

---

## 4. Dependencias

### Apps requeridas (declaradas correctamente)
```python
required_apps = ["erpnext"]
```

### Python (declaradas en `pyproject.toml`)
```
requests >= 2.31.0       # HTTP client para FacturAPI.io
cryptography >= 41.0.0   # Validaciones fiscales
python-dateutil >= 2.8.0 # Manejo de fechas SAT
```

### Apps en el bench de producción (co-instaladas)
```
frappe, erpnext, hrms, payments,
dfp_external_storage,   ← almacenamiento externo de archivos
facturacion_mx,         ← app PREDECESORA (distinta de esta)
llantascs_customs,      ← customizaciones del cliente
condominium_management, buzola-internal, wiki
```
La convivencia de `facturacion_mx` (app predecesora) y `facturacion_mexico` en el mismo bench indica que hay una **migración en curso o paralela** entre las dos apps.

### API externa
- **FacturAPI.io** — PAC para timbrado CFDI
- Soporta modo sandbox y producción (configurable en Settings)
- Cliente HTTP en `facturacion_fiscal/api_client.py` con timeout configurable y manejo de errores

---

## 5. Lo que Está Roto o Incompleto

### CRITICO: `draft_management/api.py` — integración completamente simulada
Todo el módulo de borradores usa MOCKS que devuelven datos falsos. Las funciones clave:

```python
def send_to_factorapi():      # Devuelve UUID falso, no llama a FacturAPI
def convert_draft_to_invoice(): # Devuelve XML dummy "<cfdi:Comprobante>...</cfdi:Comprobante>"
def cancel_draft_in_factorapi(): # Mock vacío
def get_draft_preview_from_factorapi(): # Mock vacío
def build_cfdi_payload():     # "Implementación simplificada - en realidad usaría el sistema existente"
```
**Impacto:** Cualquier flujo que use borradores (`fm_create_as_draft = True` en Sales Invoice) no genera un CFDI real. Falla silenciosamente — el hook que lo llama suprime el error con `frappe.log_error`.

### CRITICO: `facturacion_fiscal/api_backup.py` — fallback fiscal en `/tmp`
El sistema de recovery escribe respuestas PAC en `/tmp/facturacion_mexico_pac_fallback/`. En caso de emergencia usa `/tmp/pac_emergency_{name}_{timestamp}`.

```python
FALLBACK_DIR = "/tmp/facturacion_mexico_pac_fallback"
emergency_file = f"/tmp/pac_emergency_{sales_invoice_name}_{now()}..."
```
**Impacto:** Los datos fiscales en `/tmp` se pierden en cualquier reinicio del servidor. Viola cumplimiento fiscal (las respuestas del PAC son documentos fiscales con valor legal). El código tiene `frappe.db.commit()` con comentario `# nosemgrep` — supresión del linter de seguridad sin explicación.

### CRITICO: Motor de reglas — acciones críticas no implementadas
`motor_reglas/engine/rule_executor.py`:
```python
def execute_call_api_manual():    # retorna: "API calls not yet implemented for security reasons"
def execute_script_manual():      # retorna: "Script execution not yet implemented for security reasons"
def execute_create_document_manual(): # retorna: "Document creation not yet implemented"
```
**Impacto:** Las reglas configuradas que usen estas acciones no ejecutan nada.

### ALTO: KPI Engine — `calculate_active_alerts()` siempre retorna 0
`dashboard_fiscal/kpi_engine.py:322`:
```python
# Esto se implementará cuando tengamos el alert engine
# Por ahora, simular con datos básicos
count = 0
```
El contador de alertas activas en el dashboard siempre muestra 0 independientemente del estado real.

### ALTO: 29 archivos de migración/debug sueltos en la raíz del módulo
Directamente en `facturacion_mexico/facturacion_mexico/` existen scripts que deberían estar en `scripts/` o `one_offs/`:

```
backup_custom_fields.py, cleanup_uom_fields.py, diagnose_migration.py,
disable_generic_uoms.py, disable_generic_uoms_simple.py,
extract_sat_code_from_uom.py, fix_item_sat_field_position.py,
fix_item_sat_field_position_final.py, fix_sat_producto_servicio_names.py,
migrate_single_record.py, move_sat_field_after_uom.py,
populate_uom_sat.py, populate_uom_sat_simple.py,
validate_item_sat_field_migration.py, verify_double_timbrado_risk.py,
verify_uom_migration.py, debug_utils.py, utils_testing.py,
analyze_fm_unidad_sat_usage.py, check_item_ui_field.py,
check_producto_servicio_field.py, check_sat_section_visibility.py,
create_additional_test_invoices.py, test_*.py (varios),
...
```
`debug_utils.py` tiene IDs de documentos hardcodeados (`"FFMX-2025-00060"`).

### MEDIO: Directorios duplicados — fuente de verdad ambigua
| Par duplicado | Problema |
|---|---|
| `validation/` vs `validaciones/` | Ambos existen. `validaciones/` tiene hooks activos; `validation/` tiene solo `__init__.py` |
| `dashboard/` vs `dashboard_fiscal/` | `dashboard_fiscal/` es el activo (8 subdirectorios, KPI engine, etc.). `dashboard/` tiene solo un subdirectorio vacío |
| `custom/` vs `custom_fields/` | `custom_fields/` tiene `sales_invoice_addenda_fields.py` (11KB). `custom/fields/` también existe. La fuente de verdad ya son los fixtures |

### MEDIO: Hook en Sales Invoice suprime errores del draft silenciosamente
```python
def on_sales_invoice_submit(doc, method):
    try:
        if doc.get("fm_create_as_draft") and not doc.get("fm_draft_status"):
            result = create_draft_invoice(doc.name)
            if not result.get("success"):
                frappe.log_error(...)  # No re-raise — falla en silencio
    except Exception as e:
        frappe.log_error(...)  # Ídem
```

### BAJO: `api_backup.py` suprime advertencia del linter con `# nosemgrep`
```python
frappe.db.commit()  # nosemgrep
```
El `nosemgrep` indica que el linter marcaba este `commit()` manual como issue de seguridad/consistencia. No hay explicación de por qué se suprimió.

---

## 6. Archivos Sueltos en la Raíz del Módulo

### En `facturacion_mexico/facturacion_mexico/` (deberían estar en `one_offs/` o `scripts/`)
Aproximadamente **29 archivos .py** que son scripts de migración, diagnóstico y testing ad-hoc, incluyendo duplicados (e.g., `disable_generic_uoms.py` y `disable_generic_uoms_simple.py`, `fix_item_sat_field_position.py` y `fix_item_sat_field_position_final.py`).

### En `facturacion_mexico/scripts/` (ubicación correcta, pero contenido heterogéneo)
13 scripts: `generate_docs.py`, `backup_custom_fields.py` (duplicado del de raíz), `migrate_data.py`, `rollback_fiscal_logging_elimination.py`, `run_migration.py`, `populate_mode_of_payment_sat.py`, `drop_fm_certificate_ids.py`, `audit_field.py`, `migrate_fiscal_fields.py`, `restore_custom_field_modules_from_history.py`, `update_field_references.py`, `validate_docs.py`, `test_api_functions.py`.

### En la raíz del repo (`facturacion_mexico/`)
- `setup_new_repo.sh` — script de setup inicial del repo
- `migracion buzola.md` — nota de migración (con espacio en el nombre, no es archivo del repo Python)

---

## 7. Patches Registrados

```
[post_model_sync]
facturacion_mexico.patches.migrate_custom_field_prefixes
facturacion_mexico.patches.create_missing_item_custom_fields
facturacion_mexico.patches.migrate_sat_catalogs_to_fixtures
facturacion_mexico.patches.v1.register_facturacion_fiscal_module
facturacion_mexico.patches.v1.restore_facturapi_response_item
facturacion_mexico.patches.v2_0.migrate_fiscal_status_to_architecture
facturacion_mexico.patches.v2_0.rename_uuid_field_to_fm_uuid
facturacion_mexico.patches.v1_0.migrate_customer_tax_category_to_fm_tax_regime
```
El historial de patches refleja una migración activa: renombrado de campos, migración de catálogos a fixtures, y migración de arquitectura de estados fiscales (v2_0).

---

## 8. Resumen Ejecutivo

| Funcionalidad | Estado |
|---|---|
| Timbrado CFDI (I/E/N) | **Funcional** |
| Complemento de Pago PPD (automático) | **Funcional** |
| E-Receipts / autofactura | **Funcional** |
| Factura Global | **Funcional** |
| Cancelación CFDI | **Funcional** |
| Multi-sucursal (Branch) | **Funcional** |
| Addendas genéricas | **Funcional** |
| Validación RFC contra SAT | **Funcional** |
| Recovery / resiliencia PAC | **Funcional pero con defecto crítico** (datos en `/tmp`) |
| Draft management | **No funcional** (todo MOCK) |
| Motor de reglas | **Parcialmente implementado** (acciones clave deshabilitadas) |
| Dashboard KPIs | **Parcialmente funcional** (alertas siempre en 0) |
| Fixtures / instalación limpia | **Funcional** (correctamente declarados en hooks.py) |
| Dependencias declaradas | **Completas** (`required_apps = ["erpnext"]`) |
| Tests automatizados | **Parciales** (hay tests reales pero también muchos sueltos fuera de `/tests/`) |
| Orden del código fuente | **Deficiente** (29 scripts sueltos en raíz del módulo) |
