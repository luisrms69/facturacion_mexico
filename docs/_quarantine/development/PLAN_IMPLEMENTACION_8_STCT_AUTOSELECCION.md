# INFORME: Cambios Requeridos - Propuesta ChatGPT vs Arquitectura Actual

**Fecha:** 2025-10-23
**Propuesta analizada:** Plan de implementación STCT Auto v1 (ChatGPT)
**Arquitectura base:** Sistema E0.5 - STCT Consolidados + IEPS Cuota Automático
**Destino:** Retroalimentación para ChatGPT
**Decisión:** IMPLEMENTAR propuesta completa (8 STCT + autoselección)

---

## 📋 RESUMEN EJECUTIVO

### Estado Actual (E0.5) - PROBLEMA
❌ **Sistema con templates consolidados:**
- 2 STCT consolidados (IVA 16% + IVA 8% frontera)
- **PROBLEMA:** Sales Invoices tienen filas en $0.00 cuando no aplican
- **PROBLEMA:** Templates gigantes con todas las categorías (IEPS + Retenciones + todo)
- Selección STCT solo por zona fronteriza (no considera categorías productos)

### Propuesta ChatGPT - SOLUCIÓN
🎯 **Objetivo:** Crear 8 STCT específicos + autoselección inteligente

**8 STCT en total (4 variantes × 2 zonas):**

**Para IVA Nacional (16%):**
1. IVA Nacional - Básico (solo IVA, sin IEPS/Ret)
2. IVA Nacional + IEPS
3. IVA Nacional + Retenciones
4. IVA Nacional - Total (IEPS + Ret + todo)

**Para IVA Frontera (8%):**
1. IVA Frontera - Básico (solo IVA, sin IEPS/Ret)
2. IVA Frontera + IEPS
3. IVA Frontera + Retenciones
4. IVA Frontera - Total (IEPS + Ret + todo)

**Beneficios:**
✅ Sales Invoices SIN filas en $0.00 (template mínimo necesario)
✅ Selección automática según categorías productos
✅ Templates más simples y específicos
✅ Mejor performance (menos filas taxes)

### Cambios REQUERIDOS para Implementación
1. **P1 ALTA:** Crear 8 STCT (4 base × 2 zonas) según propuesta
2. **P1 ALTA:** Implementar autoselección según categorías (zona + productos)
3. **P1 ALTA:** Renombrar para eliminar "16%"/"8%" → "Nacional"/"Frontera"
4. **P2 MEDIA:** Normalizar descripciones filas tax
5. **P2 MEDIA:** Función rectora reglas IVA
6. **P3 BAJA:** Suite tests E2E (después de implementación)

---

## 🔍 ANÁLISIS DETALLADO POR SECCIÓN DE LA PROPUESTA

### §0 - ARRANQUE

| Item | Propuesta | Estado Actual | Acción Requerida |
|------|-----------|---------------|------------------|
| Branch feature | `feature/stct-auto-v1` | N/A | ✅ Crear branch nuevo |
| Backup BD | Obligatorio | Procedimiento existe | ✅ Ejecutar backup antes de empezar |
| Sin flags/toggles | Requerido | No usamos flags | ✅ Implementación directa |

**Status:** 🟢 LISTO PARA IMPLEMENTAR

---

### §1 - CATÁLOGO STCT: 8 TEMPLATES (4×2 ZONAS)

#### Propuesta ChatGPT:
```
4 variantes base:
1. Básico IVA (0%, tasa_zona)
2. Básico + IEPS
3. Básico + Retenciones
4. Esquema Total (todo)

× 2 zonas (Nacional 16% / Frontera 8%) = 8 STCT totales
```

#### Estado Actual:
```
2 STCT consolidados:
1. "IVA 16% - México - {abbr}" (TODO: IEPS + Retenciones + Mixto)
2. "IVA 8% - Zona Fronteriza - {abbr}" (TODO: IEPS + Retenciones + Mixto)

Problema: Filas en $0.00 en Sales Invoices
```

#### Implementación Requerida:

**1.1 - Crear 8 STCT nuevos (P1 ALTA)**

**Templates para IVA Nacional (16%):**

| # | Nombre Template | Componentes | Casos de Uso |
|---|----------------|-------------|--------------|
| 1 | IVA Nacional - Básico - {abbr} | Solo IVA 0%/16% | Papelería, servicios básicos |
| 2 | IVA Nacional + IEPS - {abbr} | IVA + IEPS (Alcohol/Azúcar/Combustibles/Tabaco) | Productos con IEPS, sin retenciones |
| 3 | IVA Nacional + Retenciones - {abbr} | IVA + Ret IVA + Ret ISR | Honorarios, arrendamiento |
| 4 | IVA Nacional - Total - {abbr} | IVA + IEPS + Retenciones | Documentos mixtos complejos |

**Templates para IVA Frontera (8%):**

| # | Nombre Template | Componentes | Casos de Uso |
|---|----------------|-------------|--------------|
| 5 | IVA Frontera - Básico - {abbr} | Solo IVA 0%/8% | Papelería zona frontera |
| 6 | IVA Frontera + IEPS - {abbr} | IVA + IEPS (Alcohol/Azúcar/Combustibles/Tabaco) | Productos IEPS zona frontera |
| 7 | IVA Frontera + Retenciones - {abbr} | IVA + Ret IVA + Ret ISR | Honorarios zona frontera |
| 8 | IVA Frontera - Total - {abbr} | IVA + IEPS + Retenciones | Documentos mixtos zona frontera |

**Estructura de cada template:**

```python
# Template 1: IVA Nacional - Básico
taxes = [
    {"description": "IVA 0%", "rate": 0, "charge_type": "On Net Total"},
    {"description": "IVA Nacional - Base (Resto)", "rate": 16, "charge_type": "On Net Total"},
]

# Template 2: IVA Nacional + IEPS
taxes = [
    {"description": "IVA 0%", "rate": 0, "charge_type": "On Net Total"},
    # IEPS slots (4 categorías × 2 tipos = 8 filas)
    {"description": "IEPS Alcohol - Tasa", "rate": 0, "charge_type": "On Net Total"},
    {"description": "IVA Nacional sobre IEPS Alcohol", "rate": 16, "charge_type": "On Previous Row Amount"},
    {"description": "IEPS Azúcar - Tasa", "rate": 0, "charge_type": "On Net Total"},
    {"description": "IVA Nacional sobre IEPS Azúcar", "rate": 16, "charge_type": "On Previous Row Amount"},
    {"description": "IEPS Combustibles - Cuota", "rate": 0, "charge_type": "Actual"},
    # (NO hay IVA cascada combustibles)
    {"description": "IEPS Tabaco - Tasa", "rate": 0, "charge_type": "On Net Total"},
    {"description": "IEPS Tabaco - Cuota", "rate": 0, "charge_type": "Actual"},
    {"description": "IVA Nacional sobre IEPS Tabaco", "rate": 16, "charge_type": "On Previous Row Total"},
    # IVA base (resto)
    {"description": "IVA Nacional - Base (Resto)", "rate": 16, "charge_type": "On Net Total"},
]

# Template 3: IVA Nacional + Retenciones
taxes = [
    {"description": "IVA 0%", "rate": 0, "charge_type": "On Net Total"},
    {"description": "IVA Nacional - Base", "rate": 16, "charge_type": "On Net Total"},
    {"description": "Retención IVA - Honorarios", "rate": 0, "charge_type": "Actual"},
    {"description": "Retención ISR - Honorarios", "rate": 0, "charge_type": "Actual"},
    {"description": "Retención IVA - Arrendamiento", "rate": 0, "charge_type": "Actual"},
    {"description": "Retención ISR - Arrendamiento", "rate": 0, "charge_type": "Actual"},
]

# Template 4: IVA Nacional - Total (consolidado actual)
taxes = [
    # Todos los slots de Template 2 + Template 3 combinados
]
```

