# 🧪 Guía de Testing - Cancelaciones Fiscales

Esta guía te ayuda a validar que el proceso de cancelaciones fiscales funciona correctamente desde la perspectiva del usuario.

## 🎯 **Objetivo**

Verificar que el sistema de cancelaciones fiscales:
- Procesa cancelaciones correctamente en FacturAPI
- Actualiza estados fiscales en la interfaz
- Permite re-facturación después de cancelación
- Mantiene integridad de datos

## 📋 **Precondiciones**

### Datos Requeridos
- [ ] Sales Invoice en estado `Submitted` con `fm_fiscal_status = "TIMBRADO"`
- [ ] Factura Fiscal México vinculada con UUID válido
- [ ] Cliente con datos fiscales completos (RFC, domicilio)
- [ ] Empresa con certificados y configuración fiscal válida

## 🔄 **Pasos de Testing**

### **1️⃣ Verificación Estado Inicial**

#### **👤 Acciones Usuario (UI Testing)**
1. **Navegar a Sales Invoice:**
   - Ir a Sales Invoice List
   - Abrir invoice en estado "TIMBRADO"
   - Verificar botones disponibles en UI

2. **Verificar información fiscal:**
   - Confirmar campo `fm_fiscal_status = "TIMBRADO"`
   - Verificar UUID presente en `fm_cfdi_uuid`
   - Revisar link a Factura Fiscal México

#### **Resultados Esperados:**
- ✅ Botón "Cancelar CFDI" visible
- ✅ Estado fiscal muestra "TIMBRADO"
- ✅ UUID visible en interfaz
- ✅ Link a Factura Fiscal México funcional

### **2️⃣ Proceso de Cancelación**

#### **👤 Acciones Usuario (Cancelación)**
1. **Iniciar cancelación:**
   - Click en botón "Cancelar CFDI"
   - Seleccionar motivo cancelación (02, 03, o 04)
   - Si es motivo 04: ingresar UUID de sustitución
   - Confirmar cancelación

2. **Monitorear proceso:**
   - Observar indicadores de progreso
   - Verificar mensajes de estado
   - Confirmar finalización proceso

#### **Resultados Esperados:**
- ✅ Modal de cancelación aparece
- ✅ Motivos de cancelación disponibles
- ✅ Campo UUID sustitución para motivo 04
- ✅ Proceso completa sin errores

### **3️⃣ Verificación Post-Cancelación**

#### **👤 Acciones Usuario (UI Update)**
1. **Verificar cambios UI:**
   - Refrescar página Sales Invoice
   - Verificar nuevo estado fiscal
   - Revisar botones disponibles
   - Confirmar cambios en campos

2. **Revisar Factura Fiscal México:**
   - Navegar a FFM vinculada
   - Verificar estado cancelación
   - Confirmar datos de cancelación

#### **Resultados Esperados:**
- ✅ `fm_fiscal_status` cambia a "CANCELADO"
- ✅ Botón "Cancelar CFDI" desaparece
- ✅ Botón "Re-Facturar" aparece
- ✅ FFM muestra estado cancelado

### **4️⃣ Testing Re-Facturación**

#### **👤 Acciones Usuario (Re-Facturación)**
1. **Iniciar re-facturación:**
   - Click en botón "Re-Facturar"
   - Confirmar acción en modal
   - Esperar creación nueva factura

2. **Verificar nueva factura:**
   - Revisar nueva Sales Invoice creada
   - Confirmar datos copiados correctamente
   - Verificar estado inicial nueva factura

#### **Resultados Esperados:**
- ✅ Nueva Sales Invoice creada
- ✅ Datos copiados de factura original
- ✅ Estado inicial: "BORRADOR"
- ✅ Nueva factura lista para timbrar

## 🎯 **Criterios de Éxito**

El testing es exitoso cuando:
- ✅ Cancelación procesa sin errores
- ✅ Estados fiscales se actualizan correctamente
- ✅ UI muestra información actualizada
- ✅ Re-facturación funciona apropiadamente
- ✅ Integridad de datos se mantiene

## ⚠️ **Casos de Error Comunes**

### Error de Conexión FacturAPI
- **Síntoma:** Timeout o error de red
- **Acción:** Verificar credenciales en site_config.json

### UUID No Válido
- **Síntoma:** Error "UUID no encontrado"
- **Acción:** Verificar que CFDI existe en FacturAPI

### Permisos Insuficientes
- **Síntoma:** Botón cancelación no visible
- **Acción:** Verificar rol usuario tiene permisos

---

*Para documentación técnica detallada, consultar archivo completo en buzola-internal*