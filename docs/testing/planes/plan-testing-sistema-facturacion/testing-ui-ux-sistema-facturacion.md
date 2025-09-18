# 🧪 Plan Testing Sistema Facturación México

**Objetivo:** Validación completa UI/UX y lógica de negocio - Sistema facturación fiscal mexicana
**Meta temporal:** 6 minutos máximo por caso de prueba
**Cobertura:** Desde operaciones básicas hasta flujos complejos con addendas y formas de pago especiales

---

## 📋 **Configuración Base Testing**

### **Datos Reales Sistema (facturacion.dev)**
```yaml
Empresa Testing:
  - Nombre: "_Test Company"
  - RFC: No configurado
  - Sitio: facturacion.dev

Clientes Reales con RFC (5 principales):
  - "CONCESIONARIA VUELA COMPAÑIA DE AVIACION": Vuela Compañía (RFC: CVA041027H80)
  - "Cervecería Cuauhtémoc Moctezuma S.A.": CCM (RFC: CCM920814BC1)
  - "Pemex Transformación Industrial": Pemex TI (RFC: PTI850715XX1)
  - "Liverpool S.A. de C.V.": Liverpool (RFC: LIV921201P24)
  - "Telmex S.A.B. de C.V.": Telmex (RFC: TEL8503159G1)

Productos Disponibles (8 seleccionados):
  - "Servicio E2E Test": Servicio de Testing E2E (UOM: E48 - Servicio)
  - "Test Item Default": Test Item Default (UOM: Nos)
  - "138-CMS Shoe": 138-CMS Shoe (UOM: _Test UOM)
  - "_Test Item With Item Tax Template": Con impuestos (UOM: _Test UOM)
  - "_Test Serialized Item": Producto serializado (UOM: _Test UOM)
  - "_Test Non Stock Item": Producto no stock (UOM: _Test UOM)
  - "_Test FG Item": Producto terminado (UOM: _Test UOM)
  - "_Test Variant Item": Producto con variantes (UOM: _Test UOM)

Centros de Costo:
  - "Main - _TC": Main (_Test Company)
  - "_Test Company - _TC": _Test Company (_Test Company)

✅ CONFIGURACIÓN FISCAL VÁLIDA:
  - ✅ Clientes con RFC reales del SAT
  - ✅ 18 clientes disponibles con RFC válidos
  - ⚠️ Empresa "_Test Company" sin RFC (configurar si necesario)
  - 🎯 Testing incluye UI/UX + validación fiscal básica
```

### **Nomenclatura Evidencias**
```
Formato: TC-{nivel}-{numero}-{descripcion}-{gate}.png
Ejemplo: TC-B-001-crear-factura-G02.png

Niveles:
- B: Básico (1-20)
- I: Intermedio (21-40)
- A: Avanzado (41-62)

Gates:
- G01: Estado inicial
- G02: Datos capturados
- G03: Validación exitosa
- G04: Resultado final
```

---

## 🟢 **NIVEL BÁSICO (1-20): Operaciones Fundamentales**

### **TC-B-001: Crear Factura Simple**
**Tiempo objetivo:** 4 min | **Gates:** 4 evidencias

**Preparación:**
- Cliente: "CONCESIONARIA VUELA COMPAÑIA DE AVIACION" (RFC: CVA041027H80)
- Producto: "Servicio E2E Test"
- Importe: $1,000.00 MXN
- Centro costo: "Main - _TC"

**Ejecución:**
1. **G01:** Sales Invoice nuevo (pantalla inicial limpia)
2. **G02:** Cliente y producto seleccionados, importe calculado
3. **G03:** Submit exitoso, documento en estado "Submitted"
4. **G04:** Botón "Timbrar Factura" visible y activo

**Invariantes UI/UX:**
- Cliente seleccionado correctamente de dropdown
- Producto autocompletado funcionando
- Cálculos automáticos funcionando
- Botón fiscal aparece después de Submit
- Estados documento correctos en interfaz