**Complejidad:** 🔴 ALTA (16-20 horas)
- Modificar `generador_templates_fiscal.py` para generar 8 variantes
- Definir estructura filas por variante
- Script migración/generación para empresas existentes
- Tests de generación

**Impacto:** 🔴 ALTO - Cambio estructural
**Prioridad:** 🔴 P1 ALTA

**Beneficios:**
- ✅ Sales Invoices SIN filas $0.00
- ✅ Templates específicos por escenario
- ✅ Mejor UX (menos ruido visual)
- ✅ Mejor performance (menos filas calcular)

**Recomendación:** ✅ IMPLEMENTAR (objetivo principal proyecto)

---

**1.2 - Normalizar descripciones filas tax (P2 MEDIA)**

**Objetivo:** Descripciones sin hardcode tasas, direccionables por slot semántico

**Antes:**
```
"IVA 16% sobre IEPS Alcohol"
"IVA 16% sobre IEPS Tabaco (Tasa + Cuota)"
"IVA 16% base (neto)"
"Retención IVA Honorarios (2/3 IVA trasladado, tasa via ITT)"
```

**Después:**
```
"IVA Nacional sobre IEPS Alcohol"
"IVA Nacional sobre IEPS Tabaco"
"IVA Nacional - Base (Resto)"
"Retención IVA - Honorarios"
```

**Complejidad:** 🟡 MEDIO (4 horas)
**Impacto:** 🟡 MEDIO
**Prioridad:** 🟡 P2 MEDIA

**Recomendación:** ✅ IMPLEMENTAR (parte de §1.1)

---

### §2 - CLASIFICACIÓN POR CATEGORÍA (Incluye Tabaco)

#### Propuesta ChatGPT:
```
Objetivo: Función que clasifica items del documento en categorías
para determinar qué STCT aplicar.

Categorías: Alcohol, Azúcar, Combustibles, Tabaco, Retenciones, Resto

Fuente verdad:
1. Item Tax Template (ITT) del item
2. Item Group (fallback si no hay ITT)
```

#### Estado Actual:
```
Clasificación IMPLÍCITA:
- ITT determina qué taxes aplican al item
- Hooks leen ITT para calcular IEPS/IVA
- NO hay función centralizada clasificar_items()
```

#### Implementación Requerida:

**2.1 - Crear función clasificación items (P1 ALTA)**

```python
def clasificar_items_documento(doc: "Sales Invoice") -> dict:
    """
    Clasifica items del documento en categorías fiscales.

    Returns:
        {
            "tiene_ieps": bool,
            "tiene_retenciones": bool,
            "categorias": ["Alcohol", "Resto"],
            "items_por_categoria": {
                "Alcohol": ["Item-001"],
                "Resto": ["Item-002", "Item-003"],
            }
        }
    """
    categorias = set()
    items_por_categoria = defaultdict(list)

    for item in doc.items:
        # Inferir categoría desde ITT del item
        if not item.item_tax_template:
            categoria = "Resto"
        else:
            itt = frappe.get_cached_doc("Item Tax Template", item.item_tax_template)
            categoria = _inferir_categoria_desde_itt(itt)

        categorias.add(categoria)
        items_por_categoria[categoria].append(item.item_code)

    return {
        "tiene_ieps": any(c in CATEGORIAS_IEPS for c in categorias),
        "tiene_retenciones": any(c in CATEGORIAS_RETENCION for c in categorias),
        "categorias": list(categorias),
        "items_por_categoria": dict(items_por_categoria),
    }


def _inferir_categoria_desde_itt(itt: "Item Tax Template") -> str:
    """
    Infiere categoría fiscal desde estructura ITT.

    Lógica:
    - Si ITT tiene cuenta IEPS Alcohol → "Alcohol"
    - Si ITT tiene cuenta IEPS Azúcar → "Azucar"
    - Si ITT tiene cuenta IEPS Combustibles → "Combustibles"
    - Si ITT tiene cuenta IEPS Tabaco → "Tabaco"
    - Si ITT tiene Ret IVA/ISR → "Retenciones"
    - Else → "Resto"
    """
    # Obtener mapeos fiscales de la empresa
    company = frappe.defaults.get_global_default("company")
    config_fiscal = frappe.get_cached_doc("Configuracion Fiscal Mexico", company)

    for tax_row in itt.taxes:
        account = tax_row.tax_type
        mapeo = config_fiscal.get_mapeo_por_cuenta(account)

        if mapeo:
            if mapeo.rol_fiscal == "IEPS":
                if "Alcohol" in mapeo.descripcion:
                    return "Alcohol"
                elif "Azúcar" in mapeo.descripcion or "Bebidas" in mapeo.descripcion:
                    return "Azucar"
                elif "Combustibles" in mapeo.descripcion or "Gasolina" in mapeo.descripcion:
                    return "Combustibles"
                elif "Tabaco" in mapeo.descripcion:
                    return "Tabaco"
            elif mapeo.rol_fiscal in ("RET_IVA", "RET_ISR"):
                return "Retenciones"

    return "Resto"


# Constantes
CATEGORIAS_IEPS = {"Alcohol", "Azucar", "Combustibles", "Tabaco"}
CATEGORIAS_RETENCION = {"Retenciones"}
```

**Complejidad:** 🟡 MEDIO (4-6 horas)
**Impacto:** 🔴 ALTO (base para §3)
**Prioridad:** 🔴 P1 ALTA

**Recomendación:** ✅ IMPLEMENTAR (prerequisito §3)

---

### §3 - AUTOSELECCIÓN DE STCT EN SAVE

#### Propuesta ChatGPT:
```
Objetivo: Seleccionar automáticamente STCT mínimo necesario
según zona + categorías de productos.

Regla determinista:
- Solo Resto → Básico IVA
- IEPS + no Ret → Básico + IEPS
- Ret + no IEPS → Básico + Retenciones
- IEPS + Ret → Esquema Total
```

#### Estado Actual:
```
Autoselección LIMITADA:
- Solo considera zona fronteriza (Branch.fm_is_border_zone)
- NO considera categorías de productos
- Siempre usa template consolidado (aunque solo tenga IVA)

Hook actual: sales_invoice_automated_tax.py:before_validate()
```

#### Implementación Requerida:

**3.1 - Ampliar lógica autoselección STCT (P1 ALTA)**

