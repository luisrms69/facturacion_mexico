# Solución IEPS Tabaco Doble (Tasa 160% + Cuota $0.35/cigarro)

**Fecha:** 2025-10-21
**Contexto:** Implementación IEPS Cuota variable (E4)

---

## 🎯 Problema

Cigarros tienen **2 tipos IEPS simultáneos** según Ley IEPS Art. 2-I-C:
1. **IEPS Tasa 160%** sobre precio de enajenación
2. **IEPS Cuota variable** por cigarro individual (ej: $0.35/cigarro en 2025)

Actualmente sistema solo soporta 1 IEPS por item.

---

## ✅ Solución Aprobada

### **Arquitectura UOM:**

**Catálogo SAT c_ClaveUnidad:**
- **XPA** = Cajetilla (Pack) ✅ EXISTE EN CATÁLOGO SAT
- **H87** = Pieza (cigarro individual) ✅ EXISTE EN CATÁLOGO SAT

**Estrategia:**
1. **Tabla "IEPS Cuota SAT"** define impuesto por **cigarro individual (H87)**
2. **Item** usa **XPA (Cajetilla)** como UOM principal
3. **UOM Conversion** define relación: 1 XPA = 20 H87
4. **Sistema** calcula automáticamente unidades base

---

## 📋 Configuración Paso a Paso

### **PASO 1: Tabla "IEPS Cuota SAT"**

Crear registro:
```
DocType: IEPS Cuota SAT
- company: CONSULTORIA EN NEGOCIOS Y APLICACIONES SA DE CV
- clave_prod_serv: 53131604 (Cigarros - catálogo SAT)
- descripcion: Cigarros rubio cajetilla
- uom: H87 (cigarro individual, NO cajetilla)
- cuota: 0.35 (pesos por cigarro)
- cuenta_ieps: 2117005 - IEPS Tabaco Cuota
- vigencia_desde: 2025-01-01
- vigencia_hasta: (dejar vacío si vigente indefinidamente)
```

**⚠️ IMPORTANTE:**
- `uom` debe ser **H87** (cigarro individual), NO XPA (cajetilla)
- `cuota` es monto variable según normativa SHCP (actualizable)

---

### **PASO 2: Item Configuration**

**Item Master: Cajetilla Marlboro**
```
Item Code: ITEM-CIGARRO-001
Item Name: Cigarros Marlboro Cajetilla 20 unidades
Stock UOM: XPA - Cajetilla
fm_producto_servicio_sat: 53131604
```

**UOM Conversion:**
```
Item → UOMs → Add Row:
- UOM: H87 - Pieza
- Conversion Factor: 20.0
```

**Interpretación:** 1 Cajetilla (XPA) = 20 Cigarros (H87)

---

### **PASO 3: Item Tax Template**

**ITT: IEPS Tabaco Doble + IVA 16%**
```json
{
  "title": "IEPS Tabaco 160% + Cuota + IVA 16%",
  "taxes": [
    {
      "tax_type": "2117001 - IEPS Tabaco Tasa 160%",
      "tax_rate": 160.0,
      "charge_type": "On Net Total"
    },
    {
      "tax_type": "2117005 - IEPS Tabaco Cuota",
      "tax_rate": 0.0,
      "charge_type": "On Net Total"
    },
    {
      "tax_type": "2116001 - IVA 16%",
      "tax_rate": 16.0,
      "charge_type": "On Previous Row Total"
    }
  ]
}
```

**⚠️ ORDEN CRÍTICO:**
1. IEPS Tasa 160% (primero)
2. IEPS Cuota (segundo)
3. IVA 16% (último, sobre precio + ambos IEPS)

---

## 🧮 Ejemplo Cálculo

**Sales Invoice:**
- Item: Cajetilla Marlboro
- Qty: 1 XPA
- Price: $50.00/cajetilla

**Cálculos automáticos:**

1. **Conversión UOM:**
   - 1 XPA × 20 H87/XPA = 20 cigarros

2. **IEPS Tasa 160%:**
   - Base: $50.00
   - Importe: $50.00 × 160% = $80.00

3. **IEPS Cuota (hook automático):**
   - UOM base tabla SAT: H87
   - Cuota tabla SAT: $0.35/cigarro
   - Cantidad base: 20 cigarros
   - Importe: 20 × $0.35 = $7.00

4. **IVA 16%:**
   - Base: $50.00 + $80.00 + $7.00 = $137.00
   - Importe: $137.00 × 16% = $21.92

