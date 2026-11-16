# CLAUDE.md — facturacion_mexico

> **Reglas de operación Claude Code** (commits, PRs, base de datos, flujo de trabajo, prohibiciones git):
> Ver `/home/erpnext/Developer/frappe-infrastructure/.claude/CLAUDE.md`

---

## Estado del proyecto

- **Migración:** v15 → v16 completada (2026-05-01)
- **Bench:** `/home/erpnext/frappe-bench-v16`
- **Branch activo:** feature branch creada desde `main` (nunca commitear en `main`)
- **Versión:** 0.0.1 (desarrollo activo)
- **En producción:** No

---

## Sites de desarrollo y prueba

| Site | Propósito | Notas |
|---|---|---|
| `facturacion-v16.dev` | Desarrollo activo | Site principal para implementación de features |
| `test-facturacion.localhost` | Tests unitarios | Solo para `bench run-tests` — nunca modificar manualmente |
| `test-fm-v010.localhost` | Prueba instalación limpia | Simula fresh install con empresa real y credenciales FacturAPI sandbox |

**Reglas de uso:**
- `bench migrate` → solo el site donde se está trabajando en ese momento. Nunca en ambos por default.
- `bench run-tests` → siempre `test-facturacion.localhost`
- `bench export-fixtures` → siempre `facturacion-v16.dev`
- Smoke tests / validación visual → `test-fm-v010.localhost`

**Site activo en este momento:** `test-fm-v010.localhost` (prueba fresh install en curso)

---

## Comandos — bench v16 multi-site

Este bench comparte sitios. **Siempre especificar `--site`.**

```bash
# Desarrollo
bench --site facturacion-v16.dev migrate
bench --site facturacion-v16.dev export-fixtures --app facturacion_mexico
bench --site facturacion-v16.dev console
bench --site facturacion-v16.dev execute facturacion_mexico.one_offs.<script>.run
bench build --app facturacion_mexico

# Tests unitarios
bench --site test-facturacion.localhost run-tests --app facturacion_mexico

# Prueba fresh install
bench --site test-fm-v010.localhost migrate
bench --site test-fm-v010.localhost list-apps
```

**NUNCA:** `bench migrate` sin `--site` — afecta todos los sites del bench compartido.

---

## Arquitectura y referencia

La descripción de arquitectura, DocTypes, Custom Fields, hooks, flujos, estado funcional,
limitaciones conocidas, fixtures y patches vive en `docs/` (no se duplica aquí):

- Arquitectura implementada, flujos, DocTypes, custom fields críticos, integraciones externas,
  estado funcional y limitaciones conocidas → `docs/tecnico/arquitectura.md`
- Referencia de DocTypes → `docs/referencia/doctypes.md`
- Referencia de campos fiscales → `docs/referencia/campos-fiscales.md`
- Hooks y fixtures declarados → `docs/referencia/hooks.md`
- API whitelisted → `docs/referencia/api.md`
- Configuración por empresa → `docs/referencia/configuracion.md`
- Patches históricos registrados → `docs/adr/0000-estado-real-pre-migracion.md` (§7)
- Decisiones arquitectónicas permanentes → `docs/adr/`

---

## Dependencias

**Apps de Frappe requeridas:** erpnext (declarado en `required_apps`)  
**Apps en el mismo bench (v16):** hrms, payments, facturacion_mexico  
**API externa:** FacturAPI.io (credenciales por empresa en `Facturacion Mexico Company Settings`)

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

### RG-010b: Patches — PROHIBICIÓN ABSOLUTA

- **`patches.txt` está vacío** — no hay patches activos en el app.
- Los archivos `.py` de patches están en `patches/legacy/` solo como referencia histórica.
- **PROHIBIDO ejecutar patches legacy** via `bench execute` como workaround.
- **PROHIBIDO reactivar patches** comentados o moverlos de legacy/ sin PR aprobado.
- Si `bench migrate` falla, se corrige la **causa actual** (código, fixtures, after_migrate).
  Nunca se revive un patch viejo para tapar el error.

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

## REGLAS GIT — FACTURACION MEXICO

Para commits, push y PRs usar **siempre** `/ship`:
- `/ship commit` — para commits
- `/ship push` — para push
- `/ship pr` — para pull requests (incluye `/pr-ready` completo con linters, tests, fixtures y doc-review)

Site de desarrollo: `facturacion-v16.dev` — Site de tests: `test-facturacion.localhost`

---

## Auditoría pre-migración

Ver `docs/adr/0000-estado-real-pre-migracion.md` para el estado documentado el 2026-04-25.