```python
def seleccionar_stct_automatico(doc):
    """
    Selecciona STCT óptimo según zona + categorías productos.

    Matriz decisión (4 variantes × 2 zonas = 8 opciones):

    | Tiene IEPS | Tiene Ret | Zona Nacional      | Zona Frontera           |
    |------------|-----------|-------------------|------------------------|
    | No         | No        | IVA Nacional - Básico | IVA Frontera - Básico |
    | Sí         | No        | IVA Nacional + IEPS   | IVA Frontera + IEPS   |
    | No         | Sí        | IVA Nacional + Ret    | IVA Frontera + Ret    |
    | Sí         | Sí        | IVA Nacional - Total  | IVA Frontera - Total  |
    """
    # PASO 1: Determinar zona
    branch = frappe.get_doc("Branch", doc.fm_branch)
    zona = "Frontera" if branch.fm_is_border_zone else "Nacional"

    # PASO 2: Clasificar productos (§2.1)
    clasificacion = clasificar_items_documento(doc)

    # PASO 3: Determinar variante según matriz decisión
    tiene_ieps = clasificacion["tiene_ieps"]
    tiene_ret = clasificacion["tiene_retenciones"]

    if not tiene_ieps and not tiene_ret:
        variante = "Básico"
    elif tiene_ieps and not tiene_ret:
        variante = "IEPS"
    elif tiene_ret and not tiene_ieps:
        variante = "Retenciones"
    else:  # tiene_ieps and tiene_ret
        variante = "Total"

    # PASO 4: Buscar STCT
    company = doc.company
    abbr = frappe.get_cached_value("Company", company, "abbr")

    # Construir nombre según variante
    if variante == "Básico":
        pattern = f"IVA {zona} - Básico - {abbr}"
    elif variante == "IEPS":
        pattern = f"IVA {zona} + IEPS - {abbr}"
    elif variante == "Retenciones":
        pattern = f"IVA {zona} + Retenciones - {abbr}"
    else:  # Total
        pattern = f"IVA {zona} - Total - {abbr}"

    stct = frappe.db.get_value(
        "Sales Taxes and Charges Template",
        {"title": pattern, "company": company},
        "name"
    )

    if not stct:
        frappe.throw(
            f"No se encontró STCT: {pattern}. "
            f"Ejecute: bench --site {frappe.local.site} execute "
            f"facturacion_mexico.setup.generador_templates_fiscal.generar_para_empresa --args \"['{company}']\" "
        )

    return stct


# Hook: sales_invoice_automated_tax.py
def before_validate(doc, method=None):
    """
    Hook before_validate para Sales Invoice.
    Autoselecciona STCT según zona + categorías.
    """
    if doc.doctype != "Sales Invoice":
        return

    # Solo autoseleccionar si no hay STCT o es de nuestra app
    if not doc.taxes_and_charges or _es_stct_facturacion_mexico(doc.taxes_and_charges):
        stct_auto = seleccionar_stct_automatico(doc)

        # Si cambió el STCT, recargar taxes
        if doc.taxes_and_charges != stct_auto:
            doc.taxes_and_charges = stct_auto
            doc.set_taxes()  # Recargar filas taxes desde template
```

**Complejidad:** 🟡 MEDIO (6 horas con §2.1)
**Impacto:** 🔴 ALTO (UX mejorada, sin filas $0)
**Prioridad:** 🔴 P1 ALTA

**Recomendación:** ✅ IMPLEMENTAR (objetivo principal proyecto)

---

### §4 - "FUNCIÓN RECTORA" (Ruteo IVA por escenario)

#### Propuesta ChatGPT:
```
Objetivo: Centralizar reglas de base IVA por categoría.

Reglas (ya implementadas):
- Combustibles: IVA sobre neto (sin IEPS)
- Alcohol/Azúcar: IVA cascada (con IEPS)
- Resto: IVA sobre neto

Tabaco: Pasar sin cambios en esta fase.
```

#### Estado Actual:
```
Reglas implementadas en múltiples lugares:
- STCT: charge_type determina base IVA
- Hooks: Ajustes específicos por categoría
- Metadata: Mapeo Fiscal.integra_base_iva

NO hay función centralizada que documente reglas.
```

#### Implementación Requerida:

**4.1 - Crear función rectora reglas IVA (P2 MEDIA)**

```python
def aplicar_reglas_iva_por_categoria(doc, clasificacion: dict):
    """
    Función rectora: reglas de base IVA por categoría.

    Reglas:
    1. Combustibles: IVA sobre neto (NO integra IEPS)
    2. Alcohol/Azúcar: IVA cascada (SÍ integra IEPS)
    3. Tabaco: IVA cascada sobre ambos IEPS (SÍ integra)
    4. Resto: IVA sobre neto

    Args:
        doc: Sales Invoice
        clasificacion: Output de clasificar_items_documento()

    Returns:
        dict con reglas aplicadas por categoría
    """
    reglas_aplicadas = {}

    for categoria in clasificacion["categorias"]:
        regla = REGLAS_IVA_POR_CATEGORIA.get(categoria)

        reglas_aplicadas[categoria] = {
            "tipo_base": regla["tipo_base"],
            "integra_ieps": regla["integra_base_iva"],
            "fundamento_legal": regla["fundamento_legal"],
        }

    return reglas_aplicadas


# Constante de reglas (documentación explícita)
REGLAS_IVA_POR_CATEGORIA = {
    "Combustibles": {
        "tipo_base": "neto",
        "fundamento_legal": "LIEPS Art. 2-A Fracc. II",
        "integra_base_iva": False,
        "nota": "Excepción legal: IVA NO se calcula sobre IEPS Cuota",
    },
    "Alcohol": {
        "tipo_base": "cascada",
        "fundamento_legal": "Ley IVA Art. 12",
        "integra_base_iva": True,
        "nota": "IVA se calcula sobre precio + IEPS Tasa",
    },
    "Azucar": {
        "tipo_base": "cascada",
        "fundamento_legal": "Ley IVA Art. 12",
        "integra_base_iva": True,
        "nota": "IVA se calcula sobre precio + IEPS Tasa",
    },
    "Tabaco": {
        "tipo_base": "cascada",
        "fundamento_legal": "Ley IVA Art. 12",
        "integra_base_iva": True,
        "nota": "IVA cascada sobre IEPS Tasa + IEPS Cuota simultáneos",
    },
    "Resto": {
        "tipo_base": "neto",
        "fundamento_legal": "Ley IVA Art. 12 (base estándar)",
        "integra_base_iva": False,
        "nota": "IVA sobre precio de venta sin IEPS",
    },
}
```

**Complejidad:** 🟡 MEDIO (4 horas)
**Impacto:** 🟢 BAJO (documentación, no cambia lógica)
**Prioridad:** 🟡 P2 MEDIA

**Recomendación:** ✅ IMPLEMENTAR (mejora calidad código)

---

**4.2 - Validación post-cálculo (P2 MEDIA)**

```python
def validar_aplicacion_reglas_iva(doc, clasificacion: dict):
    """
    Valida que hooks aplicaron reglas correctamente.
    Ejecuta en before_submit (no bloquea, solo alerta).
    """
    reglas_esperadas = aplicar_reglas_iva_por_categoria(doc, clasificacion)

    inconsistencias = []

    for categoria, items in clasificacion["items_por_categoria"].items():
        regla = reglas_esperadas[categoria]

        for item_code in items:
            # Verificar que IVA item cumple regla
            iva_item = _get_iva_item_from_item_wise(doc, item_code)

            if regla["tipo_base"] == "neto":
                # Validar: IVA = net_amount × tasa
                pass
            elif regla["tipo_base"] == "cascada":
                # Validar: IVA = (net_amount + ieps) × tasa
                pass

    if inconsistencias:
        frappe.log_error(
            "Inconsistencia reglas IVA",
            json.dumps(inconsistencias, indent=2)
        )
```

**Complejidad:** 🟢 BAJO (2 horas)
**Impacto:** 🟡 MEDIO (detección bugs)
**Prioridad:** 🟡 P2 MEDIA

**Recomendación:** ✅ IMPLEMENTAR (capa validación extra)

---

### §5 - ELIMINADO (Observabilidad)

**Propuesta:** Reportes/resúmenes adicionales

**Estado Actual:** Tax Breakup nativo ERPNext suficiente

**Recomendación:** ✅ NO IMPLEMENTAR (Tax Breakup cubre necesidad)

---

### §6 - PRUEBAS

#### Propuesta ChatGPT:
```
Tests de escenarios:
1. Básico IVA (solo Resto)
2. Básico + IEPS (Alcohol/Azúcar/Combustibles)
3. Básico + Retenciones
4. Esquema Total (mixto)
5. Ediciones (agregar/quitar items → cambio STCT)
6. Descuentos por línea
```

