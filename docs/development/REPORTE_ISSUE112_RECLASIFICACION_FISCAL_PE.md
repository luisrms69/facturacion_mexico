# Issue #112 — Reclasificación Fiscal en Payment Entry
# Análisis de Arquitectura y Diseño para Resolución
# Fecha: 2026-05-10
# Estado: DISEÑO APROBADO — pendiente implementación

---

## Contexto del problema

Issue #112 es la **prioridad 1 del cierre de roadmap**. No es un bug menor —
es una deficiencia arquitectónica en el flujo de reclasificación fiscal que ocurre
cada vez que se registra un cobro PPD (y eventualmente pagos).

El problema tiene dos niveles:
1. **Inmediato:** el sistema falla silenciosamente cuando no hay mapeo — no avisa
2. **Arquitectónico:** hay un diseño deficiente entre dos doctypes que deben trabajar
   juntos pero están completamente desconectados

---

## El flujo de reclasificación fiscal — qué debe pasar

Cuando una empresa mexicana emite una factura PPD (pago en parcialidades o diferido):

```
MOMENTO 1 — Timbrado de la factura (Sales Invoice):
  IVA 16% = $160 → queda en "IVA por Cobrar" (cuenta temporal/transitoria)
  No se reconoce como ingreso fiscal todavía

MOMENTO 2 — Registro del cobro (Payment Entry):
  El IVA pendiente SE RECLASIFICA:
  Dr  "IVA por Cobrar"  $160   ← cuenta_origen (transitoria)
  Cr  "IVA Cobrado"     $160   ← cuenta_destino (definitiva)

  Este GL extra es el que genera payment_entry_reclasificacion.py
```

⚠️ **Nota sobre IVA 0% y Exento:** Aunque estos impuestos no generan monto
reclasificable en Payment Entry, pueden requerir visibilidad para reportes
fiscales. Por tanto, **ningún rol fiscal se excluye automáticamente**
— todos se muestran para revisión y el usuario decide si los configura
o los marca como Omitido. No implica que todos requieran movimiento
contable en el cobro.

---

## Arquitectura aprobada

```
CFM (declaración de alcance fiscal — ingresos)
  ↓ lectura (solo detección, sin modificar)
CRFM [NUEVO] (rector: qué cuentas se reclasifican y a dónde)
  ↓ genera idempotente
MRFPE (tabla operativa — sin cambios en schema Fase 1)
  ↓ consume (sin cambios)
payment_entry_reclasificacion.py (solo se agrega log_error)
```

### Criterios de diseño aprobados

1. No mover la lógica actual de Payment Entry — solo agregar `log_error`
2. No eliminar MRFPE — sigue siendo tabla operativa final
3. No modificar CFM — solo lectura para detección
4. CFM no absorbe egresos/pagos — no es fuente universal
5. CRFM es flexible para fuentes futuras (`source_type` por regla, no por header)
6. Generación de MRFPE idempotente: no duplicar, no borrar registros manuales
7. Permitir revisar faltantes antes de generar
8. Retenciones: detectar pero no auto-generar en Fase 1
9. MRFPE existentes: detectar como "Ya existe externo", no migrar
10. Modo Manual funciona sin CFM
11. **Sin exclusiones automáticas de roles** — incluso IVA 0% y Exento se muestran para revisión fiscal/reportes; el usuario decide si se omiten
12. Issue #112 se cierra con: Fase 0 + CRFM Cobros + detección/generación idempotente

---

## Diseño final del nuevo DocType: Configuracion Reclasificacion Fiscal Mexico (CRFM)

### Header (uno por empresa, naming `CRFM-{company}`)

```
company           (Link → Company, reqd, unique)
enabled           (Check, default 1)
ultima_deteccion  (Datetime, read_only)
ultima_generacion (Datetime, read_only)
```

**Nota:** `source_type` NO va en el header — va en cada regla de la child table.
Esto permite que el mismo CRFM maneje reglas de distintas fuentes en el futuro.

### Child table: Regla Reclasificacion Fiscal

```
source_type     (Select: "Ingresos / CFM" | "Manual", reqd)
tipo_operacion  (Select: Cobro | Pago, reqd)
rol_fiscal      (Data, read_only — contexto semántico de CFM)
cuenta_origen   (Link → Account, reqd, read_only si source_type = Ingresos/CFM)
cuenta_destino  (Link → Account — el usuario confirma antes de generar)
activo          (Check, default 1)
estado_mrfpe    (Select: ver tabla de estados, read_only)
mrfpe_ref       (Link → MRFPE, read_only — apunta al MRFPE relacionado, generado o externo)
nota            (Small Text — mensaje contextual auto-llenado por el sistema o editable por usuario)
```

**Semántica de `mrfpe_ref`:** apunta al MRFPE relacionado independientemente de su
origen. `estado_mrfpe` es quien indica si fue generado por este CRFM ("Generado")
o si existía previamente ("Ya existe externo"). No se usan dos campos separados
en Fase 1 — `estado_mrfpe` da el contexto suficiente.

