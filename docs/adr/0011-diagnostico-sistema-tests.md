# ADR 0011 — DIAGNÓSTICO SISTEMA DE TESTS
======================================
Fecha: 2026-05-03
Site: facturacion-v16.dev
Bench: /home/erpnext/frappe-bench-v16

---

## Estado actual

| Métrica | Valor |
|---------|-------|
| Archivos de test | 49 |
| Total `def test_` | 482 |
| Líneas de código de tests | ~24,000 |
| Tests que pasan | **0** |
| Porcentaje éxito | **0%** |

---

## Causa raíz del crash

El runner falla en la **inicialización de ERPNext** antes de ejecutar
un solo test de `facturacion_mexico`:

```
frappe.exceptions.DuplicateEntryError:
('Item Tax Template', '_Test Item Tax Template 1 - _TC',
 IntegrityError(1062, "Duplicate entry ... for key 'PRIMARY'"))
```

**Cadena de fallo:**

```
bench run-tests --app facturacion_mexico
  → Frappe test runner carga dependencias de doctypes
  → Importa test_sales_invoice.py de ERPNext
  → ERPNextTestSuite.BootStrapTestData().__init__()
  → make_master_data() → make_item_tax_template()
  → frappe.get_doc(record).insert()
  → DuplicateEntryError ← CRASH
```

`facturacion-v16.dev` tiene datos reales de desarrollo (Item Tax Templates,
STCTs, Items, etc. creados manualmente). El bootstrap de ERPNext asume una
DB de test limpia. El conflicto es estructural — no un bug de código.

---

## Problema de los 38 archivos legacy `test_layer*.py`

Escritos durante el desarrollo en bench v15 para el site `facturacion.dev`.

**Supuestos que ya no son válidos en v16:**

| Supuesto legacy | Realidad en facturacion-v16.dev |
|----------------|--------------------------------|
| DB limpia sin datos | DB con datos de desarrollo activo |
| `_Test Company` con `INR` como currency | Company con `MXN` |
| No hay STCTs previos | STCTs creados manualmente para pruebas |
| Frappe v15 test runner | Frappe v16 con API diferente |
| `make_test_records` disponible | Comportamiento diferente en v16 |

**Señales adicionales de deuda:**

- `bootstrap.py` intenta normalizar `_Test Company.default_currency` a `INR`
  (la currency de test de ERPNext) — contradicción directa con el sistema fiscal MX
  que requiere `MXN`
- Tests de Layer 3-4 crean documentos completos (Branch, Company, Customer, SI)
  que colisionan con datos existentes
- Tests de Layer 4 incluyen "stress testing" y "disaster recovery" —
  categorías inapropiadas para un CI de app Frappe

---

## Los 6 tests recientes que SÍ son rescatables

Escritos durante el desarrollo E0-E4 (rama `feature/e4-ieps-on-item-quantity`).
Son determinísticos, no dependen de DB:

| Archivo | Tests | Naturaleza |
|---------|-------|------------|
| `test_autoseleccion_stct.py` | 7 | Lógica pura: `_determinar_variante_stct()` |
| `test_clasificacion_items.py` | 7 | Lógica pura: `clasificar_items_documento()` |
| `test_hito1_constantes.py` | 8 | Constantes fiscales SAT — sin DB |
| `test_sync_roles_fiscales_json_python.py` | 3 | Sincronización JSON↔Python |
| `test_migration_compatibility.py` | 6 | Compatibilidad patches — minimal DB |
| `test_wizard_mapeo_fiscal.py` | 14 | Wizard fiscal — necesita revisión |

**Total rescatable: ~45 tests** (estimado, pendiente verificar `test_wizard_mapeo_fiscal`)

---

## Propuesta de rediseño

### Principios

1. **Sin dependencias de datos existentes.** Cada test crea y destruye sus propios
   datos. Nunca asume que un registro específico existe en la DB.