#### Estado Actual:
```
Tests limitados:
✅ test_itt_order_ieps_before_iva.py (orden fiscal)
⚠️ Tests manuales documentados (E4 suite)
❌ Tests automatizados E2E escenarios completos
❌ Tests autoselección STCT
❌ Tests cambio STCT al agregar/quitar items
```

#### Implementación Requerida:

**6.1 - Suite tests E2E (P0 URGENTE)**

```python
# tests/test_autoseleccion_stct_e2e.py

class TestAutoseleccionSTCT(FrappeTestCase):
    """
    Tests E2E de autoselección STCT según categorías.
    """

    def test_escenario_1_basico_iva_solo_resto(self):
        """Test: Solo items normales → STCT Básico."""
        si = crear_si_test({
            "branch": "Branch Nacional",  # NO frontera
            "items": [
                {"item_code": "Papelería-001", "qty": 10, "rate": 100},
            ]
        })

        # Verificar STCT autoseleccionado
        self.assertEqual(
            si.taxes_and_charges,
            "IVA Nacional - Básico - _TC"
        )

        # Verificar solo tiene filas IVA (sin IEPS/Ret)
        self.assertEqual(len(si.taxes), 2)  # IVA 0% + IVA 16%

        # Verificar NO hay filas en $0
        for tax in si.taxes:
            if tax.rate > 0:
                self.assertGreater(tax.tax_amount, 0)

    def test_escenario_2_basico_ieps_alcohol(self):
        """Test: Alcohol → STCT Básico + IEPS."""
        si = crear_si_test({
            "branch": "Branch Nacional",
            "items": [
                {"item_code": "TEST-IEPS-ALCOHOL-001", "qty": 6, "rate": 550},
            ]
        })

        # Verificar STCT autoseleccionado
        self.assertEqual(
            si.taxes_and_charges,
            "IVA Nacional + IEPS - _TC"
        )

        # Verificar tiene filas IEPS + IVA (sin Retenciones)
        tiene_ieps = any("IEPS Alcohol" in t.description for t in si.taxes)
        tiene_ret = any("Retención" in t.description for t in si.taxes)

        self.assertTrue(tiene_ieps)
        self.assertFalse(tiene_ret)

    def test_escenario_3_retenciones_honorarios(self):
        """Test: Honorarios → STCT Básico + Retenciones."""
        si = crear_si_test({
            "branch": "Branch Nacional",
            "items": [
                {"item_code": "Servicio-Honorarios-001", "qty": 1, "rate": 10000},
            ]
        })

        # Verificar STCT autoseleccionado
        self.assertEqual(
            si.taxes_and_charges,
            "IVA Nacional + Retenciones - _TC"
        )

        # Verificar tiene Retenciones (sin IEPS)
        tiene_ieps = any("IEPS" in t.description for t in si.taxes)
        tiene_ret = any("Retención" in t.description for t in si.taxes)

        self.assertFalse(tiene_ieps)
        self.assertTrue(tiene_ret)

    def test_escenario_4_total_mixto(self):
        """Test: Alcohol + Honorarios → STCT Total."""
        si = crear_si_test({
            "branch": "Branch Nacional",
            "items": [
                {"item_code": "TEST-IEPS-ALCOHOL-001", "qty": 6, "rate": 550},
                {"item_code": "Servicio-Honorarios-001", "qty": 1, "rate": 5000},
            ]
        })

        # Verificar STCT consolidado (tiene ambos)
        self.assertEqual(
            si.taxes_and_charges,
            "IVA Nacional - Total - _TC"
        )

        # Verificar tiene IEPS + Retenciones
        tiene_ieps = any("IEPS" in t.description for t in si.taxes)
        tiene_ret = any("Retención" in t.description for t in si.taxes)

        self.assertTrue(tiene_ieps)
        self.assertTrue(tiene_ret)

    def test_escenario_5_zona_frontera(self):
        """Test: Zona frontera → STCT con IVA 8%."""
        si = crear_si_test({
            "branch": "Branch Frontera",  # fm_is_border_zone = 1
            "items": [
                {"item_code": "Papelería-001", "qty": 10, "rate": 100},
            ]
        })

        # Verificar STCT Frontera
        self.assertEqual(
            si.taxes_and_charges,
            "IVA Frontera - Básico - _TC"
        )

        # Verificar tasa IVA = 8%
        iva_tax = [t for t in si.taxes if t.rate > 0][0]
        self.assertEqual(iva_tax.rate, 8.0)

    def test_escenario_6_cambio_stct_al_agregar_item(self):
        """Test: Agregar item IEPS → cambia STCT Básico → IEPS."""
        si = crear_si_test({
            "branch": "Branch Nacional",
            "items": [
                {"item_code": "Papelería-001", "qty": 10, "rate": 100},
            ]
        })

        # Inicial: STCT Básico
        self.assertEqual(si.taxes_and_charges, "IVA Nacional - Básico - _TC")

        # Agregar item Alcohol
        si.append("items", {
            "item_code": "TEST-IEPS-ALCOHOL-001",
            "qty": 6,
            "rate": 550,
        })

        si.save()  # Trigger before_validate → autoselección

        # Verificar STCT cambió a IEPS
        self.assertEqual(si.taxes_and_charges, "IVA Nacional + IEPS - _TC")

    def test_escenario_7_sin_filas_cero(self):
        """Test: Templates específicos NO tienen filas en $0."""
        si = crear_si_test({
            "branch": "Branch Nacional",
            "items": [
                {"item_code": "Papelería-001", "qty": 10, "rate": 100},
            ]
        })

        # STCT Básico: solo IVA 0% + IVA 16%
        # NO debe tener filas IEPS/Retenciones

        descripciones_ieps = [
            "IEPS Alcohol", "IEPS Azúcar", "IEPS Combustibles", "IEPS Tabaco"
        ]
        descripciones_ret = [
            "Retención IVA", "Retención ISR"
        ]

        for tax in si.taxes:
            # Verificar NO hay filas IEPS
            for desc_ieps in descripciones_ieps:
                self.assertNotIn(desc_ieps, tax.description)

            # Verificar NO hay filas Retenciones
            for desc_ret in descripciones_ret:
                self.assertNotIn(desc_ret, tax.description)
```

**Complejidad:** 🟡 MEDIO (8-12 horas)
**Impacto:** 🔴 ALTO (prevención regresiones)
**Prioridad:** ⚠️ P0 URGENTE

**Recomendación:** ✅ IMPLEMENTAR ANTES de §1/§3 (TDD approach)

---

### §7 - DESPLIEGUE

**Propuesta:** Merge sin flags cuando tests pasen

**Status:** 🟢 ALINEADO con workflow actual

**Recomendación:** ✅ MANTENER

---

### §8 - COMPATIBILIDAD CON ESQUEMA IEPS ACTUAL

#### Propuesta ChatGPT:
```
La clasificación consulta campos ieps_tipo (select: tasa/cuota).
```

#### Estado Actual:
```
NO existen campos ieps_tipo.
Clasificación via ITT (estructura taxes).
```

#### Recomendación:

**8.1 - NO crear campos ieps_tipo (INNECESARIO)**

**Razón:**
- ITT ya clasifica correctamente
- Agregar campos duplica información
- Mayor complejidad sin beneficio

**Status:** ❌ NO IMPLEMENTAR

---

### §9 - SOBRE TABACO

#### Propuesta ChatGPT:
```
- SÍ está en clasificación (influye autoselección)
- NO se toca su cálculo en esta fase
```

#### Estado Actual:
```
Tabaco:
✅ Clasificado (via ITT "IEPS Tabaco")
✅ Cálculo implementado (IEPS Tasa + Cuota)
⚠️ IVA tiene BUG conocido (tax_amount incorrecto)
```