**Uso del campo `nota`:** el sistema lo auto-llena en la detección para guiar al
usuario. Ejemplos:
- Retención detectada — revisar mecánica contable antes de generar MRFPE.
- IVA 0% / Exento — normalmente puede marcarse como Omitido si no hay cuenta destino.
- MRFPE externo detectado — funciona correctamente sin intervención.

### Tabla de estados de `estado_mrfpe`

| Estado | Significado | Acción del usuario |
|---|---|---|
| `Pendiente cuenta destino` | Detectado desde CFM, falta cuenta_destino | Debe llenar cuenta_destino |
| `Listo para generar` | cuenta_destino definida, aún no se ha creado MRFPE — **transición automática** | Clic en "Generar MRFPE" |
| `Generado` | MRFPE creado por este CRFM; mrfpe_ref apunta al registro generado | Ninguna |
| `Ya existe externo` | Ya hay MRFPE activo para esta cuenta_origen, no generado por CRFM; mrfpe_ref apunta a él | Puede "adoptar" en Fase 2 |
| `Omitido` | El usuario decidió no reclasificar este impuesto | Ninguna |

**Transición automática a "Listo para generar":** cuando el usuario llena
`cuenta_destino` en una regla con estado "Pendiente cuenta destino", el estado
debe cambiar automáticamente. Se implementa en `validate()` del CRFM (Python)
o como evento `cuenta_destino` en el JS del form. Se prefiere `validate()` para
que funcione también en imports y bench execute.

---

## Flujo de uso — dos botones separados

### Botón 1: "Detectar Faltantes" (solo source_type = Ingresos/CFM)

```python
cfm = frappe.get_doc("Configuracion Fiscal Mexico", f"CFM-{company}")

for row in cfm.mapeo_cuentas:
    # Solo filas con cuenta mapeada y validada
    if row.estado_validacion != "Válido" or not row.cuenta_impuesto:
        continue

    # TODOS los roles — sin exclusiones automáticas; el usuario decide qué omitir
    # El usuario decide qué reclasificar mediante cuenta_destino y estado

    # ¿Ya existe en MRFPE externo?
    mrfpe_externo = frappe.db.get_value(
        "Mapeo Reclasificacion Fiscal Payment Entry",
        {"company": company, "tipo_operacion": "Cobro",
         "cuenta_origen": row.cuenta_impuesto, "activo": 1},
        "name"
    )

    # ¿Ya existe regla en este CRFM?
    regla_existente = _buscar_regla_existente(crfm, row.cuenta_impuesto, "Cobro")

    if regla_existente:
        continue  # ya procesada

    estado = "Ya existe externo" if mrfpe_externo else "Pendiente cuenta destino"
    mrfpe_ref = mrfpe_externo if mrfpe_externo else None

    # Nota contextual automática
    nota = ""
    if mrfpe_externo:
        nota = "MRFPE externo detectado — funciona correctamente sin intervención."
    elif row.es_retencion:
        nota = "Retención detectada — revisar mecánica contable antes de generar MRFPE."
    elif row.rol_fiscal in ("IVA Exento", "IVA por Pagar (0% exportación)"):
        nota = "IVA 0% / Exento — puede marcarse como Omitido si no hay cuenta destino."

    crfm.append("reglas", {
        "source_type": "Ingresos / CFM",
        "tipo_operacion": "Cobro",
        "rol_fiscal": row.rol_fiscal,
        "cuenta_origen": row.cuenta_impuesto,
        "estado_mrfpe": estado,
        "mrfpe_ref": mrfpe_ref,
        "nota": nota,
    })
```

**Resultado visible para el usuario:**

```
| Rol Fiscal        | Cuenta Origen           | Cuenta Destino   | Estado                    |
| IVA Nacional      | 2101-IVA Cobrable       | [editable]       | Pendiente cuenta destino  |
| IVA Frontera      | 2102-IVA Cobr.Frontera  | [editable]       | Pendiente cuenta destino  |
| IVA 0% Exportac.  | 2103-IVA Export         | [editable]       | Pendiente cuenta destino  |
| IVA Exento        | 2104-IVA Exento         | [editable]       | Pendiente cuenta destino  |
| Ret. IVA Honor.   | 2201-IVA Ret.Hon        | [editable]       | Pendiente cuenta destino  |
| IVA Nacional      | 2101-IVA Cobrable       | 2105-IVA Cobrado | Ya existe externo         |
```

El usuario llena `cuenta_destino` en las filas que corresponde.
Para retenciones, puede marcar `Omitido` si decide no reclasificar en Fase 1.

### Botón 2: "Generar MRFPE"

