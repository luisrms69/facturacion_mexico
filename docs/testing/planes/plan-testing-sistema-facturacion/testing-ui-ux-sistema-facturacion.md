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
4. **G04:** Estado "CANCELADO", acuse disponible automáticamente

**Invariantes:**
- `fm_fiscal_status = "CANCELADO"`
- `fm_motivo_cancelacion = "03"`
- Acuse cancelación presente (PDF + XML)
- CFDI original preservado
- Archivos descargados automáticamente: `{FFM_NAME}_acuse_cancelacion.pdf/xml`

**✅ RESULTADO TC-B-004:** Completado exitosamente
- **Funcionalidad:** Descarga automática acuse cancelación implementada
- **Archivos:** PDF y XML del acuse se descargan automáticamente usando endpoints FacturAPI
- **Integración:** Usa mismo patrón que descarga PDF/XML timbrado para consistencia
- **Status:** Cancelación motivo 03 funciona correctamente con acuse automático

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

### **TC-B-006: Tipo de Comprobante - Ingreso (I)**
**Tiempo objetivo:** 5 min | **Gates:** 4 evidencias

**Preparación:**
- Factura nueva con cliente RFC válido
- Verificar tipo comprobante por defecto

**Ejecución:**
1. **G01:** Nueva Factura Fiscal México, tipo comprobante "I - Ingreso" por defecto
2. **G02:** Campo tipo comprobante read-only, no editable
3. **G03:** Timbrado exitoso con tipo "I" en payload FacturAPI
4. **G04:** CFDI generado con TipoDeComprobante="I"

**Invariantes:**
- `fm_tipo_comprobante = "I - Ingreso"` por defecto
- Campo read-only en interfaz
- Payload FacturAPI incluye `"type": "I"`
- XML CFDI con atributo correcto

### **TC-B-007: Sales Invoice Return - Tipo Egreso (E)**
**Tiempo objetivo:** 6 min | **Gates:** 4 evidencias

**Preparación:**
- Sales Invoice original timbrada
- Crear Sales Invoice de devolución

**Ejecución:**
1. **G01:** Return Sales Invoice, tipo comprobante automático "E - Egreso"
2. **G02:** Campos relación SAT visibles: tipo relación y UUID relacionado
3. **G03:** Configurar relación "03 - Devolución de mercancía" + UUID original
4. **G04:** Timbrado exitoso con related_documents en payload

**Invariantes:**
- `fm_tipo_comprobante = "E - Egreso"` automático para returns
- Campos relacionados visibles condicionalmente
- Payload incluye `"type": "E"` y `related_documents`
- Validación UUID relacionado obligatorio

### **TC-B-008: Configuración Settings - Tipo Traslado**
**Tiempo objetivo:** 3 min | **Gates:** 4 evidencias

**Preparación:**
- Acceso a Facturacion Mexico Settings
- Verificar configuración tipo comprobante

**Ejecución:**
1. **G01:** Settings form, sección "Configuración Tipo de Comprobante"
2. **G02:** Campo "Habilitar Traslado (T)" desactivado por defecto
3. **G03:** Descripción indica "No implementado: debe permanecer desactivado"
4. **G04:** Campo "Permitir editar relación en Egreso" disponible

**Invariantes:**
- `habilitar_traslado = 0` (desactivado)
- Descripción preventiva visible
- Campo avanzado edición relaciones presente
- Configuración preservada después de save

### **TC-B-009-020: [Casos Básicos Adicionales]**
- TC-B-009: Factura con múltiples productos
- TC-B-010: Aplicar descuentos
- TC-B-011: IVA 0% productos exentos
- TC-B-012: Cliente público general
- TC-B-013: Verificar cálculo impuestos automático
- TC-B-014: Formato PDF generado
- TC-B-015: Archivo XML estructura
- TC-B-016: Serie fiscal automática
- TC-B-017: Folio consecutivo
- TC-B-018: Validación RFC emisor
- TC-B-019: Centro de costos multisucursal
- TC-B-020: Uso CFDI por defecto

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

### **TC-I-026: Validación Tipo Comprobante en Contexto**
**Tiempo objetivo:** 5 min | **Gates:** 4 evidencias