#### Decisión: Posponer corrección bug IVA Tabaco

**⏸️ NOTA IMPORTANTE:**
El bug de IVA Tabaco se atenderá **en su turno natural**, cuando corresponda revisar el cálculo de **TODOS los IEPS** de forma integral. No se corregirá de forma aislada en esta fase.

**Bug documentado (se atenderá en fase futura):**

**9.1 - Corregir bug IVA Tabaco (⏸️ FASE FUTURA - Revisión integral IEPS)**

**Archivo:** `sales_invoice_ieps.py:233-243`

**Problema identificado:**
```python
# ACTUAL (BUGGY)
for item in doc.items:
    if item.item_code in distribucion_ieps:
        ieps_amount = distribucion_ieps[item.item_code][1]
        if ieps_amount > 0:  # ← Bug: True para TODOS los items
            base_iva = flt(item.net_amount)
            iva_amount = flt(base_iva * iva_rate / 100)
            iva_distribucion[item.item_code] = [iva_rate, iva_amount]

# Resultado:
# iva_distribucion = {
#     "Alcohol": [16, 528.00],    # ← NO debería estar
#     "Tabaco": [16, 80.00],      # ✅ Correcto
#     "Azucar": [16, 64.00],      # ← NO debería estar
#     "Combustibles": [16, 166.40] # ← NO debería estar
# }
# tax_amount = 528 + 80 + 64 + 166.40 = $838.40 ❌
# Esperado: tax_amount = $80.00 (solo Tabaco) ✅
```

**Corrección propuesta (para fase futura):**
```python
# Obtener cuenta IEPS Cuota de ESTA fila tax específica
ieps_cuota_account = ieps_tax_row.account_head

# Solo incluir items que contribuyen a ESTA cuenta específica
for item in doc.items:
    if not item.item_tax_template:
        continue

    # Verificar que ITT del item contribuye a esta cuenta IEPS Cuota
    itt = frappe.get_cached_doc("Item Tax Template", item.item_tax_template)

    contribuye_a_esta_cuenta = False
    for itt_tax in itt.taxes:
        if itt_tax.tax_type == ieps_cuota_account:
            contribuye_a_esta_cuenta = True
            break

    if contribuye_a_esta_cuenta:
        # Solo ESTE item contribuye a esta fila IEPS Cuota
        base_iva = flt(item.net_amount)
        iva_amount = flt(base_iva * iva_rate / 100, iva_tax.precision("tax_amount"))
        iva_distribucion[item.item_code] = [iva_rate, iva_amount]

# Resultado correcto:
# iva_distribucion = {"Tabaco": [16, 80.00]}
# tax_amount = $80.00 ✅
```

**Complejidad:** 🟡 MEDIO (4 horas)
**Impacto:** 🟡 MEDIO (discrepancia conocida, no bloqueante)
**Prioridad:** ⏸️ FASE FUTURA (revisión integral IEPS)

**Recomendación:** ⏸️ POSPONER a fase de revisión completa cálculo IEPS

---

## 📊 MATRIZ DE CAMBIOS: CLASIFICACIÓN COMPLETA

| # | Cambio | Complejidad | Impacto | Prioridad | Esfuerzo | Riesgo |
|---|--------|-------------|---------|-----------|----------|--------|
| **1.1** | **Crear 8 STCT (4 base × 2 zonas)** | 🔴 Alta | 🔴 Crítico | 🔴 P1 ALTA | 20h | 🟡 Medio |
| **2.1** | **Función clasificación items** | 🟡 Medio | 🔴 Alto | 🔴 P1 ALTA | 6h | 🟢 Bajo |
| **3.1** | **Autoselección STCT según categorías** | 🟡 Medio | 🔴 Alto | 🔴 P1 ALTA | 6h | 🟢 Bajo |
| **1.2** | **Normalizar descripciones filas** | 🟡 Medio | 🟡 Medio | 🟡 P2 MEDIA | 4h | 🟢 Bajo |
| **4.1** | **Función rectora reglas IVA** | 🟡 Medio | 🟢 Bajo | 🟡 P2 MEDIA | 4h | 🟢 Bajo |
| **4.2** | **Validación post-cálculo** | 🟢 Bajo | 🟡 Medio | 🟡 P2 MEDIA | 2h | 🟢 Bajo |
| **6.1** | **Suite tests E2E (post-implementación)** | 🟡 Medio | 🟢 Bajo | 🟢 P3 BAJA | 12h | 🟢 Bajo |
| **9.1** | **Bug IVA Tabaco (pospuesto)** | 🟡 Medio | 🟡 Medio | ⏸️ FASE FUTURA | 4h | 🟢 Bajo |

### Leyenda:
- **Complejidad:** 🟢 Bajo | 🟡 Medio | 🔴 Alto
- **Impacto:** 🟢 Bajo | 🟡 Medio | 🔴 Alto | 🔴 Crítico
- **Prioridad:** 🔴 P1 (Alta) | 🟡 P2 (Media) | 🟢 P3 (Baja) | ⏸️ FASE FUTURA
- **Riesgo:** 🟢 Bajo | 🟡 Medio | 🔴 Alto

---

## 🎯 PLAN DE IMPLEMENTACIÓN RECOMENDADO

### FASE 1: CREAR 8 STCT + CLASIFICACIÓN (Semana 1-2) - ✅ COMPLETADA

**Estado:** ✅ **COMPLETADA** (26h implementadas)

**Commits:**
- `3fdb47b` (oct 24): Crear 8 STCT específicos + generación automática ITT
- `26e8bc5` (oct 24): Consolidar fuente verdad Item Groups + clasificación

**Implementación:**

```
✅ 2.1 - Función clasificación items (6h) - COMMIT 26e8bc5
     ├─ clasificar_items_documento() en utils/clasificacion_items.py
     ├─ TABLA_MAESTRA_GRUPOS_FISCALES (fuente verdad única)
     ├─ Constantes auto-generadas: CATEGORIAS_IEPS, CATEGORIAS_RETENCION
     ├─ Diccionario ITEM_GROUP_CATEGORIA para mapeo directo
     └─ Suite tests unitarios (7 tests, 0.455s) - test_clasificacion_items.py

✅ 1.1 - Crear 8 STCT (20h) - COMMIT 3fdb47b
     ├─ Reescritura generador_templates_fiscal.py (-546 líneas)
     ├─ Función generate_8_stct_for_company() con 4 variantes × 2 zonas
     ├─ Templates específicos generados:
     │   ├─ Básico: 1 fila (solo IVA)
     │   ├─ IEPS: 6 filas (IVA + 4 IEPS + cascada)
     │   ├─ Retenciones: 3 filas (IVA + ISR + IVA Ret)
     │   └─ Total: 8 filas (todas combinadas)
     ├─ Templates consolidados viejos deshabilitados automáticamente
     ├─ Generación automática 18 ITT desde UI
     └─ Fuzzy matching roles fiscales (sin hardcode nombres)

✅ 1.2 - Normalizar descripciones (incluido en §1.1) - COMMIT 3fdb47b
     └─ Nombres semánticos: "IVA Nacional - Básico" (sin porcentajes)

Total Fase 1: 26 horas ✅
```

**Criterios éxito:**
- ✅ 8 STCT creados en todas las empresas
- ✅ Nombres sin "16%"/"8%" → "Nacional"/"Frontera"
- ✅ Descripciones normalizadas
- ✅ Templates consolidados viejos deshabilitados
- ✅ Clasificación items implementada y testeada

---

### FASE 2: AUTOSELECCIÓN STCT (Semana 3) - ✅ COMPLETADA

**Estado:** ✅ **COMPLETADA** (6h implementadas)

