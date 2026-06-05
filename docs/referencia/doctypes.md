<!--
  ARCHIVO GENERADO AUTOMÁTICAMENTE. NO EDITAR MANUALMENTE.
  Regenerar con: python3 scripts/generate_reference.py
  Fecha generación: 2026-05-30 02:32
-->


# Referencia — DocTypes

DocTypes del app organizados por módulo. Incluye campos activos (excluye Section Break, Column Break, HTML).


## Addendas


### Addenda Configuration

Fuente: `facturacion_mexico/addendas/doctype/addenda_configuration/addenda_configuration.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `customer` | Cliente | Link | ✅ | Customer |
| `addenda_type` | Tipo de Addenda | Link | ✅ | Addenda Type |
| `is_active` | Activo | Check |  |  |
| `priority` | Prioridad | Int |  |  |
| `auto_apply` | Aplicar Automáticamente | Check |  |  |
| `validation_level` | Nivel de Validación | Select |  | Warning… |
| `effective_date` | Fecha de Inicio | Date |  |  |
| `expiry_date` | Fecha de Fin | Date |  |  |
| `notify_on_error` | Notificar Errores por Email | Check |  |  |
| `error_recipients` | Destinatarios de Errores | Small Text |  |  |
| `field_values` | Valores de Campos | Table |  | Addenda Field Value |
| `creation_date` | Fecha de Creación | Datetime |  |  |
| `modified_date` | Fecha de Modificación | Datetime |  |  |
| `created_by` | Creado por | Link |  | User |
| `modified_by` | Modificado por | Link |  | User |


### Addenda Field Definition _Child table_

Fuente: `facturacion_mexico/addendas/doctype/addenda_field_definition/addenda_field_definition.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `field_name` | Nombre Interno | Data | ✅ |  |
| `field_label` | Etiqueta Visible | Data | ✅ |  |
| `field_type` | Tipo de Campo | Select | ✅ | Data… |
| `is_mandatory` | Obligatorio | Check |  |  |
| `default_value` | Valor por Defecto | Data |  |  |
| `options` | Opciones (para Select) | Small Text |  |  |
| `validation_pattern` | Patrón de Validación (Regex) | Data |  |  |
| `help_text` | Texto de Ayuda | Text |  |  |
| `xml_attribute` | Nombre del Atributo XML | Data |  |  |
| `xml_element` | Nombre del Elemento XML | Data |  |  |


### Addenda Field Value _Child table_

Fuente: `facturacion_mexico/addendas/doctype/addenda_field_value/addenda_field_value.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `field_definition` | Definición Campo | Link | ✅ | Addenda Field Definition |
| `field_value` | Valor Campo | Data |  |  |
| `is_dynamic` | Es Dinámico | Check |  |  |
| `dynamic_source` | Fuente Dinámica | Select |  | … |
| `dynamic_field` | Campo Dinámico | Data |  |  |
| `transformation` | Transformación | Select |  | … |
| `validation_pattern` | Patrón de Validación | Data |  |  |
| `default_value` | Valor Por Defecto | Data |  |  |
| `is_required` | Es Requerido | Check |  |  |


### Addenda Product Mapping

Fuente: `facturacion_mexico/addendas/doctype/addenda_product_mapping/addenda_product_mapping.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `customer` | Cliente | Link | ✅ | Customer |
| `item` | Artículo | Link | ✅ | Item |
| `item_code` | Código Artículo | Data |  |  |
| `item_name` | Nombre Artículo | Data |  |  |
| `customer_item_code` | Código Cliente | Data | ✅ |  |
| `customer_item_description` | Descripción Cliente | Data |  |  |
| `customer_uom` | UOM Cliente | Link |  | UOM |
| `is_active` | Activo | Check |  |  |
| `additional_data` | Datos Adicionales | Code |  | JSON |
| `mapping_notes` | Notas del Mapeo | Text |  |  |
| `created_by` | Creado Por | Link |  | User |
| `created_date` | Fecha de Creación | Datetime |  |  |
| `modified_by` | Modificado Por | Link |  | User |
| `modified_date` | Fecha de Modificación | Datetime |  |  |


### Addenda Template

Fuente: `facturacion_mexico/addendas/doctype/addenda_template/addenda_template.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `name1` | Name | Data |  |  |
| `addenda_type` | Tipo de Addenda | Link | ✅ | Addenda Type |
| `template_name` | Nombre del Template | Data | ✅ |  |
| `version` | Versión | Data | ✅ |  |
| `description` | Descripción | Small Text |  |  |
| `is_default` | Es Template Por Defecto | Check |  |  |
| `template_xml` | Template XML | Code | ✅ | XML |
| `usage_notes` | Notas de Uso | Text Editor |  |  |
| `created_by` | Creado Por | Link |  | User |
| `created_date` | Fecha de Creación | Datetime |  |  |
| `modified_by` | Modificado Por | Link |  | User |
| `modified_date` | Fecha de Modificación | Datetime |  |  |


### Addenda Type

Fuente: `facturacion_mexico/addendas/doctype/addenda_type/addenda_type.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `name` | Nombre del Tipo | Data | ✅ |  |
| `description` | Descripción | Text |  |  |
| `version` | Versión | Data | ✅ |  |
| `namespace` | Namespace XML | Data |  |  |
| `is_active` | Activo | Check |  |  |
| `requires_product_mapping` | Requiere Mapeo de Productos | Check |  |  |
| `requires_specific_certificate` | Requiere Certificado Específico | Check |  |  |
| `documentation_url` | URL de Documentación | Data |  |  |
| `xml_template` | Template XML (Jinja2) | Code |  | XML |
| `sample_xml` | XML de Ejemplo | Code |  | XML |
| `xsd_schema` | Esquema XSD | Code |  | XML |
| `field_definitions` | Campos Disponibles | Table |  | Addenda Field Definition |
| `validation_rules` | Reglas de Validación (JSON) | Code |  | JSON |
| `creation_date` | Fecha de Creación | Datetime |  |  |
| `modified_date` | Fecha de Modificación | Datetime |  |  |
| `created_by` | Creado por | Link |  | User |
| `modified_by` | Modificado por | Link |  | User |


## CFDI Recibidos


### CFDI Concepto Mapping

