# 📝 Facturas en Borrador

El sistema de **Facturas en Borrador** permite crear y revisar facturas antes del timbrado final, mejorando el control y reduciendo errores en el proceso de facturación electrónica.

## 🎯 Propósito

- **Revisión previa**: Validar todos los datos antes del timbrado irreversible
- **Flujo de aprobación**: Permitir supervisión en facturas críticas
- **Reducción de errores**: Evitar cancelaciones SAT costosas por errores
- **Mejor experiencia**: Mayor confianza en el proceso de facturación

## 🏗️ Cómo Funciona

### 1. Crear Factura como Borrador

En el formulario de **Sales Invoice**:

1. ✅ Marcar el checkbox **"Crear como Borrador"**
2. 📄 Completar todos los datos normalmente (cliente, items, totales)
3. 💾 **Submit** el documento

El sistema enviará la factura a FacturAPI en **modo borrador**, sin timbrar definitivamente.

### 2. Estados del Borrador

| Estado | Descripción | Acciones Disponibles |
|--------|-------------|---------------------|
| **Borrador** | Factura creada en FacturAPI, pendiente revisión | Preview, Aprobar, Cancelar |
| **En Revisión** | Proceso de aprobación en curso | Esperar aprobación |
| **Aprobado** | Borrador aprobado, listo para timbrar | Timbrar automáticamente |
| **Timbrado** | Factura timbrada definitivamente | Ver PDF/XML final |

### 3. Revisar y Aprobar

#### Ver Preview del Borrador
- **Botón "Ver Preview"**: Muestra XML y PDF preliminar
- **Verificación visual**: Revisar datos, cálculos, addendas
- **URL temporal**: Link de preview válido por tiempo limitado

#### Aprobar para Timbrado
- **Botón "Aprobar y Timbrar"**: Convierte borrador a factura final
- **Timbrado automático**: Se ejecuta inmediatamente tras aprobación
- **CFDI final**: Se genera UUID y XML definitivo

### 4. Cancelar Borrador (Opcional)

Si se detectan errores:
- **Botón "Cancelar Borrador"**: Elimina borrador sin timbrar
- **Edición posible**: Se puede modificar la factura y volver a crear borrador
- **Sin costo SAT**: No se genera CFDI definitivo

## 📋 Guía Paso a Paso

### Escenario 1: Factura Simple

```
1. Sales Invoice → "Crear como Borrador" ✅ → Submit
2. Estado: "Borrador" → "Ver Preview" → Revisar
3. Todo correcto → "Aprobar y Timbrar" → Estado: "Timbrado"
```

### Escenario 2: Factura con Correcciones

```
1. Sales Invoice → "Crear como Borrador" ✅ → Submit  
2. Estado: "Borrador" → "Ver Preview" → ❌ Error detectado
3. "Cancelar Borrador" → Editar factura → Submit nuevamente
4. Estado: "Borrador" → "Ver Preview" → ✅ Correcto
5. "Aprobar y Timbrar" → Estado: "Timbrado"
```

### Escenario 3: Flujo de Aprobación

```
1. Usuario Operativo: Crea borrador
2. Estado: "Borrador" → Notificar a supervisor
3. Supervisor: Revisa preview y datos
4. Supervisor: "Aprobar y Timbrar" → Estado: "Timbrado"
```

## 🔧 Configuración y Campos

### Campos en Sales Invoice

| Campo | Tipo | Descripción |
|-------|------|-------------|
| **Crear como Borrador** | Checkbox | Activar modo borrador |
| **Estado Borrador** | Select | Estado actual del borrador |
| **ID Borrador FacturAPI** | Data | Identificador en FacturAPI |
| **Fecha Creación Borrador** | Datetime | Cuándo se creó el borrador |
| **Aprobado Por** | Link (User) | Quién aprobó el borrador |

### Integración con Addendas

Los borradores son **totalmente compatibles** con el sistema de addendas:

- ✅ **Preview incluye addenda**: El XML preliminar muestra la addenda completa
- ✅ **Validación previa**: Se verifica la addenda antes del timbrado
- ✅ **Corrección posible**: Si hay errores en addenda, se puede cancelar y corregir

### Integración Multi-Sucursal

Los borradores respetan la **configuración multi-sucursal**:

- ✅ **Por sucursal**: Cada sucursal maneja sus propios borradores
- ✅ **Configuración independiente**: Series y configuración por sucursal
- ✅ **Permisos**: Control de acceso según sucursal del usuario

## ⚠️ Consideraciones Importantes

### Limitaciones de Tiempo
- **TTL FacturAPI**: Los borradores pueden tener tiempo de vida limitado
- **Preview temporal**: URLs de preview expiran después de cierto tiempo
- **Recomendación**: Procesar borradores dentro de 24 horas

### Permisos y Roles
- **Crear borradores**: Usuarios con rol "Sales User"  
- **Aprobar borradores**: Usuarios con rol "Sales Manager"
- **Ver preview**: Mismos permisos que la factura original

### Casos de Error
- **Error FacturAPI**: Si falla la comunicación, se mantiene estado local
- **Rollback automático**: Errores en aprobación revierten a estado borrador
- **Logs detallados**: Todos los errores se registran para debugging

## 🚀 Beneficios del Sistema

### Para Usuarios Operativos
- ✅ **Mayor confianza**: Ver resultado antes de timbrar definitivamente
- ✅ **Menos errores**: Detectar problemas antes del timbrado irreversible
- ✅ **Aprendizaje**: Entender mejor el proceso de facturación

### Para Supervisores
- ✅ **Control de calidad**: Revisar facturas críticas antes del timbrado
- ✅ **Compliance**: Asegurar cumplimiento de políticas internas
- ✅ **Reducción de riesgos**: Evitar cancelaciones SAT costosas

### Para la Empresa
- ✅ **Ahorro de costos**: Menos cancelaciones y re-expediciones
- ✅ **Mejora de procesos**: Flujo de trabajo más robusto
- ✅ **Auditoría**: Trazabilidad completa del proceso de aprobación

## 🔗 APIs y Automatización

Para integraciones y automatización avanzada, consultar:

- [📚 API Reference - Draft Management](../api/draft-management.md)
- [👨‍💻 Development Guide - Draft Workflow](../development/draft-workflow.md)

## 📞 Soporte

Si encuentras problemas con el sistema de borradores:

1. **Verificar logs**: Error Log en ERPNext
2. **Estado FacturAPI**: Verificar conectividad con el PAC
3. **Permisos de usuario**: Confirmar roles y permisos
4. **Contactar soporte**: it@buzola.mx para asistencia técnica