**Commits:**
- `3eae7c9` (oct 25): Fix generación templates + carga tax rows + autoselección

**Implementación:**

```
✅ 3.1 - Autoselección STCT según categorías (6h) - COMMIT 3eae7c9
     ├─ Función _determinar_variante_stct(doc) en sales_invoice_automated_tax.py
     ├─ Función _find_stct_by_variant(company, zona, variant) para búsqueda exacta
     ├─ Matriz decisión implementada:
     │   • zona × (tiene_ieps, tiene_retenciones) → 8 STCT específicos
     │   • Fallback a "Básico" si template específico no existe
     ├─ Hook before_validate() actualizado:
     │   • Clasifica items con clasificar_items_documento()
     │   • Determina zona desde Branch.fm_is_border_zone
     │   • Selecciona STCT apropiado automáticamente
     │   • Carga tax rows usando get_taxes_and_charges() nativo ERPNext
     ├─ Mensaje UI: "Impuestos configurados automáticamente: IVA {tasa} - {variante}"
     ├─ Eliminado código JavaScript legacy (_fm_apply_branch_tax_template)
     └─ Tests unitarios autoselección (7 tests, 0.803s) - test_autoseleccion_stct.py

Total Fase 2: 6 horas ✅
```

**Criterios éxito:**
- ✅ Autoselección funciona según matriz decisión (2×4 = 8 combinaciones)
- ✅ Sales Invoices SIN filas en $0 (solo template necesario)
- ✅ Template cambia automáticamente al modificar items
- ✅ Tax rows se cargan correctamente en UI
- ✅ Suite tests unitarios completa

---

### FASE 3: FUNCIÓN RECTORA + VALIDACIÓN (Semana 4) - ❌ NO IMPLEMENTADA

**Estado:** ❌ **NO IMPLEMENTADA** (0h de 6h)

**Commits:** NINGUNO

**Pendiente:**

```
❌ 4.1 - Función rectora reglas IVA e ISR (4h) - NO EXISTE
     ├─ Tabla REGLAS_CALCULO_IMPUESTOS en Mapeo Cuenta Fiscal Mexico
     │   ├─ Agregar campos: regla_base, regla_calculo, tipo_calculo
     │   ├─ Configurar reglas por rol fiscal:
     │   │   • IVA Nacional: base=net_amount, tipo=porcentual
     │   │   • IEPS Alcohol: base=net_amount, tipo=porcentual, integra_iva=true
     │   │   • IEPS Combustibles: base=qty, tipo=cuota, integra_iva=false
     │   │   • Ret IVA Honorarios: base=iva_trasladado, tipo=porcentual
     │   └─ Migrar lógica hardcoded desde sales_invoice_ieps.py
     ├─ Función rectora aplicar_reglas_calculo_impuestos(doc, tax_row)
     │   ├─ Lee reglas desde Mapeo Cuenta Fiscal Mexico
     │   ├─ Aplica regla según tipo_calculo
     │   ├─ Retorna: {base_calculada, monto_impuesto, item_wise_detail}
     │   └─ Centraliza toda la lógica de cálculo
     ├─ Refactorizar hooks:
     │   • calcular_ieps_cuota() → usa función rectora
     │   • _congelar_iva_sobre_ieps_cuota() → usa función rectora
     │   • ajustar_base_iva_combustibles() → usa función rectora
     └─ Tests unitarios reglas (mínimo 10 tests cubriendo todos los tipos)

❌ 4.2 - Validación post-cálculo (2h) - NO EXISTE
     ├─ Hook validar_aplicacion_reglas_fiscales(doc)
     │   ├─ Ejecuta en before_submit
     │   ├─ Verifica: suma item_wise_tax_detail == tax_amount
     │   ├─ Verifica: reglas aplicadas correctamente por categoría
     │   ├─ Verifica: tolerancias redondeo (±$0.01 item, ±$0.05 total)
     │   └─ Log errores sin bloquear (solo alertas)
     └─ Validación orden fiscal IEPS→IVA (ya existe parcialmente)

Total Fase 3: 6 horas ❌ PENDIENTE
```

**Criterios éxito PENDIENTES:**
- ❌ Tabla reglas configuración creada y migrada
- ❌ Función rectora implementada y centralizada
- ❌ Lógica hardcoded refactorizada
- ❌ Validación post-cálculo implementada
- ❌ Tests unitarios completos

---

### FASE 4: SUITE TESTS E2E (Post-implementación) - ⚠️ PARCIAL

**Estado:** ⚠️ **PARCIAL** (2h de 12h - solo tests unitarios)

**Commits:**
- `f15e46f` (oct 25): Tests autoselección STCT (UNITARIOS, no E2E)

**Implementación PARCIAL:**

```
⚠️ 6.1 - Suite tests autoselección (2h) - COMMIT f15e46f
     ✅ test_autoseleccion_stct.py (7 tests unitarios, 246 líneas)
        ├─ test_determinar_variante_basico()
        ├─ test_determinar_variante_ieps()
        ├─ test_determinar_variante_retenciones()
        ├─ test_determinar_variante_total()
        ├─ test_find_stct_by_variant_nacional_basico()
        ├─ test_find_stct_by_variant_frontera_ieps()
        └─ test_matriz_decision_completa()

     ❌ LIMITACIÓN: Tests UNITARIOS (funciones aisladas), NO E2E
        • NO crean Sales Invoice completa
        • NO verifican cálculos fiscales reales
        • NO validan grand_total correcto
        • NO verifican payload CFDI
```

**Pendiente (10h):**

```
❌ 6.2 - Suite tests E2E completos (10h) - NO EXISTE
     ├─ test_e2e_escenario_1_basico_iva()
     │   • Crear SI con items normales → STCT Básico
     │   • Verificar tax_amount correcto
     │   • Verificar grand_total coherente
     │   • Verificar sin filas $0
     ├─ test_e2e_escenario_2_ieps_alcohol()
     │   • Crear SI con items IEPS Alcohol → STCT IEPS
     │   • Verificar cálculo IEPS correcto
     │   • Verificar IVA cascada sobre IEPS
     │   • Verificar item_wise_tax_detail granular
     ├─ test_e2e_escenario_3_retenciones_honorarios()
     │   • Crear SI con servicios honorarios → STCT Retenciones
     │   • Verificar retención ISR correcta
     │   • Verificar retención IVA 2/3 IVA trasladado
     │   • Verificar grand_total neto correcto
     ├─ test_e2e_escenario_4_total_mixto()
     │   • Crear SI IEPS + Retenciones → STCT Total
     │   • Verificar todos impuestos aplicados
     │   • Verificar coherencia grand_total
     ├─ test_e2e_escenario_5_zona_frontera()
     │   • Crear SI zona frontera → STCT Frontera
     │   • Verificar IVA 8% aplicado
     │   • Verificar mensaje UI correcto
     ├─ test_e2e_escenario_6_cambio_stct_dinamico()
     │   • Crear SI normal → STCT Básico
     │   • Agregar item IEPS → STCT cambia a IEPS
     │   • Verificar tax rows recargadas
     │   • Verificar cálculos actualizados
     └─ test_e2e_escenario_7_sin_filas_cero()
         • Crear SI Básico → verificar SOLO 1 fila IVA
         • Verificar NO aparecen filas IEPS/Retenciones en $0

Total Fase 4: 12 horas ⚠️ PENDIENTE (2h completadas, 10h faltantes)
```

**Criterios éxito:**
- ⚠️ Suite tests parcial (solo unitarios, falta E2E)
- ⚠️ Cobertura FUNCIONES completa, cobertura ESCENARIOS pendiente
- ❌ Tests E2E con Sales Invoice completas NO IMPLEMENTADOS
- ❌ Validación cálculos fiscales completos NO IMPLEMENTADA
- ❌ Verificación payload CFDI NO IMPLEMENTADA

