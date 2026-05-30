# Arquitectura E4 (Rediseño): IEPS "Cuota" con `On Item Quantity`

**Proyecto:** Facturación México
**Fecha:** 2025-10-27
**Versión:** E4 - Rediseño completo sistema cuotas IEPS
**Estado:** 📐 DISEÑO ARQUITECTÓNICO (sin código)

---

## CONTEXTO DECISIÓN ARQUITECTÓNICA

### Situación Actual
- **FIX-V1** funciona en draft pero falla en submit (cuotas desaparecen, -$234.84)
- **charge_type="Actual"** no es estable en ciclo de vida Sales Invoice
- **ITT conflicts** causan comportamiento impredecible
- **Hooks tardíos** (on_submit) son frágiles y no confiables

### Decisión Estratégica
- **Rediseño completo** adoptando `charge_type="On Item Quantity"`
- **Sin producción activa** - Estamos diseñando desde cero
- **Sin feature flags** - Una sola ruta, limpia y determinista
- **Legacy inmediato** - Eliminar tras validación DEV (no hay espera prod)

---

## 0) LINEAMIENTOS DUROS (NO NEGOCIABLES)

### 1. Sin feature flags ni toggles
- ❌ No habrá rutas paralelas ni switches en tiempo de ejecución
- ✅ Una sola implementación: `On Item Quantity`
- ✅ Código limpio, predecible, mantenible

### 2. Legacy fuera del camino
- 🗑️ Plantillas/flows "Actual" → **comentados** y marcados como **deprecados** inmediatamente
- ⏱️ Tras validar resultados en DEV → **se eliminan** definitivamente
- 📦 No hay "2 semanas en prod" porque **no hay producción activa**

### 3. Reversa solo por operaciones de plataforma
- 💾 Si algo sale mal: **restore de backup** y/o **revert de commit**
- ❌ No se introduce lógica de convivencia en código
- ✅ Backups obligatorios antes de cada cambio mayor

---

## 1) DECISIONES DE ARQUITECTURA

### Fuente única de cuotas
- ✅ **Solo STCT** con filas `charge_type = On Item Quantity`
- ❌ **ITT sin cuotas:** Queda **prohibido** modelar cuotas en ITT (validador duro)
- 📋 Single source of truth elimina conflictos y comportamiento impredecible

### UOM canónica
- 📏 La del *Doctype Cuotas IEPS*: campo `uom_base` (p.ej., litro, cigarro)
- 🔄 La factura puede usar otras UOM; se convierten por ítem usando factores del Item
- ⚠️ Si falta conversión → **bloqueo duro** al validar

### Cascada de IVA sobre cuota
- 📊 Fila separada por cada cuota con `On Previous Row Amount` apuntando a su fila cuota
- ✅ Comportamiento nativo ERPNext, estable en submit/amend
- 🔗 Relación explícita: IVA → Cuota (trazabilidad)

### Sin mutaciones tardías
- 🚫 No se toque nada en `before_submit/on_submit`
- ✅ Todo debe cuadrar **antes** de `validate`
- 🎯 Objetivo: comportamiento idéntico Draft ↔ Submit

---

## 2) CONTRATOS DE DATOS

### Cuotas IEPS (SSOT)
**Ubicación:** Doctype `Cuotas IEPS` (tabla maestra)

**Campos críticos:**
- `monto_cuota` (Decimal): Importe unitario de la cuota
- `uom_base` (Link UOM): UOM canónica para esta cuota
- `vigencia_inicio` / `vigencia_fin` (Date): Período de aplicación
- `categoria_ieps` (Select): Tipo de producto IEPS

**Validaciones:**
- ✅ `monto_cuota > 0`
- ✅ `uom_base` debe existir en UOM master
- ✅ Solo una cuota activa por categoría + fecha

### Mapeo de cuentas
**Ubicación:** Sales Taxes and Charges Template (STCT)

**Campos críticos:**
- `account_head` (Link Account): Cuenta contable IEPS
- `rol_fiscal` (Select): Uno de los roles IEPS_* definidos
- `tipo_factor` (Data): "Cuota" (para envío PAC)
- `charge_type` (Select): **"On Item Quantity"** (obligatorio)