Fuente: `facturacion_mexico/cfdi_recibidos/doctype/cfdi_concepto_mapping/cfdi_concepto_mapping.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `company` | Empresa | Link |  | Company |
| `supplier` | Proveedor | Link |  | Supplier |
| `supplier_rfc` | RFC Proveedor | Data |  |  |
| `sat_product_key` | Clave Producto/Servicio SAT | Data |  |  |
| `target_type` | Tipo de Destino | Select | ✅ | Item… |
| `target_item` | Item | Link |  | Item |
| `target_account` | Cuenta de Gasto | Link |  | Account |
| `target_cost_center` | Centro de Costo | Link |  | Cost Center |
| `is_active` | Activo | Check |  |  |


### CFDI Recibido

Fuente: `facturacion_mexico/cfdi_recibidos/doctype/cfdi_recibido/cfdi_recibido.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `naming_series` | Serie | Select | ✅ | CFDI-REC-.YYYY.-.##### |
| `uuid` | UUID CFDI | Data | ✅ |  |
| `xml_file` | Archivo XML | Attach |  |  |
| `xml_hash` | Hash XML (SHA256) | Data |  |  |
| `company` | Empresa | Link | ✅ | Company |
| `status` | Estado | Data | ✅ |  |
| `no_procesar` | No procesar | Check |  |  |
| `error_message` | Mensaje de Error | Text |  |  |
| `cfdi_type` | Tipo CFDI | Data |  |  |
| `version` | Versión | Data |  |  |
| `issue_date` | Fecha Emisión | Date |  |  |
| `serie` | Serie | Data |  |  |
| `folio` | Folio | Data |  |  |
| `currency` | Moneda | Data |  |  |
| `exchange_rate` | Tipo de Cambio | Float |  |  |
| `fm_payment_method_sat` | Método de Pago SAT | Link |  | Metodo Pago SAT |
| `fm_payment_form_sat` | Forma de Pago SAT | Link |  | Forma Pago SAT |
| `uso_cfdi` | Uso CFDI | Data |  |  |
| `supplier_rfc` | RFC Emisor | Data |  |  |
| `supplier_name` | Nombre Emisor | Data |  |  |
| `supplier_tax_regime` | Régimen Fiscal Emisor | Data |  |  |
| `receiver_rfc` | RFC Receptor | Data |  |  |
| `receiver_name` | Nombre Receptor | Data |  |  |
| `subtotal` | Subtotal | Currency |  |  |
| `discount` | Descuento | Currency |  |  |
| `total_impuestos_trasladados` | Total Impuestos Trasladados | Currency |  |  |
| `total_impuestos_retenidos` | Total Impuestos Retenidos | Currency |  |  |
| `total` | Total | Currency |  |  |
| `impuestos_json` | Impuestos (JSON completo) | JSON |  |  |
| `fecha_timbrado` | Fecha Timbrado | Datetime |  |  |
| `rfc_pac` | RFC del PAC | Data |  |  |
| `no_certificado_sat` | No. Certificado SAT | Data |  |  |
| `no_certificado_emisor` | No. Certificado Emisor | Data |  |  |
| `supplier` | Proveedor | Link |  | Supplier |
| `department` | Departamento | Link |  | Department |
| `purchase_invoice` | Factura de Compra | Link |  | Purchase Invoice |
| `conceptos` | Conceptos | Table |  | CFDI Recibido Concepto |


### CFDI Recibido Concepto _Child table_

Fuente: `facturacion_mexico/cfdi_recibidos/doctype/cfdi_recibido_concepto/cfdi_recibido_concepto.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `sat_product_key` | Clave Producto/Servicio SAT | Data |  |  |
| `no_identificacion` | No. Identificacion | Data |  |  |
| `description` | Descripción | Text |  |  |
| `quantity` | Cantidad | Float |  |  |
| `unit_key` | Clave Unidad | Data |  |  |
| `unit` | Unidad | Data |  |  |
| `unit_price` | Valor Unitario | Currency |  |  |
| `amount` | Importe | Currency |  |  |
| `discount` | Descuento | Currency |  |  |
| `tax_object` | Objeto Impuesto | Data |  |  |
| `item_group` | Grupo de Gasto | Link |  | Item Group |
| `item_code` | Item | Link |  | Item |
| `expense_account` | Cuenta de Gasto | Link |  | Account |
| `item_resolution` | Resolución | Select |  | Pendiente… |
| `item_match_reason` | Motivo de match | Data |  |  |
| `item_match_confidence` | Confianza | Select |  | … |
| `taxes_json` | Impuestos (JSON) | JSON |  |  |


### Configuracion CFDI Recibidos

Fuente: `facturacion_mexico/cfdi_recibidos/doctype/configuracion_cfdi_recibidos/configuracion_cfdi_recibidos.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `company` | Empresa | Link | ✅ | Company |
| `reglas_impuesto` | Reglas de Impuesto | Table |  | Regla Impuesto CFDI Recibido |
| `default_payment_terms_supplier` | Condiciones de Pago por Defecto (Proveedor) | Link |  | Payment Terms Template |
| `mapeo_departamentos` | Mapeo de Departamentos | Table |  | Mapeo Departamento CFDI Recibido |
| `purchase_taxes_template` | Purchase Taxes and Charges Template | Link |  | Purchase Taxes and Charges Template |
| `wizard_completado` | Template Generado | Check |  |  |
| `ultima_generacion` | Última Generación | Datetime |  |  |
| `modo_resolucion_contable` | Modo de resolución contable | Select |  | Manual / Automatico CoA SAT |
| `formato_coa` | Formato CoA | Select |  | \#\#\#\#\#\#\#\# / \#\#\#-\#\#-\#\#\# / \#\#\#.\#\#.\#\#\# |
| `tolerancia_total_absoluta` | Tolerancia Absoluta (MXN) | Float |  |  |
| `tolerancia_total_porcentual` | Tolerancia Porcentual (%) | Percent |  |  |


### Mapeo Departamento CFDI Recibido _Child table_

Fuente: `facturacion_mexico/cfdi_recibidos/doctype/mapeo_departamento_cfdi_recibido/mapeo_departamento_cfdi_recibido.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `department` | Departamento | Link | ✅ | Department |
| `familia_sat` | Familia SAT | Select |  | … |


### Regla Impuesto CFDI Recibido _Child table_

Fuente: `facturacion_mexico/cfdi_recibidos/doctype/regla_impuesto_cfdi_recibido/regla_impuesto_cfdi_recibido.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `impuesto_sat` | Impuesto SAT | Link | ✅ | Impuesto SAT |
| `tipo_factor` | Tipo Factor | Select |  | … |
| `tasa_cuota` | Tasa | Float |  |  |
| `descripcion` | Descripción | Data | ✅ |  |
| `es_retencion` | Es Retención | Check |  |  |
| `cuenta_impuesto` | Cuenta Contable | Link |  | Account |
| `activo` | Activo | Check |  |  |


### Regla Item CFDI Recibido

Fuente: `facturacion_mexico/cfdi_recibidos/doctype/regla_item_cfdi_recibido/regla_item_cfdi_recibido.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `target_item` | Artículo | Link | ✅ | Item |
| `match_reason` | Motivo / Descripcion | Data |  |  |
| `company` | Empresa | Link |  | Company |
| `supplier_rfc` | RFC Proveedor | Data |  |  |
| `sat_product_key` | Clave SAT Producto/Servicio | Link |  | SAT Producto Servicio |
| `keywords` | Palabras clave | Data |  |  |
| `priority` | Prioridad | Int |  |  |
| `is_active` | Activa | Check |  |  |


## Catalogos SAT


### Forma Pago SAT

Fuente: `facturacion_mexico/catalogos_sat/doctype/forma_pago_sat/forma_pago_sat.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `code` | Código | Data | ✅ |  |
| `description` | Descripción | Data | ✅ |  |
| `vigencia_desde` | Vigencia Desde | Date |  |  |
| `vigencia_hasta` | Vigencia Hasta | Date |  |  |