**Nota:** Cliente con RFC real. Puede proceder con timbrado si empresa tiene RFC configurado.

### **TC-B-002: Verificar Datos Fiscales Cliente**
**Tiempo objetivo:** 3 min | **Gates:** 4 evidencias

**Preparación:**
- Cliente: "Cervecería Cuauhtémoc Moctezuma S.A." (RFC: CCM920814BC1)
- Navegar a master Customer

**Ejecución:**
1. **G01:** Customer form abierto desde listado
2. **G02:** Campos fiscales visibles (tax_id, address, etc)
3. **G03:** Estructura de campos correcta en interfaz
4. **G04:** Capacidad de editar campos fiscales

**Invariantes UI/UX:**
- Customer form carga correctamente
- Campos fiscales están presentes en form
- Navegación Customer ↔ Address funcional
- Campos editables según permisos usuario
- Validaciones frontend funcionando

**Nota:** Cliente con RFC real. Validar estructura UI + datos fiscales correctos.

**✅ RESULTADO TC-B-002:** Completado exitosamente
- **Hallazgo:** Botón validación SAT aparece cuando se define dirección principal del cliente
- **Resolución:** Mensaje "Se requiere dirección principal" desaparece al configurar dirección
- **Status:** Datos fiscales verificados correctamente, validación SAT funcional

### **TC-B-003: Configurar Producto con Claves SAT**
**Tiempo objetivo:** 5 min | **Gates:** 4 evidencias

**Preparación:**
- Producto nuevo: Material oficina
- Claves SAT: 52121500 / H87

**Ejecución:**
1. **G01:** Item form nuevo
2. **G02:** Claves SAT configuradas
3. **G03:** Validación catálogo SAT exitosa
4. **G04:** Producto disponible para facturación

**Invariantes:**
- Clave producto SAT válida
- Clave unidad compatible
- Descripción fiscal presente
- Impuestos configurados correctamente

**✅ RESULTADO TC-B-003:** Completado exitosamente
- **Rollback aplicado:** title_field = descripcion, autoname = field:codigo
- **Filtros optimizados:** Sin duplicidad, muestra Código + Descripción
- **Status:** Configuración SAT Producto Servicio funcionando correctamente
- **Naming verificado:** doc.name = codigo, filtros sin duplicidad

**🚧 ISSUE IDENTIFICADO TC-B-003:**
- **Problema:** Material oficina no aplica impuestos automáticamente en Sales Invoice
- **Contexto:** SAT Producto Servicio tiene "incluye_objeto_impuesto = 02" (Sí es objeto de impuestos)
- **Gap:** Falta vinculación entre catálogo SAT y plantillas impuestos ERPNext
- **Bloqueador:** Requiere migración catálogo impuestos y configuración automática

### **TC-B-004: Cancelar CFDI Motivo 03**
**Tiempo objetivo:** 6 min | **Gates:** 4 evidencias

**Preparación:**
- Factura timbrada disponible
- Motivo: Error sin relación

**Ejecución:**
1. **G01:** CFDI timbrado en Sales Invoice
2. **G02:** Diálogo cancelación, motivo 03 seleccionado
3. **G03:** Confirmación SAT recibida
4. **G04:** Estado "CANCELADO", acuse disponible

**Invariantes:**
- `fm_fiscal_status = "CANCELADO"`
- `fm_motivo_cancelacion = "03"`
- Acuse cancelación presente
- CFDI original preservado

### **TC-B-005: Re-facturar Mismo Sales Invoice**
**Tiempo objetivo:** 6 min | **Gates:** 4 evidencias

**Preparación:**
- CFDI cancelado motivo 02/03
- Cambio solo régimen fiscal

**Ejecución:**
1. **G01:** SI con CFDI cancelado, botón "Nueva FFM (misma SI)"
2. **G02:** Solo régimen fiscal modificable
3. **G03:** Nuevo CFDI generado
4. **G04:** Etiqueta "Re-facturado", historial fiscal visible