**Validaciones:**
- ✅ `rol_fiscal` debe ser de familia IEPS_*
- ✅ `tipo_factor = "Cuota"` si `charge_type = "On Item Quantity"`
- ✅ `account_head` debe ser cuenta de pasivo/impuesto

### Item (por cada producto con cuota)
**Ubicación:** Doctype `Item`

**Requisitos:**
- 🔗 **Ruta de conversión** desde UOM de venta → **UOM canónica** (determinística)
- 📦 UOM Conversions configuradas en Item
- ⚠️ Si falta conversión para ítem con cuota → **bloqueo duro** al validar

**Ejemplo conversión:**
```
Item: Cerveza 355ml
- UOM venta: Caja (24 piezas)
- UOM canónica IEPS: Litro
- Conversión: 1 Caja = 24 piezas × 0.355 L = 8.52 L
```

---

## 3) REDISEÑO DE STCT (PLANTILLAS)

### Estructura filas por plantilla (orden obligatorio)

**Orden de filas:**
1. Todas las **cuotas IEPS** como `On Item Quantity` (una por tipo de IEPS aplicable)
2. Justo después, su **IVA sobre cuota** con `On Previous Row Amount` apuntando a la fila cuota anterior
3. Retenciones/IVA base adicionales según aplique

**Ejemplo plantilla tabaco:**
```
Fila 1: IEPS Cuota Tabaco
  - charge_type: "On Item Quantity"
  - rate: 0.00 (se calcula dinámicamente)
  - account_head: IEPS Tabaco por Pagar
  - rol_fiscal: IEPS_CUOTA_TABACO

Fila 2: IVA sobre IEPS Cuota Tabaco
  - charge_type: "On Previous Row Amount"
  - row_id: 1 (referencia a fila anterior)
  - rate: 16.00
  - account_head: IVA Trasladado
  - rol_fiscal: IVA_TRASLADO_16
```

### Reglas de diseño
- ✅ Cada fila "IVA sobre cuota" referencia **la cuota correspondiente** (no una genérica)
- ✅ Nombres y descripciones claros para auditoría
- ❌ **No** incluir filas con `charge_type = "Actual"` (legacy deprecado)
- ✅ Usar `item_wise_tax_detail` para distribución por ítem

---

## 4) CONVERSIÓN DE UOM (NÚCLEO FUNCIONAL)

### Cálculo conceptual

**Por ítem:**
```python
# 1. Obtener cuota unitaria canónica (desde Cuotas IEPS)
cuota_unitaria = obtener_cuota_ieps(categoria, fecha)  # ej: $0.85/litro

# 2. Obtener UOM canónica (desde Cuotas IEPS)
uom_canonica = cuota_ieps.uom_base  # ej: "Litro"

# 3. Convertir cantidad facturada a UOM canónica
qty_canonica = convertir_uom(
    qty_facturada=item.qty,          # ej: 2 cajas
    uom_origen=item.uom,             # ej: "Caja"
    uom_destino=uom_canonica,        # ej: "Litro"
    conversion_factors=item.uoms     # factores del Item
)  # resultado: 17.04 litros

# 4. Calcular IEPS ítem
ieps_item = cuota_unitaria × qty_canonica
# resultado: $0.85 × 17.04 = $14.48
```

**Por documento:**
```python
total_ieps = sum(ieps_item for item in doc.items)
```

### Distribución
- ✅ `item_wise_tax_detail` debe reflejar la asignación por ítem (nativo ERPNext)
- ✅ ERPNext maneja distribución automáticamente con `On Item Quantity`
- ✅ Cada ítem tiene su importe IEPS independiente

### Fraccionarios
- ✅ Se aceptan cantidades decimales (p.ej., 1.5 cajas → 12.78 litros)
- ✅ Usar precisión del Sales Invoice (`doc.precision("qty")`)
- ⚠️ Documentar tolerancias de redondeo

---

## 5) CICLO DE VIDA (SIN HACKS EN SUBMIT)

### before_validate