### Impuesto SAT

Fuente: `facturacion_mexico/catalogos_sat/doctype/impuesto_sat/impuesto_sat.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `code` | Código | Data | ✅ |  |
| `description` | Descripción | Data | ✅ |  |
| `vigencia_desde` | Vigencia Desde | Date |  |  |
| `vigencia_hasta` | Vigencia Hasta | Date |  |  |


### Metodo Pago SAT

Fuente: `facturacion_mexico/catalogos_sat/doctype/metodo_pago_sat/metodo_pago_sat.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `code` | Código | Data | ✅ |  |
| `description` | Descripción | Data | ✅ |  |
| `vigencia_desde` | Vigencia Desde | Date |  |  |
| `vigencia_hasta` | Vigencia Hasta | Date |  |  |


### Moneda SAT

Fuente: `facturacion_mexico/catalogos_sat/doctype/moneda_sat/moneda_sat.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `code` | Código | Data | ✅ |  |
| `description` | Descripción | Data | ✅ |  |
| `decimales` | Decimales | Int |  |  |
| `vigencia_desde` | Vigencia Desde | Date |  |  |
| `vigencia_hasta` | Vigencia Hasta | Date |  |  |


### Regimen Fiscal SAT

Fuente: `facturacion_mexico/catalogos_sat/doctype/regimen_fiscal_sat/regimen_fiscal_sat.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `code` | Código | Data | ✅ |  |
| `description` | Descripción | Data | ✅ |  |
| `aplica_fisica` | Aplica Persona Física | Check |  |  |
| `aplica_moral` | Aplica Persona Moral | Check |  |  |
| `vigencia_desde` | Vigencia Desde | Date |  |  |
| `vigencia_hasta` | Vigencia Hasta | Date |  |  |


### SAT Producto Servicio

Fuente: `facturacion_mexico/catalogos_sat/doctype/sat_producto_servicio/sat_producto_servicio.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `codigo` | Código | Data | ✅ |  |
| `descripcion` | Descripción | Data | ✅ |  |
| `incluye_objeto_impuesto` | Incluye Objeto Impuesto | Select |  | 01… |
| `complemento` | Complemento | Data |  |  |
| `fecha_inicio_vigencia` | Fecha Inicio Vigencia | Date |  |  |
| `fecha_fin_vigencia` | Fecha Fin Vigencia | Date |  |  |
| `palabras_similares` | Palabras Similares | Text |  |  |


### Tasa IVA SAT

Fuente: `facturacion_mexico/catalogos_sat/doctype/tasa_iva_sat/tasa_iva_sat.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `clave` | Clave | Data | ✅ |  |
| `descripcion` | Descripción | Data | ✅ |  |
| `tasa_cuota` | Tasa | Float | ✅ |  |
| `activo` | Activo | Check |  |  |


### Uso CFDI SAT

Fuente: `facturacion_mexico/catalogos_sat/doctype/uso_cfdi_sat/uso_cfdi_sat.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `code` | Código | Data | ✅ |  |
| `description` | Descripción | Data | ✅ |  |
| `aplica_fisica` | Aplica Persona Física | Check |  |  |
| `aplica_moral` | Aplica Persona Moral | Check |  |  |
| `vigencia_desde` | Vigencia Desde | Date |  |  |
| `vigencia_hasta` | Vigencia Hasta | Date |  |  |


## Complementos Pago


### Complemento Pago MX _Submittable_

Fuente: `facturacion_mexico/complementos_pago/doctype/complemento_pago_mx/complemento_pago_mx.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `payment_entry` | Payment Entry | Link |  | Payment Entry |
| `company` | Empresa | Link |  | Company |
| `customer` | Cliente | Link |  | Customer |
| `status` | Estado | Select |  | … |
| `fecha_pago` | Fecha de Pago | Datetime | ✅ |  |
| `forma_pago_p` | Forma de Pago | Link | ✅ | Forma Pago SAT |
| `moneda_p` | Moneda | Link | ✅ | Moneda SAT |
| `monto_p` | Monto | Currency | ✅ |  |
| `tipo_cambio_p` | Tipo de Cambio | Currency |  |  |
| `uuid_sat` | UUID SAT | Data |  |  |
| `serie_folio` | Serie y Folio | Data |  |  |
| `folio_fiscal` | Folio Fiscal | Data |  |  |
| `estatus_sat` | Estatus SAT | Select |  | … |
| `fecha_timbrado` | Fecha de Timbrado | Datetime |  |  |
| `id_documento` | ID Documento | Data |  |  |
| `fecha_folio_fiscal` | Fecha Folio Fiscal | Date |  |  |
| `no_certificado_sat` | No. Certificado SAT | Data |  |  |
| `fecha_certificacion_sat` | Fecha Certificación SAT | Datetime |  |  |
| `pac_cert_sat` | PAC Certificado SAT | Data |  |  |
| `version` | Versión Complemento | Data |  |  |
| `version_cfdi` | Versión CFDI | Data |  |  |
| `facturapi_id` | FacturAPI ID | Data |  |  |
| `pdf_file` | PDF | Attach |  |  |
| `xml_file` | XML | Attach |  |  |
| `fm_ultimo_response_log` | Último Log de Respuesta | Link |  | FacturAPI Response Log |
| `num_operacion` | Número de Operación | Data |  |  |
| `rfc_emisor_cta_ord` | RFC Emisor Cuenta Ordenante | Data |  |  |
| `nom_banco_ord_ext` | Nombre Banco Ordenante Extranjero | Data |  |  |
| `cta_ordenante` | Cuenta Ordenante | Data |  |  |
| `rfc_emisor_cta_ben` | RFC Emisor Cuenta Beneficiario | Data |  |  |
| `cta_beneficiario` | Cuenta Beneficiario | Data |  |  |
| `tipo_cad_pago` | Tipo Cadena Pago | Select |  | … |
| `cert_pago` | Certificado Pago | Long Text |  |  |
| `cad_pago` | Cadena Pago | Long Text |  |  |
| `sello_pago` | Sello Pago | Long Text |  |  |
| `documentos_relacionados` | Documentos Relacionados | Table |  | Documento Relacionado Pago MX |
| `detalles_impuestos` | Impuestos Trasladados y Retenidos | Table |  | Detalle Complemento Pago MX |
| `naming_series` | Serie de Nomenclatura | Select | ✅ | COMP-PAG-.YYYY.- |
| `amended_from` | Amended From | Link |  | Complemento Pago MX |


### Detalle Complemento Pago MX _Child table_

