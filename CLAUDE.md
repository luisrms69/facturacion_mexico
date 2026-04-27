# CLAUDE.md — facturacion_mexico

## Estado de migración
- **Migrada a v16:** No
- **Versión origen:** v15 (Frappe 15.97, ERPNext 15.95)
- **En producción:** No — en desarrollo activo
- **Branch activo:** feature/e4-ieps-on-item-quantity
- **Sitio de desarrollo:** facturacion.dev
- **Versión:** 0.0.1

## Entorno
Ver contexto global en `frappe-infrastructure/.claude/CLAUDE.md`.

**Bench:** /home/erpnext/frappe-bench  
**Comandos siempre con --site:**
```bash
bench --site facturacion.dev migrate
bench --site facturacion.dev export-fixtures --app facturacion_mexico
bench --site facturacion.dev run-tests --app facturacion_mexico
bench build --app facturacion_mexico
```
**NUNCA:** `bench migrate` sin --site (afecta otros sitios del bench compartido)

---

## Qué hace esta app

App de facturación electrónica CFDI para México, integrada con FacturAPI.io como PAC. Extiende ERPNext para emitir, cancelar y gestionar CFDIs (tipos I, E, N, P) desde Sales Invoice, con soporte multi-sucursal, addendas, e-receipts y complementos de pago.

---

## Doctypes principales

| DocType | Qué es |
|---|---|
| `Factura Fiscal Mexico` | DocType central — CFDI tipo I/E/N via FacturAPI. Submittable. |
| `Complemento Pago MX` | CFDI tipo P (PPD). Se genera automáticamente desde Payment Entry. |
| `EReceipt MX` | Recibo digital para autofacturación por el cliente. |
| `Factura Global MX` | Agrupa E-Receipts en CFDI global. |
| `Facturacion Mexico Settings` | Single — credenciales FacturAPI (sandbox/live), config global. |
| `Configuracion Fiscal Mexico` | Single — configuración fiscal de la empresa. |
| `Configuracion Fiscal Sucursal` | Config fiscal por Branch con folios, serie y certificados independientes. |
| `FacturAPI Response Log` | Trazabilidad de respuestas del PAC. |

Catálogos SAT propios: `Uso CFDI SAT`, `Forma Pago SAT`, `Metodo Pago SAT`, `Regimen Fiscal SAT`, `Moneda SAT`, `Impuesto SAT`, `SAT Producto Servicio`, `IEPS Cuota SAT`.

---

## Lógica crítica

### Flujo principal
```
Sales Invoice (submit) → doc_events hooks → Factura Fiscal Mexico → api_client.py → FacturAPI.io → SAT
```

### Custom Fields sobre DocTypes de ERPNext
- **Sales Invoice:** ~40 campos (estado fiscal, timbrado, multi-sucursal, addenda, draft, e-receipt)
- **Branch:** 14 campos (multi-sucursal fiscal: folios, series, certificados)
- **Customer:** 12 campos (RFC, régimen fiscal, uso CFDI, addenda)
- **Payment Entry:** 5 campos (forma de pago SAT, complemento PPD)
- **Item:** 3 campos (clave producto/servicio SAT)

### Hooks activos
- `Customer.validate` → validación RFC
- `Sales Invoice.validate` → cálculo automático de impuestos
- `Payment Entry.on_submit` → crea complemento PPD automáticamente
- `Branch.validate/on_update` → campos fiscales multi-sucursal

### API externa
- **FacturAPI.io** — PAC para timbrado CFDI
- Soporta sandbox y producción (configurable en Facturacion Mexico Settings)
- Cliente HTTP en `facturacion_fiscal/api_client.py`

---

## Funcionalidades y su estado