**Validaciones obligatorias:**
1. **Incompatibilidad ITT:** Si hay cuotas en ITT → **error** y no permite guardar
2. **Ruta de conversión:** Verificar conversión UOM para cada ítem con cuota → si falta: **error**
3. **Semántica consistente:** Asegurar que las filas `On Item Quantity` tengan estructura correcta

**Ejemplo validación ITT:**
```python
def validar_itt_sin_cuotas(doc):
    """Validador duro: ITT no puede tener cuotas."""
    for item in doc.items:
        if not item.item_tax_template:
            continue
        itt = frappe.get_doc("Item Tax Template", item.item_tax_template)
        for tax in itt.taxes:
            if tiene_cuota_ieps(tax.tax_type):
                frappe.throw(
                    f"Item {item.item_code}: ITT '{itt.name}' tiene cuotas IEPS. "
                    "Las cuotas deben estar solo en STCT.",
                    title="Error Configuración IEPS"
                )
```

### validate (ERPNext core)

**Comportamiento esperado:**
- ✅ ERPNext calcula de forma nativa con `On Item Quantity`
- ✅ **Objetivo:** Aquí ya no se requiera corrección manual
- ✅ `doc.calculate_taxes_and_totals()` funciona correctamente
- ✅ Todos los totales cuadran

### save / submit / cancel / amend

**Comportamiento esperado:**
- 🚫 **Sin mutaciones** en hooks tardíos (`before_submit`, `on_submit`)
- ✅ En **Amend** se reasigna la misma plantilla STCT
- ✅ Se espera comportamiento idéntico Draft ↔ Submit
- ✅ Cuotas permanecen como `On Item Quantity` en todos los estados

---

## 6) VERIFICACIÓN VS PAC (CRITERIOS)

### Dataset de referencia
**Ubicación:** `/home/erpnext/frappe-bench/apps/facturacion_mexico/docs/development/REPORTE_COMPARACION_SI_TEST_VS_PAC.md`

**Contenido:**
- Sales Invoices de prueba con cuotas IEPS
- Respuestas PAC esperadas
- Diferencias documentadas

### Criterios de aceptación

#### 1. Draft = Submit (sin regresión)
- ✅ `grand_total` idéntico en draft y submit
- ✅ `total_taxes_and_charges` idéntico en draft y submit
- ✅ Por ítem: `item_wise_tax_detail` consistente

#### 2. Cuotas permanecen estables
- ✅ `charge_type = "On Item Quantity"` después del submit
- ❌ No cambiar a "Actual" o "On Net Total"
- ✅ `rate` y `tax_amount` sin mutaciones

#### 3. IVA sobre cuota en cascada correcto
- ✅ Filas IVA apuntan correctamente a su cuota (`row_id`)
- ✅ Base IVA = `tax_amount` de la fila cuota
- ✅ Cálculo: `iva_cuota = base_cuota × 0.16`

#### 4. Diferencia vs PAC ≤ $0.05 MXN
- ✅ Por documento: `|grand_total_si - total_pac| ≤ 0.05`
- ⚠️ Tolerancia legal de redondeo
- 📊 Reporte comparativo debe documentar diferencias

#### 5. Reporte comparativo ítem a ítem
**Columnas requeridas:**
- Item Code
- Qty (UOM venta)
- Qty canónica (UOM base)
- Base imponible
- Cuota IEPS
- IVA sobre cuota
- Total ítem
- Diferencia vs PAC

---

## 7) ENVÍO AL PAC (ADAPTACIONES CONCEPTUALES)

### TipoFactor = "Cuota"
- 📋 Campo XML: `<cfdi:Traslado TipoFactor="Cuota">`
- ✅ Identifica impuestos por unidad (no porcentaje)
- 🔗 Mapping desde `tipo_factor` del tax row

### Base (por ítem)
**Cálculo:**
```python
# Para cada ítem con cuota IEPS
base_pac = qty_canonica × valor_unitario_cuota

# Ejemplo:
# qty_canonica = 17.04 litros
# valor_unitario_cuota = $0.85/litro
# base_pac = 17.04 × 0.85 = $14.48
```

**Alternativa (según requerimiento PAC):**
```python
# Algunos PACs requieren cantidad como "base"
base_pac = qty_canonica  # 17.04
tasa_cuota = valor_unitario_cuota  # $0.85
```

