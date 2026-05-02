# ADR 0006 — ANÁLISIS DE BRANCHES WIP
======================================
Fecha: 2026-05-01
Método: `gh api repos/luisrms69/facturacion_mexico/compare/main...<branch>`

---

## Tabla resumen

| Branch | Commits sobre main | Archivos código tocados | Funcionalidad | IEPS | Tax Category | Prioridad merge |
|--------|:-----------------:|------------------------|---------------|:----:|:------------:|:---------------:|
| `fix/remove-zombie-patch-create-custom-fields` | 1 | `patches.txt` | Elimina patch zombie que rompe install v16 | — | — | **URGENTE** |
| `feature/infra-setup` | 4 | `CLAUDE.md`, `.github/` | CI, PR template, ADR Fase 0 | — | — | Alta |
| `feature/migracion-tax-category-to-custom-field` | 1 | `patches.txt`, `custom_field.json`, `patches/v1_0/migrate_customer_tax_category_to_fm_tax_regime.py` | Solo el patch de migración tax_category→fm_tax_regime | — | ✓✓✓ | Media (superado por e1) |
| `feat/mx-fiscal-E0-E3-issues-65-66` | 10 | `configuracion_fiscal_mexico`, `mapeo_cuenta_fiscal_mexico`, `constantes_fiscales.py`, `generador_templates_fiscal.py`, `hooks_handlers/sales_invoice_automated_tax.py` | Wizard mapeo fiscal E0.5 + DocTypes base + sistema automatizado impuestos (estructura) | ✓ | — | Media (superado por e1) |
| `feature/migracion-tax-category-correct-base` | 16 | ídem E0-E3 + `timbrado_api.py`, `factura_fiscal_mexico.py` | E0.5 + migración tax_category completa + limpieza Tax Categories SAT | ✓ | ✓✓✓ | Media (superado por e1) |
| `feature/e1-automated-tax-system` | 30 | +`ieps_cuota_sat`, `utils/calculo_impuestos.py`, `utils/reglas_calculo_fiscal.py`, `utils/roles_fiscales.py`, `setup/item_groups.py` | Sistema completo E0→E4: wizard + migración + IEPS granular + retenciones + puente SI→PAC | ✓✓✓ | ✓✓✓ | Alta (base sólida) |
| `fix/ieps-tabaco-dual-campos-tax-breakup` | 33 | ídem e1 + `utils/clasificacion_items.py` | Superset de e1 + fix IEPS Cuota congelado + corrección keys item_wise_tax_detail | ✓✓✓✓ | ✓✓✓ | Alta (más avanzado que e1) |
| `feature/e4-ieps-on-item-quantity` | 42 | ídem fix/ieps + `utils/mapeo_charge_type.py`, tests adicionales | La más completa: todo lo anterior + STCT 8 específicos + clasificación items + FIX-V1 cuotas | ✓✓✓✓ | ✓✓✓ | **Candidata principal** (WIP en últimos commits) |
| `feature/cleanup-documentacion-one-offs` | 1 | solo `docs/` | Mueve archivos Sprint6 a docs/, limpia one-offs | — | — | Baja (solo docs) |
| `develop` | 0 | — | Vacía, idéntica a main | — | — | Ignorar |

---

## Análisis por branch

### `fix/remove-zombie-patch-create-custom-fields` — 1 commit ⚡ URGENTE

**Qué hace:** Elimina de `patches.txt` un patch llamado `create_custom_fields` que viola
REGLA#4 del proyecto y rompe instalaciones limpias en v16.

**Por qué es urgente:** Cada vez que se hace `bench migrate` en una instalación nueva de v16,
ese patch zombie se ejecuta y falla. Debe mergearse antes que cualquier otra rama para
que el baseline esté limpio.

**Riesgo:** Mínimo. Un solo archivo, una sola línea eliminada.

---

### `feature/infra-setup` — 4 commits

**Qué hace:**
- ADR Fase 0: estado real pre-migración
- CLAUDE.md reescrito con nuevo formato
- PR template agregado a `.github/`
- CI deshabilitado temporalmente (pendiente actualización para v16)

**Relación con fiscal:** Ninguna. Solo infraestructura y documentación de proceso.

**Riesgo:** Mínimo. Sin cambios en lógica de negocio.

---

### `feature/migracion-tax-category-to-custom-field` — 1 commit

