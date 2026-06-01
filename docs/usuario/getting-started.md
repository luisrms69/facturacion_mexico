# Primeros Pasos

Guía para configurar el sistema y emitir el primer CFDI.

---

## Requisitos previos

- ERPNext v16 instalado
- Cuenta activa en [FacturAPI.io](https://www.facturapi.io) (sandbox para pruebas)
- RFC de la empresa emisora
- Código postal fiscal

---

## Instalación

```bash
bench get-app facturacion_mexico https://github.com/luisrms69/facturacion_mexico.git
bench --site tu-sitio.local install-app facturacion_mexico
bench --site tu-sitio.local migrate
```

---

## Configuración inicial

### 1. Facturacion Mexico Company Settings

Accede desde el workspace **Facturación México → Facturacion Mexico Company Settings**.

Crea un registro **por cada empresa** que emitirá CFDIs.

| Campo | Descripción |
|---|---|
| Company | Empresa emisora (Link a ERPNext Company) |
| API Key Producción | API Key de FacturAPI.io para producción |
| API Key Pruebas | API Key de FacturAPI.io para sandbox |
| Modo Sandbox | Activar para pruebas, desactivar para producción |
| Método de Pago por Defecto | PUE o PPD — se aplica al crear nuevas facturas |
| Enviar Email por Defecto | Si el sistema envía CFDI por email automáticamente |

> Los certificados SAT (.cer/.key) se gestionan en el portal de FacturAPI.io, no en ERPNext.

> Si tienes varias empresas, crea un registro de Company Settings por cada una.

### 2. Company — datos fiscales

En **Setup > Company**:

- **Tax ID**: RFC de la empresa
- **Default Currency**: MXN

### 3. Configuracion Fiscal Mexico

Accede desde el workspace **Facturación México**.

Ejecuta el wizard **"Generar Template de Impuestos"** para crear los Sales Taxes and Charges Templates necesarios. Sin este paso el timbrado falla.

Prerrequisito: tener las cuentas contables de impuestos configuradas en el Chart of Accounts (IVA por pagar, IEPS, retenciones según aplique).

---

## Primer CFDI

### Cliente con datos fiscales

En **Selling > Customer**, llenar en la sección fiscal:

| Campo | Descripción |
|---|---|
| `fm_rfc` | RFC del cliente |
| `fm_tax_regime` | Régimen fiscal SAT |
| `fm_uso_cfdi_default` | Uso CFDI por defecto |

### Item con clave SAT

Cada item debe tener configurado `fm_producto_servicio_sat` (clave del catálogo SAT). Sin esta clave el timbrado se bloquea.

### Emitir la factura

1. Crear Sales Invoice en **Selling > Sales Invoice**
2. Seleccionar el cliente (debe tener RFC en `tax_id`)
3. Agregar items con clave SAT configurada
4. Verificar que los impuestos se calculen correctamente
5. **Submit** — se crea la **Factura Fiscal Mexico** en estado `BORRADOR`
6. Clic en el botón **"Timbrar Factura"** → abre el FFM → clic en **"Timbrar con FacturAPI"**

Si el timbrado es exitoso, el FFM cambia a estado `TIMBRADO` y el Sales Invoice muestra `fm_fiscal_status = TIMBRADO`.

> Ver el flujo completo en [Emitir un CFDI](emitir-cfdi.md).

---

## Siguientes pasos

- [Cancelar un CFDI](cancelar-cfdi.md)
- [Configurar Multi-sucursal](multisucursal.md)
- [Addendas para clientes corporativos](addendas.md)
- [CFDI Recibidos — registrar compras](cfdi-recibidos.md)
- [Troubleshooting](troubleshooting.md)