### IVA sobre cuota
- 📋 Traslado independiente con **base = importe de la cuota**
- ✅ Por ítem/total según esquema actual
- 🔗 Alineado con `item_wise_tax_detail`

**Ejemplo XML:**
```xml
<cfdi:Traslado Base="14.48" Impuesto="002" TipoFactor="Cuota"
               TasaOCuota="0.85" Importe="14.48"/>
<cfdi:Traslado Base="14.48" Impuesto="002" TipoFactor="Tasa"
               TasaOCuota="0.16" Importe="2.32"/>
```

### Trazabilidad
- ✅ Mantener granularidad por ítem
- ✅ Alineada con `item_wise_tax_detail`
- ✅ Reporte de auditoría debe mostrar distribución ítem a ítem

---

## 8) VALIDACIONES Y GUARDAS

### Bloqueos duros (hard errors)

#### 1. Detectar cuotas en ITT
```python
Trigger: before_validate
Condición: Item Tax Template con rol_fiscal IEPS_CUOTA_*
Acción: frappe.throw() - no permite guardar
Mensaje: "Item {code}: ITT '{template}' contiene cuotas IEPS.
         Las cuotas deben estar solo en STCT."
```

#### 2. Falta de conversión UOM canónica
```python
Trigger: before_validate
Condición: Item con cuota IEPS pero sin conversión a uom_base
Acción: frappe.throw() - no permite guardar
Mensaje: "Item {code}: Falta conversión de {uom_venta} a {uom_canonica}.
         Configure UOM Conversion en el Item."
```

### Advertencias suaves (soft warnings)

#### 1. Multipaso de UOM
```python
Trigger: before_validate
Condición: Conversión requiere >2 pasos (caja→botella→ml)
Acción: frappe.msgprint() - log de auditoría
Mensaje: "Item {code}: Conversión UOM multi-paso detectada
         ({pasos} pasos). Revisar factores."
```

#### 2. Montos muy pequeños por ítem
```python
Trigger: validate
Condición: IEPS por ítem < $0.01
Acción: frappe.msgprint() - aviso de posible redondeo
Mensaje: "Item {code}: IEPS muy pequeño (${monto}).
         Posible redondeo significativo."
```

### Precisión

**Configuración:**
- ✅ Usar `doc.precision("qty")` para cantidades
- ✅ Usar `doc.precision("rate")` para tasas
- ✅ Usar `doc.precision("tax_amount")` para importes
- ✅ Documentar tolerancias: ≤ $0.05 MXN por documento

---

## 9) MIGRACIÓN Y OPERACIÓN (SIN CONVIVENCIAS)

### Paso previo obligatorio

#### 1. Auditoría completa
**Inventariar:**
- 📋 STCT con filas `charge_type = "Actual"` (legacy a deprecar)
- 📋 ITT con cuotas IEPS (a corregir antes de implementación)
- 📋 Items sin conversión UOM canónica (a completar)

**Comando auditoría:**
```bash
bench --site facturacion.dev execute \
  "facturacion_mexico.one_offs.auditoria_pre_e4.run"
```

#### 2. Backup obligatorio
```bash
bench --site facturacion.dev backup --with-files \
  --backup-path-suffix="pre-e4-on-item-quantity-$(date +%Y%m%d-%H%M)"
```

### Ejecución

#### Fase 1: Rediseñar STCT
1. Crear nuevos STCT con `On Item Quantity`
2. Comentar filas "Actual" en templates existentes (deprecadas)
3. Actualizar `generador_templates_fiscal.py` para generar solo `On Item Quantity`

#### Fase 2: Validar en DEV
1. Crear Sales Invoices de prueba (usar dataset PAC)
2. Verificar Draft = Submit
3. Comparar vs respuestas PAC (delta ≤ $0.05 MXN)
4. Ejecutar 6 casos imprescindibles (ver sección 10)

#### Fase 3: Eliminar legacy
**Condición:** Testing Gate aprobado (ver siguiente sección)

**Acciones:**
1. Eliminar filas comentadas de STCT legacy
2. Eliminar código deprecated en hooks
3. Eliminar funciones auxiliares obsoletas
4. Actualizar documentación

