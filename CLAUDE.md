# CLAUDE.md — facturacion_mexico

> **Reglas de operación Claude Code** (commits, PRs, base de datos, flujo de trabajo, prohibiciones git):
> Ver `/home/erpnext/Developer/frappe-infrastructure/.claude/CLAUDE.md`

---

## Estado del proyecto

- **Migración:** v15 → v16 completada (2026-05-01)
- **Bench:** `/home/erpnext/frappe-bench-v16`
- **Site activo:** `facturacion-v16.dev`
- **Branch activo:** `feature/e4-ieps-on-item-quantity`
- **Versión:** 0.0.1 (desarrollo activo)
- **En producción:** No

---

## Comandos — bench v16 multi-site

Este bench comparte sitios. **Siempre usar `--site facturacion-v16.dev`.**

```bash
bench --site facturacion-v16.dev migrate
bench --site facturacion-v16.dev run-tests --app facturacion_mexico
bench --site facturacion-v16.dev export-fixtures --app facturacion_mexico
bench --site facturacion-v16.dev console
bench --site facturacion-v16.dev execute facturacion_mexico.one_offs.<script>.run
bench build --app facturacion_mexico
```

**NUNCA:** `bench migrate` sin `--site` — afecta otros sites del bench compartido.

---

## Qué hace esta app

App de facturación electrónica CFDI para México, integrada con FacturAPI.io como PAC.
Extiende ERPNext para emitir, cancelar y gestionar CFDIs (tipos I, E, P) desde Sales Invoice,
con soporte multi-sucursal, addendas, e-receipts y complementos de pago.

### DocTypes principales

| DocType | Qué es | Estado |
|---|---|---|
| `Factura Fiscal Mexico` | CFDI tipo I/E via FacturAPI. Submittable. | ✅ Funcional |
| `Complemento Pago MX` | CFDI tipo P (PPD). Auto desde Payment Entry. | ✅ Funcional |
| `EReceipt MX` | Recibo digital para autofacturación. | ✅ Funcional |
| `Factura Global MX` | Agrupa E-Receipts en CFDI global. | ✅ Funcional |
| `Facturacion Mexico Settings` | Single — credenciales FacturAPI, config global. | ✅ Funcional |
| `Configuracion Fiscal Mexico` | Config fiscal por empresa — wizard STCT/ITT. | ✅ Funcional |
| `Configuracion Fiscal Sucursal` | Config fiscal por Branch con folios y series. | ✅ Funcional |
| `IEPS Cuota SAT` | Cuotas fijas IEPS por producto/empresa/fecha. | ✅ Creado, sin datos |
| `FacturAPI Response Log` | Trazabilidad de respuestas del PAC. | ✅ Funcional |

Catálogos SAT propios: `Uso CFDI SAT`, `Forma Pago SAT`, `Metodo Pago SAT`,
`Regimen Fiscal SAT`, `SAT Producto Servicio`.

---

## Lógica crítica

### Flujo principal

```
Sales Invoice (submit)
  → doc_events hooks
  → Factura Fiscal Mexico
  → timbrado_api.py
  → FacturAPI.io
  → SAT
```

### Custom Fields sobre DocTypes de ERPNext

- **Sales Invoice:** ~35 campos (estado fiscal, timbrado, multi-sucursal, addenda)
- **Branch:** 14 campos (folios, series, certificados)
- **Customer:** 12 campos (RFC, régimen fiscal, uso CFDI)
- **Item:** 3 campos (clave SAT)
- **Payment Entry:** 5 campos (forma de pago SAT)

Prefijo obligatorio: `fm_*` para todos los custom fields.

### Hooks activos

- `Sales Invoice.before_validate` → asignación automática STCT por Branch
- `Sales Invoice.validate` → `cost_center` y `fm_producto_servicio_sat` obligatorios en cada línea
- `Customer.validate` → validación formato RFC
- `Payment Entry.on_submit` → crea complemento PPD automáticamente
- `Branch.validate/on_update` → campos fiscales multi-sucursal

### API externa

- **FacturAPI.io** — PAC para timbrado CFDI
- Sandbox/producción configurable en `Facturacion Mexico Settings`
- Cliente HTTP en `facturacion_fiscal/timbrado_api.py`

---

## Problemas críticos conocidos (no tocar sin plan)

1. **`draft_management/api.py`** — completamente simulado con MOCKs. Flujos con
   `fm_create_as_draft = True` no generan CFDI real. Falla silenciosamente.

2. **`facturacion_fiscal/api_backup.py`** — fallback de recovery escribe en `/tmp/`.
   Se pierde en reinicio. Viola cumplimiento fiscal (respuestas PAC tienen valor legal).

3. **IEPS Cuota $0 en submit** (issue #81) — cuotas `charge_type="Actual"` se vuelven $0
   al hacer submit. Hooks comentados (`# E4 DISABLED`). No bloquea timbrado de IVA estándar.

4. **Motor de reglas** — `execute_call_api_manual()` y similares retornan strings de error,
   no ejecutan nada.

---

## Reglas específicas de facturacion_mexico

### RG-001: Idioma español obligatorio

- Labels DocTypes/campos, opciones Select, mensajes error, docstrings → español
- Variables de código → inglés (convención técnica)

### RG-003: Testing

- Suite ≤ 5 min, determinista, sin red, sin commits manuales
- `FrappeTestCase` + IDs únicos con `frappe.generate_hash()`
- Mock solo en boundary externo (FacturAPI, SAT) — nunca `frappe.get_doc`

```python
class TestReglaNegocio(FrappeTestCase):
    def setUp(self):
        self.test_id = "TEST-" + frappe.generate_hash()[:6]
```

### RG-007: Hooks específicos

- Prohibidos hooks universales (`"*"`) — bloquean setup wizard
- Solo hooks específicos por DocType
- Tests obligatorios después de modificar `hooks.py`

### RG-009: Fixtures obligatorios (zero-config)

- Todo Custom Field, Workflow, Property Setter → fixture en `hooks.py`
- Prohibido crear configuración solo local que no migre
- Prohibido `frappe.db.sql("UPDATE...")` como atajo a fixture roto

### RG-010: Scripts one-off

- Ubicación: `facturacion_mexico/one_offs/`
- Solo via `bench execute`, nunca `python3 script.py`
- No commitear al repo
- Nombres: `{accion}_{descripcion}.py` (no iniciar con número)

```bash
bench --site facturacion-v16.dev execute "facturacion_mexico.one_offs.script_name.run"
```

### RE-001: Normativa SAT

- Workflows 01/02/03/04 según normativa SAT
- Override class para múltiples FFMs (evita LinkExistsError)
- TipoRelación 04 obligatorio en sustituciones
- Validaciones estrictas motivos cancelación

### RE-002: Documentación

- `docs/instructions/` → SOLO el usuario puede crear archivos ahí. Claude solo lee.
- Planes de implementación → `docs/development/`
- Reportes técnicos → `docs/development/` o `docs/audit/`
- ADRs → `docs/adr/`

### RE-005: Custom Fields

- Prefijo `fm_*` obligatorio en todos los custom fields
- Todo custom field debe tener fixture declarado en `hooks.py`
- Sin fixture → bloquea deployment en site nuevo

---

## Antes de cada PR

- [ ] Tests pasan: `bench --site facturacion-v16.dev run-tests --app facturacion_mexico`
- [ ] Fixtures exportados si hubo cambios de Custom Fields, Workflows o Roles
- [ ] Patch creado si hay cambios de esquema con datos existentes
- [ ] Sin secretos (credenciales FacturAPI nunca en código)
- [ ] `bench --site facturacion-v16.dev migrate` limpio
