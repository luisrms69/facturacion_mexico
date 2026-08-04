# Referencia de configuración

Esta página es la **referencia de los campos de configuración** de `facturacion_mexico`,
organizados por su alcance: **por empresa**, **por sucursal** y **por cliente**.

Solo se documentan los campos **configurables aprobados** (obligatorios de implementación,
opcionales de negocio y operativos/administrativos). Se excluyen los campos calculados,
de solo lectura sin valor operativo, los metadatos sin uso y los módulos no aprobados
(Dashboard fiscal, Panel de control, Monitor de salud del sistema, gestión de borradores y
motor de reglas).

Cada tabla se agrupa por DocType. Los datos (etiqueta, obligatoriedad y valor por defecto) se
tomaron directamente de la definición `.json` real de cada DocType.

> **Alcance:** "empresa" = un registro por Company · "sucursal" = un registro por Branch ·
> "cliente" = un registro por Customer/tipo de addenda.

---

## Facturacion Mexico Company Settings — por empresa

DocType de settings principal del app. Un registro por Company (`FMCS-{Company}`).
Roles con escritura: System Manager y Facturacion Mexico System Manager (Facturacion Mexico
Manager solo lectura).

| Etiqueta visible | fieldname | Alcance | Obligatorio | Default | Propósito | Si se deja vacío | Funcionalidad que lo usa |
|---|---|---|---|---|---|---|---|
| Company | `company` | empresa | Sí (único) | — | Empresa a la que aplica esta configuración. | No aplica (obligatorio). | Clave del registro; todas las lecturas de configuración por empresa. |
| Modo Sandbox | `sandbox_mode` | empresa | No | 1 (activo) | Activa el modo de pruebas de FacturAPI. | Falsy → opera en modo producción. | Cliente FacturAPI (selección sandbox vs producción). |
| API Key Producción | `api_key` | empresa | No | — | API Key de producción de FacturAPI.io. | Sin key de producción, el timbrado en producción falla. | Cliente FacturAPI (producción). |
| API Key Pruebas | `test_api_key` | empresa | No | — | API Key de pruebas (sandbox) de FacturAPI.io. | Sin key sandbox, el timbrado en sandbox falla. | Cliente FacturAPI (sandbox). |
| Modo Facturación por Defecto | `ereceipt_mode_default` | empresa | No | Normal | Modo por defecto de nuevas Sales Invoice: Normal (timbrado directo) o E-Receipt (recibo para autofacturación). | Se asume Normal. | Handler JS de e-receipts (asigna `fm_ereceipt_mode` en la Sales Invoice). |
| Método de Pago por Defecto | `metodo_pago_default` | empresa | No | PUE | Método de pago SAT asignado a nuevas Facturas Fiscales Mexico (PUE/PPD). | Fallback a PUE. | Asignación de método de pago en Factura Fiscal Mexico. |
| Cuenta de Descuentos y Bonificaciones | `cuenta_descuentos` | empresa | No | — | Cuenta de ingresos para notas de crédito por descuento/bonificación (CFDI E, TipoRelación 01). | No se auto-detecta el motivo "Descuento / Bonificación". | Auto-detección de motivo en notas de crédito por descuento. |
| Enviar Email por Defecto | `send_email_default` | empresa | No | 0 (no) | Envía XML y PDF del CFDI al cliente automáticamente al timbrar. | Falsy → no se envía email automático. | Timbrado (envío de correo). |
| Descargar PDF/XML automáticamente | `download_files_default` | empresa | No | 1 (sí) | Descarga y adjunta PDF y XML automáticamente al timbrar Factura Fiscal Mexico y Complemento Pago MX. | Falsy → no descarga PDF/XML. | Timbrado (descarga de archivos). |
| Email Fallback Cliente | `customer_email_fallback` | empresa | No | — | Destinatario usado cuando el cliente no tiene email. | Si el cliente no tiene email, no se envía correo. | Resolución de destinatario de email (3er nivel). |
| Tipo Vencimiento por Defecto | `ereceipt_expiry_type_default` | empresa | No | Fixed Days | Tipo de vencimiento por defecto de E-Receipts (Fixed Days / End of Month / Custom Date). | Se asume Fixed Days. | Creación de E-Receipts. |
| Días Vencimiento por Defecto | `ereceipt_expiry_days_default` | empresa | No | 3 | Días de vencimiento por defecto de E-Receipts (aplica con tipo Fixed Days). | Se asume 3 días. | Creación de E-Receipts. |
| Forma de Pago E-Receipt por Defecto | `ereceipt_payment_form_default` | empresa | No | 28 | Forma de pago SAT para E-Receipts cuando no se obtiene del Payment Entry (28=débito, 04=crédito, 01=efectivo, 03=transferencia). | Fallback a 28 (tarjeta débito). | Creación de E-Receipts. |
| Forma de Pago Global por Defecto | `global_payment_form_default` | empresa | No | 01 | Forma de pago SAT para facturas globales cuando no hay una forma clara de los receipts. | Fallback a 01 (efectivo). | Construcción de factura global. |
| Notificar al Timbrar Factura Global | `notify_global_generation` | empresa | No | 0 (no) | Envía notificación por email al timbrar una Factura Global. | Falsy → no notifica. | Notificación al timbrar factura global. |
| Emails de Notificación Factura Global | `global_notification_emails` | empresa | No | — | Emails (separados por coma) que reciben la notificación de factura global. Depende de "Notificar al Timbrar Factura Global". | Solo se notifica al usuario creador. | Notificación al timbrar factura global. |
| Incluir Orden de Compra | `pdf_incluir_po_no` | empresa | No | 1 (sí) | Incluye el número de orden de compra del cliente (po_no) en el PDF del CFDI. | Falsy → no incluye po_no en el PDF. | Generación del PDF del CFDI. |
| Incluir Observaciones | `pdf_incluir_remarks` | empresa | No | 1 (sí) | Incluye el campo Observaciones (remarks) de la Sales Invoice en el PDF del CFDI. | Falsy → no incluye remarks en el PDF. | Generación del PDF del CFDI. |
| Leyenda PUE | `pdf_nota_pue` | empresa | No | — | Leyenda opcional para facturas con método de pago PUE. | Se omite la leyenda PUE. | Generación del PDF del CFDI. |
| Leyenda PPD | `pdf_nota_ppd` | empresa | No | — | Leyenda opcional para facturas con método de pago PPD. Admite variables {company}, {total}, {due_date}. | Se omite la leyenda PPD. | Generación del PDF del CFDI. |