**NO hay espera de "2 semanas en prod"** porque no existe producción activa.

### Reversa (si se necesita)

**Método único:**
1. **Restore de backup** (DB + files)
2. **Revert de commit** (git revert)

**NO hay:**
- ❌ Rutas paralelas en código
- ❌ Feature flags para activar/desactivar
- ❌ Lógica de convivencia

---

## 10) TESTING GATE (OBLIGATORIO)

### Criterios de aprobación

**Todos los criterios deben cumplirse al 100% antes de eliminar legacy:**

#### 1. Suite unitaria/funcional: 100% verde
- ✅ Tests existentes pasan sin errores
- ✅ Tests nuevos E4 pasan sin errores
- ✅ No flaky tests
- ⏱️ Tiempo ejecución ≤ 5 min

#### 2. Seis casos imprescindibles: OK

##### Caso 1: Draft→Submit con UOM heterogéneas
```
Items: 3-5 productos con UOM distintas
  - Cerveza (Caja 24×355ml)
  - Tequila (Botella 750ml)
  - Cigarros (Cajetilla 20 piezas)
Verificar:
  - Draft totals = Submit totals
  - charge_type permanece "On Item Quantity"
  - item_wise_tax_detail consistente
```

##### Caso 2: Devolución parcial (is_return)
```
Escenario: Nota de crédito 50% de factura original
Verificar:
  - Cuotas IEPS proporcionalmente negativas
  - IVA sobre cuota proporcionalmente negativo
  - Totales cuadran
```

##### Caso 3: Bundles (Product Bundle)
```
Escenario: Paquete mixto (6 cervezas + 2 tequilas)
Verificar:
  - Expansión correcta a ítems componentes
  - Cuotas calculadas por componente
  - Totales cuadran vs componentes individuales
```

##### Caso 4: Descuentos por ítem
```
Escenario: 20% descuento en un ítem con cuota
Verificar:
  - Cuota IEPS NO cambia (basada en qty, no en valor)
  - Descuento aplica solo a base imponible
  - IVA sobre cuota no afectado por descuento
```

##### Caso 5: Stress con 100+ ítems
```
Escenario: Factura con 150 ítems, UOM mixtas
Verificar:
  - Performance: save/submit ≤ 10 segundos
  - Memoria: sin out of memory
  - Totales cuadran
```

##### Caso 6: Comparativa PAC (dataset completo)
```
Dataset: REPORTE_COMPARACION_SI_TEST_VS_PAC.md
Verificar:
  - Cada SI vs respuesta PAC
  - Delta ≤ $0.05 MXN por documento
  - Reporte comparativo sin divergencias inesperadas
```

#### 3. Verificación Draft = Submit
- ✅ Para cada SI de prueba:
  - `grand_total` (draft) = `grand_total` (submit)
  - `total_taxes_and_charges` (draft) = `total_taxes_and_charges` (submit)
  - Cuotas permanecen `On Item Quantity` (no cambian a "Actual")
  - `item_wise_tax_detail` idéntico

#### 4. IVA cascada correcto
- ✅ Cada fila IVA apunta correctamente a su cuota (`row_id`)
- ✅ Base IVA = `tax_amount` de la cuota
- ✅ Cálculo correcto: 16% sobre cuota

#### 5. Delta PAC ≤ $0.05 MXN
- ✅ Por cada documento del dataset
- ✅ Tolerancia legal de redondeo
- 📊 Reporte detallado de diferencias

### Checklist de aprobación

```markdown
- [ ] Suite tests: 100% verde
- [ ] Caso 1 (Draft→Submit UOM heterogéneas): OK
- [ ] Caso 2 (Devolución parcial): OK
- [ ] Caso 3 (Bundles): OK
- [ ] Caso 4 (Descuentos por ítem): OK
- [ ] Caso 5 (Stress 100+ ítems): OK
- [ ] Caso 6 (Comparativa PAC dataset): OK
- [ ] Verificación Draft = Submit: OK
- [ ] IVA cascada correcto: OK
- [ ] Delta PAC ≤ $0.05 MXN: OK
- [ ] Documentación actualizada: OK
- [ ] Code review aprobado: OK
```