Fuente: `facturacion_mexico/complementos_pago/doctype/detalle_complemento_pago_mx/detalle_complemento_pago_mx.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `tipo_impuesto` | Tipo Impuesto | Select | ✅ | … |
| `impuesto` | Impuesto | Link | ✅ | Impuesto SAT |
| `tipo_factor` | Tipo Factor | Select | ✅ | … |
| `tasa_cuota` | Tasa o Cuota | Currency |  |  |
| `base_dr` | Base DR | Currency | ✅ |  |
| `importe_dr` | Importe DR | Currency |  |  |
| `documento_relacionado` | ID Documento Relacionado | Data | ✅ |  |


### Documento Relacionado Pago MX _Child table_

Fuente: `facturacion_mexico/complementos_pago/doctype/documento_relacionado_pago_mx/documento_relacionado_pago_mx.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `id_documento` | ID Documento | Data | ✅ |  |
| `serie` | Serie | Data |  |  |
| `folio` | Folio | Data |  |  |
| `moneda_dr` | Moneda | Link | ✅ | Moneda SAT |
| `equivalencia_dr` | Equivalencia DR | Currency |  |  |
| `num_parcialidad` | Número Parcialidad | Int | ✅ |  |
| `imp_saldo_ant` | Importe Saldo Anterior | Currency | ✅ |  |
| `imp_pagado` | Importe Pagado | Currency | ✅ |  |
| `imp_saldo_insoluto` | Importe Saldo Insoluto | Currency |  |  |
| `objeto_imp_dr` | Objeto Impuesto | Select | ✅ | … |
| `tipo_documento` | Tipo Documento | Select |  | … |
| `referencia_documento` | Referencia Documento | Dynamic Link |  | tipo_documento |


## Dashboard Fiscal


### Dashboard User Preference

Fuente: `facturacion_mexico/dashboard_fiscal/doctype/dashboard_user_preference/dashboard_user_preference.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `user` | Usuario | Link | ✅ | User |
| `last_viewed` | Último Acceso | Datetime |  |  |
| `default_company` | Company por Defecto | Link |  | Company |
| `dashboard_theme` | Tema Dashboard | Select |  | Light… |
| `dashboard_layout` | Layout del Dashboard | JSON |  |  |
| `custom_date_range` | Rango de Fechas por Defecto | Select |  | Today… |
| `auto_refresh_enabled` | Auto-refresh Activado | Check |  |  |
| `refresh_interval` | Intervalo Refresh (segundos) | Int |  |  |
| `favorite_widgets` | Widgets Favoritos (JSON) | Small Text |  |  |
| `hidden_widgets` | Widgets Ocultos (JSON) | Small Text |  |  |
| `notification_preferences` | Preferencias de Notificaciones | JSON |  |  |
| `email_digest_enabled` | Resumen Email Activado | Check |  |  |
| `alert_frequency` | Frecuencia de Alertas | Select |  | Immediate… |
| `mobile_notifications` | Notificaciones Móviles | Check |  |  |


### Dashboard Widget Allowed Role _Child table_

Fuente: `facturacion_mexico/dashboard_fiscal/doctype/dashboard_widget_allowed_role/dashboard_widget_allowed_role.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `role` | Rol | Link | ✅ | Role |


### Dashboard Widget Config

Fuente: `facturacion_mexico/dashboard_fiscal/doctype/dashboard_widget_config/dashboard_widget_config.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `widget_name` | Nombre del Widget | Data | ✅ |  |
| `widget_code` | Código del Widget | Data | ✅ |  |
| `widget_type` | Tipo de Widget | Select | ✅ | KPI… |
| `module` | Módulo | Select | ✅ | Timbrado… |
| `is_active` | Widget Activo | Check |  |  |
| `display_order` | Orden de Display | Int |  |  |
| `grid_row` | Fila del Grid | Int | ✅ |  |
| `grid_col` | Columna del Grid | Int | ✅ |  |
| `grid_width` | Ancho del Grid | Int | ✅ |  |
| `grid_height` | Alto del Grid | Int | ✅ |  |
| `css_classes` | Clases CSS | Data |  |  |
| `custom_styles` | Estilos Personalizados (JSON) | Code |  |  |
| `data_source` | Fuente de Datos | Select |  | Registry KPI… |
| `kpi_function` | Función KPI | Data |  |  |
| `chart_config` | Configuración del Chart (JSON) | Code |  |  |
| `custom_query` | Query Personalizada (SQL) | Code |  |  |
| `refresh_interval` | Intervalo de Actualización (seg) | Int |  |  |
| `cache_enabled` | Cache Habilitado | Check |  |  |
| `cache_ttl` | TTL del Cache (seg) | Int |  |  |
| `title_template` | Template del Título | Data |  |  |
| `value_format` | Formato del Valor | Select |  | currency… |
| `color_config` | Configuración de Colores (JSON) | Code |  |  |
| `icon_config` | Configuración del Icono (JSON) | Code |  |  |
| `show_trend` | Mostrar Tendencia | Check |  |  |
| `trend_period` | Período de Tendencia (días) | Int |  |  |
| `show_comparison` | Mostrar Comparación | Check |  |  |
| `allowed_roles` | Roles Permitidos | Table |  | Dashboard Widget Allowed Role |
| `required_permissions` | Permisos Requeridos | Text |  |  |
| `last_updated` | Última Actualización | Datetime |  |  |
| `view_count` | Veces Visualizado | Int |  |  |
| `last_accessed` | Último Acceso | Datetime |  |  |


### Fiscal Alert Notify Role _Child table_

Fuente: `facturacion_mexico/dashboard_fiscal/doctype/fiscal_alert_notify_role/fiscal_alert_notify_role.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `role` | Rol | Link | ✅ | Role |


### Fiscal Alert Notify User _Child table_

Fuente: `facturacion_mexico/dashboard_fiscal/doctype/fiscal_alert_notify_user/fiscal_alert_notify_user.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `user` | Usuario | Link | ✅ | User |


### Fiscal Alert Rule

Fuente: `facturacion_mexico/dashboard_fiscal/doctype/fiscal_alert_rule/fiscal_alert_rule.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `alert_name` | Nombre de la Alerta | Data | ✅ |  |
| `alert_code` | Código de Alerta | Data | ✅ |  |
| `alert_type` | Tipo de Alerta | Select | ✅ | Error… |
| `module` | Módulo | Select | ✅ | Timbrado… |
| `is_active` | Alerta Activa | Check |  |  |
| `priority` | Prioridad | Int |  |  |
| `condition_type` | Tipo de Condición | Select |  | Count… |
| `condition_field` | Campo a Evaluar | Data |  |  |
| `condition_operator` | Operador | Select |  | >… |
| `condition_value` | Valor de Comparación | Float |  |  |
| `custom_condition` | Condición Personalizada (Python) | Code |  |  |
| `message_template` | Plantilla de Mensaje | Text | ✅ |  |
| `notify_roles` | Roles a Notificar | Table |  | Fiscal Alert Notify Role |
| `notify_users` | Usuarios Específicos | Table |  | Fiscal Alert Notify User |
| `send_email` | Enviar Notificación por Email | Check |  |  |
| `show_in_dashboard` | Mostrar en Dashboard | Check |  |  |
| `last_triggered` | Última Activación | Datetime |  |  |
| `trigger_count` | Veces Activada | Int |  |  |


### Fiscal Dashboard Config _Single_