**Invariantes:**
- Mismo Sales Invoice ID
- Nueva FFM con UUID diferente
- FFM anterior en historial
- Vínculo SI ↔ FFM actualizado

### **TC-B-006-020: [Casos Básicos Adicionales]**
- TC-B-006: Factura con múltiples productos
- TC-B-007: Aplicar descuentos
- TC-B-008: IVA 0% productos exentos
- TC-B-009: Cliente público general
- TC-B-010: Verificar cálculo impuestos automático
- TC-B-011: Formato PDF generado
- TC-B-012: Archivo XML estructura
- TC-B-013: Serie fiscal automática
- TC-B-014: Folio consecutivo
- TC-B-015: Validación RFC emisor
- TC-B-016: Centro de costos multisucursal
- TC-B-017: Uso CFDI por defecto
- TC-B-018: Forma de pago 99 (PUE)
- TC-B-019: Método de pago transferencia
- TC-B-020: Moneda nacional (MXN)

---

## 🟡 **NIVEL INTERMEDIO (21-40): Workflows Complejos**

### **TC-I-021: Sustitución CFDI (Motivo 01)**
**Tiempo objetivo:** 6 min | **Gates:** 4 evidencias

**Preparación:**
- CFDI timbrado con error conceptos
- Corrección: cambio cantidad/precio

**Ejecución:**
1. **G01:** SI original, botón "Sustituir CFDI (01)"
2. **G02:** Nueva SI creada, modificaciones aplicadas
3. **G03:** TipoRelación 04 configurado, nueva factura timbrada
4. **G04:** SI original cancelada, vínculo sustitución establecido

**Invariantes:**
- Nueva Sales Invoice ID
- SI original `docstatus = 2`
- Relación "sustituye a" / "sustituida por"
- Cancelación automática motivo 01

### **TC-I-022: Workflow 04 con UUID Sustitución**
**Tiempo objetivo:** 6 min | **Gates:** 4 evidencias

**Preparación:**
- CFDI para cancelar motivo 04
- UUID sustituto válido disponible

**Ejecución:**
1. **G01:** Diálogo cancelación motivo 04
2. **G02:** UUID sustitución capturado
3. **G03:** Validación UUID exitosa
4. **G04:** Cancelación confirmada con relación

**Invariantes:**
- Motivo cancelación "04"
- UUID sustitución 36 caracteres
- Validación FacturAPI exitosa
- Relación sustitución registrada

### **TC-I-023: Cancelación con Plazo Vencido**
**Tiempo objetivo:** 5 min | **Gates:** 4 evidencias

**Preparación:**
- CFDI con más de 72 horas
- Simular restricción temporal

**Ejecución:**
1. **G01:** CFDI antiguo seleccionado
2. **G02:** Aviso plazo vencido mostrado
3. **G03:** Confirmación requerida explícita
4. **G04:** Solicitud cancelación enviada

**Invariantes:**
- Advertencia plazo visible
- Confirmación adicional requerida
- Proceso solicitud (no cancelación directa)
- Estado pendiente apropiado

### **TC-I-024: Multisucursal - Series Específicas**
**Tiempo objetivo:** 5 min | **Gates:** 4 evidencias

**Preparación:**
- 2 centros de costo configurados
- Series fiscales mapeadas

**Ejecución:**
1. **G01:** Sales Invoice, selección centro costo
2. **G02:** Serie fiscal determinada automáticamente
3. **G03:** Aviso serie mostrado pre-timbrado
4. **G04:** CFDI generado con serie correcta

**Invariantes:**
- Serie según centro de costo
- Aviso serie visible
- Folio secuencial por serie
- Configuración preservada

### **TC-I-025: Addenda Personalizada**
**Tiempo objetivo:** 6 min | **Gates:** 4 evidencias

**Preparación:**
- Cliente con addenda requerida
- XML addenda configurado

**Ejecución:**
1. **G01:** Configuración addenda en Customer
2. **G02:** Sales Invoice con cliente addenda
3. **G03:** Timbrado incluyendo addenda
4. **G04:** XML final con addenda validada