**Solo cuando TODO el checklist esté marcado → Proceder a eliminar legacy**

---

## 11) RIESGOS Y CÓMO LOS TRATAMOS

### Riesgo 1: Conflicto STCT vs ITT
**Impacto:** Cuotas duplicadas o comportamiento impredecible
**Mitigación:** **Bloqueo duro** en validación - no permite guardar si ITT tiene cuotas
**Responsable:** Validador en `before_validate`

### Riesgo 2: Conversión UOM faltante
**Impacto:** No se puede calcular cuota, factura bloqueada
**Mitigación:** **Bloqueo duro** - se corrige el catálogo antes de facturar
**Responsable:** Validador en `before_validate` + auditoría pre-implementación

### Riesgo 3: Deltas por redondeo
**Impacto:** Pequeñas diferencias vs PAC (centavos)
**Mitigación:** Documentados; criterio ≤ $0.05 MXN; usar precisión del SI
**Responsable:** Testing Gate + reporte comparativo

### Riesgo 4: Cambios futuros en ERPNext
**Impacto:** Actualización framework puede romper cálculos
**Mitigación:** Estamos en *comportamiento nativo* de `On Item Quantity`; sin hooks tardíos frágiles
**Responsable:** Tests de regresión + monitoreo actualizaciones ERPNext

### Riesgo 5: Performance con muchos ítems
**Impacto:** Save/submit lento con 100+ ítems
**Mitigación:** Caso 5 del Testing Gate (stress test); optimizar conversión UOM si necesario
**Responsable:** Testing performance antes de aprobar

---

## 12) MATRIZ DE UOM (POR CATEGORÍA IEPS)

### Categoría: Bebidas Alcohólicas

**UOM canónica:** Litro

**UOM de venta aceptadas:**
| UOM Venta | Factor Conversión | Ejemplo |
|-----------|-------------------|---------|
| Litro | 1.0 | 1 L = 1 L |
| Mililitro | 0.001 | 1000 mL = 1 L |
| Botella 750ml | 0.75 | 1 Bot = 0.75 L |
| Botella 1L | 1.0 | 1 Bot = 1 L |
| Caja 12×750ml | 9.0 | 1 Caja = 9 L |
| Caja 24×355ml | 8.52 | 1 Caja = 8.52 L |

**Configuración requerida:**
- ✅ UOM Conversion en cada Item
- ✅ Factor determinístico (no cambia)
- ⚠️ Si falta → bloqueo al validar

### Categoría: Tabaco

**UOM canónica:** Cigarro

**UOM de venta aceptadas:**
| UOM Venta | Factor Conversión | Ejemplo |
|-----------|-------------------|---------|
| Cigarro | 1.0 | 1 Cig = 1 Cig |
| Cajetilla (20) | 20.0 | 1 Caj = 20 Cig |
| Cajetilla (14) | 14.0 | 1 Caj = 14 Cig |
| Cartón (10 cajetillas) | 200.0 | 1 Cart = 200 Cig |
| Gramo (tabaco suelto) | (varía) | Definir por producto |

**Configuración requerida:**
- ✅ Especificar cantidad de cigarros por cajetilla
- ✅ UOM Conversion en cada Item
- ⚠️ Tabaco suelto requiere factor específico

### Categoría: Refrescos/Bebidas Azucaradas

**UOM canónica:** Litro

**UOM de venta aceptadas:**
| UOM Venta | Factor Conversión | Ejemplo |
|-----------|-------------------|---------|
| Litro | 1.0 | 1 L = 1 L |
| Mililitro | 0.001 | 1000 mL = 1 L |
| Botella 600ml | 0.6 | 1 Bot = 0.6 L |
| Botella 2L | 2.0 | 1 Bot = 2 L |
| Lata 355ml | 0.355 | 1 Lata = 0.355 L |
| Six-pack 355ml | 2.13 | 1 Pack = 2.13 L |

**Configuración requerida:**
- ✅ UOM Conversion en cada Item
- ✅ Factor exacto según volumen del empaque

### Categoría: Combustibles

**UOM canónica:** Litro