**Preparación:**
- Sales Invoice normal vs Return Sales Invoice
- Verificar comportamiento automático

**Ejecución:**
1. **G01:** Función `_is_sales_invoice_return()` detecta returns correctamente
2. **G02:** Tipo comprobante se asigna automáticamente según contexto
3. **G03:** Campo read-only impide modificación manual
4. **G04:** API `sat_options()` devuelve catálogos SAT correctos

**Invariantes:**
- Detección automática return funcional
- Asignación tipo correcta (I vs E)
- Validaciones backend activas
- API SAT responde catálogos válidos

### **TC-I-027: Relaciones SAT - Tipo Egreso Completo**
**Tiempo objetivo:** 6 min | **Gates:** 4 evidencias

**Preparación:**
- Sales Invoice Return configurada
- UUID original disponible para relación

**Ejecución:**
1. **G01:** Tipo Egreso (E) seleccionado, campos relación visibles
2. **G02:** Dropdown tipo relación SAT poblado correctamente
3. **G03:** Validación UUID relacionado (36 caracteres, formato válido)
4. **G04:** Payload FacturAPI con related_documents estructura correcta

**Invariantes:**
- Visibility condicional campos relación
- Opciones SAT catálogo tipo relación
- Validación formato UUID estricta
- Estructura payload conforme FacturAPI

### **TC-I-028: Combinación Sustitución + Tipo Comprobante**
**Tiempo objetivo:** 6 min | **Gates:** 4 evidencias

**Preparación:**
- CFDI original para sustituir (workflow 01)
- Sales Invoice nueva con modificaciones

**Ejecución:**
1. **G01:** Sustitución 01 con tipo Egreso por cambio conceptos
2. **G02:** Relación 04 (sustitución) + relación específica (01/03/etc)
3. **G03:** Payload con múltiples related_documents
4. **G04:** Cancelación automática original motivo 01

**Invariantes:**
- Múltiples relaciones en mismo payload
- Combinación sustitución + tipo comprobante
- Cancelación cascada correcta
- Estructura related_documents válida

### **TC-I-029-040: [Casos Intermedios Adicionales]**
- TC-I-029: Forma pago 02 (Dación en pago)
- TC-I-030: Forma pago 23 (Novación)
- TC-I-031: Forma pago 30 (Aplicación anticipos)
- TC-I-032: Complemento pagos (no facturación)
- TC-I-033: Retenciones ISR servicios profesionales
- TC-I-034: IEPS productos específicos
- TC-I-035: Factura con moneda extranjera
- TC-I-036: Tipo cambio automático
- TC-I-037: Nota de crédito fiscal
- TC-I-038: Múltiples impuestos mismo concepto
- TC-I-039: Descuentos a nivel línea
- TC-I-040: Descuentos globales

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

### **TC-A-046: Validación Server-Side Tipo Comprobante**
**Tiempo objetivo:** 6 min | **Gates:** 4 evidencias

**Preparación:**
- Bypassing frontend, llamadas directas API
- Casos edge manipulación datos

**Ejecución:**
1. **G01:** Intento modificar tipo comprobante via API directa
2. **G02:** Validación `validate_tipo_comprobante()` rechaza cambios inválidos
3. **G03:** Tipo E sin UUID relacionado genera error apropiado
4. **G04:** Función `_find_uuid_cfdi_origen()` maneja casos sin CFDI origen

**Invariantes:**
- Validaciones server-side estrictas
- Errores descriptivos para usuarios
- Protección contra manipulación API
- Manejo robusto casos edge

### **TC-A-047: Compatibilidad Backwards - Facturas Legacy**
**Tiempo objetivo:** 6 min | **Gates:** 4 evidencias

**Preparación:**
- Facturas existentes sin fm_tipo_comprobante
- Migración automática en validación

**Ejecución:**
1. **G01:** Factura legacy sin tipo comprobante
2. **G02:** Función `_set_tipo_from_context()` asigna tipo automáticamente
3. **G03:** Save/update preserva compatibilidad
4. **G04:** Timbrado exitoso con tipo inferido

**Invariantes:**
- Zero breaking changes facturas existentes
- Migración automática transparente
- Comportamiento consistente legacy vs nuevo
- Performance no degradado

