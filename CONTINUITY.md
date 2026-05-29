# CONTINUITY.md — facturacion_mexico

**Fecha:** 2026-05-28
**Rama activa:** `feature/cfdi-recibidos-fase3-pi`
**Tarea actual:** Motor de resolución de items commiteado — próximo paso: PR o hito F.3 (build PI)

---

## Recuperación rápida

Estoy trabajando en:
Pipeline de ingesta CFDI Recibidos (XML → PI Draft). El motor guiado de resolución de items
quedó commiteado. El flujo completo Upload → proveedor → departamento → items → Generar PI
está funcional en GUI.

Plan que estoy siguiendo:
No hay doc externo de plan activo. Todo el contexto está en esta sesión.

Objetivo inmediato:
Decidir entre abrir PR de esta rama o continuar con hito F.3 (mejoras al build_purchase_invoice).

Criterio de avance:
Usuario decide si PR o continuar en la misma rama.

---

## Estado actual

### Ya cerrado
- DocType `Regla Item CFDI Recibido` + `concept_text_normalizer.py` + `item_resolution_engine.py`
- 5 endpoints: get_item_resolution_options, assign_item_to_concepto,
  create_specific/grouping_item_from_concepto, assign_generic_item_to_concepto
- Dialog "Resolver Items pendientes": chips con item_name, sección Sugerencias con estilo
- Auto-código item: `{SLUG}-{NNN}` desde primera palabra del grupo
- Auto-creación de `Regla Item CFDI Recibido` al asignar item con no_identificacion
- Pipeline upload encadenado: auto-proveedor → dialog dept → clasificar items → form CFDI
- Botón "Cargar XML" standalone; grupo "Flujo Manual"; botón "Marcar No Procesar"
- Campo sat_product_key en Regla Item → Link a SAT Producto Servicio
- 44 tests pasando (20 normalizer + 24 motor)
- bench migrate ejecutado en esta sesión

### En progreso
- Nada

### Pendiente inmediato
1. Decidir: PR de la rama actual vs continuar con hito F.3

### No repetir
- No hacer bench migrate de nuevo sin necesidad
- No proponer commits sin que el usuario lo solicite
- No asignar GASTO-* genéricos automáticamente
- No incluir docs/development/REPORTE_*.md en commits
- No incluir one_offs/ en commits

---

## Decisiones vigentes
- Auto-asignación en upload: SOLO nivel 5 (no_identificacion == item_code existente)
- Regla auto-aprendida: RFC + keywords=no_identificacion → item_code (priority 5)
- Keywords en motor: match contra `description` OR `no_identificacion`
- sat_product_key en Regla Item: Link a SAT Producto Servicio (no Data)
- Chips en resolver dialog muestran item_name; item_code en tooltip
- "Cargar XML" standalone fuera del grupo "Flujo Manual"

---

## Archivos relevantes ahora

### Leer primero
- `facturacion_mexico/cfdi_recibidos/api.py`
- `facturacion_mexico/cfdi_recibidos/doctype/cfdi_recibido/cfdi_recibido.js`
- `facturacion_mexico/cfdi_recibidos/doctype/cfdi_recibido/cfdi_recibido_list.js`

### Probablemente editar (próxima sesión)
- `facturacion_mexico/cfdi_recibidos/services/purchase_invoice_builder.py` — hito F.3

### No tocar
- `facturacion_mexico/one_offs/` — nunca commitear
- `docs/development/REPORTE_*.md` — no commitear

---

## Riesgos / cuidados
- `purchase_invoice_builder.py` marcado WIP desde sesiones anteriores — revisar antes de tocar
- Fixtures de `Regla Item CFDI Recibido` no exportados explícitamente (DocType nuevo en JSON)