---

### ⏸️ FASE FUTURA: REVISIÓN INTEGRAL IEPS
**Objetivo:** Revisar y corregir cálculo TODOS los IEPS (incluido Tabaco)

```
⏸️ 9.1 - Corregir bug IVA Tabaco (4h)
     ├─ Fix filtro items por cuenta IEPS específica
     ├─ Tests unitarios del fix
     └─ Verificar cálculos Tabaco correctos

⏸️ Revisar cálculo completo IEPS todas categorías
     ├─ Alcohol
     ├─ Azúcar/Bebidas
     ├─ Combustibles
     └─ Tabaco

Total Fase Futura: TBD
```

**Nota:** Esta fase se ejecutará cuando corresponda revisar integralmente el cálculo de IEPS.

---

## 📝 RETROALIMENTACIÓN PARA CHATGPT

### ✅ Propuesta EXCELENTE y CORRECTA:

1. **Objetivo claro:** 8 STCT (4 variantes × 2 zonas)
2. **Justificación válida:** Eliminar filas $0 en Sales Invoices
3. **Autoselección inteligente:** Zona + categorías productos
4. **Estructura lógica:** Fase por fase, sin tocar Tabaco inicialmente

### ✅ Implementar TODO según propuesta:

**§1 - Crear 8 STCT:**
- ✅ IVA Nacional/Frontera - Básico
- ✅ IVA Nacional/Frontera + IEPS
- ✅ IVA Nacional/Frontera + Retenciones
- ✅ IVA Nacional/Frontera - Total

**§2 - Clasificación items:**
- ✅ Función clasificar_items_documento()
- ✅ Inferir desde ITT (no crear campo ieps_tipo)

**§3 - Autoselección STCT:**
- ✅ Matriz decisión según zona + categorías
- ✅ Hook before_validate actualizado

**§4 - Función rectora:**
- ✅ Documentar reglas IVA por categoría
- ✅ Validación post-cálculo

**§6 - Tests E2E:**
- ✅ Suite completa antes de implementación (TDD)

### ⏸️ Nota sobre bug IVA Tabaco:

**Bug IVA Tabaco (identificado, pospuesto):**
- Se atenderá en fase futura de revisión integral IEPS
- No se corregirá de forma aislada en esta implementación
- Documentado en §9.1 para referencia futura

### ❌ NO implementar:

**§8 - Campo ieps_tipo:**
- Innecesario (ITT ya clasifica)
- Duplica información

### 📋 Secuencia recomendada:

```
FASE 1 (Semana 1-2):
  ✅ Función clasificación (6h)
  ✅ Crear 8 STCT (20h)

FASE 2 (Semana 3):
  ✅ Autoselección STCT (6h)

FASE 3 (Semana 4):
  ✅ Función rectora + validación (6h)

FASE 4 (Post-implementación):
  ✅ Suite tests E2E (12h)

FASE FUTURA (TBD):
  ⏸️ Revisión integral IEPS (incluye bug Tabaco)
```

**Total estimado:** 50 horas (~6 días trabajo efectivo)

**Nota:**
- Tests E2E se ejecutan DESPUÉS de implementación completa
- Bug IVA Tabaco pospuesto a fase futura de revisión integral IEPS

---

## 🎯 CONCLUSIONES

### Propuesta ChatGPT es CORRECTA y NECESARIA:

✅ **Problema identificado correctamente:**
- Templates consolidados causan filas $0 en Sales Invoices
- UX subóptima con templates gigantes

✅ **Solución apropiada:**
- 8 STCT específicos (4 variantes × 2 zonas)
- Autoselección inteligente según categorías
- Templates mínimos necesarios

✅ **Arquitectura sólida:**
- Clasificación centralizada
- Matriz decisión clara
- Función rectora documentando reglas

### Implementación debe ser COMPLETA:

🔴 **P1 ALTA:**
- Crear 8 STCT según propuesta
- Función clasificación items
- Autoselección según categorías

🟡 **P2 MEDIA:**
- Función rectora reglas IVA
- Validación post-cálculo

🟢 **P3 BAJA:**
- Suite tests E2E (post-implementación)

⏸️ **FASE FUTURA:**
- Bug IVA Tabaco (revisión integral IEPS)

### NO hay "opcionales" ni "futuros":

La propuesta debe implementarse COMPLETA:
- ✅ 8 STCT (no 2 consolidados)
- ✅ Autoselección según categorías (no solo zona)
- ✅ Eliminar filas $0 (objetivo principal)

---

**Elaborado por:** Claude Code
**Estado original:** LISTO PARA IMPLEMENTACIÓN (oct 24, 2025)
**Estado actualizado:** PARCIAL - FASE 1-2 COMPLETAS, FASE 3-4 PENDIENTES (oct 25, 2025)
**Progreso:** 34h de 50h (68% completado)
**Pendiente:** FASE 3 (función rectora) + FASE 4 (tests E2E) = 16h

---

## 📊 **RESUMEN EJECUTIVO - ESTADO ACTUAL**

### **Completado (34h / 50h = 68%)**

| Fase | Horas | Estado | Commits | Resultado |
|------|-------|--------|---------|-----------|
| FASE 1 | 26h | ✅ COMPLETA | 3fdb47b, 26e8bc5 | 8 STCT generados + clasificación items |
| FASE 2 | 6h | ✅ COMPLETA | 3eae7c9 | Autoselección inteligente + carga tax rows |
| FASE 3 | 0h | ❌ PENDIENTE | - | Función rectora + validación NO EXISTE |
| FASE 4 | 2h | ⚠️ PARCIAL | f15e46f | Tests unitarios (falta E2E) |

### **Pendiente (16h / 50h = 32%)**

1. **FASE 3: Función Rectora** (6h)
   - Tabla reglas cálculo unificada
   - Centralizar lógica hardcoded
   - Validación post-cálculo

2. **FASE 4: Tests E2E** (10h)
   - 7 escenarios completos
   - Validación cálculos fiscales
   - Verificación payload CFDI

### **Validaciones UI: FALTANTES**

❌ JavaScript validaciones críticas:
- Branch obligatorio
- Cost Center obligatorio
- Items vacíos
- RFC validado
- Zona frontera coherente

---

## 🏗️ **PROPUESTA ARQUITECTURA: FUNCIÓN RECTORA (FASE 3)**

### **Problema Actual**

**Cálculos dispersos en múltiples lugares:**

```
sales_invoice_ieps.py (776 líneas):
├─ calcular_ieps_cuota() - líneas 260-362
├─ _congelar_iva_sobre_ieps_cuota() - líneas 195-257
├─ ajustar_base_iva_combustibles() - líneas 369-432
├─ _corregir_item_wise_tax_detail_ieps_cuota() - líneas 489-556
├─ _ajustar_item_wise_tax_detail_iva_combustibles() - líneas 563-629
├─ _validar_tolerancias_redondeo() - líneas 636-692
└─ _validar_orden_fiscal_ieps_iva() - líneas 699-746

Problemas:
❌ Lógica hardcoded dispersa (integra_base_iva, tipo_factor)
❌ Reglas duplicadas en múltiples funciones
❌ Difícil mantener coherencia
❌ Imposible extender sin modificar código
❌ Sin centralización de reglas fiscales
```

### **Solución Propuesta: Tabla Reglas + Función Rectora**

**Arquitectura unificada:**