!!! warning "E-Receipts y Factura Global — pendientes de validación integral"
    Los campos con prefijo `ereceipt_*` (modo, vencimiento, forma de pago) configuran el módulo
    **E-Receipts**, que **no está validado integralmente** (portal/autofactura/expiración sin
    aprobar). Los campos `global_*` (`notify_global_generation`, `global_notification_emails`,
    `global_payment_form_default`, y `global_customer`/`global_item`) pertenecen a **Factura
    Global**, funcionalidad **sin interfaz operable ni validación integral**. Puedes capturarlos,
    pero **no** están aprobados como operativos. `global_customer` y `global_item` se detallan en la
    sección final "Factura Global — funcionalidad pendiente de interfaz y validación integral".

---

## Configuracion Fiscal Mexico — por empresa

Configuración fiscal por empresa (wizard STCT/ITT). Un registro por Company (`CFM-{Company}`).
Roles con escritura: System Manager y Accounts Manager.

| Etiqueta visible | fieldname | Alcance | Obligatorio | Default | Propósito | Si se deja vacío | Funcionalidad que lo usa |
|---|---|---|---|---|---|---|---|
| Empresa | `company` | empresa | Sí (único) | — | Empresa a la que aplica la configuración fiscal. | No aplica (obligatorio). | Clave del registro; generador de templates y hooks IEPS. |
| IVA Exento | `enable_exento` | empresa | No | 0 (no) | Habilita productos/servicios legalmente exentos de IVA. | Falsy → régimen exento no habilitado; no genera fila de mapeo. | Generación de templates fiscales (STCT/ITT). |
| Zona Fronteriza | `enable_frontera` | empresa | No | 0 (no) | Habilita IVA 8% para la franja fronteriza norte. | Falsy → sin IVA 8% frontera. | Generación de templates fiscales. |
| IVA tasa 0% / Exportación | `enable_exportacion` | empresa | No | 0 (no) | Habilita IVA tasa 0% (alimentos no industrializados y exportaciones). | Falsy → sin tasa 0%. | Generación de templates fiscales. |
| IEPS Alcohol | `enable_ieps_alcohol` | empresa | No | 0 (no) | Habilita IEPS de bebidas alcohólicas. | Falsy → IEPS alcohol no disponible. | Generación de templates fiscales. |
| IEPS Azúcar/Bebidas | `enable_ieps_azucar` | empresa | No | 0 (no) | Habilita IEPS de bebidas con azúcar añadida. | Falsy → no disponible. | Generación de templates fiscales. |
| IEPS Combustibles | `enable_ieps_combustibles` | empresa | No | 0 (no) | Habilita IEPS de combustibles (cuota fija por litro). | Falsy → no disponible. | Generación de templates fiscales. |
| IEPS Tabaco | `enable_ieps_tabaco` | empresa | No | 0 (no) | Habilita IEPS de tabaco. | Falsy → no disponible. | Generación de templates fiscales. |
| Retenciones Honorarios | `enable_ret_honorarios` | empresa | No | 0 (no) | Habilita retenciones de servicios profesionales (ISR + IVA). | Falsy → sin retención de honorarios. | Generación de templates fiscales. |
| Retenciones Arrendamiento | `enable_ret_arrendamiento` | empresa | No | 0 (no) | Habilita retenciones por arrendamiento de inmuebles (ISR + IVA). | Falsy → sin retención de arrendamiento. | Generación de templates fiscales. |
| Retenciones Autotransporte | `enable_ret_autotransporte` | empresa | No | 0 (no) | Habilita retención IVA 4% de autotransporte terrestre de carga federal. | Falsy → sin retención de autotransporte. | Generación de templates fiscales. |
| Retenciones RESICO | `enable_ret_resico` | empresa | No | 0 (no) | Habilita retenciones RESICO (ISR + IVA) a personas físicas. | Falsy → sin retención RESICO. | Generación de templates fiscales. |
| Tasa ISR RESICO | `tasa_isr_resico` | empresa | No (depende de Retenciones RESICO) | 1.25 | Porcentaje de retención ISR para RESICO. | Se usa 1.25% por defecto. | Cálculo de retención RESICO. |
| Cuentas de Impuestos | `mapeo_cuentas` | empresa | Sí | — | Tabla de mapeo de cuentas contables de impuestos (Mapeo Cuenta Fiscal Mexico). | Bloquea el guardado (obligatorio); sin filas no hay cuentas de impuesto. | Hooks IEPS y generación de templates. |
| Precios de venta incluyen impuestos | `sales_prices_include_tax` | empresa | No | 0 (no) | Marca el impuesto como incluido en el precio capturado en los STCT de venta generados por el app. | Falsy → el STCT no marca impuesto incluido en el precio. | Generación de templates fiscales (STCT). |