**Invariantes:**
- Addenda incluida en XML
- Estructura addenda válida
- Cliente-addenda vinculación correcta
- XML completo generado

### **TC-I-026-040: [Casos Intermedios Adicionales]**
- TC-I-026: Forma pago 02 (Dación en pago)
- TC-I-027: Forma pago 23 (Novación)
- TC-I-028: Forma pago 30 (Aplicación anticipos)
- TC-I-029: Complemento pagos (no facturación)
- TC-I-030: Retenciones ISR servicios profesionales
- TC-I-031: IEPS productos específicos
- TC-I-032: Factura con moneda extranjera
- TC-I-033: Tipo cambio automático
- TC-I-034: Nota de crédito fiscal
- TC-I-035: Factura de egresos
- TC-I-036: Múltiples impuestos mismo concepto
- TC-I-037: Descuentos a nivel línea
- TC-I-038: Descuentos globales
- TC-I-039: Validación límites facturación
- TC-I-040: Configuración certificados SAT

---

## 🔴 **NIVEL AVANZADO (41-62): Casos Edge y Excepciones**

### **TC-A-041: Recuperación Error Timbrado**
**Tiempo objetivo:** 6 min | **Gates:** 4 evidencias

**Preparación:**
- Simulación fallo FacturAPI
- Sales Invoice en estado inconsistente

**Ejecución:**
1. **G01:** Error timbrado detectado
2. **G02:** Diagnóstico estado fiscal
3. **G03:** Sincronización manual ejecutada
4. **G04:** Estado corregido, operación recuperada

**Invariantes:**
- Estado fiscal consistente
- Datos FacturAPI sincronizados
- No duplicación documentos
- Integridad preservada

### **TC-A-042: Múltiples FFM Misma SI**
**Tiempo objetivo:** 6 min | **Gates:** 4 evidencias

**Preparación:**
- SI con múltiples intentos facturación
- Manejo LinkExistsError

**Ejecución:**
1. **G01:** SI con FFM existente
2. **G02:** Intento segunda facturación
3. **G03:** Override automático LinkExistsError
4. **G04:** Nueva FFM creada, relaciones correctas

**Invariantes:**
- Una FFM vigente por SI
- FFM anteriores preservadas
- `ignore_links = True` aplicado
- Historial fiscal completo

### **TC-A-043: Cancelación Masiva (Lote)**
**Tiempo objetivo:** 6 min | **Gates:** 4 evidencias

**Preparación:**
- 5 CFDIs para cancelación simultánea
- Diferentes motivos cancelación

**Ejecución:**
1. **G01:** Selección múltiple CFDIs
2. **G02:** Configuración motivos por lote
3. **G03:** Procesamiento paralelo
4. **G04:** Resultados consolidados, errores identificados

**Invariantes:**
- Procesamiento atómico por CFDI
- Errores no bloquean lote completo
- Reporte resultados detallado
- Rollback parcial en fallos

### **TC-A-044: Archivos Corruptos/Perdidos**
**Tiempo objetivo:** 6 min | **Gates:** 4 evidencias

**Preparación:**
- CFDI con archivos PDF/XML faltantes
- Simulación corrupción

**Ejecución:**
1. **G01:** Detección archivos faltantes
2. **G02:** Re-descarga desde FacturAPI
3. **G03:** Validación integridad archivos
4. **G04:** Restauración completa exitosa

**Invariantes:**
- Archivos íntegros restaurados
- Checksums validados
- Vínculos reparados
- Historial preservado

### **TC-A-045: Concurrencia Usuarios**
**Tiempo objetivo:** 6 min | **Gates:** 4 evidencias

**Preparación:**
- 2 usuarios modificando misma SI
- Simulación conflicto concurrencia

**Ejecución:**
1. **G01:** Usuarios simultáneos en SI
2. **G02:** Modificaciones conflictivas detectadas
3. **G03:** Resolución conflicto automática/manual
4. **G04:** Estado final consistente

