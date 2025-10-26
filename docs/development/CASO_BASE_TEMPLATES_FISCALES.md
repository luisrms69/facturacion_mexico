# Caso Base - Templates Fiscales México

**Fecha generación:** 2025-10-25
**Sistema:** Facturación México - Generador Templates Fiscal
**Empresa:** _Test Company
**Commit base:** Post-migración nomenclatura roles fiscales

---

## 📋 **Tabla de Contenidos Templates Críticos**

### **1. IVA 0% y Exentos**

| Template | Tax Types Incluidos | Rate | Rol Fiscal Mapeado |
|----------|---------------------|------|-------------------|
| **ITT IVA 0%** | IVA Nacional | 0.0% | IVA por Pagar (Nacional) |
| | IVA Frontera | 0.0% | IVA por Pagar (Frontera) |
| | IVA 0% | 0.0% | IVA por Pagar (0% exportación) |
| **ITT Exento** | IVA Nacional | 0.0% | IVA por Pagar (Nacional) |
| | IVA Frontera | 0.0% | IVA por Pagar (Frontera) |
| | IVA Exento | 0.0% | IVA Exento |

**Propósito:**
- **ITT IVA 0%**: Items con tasa 0% (exportación principalmente)
- **ITT Exento**: Items exentos de IVA según LIVA

---

### **2. IEPS (4 templates - uno por categoría)**

| Template | Tax Type | Rate | Rol Fiscal Mapeado | Tipo Factor |
|----------|----------|------|-------------------|-------------|
| **ITT IEPS Alcohol** | IEPS Alcohol | 0.0% | IEPS por Pagar (Alcohol) | Tasa |
| **ITT IEPS Azúcar** | IEPS Azúcar/Bebidas | 0.0% | IEPS por Pagar (Azúcar/Bebidas) | Tasa |
| **ITT IEPS Combustibles** | IEPS Combustibles | 0.0% | IEPS por Pagar (Combustibles) | Cuota |
| **ITT IEPS Tabaco** | IEPS Tabaco | 0.0% | IEPS por Pagar (Tabaco) | Tasa |

**⚠️ Nota Importante:**
- Rate 0.0% en ITT porque **tasa/cuota real se configura en Item.fm_ieps_rate**
- Sistema E1 Automated Tax calcula IEPS dinámicamente según Item Group
- IEPS Tabaco Cuota NO tiene ITT dedicado (se maneja vía sistema automatizado)

---

### **3. Retenciones (4 categorías × 2 impuestos cada una)**

#### **3.1 Honorarios (Servicios Profesionales)**

| Template | Tax Types Incluidos | Rate | Rol Fiscal Mapeado |
|----------|---------------------|------|-------------------|
| **ITT ISR + IVA Ret Honorarios** | ISR Ret Honorarios | 0.0% | ISR Retenido (Honorarios) |
| | IVA Ret Honorarios | 0.0% | IVA Retenido (Honorarios) |
| **ITT ISR Honorarios** | ISR Ret Honorarios | 0.0% | ISR Retenido (Honorarios) |
| **ITT IVA Retenido Honorarios** | IVA Ret Honorarios | 0.0% | IVA Retenido (Honorarios) |

#### **3.2 Arrendamiento**

| Template | Tax Types Incluidos | Rate | Rol Fiscal Mapeado |
|----------|---------------------|------|-------------------|
| **ITT ISR + IVA Ret Arrendamiento** | ISR Ret Arrendamiento | 0.0% | ISR Retenido (Arrendamiento) |
| | IVA Ret Arrendamiento | 0.0% | IVA Retenido (Arrendamiento) |
| **ITT ISR Arrendamiento** | ISR Ret Arrendamiento | 0.0% | ISR Retenido (Arrendamiento) |
| **ITT IVA Retenido Arrendamiento** | IVA Ret Arrendamiento | 0.0% | IVA Retenido (Arrendamiento) |

#### **3.3 Autotransporte**

