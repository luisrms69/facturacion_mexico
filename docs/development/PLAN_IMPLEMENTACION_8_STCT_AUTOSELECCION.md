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

### FASE 1: CREAR 8 STCT + CLASIFICACIÓN (Semana 1-2)
**Objetivo:** Implementar estructura base (8 templates + clasificación)

```
✅ 2.1 - Función clasificación items (6h)
     ├─ clasificar_items_documento()
     ├─ _inferir_categoria_desde_itt()
     ├─ Constantes CATEGORIAS_IEPS / CATEGORIAS_RETENCION
     └─ Tests unitarios clasificación

✅ 1.1 - Crear 8 STCT (20h)
     ├─ Modificar generador_templates_fiscal.py
     │   ├─ Generar 4 variantes base
     │   └─ × 2 zonas (Nacional/Frontera) = 8 totales
     ├─ Definir estructura filas por variante:
     │   ├─ Básico: solo IVA 0% + IVA base
     │   ├─ IEPS: IVA + slots IEPS (4 categorías)
     │   ├─ Retenciones: IVA + Ret IVA + Ret ISR
     │   └─ Total: todos los slots combinados
     ├─ Script generación para empresas existentes
     ├─ Tests generación templates
     └─ Ejecutar en dev/testing

✅ 1.2 - Normalizar descripciones (incluido en §1.1)

Total Fase 1: 26 horas
```

**Criterio éxito:**
- 8 STCT creados en todas las empresas ✅
- Nombres sin "16%"/"8%" → "Nacional"/"Frontera" ✅
- Descripciones normalizadas ✅

---

### FASE 2: AUTOSELECCIÓN STCT (Semana 3)
**Objetivo:** Implementar lógica autoselección inteligente

```
✅ 3.1 - Autoselección STCT según categorías (6h)
     ├─ Función seleccionar_stct_automatico()
     ├─ Matriz decisión (zona + tiene_ieps + tiene_ret)
     ├─ Hook before_validate() actualizado
     └─ Tests integración con §2.1

Total Fase 2: 6 horas
```

**Criterio éxito:**
- Autoselección funciona según matriz decisión ✅
- Sales Invoices SIN filas en $0 ✅
- Template cambia al agregar/quitar items ✅

---

### FASE 3: FUNCIÓN RECTORA + VALIDACIÓN (Semana 4)
**Objetivo:** Documentar reglas + validación extra

```
✅ 4.1 - Función rectora reglas IVA (4h)
     ├─ Constante REGLAS_IVA_POR_CATEGORIA
     ├─ Función aplicar_reglas_iva_por_categoria()
     └─ Tests unitarios reglas

✅ 4.2 - Validación post-cálculo (2h)
     └─ Hook validar_aplicacion_reglas_iva()

Total Fase 3: 6 horas
```

**Criterio éxito:**
- Reglas IVA documentadas explícitamente ✅
- Validación detecta inconsistencias ✅

---

### FASE 4: SUITE TESTS E2E (Post-implementación)
**Objetivo:** Validar implementación completa con tests E2E

```
✅ 6.1 - Crear suite tests E2E autoselección (12h)
     ├─ Test escenario Básico (solo Resto)
     ├─ Test escenario IEPS (Alcohol/Tabaco/etc)
     ├─ Test escenario Retenciones (Honorarios)
     ├─ Test escenario Total (mixto)
     ├─ Test zona frontera (IVA 8%)
     ├─ Test cambio STCT al agregar/quitar items
     └─ Test sin filas en $0

Total Fase 4: 12 horas
```

**Criterio éxito:**
- Suite tests E2E completa ✅
- Todos los tests PASANDO (green) ✅
- Cobertura escenarios principales ✅

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
**Estado:** LISTO PARA IMPLEMENTACIÓN
**Próximo paso:** Crear 8 STCT + Función clasificación (FASE 1)
**Estimación total:** 50 horas (~6 días)

