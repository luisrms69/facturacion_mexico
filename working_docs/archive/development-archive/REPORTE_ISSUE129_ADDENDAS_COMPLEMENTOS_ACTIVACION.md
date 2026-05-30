# Issue #129 — Verificar campos de activación en payload: addendas y complementos
# Reporte de entendimiento y propuesta de solución
# Fecha: 2026-05-12

---

## Entendimiento del problema

### Contexto

El Customer tiene dos campos conceptuales relacionados con addendas:
- `fm_requires_addenda` (Check) — indica si el cliente requiere addenda
- `fm_default_addenda_type` (Link) — tipo de addenda por defecto

El issue pregunta: ¿estos campos tienen efecto real en el CFDI, o son solo decorativos?

### Lo que encontré en el código — análisis exhaustivo

#### Origen de los campos

**Fixtures — CONFIRMADO:** `Customer-fm_requires_addenda` y `Customer-fm_default_addenda_type` están declarados en `fixtures/custom_field.json` y en `hooks.py` en la lista de fixtures exportados. Los campos de `Sales Invoice-fm_addenda_*` (status, xml, errors, required, type, etc.) también están en fixtures.

Esto significa que los campos **existen en la BD de cualquier instalación** — están correctamente versionados y se despliegan con `bench migrate`.

**Hooks.py — doc_events:** El `Customer` tiene registrado solo:
```python
"Customer": {
    "validate": "...customer_validate.validate_rfc_format",
    "before_save": "...customer_validate.validate_rfc_format",
    "after_insert": "...customer_validate.schedule_rfc_validation",
}
```
**No hay ningún hook de addenda registrado para Customer.**

#### Cadena completa del flujo de addendas

La investigación reveló que el sistema de addendas **SÍ tiene un flujo completo**, pero está desconectado de `hooks.py`:

**1. Detección automática (`addenda_auto_detector.py`)**
- `customer_after_insert()` — función que SE AUTO-APLICA si detecta con >80% de confianza
- Lee `fm_requires_addenda` del Customer
- Si detecta, setea `doc.fm_requires_addenda = 1` y `doc.fm_addenda_type`
- **PERO:** esta función NO está registrada como hook en `hooks.py` → **NUNCA SE EJECUTA**

**2. Propagación a Sales Invoice (`hooks_handlers/sales_invoice_validate.py`)**
- Lee `customer.fm_requires_addenda` → si es 1, pone `fm_addenda_required=1` en la SI
- Maneja estado `fm_addenda_status` (Pendiente, Generando, Completada, Error)
- **PERO:** este handler tampoco aparece en `hooks.py` → **NO ESTÁ CONECTADO**

**3. Generación post-submit (`hooks_handlers/sales_invoice_submit.py`)**
- `sales_invoice_on_submit()` — genera addenda en background job después del submit
- Si `fm_addenda_required=1` y `auto_apply=True`, encola la generación
- `generate_addenda_background()` → `generate_addenda_xml()` → genera XML
- `insert_addenda_in_cfdi()` → usa `CFDIParser` para insertar en el XML del CFDI
- **PERO:** `sales_invoice_on_submit` NO está registrado en `hooks.py` → **NUNCA SE EJECUTA**

#### Resumen: ¿qué está conectado y qué no?

| Componente | ¿En hooks.py? | ¿Funciona? |
|---|---|---|
| `Customer.fm_requires_addenda` fixture | ✅ Sí | Campo existe en BD |
| `Customer.fm_default_addenda_type` fixture | ✅ Sí | Campo existe en BD |
| `addenda_auto_detector.customer_after_insert` | ❌ NO | NUNCA se ejecuta |
| `sales_invoice_validate` (propagación) | ❌ NO | NUNCA se ejecuta |
| `sales_invoice_on_submit` (generación post-timbrado) | ❌ NO | NUNCA se ejecuta |
| Módulo `addendas/` completo | Código existe | Funciones aisladas, invocables manualmente vía API |

#### Conclusión definitiva sobre addendas

Los campos `fm_requires_addenda` y `fm_default_addenda_type` son **decorativos en la práctica actual**. El código de addendas (detección, propagación, generación post-timbrado) existe y está escrito, pero **ningún hook está registrado en `hooks.py`**, por lo que el flujo completo nunca se activa automáticamente. La addenda **no llega al CFDI final** en ningún escenario normal de operación.