**Qué hace:** El patch `patches/v1_0/migrate_customer_tax_category_to_fm_tax_regime.py`
que migra el campo `tax_category` del doctype Customer al custom field `fm_tax_regime`.

**Superado por:** `feature/e1-automated-tax-system` contiene este mismo commit más 29 adicionales.
Mergearlo solo no tiene sentido sin el resto de e1.

---

### `feat/mx-fiscal-E0-E3-issues-65-66` — 10 commits

**Qué hace (E0.5):**
- Nuevos DocTypes: `Configuracion Fiscal Mexico`, `Mapeo Cuenta Fiscal Mexico`
- Constantes fiscales centralizadas (`constantes_fiscales.py`)
- Generador de templates de impuestos (`generador_templates_fiscal.py`)
- Hook `sales_invoice_automated_tax.py` — estructura base del sistema automatizado
- UI JS en Sales Invoice (botón preview templates)

**Superado por:** `feature/e1-automated-tax-system` (los primeros 10 commits son idénticos).

---

### `feature/migracion-tax-category-correct-base` — 16 commits

**Qué hace (E0.5 + migración):**
Todo lo de `feat/mx-fiscal-E0-E3-issues-65-66` más:
- Migración `Customer.tax_category → fm_tax_regime` con patch idempotente (3 fases)
- Eliminación definitiva de Tax Categories SAT del sistema
- Corrección referencias en `timbrado_api.py` y `factura_fiscal_mexico.py`
- Fix alcance E0.5: elimina creación Tax Rules

**Superado por:** `feature/e1-automated-tax-system` (primeros 16 commits son idénticos).

---

### `feature/e1-automated-tax-system` — 30 commits ⭐

**Qué hace (E0 → E4 parcial):**

| Hito | Descripción |
|------|-------------|
| E0.5 | Wizard mapeo fiscal + DocTypes base |
| Migración | `Customer.tax_category → fm_tax_regime` |
| E1 | Sistema mixto ITT 0% + IVA normal en misma factura |
| Item Groups | Sistema automático con asignación ITT por grupo |
| E2-E3 | IEPS granular + retenciones multi-tipo (precisión mejorada) + RESICO |
| E4 | Puente SI→PAC read-only con impuestos por concepto + validación payload |
| WIP | IEPS Cuota parcial (último commit marcado como `wip`) |

**Archivos de código nuevos respecto a main:**
- `config/sat_objeto_impuesto.py`, `sat_tax_rates.py`, `sat_tipo_factor.py`
- `facturacion_fiscal/config/constantes_fiscales.py`
- `facturacion_fiscal/doctype/configuracion_fiscal_mexico/` (DocType completo)
- `facturacion_fiscal/doctype/ieps_cuota_sat/` (DocType)
- `facturacion_fiscal/doctype/mapeo_cuenta_fiscal_mexico/` (DocType)
- `facturacion_fiscal/setup/generador_templates_fiscal.py`
- `hooks_handlers/sales_invoice_automated_tax.py`
- `hooks_handlers/sales_invoice_ieps.py`
- `patches/v1_0/migrate_customer_tax_category_to_fm_tax_regime.py`
- `setup/item_groups.py`
- `utils/calculo_impuestos.py`, `clasificacion_items.py`, `reglas_calculo_fiscal.py`, `roles_fiscales.py`

**Relación con fiscal/IEPS/tax:** Muy alta. Es el sistema completo de cálculo automático
de impuestos para CFDI mexicano.

---

### `fix/ieps-tabaco-dual-campos-tax-breakup` — 33 commits ⭐

**Qué hace:** Superset de `feature/e1-automated-tax-system` (primeros 30 commits idénticos) más:
- Congelación IEPS Cuota y IVA cascada (checkpoint funcional)
- Fix crítico: corrección de keys en `item_wise_tax_detail` para IEPS Cuota
  (usaba `item.name` en lugar de `item.item_code` → bug en tax breakup)

**Diferencia respecto a e1:** 3 commits adicionales que resuelven el bug de doble campo
en impuestos de tabaco/IEPS cuota fija. Esta es la corrección que faltaba en e1.

**Archivos adicionales:** `utils/clasificacion_items.py`

---

### `feature/e4-ieps-on-item-quantity` — 42 commits 🏆 CANDIDATA PRINCIPAL

