# Automatización de Email CFDI

Este sistema permite el envío automático de CFDI por email después del timbrado exitoso, utilizando una configuración jerárquica inteligente.

## Configuración del Sistema

### 1. Configuración Global (Settings)

Ir a **Facturación México Settings** para configurar el comportamiento por defecto:

- **send_email_default**: Comportamiento por defecto para todos los clientes
  - `0` = No enviar automáticamente
  - `1` = Enviar automáticamente
- **customer_email_fallback**: Email de respaldo cuando el cliente no tiene email configurado

### 2. Configuración por Cliente

En el DocType **Customer**, encontrarás el campo **fm_envio_email_cliente** con estas opciones:

- **"Default (usar settings)"**: Usa la configuración global de Settings
- **"Enviar"**: Fuerza el envío automático para este cliente específico
- **"No enviar"**: Desactiva el envío automático para este cliente específico

### 3. Lógica de Prioridad (Cascade)

El sistema evalúa en este orden:

1. **Cliente específico**: Si el cliente tiene "Enviar" o "No enviar" → Se respeta esa preferencia
2. **Settings global**: Si el cliente tiene "Default" → Se usa `send_email_default`
3. **No enviar**: Si no hay configuración → No se envía automáticamente

## Funcionamiento Automático

### Auto-configuración del Campo

Cuando se crea una nueva **Factura Fiscal México**:

1. El sistema evalúa automáticamente la configuración cascade
2. Asigna el valor al campo `fm_enviar_email_timbrado` (checkbox)
3. Este campo determina si se enviará email al timbrar

### Envío Post-Timbrado

Después de un timbrado exitoso:

1. Si `fm_enviar_email_timbrado = 1` → Se envía automáticamente
2. El sistema resuelve el destinatario usando la misma lógica cascade
3. Se envía via FacturAPI con los archivos PDF y XML adjuntos

## Uso Manual de Botones

### Dropdown "Comprobantes"

Para facturas ya timbradas, el sistema muestra un dropdown "Comprobantes" con:

- **Descargar PDF+XML**: Descarga los archivos CFDI localmente
- **Enviar por email**: Envío manual usando la lógica cascade (sin prompt)

### Otros Botones Disponibles

- **"¿Cómo sustituir?"**: Ayuda contextual sobre sustitución de CFDI
- **"Ver Sales Invoice"**: Navegación al Sales Invoice origen
- **"Cancelar en FacturAPI"**: Cancelación fiscal (según estado)

## Resolución de Destinatarios

El sistema busca el email destinatario en este orden:

1. **fm_email_facturacion** del documento FFM
2. **customer_email** del Customer
3. **customer_email_fallback** de Settings
4. Si no encuentra ninguno → No envía y notifica

## Casos de Uso Comunes

### Configuración Empresa Pequeña
- Settings: `send_email_default = 1`
- Todos los clientes en "Default"
- Resultado: Envío automático para todos

### Configuración Empresa Grande
- Settings: `send_email_default = 0`
- Clientes VIP en "Enviar"
- Clientes normales en "Default" o "No enviar"
- Resultado: Envío selectivo solo para VIP

### Configuración Mixta
- Settings: `send_email_default = 1`
- Clientes problemáticos en "No enviar"
- Resto en "Default"
- Resultado: Envío para todos excepto excluidos

## Troubleshooting

### El campo no se auto-configura
- Verificar que existe el custom field `fm_envio_email_cliente` en Customer
- Verificar que existen los campos Settings: `send_email_default` y `customer_email_fallback`

### No se envía automáticamente
- Verificar que `fm_enviar_email_timbrado = 1` en el documento FFM
- Verificar que hay un email válido configurado
- Revisar logs de Frappe para errores específicos

### El dropdown no aparece
- El dropdown solo aparece para documentos timbrados (`docstatus = 1` y `fm_uuid` presente)
- Hacer refresh si es necesario