### Conclusión sobre complementos/PPD

No existe un campo `fm_usa_complemento` o similar en Customer. El flujo de complementos se determina en runtime:
- `fm_require_complement` en Payment Entry — calculado por `check_ppd_requirement()` cuando la SI tiene `fm_es_ppd=1` y FFM timbrada
- No hay propiedad declarativa a nivel de Customer que diga "este cliente opera PPD"

---

## Decisión de arquitectura — DEFINITIVA (v3, revisada con ChatGPT)

**Pre-timbrado como flujo principal. Post-timbrado como capacidad excepcional/manual. Motor común AddendaService neutral.**

La addenda NO forma parte de la cadena original ni del sello fiscal SAT. Técnicamente puede agregarse antes o después, pero el flujo principal es antes — enviando `addenda` y `namespaces` en el payload de `create_invoice` de FacturAPI.

---

## Motor común: AddendaService

El componente central debe ser un servicio neutral, **no acoplado a FacturAPI ni a post-proceso**. Sus responsabilidades son:

```
AddendaService
  resolve()              → determinar si la SI requiere addenda
  validate_required_data() → validar datos obligatorios por tipo de addenda
  render()               → construir y renderizar XML de addenda
  → devolver: addenda_xml + namespaces + metadata + errores claros
```

El `AddendaGenerator` existente puede ser la base, pero debe revisarse antes de activar. **No asumir que está listo.**

---

## Fuente de verdad: Sales Invoice vs FFM

| Donde | Qué guarda |
|---|---|
| **Sales Invoice** | Configuración operativa: `fm_addenda_required`, `fm_addenda_type`, `fm_addenda_status`, `fm_addenda_error` |
| **FFM** | Resultado fiscal/timbrado: `fm_addenda_applied_mode`, `fm_addenda_xml`, `fm_cfdi_xml` |

AddendaService recibe SI y/o FFM, pero resuelve la configuración desde SI. No duplicar configuración sin regla clara.

### Regla de congelamiento

La propagación Customer → SI corre en `Sales Invoice.validate`. En Frappe, docs submitted son read-only y `validate` no corre sobre ellos — el congelamiento es parcialmente automático.

El riesgo real: si el operador edita el draft varias veces y el hook siempre sobrescribe desde Customer, pierde un override manual que haya hecho.

**Regla de propagación:**
- Propagar `fm_requires_addenda` y `fm_default_addenda_type` desde Customer → SI **solo si el campo en SI está vacío** (no sobrescribir override manual)
- Después de submit/timbrado: configuración de addenda congelada — cambios en Customer no afectan SIs existentes
- El override manual en SI draft es válido y debe respetarse

---

## Definición de `fm_cfdi_xml` — regla permanente

```
fm_cfdi_xml = XML oficial descargado desde FacturAPI después del timbrado.
Puede contener <Addenda> si fue enviada pre-timbrado.
Nunca se altera después de guardado.
```

En pre-timbrado: FacturAPI devuelve XML con addenda integrada → se guarda en `fm_cfdi_xml` tal cual.
En post-timbrado manual: `fm_cfdi_xml` NO se modifica → se genera XML entregable separado.

Para post-timbrado: el XML entregable con addenda se guarda en `fm_cfdi_xml_deliverable` (campo nuevo a definir en Fase 6) o como attachment específico con auditoría (usuario, fecha, hash).

---

## Política de fallo — tabla

| Caso | Acción |
|---|---|
| `fm_addenda_required = 1` y no hay tipo configurado | Bloquear timbrado |
| Tipo configurado pero faltan datos obligatorios | Bloquear timbrado |
| Tipo configurado pero template no existe | Bloquear timbrado |
| Addenda opcional y falla generación | No bloquear, registrar advertencia |
| FacturAPI rechaza addenda | Bloquear y guardar error en `fm_addenda_error` |
| XML final timbrado no contiene `<Addenda>` | Marcar error crítico en `fm_addenda_status` |

---

## Flujo A — Pre-timbrado (principal)