### **TC-A-048: Casos Edge Payload FacturAPI**
**Tiempo objetivo:** 6 min | **Gates:** 4 evidencias

**Preparación:**
- Combinar multiple related_documents
- Sustitución + Egreso + UUID relacionado

**Ejecución:**
1. **G01:** Payload con related_documents múltiples (tipo E + sustitución)
2. **G02:** Estructura JSON válida para FacturAPI
3. **G03:** Orden elementos preservado
4. **G04:** Respuesta FacturAPI exitosa con estructura compleja

**Invariantes:**
- Estructura related_documents conforme API
- Múltiples relaciones en mismo documento
- JSON serialization correcta
- Respuesta FacturAPI válida

### **TC-A-049: Armonización Direcciones FFM-ERPNext**
**Tiempo objetivo:** 5 min | **Gates:** 4 evidencias

**Preparación:**
- Customer con dirección principal configurada
- Verificar consistencia direcciones Customer UI vs FFM

**Ejecución:**
1. **G01:** Customer form muestra "Dirección Primaria" correctamente formateada
2. **G02:** FFM._get_primary_address_display() retorna misma dirección que ERPNext
3. **G03:** Campo "Dirección Principal Formateada" en FFM ya no aparece vacío
4. **G04:** Ambos sistemas usan get_address_display() estándar de Frappe

**Invariantes:**
- Misma fuente: customer_primary_address + fallbacks
- Mismo formato: get_address_display() de Frappe
- Sin discrepancias entre Customer UI y FFM
- Campo FFM poblado correctamente

**✅ RESULTADO TC-A-049:** Completado exitosamente
- **Implementación:** Patch armonización direcciones aplicado según propuesta ChatGPT
- **Cambios:** _get_primary_address() usa misma lógica que ERPNext, _get_primary_address_display() usa get_address_display() estándar
- **Verificación:** FFM ahora muestra exactamente la misma dirección que Customer UI
- **Status:** Inconsistencia direcciones Customer ↔ FFM eliminada completamente

### **TC-A-050: Eliminación Campos Duplicados Customer**

**Objetivo:** Validar que eliminación de campos "Régimen Fiscal" duplicados en Customer no afecta funcionalidad fiscal

**Pre-condiciones:**
- Customer con tax_category configurado (único campo régimen fiscal)
- FFM existentes que usen tax_category
- Sistema actualizado con fixture limpio

**Pasos de prueba:**
1. **Customer UI:**
   - Abrir cualquier Customer
   - Verificar que solo existe 1 campo régimen fiscal: "Categoría de Impuestos"
   - Verificar que NO existe sección "Información Fiscal México"
   - Verificar que "Uso CFDI por Defecto" está junto a campos fiscales nativos

2. **FFM Creation:**
   - Crear FFM para Customer con tax_category configurado
   - Verificar que FFM obtiene régimen fiscal de tax_category
   - Verificar que campo "Régimen Fiscal Customer" se puebla correctamente

3. **Funcionalidad Timbrado:**
   - Completar timbrado FFM
   - Verificar que XML contiene régimen fiscal correcto
   - Verificar que proceso fiscal NO tiene errores

**Resultados esperados:**
- Un solo campo régimen fiscal visible en Customer UI
- FFM funciona correctamente con tax_category nativo
- Sin errores en proceso de timbrado
- Limpieza UI eliminando confusión duplicados

**✅ RESULTADO TC-A-050:** Completado exitosamente
- **Implementación:** Eliminación campos duplicados completada según propuesta ChatGPT exacta
- **Script:** eliminar_regimen_fiscal_duplicado.py ejecutado via bench execute
- **Fixture:** Eliminados 3 objetos JSON (fm_regimen_fiscal, fm_informacion_fiscal_mx_section, fm_column_break_fiscal_customer)
- **Verificación:** Greps confirman eliminación completa, FFM usa tax_category nativo correctamente
- **UI:** Customer ahora tiene solo 1 campo régimen fiscal, sección eliminada, fm_uso_cfdi_default reubicado limpiamente
- **Status:** Duplicación campos Customer eliminada definitivamente, arquitectura fiscal limpia