**Invariantes:**
- Sin pérdida datos
- Timestamp updates correctos
- Locks apropiados aplicados
- Notificaciones conflicto

### **TC-A-046-062: [Casos Avanzados Adicionales]**
- TC-A-046: Migración datos legacy
- TC-A-047: Backup/restore configuración
- TC-A-048: Certificados vencidos durante operación
- TC-A-049: Pérdida conectividad FacturAPI
- TC-A-050: Timeout operaciones largas
- TC-A-051: Validación cruzada SAT-FacturAPI
- TC-A-052: Auditoría fiscal completa
- TC-A-053: Exportación masiva reportes
- TC-A-054: Importación catálogos SAT
- TC-A-055: Configuración roles/permisos granulares
- TC-A-056: Integración sistemas terceros
- TC-A-057: API webhook callbacks
- TC-A-058: Logs debugging avanzado
- TC-A-059: Performance testing carga
- TC-A-060: Disaster recovery
- TC-A-061: Compliance audit trail
- TC-A-062: Security penetration testing

---

## 📊 **Métricas y Reportes**

### **Métricas por Ejecución**
```yaml
Tiempo total objetivo: 6 horas (62 casos × 6 min promedio)
Success rate target: ≥95%
Coverage areas:
  - UI/UX: 100% workflows críticos
  - Business logic: 100% reglas SAT
  - Integration: 95% endpoints FacturAPI
  - Error handling: 90% casos edge

KPIs críticos:
  - Zero data loss: 100%
  - Fiscal compliance: 100%
  - User experience: ≥95% satisfaction
```

### **Reporte Template**
```markdown
# Reporte Ejecución Testing - [FECHA]

## Resumen Ejecutivo
- Casos ejecutados: X/62
- Success rate: XX%
- Tiempo total: XX horas
- Issues críticos: X

## Resultados por Nivel
### Básico (1-20): XX% success
### Intermedio (21-40): XX% success
### Avanzado (41-62): XX% success

## Issues Identificados
[Lista priorizada con severidad]

## Evidencias
[Links a screenshots por caso]

## Recomendaciones
[Acciones correctivas prioritarias]
```

---

## 🎯 **Criterios Éxito Global**

### **Gates de Aceptación**
- ✅ **Funcional:** 100% workflows básicos operativos
- ✅ **Fiscal:** 100% compliance normativa SAT
- ✅ **Performance:** ≤6 min promedio por caso
- ✅ **UX:** Navegación intuitiva, mensajes claros
- ✅ **Robustez:** Manejo errors, recuperación automática

### **Definición "Testing Completo"**
1. Todos los casos TC-B-001 a TC-B-020 al 100%
2. ≥90% casos TC-I-021 a TC-I-040 exitosos
3. ≥80% casos TC-A-041 a TC-A-062 exitosos
4. Documentación evidencias completa
5. Plan corrección issues identificados

**¡SISTEMA TESTING UI/UX COMPLETADO!** 🚀

---

## 🚀 **INICIAR EJECUCIÓN**

### **Comandos Preparación**
```bash
# Verificar sitio
bench --site facturacion.dev list-apps

# Acceso sistema
http://facturacion.dev:8000

# Usuario sugerido: Administrator (todos los permisos)
```

### **Primer Caso: TC-B-001**
**COMENZAR:** Crear Sales Invoice con "CONCESIONARIA VUELA COMPAÑIA DE AVIACION" (RFC: CVA041027H80) + "Servicio E2E Test"

**Comando verificación datos:**
```bash
bench --site facturacion.dev execute "facturacion_mexico.obtener_datos_testing.obtener_datos_testing"
```

### **Directorio Evidencias**
- Crear: `docs/testing/planes/plan-testing-sistema-facturacion/evidencias/TC-B-001-crear-factura/`
- Capturar: `TC-B-001-crear-factura-G01.png`, `TC-B-001-crear-factura-G02.png`, etc.

**¡EMPEZAR TESTING!** 🎯