Fuente: `facturacion_mexico/dashboard_fiscal/doctype/fiscal_dashboard_config/fiscal_dashboard_config.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `refresh_interval` | Intervalo de Actualización (segundos) | Int | ✅ |  |
| `enable_auto_refresh` | Habilitar Actualización Automática | Check |  |  |
| `cache_duration` | Duración Cache (segundos) | Int | ✅ |  |
| `performance_mode` | Modo Rendimiento | Check |  |  |
| `default_period` | Período Por Defecto | Select | ✅ | today… |
| `dashboard_theme` | Tema del Dashboard | Select | ✅ | light… |
| `show_trend_indicators` | Mostrar Indicadores de Tendencia | Check |  |  |
| `enable_drill_down` | Habilitar Drill-Down | Check |  |  |
| `show_monetary_in_thousands` | Mostrar Montos en Miles | Check |  |  |
| `default_widgets_layout` | Layout Por Defecto de Widgets | JSON |  |  |
| `enable_alerts` | Sistema de Alertas Activo | Check |  |  |
| `alert_check_frequency` | Frecuencia de Verificación de Alertas | Select |  | 5min… |


### Fiscal Health Factor _Child table_

Fuente: `facturacion_mexico/dashboard_fiscal/doctype/fiscal_health_factor/fiscal_health_factor.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `factor_type` | Tipo de Factor | Select | ✅ | Timbrado… |
| `description` | Descripción | Text | ✅ |  |
| `impact_score` | Impacto Score | Int |  |  |
| `calculation_details` | Detalles de Cálculo | Small Text |  |  |


### Fiscal Health Recommendation _Child table_

Fuente: `facturacion_mexico/dashboard_fiscal/doctype/fiscal_health_recommendation/fiscal_health_recommendation.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `category` | Categoría | Select | ✅ | Timbrado… |
| `recommendation` | Recomendación | Text | ✅ |  |
| `priority` | Prioridad | Select | ✅ | High… |
| `estimated_days` | Días Estimados | Int |  |  |
| `action_required` | Acción Requerida | Small Text |  |  |
| `responsible_role` | Rol Responsable | Link |  | Role |
| `status` | Estado | Select |  | Pending… |
| `implementation_date` | Fecha Implementación | Date |  |  |
| `completion_notes` | Notas de Completado | Small Text |  |  |


### Fiscal Health Score

Fuente: `facturacion_mexico/dashboard_fiscal/doctype/fiscal_health_score/fiscal_health_score.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `score_date` | Fecha del Score | Date | ✅ |  |
| `company` | Company | Link | ✅ | Company |
| `overall_score` | Score General | Float |  |  |
| `calculation_method` | Método de Cálculo | Select |  | Weighted Average… |
| `last_calculated` | Última Calculación | Datetime |  |  |
| `timbrado_score` | Score Timbrado | Float |  |  |
| `ppd_score` | Score PPD | Float |  |  |
| `ereceipts_score` | Score E-Receipts | Float |  |  |
| `addendas_score` | Score Addendas | Float |  |  |
| `global_invoices_score` | Score Facturas Globales | Float |  |  |
| `rules_compliance_score` | Score Cumplimiento Reglas | Float |  |  |
| `factors_positive` | Factores Positivos | Table |  | Fiscal Health Factor |
| `factors_negative` | Factores Negativos | Table |  | Fiscal Health Factor |
| `recommendations` | Recomendaciones | Table |  | Fiscal Health Recommendation |
| `created_by` | Creado por | Link |  | User |
| `calculation_duration_ms` | Duración Cálculo (ms) | Int |  |  |


## EReceipts


### EReceipt MX _Submittable_

Fuente: `facturacion_mexico/ereceipts/doctype/ereceipt_mx/ereceipt_mx.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `naming_series` | Serie de Nomenclatura | Select | ✅ | E-REC-.YYYY.- |
| `sales_invoice` | Sales Invoice | Link |  | Sales Invoice |
| `company` | Company | Link | ✅ | Company |
| `customer` | Customer | Link |  | Customer |
| `customer_name` | Customer Name | Data |  |  |
| `total` | Total | Currency | ✅ |  |
| `date_issued` | Fecha de Emisión | Date | ✅ |  |
| `status` | Status | Select | ✅ | open… |
| `expiry_type` | Tipo de Vencimiento | Select | ✅ | Fixed Days… |
| `expiry_days` | Días para Vencer | Int |  |  |
| `expiry_date` | Fecha de Vencimiento | Date | ✅ |  |
| `days_to_expire` | Días Restantes | Int |  |  |
| `facturapi_id` | FacturAPI ID | Data |  |  |
| `key` | Clave de Autofactura | Data |  |  |
| `self_invoice_url` | URL de Autofacturación | Data |  |  |
| `receipt_pdf_url` | URL del PDF | Data |  |  |
| `invoiced` | Ya Facturado | Check |  |  |
| `related_factura_fiscal` | Factura Fiscal Generada | Link |  | Factura Fiscal Mexico |
| `included_in_global` | Incluido en Factura Global | Check |  |  |
| `global_invoice_date` | Fecha Factura Global | Date |  |  |
| `creation_method` | Método de Creación | Select |  | Automatic… |
| `created_by_user` | Creado Por | Link |  | User |
| `last_status_check` | Última Verificación de Status | Datetime |  |  |
| `notes` | Notas | Small Text |  |  |
| `amended_from` | Amended From | Link |  | EReceipt MX |


## Facturacion Fiscal


### Configuracion Fiscal Mexico

Fuente: `facturacion_mexico/facturacion_fiscal/doctype/configuracion_fiscal_mexico/configuracion_fiscal_mexico.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `company` | Empresa | Link | ✅ | Company |
| `enable_exento` | IVA Exento | Check |  |  |
| `enable_frontera` | Zona Fronteriza | Check |  |  |
| `enable_exportacion` | Exportación (IVA 0%) | Check |  |  |
| `enable_ieps_alcohol` | IEPS Alcohol | Check |  |  |
| `enable_ieps_azucar` | IEPS Azúcar/Bebidas | Check |  |  |
| `enable_ieps_combustibles` | IEPS Combustibles | Check |  |  |
| `enable_ieps_tabaco` | IEPS Tabaco | Check |  |  |
| `enable_ret_honorarios` | Retenciones Honorarios | Check |  |  |
| `enable_ret_arrendamiento` | Retenciones Arrendamiento | Check |  |  |
| `enable_ret_autotransporte` | Retenciones Autotransporte | Check |  |  |
| `enable_ret_resico` | Retenciones RESICO | Check |  |  |
| `tasa_isr_resico` | Tasa ISR RESICO | Percent |  |  |
| `mapeo_cuentas` | Cuentas de Impuestos | Table | ✅ | Mapeo Cuenta Fiscal Mexico |
| `configuracion_completa` | Configuración Completa | Check |  |  |
| `ultima_actualizacion` | Última Actualización | Datetime |  |  |
| `templates_generados` | Templates Generados | Int |  |  |
| `version_esquema` | Versión Esquema | Data |  |  |


### Configuracion Reclasificacion Fiscal Mexico