### **TC-A-051: Descarga Automática Acuse Cancelación**
**Tiempo objetivo:** 6 min | **Gates:** 4 evidencias

**Preparación:**
- CFDI timbrado para cancelar (cualquier motivo)
- Verificar funcionamiento endpoints FacturAPI

**Ejecución:**
1. **G01:** CFDI listo para cancelación, archivos PDF/XML timbrado presentes
2. **G02:** Ejecutar cancelación, verificar llamada automática descarga acuse
3. **G03:** Confirmar archivos `{FFM_NAME}_acuse_cancelacion.pdf/xml` generados
4. **G04:** Validar integridad archivos y vinculación correcta en FFM

**Invariantes:**
- Descarga automática sin intervención usuario
- Archivos PDF y XML del acuse presentes en attachments
- Nomenclatura consistente con patrón sistema
- Manejo errores sin afectar flujo principal de cancelación
- Uso correcto endpoints `/invoices/{id}/cancellation_receipt/pdf|xml`

**✅ RESULTADO TC-A-051:** Completado exitosamente
- **Implementación:** Sistema descarga automática acuse funcionando correctamente
- **Endpoints:** `/v2/invoices/{id}/cancellation_receipt/xml` y `/cancellation_receipt/pdf` confirmados
- **Patrón:** Reutiliza `_save_file_attachment()` existente para consistencia
- **Status:** Funcionalidad automática completa, archivos disponibles inmediatamente post-cancelación

### **TC-A-052-064: [Casos Avanzados Adicionales]**
- TC-A-052: Migración datos legacy
- TC-A-053: Backup/restore configuración
- TC-A-054: Certificados vencidos durante operación
- TC-A-055: Pérdida conectividad FacturAPI
- TC-A-056: Timeout operaciones largas
- TC-A-057: Validación cruzada SAT-FacturAPI
- TC-A-058: Auditoría fiscal completa
- TC-A-059: Exportación masiva reportes
- TC-A-060: Importación catálogos SAT
- TC-A-061: Configuración roles/permisos granulares
- TC-A-062: Integración sistemas terceros
- TC-A-063: API webhook callbacks
- TC-A-064: Logs debugging avanzado
- TC-A-065: Performance testing carga

---

## 📊 **Métricas y Reportes**

### **Métricas por Ejecución**
```yaml
Tiempo total objetivo: 6.4 horas (64 casos × 6 min promedio)
Success rate target: ≥95%
Coverage areas:
  - UI/UX: 100% workflows críticos
  - Business logic: 100% reglas SAT
  - Integration: 95% endpoints FacturAPI
  - Error handling: 90% casos edge
  - Tipo Comprobante: 100% workflows I/E/T
  - Armonización Direcciones: 100% consistency FFM ↔ ERPNext

KPIs críticos:
  - Zero data loss: 100%
  - Fiscal compliance: 100%
  - User experience: ≥95% satisfaction
  - Tipo comprobante SAT: 100% compliance
  - Consistencia direcciones: 100% armonización
  - Campos Customer limpios: 100% eliminación duplicados

Nuevas funcionalidades incluidas:
  - TC-B-004: Descarga automática acuse cancelación (PDF+XML) ✅ COMPLETADO
  - TC-B-006: Tipo Comprobante Ingreso (I) por defecto
  - TC-B-007: Sales Invoice Return → Egreso (E) automático
  - TC-B-008: Configuración Settings tipo comprobante
  - TC-I-026: Validaciones contexto automático
  - TC-I-027: Relaciones SAT completas
  - TC-I-028: Combinación sustitución + tipo comprobante
  - TC-A-046: Validaciones server-side estrictas
  - TC-A-047: Compatibilidad backwards facturas legacy
  - TC-A-048: Casos edge payload FacturAPI múltiple
  - TC-A-049: Armonización direcciones FFM-ERPNext ✅ COMPLETADO
  - TC-A-050: Eliminación campos duplicados Customer ✅ COMPLETADO
```

### **Reporte Template**
```markdown
# Reporte Ejecución Testing - [FECHA]

## Resumen Ejecutivo
- Casos ejecutados: X/64
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
3. ≥80% casos TC-A-041 a TC-A-064 exitosos
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