```python
creados = []
ya_existian = []
pendientes = []

for regla in crfm.reglas:
    if regla.estado_mrfpe in ("Ya existe externo", "Generado", "Omitido"):
        continue

    if not regla.cuenta_destino:
        pendientes.append(regla.cuenta_origen)
        continue

    # Idempotencia
    if frappe.db.exists("Mapeo Reclasificacion Fiscal Payment Entry", {
        "company": company,
        "tipo_operacion": regla.tipo_operacion,
        "cuenta_origen": regla.cuenta_origen,
        "activo": 1,
    }):
        regla.estado_mrfpe = "Ya existe externo"
        ya_existian.append(regla.cuenta_origen)
        continue

    mrfpe = frappe.new_doc("Mapeo Reclasificacion Fiscal Payment Entry")
    mrfpe.company = company
    mrfpe.tipo_operacion = regla.tipo_operacion
    mrfpe.cuenta_origen = regla.cuenta_origen
    mrfpe.cuenta_destino = regla.cuenta_destino
    mrfpe.activo = 1
    mrfpe.insert(ignore_permissions=True)

    regla.mrfpe_ref = mrfpe.name
    regla.estado_mrfpe = "Generado"
    creados.append(mrfpe.name)

# Reporte final al usuario
frappe.msgprint(f"Creados: {len(creados)} | Ya existían: {len(ya_existian)} | Pendientes: {len(pendientes)}")
```

---

## Fase 0 — Fix inmediato (PR independiente)

Antes de implementar CRFM, este cambio elimina el silencio contable:

```python
# payment_entry_reclasificacion.py
if not cuenta_destino:
    frappe.log_error(
        f"Sin mapeo de reclasificación: {company} / {tipo_operacion} / "
        f"{tax.account_head} en PE {doc.name}. Impuesto no reclasificado.",
        "Reclasificación Fiscal Incompleta"
    )
    continue
```

Riesgo: mínimo. No cambia comportamiento del GL.

---

## Alcance por fases

### Fase 0 — log_error (PR pequeño, inmediato)
- `payment_entry_reclasificacion.py`: `continue` → `log_error + continue`

### Fase 1 — CRFM para Cobros
- DocType `Configuracion Reclasificacion Fiscal Mexico` + child `Regla Reclasificacion Fiscal`
- Botón "Detectar Faltantes" (solo Cobros, source_type = Ingresos/CFM)
- Botón "Generar MRFPE" (idempotente)
- Modo Manual (sin CFM) funcional
- Retenciones: detectadas, usuario decide (no auto-generación)
- MRFPE existentes: detectados como "Ya existe externo"
- **Cierra issue #112**

### Fase 2 — Adopción de MRFPE manuales (futuro)
- Botón "Adoptar MRFPE existente" — vincula registros externos a CRFM
- Referencia inversa en MRFPE (`crfm_ref`, `managed_by_crfm`) — toca schema MRFPE

### Fase 3 — Pagos/Egresos (futuro, issue separado)
- `source_type = "Egresos / futuro"` se activa
- Nueva fuente de detección para compras/pagos
- Abre issue separado: "Configuración fiscal de egresos/pagos"

---

## Análisis de riesgos

| Riesgo | Nivel | Detalle |
|---|---|---|
| Migración de datos | ✅ Ninguno | DocType nuevo — sin datos históricos |
| MRFPE existente | ✅ Ninguno | No se toca. Instalaciones con MRFPE manual siguen funcionando |
| CFM | ✅ Ninguno | Solo lectura |
| payment_entry_reclasificacion.py | ✅ Mínimo | Solo agrega log_error |
| Fixtures | ⚠️ Bajo | 2 DocTypes nuevos: JSON + hooks.py |
| Permisos | ⚠️ Bajo | System Manager + Accounts Manager (igual que MRFPE) |
| Idempotencia generación | ⚠️ Medio | `frappe.db.exists()` antes de `insert()` — cubierto en pseudocódigo |
| Exclusiones incorrectas de roles | ⚠️ Cubierto | Sin exclusiones automáticas — todos los roles visibles para el usuario |

---

## Archivos a crear (Fase 0 + Fase 1)

### Fase 0 (1 archivo modificado)
```
facturacion_mexico/facturacion_fiscal/services/payment_entry_reclasificacion.py
```

### Fase 1 (nuevos)
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
```

### Fase 1 (modificados)
```
facturacion_mexico/hooks.py  — agregar fixtures para los 2 nuevos doctypes
```

### NO se modifican
```
mapeo_reclasificacion_fiscal_payment_entry.py / .json / .js
configuracion_fiscal_mexico.py / .json / .js
mapeo_cuenta_fiscal_mexico.json
payment_entry_reclasificacion.py (solo Fase 0)
```

---

## Referencias

- Issue #112: https://github.com/luisrms69/facturacion_mexico/issues/112
- `facturacion_mexico/facturacion_fiscal/services/payment_entry_reclasificacion.py`
- `facturacion_mexico/facturacion_fiscal/doctype/mapeo_reclasificacion_fiscal_payment_entry/`
- `facturacion_mexico/facturacion_fiscal/doctype/configuracion_fiscal_mexico/`
- `facturacion_mexico/utils/roles_fiscales.py`