Fuente: `facturacion_mexico/facturacion_fiscal/doctype/configuracion_reclasificacion_fiscal_mexico/configuracion_reclasificacion_fiscal_mexico.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `company` | Empresa | Link | ✅ | Company |
| `ultima_deteccion` | Última Carga | Datetime |  |  |
| `ultima_generacion` | Último Aplicar | Datetime |  |  |
| `reglas` | Reglas | Table |  | Regla Reclasificacion Fiscal |


### Control Panel Settings

Fuente: `facturacion_mexico/facturacion_fiscal/doctype/control_panel_settings/control_panel_settings.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `pac_failure_threshold` | Umbral PAC Failure Rate (%) | Int | ✅ |  |
| `recovery_tasks_threshold` | Umbral Recovery Tasks Pendientes | Int | ✅ |  |
| `response_time_threshold` | Umbral Tiempo Respuesta (ms) | Int | ✅ |  |
| `filesystem_usage_threshold` | Umbral Filesystem Usage (%) | Int | ✅ |  |
| `email_notifications` | Activar Notificaciones Email | Check |  |  |
| `email_recipients` | Email Recipients (separados por coma) | Small Text |  |  |
| `system_notifications` | Activar Notificaciones Sistema Frappe | Check |  |  |
| `webhook_notifications` | Activar Webhook Notifications | Check |  |  |
| `webhook_url` | Webhook URL (Slack, Teams, etc.) | Data |  |  |
| `check_interval` | Frecuencia de Verificación | Select | ✅ | 5 minutos… |
| `alert_cooldown` | Cooldown Entre Alertas (minutos) | Int | ✅ |  |


### FacturAPI Response Log

Fuente: `facturacion_mexico/facturacion_fiscal/doctype/facturapi_response_log/facturapi_response_log.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `naming_series` | Serie de Numeración | Select | ✅ | FAPI-LOG-.YYYY.- |
| `request_id` | ID de Solicitud | Data |  |  |
| `request_timestamp` | Timestamp de Solicitud | Datetime |  |  |
| `request_payload` | Payload de Auditoría (no payload real a FacturAPI) | JSON |  |  |
| `factura_fiscal_mexico` | Factura Fiscal Mexico | Link |  | Factura Fiscal Mexico |
| `complemento_pago_mx` | Complemento Pago MX | Link |  | Complemento Pago MX |
| `timestamp` | Fecha y Hora | Datetime | ✅ |  |
| `operation_type` | Tipo de Operación | Select | ✅ | Timbrado… |
| `timeout_flag` | Timeout | Check |  |  |
| `retry_of` | Reintento de | Link |  | FacturAPI Response Log |
| `success` | Éxito | Check |  |  |
| `status_code` | Código HTTP | Data |  |  |
| `response_time_ms` | Tiempo de Respuesta (ms) | Float |  |  |
| `facturapi_response` | Respuesta JSON Completa | JSON |  |  |
| `error_message` | Mensaje de Error | Text |  |  |
| `user_role` | Rol de Usuario | Data |  |  |
| `ip_address` | Dirección IP | Data |  |  |


### Factura Fiscal Mexico _Submittable_

Fuente: `facturacion_mexico/facturacion_fiscal/doctype/factura_fiscal_mexico/factura_fiscal_mexico.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `naming_series` | Serie de Numeración | Select | ✅ | FFMX-.YYYY.- |
| `sales_invoice` | Factura de Venta | Link | ✅ | Sales Invoice |
| `company` | Empresa Vendedora | Link | ✅ | Company |
| `customer` | Cliente | Link | ✅ | Customer |
| `fm_facturar_venta_mostrador` | ¿Facturar a Venta Mostrador? | Check |  |  |
| `status` | Estado Fiscal | Select | ✅ | BORRADOR… |
| `fm_payment_method_sat` | Método de Pago SAT | Select |  | PUE… |
| `fm_forma_pago_timbrado` | Forma de Pago para Timbrado | Link |  | Mode of Payment |
| `fm_tipo_comprobante` | Tipo de comprobante (SAT) | Select | ✅ |  |
| `fm_tipo_relacion_sat` | Tipo de Relación (SAT) | Select |  |  |
| `fm_uuid_relacionado` | UUID relacionado | Data |  |  |
| `fecha_timbrado` | Fecha de Timbrado | Datetime |  |  |
| `facturapi_id` | FacturAPI ID | Data |  |  |
| `fm_cfdi_use` | Uso del CFDI | Link |  | Uso CFDI SAT |
| `fm_uuid` | UUID Fiscal | Data |  |  |
| `fm_motivo_cancelacion` | Motivo Cancelación SAT | Select |  | 01… |
| `fm_serie_folio` | Serie y Folio | Data |  |  |
| `fm_lugar_expedicion` | Lugar de Expedición | Data |  |  |
| `serie` | Serie | Data |  |  |
| `folio` | Folio | Data |  |  |
| `total_fiscal` | Total Fiscal | Currency |  |  |
| `si_total_antes_iva` | Total antes de IVA (SI) | Currency |  |  |
| `si_iva` | IVA (SI) | Currency |  |  |
| `si_otros_impuestos` | Otros Impuestos (SI) | Currency |  |  |
| `si_total_neto` | Total Neto (SI) | Currency |  |  |
| `pdf_file` | Archivo PDF | Attach |  |  |
| `xml_file` | Archivo XML | Attach |  |  |
| `fm_enviar_email_timbrado` | Enviar CFDI por email al timbrar | Check |  |  |
| `cancellation_reason` | Motivo de Cancelación | Select |  | 01 - Comprobantes emitidos con errores con relación… |
| `cancellation_date` | Fecha de Cancelación | Datetime |  |  |
| `fm_cp_cliente` | CP Cliente | Data |  |  |
| `fm_email_facturacion` | Email Facturación | Data |  |  |
| `fm_rfc_cliente` | RFC Cliente | Data |  |  |
| `fm_tax_system` | Régimen Fiscal (Código) | Data |  |  |
| `fm_direccion_principal_link` | Dirección Principal | Link |  | Address |
| `fm_direccion_principal_display` | Dirección Completa | Small Text |  |  |
| `fm_last_pac_sync` | Última Sincronización PAC | Datetime |  |  |
| `fm_sync_status` | Estado de Sincronización | Select |  | synced… |
| `fm_sync_error` | Error de Sincronización | Text |  |  |
| `fm_xml_url` | URL del XML | Data |  |  |
| `fm_pdf_url` | URL del PDF | Data |  |  |
| `fm_last_response_log` | Último Log de Respuesta | Link |  | FacturAPI Response Log |


### Facturacion Mexico Settings _Single_