---

## Configuracion Fiscal Sucursal — por sucursal

Configuración fiscal por Branch. Un registro por sucursal (naming `CFS-.YYYY.-`). La empresa se
obtiene automáticamente de la sucursal. Roles con escritura: System Manager y Accounts Manager
(Accounts User solo lectura).

| Etiqueta visible | fieldname | Alcance | Obligatorio | Default | Propósito | Si se deja vacío | Funcionalidad que lo usa |
|---|---|---|---|---|---|---|---|
| Series | `naming_series` | sucursal | Sí | — | Serie de nomenclatura del registro (CFS-.YYYY.-). | No aplica (obligatorio). | Nomenclatura del documento. |
| Sucursal | `branch` | sucursal | Sí (único) | — | Branch al que aplica la configuración. | No aplica (obligatorio). | Clave del registro; selector de certificados y migración. |
| IDs de Certificados | `certificate_ids` | sucursal | No | — | Certificados (CSD) asignados a esta sucursal (arreglo JSON). | Sin certificados asignados a la sucursal. | Selector de certificados multi-sucursal. |
| Umbral de Advertencia | `folio_warning_threshold` | sucursal | No | 100 | Folios restantes que disparan una advertencia de folios bajos. | Se asume 100. | Alertas de folios de la sucursal. |
| Umbral Crítico | `folio_critical_threshold` | sucursal | No | 50 | Folios restantes que disparan una alerta crítica. | Se asume 50. | Validación (debe ser menor que el umbral de advertencia). |
| Activa | `is_active` | sucursal | No | 1 (activa) | Indica si la sucursal está activa para facturación. | Falsy → sucursal inactiva. | Filtro de sucursales activas. |
| Necesita Atención | `needs_attention` | sucursal | No | 0 (no) | Marca que la sucursal requiere atención del usuario. | Falsy → sin alerta. | Gestor de sucursales (branch manager). |