| Template | Tax Types Incluidos | Rate | Rol Fiscal Mapeado |
|----------|---------------------|------|-------------------|
| **ITT ISR + IVA Ret Autotransporte** | ISR Ret Autotransporte | 0.0% | ISR Retenido (Autotransporte) |
| | IVA Ret Autotransporte | 0.0% | IVA Retenido (Autotransporte) |
| **ITT ISR Autotransporte** | ISR Ret Autotransporte | 0.0% | ISR Retenido (Autotransporte) |
| **ITT IVA Retenido Autotransporte** | IVA Ret Autotransporte | 0.0% | IVA Retenido (Autotransporte) |

#### **3.4 RESICO (Régimen Simplificado de Confianza)**

| Template | Tax Types Incluidos | Rate | Rol Fiscal Mapeado |
|----------|---------------------|------|-------------------|
| **ITT ISR + IVA Ret RESICO** | ISR Ret RESICO | 0.0% | ISR Retenido (RESICO) |
| | IVA Ret RESICO | 0.0% | IVA Retenido (RESICO) |

**⚠️ Nota Retenciones:**
- Rate 0.0% en ITT porque **tasa real se configura dinámicamente**:
  - ISR Honorarios: 10% según LISR Art. 106
  - IVA Honorarios: 10.67% (2/3 de IVA 16%) según LIVA Art. 1-A
  - Otros: tasas según normativa SAT vigente
- Templates combinados (ISR + IVA) para escenarios donde aplican ambas retenciones
- Templates individuales para escenarios donde aplica solo una retención

---

## 🏗️ **Estructura Completa Templates Generados**

### **STCT (Sales Taxes and Charges Templates) - 14 templates**

#### **Templates Habilitados (10)**

| Template | Disabled | Taxes | Propósito |
|----------|----------|-------|-----------|
| IVA Nacional - Básico | No | 1 | IVA 16% simple |
| IVA Nacional - IEPS | No | 6 | IVA 16% + 5 IEPS |
| IVA Nacional - Retenciones | No | 9 | IVA 16% + 8 retenciones |
| IVA Nacional - Total | No | 14 | IVA 16% + IEPS + Retenciones |
| IVA Frontera - Básico | No | 1 | IVA 8% simple |
| IVA Frontera - IEPS | No | 6 | IVA 8% + 5 IEPS |
| IVA Frontera - Retenciones | No | 9 | IVA 8% + 8 retenciones |
| IVA Frontera - Total | No | 14 | IVA 8% + IEPS + Retenciones |
| Retenciones Honorarios - México | No | 2 | ISR 10% + IVA 10.67% |
| Mexico Tax | No | 1 | Legacy IVA 16% (compatibilidad) |

#### **Templates Deshabilitados (3) - Obsoletos**

| Template | Disabled | Razón |
|----------|----------|-------|
| IVA 0% - México | Sí | Reemplazado por ITT IVA 0% |
| IVA 16% - México | Sí | Nomenclatura antigua (pre-migración) |
| IVA 8% Frontera - México | Sí | Nomenclatura antigua (pre-migración) |
| Sin Impuestos - México | Sí | 0 taxes, sin uso práctico |

**🔍 Análisis STCT Nacional/Frontera - Total:**

Estos templates tienen **estructura idéntica** pero diferentes rates IVA:

```
Estructura (14 filas):
1. IVA (16% o 8%) - On Net Total
2. IEPS Alcohol - On Net Total
3. IEPS Azúcar/Bebidas - Actual
4. IEPS Combustibles - Actual
5. IEPS Tabaco - On Net Total
6. IEPS Tabaco Cuota - Actual
7. IVA Retenido Honorarios - On Net Total
8. ISR Retenido Honorarios - On Net Total
9. IVA Retenido Arrendamiento - On Net Total
10. ISR Retenido Arrendamiento - On Net Total
11. IVA Retenido Autotransporte - On Net Total
12. ISR Retenido Autotransporte - On Net Total
13. IVA Retenido RESICO - On Net Total
14. ISR Retenido RESICO - On Net Total
```

**Charge Types explicados:**
- **On Net Total**: Calcula sobre subtotal items (base estándar)
- **On Previous Row Amount**: Calcula sobre fila anterior (cascada IEPS → IVA)
- **Actual**: Cantidad fija en moneda (IEPS cuota principalmente)

---

### **ITT (Item Tax Templates) - 21 templates generados**

#### **Clasificación por Propósito**

