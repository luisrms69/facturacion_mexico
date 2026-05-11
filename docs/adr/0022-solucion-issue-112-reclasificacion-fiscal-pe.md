# ADR-0022 — Solución Issue #112: Reclasificación Fiscal en Payment Entry

**Fecha:** 2026-05-11
**Estado:** Implementado (Fase 0 PR #126 + Fase 1 en progreso)
**Issue:** #112 — Mapeo Reclasificacion Fiscal Payment Entry necesita validación y UX mejorada

---

## Contexto

Al registrar cobros PPD en Payment Entry, el sistema reclasifica impuestos de
cuentas transitorias (al timbrar) a cuentas definitivas (al cobrar). Este mecanismo
usa `Mapeo Reclasificacion Fiscal Payment Entry` (MRFPE) como tabla operativa.

El problema tenía dos niveles:
1. **Silencio contable:** cuando faltaba un mapeo, `payment_entry_reclasificacion.py`
   hacía `continue` silencioso — el IVA no se reclasificaba y nadie se enteraba.
2. **Sin guía de configuración:** el usuario debía crear los registros MRFPE
   manualmente sin ninguna validación de completitud ni flujo guiado.

---

## Arquitectura implementada

```
CFM (declaración de alcance fiscal — ingresos)
  ↓ lectura — sin modificar
CRFM [NUEVO] (rector: qué cuentas se reclasifican y a dónde)
  ↓ crea/actualiza idempotente
MRFPE (tabla operativa — sin cambios de schema)
  ↓ consume — sin cambios
payment_entry_reclasificacion.py
```

### Principios de diseño

- CFM no se modifica — solo lectura para detección
- MRFPE permanece como tabla operativa final
- CRFM es el intermediario que conecta CFM con MRFPE
- Sin estados visibles para el usuario — la lógica es implícita en `cuenta_destino`
- Sin conceptos de "Omitido" — filas vacías simplemente se saltan

---

## Fase 0 — Eliminar silencio contable (PR #126 — completo)

**Archivo:** `payment_entry_reclasificacion.py`

Cambio: `continue` silencioso → `frappe.msgprint` naranja que lista las cuentas
sin mapeo. El PE se guarda sin bloquear. La reclasificación sigue saltándose
las cuentas sin mapeo, pero ahora el usuario lo sabe.

**Tests:** 14/14 PASS (`TestPaymentEntryReclasificacion`)

---

## Fase 1 — DocType CRFM (este PR)

### Nuevos DocTypes

**`Configuracion Reclasificacion Fiscal Mexico` (CRFM)**
- Uno por empresa (`CRFM-{company}`)
- Dos métodos whitelisted: `cargar_reglas()` y `aplicar()`
- Sin estados, sin máquina de estados — la lógica vive en `cuenta_destino`

**`Regla Reclasificacion Fiscal`** (child table de CRFM)

| Campo | Tipo | Descripción |
|---|---|---|
| `rol_fiscal` | Data, read-only | Tipo semántico del impuesto (de CFM) |
| `cuenta_origen` | Link Account, read-only | Cuenta transitoria (al timbrar) |
| `cuenta_destino` | Link Account, **editable** | Cuenta definitiva (al cobrar) — filtro Tax |
| `mrfpe_ref` | Link MRFPE, read-only | Referencia al mapeo operativo vigente |
| `tipo_operacion` | Select, read-only | Cobro / Pago |
| `source_type` | Select, read-only | Ingresos / CFM \| Manual |

### Flujo de uso

**"1. Cargar Reglas"** → llama `cargar_reglas()`:
- Limpia las reglas automáticas (source_type = "Ingresos / CFM")
- Lee `CFM.mapeo_cuentas` (solo filas `estado_validacion = "Válido"`)
- Para cada cuenta: busca MRFPE existente con `frappe.get_all(ignore_permissions=True)`
- Si MRFPE existe → carga `cuenta_destino` del mapeo actual + `mrfpe_ref`
- Si no existe → `cuenta_destino` vacío para que el usuario la llene
- Preserva `cuenta_destino` que el usuario ya había llenado en runs anteriores

**El usuario edita `cuenta_destino`** en el grid directamente (filtro: solo cuentas Tax).

**"2. Generar Mapeos"** → llama `aplicar()`:
- Bloquea si alguna fila tiene `cuenta_destino` vacío — lista cuáles faltan
- Para cada fila con `cuenta_destino`:
  - Si MRFPE existe y `cuenta_destino` es igual → sin cambios
  - Si MRFPE existe y `cuenta_destino` cambió → actualiza MRFPE
  - Si no existe MRFPE → crea nuevo MRFPE
- Reporta: Creados / Actualizados / Sin cambios / Sin cuenta destino

### Archivos creados

```
facturacion_mexico/facturacion_fiscal/doctype/
  configuracion_reclasificacion_fiscal_mexico/
    configuracion_reclasificacion_fiscal_mexico.json
    configuracion_reclasificacion_fiscal_mexico.py
    configuracion_reclasificacion_fiscal_mexico.js
    test_configuracion_reclasificacion_fiscal_mexico.py

  regla_reclasificacion_fiscal/
    regla_reclasificacion_fiscal.json
    regla_reclasificacion_fiscal.py
    __init__.py
```

### Tests

| Clase | Tests | Cobertura |
|---|---|---|
| `TestCRFMCargarReglas` | 7 | sin CFM, sin MRFPE, con MRFPE, preservar previo, ignorar inválidos, reconstruir |
| `TestCRFMAplicar` | 6 | crear, actualizar, sin cambio, saltar vacíos, datos correctos, sin empresa |

**13/13 PASS** en `test-facturacion.localhost`

---

## Fase 2 — Pagos/Egresos (pendiente, issue separado)

`source_type = "Manual"` ya existe en el schema. La detección automática para
Purchase Invoice/pagos a proveedores se implementará en un issue dedicado.

---

## Alternativas descartadas

**Extender CFM** con campos de reclasificación: descartado porque CFM está
orientado a ingresos/facturación, ya causó problemas, y mezclaría
responsabilidades de timbrado con responsabilidades de cobro.

**Máquina de estados en el grid**: descartado — sobre-ingenierizado. El usuario
solo necesita ver y editar `cuenta_destino`. El sistema decide qué hacer.

---

## Consecuencias

**Positivas:**
- El usuario tiene un flujo guiado para configurar reclasificación
- CFM no se modifica — sin riesgo de regresión en timbrado
- MRFPE sigue funcionando sin cambios — instalaciones existentes compatibles
- Grid simple: 6 columnas, solo `cuenta_destino` es editable

**Pendientes:**
- Issue #123 — selector `_hide_cancel_button` demasiado amplio (PE)
- Issue #124 — consolidar llamadas `get_fiscal_ui_state` en SI refresh
- Issue #127 — revisión de permisos CRFM y Regla Reclasificacion Fiscal

---

## Referencias

- Issue #112: https://github.com/luisrms69/facturacion_mexico/issues/112
- PR #126: fix(reclasificacion): avisar al usuario cuando falta mapeo en PE
- `facturacion_mexico/facturacion_fiscal/services/payment_entry_reclasificacion.py`
- `facturacion_mexico/facturacion_fiscal/doctype/mapeo_reclasificacion_fiscal_payment_entry/`
- `facturacion_mexico/facturacion_fiscal/doctype/configuracion_reclasificacion_fiscal_mexico/`