| Funcionalidad | Estado |
|---|---|
| Timbrado CFDI (I/E/N) | ✅ Funcional |
| Complemento de Pago PPD | ✅ Funcional |
| E-Receipts / autofactura | ✅ Funcional |
| Factura Global | ✅ Funcional |
| Cancelación CFDI | ✅ Funcional |
| Multi-sucursal (Branch) | ✅ Funcional |
| Addendas genéricas | ✅ Funcional |
| Validación RFC contra SAT | ✅ Funcional |
| Recovery / resiliencia PAC | ⚠️ Funcional pero defecto crítico (datos en /tmp) |
| Draft management | ❌ No funcional — todo MOCK |
| Motor de reglas | ⚠️ Parcial — acciones clave deshabilitadas |
| Dashboard KPIs | ⚠️ Parcial — alertas siempre en 0 |

---

## Problemas críticos conocidos (no tocar sin plan)

1. **`draft_management/api.py`** — completamente simulado con MOCKs. Los flujos con `fm_create_as_draft = True` no generan CFDI real. Falla silenciosamente.

2. **`facturacion_fiscal/api_backup.py`** — el fallback de recovery escribe respuestas PAC en `/tmp/`. Se pierden en reinicio. Viola cumplimiento fiscal (las respuestas PAC son documentos con valor legal).

3. **Motor de reglas** — `execute_call_api_manual()`, `execute_script_manual()`, `execute_create_document_manual()` retornan strings de error, no ejecutan nada.

4. **29 scripts sueltos** en raíz del módulo (`facturacion_mexico/facturacion_mexico/`) que deberían estar en `one_offs/` o `scripts/`.

5. **Directorios duplicados:** `validation/` vs `validaciones/`, `dashboard/` vs `dashboard_fiscal/`, `custom/` vs `custom_fields/`.

---

## Dependencias

**Apps de Frappe requeridas:** erpnext (declared in `required_apps`)  
**Apps en el mismo bench:** llantascs_customs, condominium_management, facturacion_mx (predecesora), dfp_external_storage, hrms, payments, wiki  
**API externa:** FacturAPI.io (credenciales en Facturacion Mexico Settings)

---

## Fixtures

Correctamente declarados en `hooks.py`:
- Custom Fields (filtro por módulo `Facturacion Mexico`)
- Mode of Payment (formas de pago SAT)
- UOM (unidades SAT)
- 3 Roles: Facturacion Mexico User/Manager/System Manager
- DocPerms para Factura Fiscal Mexico y Sales Invoice

Catálogos SAT (`sat_uso_cfdi.json`, `sat_forma_pago.json`, `sat_regimen_fiscal.json`) — exportados pero comentados en hooks.py. Se poblan via `after_install`.

---

## Patches registrados

```
facturacion_mexico.patches.migrate_custom_field_prefixes
facturacion_mexico.patches.create_missing_item_custom_fields
facturacion_mexico.patches.migrate_sat_catalogs_to_fixtures
facturacion_mexico.patches.v1.register_facturacion_fiscal_module
facturacion_mexico.patches.v1.restore_facturapi_response_item
facturacion_mexico.patches.v2_0.migrate_fiscal_status_to_architecture
facturacion_mexico.patches.v2_0.rename_uuid_field_to_fm_uuid
facturacion_mexico.patches.v1_0.migrate_customer_tax_category_to_fm_tax_regime
```

---

## Tests

```bash
bench --site facturacion.dev run-tests --app facturacion_mexico
pytest apps/facturacion_mexico/ -v --tb=short
```

Tests reales en `tests/`. Scripts de testing ad-hoc en `one_offs/` — no son tests del framework.

---

## Antes de cada PR

- [ ] Tests pasan
- [ ] Fixtures exportados si hubo cambios de Custom Fields, Workflows, Roles, DocPerms
- [ ] Patch creado si hay cambios de esquema con datos
- [ ] Sin secrets (credenciales FacturAPI nunca en código)
- [ ] `bench --site facturacion.dev migrate` limpio en desarrollo
- [ ] Ver checklist global en `frappe-infrastructure/CONTRIBUTING.md`

---

## Auditoría pre-migración

Ver `docs/adr/0000-estado-real-pre-migracion.md` para el estado completo documentado el 2026-04-25.