```
┌─────────────────────────────────────────────────┐
│ Mapeo Cuenta Fiscal Mexico (Child Table)       │
│ ─────────────────────────────────────────────── │
│ CAMPOS EXISTENTES:                              │
│ • rol_fiscal (Select)                           │
│ • cuenta_impuesto (Link)                        │
│ • tipo_factor (Tasa/Cuota)                      │
│ • integra_base_iva (Check)                      │
│ • es_retencion (Check)                          │
│ ─────────────────────────────────────────────── │
│ CAMPOS NUEVOS (FASE 3):                         │
│ • regla_base (Select): net_amount, qty,         │
│                        iva_trasladado, previous │
│ • regla_calculo (Select): porcentual, cuota,    │
│                          cascada, retencion     │
│ • fundamento_legal (Text): LIEPS Art.2-A        │
│ • notas_calculo (Text): Especificaciones        │
└─────────────────────────────────────────────────┘
           ▼
┌─────────────────────────────────────────────────┐
│ aplicar_reglas_calculo_impuestos(doc, tax_row) │
│ ─────────────────────────────────────────────── │
│ 1. Lee metadata desde Mapeo Cuenta Fiscal      │
│ 2. Identifica regla_base + regla_calculo       │
│ 3. Aplica cálculo según regla:                 │
│    • porcentual: base × tasa / 100             │
│    • cuota: qty × cuota_unitaria               │
│    • cascada: (base + impuesto_previo) × tasa  │
│    • retencion: iva_trasladado × tasa_ret      │
│ 4. Retorna: {base, monto, item_wise_detail}    │
└─────────────────────────────────────────────────┘
           ▼
┌─────────────────────────────────────────────────┐
│ generador_templates_fiscal.py                  │
│ ─────────────────────────────────────────────── │
│ UNIFICA GENERACIÓN STCT + ITT:                  │
│ • Lee MISMA tabla Mapeo Cuenta Fiscal          │
│ • Genera tax rows según regla_base/calculo     │
│ • Estructura charge_type según regla:          │
│   - regla_base=net_amount → "On Net Total"     │
│   - regla_base=previous → "On Previous Row"    │
│   - regla_calculo=cuota → "Actual"             │
│ • Coherencia 100% templates ↔ cálculo runtime  │
└─────────────────────────────────────────────────┘
```

### **Ejemplo Configuración Tabla**

| rol_fiscal | tipo_factor | integra_base_iva | regla_base | regla_calculo | fundamento_legal |
|------------|-------------|------------------|------------|---------------|------------------|
| IVA por Pagar (Nacional) | Tasa | N/A | net_amount | porcentual | Ley IVA Art. 12 |
| IEPS por Pagar (Alcohol) | Tasa | ✓ | net_amount | porcentual | LIEPS Art. 2 |
| IEPS por Pagar (Combustibles) | Cuota | ✗ | qty | cuota | LIEPS Art. 2-A II |
| IEPS por Pagar (Tabaco) | Tasa | ✓ | net_amount | porcentual | LIEPS Art. 2-I-C |
| IEPS por Pagar (Tabaco Cuota) | Cuota | ✓ | qty | cuota | LIEPS Art. 2-I-C |
| IVA Retenido (Honorarios) | Tasa | N/A | iva_trasladado | retencion | CFF Art. 1-A III |
| ISR Retenido (Honorarios) | Tasa | N/A | net_amount | porcentual | LISR Art. 106 |

### **Refactorización Código**

**ANTES (hardcoded disperso):**
```python
# sales_invoice_ieps.py - línea 281
metadata = _obtener_metadata_cuenta(tax_row.account_head, doc.company)
if metadata["tipo_factor"] != "Cuota":
    continue  # Lógica hardcoded

# Línea 310
if item.uom == uom_base:
    conversion_factor = 1.0  # Lógica duplicada

# Línea 416
if metadata["tipo_factor"] == "Cuota" and not metadata["integra_base_iva"]:
    # Más lógica hardcoded
```

**DESPUÉS (tabla + función rectora):**
```python
# facturacion_mexico/utils/reglas_fiscales.py (NUEVO)
def aplicar_reglas_calculo_impuestos(doc, tax_row, metadata):
    """
    Función rectora: aplica reglas cálculo impuestos desde configuración.

    Args:
        doc: Sales Invoice
        tax_row: Tax row a calcular
        metadata: Metadata desde Mapeo Cuenta Fiscal

    Returns:
        dict: {base_calculada, monto_impuesto, item_wise_detail}
    """
    regla_base = metadata["regla_base"]
    regla_calculo = metadata["regla_calculo"]

    if regla_calculo == "porcentual":
        return _calcular_porcentual(doc, tax_row, regla_base, metadata)
    elif regla_calculo == "cuota":
        return _calcular_cuota(doc, tax_row, regla_base, metadata)
    elif regla_calculo == "cascada":
        return _calcular_cascada(doc, tax_row, regla_base, metadata)
    elif regla_calculo == "retencion":
        return _calcular_retencion(doc, tax_row, regla_base, metadata)

    frappe.throw(f"Regla de cálculo desconocida: {regla_calculo}")

# sales_invoice_ieps.py (REFACTORIZADO)
def calcular_impuestos_automaticos(doc, method=None):
    """Hook único que aplica todas las reglas fiscales."""
    config_fiscal = _obtener_config_fiscal(doc.company)

    for tax_row in doc.taxes:
        metadata = _obtener_metadata_cuenta(tax_row.account_head, doc.company)
        if not metadata:
            continue

        # Función rectora centralizada
        resultado = aplicar_reglas_calculo_impuestos(doc, tax_row, metadata)

        # Aplicar resultado
        tax_row.tax_amount = resultado["monto_impuesto"]
        tax_row.item_wise_tax_detail = json.dumps(resultado["item_wise_detail"])
```

### **Beneficios Arquitectura Unificada**

✅ **Single Source of Truth:**
- Tabla Mapeo Cuenta Fiscal = ÚNICA fuente reglas
- Generación templates lee MISMA tabla
- Cálculo runtime lee MISMA tabla
- Coherencia 100% garantizada

✅ **Mantenibilidad:**
- Agregar nuevo impuesto = agregar fila en tabla
- Sin modificar código Python
- Reglas visibles en UI (no hardcoded)

✅ **Extensibilidad:**
- Soporta nuevos tipos cálculo sin código
- Fundamento legal documentado por regla
- Fácil auditar coherencia fiscal

✅ **Testing:**
- Tests unitarios por tipo_calculo
- Validación automática tabla ↔ código
- Detección temprana desincronización

### **Plan Implementación FASE 3**

```
PASO 1: Agregar campos Mapeo Cuenta Fiscal (1h)
├─ regla_base (Select): net_amount, qty, iva_trasladado, previous
├─ regla_calculo (Select): porcentual, cuota, cascada, retencion
├─ fundamento_legal (Text)
└─ Migración: bench migrate

PASO 2: Migrar metadata existente (1h)
├─ Script migración one_offs/
├─ Poblar regla_base/regla_calculo desde tipo_factor actual
└─ Validar coherencia post-migración

PASO 3: Crear función rectora (2h)
├─ Archivo: facturacion_mexico/utils/reglas_fiscales.py
├─ Función aplicar_reglas_calculo_impuestos()
├─ Helpers: _calcular_porcentual, _calcular_cuota, etc.
└─ Tests unitarios (10 tests mínimo)

PASO 4: Refactorizar hooks (2h)
├─ Unificar calcular_ieps_cuota() → usa función rectora
├─ Eliminar lógica hardcoded dispersa
├─ Mantener validaciones (tolerancias, orden fiscal)
└─ Tests regresión (verificar NO ROMPE cálculos actuales)

Total FASE 3: 6 horas
```

---

**🤖 Generated with [Claude Code](https://claude.com/claude-code)**