```
Sales Invoice.validate  [solo propagación — nunca bloquea guardado]
  → AddendaService.resolve()          [¿requiere addenda?]
  → propagar flags a SI               [no generar XML, no validar datos]

_prepare_facturapi_data()  [construye payload]
  → AddendaService.validate_required_data()   [aquí sí bloquea]
  → si falta dato → frappe.throw("Addenda requerida pero faltan: ...")
  → AddendaService.render()
  → payload["addenda"] = addenda_xml
  → payload["namespaces"] = {...}

FacturAPI create_invoice()
  → si falla → guardar error, NO marcar applied_mode

Post-timbrado exitoso  [en handler de respuesta]
  → XML descargado
  → verificar que contiene <Addenda>
  → fm_cfdi_xml = XML oficial de FacturAPI (con Addenda integrada)
  → fm_addenda_applied_mode = "pre_stamp"   [solo aquí, después de verificar]
  → fm_addenda_status = "Completada"
```

**Regla crítica de implementación:** `_prepare_facturapi_data()` solo construye payload. El estado `fm_addenda_applied_mode` se marca únicamente en el handler de respuesta exitosa, después de descargar y verificar el XML. Si FacturAPI falla, se guarda el error pero el estado no se actualiza.

FacturAPI acepta `addenda: string<xml>` y `namespaces` en `create_invoice`. También soporta modo draft: `create draft → edit draft con addenda → stamp draft` — eso sigue siendo pre-timbrado, no post-timbrado.

---

## Flujo B — Post-timbrado (excepcional/manual)

Para casos donde el cliente pide addenda DESPUÉS de recibir la factura (orden de compra, folio de recepción, referencia que no existían al timbrar).

```
FFM/SI ya timbrada
→ Botón explícito: "Generar/Actualizar Addenda"
→ Verificar: ¿fm_cfdi_xml ya contiene <Addenda>?
   → si sí → solicitar confirmación explícita de reemplazo
→ AddendaService.validate_required_data()
→ AddendaService.render()
→ CfdiAddendaInjector.insert() sobre copia de fm_cfdi_xml
→ XML entregable guardado (campo fm_cfdi_xml_deliverable o attachment — decisión Fase 6)
→ Auditoría: usuario, fecha, modo, hash XML resultante
→ fm_addenda_applied_mode = "post_stamp"
```

**Restricciones:**
- NO automático — siempre acción explícita del operador
- NO modifica `fm_cfdi_xml` (fiscal original intocable)
- NO retimbra ni cancela
- NO aplica a Complementos de Pago (datos fiscales propios)
- NO corre masivamente sin control
- Si ya existe addenda pre-timbrada: no reemplazar sin confirmación explícita

---

## Compatibilidad con implementaciones futuras

| Funcionalidad futura | Compatibilidad |
|---|---|
| Complementos de Pago | Ya implementados, flujo completamente separado |
| Carta Porte | Como complemento en payload, mismo patrón pre-timbrado |
| CFDI Global | Flujo propio, no se mezcla |
| Draft → stamp mode | Pre-timbrado, sin cambio de arquitectura |
| Post-timbrado manual | Flujo B contemplado |

**Múltiples addendas — fuera de alcance v0.2.** Implica combinar XML de varios proveedores, manejar namespaces duplicados, conflictos de schemas y orden de nodos. No prometer en esta versión.

---

## Plan de implementación por fases — ORDEN CORREGIDO

### Fase 1 — Validar FacturAPI en sandbox (1 sesión)
Confirmar:
- `create_invoice` acepta `addenda: string<xml>` y `namespaces`
- Formato exacto de namespaces para addenda propia
- XML descargado incluye `<Addenda>` correctamente
- Comportamiento del PDF con addenda
- Qué pasa si la addenda tiene namespace propio

### Fase 2 — Diseñar AddendaService neutral (1 sesión)
- Revisar `AddendaGenerator` / `generic_addenda_generator.py` — puede servir como base
- Implementar interfaz: `resolve() → validate_required_data() → render()`
- Revisar `fm_default_addenda_type` vs `fm_addenda_type` (probable inconsistencia)
- Revisar `CFDIParser`, manejo namespaces CFDI 4.0 para Flujo B futuro