5. **Total:**
   - Subtotal: $50.00
   - IEPS Tasa: $80.00
   - IEPS Cuota: $7.00
   - IVA: $21.92
   - **TOTAL: $158.92**

---

## 📄 XML Esperado

```xml
<cfdi:Concepto ClaveProdServ="53131604"
               Cantidad="1"
               ClaveUnidad="XPA"
               Unidad="Cajetilla"
               Descripcion="Cigarros Marlboro Cajetilla 20 unidades"
               ValorUnitario="50.000000"
               Importe="50.000000"
               ObjetoImp="02">
  <cfdi:Impuestos>
    <cfdi:Traslados>
      <!-- IEPS Tasa 160% -->
      <cfdi:Traslado Base="50.00"
                     Impuesto="003"
                     TipoFactor="Tasa"
                     TasaOCuota="1.600000"
                     Importe="80.00"/>

      <!-- IEPS Cuota $0.35/cigarro -->
      <cfdi:Traslado Base="20.00"
                     Impuesto="003"
                     TipoFactor="Cuota"
                     TasaOCuota="0.350000"
                     Importe="7.00"/>

      <!-- IVA 16% sobre $137 -->
      <cfdi:Traslado Base="137.00"
                     Impuesto="002"
                     TipoFactor="Tasa"
                     TasaOCuota="0.160000"
                     Importe="21.92"/>
    </cfdi:Traslados>
  </cfdi:Impuestos>
</cfdi:Concepto>
```

**Desglose XML:**
- `ClaveUnidad="XPA"` → Cajetilla (UOM factura)
- `Cantidad="1"` → 1 cajetilla
- IEPS Cuota `Base="20.00"` → 20 cigarros (conversión automática)
- IEPS Cuota `TasaOCuota="0.350000"` → Cuota de tabla SAT

---

## 🔧 Cambios Código Implementados

### **1. Constantes Fiscales**
```python
# facturacion_fiscal/config/constantes_fiscales.py

TASAS_IEPS = {
    "tabaco_cuota": {
        "tasa": 0.0,
        "descripcion": "IEPS Tabaco (Cuota variable por cigarro)",  # ← NO hardcoded
        "charge_type": "On Net Total",
        "iva_aplicable": True,
    },
}

COMBINACIONES_ALCANCE = {
    "ieps_tabaco": [
        "IEPS por Pagar (Tabaco)",  # Tasa 160%
        "IEPS por Pagar (Tabaco Cuota)",  # Cuota variable
        "IVA por Pagar (16%)",
    ],
}
```

### **2. Mapeos SAT**
```python
# config/sat_tipo_factor.py

"IEPS por Pagar (Tabaco Cuota)": {
    "tipo_factor": CUOTA,
    "impuesto_sat": "003",
    "nombre_sat": "IEPS",
    "descripcion": "IEPS Tabaco cuota variable/cigarro (según tabla SAT)",
},
```

### **3. Hook (sin cambios necesarios)**
`sales_invoice_ieps.py` ya soporta múltiples IEPS por item.

### **4. Timbrado API (sin cambios necesarios)**
`timbrado_api.py` ya itera todos los taxes del item correctamente.

---

## ⚠️ Validaciones Pendientes

1. **Generador Templates (`generador_templates_fiscal.py`):**
   - Validación actual asume 1 IEPS por item
   - Necesita ajuste para permitir múltiples IEPS (Tasa + Cuota)

2. **Orden ITT:**
   - Validar que IEPS Tasa aparezca ANTES de IEPS Cuota
   - Validar que ambos IEPS aparezcan ANTES del IVA

---

## 📊 Testing Pendiente

1. Crear Item test con UOM XPA y conversión 20 H87
2. Crear registro tabla IEPS Cuota SAT para cigarros
3. Crear/actualizar ITT con 3 taxes
4. Generar factura test
5. Verificar XML cumple especificación SAT
6. Timbrar en sandbox PAC

---

## 🔗 Referencias

- **Catálogo SAT c_ClaveUnidad:** http://pys.sat.gob.mx/PyS/catUnidades.aspx
- **XPA (Cajetilla):** https://veinte.mx/catalogos/clave/XPA
- **Ley IEPS Art. 2-I-C:** Cigarros y otros tabacos labrados
- **SHCP Cuotas vigentes:** Revisar DOF para actualizaciones anuales

---

**🤖 Generated with Claude Code**