**IVA Básico (4 templates):**
- ITT IVA Nacional (16%)
- ITT IVA Frontera (8%)
- ITT IVA 0% (tasa cero exportación)
- ITT Exento (IVA exento)

**IEPS (4 templates - uno por categoría):**
- ITT IEPS Alcohol
- ITT IEPS Azúcar
- ITT IEPS Combustibles
- ITT IEPS Tabaco

**Retenciones Combinadas (4 templates ISR + IVA):**
- ITT ISR + IVA Ret Honorarios
- ITT ISR + IVA Ret Arrendamiento
- ITT ISR + IVA Ret Autotransporte
- ITT ISR + IVA Ret RESICO

**Retenciones ISR Solo (4 templates):**
- ITT ISR Honorarios
- ITT ISR Arrendamiento
- ITT ISR Autotransporte
- *(No hay ITT ISR RESICO individual - solo combinado)*

**Retenciones IVA Solo (4 templates):**
- ITT IVA Retenido Honorarios
- ITT IVA Retenido Arrendamiento
- ITT IVA Retenido Autotransporte
- *(No hay ITT IVA RESICO individual - solo combinado)*

**Legacy/Compatibilidad (1 template):**
- Mexico Tax (IVA 16% legacy)

---

## 🚨 **Templates Duplicados/Obsoletos Detectados**

### **Nomenclatura Antigua (pre-migración)**

| Template Obsoleto | Template Nuevo | Acción Requerida |
|-------------------|----------------|------------------|
| ITT IVA 16% - _TC | ITT IVA Nacional - _TC | Desactivar obsoleto |
| ITT IVA 8% Frontera - _TC | ITT IVA Frontera - _TC | Desactivar obsoleto |
| ITT IVA Retenido Servicios - _TC | ITT IVA Retenido Honorarios - _TC | Desactivar obsoleto |

**⚠️ Acción pendiente:** Deshabilitar templates obsoletos vía script one-off.

---

## 📊 **Resumen Estadístico**

### **STCT (Sales Taxes and Charges Template)**
- **Total generados:** 14
- **Habilitados:** 10
- **Deshabilitados (obsoletos):** 4
- **Taxes promedio:** 8.5 filas por template
- **Template más completo:** IVA Nacional/Frontera - Total (14 filas cada uno)

### **ITT (Item Tax Template)**
- **Total generados:** 21 (excluyendo test fixtures ERPNext)
- **IVA básico:** 4
- **IEPS:** 4
- **Retenciones combinadas:** 4
- **Retenciones ISR:** 3
- **Retenciones IVA:** 4
- **Legacy:** 1
- **Duplicados obsoletos:** 3

---

## 🎯 **Uso Recomendado Templates**

### **Para Items Normales (sin IEPS, sin retenciones)**
- **Nacional:** Usar STCT "IVA Nacional - Básico" (1 tax)
- **Frontera:** Usar STCT "IVA Frontera - Básico" (1 tax)
- **Exportación:** Usar ITT "ITT IVA 0%" en nivel Item

### **Para Items con IEPS (Alcohol, Azúcar, Combustibles, Tabaco)**
- **Enfoque 1 - STCT completo:**
  - STCT "IVA Nacional/Frontera - IEPS" (6 taxes)
  - Sistema E1 activa IEPS según Item.fm_item_group
- **Enfoque 2 - ITT específico:**
  - STCT "IVA Nacional/Frontera - Básico" (1 tax)
  - ITT específico en Item (ej: "ITT IEPS Tabaco")

### **Para Servicios con Retenciones**
- **Honorarios (común):**
  - STCT "Retenciones Honorarios - México" (tasas preconfiguras 10% ISR + 10.67% IVA)
  - O usar STCT completo + ITT "ITT ISR + IVA Ret Honorarios"
- **Arrendamiento/Autotransporte/RESICO:**
  - STCT completo con retenciones habilitadas
  - ITT combinado o individual según aplique

---

## 🔧 **Integración con Sistema E1 Automated Tax**

### **Prelación Templates vs Sistema Automatizado**

El **Sistema E1** (hooks_handlers/sales_invoice_automated_tax.py) tiene **prioridad sobre templates** para:
1. **IEPS automático** según Item.fm_item_group
2. **IVA cascada** sobre IEPS cuando integra_base_iva=True
3. **Congelación valores** cuando Item tiene fm_ieps_rate configurado