**Qué hace:** La rama más completa. Superset de `fix/ieps-tabaco` (33 commits) más:
- Sistema 8 STCT específicos + generación automática ITT
- Consolidación single source of truth para roles fiscales (JSON ↔ Python sincronizados)
- Fix generación templates + carga tax rows + eliminación código JS legacy
- FIX-V1: preservar cuotas IEPS en estado draft (bug ERPNext)
- Tests: `test_autoseleccion_stct.py`, `test_clasificacion_items.py`, `test_sync_roles_fiscales_json_python.py`
- Checkpoint seguridad: ITT específico por item (WIP)

**Archivos adicionales sobre fix/ieps-tabaco:**
- `utils/mapeo_charge_type.py`
- `tests/test_autoseleccion_stct.py`
- `tests/test_clasificacion_items.py`
- `tests/test_sync_roles_fiscales_json_python.py`

**Estado:** Los últimos 2 commits son `chore(e4): checkpoint de seguridad` y
`fix(e1): implementar FIX-V1 para preservar cuotas IEPS en draft`. El sistema de
IEPS Cuota está funcional pero el ITT específico por item está en progreso.

---

### `feature/cleanup-documentacion-one-offs` — 1 commit

**Qué hace:** Mueve archivos temporales del Sprint6 a `docs/` y elimina one-offs obsoletos.
Sin cambios en código Python ni JS.

---

## Árbol de linaje entre branches

```
main
├── fix/remove-zombie-patch-create-custom-fields  (1)  ← merge urgente
├── feature/infra-setup  (4)                           ← merge pronto
├── feature/cleanup-documentacion-one-offs  (1)        ← merge cuando convenga
│
└── feature/migracion-tax-category-to-custom-field  (1)
      └── feat/mx-fiscal-E0-E3-issues-65-66  (10)
            └── feature/migracion-tax-category-correct-base  (16)
                  └── feature/e1-automated-tax-system  (30)
                        └── fix/ieps-tabaco-dual-campos-tax-breakup  (33)
                              └── feature/e4-ieps-on-item-quantity  (42)  ← MÁS AVANZADA
```

Las ramas intermedias están todas contenidas en `feature/e4-ieps-on-item-quantity`.
Mergear cualquiera de ellas individualmente no aporta nada si la meta final es
mergear e4.

---

## Recomendación de merge

### Orden sugerido:

**1. Inmediato** — `fix/remove-zombie-patch-create-custom-fields`
- 1 archivo, 1 línea. Sin riesgo. Desbloquea installs limpias v16.

**2. Corto plazo** — `feature/infra-setup`
- CI, PR template, CLAUDE.md. Sin riesgo funcional.

**3. Evaluación** — `feature/e4-ieps-on-item-quantity`
- Necesita revisión de los últimos 9 commits (estado WIP).
- Los primeros 33 commits son estables (los fix/ieps-tabaco los tiene).
- Decidir si mergear hasta el commit 33 (fix/ieps-tabaco) y dejar los 9 WIP en rama separada.

**4. Descartar** — `develop`, ramas intermedias superadas
- `develop` — vacía
- `feature/migracion-tax-category-to-custom-field` — contenida en e4
- `feat/mx-fiscal-E0-E3-issues-65-66` — contenida en e4
- `feature/migracion-tax-category-correct-base` — contenida en e4

**5. Docs** — `feature/cleanup-documentacion-one-offs`
- Merge cuando se haga limpieza general de docs.

---

## Impacto en el sistema actual (main)

Los cambios de `feature/e4-ieps-on-item-quantity` respecto a `main` introducen:

1. **2 nuevos DocTypes**: `Configuracion Fiscal Mexico`, `Ieps Cuota SAT` → requieren `bench migrate`
2. **1 nuevo DocType**: `Mapeo Cuenta Fiscal Mexico` → requiere `bench migrate`
3. **1 patch de datos**: `migrate_customer_tax_category_to_fm_tax_regime` → migra campo en Customer
4. **Hooks nuevos en Sales Invoice**: `sales_invoice_automated_tax.py`, `sales_invoice_ieps.py`
5. **`timbrado_api.py` modificado**: cambios en cómo construye el payload de impuestos para FacturAPI
6. **`hooks.py` modificado**: nuevos `doc_events` registrados

Antes de mergear e4 a main en producción → verificar compatibilidad con v16 de los
nuevos hooks y el sistema de Item Groups automático.