**UOM de venta aceptadas:**
| UOM Venta | Factor Conversión | Ejemplo |
|-----------|-------------------|---------|
| Litro | 1.0 | 1 L = 1 L |
| Galón (US) | 3.785 | 1 Gal = 3.785 L |
| Barril | 158.987 | 1 Barril = 158.987 L |
| Metro cúbico | 1000.0 | 1 m³ = 1000 L |

**Configuración requerida:**
- ✅ UOM Conversion en cada Item
- ⚠️ Verificar densidad si se vende por peso

---

## 13) PLAN DE ELIMINACIÓN DEL LEGACY

### Archivos/Módulos a deprecar inmediatamente

#### 1. STCT con filas "Actual"
**Ubicación:** Fixtures + registros BD
**Acción:**
- Comentar filas `charge_type = "Actual"` con prefijo `# DEPRECATED E4:`
- Agregar campo `deprecated = 1` si se necesita
- Mantener en repo por 1 ciclo de validación

#### 2. Lógica FIX-V1 en hooks
**Ubicación:** `facturacion_mexico/hooks_handlers/sales_invoice_ieps.py` líneas 363-366
**Acción:**
```python
# DEPRECATED E4: FIX-V1 solo funciona en draft, no en submit
# def forzar_recalculo_actual_cuotas(doc):
#     """DEPRECATED: charge_type='Actual' no es estable."""
#     doc.calculate_taxes_and_totals()
```

#### 3. Funciones auxiliares obsoletas
**Ubicación:** `facturacion_mexico/hooks_handlers/sales_invoice_ieps.py`
**Funciones a deprecar:**
- `_si_tiene_ieps_cuotas()` (si solo detecta "Actual")
- `_cargar_stct_taxes_forzado()` (workaround FIX-V2)
- Cualquier función que mute taxes en `on_submit`

### Archivos/Módulos a eliminar tras Testing Gate

**Condición:** TODO el checklist de Testing Gate aprobado

**Acciones:**
1. Eliminar líneas comentadas (deprecated)
2. Eliminar funciones obsoletas
3. Eliminar tests de FIX-V1 (ya no aplican)
4. Actualizar CHANGELOG.md con cambios breaking

**Comando limpieza:**
```bash
# Eliminar líneas DEPRECATED E4
find facturacion_mexico -name "*.py" -exec sed -i '/DEPRECATED E4/d' {} \;

# Commit de limpieza
git add .
git commit -m "chore(e4): eliminar código legacy charge_type='Actual'"
```

### Documentos a actualizar

#### 1. CLAUDE.md
- Actualizar sección RE-004 (IEPS Cuotas)
- Documentar nuevo flujo `On Item Quantity`
- Eliminar referencias a FIX-V1/V2

#### 2. CHANGELOG.md
```markdown
## [Unreleased]

### Changed
- **BREAKING:** Sistema cuotas IEPS rediseñado con `charge_type="On Item Quantity"`
- **BREAKING:** Plantillas STCT migradas a nuevo formato
- **BREAKING:** ITT no puede tener cuotas IEPS (validador duro)

### Removed
- Soporte para `charge_type="Actual"` en cuotas IEPS
- FIX-V1 workaround (doc.calculate_taxes_and_totals en hooks)
- FIX-V2 workaround (cargar STCT forzado)

### Fixed
- Cuotas IEPS estables en Draft ↔ Submit
- IVA sobre cuota en cascada correcto
- Conversión UOM canónica determinística
```

#### 3. Reportes técnicos
- Actualizar `REPORTE_COMPARACION_SI_TEST_VS_PAC.md`
- Crear `REPORTE_IMPLEMENTACION_E4_ON_ITEM_QUANTITY.md`
- Archivar reportes FIX-V1/V2 en `docs/development/archive/`

---

## 14) ENTREGABLES A PRODUCIR

### 1. Especificación funcional de STCT
**Archivo:** `docs/development/ESPECIFICACION_STCT_E4.md`

**Contenido:**
- Filas exactas por categoría IEPS (tabaco, alcohol, refrescos)
- Orden obligatorio (cuota → IVA cascada → retenciones)
- Valores de configuración por fila
- Ejemplos completos por categoría

