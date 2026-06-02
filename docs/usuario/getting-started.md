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

### 2. Company — datos fiscales y dirección

En **Setup > Company**:

- **Tax ID**: RFC de la empresa
- **Default Currency**: MXN

Además, crea una **Address** vinculada a la Company con la dirección fiscal:

1. Ve a **Contacts > Address > New**
2. Llena `Address Line 1`, `City`, `Pincode` (CP fiscal)
3. En la sección **Links** agrega: `Company → [nombre de tu empresa]`
4. Marca **Is Primary Address**

> El CP de esta dirección se usa como `LugarExpedicion` en el CFDI y en addendas EDI.

### 3. Configuracion Fiscal Mexico

Accede desde el workspace **Facturación México → Configuracion Fiscal Mexico → New**.

Selecciona la **Company** y activa los regímenes de impuestos que apliquen:

| Opción | Cuándo activar |
|---|---|
| IVA Exento | Productos o servicios legalmente exentos de IVA |
| Zona Fronteriza | Empresa con operaciones en franja fronteriza norte (IVA 8%) |
| Exportación | Ventas al extranjero (IVA 0% exportación) |
| IEPS Alcohol | Venta de bebidas alcohólicas |
| IEPS Azúcar | Venta de bebidas con azúcar añadida |
| IEPS Combustibles | Venta de combustibles |
| IEPS Tabaco | Venta de tabaco |
| Ret. Honorarios | Pagos a personas físicas por honorarios |
| Ret. Arrendamiento | Pagos por arrendamiento |

> **Nota para alimentos frescos (frutas y verduras):** Bajo el Art. 2-A LIVA, los vegetales
> no industrializados se gravan a **tasa 0% de IVA** — no exento, sino tasa cero.
> No activar IEPS. La tasa 0% se genera automáticamente al ejecutar el wizard.

Ejecuta el botón **"Generar Template de Impuestos"** después de configurar las opciones.
Esto crea los Sales Taxes and Charges Templates necesarios para el timbrado.

> Sin este paso el timbrado falla con error de impuestos.

---

## Primer CFDI

### Cliente con datos fiscales

En **Selling > Customer**, llenar en la sección **Tax**:

| Campo | Descripción |
|---|---|
| `tax_id` | RFC del cliente (campo nativo ERPNext) |
| `fm_tax_regime` | Régimen fiscal SAT |
| `fm_uso_cfdi_default` | Uso CFDI por defecto |

### Item con clave SAT e Item Group fiscal

Cada item debe tener:
- `fm_producto_servicio_sat` — clave del catálogo SAT. Sin esta clave el timbrado se bloquea.
- **Item Group** correcto — el sistema asigna impuestos por Item Group, no por item individual.

El wizard de Configuracion Fiscal Mexico crea estos Item Groups automáticamente:

| Item Group | Cuándo usarlo |
|---|---|
| `Artículos con IVA al 0%` | Alimentos frescos, agua, medicamentos (Art. 2-A LIVA) |
| `Artículos Exentos` | Productos legalmente exentos de IVA |
| `Artículos IEPS Alcohol` | Bebidas alcohólicas |
| `Artículos IEPS Azúcar` | Bebidas con azúcar añadida |
| `Artículos IEPS Combustibles` | Combustibles |
| `Artículos IEPS Tabaco` | Tabaco |
| `Servicios Profesionales (Honorarios)` | Honorarios a personas físicas |
| `Arrendamiento` | Pagos por arrendamiento |

Los items en cualquier otro grupo (ej. *All Item Groups*) aplican IVA 16% estándar.

> Los Item Tax Templates se asignan automáticamente al Item Group — no es necesario configurarlos en cada item.

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