### Fase 3 — Propagación Customer → Sales Invoice (antes del payload)
Registrar hook mínimo `Sales Invoice.validate`:
- Leer `customer.fm_requires_addenda` → copiar a `fm_addenda_required` en SI **solo si está vacío**
- Leer `customer.fm_default_addenda_type` → copiar a `fm_addenda_type` en SI **solo si está vacío**
- Solo propagación de flags — no generar XML, no validar datos, **no bloquear guardado de draft**
- No activar `sales_invoice_validate.py` legacy sin revisar; crear handler mínimo para evitar side effects viejos

### Fase 4 — Pre-timbrado en payload (1-2 sesiones)
- `_prepare_facturapi_data()`: si `fm_addenda_required = 1` → validate_required_data() → render → incluir en payload
- validate_required_data() aquí sí hace `frappe.throw()` — bloquea timbrado, no guardado de draft
- FacturAPI devuelve XML con addenda integrada
- En handler de respuesta exitosa: descargar XML → verificar `<Addenda>` presente → marcar `fm_addenda_applied_mode = "pre_stamp"` y `fm_addenda_status = "Completada"`
- Si FacturAPI falla: guardar error, no marcar applied_mode
- Validar XML descargado, attachments y PDF

### Fase 5 — Persistencia, descarga y attachments
- Asegurar que `fm_cfdi_xml` guarda el XML oficial sin alterar
- Attachments de descarga sirven el XML correcto según modo (pre/post stamp)
- Tests de regresión: descarga, cancelación, sustitución siguen funcionando

### Fase 6 — Post-timbrado manual (futuro)
- Decidir entre campo `fm_cfdi_xml_deliverable` vs attachment específico con hash/auditoría
- Para v0.2 con solo pre-timbrado este campo NO es necesario — el XML de FacturAPI ya viene con addenda
- Botón explícito en FFM: "Generar Addenda Post-Timbrado"
- Solo para FFMs timbradas sin `fm_addenda_applied_mode`
- Guardar en fm_cfdi_xml_deliverable o attachment — nunca sobrescribir `fm_cfdi_xml`
- Auditoría obligatoria: usuario, fecha, hash del XML resultante

### Fuera de alcance:
- `Customer.after_insert` auto-detección — no activar
- `Sales Invoice.on_submit` legacy — no activar
- Backfill retroactivo automático
- Múltiples addendas
- Complementos/PPD (flujo propio ya funcional)

---

## Estado del código existente — evaluación revisada

| Componente | Evaluación |
|---|---|
| `AddendaGenerator` / `generic_addenda_generator.py` | Revisar antes de usar — puede tener lógica desactualizada |
| `CFDIParser` / `insert_addenda_in_cfdi()` | Útil para Flujo B post-timbrado — NO activar sin test |
| `hooks_handlers/sales_invoice_submit.py` | Código legacy post-timbrado — **NO activar**; revisar si alguna lógica reutilizable |
| `hooks_handlers/sales_invoice_validate.py` | Puede reutilizarse en Fase 3 solo si queda mínimo y sin side effects viejos |
| `addenda_auto_detector.py` | Dejar desconectado — no activar en v0.2 |
| Campos `fm_addenda_*` en fixtures | Bien definidos — usar tal cual |

---

## Clasificación final

```
Tipo:      Feature incompleto — integración pendiente con arquitectura base existente
Prioridad: v0.2
Riesgo:    Medio (pre-timbrado) / Medio-alto (post-timbrado manual)
Estrategia: 6 fases; propagación antes que payload; fuente de verdad SI→FFM clara
```

**No es "solo conectar hooks". El código legacy puede tener estado/side effects viejos. Revisar antes de activar.**

---

## Referencias

- Issue #129: https://github.com/luisrms69/facturacion_mexico/issues/129
- `facturacion_mexico/addendas/` — módulo completo de addendas
- `facturacion_mexico/facturacion_fiscal/timbrado_api.py` — `_prepare_facturapi_data()`
- `facturacion_mexico/addendas/addenda_auto_detector.py` — detección automática (desconectada)
- `facturacion_mexico/addendas/api.py` — API de addendas
- PR #126: fix(reclasificacion) — complementos PPD ya validados