2. **Mock solo en boundary externo.** FacturAPI, SAT, servicios HTTP → mock.
   Nunca mockear `frappe.get_doc`, `frappe.db.get_value` ni lógica interna.

3. **Determinismo absoluto.** IDs únicos vía `frappe.generate_hash()[:6]`.
   Un test no puede depender del orden de ejecución de otro.

4. **Suite ≤ 5 minutos.** Si tarda más, algo está mal en el diseño.

5. **Cobertura funcional, no volumétrica.** 50 tests que prueban flujos reales
   valen más que 482 tests que prueban stubs.

### Qué conservar

- Los 6 archivos de tests E0-E4 (lógica pura, sin DB o mínima DB)
- El patrón `FrappeTestCase` + `frappe.generate_hash()` establecido en CLAUDE.md
- `test_sync_roles_fiscales_json_python.py` — documenta invariante crítico del sistema

### Qué descartar

- Los 38 archivos `test_layer*.py` — escritos para un entorno que ya no existe
- `bootstrap.py` — su lógica de normalización a `INR` es incompatible con MXN
- `ci_pre_tests.py`, `ci_seed.py` — infraestructura de seed que causa el crash
- `legacy_allowlist.py` — artefacto de migración ya no relevante
- Tests de "stress", "disaster recovery", "performance benchmarks" (Layer 4)
  — no pertenecen al CI de una app de negocio

### Qué construir nuevo

Tres categorías de tests en el rediseño:

**Categoría A — Lógica pura (sin DB, instantáneos):**
- Constantes SAT, clasificación de items, cálculo de impuestos, reglas fiscales
- Tiempo estimado: < 1 segundo por suite

**Categoría B — Validaciones de DocType (DB, aislados):**
- Cada test crea sus propios datos con `generate_hash()` y hace `tearDown()`
- Cubre: validaciones de FFM, hooks de SI, guards de cancelación
- Tiempo estimado: < 30 segundos por suite

**Categoría C — Flujos de timbrado (DB + mock PAC):**
- Mock de `timbrado_api.TimbradoAPI._call_facturapi()` para no tocar red
- Cubre: construcción de payload, manejo de errores PAC, estados FFM
- Tiempo estimado: < 2 minutos por suite

---

## Decisión pendiente: site dedicado de tests vs mock de datos

### Opción A — Site dedicado de tests (`test-facturacion.localhost`)

| | |
|--|--|
| **Ventaja** | DB limpia, bootstrap ERPNext funciona, tests de integración reales |
| **Ventaja** | Se puede resetear entre runs con `frappe.db.rollback()` |
| **Desventaja** | Requiere crear y mantener un site adicional |
| **Desventaja** | Setup más complejo en CI |

### Opción B — Mock de datos en todos los tests

| | |
|--|--|
| **Ventaja** | Funciona en el site actual sin cambiar infraestructura |
| **Ventaja** | Tests más rápidos |
| **Desventaja** | No prueba integración real con ERPNext |
| **Desventaja** | Más código de setup en cada test |

### Opción C — Mixta (recomendada)

- Tests A y B (lógica + validaciones) → corren en site actual con datos aislados
- Tests C (flujos completos) → site dedicado `test-facturacion.localhost` o sandbox
- La mayoría del CI corre en segundos; el subset de integración corre en PR reviews

**Decisión no tomada todavía.** Requiere alineación con el usuario antes de implementar.

---

## Siguiente paso

Antes de implementar rediseño, definir:

1. ¿Crear `test-facturacion.localhost` en bench v16 o usar `facturacion-v16.dev`
   con `frappe.db.rollback()` en cada test?
2. ¿Qué porcentaje de los 38 archivos legacy tienen valor real vs son ruido?
   (revisar manualmente los más relevantes)
3. ¿Cuáles son los flujos críticos que DEBEN tener cobertura de test?
   (timbrado básico, cancelación, tipo E son candidatos obvios)