> Los demás campos del DocType (`company`, `serie_fiscal`, `folio_current`) se obtienen
> automáticamente del Branch (`fetch_from`), y las estadísticas (`last_invoice_date`,
> `monthly_average`, `days_until_exhaustion`, `total_invoices_generated`, `last_sync_date`,
> `created_automatically`) son de solo lectura y calculadas; no son configurables y se excluyen.

---

## Configuracion CFDI Recibidos — por empresa

Configuración del wizard de CFDIs recibidos. Un registro por Company (`CFDI-REC-CFG-{Company}`).
Roles con escritura: System Manager, Accounts Manager y Facturacion Mexico Manager.

| Etiqueta visible | fieldname | Alcance | Obligatorio | Default | Propósito | Si se deja vacío | Funcionalidad que lo usa |
|---|---|---|---|---|---|---|---|
| Empresa | `company` | empresa | Sí (único) | — | Empresa a la que aplica la configuración de CFDIs recibidos. | No aplica (obligatorio). | Clave del registro; servicios de CFDI recibidos. |
| Reglas de Impuesto | `reglas_impuesto` | empresa | No | — | Tabla de reglas por tipo de impuesto recibido en CFDIs de proveedores (Regla Impuesto CFDI Recibido). | Sin reglas de impuesto de compra. | Generación del Purchase Taxes and Charges Template. |
| Condiciones de Pago por Defecto (Proveedor) | `default_payment_terms_supplier` | empresa | No | — | Condiciones de pago asignadas a proveedores nuevos creados desde CFDI Recibidos (no sobrescribe existentes). | No asigna condiciones a proveedores nuevos. | Resolución de proveedor (supplier_resolver). |
| Mapeo de Departamentos | `mapeo_departamentos` | empresa | No | — | Tabla que mapea cada Departamento ERPNext a la familia de gasto SAT 601-604 (Mapeo Departamento CFDI Recibido). | Sin clasificación de departamento a familia SAT. | Procesamiento/clasificación de CFDIs recibidos. |
| Modo de resolución contable | `modo_resolucion_contable` | empresa | No | Manual | Define cómo se obtiene la cuenta de gasto al generar Purchase Invoice Drafts (Manual / Automatico CoA SAT). | Se asume Manual (el usuario asigna la cuenta por concepto). | Constructor de Purchase Invoice desde CFDI recibido. |
| Formato CoA | `formato_coa` | empresa | No (depende de modo Automatico CoA SAT) | — | Formato del account_number del CoA de la empresa (########, ###-##-###, ###.##.###). | Solo aplica en modo automático; sin formato no resuelve la cuenta. | Constructor de Purchase Invoice (modo automático). |
| Tolerancia Absoluta (MXN) | `tolerancia_total_absoluta` | empresa | No | 1.00 | Diferencia máxima en MXN entre el total del XML CFDI y el total calculado por ERPNext. | Se asume 1.00 MXN. | Validación de totales al construir Purchase Invoice. |
| Tolerancia Porcentual (%) | `tolerancia_total_porcentual` | empresa | No | 0.5 | Porcentaje máximo del total del XML admitido como diferencia (0.5 = 0.5%). | Se asume 0.5%; el valor 0 desactiva esta tolerancia. | Validación de totales al construir Purchase Invoice. |

> Los campos `purchase_taxes_template`, `wizard_completado` y `ultima_generacion` son de solo
> lectura (los escribe el wizard) y se excluyen.

---

## Configuracion Reclasificacion Fiscal Mexico — por empresa

Configuración de reclasificación de impuestos al cobro/pago. Un registro por Company
(`CRFM-{Company}`). Roles con escritura: System Manager y Accounts Manager.

| Etiqueta visible | fieldname | Alcance | Obligatorio | Default | Propósito | Si se deja vacío | Funcionalidad que lo usa |
|---|---|---|---|---|---|---|---|
| Empresa | `company` | empresa | Sí (único) | — | Empresa a la que aplica la reclasificación fiscal. | No aplica (obligatorio). | Clave del registro. |
| Reglas | `reglas` | empresa | No | — | Tabla de reglas de reclasificación de impuestos (Regla Reclasificacion Fiscal): cuenta origen → cuenta destino al cobro/pago. | Sin reglas que aplicar. | Acciones "Cargar Reglas" y "Aplicar" del DocType. |

> Los campos `ultima_deteccion`, `ultima_generacion` (de solo lectura) e `instrucciones_html`
> (contenido HTML estático informativo) se excluyen por no ser configurables.

---

## Addenda Configuration — por cliente

Configuración de addenda por Customer y tipo de addenda (`ADCFG-{Customer}-{Addenda Type}-{###}`).
Roles con escritura: System Manager y Accounts Manager (Accounts User solo lectura).

| Etiqueta visible | fieldname | Alcance | Obligatorio | Default | Propósito | Si se deja vacío | Funcionalidad que lo usa |
|---|---|---|---|---|---|---|---|
| Cliente | `customer` | cliente | Sí | — | Cliente al que aplica esta configuración de addenda. | No aplica (obligatorio). | Clave del registro. |
| Tipo de Addenda | `addenda_type` | cliente | Sí | — | Tipo de addenda asociado (Addenda Type). | No aplica (obligatorio). | Detector automático de addenda. |
| Activo | `is_active` | cliente | No | 1 (activo) | Indica si esta configuración de addenda está activa. | Falsy → la configuración se ignora. | Filtro de configuraciones activas en detección/aplicación. |
| Aplicar Automáticamente | `auto_apply` | cliente | No | 1 (sí) | Aplica la addenda automáticamente al facturar. | Falsy → no se aplica automáticamente. | Aplicación automática de addenda. |
| Fecha de Inicio | `effective_date` | cliente | No | — | Inicio de vigencia de la configuración. | Sin límite inferior de vigencia. | Validación de vigencia. |
| Fecha de Fin | `expiry_date` | cliente | No | — | Fin de vigencia de la configuración. | Sin límite superior de vigencia. | Validación de vigencia. |
| Valores de Campos | `field_values` | cliente | No | — | Tabla de valores de los campos de la addenda (Addenda Field Value). | Sin valores de campos para la addenda. | Gestor de addendas multi-sucursal. |

> Los campos de auditoría (`creation_date`, `modified_date`, `created_by`, `modified_by`) son de
> solo lectura y se excluyen.
>
> **Nota de metadata:** el DocType declara `sort_field: priority` y `search_fields: customer,addenda_type`,
> pero el campo `priority` **no está definido** en la lista de campos del `.json`. Es una
> inconsistencia de metadata (no un campo configurable).

---

## Factura Global — funcionalidad pendiente de interfaz y validación integral

Los siguientes campos de **Facturacion Mexico Company Settings** pertenecen a la Factura Global.
**No están operativos desde la interfaz de usuario**: la Factura Global es funcional a nivel de
API/integración pero **no tiene un camino operable desde la UI**, y no ha pasado validación
integral. Se listan solo como referencia; **no** se consideran configuración aprobada para uso
desde interfaz.

| Etiqueta visible | fieldname | Alcance | Obligatorio | Default | Propósito | Si se deja vacío | Funcionalidad que lo usa |
|---|---|---|---|---|---|---|---|
| Customer Público en General | `global_customer` | empresa | No | — | Customer configurado como Público en General (RFC XAXX010101000, régimen 616), receptor de las facturas globales. | No se puede construir la factura global (receptor faltante). | Constructor CFDI de factura global. |
| Item Concepto Factura Global | `global_item` | empresa | No | — | Item que representa el concepto de ventas agrupadas en la factura global (debe tener clave y unidad SAT). | Falta el concepto para la factura global. | Constructor CFDI de factura global. |

> Advertencia: mientras la Factura Global no cuente con interfaz operable ni validación integral,
> configurar estos campos no habilita el flujo desde la UI.
