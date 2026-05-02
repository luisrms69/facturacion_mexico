# Configuración Mapeos SAT - Guía Completa

**Versión:** 1.0
**Fecha:** 2025-10-16
**Audiencia:** Administradores de sitios nuevos
**Requisito:** Facturación México instalada y migrada

---

## 📋 Tabla de Contenidos

1. [¿Qué son los Mapeos SAT?](#qué-son-los-mapeos-sat)
2. [¿Por qué son obligatorios?](#por-qué-son-obligatorios)
3. [Campos Requeridos](#campos-requeridos)
4. [Paso a Paso](#paso-a-paso)
5. [Ejemplos Comunes](#ejemplos-comunes)
6. [Troubleshooting](#troubleshooting)
7. [Script Verificación](#script-verificación)

---

## ¿Qué son los Mapeos SAT?

Los **Mapeos SAT** conectan las cuentas contables de ERPNext con los códigos fiscales oficiales del SAT (México).

```
Cuenta ERPNext          →    Mapeo SAT           →    Payload CFDI
─────────────────────────────────────────────────────────────────────
2117001 - IVA 16%      →    002 | Tasa | IVA    →    <taxes type="002"
   Trasladado                                             factor="Tasa"
                                                          rate="0.160000"/>
```

**Sin mapeo → E4.8 bloquea el timbrado.**

---

## ¿Por qué son obligatorios?

### **Normativa SAT:**
El CFDI 4.0 requiere que cada impuesto incluya:
- Código impuesto SAT (001=ISR, 002=IVA, 003=IEPS)
- Tipo de factor (Tasa, Cuota, Exento)
- Indicador de retención (withholding)

### **Arquitectura E4-RO:**
El sistema de facturación lee **directamente** desde Sales Invoice sin cálculos:
- ✅ **Sales Invoice** = Fuente de verdad
- ✅ **Mapeos SAT** = Traducción a formato PAC
- ✅ **E4.8** = Validación bloqueante

Si falta el mapeo, E4.8 muestra error **antes de enviar al PAC**.

---

## Campos Requeridos

### **Tabla: Mapeos Cuentas Fiscales**

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `cuenta_impuesto` | Link | Cuenta contable ERPNext | `2117001 - IVA 16% Trasladado` |
| `impuesto_sat` | Select | Código SAT oficial | `002` (IVA) |
| `tipo_factor` | Select | Tasa, Cuota, Exento | `Tasa` |
| `nombre_impuesto_sat` | Data | Nombre para UI/logs | `IVA` |
| `es_retencion` | Check | ¿Es retención? | ☐ No (traslado) / ☑ Sí (retención) |

### **Valores Válidos:**

#### **impuesto_sat:**
- `001` - ISR (Impuesto Sobre la Renta)
- `002` - IVA (Impuesto al Valor Agregado)
- `003` - IEPS (Impuesto Especial sobre Producción y Servicios)

#### **tipo_factor:**
- `Tasa` - Porcentaje sobre base (más común)
- `Cuota` - Monto fijo por unidad
- `Exento` - No causa impuesto

#### **es_retencion:**
- ☐ **No marcado:** Impuesto trasladado (el cliente paga)
- ☑ **Marcado:** Impuesto retenido (el emisor retiene)

---

## Paso a Paso

### **1. Identificar Cuentas Fiscales Usadas**

Ejecutar script de verificación:

```bash
bench --site [tu-sitio] execute "facturacion_mexico.one_offs.verificar_mapeos_sat.run"
```

**Resultado esperado:**
```
📊 Cuentas fiscales encontradas: 19
❌ Sin mapeo configurado: 19

   2117001 - IVA 16% Trasladado
   2118001 - ISR Ret Arrendamiento
   ...
```

### **2. Abrir Configuración Fiscal México**

1. Ir a: **Awesome Bar** → `Configuracion Fiscal Mexico`
2. Scroll hasta: **Mapeos Cuentas Fiscales**

### **3. Agregar Mapeo por Cuenta**

Para cada cuenta listada en el script:

1. Click **Agregar Fila**
2. Llenar campos (ver [Ejemplos Comunes](#ejemplos-comunes))
3. **Guardar** (Ctrl+S)

### **4. Verificar Completitud**

Re-ejecutar script:

```bash
bench --site [tu-sitio] execute "facturacion_mexico.one_offs.verificar_mapeos_sat.run"
```

**Resultado esperado:**
```
✅ Mapeos completos: 19
🚀 Puede proceder con testing E4
```

---

## Ejemplos Comunes

### **IVA Trasladado (16%)**

| Campo | Valor |
|-------|-------|
| cuenta_impuesto | `2117001 - IVA 16% Trasladado` |
| impuesto_sat | `002` |
| tipo_factor | `Tasa` |
| nombre_impuesto_sat | `IVA` |
| es_retencion | ☐ (NO marcado) |

**Resultado CFDI:**
```xml
<taxes type="002" factor="Tasa" rate="0.160000" withholding="false"/>
```

---

### **ISR Retenido Honorarios (10%)**

| Campo | Valor |
|-------|-------|
| cuenta_impuesto | `2118001 - ISR Ret Honorarios` |
| impuesto_sat | `001` |
| tipo_factor | `Tasa` |
| nombre_impuesto_sat | `ISR` |
| es_retencion | ☑ (SÍ marcado) |

**Resultado CFDI:**
```xml
<taxes type="001" factor="Tasa" rate="0.100000" withholding="true"/>
```

---

### **IVA Retenido (10.66%)**

| Campo | Valor |
|-------|-------|
| cuenta_impuesto | `2119001 - IVA Ret Arrendamiento` |
| impuesto_sat | `002` |
| tipo_factor | `Tasa` |
| nombre_impuesto_sat | `IVA` |
| es_retencion | ☑ (SÍ marcado) |

**Resultado CFDI:**
```xml
<taxes type="002" factor="Tasa" rate="0.106666" withholding="true"/>
```

---

### **IEPS Cuota Fija**

| Campo | Valor |
|-------|-------|
| cuenta_impuesto | `2117002 - IEPS Combustibles Cuota` |
| impuesto_sat | `003` |
| tipo_factor | `Cuota` |
| nombre_impuesto_sat | `IEPS` |
| es_retencion | ☐ (NO marcado) |

**Resultado CFDI:**
```xml
<taxes type="003" factor="Cuota" rate="5.500000" withholding="false"/>
```

---

### **IVA Exento (0%)**

| Campo | Valor |
|-------|-------|
| cuenta_impuesto | `98765 - IVA 0% Exento` |
| impuesto_sat | `002` |
| tipo_factor | `Exento` |
| nombre_impuesto_sat | `IVA` |
| es_retencion | ☐ (NO marcado) |

**Resultado CFDI:**
```xml
<taxes type="002" factor="Exento" rate="0.000000" withholding="false"/>
```

---

## Troubleshooting

### **Error: "Cuenta 'XXX' no tiene mapeo SAT configurado"**

**Causa:** Falta agregar mapeo en Configuracion Fiscal Mexico.

**Solución:**
1. Ejecutar script verificación (identificar cuenta exacta)
2. Agregar mapeo siguiendo [Paso a Paso](#paso-a-paso)
3. Verificar con script

---

### **Error: "Payload incompleto - customer.tax_system faltante"**

**Causa:** Error E4.8 distinto a mapeos (datos customer incompletos).

**Solución:**
- Ver: `docs/user-guide/cfdi-troubleshooting.md` (sección customer data)
- Verificar campos SAT en Customer (RFC, Régimen Fiscal, Uso CFDI)

---

### **¿Cómo saber si una cuenta es retención?**

**Reglas generales:**

| Tipo Cuenta | es_retencion |
|-------------|--------------|
| Impuesto **trasladado** (cargo al cliente) | ☐ NO |
| Impuesto **retenido** (descuento al proveedor) | ☑ SÍ |
| IVA 16% normal | ☐ NO |
| ISR Ret Honorarios 10% | ☑ SÍ |
| IVA Ret 10.66% | ☑ SÍ |

**Pista visual:** Cuentas con "Ret" en el nombre suelen ser retenciones.

---

### **¿Puedo tener múltiples mapeos para misma cuenta?**

❌ **NO.** Cada `cuenta_impuesto` debe aparecer **una sola vez**.

Si necesitas:
- IVA 16% normal → Cuenta `2117001`
- IVA 8% frontera → Cuenta `2117002` (distinta)

Cada una con su propio mapeo.

---

## Script Verificación

### **Propósito:**
Identificar cuentas fiscales sin mapeo **antes de testing E4**.

### **Ubicación:**
```
facturacion_mexico/one_offs/verificar_mapeos_sat.py
```

### **Ejecución:**
```bash
bench --site [tu-sitio] execute "facturacion_mexico.one_offs.verificar_mapeos_sat.run"
```

### **Output:**
```
======================================================================
VERIFICACIÓN MAPEOS SAT - [tu-sitio]
======================================================================

📊 Cuentas fiscales encontradas: 5

✅ MAPEOS COMPLETOS (3):
   2117001 - IVA 16% Trasladado
      → IVA (002)
      → Factor: Tasa
      → Es retención: No

⚠️  MAPEOS INCOMPLETOS (1):
   2118001 - ISR Ret Honorarios
      FALTANTES: es_retencion
      Estado actual:
         impuesto_sat: 001
         tipo_factor: Tasa
         nombre_impuesto_sat: ISR
         es_retencion: VACÍO

❌ MAPEOS FALTANTES (1):
   2119001 - IVA Ret Arrendamiento
      → No existe mapeo en 'Configuracion Fiscal Mexico'

======================================================================
RESUMEN:
======================================================================
Total cuentas usadas:      5
✅ Mapeos completos:       3
⚠️  Mapeos incompletos:     1
❌ Sin mapeo configurado:  1
```

### **Características:**
- ✅ Solo lectura (no modifica BD)
- ✅ Lista cuentas de Sales Invoices reales
- ✅ Identifica campos faltantes específicos
- ✅ Safe para ejecutar múltiples veces

---

## Checklist Setup Nuevo Sitio

- [ ] 1. Instalar facturacion_mexico app
- [ ] 2. Ejecutar `bench --site [sitio] migrate`
- [ ] 3. Crear Sales Invoices de prueba con taxes
- [ ] 4. Ejecutar script verificación mapeos
- [ ] 5. Completar mapeos en Configuracion Fiscal Mexico
- [ ] 6. Re-ejecutar script (verificar 0 faltantes)
- [ ] 7. Probar timbrado con factura prueba
- [ ] 8. Verificar XML generado contiene taxes correctos

---

## Referencias

- **E4-RO Architecture:** `docs/audit/reporte-e4-implementacion-2025-10-08.md`
- **CFDI 4.0 Spec:** Anexo 20 SAT (Catálogo Impuestos)
- **Testing E4:** `docs/testing/planes/plan-fiscal-implementacion-mx-e0-e8/`
- **Troubleshooting General:** `docs/user-guide/cfdi-troubleshooting.md`

---

**Última actualización:** 2025-10-16
**Versión:** 1.0
**Mantenedor:** Facturación México Team