Fuente: `facturacion_mexico/facturacion_fiscal/doctype/facturacion_mexico_settings/facturacion_mexico_settings.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `name` | Nombre | Data | ✅ |  |
| `api_key` | API Key Producción | Password |  |  |
| `test_api_key` | API Key Pruebas | Password |  |  |
| `sandbox_mode` | Modo Sandbox | Check |  |  |
| `timeout` | Timeout (segundos) | Int |  |  |
| `rfc_emisor` | RFC Emisor | Data | ✅ |  |
| `lugar_expedicion` | Lugar de Expedición | Data | ✅ |  |
| `ereceipt_mode_default` | Modo Facturación por Defecto | Select |  | Normal… |
| `ereceipt_expiry_type_default` | Tipo Vencimiento por Defecto | Select |  | Fixed Days… |
| `ereceipt_expiry_days_default` | Días Vencimiento por Defecto | Int |  |  |
| `ereceipt_notification_email` | Email Notificaciones E-Receipt | Data |  |  |
| `ereceipt_self_invoice_message` | Mensaje E-Receipt | Text |  |  |
| `send_email_default` | Enviar Email por Defecto | Check |  |  |
| `download_files_default` | Descargar PDF/XML automáticamente | Check |  |  |
| `enable_global_invoices` | Habilitar Facturas Globales | Check |  |  |
| `global_invoice_serie` | Serie Facturas Globales | Data |  |  |
| `global_invoice_periodicidad` | Periodicidad por Defecto | Select |  | Diaria… |
| `auto_generate_global` | Generación Automática | Check |  |  |
| `global_generation_day` | Día de Generación | Int |  |  |
| `global_generation_time` | Hora de Generación | Time |  |  |
| `include_zero_receipts` | Incluir Períodos Vacíos | Check |  |  |
| `notify_global_generation` | Notificar por Email | Check |  |  |
| `global_notification_emails` | Emails de Notificación | Small Text |  |  |
| `enable_fiscal_dashboard` | Habilitar Dashboard Fiscal | Check |  |  |
| `dashboard_default_company` | Company por Defecto | Link |  | Company |
| `dashboard_data_retention_days` | Días Retención Datos | Int |  |  |
| `enable_dashboard_notifications` | Notificaciones Activas | Check |  |  |
| `dashboard_admin_roles` | Roles Administrativos | Small Text |  |  |
| `ereceipt_monthly_limit` | Límite Mensual E-Receipts | Int |  |  |
| `global_invoice_monthly_limit` | Límite Mensual Facturas Globales | Int |  |  |
| `customer_email_fallback` | Email Fallback Cliente | Data |  |  |
| `metodo_pago_default` | Método de Pago por Defecto | Select |  | PUE… |
| `habilitar_traslado` | Habilitar Traslado (T) | Check |  |  |
| `permitir_editar_relacion_en_egreso` | Permitir editar relación en Egreso (avanzado) | Check |  |  |
| `enable_ereceipts` | Habilitar E-Receipts | Check |  |  |
| `log_retention_days` | Días de retención de logs | Int |  |  |


### IEPS Cuota SAT

Fuente: `facturacion_mexico/facturacion_fiscal/doctype/ieps_cuota_sat/ieps_cuota_sat.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `naming_series` | Serie | Select | ✅ | IEPS-CUOTA-.YYYY.- |
| `company` | Empresa | Link | ✅ | Company |
| `clave_prod_serv` | Clave Producto/Servicio SAT | Link | ✅ | SAT Producto Servicio |
| `descripcion` | Descripción | Data |  |  |
| `uom` | Unidad de Medida | Link | ✅ | UOM |
| `cuota` | Cuota por Unidad | Currency | ✅ |  |
| `cuenta_ieps` | Cuenta IEPS | Link |  | Account |
| `vigencia_desde` | Vigente Desde | Date | ✅ |  |
| `vigencia_hasta` | Vigente Hasta | Date |  |  |


### Mapeo Cuenta Fiscal Mexico _Child table_

Fuente: `facturacion_mexico/facturacion_fiscal/doctype/mapeo_cuenta_fiscal_mexico/mapeo_cuenta_fiscal_mexico.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `rol_fiscal` | Tipo de Impuesto | Select | ✅ | IVA por Pagar (Nacional)… |
| `cuenta_impuesto` | Cuenta de Impuesto | Link | ✅ | Account |
| `sugerido_automaticamente` | Sugerido Automáticamente | Check |  |  |
| `justificacion_sugerencia` | Justificación | Small Text |  |  |
| `estado_validacion` | Estado | Select |  | Válido… |
| `es_retencion` | Es Retención | Check |  |  |
| `tipo_factor` | Tipo de Factor SAT | Select |  | Tasa… |
| `integra_base_iva` | Integra Base IVA | Check |  |  |


### Mapeo Reclasificacion Fiscal Payment Entry

Fuente: `facturacion_mexico/facturacion_fiscal/doctype/mapeo_reclasificacion_fiscal_payment_entry/mapeo_reclasificacion_fiscal_payment_entry.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `company` | Empresa | Link | ✅ | Company |
| `tipo_operacion` | Tipo de Operación | Select | ✅ | … |
| `activo` | Activo | Check |  |  |
| `cuenta_origen` | Cuenta Origen (al timbrar) | Link | ✅ | Account |
| `cuenta_destino` | Cuenta Destino (al cobrar/pagar) | Link | ✅ | Account |


### Regla Reclasificacion Fiscal _Child table_

Fuente: `facturacion_mexico/facturacion_fiscal/doctype/regla_reclasificacion_fiscal/regla_reclasificacion_fiscal.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `rol_fiscal` | Tipo de Impuesto | Data |  |  |
| `cuenta_origen` | Cuenta Origen (al timbrar) | Link |  | Account |
| `cuenta_destino` | Cuenta Destino (al cobrar) | Link |  | Account |
| `mrfpe_ref` | Mapeo Activo | Link |  | Mapeo Reclasificacion Fiscal Payment Entry |
| `tipo_operacion` | Tipo | Select |  | … |
| `source_type` | Origen | Select |  | Ingresos / CFM… |
| `nota` | Nota | Small Text |  |  |


### System Health Monitor

Fuente: `facturacion_mexico/facturacion_fiscal/doctype/system_health_monitor/system_health_monitor.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `timestamp` | Timestamp | Datetime | ✅ |  |
| `pac_success_rate` | PAC Success Rate (%) | Float |  |  |
| `recovery_tasks_pending` | Recovery Tasks Pendientes | Int |  |  |
| `avg_response_time` | Tiempo Respuesta Promedio (ms) | Int |  |  |
| `failed_transactions` | Transacciones Fallidas (24h) | Int |  |  |
| `filesystem_usage` | Filesystem Usage (%) | Float |  |  |


## Facturas Globales


### Factura Global Detail _Child table_