### 2. Matriz de UOM (ver sección 12)
**Archivo:** `docs/development/MATRIZ_UOM_IEPS.md`

**Contenido:**
- UOM canónicas por categoría IEPS
- Tabla conversión UOM venta → UOM canónica
- Ejemplos de configuración en Items
- Casos edge (bundles, fraccionarios, multipaso)

### 3. Guía de validaciones
**Archivo:** `docs/development/GUIA_VALIDACIONES_E4.md`

**Contenido:**
- Bloqueos duros (ITT, conversión UOM)
- Advertencias suaves (multipaso, montos pequeños)
- Precisión y tolerancias
- Mensajes de error exactos

### 4. Checklist de pruebas (ver sección 10)
**Archivo:** `docs/testing/planes/plan-testing-e4/PLAN_TESTING_E4_ON_ITEM_QUANTITY.md`

**Contenido:**
- Testing Gate completo
- 6 casos imprescindibles detallados
- Scripts de prueba (one_offs/)
- Dataset PAC de referencia

### 5. Plan de eliminación del legacy (ver sección 13)
**Archivo:** `docs/development/PLAN_ELIMINACION_LEGACY_E4.md`

**Contenido:**
- Lista archivos/módulos a deprecar
- Lista archivos/módulos a eliminar
- Cronograma de limpieza
- Comandos específicos

---

## 15) PRÓXIMOS PASOS

### Fase actual: ✅ DISEÑO ARQUITECTÓNICO (completado)

### Siguiente fase: 📋 ESPECIFICACIONES DETALLADAS

**Orden de trabajo:**

1. **Especificación STCT** (docs/development/ESPECIFICACION_STCT_E4.md)
   - Definir filas exactas por categoría IEPS
   - Valores de configuración
   - Ejemplos completos

2. **Matriz UOM** (docs/development/MATRIZ_UOM_IEPS.md)
   - Completar categorías IEPS
   - Tabla conversión completa
   - Casos edge documentados

3. **Guía validaciones** (docs/development/GUIA_VALIDACIONES_E4.md)
   - Pseudocódigo validadores
   - Mensajes de error exactos
   - Precisión y tolerancias

4. **Plan testing** (docs/testing/planes/plan-testing-e4/)
   - Detalle 6 casos imprescindibles
   - Scripts de prueba
   - Criterios aceptación

5. **Plan eliminación legacy** (docs/development/PLAN_ELIMINACION_LEGACY_E4.md)
   - Inventario completo código a eliminar
   - Cronograma limpieza
   - Comandos específicos

### Solo después de especificaciones aprobadas: 💻 IMPLEMENTACIÓN

**NO IMPLEMENTAR CÓDIGO HASTA QUE TODAS LAS ESPECIFICACIONES ESTÉN APROBADAS**

---

## RESUMEN EJECUTIVO

### ✅ Decisión arquitectónica: Rediseño completo
- Adoptar `charge_type = "On Item Quantity"` (comportamiento nativo ERPNext)
- Eliminar `charge_type = "Actual"` (inestable en submit)
- Sin feature flags, sin convivencia, sin toggles

### 🎯 Objetivo: Cuotas IEPS estables en todo el ciclo de vida
- Draft = Submit (sin regresión)
- Cuotas permanecen `On Item Quantity` (no cambian)
- IVA sobre cuota en cascada correcto
- Delta PAC ≤ $0.05 MXN (ley)

### 🚦 Testing Gate obligatorio antes de eliminar legacy
- 6 casos imprescindibles: OK
- Suite tests: 100% verde
- Comparativa PAC: delta ≤ $0.05 MXN
- Verificación Draft = Submit: OK

### 📦 No hay producción activa
- Eliminación legacy **inmediata** tras validación DEV
- Reversa solo por restore backup + revert commit
- Sin lógica de convivencia en código

### 🔒 Validaciones duras
- ITT sin cuotas (bloqueo duro)
- Conversión UOM obligatoria (bloqueo duro)
- Sin mutaciones tardías (comportamiento nativo)

---

**Fecha documento:** 2025-10-27
**Estado:** 📐 DISEÑO APROBADO - Pendiente especificaciones detalladas
**Siguiente paso:** Crear especificaciones funcionales (sin código)