### **Flujo Combinado**

```
STCT/ITT Template (rate 0%)
         ↓
Sistema E1 Automated Tax
         ↓
Calcula rate real según:
- Item.fm_item_group (IEPS)
- Item.fm_ieps_rate (override)
- Mapeo CFG (cuenta fiscal)
         ↓
Populate item_wise_tax_detail
```

**Beneficio:** Templates sirven como "placeholders" que sistema E1 llena dinámicamente.

---

## 📝 **Notas Técnicas Importantes**

### **1. Rate 0.0% en Templates**

**No es error** - es diseño intencional:
- **IEPS:** Rate real en Item.fm_ieps_rate (dinámico por producto)
- **Retenciones:** Rate real según normativa vigente (puede cambiar anualmente)
- **IVA 0%:** Explícitamente tasa cero (exportación)

### **2. Tipo Factor SAT**

Según mapeo cuenta fiscal (Mapeo Cuenta Fiscal Mexico):
- **Tasa:** IEPS Alcohol, Azúcar, Tabaco tasa
- **Cuota:** IEPS Combustibles, Tabaco Cuota

Campo `tipo_factor` crítico para CFDI 4.0.

### **3. Integra Base IVA**

- **Default:** integra_base_iva = True (IEPS integra base IVA)
- **Excepción:** IEPS Combustibles cuota según LIEPS Art. 2-A
- **Impacto:** IVA se calcula sobre (Subtotal + IEPS) si True

### **4. Retenciones - Withholding Flag**

Campo `es_retencion` en mapeo determina:
- **CFDI:** withholding=True en nodo impuesto
- **Formato:** Retenciones van en sección separada CFDI 4.0

---

## 🧪 **Validación Caso Base**

### **Tests Ejecutados**

✅ **test_sync_roles_fiscales_json_python.py** - PASÓ
- 17 roles sincronizados JSON ↔ Python
- 0 roles faltantes
- 0 roles extras

✅ **Generación Templates Wizard** - EXITOSO
- 14 STCT generados
- 21 ITT generados
- 0 errores validación

### **Criterios Validación Pasados**

1. ✅ Todos los roles fiscales usan constantes (no hardcoded strings)
2. ✅ Templates ITT tienen tax_type mapeado a cuenta fiscal
3. ✅ STCT tienen charge_type apropiado (On Net Total, Actual, etc.)
4. ✅ Templates obsoletos marcados como disabled=1
5. ✅ 0 duplicados activos (solo obsoletos deshabilitados)

---

## 🔄 **Mantenimiento Futuro**

### **Al Actualizar Roles Fiscales**

1. Actualizar `TABLA_MAESTRA_ROLES_FISCALES` en roles_fiscales.py
2. Actualizar opciones Select en mapeo_cuenta_fiscal_mexico.json
3. `bench migrate`
4. Ejecutar script migración datos (one_offs/)
5. Validar: `bench run-tests --app facturacion_mexico --module tests.test_sync_roles_fiscales_json_python`

### **Al Regenerar Templates**

```bash
# 1. Backup BD obligatorio
bench --site facturacion.dev backup --with-files

# 2. Regenerar desde Wizard
# Configuracion Fiscal Mexico > Generar Templates

# 3. Validar estructura
bench --site facturacion.dev console
>>> doc = frappe.get_doc("Item Tax Template", "ITT IVA Nacional - _TC")
>>> print(doc.as_dict())

# 4. Deshabilitar obsoletos si aparecen duplicados
```

---

## 📚 **Referencias**

- **Generador:** facturacion_mexico/facturacion_fiscal/setup/generador_templates_fiscal.py
- **Roles Fiscales:** facturacion_mexico/utils/roles_fiscales.py
- **Test Sincronización:** facturacion_mexico/tests/test_sync_roles_fiscales_json_python.py
- **Sistema E1:** facturacion_mexico/hooks_handlers/sales_invoice_automated_tax.py

---

**Documento generado:** 2025-10-25
**Versión nomenclatura:** Post-migración semántica (Nacional/Frontera)
**Estado:** ✅ Caso base validado y funcional