Fuente: `facturacion_mexico/facturas_globales/doctype/factura_global_detail/factura_global_detail.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `ereceipt` | E-Receipt | Link | ✅ | EReceipt MX |
| `folio_receipt` | Folio Receipt | Data |  |  |
| `fecha_receipt` | Fecha Receipt | Date |  |  |
| `monto` | Monto | Currency |  |  |
| `customer_name` | Nombre Cliente | Data |  |  |
| `included_in_cfdi` | Incluido en CFDI | Check |  |  |


### Factura Global MX _Submittable_

Fuente: `facturacion_mexico/facturas_globales/doctype/factura_global_mx/factura_global_mx.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `company` | Company | Link | ✅ | Company |
| `naming_series` | Serie | Select |  | FG-.YYYY.-.MM.-… |
| `periodo_inicio` | Período Inicio | Date | ✅ |  |
| `periodo_fin` | Período Fin | Date | ✅ |  |
| `periodicidad` | Periodicidad | Select | ✅ | Diaria… |
| `receipts_detail` | Detalle de Receipts | Table |  | Factura Global Detail |
| `total_periodo` | Total del Período | Currency |  |  |
| `cantidad_receipts` | Cantidad de Receipts | Int |  |  |
| `facturapi_id` | FacturAPI ID | Data |  |  |
| `uuid` | UUID Fiscal | Data |  |  |
| `serie` | Serie Fiscal | Data |  |  |
| `folio` | Folio Fiscal | Data |  |  |
| `status` | Status | Select | ✅ | Draft… |
| `processing_time` | Tiempo de Procesamiento (s) | Float |  |  |
| `pdf_file` | PDF Timbrado | Attach |  |  |
| `xml_file` | XML Timbrado | Attach |  |  |
| `error_message` | Mensaje de Error | Text |  |  |
| `created_by` | Creado por | Link |  | User |
| `creation_timestamp` | Fecha de Creación | Datetime |  |  |
| `modified_by` | Modificado por | Link |  | User |
| `modified_timestamp` | Fecha de Modificación | Datetime |  |  |


## Motor Reglas


### Fiscal Validation Rule

Fuente: `facturacion_mexico/motor_reglas/doctype/fiscal_validation_rule/fiscal_validation_rule.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `rule_name` | Nombre de la Regla | Data | ✅ |  |
| `rule_code` | Código de Regla | Data | ✅ |  |
| `description` | Descripción | Text |  |  |
| `rule_type` | Tipo de Regla | Select | ✅ | Validation… |
| `apply_to_doctype` | Aplicar a DocType | Select | ✅ | Sales Invoice… |
| `is_active` | Activa | Check |  |  |
| `priority` | Prioridad (1-100) | Int |  |  |
| `effective_date` | Fecha de Vigencia | Date |  |  |
| `expiry_date` | Fecha de Expiración | Date |  |  |
| `error_message` | Mensaje de Error | Text |  |  |
| `warning_message` | Mensaje de Advertencia | Text |  |  |
| `severity` | Severidad | Select |  | Error… |
| `conditions` | Condiciones de la Regla | Table |  | Rule Condition |
| `actions` | Acciones a Ejecutar | Table |  | Rule Action |
| `execution_count` | Veces Ejecutada | Int |  |  |
| `last_execution` | Última Ejecución | Datetime |  |  |
| `average_execution_time` | Tiempo Promedio (ms) | Float |  |  |
| `last_error` | Último Error | Text |  |  |


### Rule Action _Child table_

Fuente: `facturacion_mexico/motor_reglas/doctype/rule_action/rule_action.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `action_type` | Tipo de Acción | Select | ✅ | Set Field… |
| `target_field` | Campo Objetivo | Data |  |  |
| `action_value` | Valor/Script a Ejecutar | Text |  |  |
| `continue_on_error` | Continuar si Falla | Check |  |  |
| `log_action` | Registrar en Log | Check |  |  |
| `description` | Descripción | Small Text |  |  |


### Rule Condition _Child table_

Fuente: `facturacion_mexico/motor_reglas/doctype/rule_condition/rule_condition.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `condition_type` | Tipo de Condición | Select | ✅ | Field… |
| `field_name` | Campo a Evaluar | Data |  |  |
| `operator` | Operador | Select | ✅ | equals… |
| `value` | Valor de Comparación | Text |  |  |
| `value_type` | Tipo de Valor | Select |  | Static… |
| `logical_operator` | Operador Lógico | Select |  | AND… |
| `group_start` | Inicio de Grupo | Check |  |  |
| `group_end` | Fin de Grupo | Check |  |  |


### Rule Execution Log

Fuente: `facturacion_mexico/motor_reglas/doctype/rule_execution_log/rule_execution_log.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `naming_series` | Naming Series | Select |  | REL-.YYYY.- |
| `rule` | Regla | Link | ✅ | Fiscal Validation Rule |
| `rule_name` | Nombre de Regla | Data |  |  |
| `document_type` | Tipo de Documento | Data |  |  |
| `document_name` | Documento | Dynamic Link |  | document_type |
| `execution_time` | Tiempo Ejecución (ms) | Float |  |  |
| `result` | Resultado | Select |  | Success… |
| `creation` | Fecha/Hora | Datetime |  |  |
| `action_type` | Tipo de Acción | Data |  |  |
| `action_idx` | Índice de Acción | Int |  |  |
| `conditions_evaluated` | Condiciones Evaluadas | Int |  |  |
| `actions_executed` | Acciones Ejecutadas | Int |  |  |
| `error_details` | Detalles de Error | Text |  |  |
| `action_details` | Detalles de Acción (JSON) | Long Text |  |  |


## Multi Sucursal


### Configuracion Fiscal Sucursal

Fuente: `facturacion_mexico/multi_sucursal/doctype/configuracion_fiscal_sucursal/configuracion_fiscal_sucursal.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `naming_series` | Series | Select | ✅ | CFS-.YYYY.- |
| `branch` | Sucursal | Link | ✅ | Branch |
| `company` | Empresa | Link | ✅ | Company |
| `certificate_ids` | IDs de Certificados | JSON |  |  |
| `serie_fiscal` | Serie Fiscal | Data |  |  |
| `folio_current` | Folio Actual | Int |  |  |
| `folio_warning_threshold` | Umbral de Advertencia | Int |  |  |
| `folio_critical_threshold` | Umbral Crítico | Int |  |  |
| `last_invoice_date` | Última Factura | Datetime |  |  |
| `monthly_average` | Promedio Mensual | Float |  |  |
| `days_until_exhaustion` | Días hasta Agotamiento | Int |  |  |
| `total_invoices_generated` | Total Facturas Generadas | Int |  |  |
| `is_active` | Activa | Check |  |  |
| `last_sync_date` | Última Sincronización | Datetime |  |  |
| `created_automatically` | Creación Automática | Check |  |  |
| `needs_attention` | Necesita Atención | Check |  |  |


## Validaciones


### SAT Validation Cache

Fuente: `facturacion_mexico/validaciones/doctype/sat_validation_cache/sat_validation_cache.json`


| Campo | Label | Tipo | Requerido | Opciones |
|---|---|---|---|---|
| `validation_type` | Tipo de Validación | Select | ✅ | … |
| `lookup_value` | Valor Consultado | Data | ✅ |  |
| `validation_date` | Fecha de Validación | Datetime | ✅ |  |
| `expiry_date` | Fecha de Expiración | Date |  |  |
| `is_valid` | Resultado Válido | Check |  |  |
| `validation_count` | Veces Validado | Int |  |  |
| `validation_data` | Respuesta Completa | JSON |  |  |
| `last_updated_by` | Última Actualización Por | Link |  | User |
| `notes` | Notas | Small Text |  |  |
