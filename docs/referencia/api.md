<!--
  ARCHIVO GENERADO AUTOMÁTICAMENTE. NO EDITAR MANUALMENTE.
  Regenerar con: python3 scripts/generate_reference.py
  Fecha generación: 2026-05-30 02:32
-->


# Referencia — API

Funciones expuestas como endpoints HTTP via `@frappe.whitelist()`.
Accesibles desde el cliente JS con `frappe.call({method: '...'})` o desde Python con `frappe.get_attr('...')`.


## Índice

- **facturacion_mexico/addendas/addenda_auto_detector.py**
  - [`detect_customer_addenda_requirement`](#detect-customer-addenda-requirement)
  - [`apply_auto_detection`](#apply-auto-detection)
  - [`bulk_auto_detect_customers`](#bulk-auto-detect-customers)
- **facturacion_mexico/addendas/api.py**
  - [`get_addenda_types`](#get-addenda-types)
  - [`get_addenda_configuration`](#get-addenda-configuration)
  - [`generate_addenda_xml`](#generate-addenda-xml)
  - [`validate_addenda_xml_api`](#validate-addenda-xml-api)
  - [`create_addenda_configuration`](#create-addenda-configuration)
  - [`get_product_mappings`](#get-product-mappings)
  - [`test_addenda_generation`](#test-addenda-generation)
  - [`get_addenda_requirements`](#get-addenda-requirements)
  - [`generate_generic_addenda`](#generate-generic-addenda)
  - [`get_addenda_field_definitions`](#get-addenda-field-definitions)
  - [`setup_customer_addenda_auto_detection`](#setup-customer-addenda-auto-detection)
  - [`install_customer_addenda_fields`](#install-customer-addenda-fields)
  - [`get_customer_addenda_info`](#get-customer-addenda-info)
- **facturacion_mexico/addendas/custom_fields/customer_addenda_fields.py**
  - [`get_addenda_fields_status`](#get-addenda-fields-status)
  - [`remove_addenda_fields`](#remove-addenda-fields)
- **facturacion_mexico/addendas/doctype/addenda_type/addenda_type.py**
  - [`validate_addenda_type_exists`](#validate-addenda-type-exists)
  - [`test_sample_xml_validation`](#test-sample-xml-validation)
- **facturacion_mexico/addendas/generic_addenda_generator.py**
  - [`generate_addenda_for_invoice`](#generate-addenda-for-invoice)
  - [`get_addenda_type_fields`](#get-addenda-type-fields)
- **facturacion_mexico/addendas/multibranch_addenda_manager.py**
  - [`get_branch_addenda_configuration`](#get-branch-addenda-configuration)
  - [`get_available_addenda_types_for_branch`](#get-available-addenda-types-for-branch)
  - [`validate_addenda_for_branch_invoice`](#validate-addenda-for-branch-invoice)
- **facturacion_mexico/addendas/validators/xsd_validator.py**
  - [`validate_xml_against_schema`](#validate-xml-against-schema)
- **facturacion_mexico/api/cancel_operations.py**
  - [`cancel_sales_invoice_after_ffm`](#cancel-sales-invoice-after-ffm)
  - [`get_cancellation_status`](#get-cancellation-status)
- **facturacion_mexico/api/complemento_summary.py**
  - [`get_complemento_summary`](#get-complemento-summary)
- **facturacion_mexico/api/ffm_summary.py**
  - [`get_ffm_summary`](#get-ffm-summary)
- **facturacion_mexico/api/fiscal_operations.py**
  - [`refacturar_misma_si`](#refacturar-misma-si)
  - [`cancelar_si_post_fiscal`](#cancelar-si-post-fiscal)
  - [`cancel_sales_invoice_after_ffm`](#cancel-sales-invoice-after-ffm)
- **facturacion_mexico/catalogos_sat/api.py**
  - [`get_uso_cfdi_for_customer`](#get-uso-cfdi-for-customer)
  - [`get_regimen_fiscal_for_customer`](#get-regimen-fiscal-for-customer)
  - [`sync_sat_catalogs`](#sync-sat-catalogs)
  - [`validate_rfc`](#validate-rfc)
- **facturacion_mexico/cfdi_recibidos/api.py**
  - [`upload_xml`](#upload-xml)
  - [`resolve_supplier`](#resolve-supplier)
  - [`classify_concepts`](#classify-concepts)
  - [`save_mapping_rule`](#save-mapping-rule)
  - [`generate_missing_suppliers`](#generate-missing-suppliers)
  - [`get_department_candidates`](#get-department-candidates)
  - [`assign_departments`](#assign-departments)
  - [`build_purchase_invoice`](#build-purchase-invoice)
  - [`build_purchase_invoices_pending_batch`](#build-purchase-invoices-pending-batch)
  - [`propose_item`](#propose-item)
  - [`classify_all_concepts`](#classify-all-concepts)
  - [`suggest_supplier_from_cfdi`](#suggest-supplier-from-cfdi)
  - [`get_item_resolution_options`](#get-item-resolution-options)
  - [`assign_item_to_concepto`](#assign-item-to-concepto)
  - [`create_specific_item_from_concepto`](#create-specific-item-from-concepto)
  - [`create_grouping_item_from_concepto`](#create-grouping-item-from-concepto)
  - [`assign_generic_item_to_concepto`](#assign-generic-item-to-concepto)
  - [`get_next_item_code_for_group`](#get-next-item-code-for-group)
- **facturacion_mexico/cfdi_recibidos/queries.py**
  - [`get_expense_item_groups`](#get-expense-item-groups)
  - [`get_expense_items`](#get-expense-items)
- **facturacion_mexico/cfdi_recibidos/services/wizard_cfdi_recibidos.py**
  - [`get_opciones_impuesto_iniciales`](#get-opciones-impuesto-iniciales)
  - [`generar_template_impuestos`](#generar-template-impuestos)
- **facturacion_mexico/complementos_pago/api.py**
  - [`crear_complemento_pago_desde_pe`](#crear-complemento-pago-desde-pe)
  - [`timbrar_complemento_pago`](#timbrar-complemento-pago)
  - [`cancelar_complemento_pago`](#cancelar-complemento-pago)
  - [`revisar_estatus_cancelacion_complemento`](#revisar-estatus-cancelacion-complemento)
  - [`descargar_archivos_complemento`](#descargar-archivos-complemento)
  - [`crear_complemento_desde_payment_entry`](#crear-complemento-desde-payment-entry)
  - [`consultar_estatus_complemento`](#consultar-estatus-complemento)
  - [`generar_xml_complemento`](#generar-xml-complemento)
  - [`obtener_complementos_pendientes_timbrado`](#obtener-complementos-pendientes-timbrado)
  - [`reporte_complementos_periodo`](#reporte-complementos-periodo)
  - [`get_active_pe_for_si`](#get-active-pe-for-si)
- **facturacion_mexico/complementos_pago/doctype/complemento_pago_mx/complemento_pago_mx.py**
  - [`generar_xml_complemento`](#generar-xml-complemento)
  - [`consultar_estatus_sat`](#consultar-estatus-sat)
- **facturacion_mexico/dashboard_fiscal/api.py**
  - [`get_dashboard_data`](#get-dashboard-data)
  - [`get_module_kpis`](#get-module-kpis)
  - [`get_active_alerts`](#get-active-alerts)
  - [`get_fiscal_health_score`](#get-fiscal-health-score)
  - [`save_dashboard_layout`](#save-dashboard-layout)
  - [`export_dashboard_report`](#export-dashboard-report)
  - [`get_trend_analysis`](#get-trend-analysis)
- **facturacion_mexico/dashboard_fiscal/doctype/dashboard_user_preference/dashboard_user_preference.py**
  - [`get_user_preferences`](#get-user-preferences)
  - [`save_user_layout`](#save-user-layout)
- **facturacion_mexico/dashboard_fiscal/doctype/fiscal_health_score/fiscal_health_score.py**
  - [`get_health_trend`](#get-health-trend)
  - [`recalculate_score`](#recalculate-score)
- **facturacion_mexico/dashboard_fiscal/integrations/multibranch_integration.py**
  - [`setup_multibranch_integration`](#setup-multibranch-integration)
  - [`get_multibranch_dashboard_data`](#get-multibranch-dashboard-data)
- **facturacion_mexico/draft_management/api.py**
  - [`create_draft_invoice`](#create-draft-invoice)
  - [`approve_and_invoice_draft`](#approve-and-invoice-draft)
  - [`cancel_draft`](#cancel-draft)
  - [`get_draft_preview`](#get-draft-preview)
- **facturacion_mexico/ereceipts/api.py**
  - [`crear_ereceipt`](#crear-ereceipt)
  - [`get_ereceipt_status`](#get-ereceipt-status)
  - [`expire_ereceipts`](#expire-ereceipts)
  - [`get_ereceipts_for_global_invoice`](#get-ereceipts-for-global-invoice)
  - [`invoice_ereceipt`](#invoice-ereceipt)
- **facturacion_mexico/ereceipts/doctype/ereceipt_mx/ereceipt_mx.py**
  - [`bulk_expire_ereceipts`](#bulk-expire-ereceipts)
  - [`get_ereceipts_for_period`](#get-ereceipts-for-period)
  - [`get_expiring_ereceipts`](#get-expiring-ereceipts)
- **facturacion_mexico/facturacion_fiscal/api/__init__.py**
  - [`write_pac_response`](#write-pac-response)
  - [`write_pac_timeout`](#write-pac-timeout)
  - [`recover_from_file`](#recover-from-file)
  - [`get_fallback_files`](#get-fallback-files)
  - [`get_fiscal_states_config`](#get-fiscal-states-config)
  - [`get_fiscal_states`](#get-fiscal-states)
  - [`validate_fiscal_state`](#validate-fiscal-state)
  - [`get_next_fiscal_state`](#get-next-fiscal-state)
- **facturacion_mexico/facturacion_fiscal/api/admin_tools.py**
  - [`get_system_health_metrics`](#get-system-health-metrics)
  - [`get_os_health_metrics`](#get-os-health-metrics)
  - [`get_audit_trail`](#get-audit-trail)
  - [`get_alerts_configuration`](#get-alerts-configuration)
  - [`save_alerts_configuration`](#save-alerts-configuration)
  - [`test_alerts_system`](#test-alerts-system)
  - [`check_alert_conditions`](#check-alert-conditions)
- **facturacion_mexico/facturacion_fiscal/api_client.py**
  - [`test_facturapi_connection`](#test-facturapi-connection)
- **facturacion_mexico/facturacion_fiscal/doctype/configuracion_fiscal_mexico/configuracion_fiscal_mexico.py**
  - [`aplicar_mapeo_y_generar_templates`](#aplicar-mapeo-y-generar-templates)
  - [`agregar_filas_por_alcance`](#agregar-filas-por-alcance)
  - [`sincronizar_tabla_con_alcance`](#sincronizar-tabla-con-alcance)
- **facturacion_mexico/facturacion_fiscal/doctype/configuracion_reclasificacion_fiscal_mexico/configuracion_reclasificacion_fiscal_mexico.py**
  - [`cargar_reglas`](#cargar-reglas)
  - [`aplicar`](#aplicar)
- **facturacion_mexico/facturacion_fiscal/doctype/control_panel_settings/control_panel_settings.py**
  - [`get_alerts_configuration`](#get-alerts-configuration)
  - [`save_alerts_configuration`](#save-alerts-configuration)
  - [`test_alerts_system`](#test-alerts-system)
  - [`check_alert_conditions`](#check-alert-conditions)
- **facturacion_mexico/facturacion_fiscal/doctype/factura_fiscal_mexico/factura_fiscal_mexico.py**
  - [`get_payment_entry_for_javascript`](#get-payment-entry-for-javascript)
  - [`sat_options`](#sat-options)
  - [`get_sales_invoice_for_ffm`](#get-sales-invoice-for-ffm)
  - [`check_si_customer_rfc_validated`](#check-si-customer-rfc-validated)
  - [`cancel_ffm_keep_si`](#cancel-ffm-keep-si)
  - [`action_send_cfdi_email`](#action-send-cfdi-email)
  - [`request_stamping`](#request-stamping)
  - [`request_cancellation`](#request-cancellation)
- **facturacion_mexico/facturacion_fiscal/doctype/system_health_monitor/system_health_monitor.py**
  - [`get_system_health_metrics`](#get-system-health-metrics)
  - [`get_os_health_metrics`](#get-os-health-metrics)
- **facturacion_mexico/facturacion_fiscal/services/payment_entry_reclasificacion.py**
  - [`analizar_payment_entry_whitelisted`](#analizar-payment-entry-whitelisted)
- **facturacion_mexico/facturacion_fiscal/setup/generador_templates_fiscal.py**
  - [`generate_8_stct_for_company`](#generate-8-stct-for-company)
  - [`generate_itt_for_company`](#generate-itt-for-company)
- **facturacion_mexico/facturacion_fiscal/timbrado_api.py**
  - [`timbrar_factura`](#timbrar-factura)
  - [`cancelar_factura`](#cancelar-factura)
  - [`create_substitution_si`](#create-substitution-si)
  - [`get_sat_cancellation_motives`](#get-sat-cancellation-motives)
  - [`revisar_estatus_cancelacion`](#revisar-estatus-cancelacion)
  - [`test_connection`](#test-connection)
- **facturacion_mexico/facturacion_fiscal/validations.py**
  - [`validate_customer_fiscal_data`](#validate-customer-fiscal-data)
  - [`get_customer_fiscal_summary`](#get-customer-fiscal-summary)
  - [`validate_rfc_external`](#validate-rfc-external)
- **facturacion_mexico/facturas_globales/api.py**
  - [`get_available_ereceipts`](#get-available-ereceipts)
  - [`create_global_invoice`](#create-global-invoice)
  - [`preview_global_invoice`](#preview-global-invoice)
  - [`generate_global_cfdi`](#generate-global-cfdi)
  - [`get_global_invoice_stats`](#get-global-invoice-stats)
  - [`cancel_global_invoice`](#cancel-global-invoice)
  - [`get_suggested_periods`](#get-suggested-periods)
- **facturacion_mexico/fiscal_state/api.py**
  - [`get_fiscal_ui_state`](#get-fiscal-ui-state)
- **facturacion_mexico/motor_reglas/api.py**
  - [`get_applicable_rules`](#get-applicable-rules)
  - [`test_rule`](#test-rule)
  - [`create_rule_from_template`](#create-rule-from-template)
  - [`get_rule_execution_stats`](#get-rule-execution-stats)
  - [`bulk_apply_rules`](#bulk-apply-rules)
  - [`validate_rule_syntax`](#validate-rule-syntax)
  - [`execute_validation_rules`](#execute-validation-rules)
- **facturacion_mexico/multi_sucursal/api.py**
  - [`get_lugar_expedicion`](#get-lugar-expedicion)
  - [`get_sucursales_disponibles`](#get-sucursales-disponibles)
  - [`establecer_lugar_expedicion`](#establecer-lugar-expedicion)
  - [`validar_configuracion_sucursales`](#validar-configuracion-sucursales)
  - [`bulk_set_lugar_expedicion`](#bulk-set-lugar-expedicion)
  - [`get_facturas_sin_lugar_expedicion`](#get-facturas-sin-lugar-expedicion)
- **facturacion_mexico/multi_sucursal/branch_auto_selector.py**
  - [`auto_select_branch_for_invoice`](#auto-select-branch-for-invoice)
  - [`get_user_preferred_branches`](#get-user-preferred-branches)
  - [`validate_branch_for_invoice`](#validate-branch-for-invoice)
- **facturacion_mexico/multi_sucursal/branch_folio_manager.py**
  - [`get_branch_folio_status`](#get-branch-folio-status)
  - [`reserve_folio_for_invoice`](#reserve-folio-for-invoice)
  - [`release_folio_for_invoice`](#release-folio-for-invoice)
  - [`get_branch_folio_reservations`](#get-branch-folio-reservations)
- **facturacion_mexico/multi_sucursal/branch_manager.py**
  - [`get_company_branch_health_summary`](#get-company-branch-health-summary)
  - [`get_certificate_optimization_suggestions`](#get-certificate-optimization-suggestions)
- **facturacion_mexico/multi_sucursal/certificate_selector.py**
  - [`get_branch_certificate_status`](#get-branch-certificate-status)
  - [`select_certificate_for_invoice`](#select-certificate-for-invoice)
- **facturacion_mexico/multi_sucursal/doctype/configuracion_fiscal_sucursal/configuracion_fiscal_sucursal.py**
  - [`get_branch_fiscal_status`](#get-branch-fiscal-status)
  - [`sync_all_branch_configurations`](#sync-all-branch-configurations)
- **facturacion_mexico/multi_sucursal/migration.py**
  - [`detect_legacy_system`](#detect-legacy-system)
  - [`preview_migration`](#preview-migration)
  - [`execute_migration`](#execute-migration)
  - [`get_migration_status`](#get-migration-status)
- **facturacion_mexico/multi_sucursal/utils.py**
  - [`refresh_all_branch_configurations`](#refresh-all-branch-configurations)
- **facturacion_mexico/validaciones/api.py**
  - [`validate_rfc`](#validate-rfc)
  - [`validate_customer_rfc_with_facturapi`](#validate-customer-rfc-with-facturapi)
  - [`validate_lista_69b`](#validate-lista-69b)
  - [`bulk_validate_rfc`](#bulk-validate-rfc)
  - [`get_cache_stats`](#get-cache-stats)
  - [`cleanup_expired_cache`](#cleanup-expired-cache)
  - [`force_refresh_cache`](#force-refresh-cache)
  - [`validate_customers_bulk`](#validate-customers-bulk)
  - [`get_nightly_validation_stats`](#get-nightly-validation-stats)
  - [`get_customers_validation_summary`](#get-customers-validation-summary)
- **facturacion_mexico/validaciones/doctype/sat_validation_cache/sat_validation_cache.py**
  - [`cleanup_expired_cache`](#cleanup-expired-cache)
  - [`get_cache_statistics`](#get-cache-statistics)
- **facturacion_mexico/validaciones/sales_invoice_cancel_guard.py**
  - [`can_cancel_sales_invoice`](#can-cancel-sales-invoice)
- **facturacion_mexico/validation/architecture_validator.py**
  - [`validate_resilient_architecture`](#validate-resilient-architecture)
  - [`validate_shadow_mode_invoices`](#validate-shadow-mode-invoices)


---


## `facturacion_mexico/addendas/addenda_auto_detector.py`


### `detect_customer_addenda_requirement(customer)`

**Módulo:** `facturacion_mexico.addendas.addenda_auto_detector`

API para detectar requerimiento de addenda de un cliente


### `apply_auto_detection(customer)`

**Módulo:** `facturacion_mexico.addendas.addenda_auto_detector`

API para aplicar auto-detección a un cliente


### `bulk_auto_detect_customers(limit)`

**Módulo:** `facturacion_mexico.addendas.addenda_auto_detector`

API para auto-detección en lote


## `facturacion_mexico/addendas/api.py`


### `get_addenda_types()`

**Módulo:** `facturacion_mexico.addendas.api`

Obtener tipos de addenda activos.


### `get_addenda_configuration(customer)`

**Módulo:** `facturacion_mexico.addendas.api`

Obtener configuración de addenda para cliente.


### `generate_addenda_xml(sales_invoice, addenda_type, validate_output)`

**Módulo:** `facturacion_mexico.addendas.api`

Generar XML de addenda para factura.


### `validate_addenda_xml_api(xml_content, addenda_type)`

**Módulo:** `facturacion_mexico.addendas.api`

Validar XML contra XSD.


### `create_addenda_configuration(customer, addenda_type, field_values)`

**Módulo:** `facturacion_mexico.addendas.api`

Crear nueva configuración de addenda.


### `get_product_mappings(customer, items)`

**Módulo:** `facturacion_mexico.addendas.api`

Obtener mapeo de productos para cliente.


### `test_addenda_generation(sales_invoice, addenda_type)`

**Módulo:** `facturacion_mexico.addendas.api`

Generar addenda de prueba sin timbrar.


### `get_addenda_requirements(customer)`

**Módulo:** `facturacion_mexico.addendas.api`

Verificar si un cliente requiere addenda y qué tipo.


### `generate_generic_addenda(sales_invoice, addenda_type, addenda_values)`

**Módulo:** `facturacion_mexico.addendas.api`

Generar addenda usando sistema genérico con Jinja2 templates


### `get_addenda_field_definitions(addenda_type)`

**Módulo:** `facturacion_mexico.addendas.api`

Obtener definición de campos para un tipo de addenda


### `setup_customer_addenda_auto_detection(customer, apply_changes)`

**Módulo:** `facturacion_mexico.addendas.api`

Ejecutar auto-detección de addendas para cliente


### `install_customer_addenda_fields()`

**Módulo:** `facturacion_mexico.addendas.api`

Instalar custom fields de addenda en Customer


### `get_customer_addenda_info(customer)`

**Módulo:** `facturacion_mexico.addendas.api`

Obtener información completa de addenda para un cliente


## `facturacion_mexico/addendas/custom_fields/customer_addenda_fields.py`


### `get_addenda_fields_status()`

**Módulo:** `facturacion_mexico.addendas.custom_fields.customer_addenda_fields`

API para obtener información sobre campos de addenda


### `remove_addenda_fields()`

**Módulo:** `facturacion_mexico.addendas.custom_fields.customer_addenda_fields`

API para remover custom fields de addenda (solo para testing)


## `facturacion_mexico/addendas/doctype/addenda_type/addenda_type.py`


### `validate_addenda_type_exists(addenda_type)`

**Módulo:** `facturacion_mexico.addendas.doctype.addenda_type.addenda_type`

Validar que existe un tipo de addenda activo.


### `test_sample_xml_validation()`

**Módulo:** `facturacion_mexico.addendas.doctype.addenda_type.addenda_type`

Probar validación del XML de ejemplo contra el esquema.


## `facturacion_mexico/addendas/generic_addenda_generator.py`


### `generate_addenda_for_invoice(sales_invoice, addenda_type, addenda_values)`

**Módulo:** `facturacion_mexico.addendas.generic_addenda_generator`

API para generar addenda para una factura específica


### `get_addenda_type_fields(addenda_type)`

**Módulo:** `facturacion_mexico.addendas.generic_addenda_generator`

API para obtener campos requeridos de un tipo de addenda


## `facturacion_mexico/addendas/multibranch_addenda_manager.py`


### `get_branch_addenda_configuration(company, branch, customer)`

**Módulo:** `facturacion_mexico.addendas.multibranch_addenda_manager`

API para obtener configuración de addendas por sucursal


### `get_available_addenda_types_for_branch(company, branch)`

**Módulo:** `facturacion_mexico.addendas.multibranch_addenda_manager`

API para obtener tipos de addenda disponibles para una sucursal


### `validate_addenda_for_branch_invoice(sales_invoice, branch)`

**Módulo:** `facturacion_mexico.addendas.multibranch_addenda_manager`

API para validar addenda con sucursal específica


## `facturacion_mexico/addendas/validators/xsd_validator.py`


### `validate_xml_against_schema(xml_content, xsd_content)`

**Módulo:** `facturacion_mexico.addendas.validators.xsd_validator`

API endpoint para validar XML contra esquema XSD.


## `facturacion_mexico/api/cancel_operations.py`


### `cancel_sales_invoice_after_ffm(si_name)`

**Módulo:** `facturacion_mexico.api.cancel_operations`

Orquestador seguro para cancelación Sales Invoice post-cancelación fiscal.


### `get_cancellation_status(si_name)`

**Módulo:** `facturacion_mexico.api.cancel_operations`

Verificar estado de cancelación de Sales Invoice.


## `facturacion_mexico/api/complemento_summary.py`


### `get_complemento_summary(complemento_name)`

**Módulo:** `facturacion_mexico.api.complemento_summary`

Resumen del Complemento Pago MX para widget en Payment Entry.


## `facturacion_mexico/api/ffm_summary.py`


### `get_ffm_summary(ffm_name)`

**Módulo:** `facturacion_mexico.api.ffm_summary`

Obtiene resumen de información de Factura Fiscal Mexico.


## `facturacion_mexico/api/fiscal_operations.py`


### `refacturar_misma_si(si_name)`

**Módulo:** `facturacion_mexico.api.fiscal_operations`

Re-facturación con la MISMA Sales Invoice para motivos 02/03/04:


### `cancelar_si_post_fiscal(si_name)`

**Módulo:** `facturacion_mexico.api.fiscal_operations`

Cancela una SI cuya FFM ya fue cancelada ante el SAT.


### `cancel_sales_invoice_after_ffm(si_name)`

**Módulo:** `facturacion_mexico.api.fiscal_operations`

DEPRECATED: Usar botón Cancel nativo.


## `facturacion_mexico/catalogos_sat/api.py`


### `get_uso_cfdi_for_customer(customer_name)`

**Módulo:** `facturacion_mexico.catalogos_sat.api`

Obtener usos CFDI válidos para un cliente específico.


### `get_regimen_fiscal_for_customer(customer_name)`

**Módulo:** `facturacion_mexico.catalogos_sat.api`

Obtener regímenes fiscales válidos para un cliente específico.


### `sync_sat_catalogs()`

**Módulo:** `facturacion_mexico.catalogos_sat.api`

Sincronizar catálogos SAT (tarea programada).


### `validate_rfc(rfc)`

**Módulo:** `facturacion_mexico.catalogos_sat.api`

Validar RFC con dígito verificador.


## `facturacion_mexico/cfdi_recibidos/api.py`


### `upload_xml(company)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.api`

Carga uno o varios XMLs CFDI 4.0 y los procesa como CFDI Recibido.


### `resolve_supplier(cfdi_recibido, supplier)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.api`

Asigna el proveedor al CFDI Recibido.


### `classify_concepts(cfdi_recibido)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.api`

Aplica reglas de CFDI Concepto Mapping sobre todos los conceptos.


### `save_mapping_rule(target_type, supplier_rfc, sat_product_key, target_item, target_account, target_cost_center, company)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.api`

Crea o actualiza una regla de CFDI Concepto Mapping.


### `generate_missing_suppliers(cfdi_names)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.api`

Crea Suppliers en lote para CFDIs en estado 'Falta proveedor'.


### `get_department_candidates(company)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.api`

Retorna CFDIs con proveedor asignado y sin departamento.


### `assign_departments(assignments)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.api`

Asigna departamento a múltiples CFDIs Recibidos en lote.


### `build_purchase_invoice(cfdi_recibido)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.api`

Convierte CFDI Recibido Clasificado a Purchase Invoice Draft.


### `build_purchase_invoices_pending_batch()`

**Módulo:** `facturacion_mexico.cfdi_recibidos.api`

Convierte todos los CFDI Recibidos elegibles a Purchase Invoice en lote.


### `propose_item(cfdi_recibido, sat_product_key, no_identificacion, item_group)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.api`

Propone item_code e item_resolution para un concepto CFDI.


### `classify_all_concepts(cfdi_recibido)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.api`

Auto-asigna Items a conceptos sin item_code, exclusivamente por coincidencia


### `suggest_supplier_from_cfdi(cfdi_recibido)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.api`

Sugiere datos de proveedor basándose en el RFC del CFDI. No crea Supplier automáticamente.


### `get_item_resolution_options(cfdi_recibido, concepto_name)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.api`

Propone opciones de Item para un concepto específico usando el motor de resolución.


### `assign_item_to_concepto(concepto_name, item_code, item_resolution, match_reason, match_confidence)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.api`

Confirma la asignación de un Item a un concepto CFDI Recibido.


### `create_specific_item_from_concepto(cfdi_recibido, concepto_name, item_code, item_name, item_group_name)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.api`

Crea un Item específico de gasto y lo asigna al concepto.


### `create_grouping_item_from_concepto(cfdi_recibido, concepto_name, item_code, item_name, item_group_name)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.api`

Crea un Item agrupador de gasto y lo asigna al concepto.


### `assign_generic_item_to_concepto(cfdi_recibido, concepto_name)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.api`

Asigna el Item genérico GASTO-* del item_group del concepto.


### `get_next_item_code_for_group(item_group)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.api`

Genera el próximo item_code disponible para un grupo de gasto.


## `facturacion_mexico/cfdi_recibidos/queries.py`


### `get_expense_item_groups(doctype, txt, searchfield, start, page_len, filters)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.queries`

Retorna Item Groups que son hojas (is_group=0) bajo el grupo "Gastos".


### `get_expense_items(doctype, txt, searchfield, start, page_len, filters)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.queries`

Retorna Items válidos para asignar en conceptos CFDI:


## `facturacion_mexico/cfdi_recibidos/services/wizard_cfdi_recibidos.py`


### `get_opciones_impuesto_iniciales()`

**Módulo:** `facturacion_mexico.cfdi_recibidos.services.wizard_cfdi_recibidos`

Retorna opciones de impuesto iniciales para el wizard de Configuracion CFDI Recibidos.


### `generar_template_impuestos(config_name)`

**Módulo:** `facturacion_mexico.cfdi_recibidos.services.wizard_cfdi_recibidos`

Genera o actualiza el Purchase Taxes and Charges Template para CFDI Recibidos.


## `facturacion_mexico/complementos_pago/api.py`


### `crear_complemento_pago_desde_pe(payment_entry_name)`

**Módulo:** `facturacion_mexico.complementos_pago.api`

Crea Complemento Pago MX en borrador desde un Payment Entry PPD.


### `timbrar_complemento_pago(complemento_name)`

**Módulo:** `facturacion_mexico.complementos_pago.api`

Timbra un Complemento Pago MX con FacturAPI.


### `cancelar_complemento_pago(complemento_name, motivo)`

**Módulo:** `facturacion_mexico.complementos_pago.api`

Cancela un Complemento Pago MX timbrado con FacturAPI.


### `revisar_estatus_cancelacion_complemento(complemento_name)`

**Módulo:** `facturacion_mexico.complementos_pago.api`

Consulta FacturAPI para actualizar estado de cancelación pendiente.


### `descargar_archivos_complemento(complemento_name)`

**Módulo:** `facturacion_mexico.complementos_pago.api`

Descarga manual de PDF/XML — equivalente al botón en FFM.


### `crear_complemento_desde_payment_entry(payment_entry_name)`

**Módulo:** `facturacion_mexico.complementos_pago.api`

Crea un Complemento de Pago MX basado en un Payment Entry de ERPNext


### `consultar_estatus_complemento(complemento_id)`

**Módulo:** `facturacion_mexico.complementos_pago.api`

Consulta el estatus de un complemento de pago en el SAT


### `generar_xml_complemento(complemento_name)`

**Módulo:** `facturacion_mexico.complementos_pago.api`

Genera el XML del complemento de pago según estándar SAT


### `obtener_complementos_pendientes_timbrado()`

**Módulo:** `facturacion_mexico.complementos_pago.api`

Obtiene complementos de pago pendientes de timbrado


### `reporte_complementos_periodo(fecha_inicio, fecha_fin)`

**Módulo:** `facturacion_mexico.complementos_pago.api`

Genera reporte de complementos de pago por período


### `get_active_pe_for_si(si_name)`

**Módulo:** `facturacion_mexico.complementos_pago.api`

Retorna el name del primer Payment Entry submitted ligado a la SI,


## `facturacion_mexico/complementos_pago/doctype/complemento_pago_mx/complemento_pago_mx.py`


### `generar_xml_complemento()`

**Módulo:** `facturacion_mexico.complementos_pago.doctype.complemento_pago_mx.complemento_pago_mx`


### `consultar_estatus_sat()`

**Módulo:** `facturacion_mexico.complementos_pago.doctype.complemento_pago_mx.complemento_pago_mx`


## `facturacion_mexico/dashboard_fiscal/api.py`


### `get_dashboard_data(period, company)`

**Módulo:** `facturacion_mexico.dashboard_fiscal.api`

Obtener todos los datos del dashboard


### `get_module_kpis(module_name, filters)`

**Módulo:** `facturacion_mexico.dashboard_fiscal.api`

Obtener KPIs específicos de un módulo


### `get_active_alerts(severity, module)`

**Módulo:** `facturacion_mexico.dashboard_fiscal.api`

Obtener alertas activas del sistema


### `get_fiscal_health_score(company, date)`

**Módulo:** `facturacion_mexico.dashboard_fiscal.api`

Calcular score de salud fiscal


### `save_dashboard_layout(layout_config)`

**Módulo:** `facturacion_mexico.dashboard_fiscal.api`

Guardar configuración de dashboard del usuario


### `export_dashboard_report(report_type, filters, format_type)`

**Módulo:** `facturacion_mexico.dashboard_fiscal.api`

Exportar reportes del dashboard


### `get_trend_analysis(metric, period)`

**Módulo:** `facturacion_mexico.dashboard_fiscal.api`

Análisis de tendencias para métrica


## `facturacion_mexico/dashboard_fiscal/doctype/dashboard_user_preference/dashboard_user_preference.py`


### `get_user_preferences(user)`

**Módulo:** `facturacion_mexico.dashboard_fiscal.doctype.dashboard_user_preference.dashboard_user_preference`

Obtener preferencias de usuario (API pública)


### `save_user_layout(layout_data)`

**Módulo:** `facturacion_mexico.dashboard_fiscal.doctype.dashboard_user_preference.dashboard_user_preference`

Guardar layout personalizado del usuario


## `facturacion_mexico/dashboard_fiscal/doctype/fiscal_health_score/fiscal_health_score.py`


### `get_health_trend(company, months)`

**Módulo:** `facturacion_mexico.dashboard_fiscal.doctype.fiscal_health_score.fiscal_health_score`

Obtener tendencia de salud fiscal


### `recalculate_score()`

**Módulo:** `facturacion_mexico.dashboard_fiscal.doctype.fiscal_health_score.fiscal_health_score`

Recalcular el score de salud fiscal


## `facturacion_mexico/dashboard_fiscal/integrations/multibranch_integration.py`


### `setup_multibranch_integration()`

**Módulo:** `facturacion_mexico.dashboard_fiscal.integrations.multibranch_integration`

API para configurar integración multi-sucursal


### `get_multibranch_dashboard_data()`

**Módulo:** `facturacion_mexico.dashboard_fiscal.integrations.multibranch_integration`

API para obtener datos completos del dashboard multi-sucursal


## `facturacion_mexico/draft_management/api.py`


### `create_draft_invoice(sales_invoice_name)`

**Módulo:** `facturacion_mexico.draft_management.api`

Crear factura borrador en FacturAPI


### `approve_and_invoice_draft(sales_invoice_name, approved_by)`

**Módulo:** `facturacion_mexico.draft_management.api`

Aprobar borrador y convertir a factura timbrada


### `cancel_draft(sales_invoice_name)`

**Módulo:** `facturacion_mexico.draft_management.api`

Cancelar borrador sin timbrar


### `get_draft_preview(sales_invoice_name)`

**Módulo:** `facturacion_mexico.draft_management.api`

Obtener preview/vista previa del borrador


## `facturacion_mexico/ereceipts/api.py`


### `crear_ereceipt(sales_invoice_name)`

**Módulo:** `facturacion_mexico.ereceipts.api`

Crea E-Receipt desde Sales Invoice.


### `get_ereceipt_status(ereceipt_name)`

**Módulo:** `facturacion_mexico.ereceipts.api`

Consulta status de E-Receipt.


### `expire_ereceipts()`

**Módulo:** `facturacion_mexico.ereceipts.api`

Marca E-Receipts expirados (llamada por scheduler).


### `get_ereceipts_for_global_invoice(date_from, date_to, customer)`

**Módulo:** `facturacion_mexico.ereceipts.api`

Obtiene E-Receipts para factura global.


### `invoice_ereceipt(ereceipt_name, customer_data)`

**Módulo:** `facturacion_mexico.ereceipts.api`

Convierte E-Receipt a factura.


## `facturacion_mexico/ereceipts/doctype/ereceipt_mx/ereceipt_mx.py`


### `bulk_expire_ereceipts()`

**Módulo:** `facturacion_mexico.ereceipts.doctype.ereceipt_mx.ereceipt_mx`

Marcar E-Receipts expirados en lote (scheduler).


### `get_ereceipts_for_period(date_from, date_to, company, customer)`

**Módulo:** `facturacion_mexico.ereceipts.doctype.ereceipt_mx.ereceipt_mx`

Obtener E-Receipts para un período.


### `get_expiring_ereceipts(days_ahead)`

**Módulo:** `facturacion_mexico.ereceipts.doctype.ereceipt_mx.ereceipt_mx`

Obtener E-Receipts que vencen pronto.


## `facturacion_mexico/facturacion_fiscal/api/__init__.py`


### `write_pac_response(sales_invoice_name, request_data, response_data, operation_type)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.api.__init__`

API pública para escribir respuesta PAC.


### `write_pac_timeout(sales_invoice_name, request_data, timeout_seconds)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.api.__init__`

Registrar timeout de PAC y programar recovery.


### `recover_from_file(fallback_file_path)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.api.__init__`

Recuperar respuesta PAC desde archivo fallback cuando BD vuelve disponible.


### `get_fallback_files()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.api.__init__`

Listar archivos fallback pendientes de recovery.


### `get_fiscal_states_config()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.api.__init__`

Obtener configuración completa de estados fiscales para JavaScript.


### `get_fiscal_states()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.api.__init__`

Obtener solo los estados fiscales principales.


### `validate_fiscal_state(state)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.api.__init__`

Validar si un estado fiscal es válido.


### `get_next_fiscal_state(current_state, action)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.api.__init__`

Obtener el siguiente estado basado en la acción.


## `facturacion_mexico/facturacion_fiscal/api/admin_tools.py`


### `get_system_health_metrics()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.api.admin_tools`

Obtener métricas de salud del sistema resiliente.


### `get_os_health_metrics()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.api.admin_tools`

Obtener métricas de salud del sistema operativo.


### `get_audit_trail(filters)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.api.admin_tools`

Obtener audit trail con filtros.


### `get_alerts_configuration()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.api.admin_tools`

Obtener configuración actual de alertas.


### `save_alerts_configuration(config)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.api.admin_tools`

Guardar configuración de alertas.


### `test_alerts_system()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.api.admin_tools`

Test del sistema de alertas.


### `check_alert_conditions()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.api.admin_tools`

Verificar condiciones de alerta y disparar si es necesario.


## `facturacion_mexico/facturacion_fiscal/api_client.py`


### `test_facturapi_connection()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.api_client`

API para probar conexión desde interfaz.


## `facturacion_mexico/facturacion_fiscal/doctype/configuracion_fiscal_mexico/configuracion_fiscal_mexico.py`


### `aplicar_mapeo_y_generar_templates()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.configuracion_fiscal_mexico.configuracion_fiscal_mexico`

Aplicar mapeo y generar templates fiscales.


### `agregar_filas_por_alcance()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.configuracion_fiscal_mexico.configuracion_fiscal_mexico`

LEGACY: Mantener compatibilidad.


### `sincronizar_tabla_con_alcance()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.configuracion_fiscal_mexico.configuracion_fiscal_mexico`

Sincronizar tabla con alcance seleccionado: AGREGAR y ELIMINAR filas.


## `facturacion_mexico/facturacion_fiscal/doctype/configuracion_reclasificacion_fiscal_mexico/configuracion_reclasificacion_fiscal_mexico.py`


### `cargar_reglas()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.configuracion_reclasificacion_fiscal_mexico.configuracion_reclasificacion_fiscal_mexico`

Reconstruye la tabla desde CFM. Preserva cuenta_destino que el usuario ya llenó.


### `aplicar()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.configuracion_reclasificacion_fiscal_mexico.configuracion_reclasificacion_fiscal_mexico`

Crea o actualiza MRFPE según cuenta_destino de cada regla.


## `facturacion_mexico/facturacion_fiscal/doctype/control_panel_settings/control_panel_settings.py`


### `get_alerts_configuration()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.control_panel_settings.control_panel_settings`

Obtener configuración actual de alertas.


### `save_alerts_configuration(config)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.control_panel_settings.control_panel_settings`

Guardar configuración de alertas.


### `test_alerts_system()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.control_panel_settings.control_panel_settings`

Test del sistema de alertas.


### `check_alert_conditions()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.control_panel_settings.control_panel_settings`

Verificar condiciones de alerta y disparar si es necesario.


## `facturacion_mexico/facturacion_fiscal/doctype/factura_fiscal_mexico/factura_fiscal_mexico.py`


### `get_payment_entry_for_javascript(invoice_name)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico`

Wrapper para JavaScript - buscar Payment Entry por Sales Invoice.


### `sat_options()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico`

API para obtener opciones SAT centralizadas.


### `get_sales_invoice_for_ffm(doctype, txt, searchfield, start, page_len, filters)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico`

Devuelve SOLO Sales Invoices elegibles para FFM:


### `check_si_customer_rfc_validated(si_name)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico`

Valida que la SI seleccionada tenga cliente con RFC validado (respaldo en on_change).


### `cancel_ffm_keep_si(ffm_name)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico`

Cancela SOLO la FFM (sin cfdi_uuid) y libera la Sales Invoice enlazada.


### `action_send_cfdi_email(ffm_name, to)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico`

Whitelisted para el botón manual en FFM (usa el MISMO flujo).


### `request_stamping()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico`

Solicitar timbrado fiscal.


### `request_cancellation()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico`

Solicitar cancelación fiscal.


## `facturacion_mexico/facturacion_fiscal/doctype/system_health_monitor/system_health_monitor.py`


### `get_system_health_metrics()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.system_health_monitor.system_health_monitor`

Obtener métricas de salud del sistema resiliente.


### `get_os_health_metrics()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.doctype.system_health_monitor.system_health_monitor`

Obtener métricas de salud del sistema operativo.


## `facturacion_mexico/facturacion_fiscal/services/payment_entry_reclasificacion.py`


### `analizar_payment_entry_whitelisted(payment_entry_name)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.services.payment_entry_reclasificacion`

Diagnóstico desde bench console — no modifica nada.


## `facturacion_mexico/facturacion_fiscal/setup/generador_templates_fiscal.py`


### `generate_8_stct_for_company(company, abbr, iva_nacional_rate, iva_frontera_rate)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.setup.generador_templates_fiscal`

Genera 8 STCT (Nacional/Frontera x Básico/IEPS/Retenciones/Total) con lógica parcial.


### `generate_itt_for_company(company)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.setup.generador_templates_fiscal`

Generar Item Tax Templates para una empresa basándose en Configuracion Fiscal Mexico.


## `facturacion_mexico/facturacion_fiscal/timbrado_api.py`


### `timbrar_factura(sales_invoice)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.timbrado_api`

API para timbrar factura desde interfaz.


### `cancelar_factura(sales_invoice, uuid, ffm_name, motivo, substitution_uuid)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.timbrado_api`

API para cancelar factura desde interfaz - tolerante a múltiples parámetros.


### `create_substitution_si(si_name)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.timbrado_api`

Crear Sales Invoice de reemplazo para workflow 01 (sustitución).


### `get_sat_cancellation_motives()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.timbrado_api`

API para obtener motivos de cancelación SAT para UI.


### `revisar_estatus_cancelacion(ffm_name)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.timbrado_api`

Consulta FacturAPI para resolver estado PENDIENTE_CANCELACION.


### `test_connection()`

**Módulo:** `facturacion_mexico.facturacion_fiscal.timbrado_api`

Probar conexión con FacturAPI desde interfaz.


## `facturacion_mexico/facturacion_fiscal/validations.py`


### `validate_customer_fiscal_data(customer)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.validations`

Validar datos fiscales de un cliente para verificar si está listo para facturación.


### `get_customer_fiscal_summary(customer)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.validations`

Obtener resumen fiscal de un cliente para mostrar en el formulario.


### `validate_rfc_external(customer)`

**Módulo:** `facturacion_mexico.facturacion_fiscal.validations`

Validar RFC con servicios externos (FacturAPI/SAT).


## `facturacion_mexico/facturas_globales/api.py`


### `get_available_ereceipts(periodo_inicio, periodo_fin, company)`

**Módulo:** `facturacion_mexico.facturas_globales.api`

Obtener E-Receipts disponibles para factura global.


### `create_global_invoice(periodo_inicio, periodo_fin, periodicidad, company, ereceipt_list)`

**Módulo:** `facturacion_mexico.facturas_globales.api`

Crear factura global con receipts seleccionados.


### `preview_global_invoice(periodo_inicio, periodo_fin, company)`

**Módulo:** `facturacion_mexico.facturas_globales.api`

Preview de factura global sin crear.


### `generate_global_cfdi(factura_global_name)`

**Módulo:** `facturacion_mexico.facturas_globales.api`

Generar CFDI en FacturAPI.io.


### `get_global_invoice_stats(year, month, company)`

**Módulo:** `facturacion_mexico.facturas_globales.api`

Estadísticas de facturas globales.


### `cancel_global_invoice(factura_global_name, reason)`

**Módulo:** `facturacion_mexico.facturas_globales.api`

Cancelar factura global.


### `get_suggested_periods(company, periodicidad)`

**Módulo:** `facturacion_mexico.facturas_globales.api`

Obtener períodos sugeridos para facturas globales.


## `facturacion_mexico/fiscal_state/api.py`


### `get_fiscal_ui_state(doctype, name)`

**Módulo:** `facturacion_mexico.fiscal_state.api`

Retorna el estado fiscal centralizado para un documento.


## `facturacion_mexico/motor_reglas/api.py`


### `get_applicable_rules(doctype, context)`

**Módulo:** `facturacion_mexico.motor_reglas.api`

Obtener reglas aplicables a un DocType específico.


### `test_rule(rule_name, document_name)`

**Módulo:** `facturacion_mexico.motor_reglas.api`

Probar regla en documento específico sin afectar el documento.


### `create_rule_from_template(template_name, customizations)`

**Módulo:** `facturacion_mexico.motor_reglas.api`

Crear regla desde template predefinido.


### `get_rule_execution_stats(rule_name, date_range)`

**Módulo:** `facturacion_mexico.motor_reglas.api`

Obtener estadísticas de ejecución de reglas.


### `bulk_apply_rules(doctype, filters, dry_run)`

**Módulo:** `facturacion_mexico.motor_reglas.api`

Aplicar reglas masivamente a documentos existentes.


### `validate_rule_syntax(rule_name)`

**Módulo:** `facturacion_mexico.motor_reglas.api`

Validar sintaxis completa de una regla.


### `execute_validation_rules(doctype, document_name)`

**Módulo:** `facturacion_mexico.motor_reglas.api`

Ejecutar todas las reglas de validación para un documento específico.


## `facturacion_mexico/multi_sucursal/api.py`


### `get_lugar_expedicion(company, sales_invoice, customer)`

**Módulo:** `facturacion_mexico.multi_sucursal.api`

API: Obtener lugar de expedición según reglas de negocio.


### `get_sucursales_disponibles(company)`

**Módulo:** `facturacion_mexico.multi_sucursal.api`

API: Obtener lista de sucursales disponibles.


### `establecer_lugar_expedicion(sales_invoice, codigo_postal, force_update)`

**Módulo:** `facturacion_mexico.multi_sucursal.api`

API: Establecer lugar de expedición en una factura.


### `validar_configuracion_sucursales(company)`

**Módulo:** `facturacion_mexico.multi_sucursal.api`

API: Validar configuración de sucursales para una empresa.


### `bulk_set_lugar_expedicion(invoices, codigo_postal)`

**Módulo:** `facturacion_mexico.multi_sucursal.api`

API: Establecer lugar de expedición en múltiples facturas.


### `get_facturas_sin_lugar_expedicion(company, days, limit)`

**Módulo:** `facturacion_mexico.multi_sucursal.api`

API: Obtener facturas sin lugar de expedición.


## `facturacion_mexico/multi_sucursal/branch_auto_selector.py`


### `auto_select_branch_for_invoice(company, sales_invoice)`

**Módulo:** `facturacion_mexico.multi_sucursal.branch_auto_selector`

API para auto-selección de sucursal


### `get_user_preferred_branches(company)`

**Módulo:** `facturacion_mexico.multi_sucursal.branch_auto_selector`

API para obtener sucursales preferidas del usuario


### `validate_branch_for_invoice(company, branch, sales_invoice)`

**Módulo:** `facturacion_mexico.multi_sucursal.branch_auto_selector`

API para validar sucursal para factura


## `facturacion_mexico/multi_sucursal/branch_folio_manager.py`


### `get_branch_folio_status(branch)`

**Módulo:** `facturacion_mexico.multi_sucursal.branch_folio_manager`

API para obtener estado de folios de una sucursal


### `reserve_folio_for_invoice(branch, sales_invoice)`

**Módulo:** `facturacion_mexico.multi_sucursal.branch_folio_manager`

API para reservar folio para factura


### `release_folio_for_invoice(branch, sales_invoice)`

**Módulo:** `facturacion_mexico.multi_sucursal.branch_folio_manager`

API para liberar folio de factura


### `get_branch_folio_reservations(branch, status)`

**Módulo:** `facturacion_mexico.multi_sucursal.branch_folio_manager`

API para obtener reservas de folios


## `facturacion_mexico/multi_sucursal/branch_manager.py`


### `get_company_branch_health_summary(company)`

**Módulo:** `facturacion_mexico.multi_sucursal.branch_manager`

API para obtener resumen de salud de sucursales de una empresa


### `get_certificate_optimization_suggestions(company)`

**Módulo:** `facturacion_mexico.multi_sucursal.branch_manager`

API para obtener sugerencias de optimización de certificados


## `facturacion_mexico/multi_sucursal/certificate_selector.py`


### `get_branch_certificate_status(branch)`

**Módulo:** `facturacion_mexico.multi_sucursal.certificate_selector`

API para obtener estado de certificados de una sucursal


### `select_certificate_for_invoice(branch, certificate_type)`

**Módulo:** `facturacion_mexico.multi_sucursal.certificate_selector`

API para seleccionar certificado óptimo para facturación


## `facturacion_mexico/multi_sucursal/doctype/configuracion_fiscal_sucursal/configuracion_fiscal_sucursal.py`


### `get_branch_fiscal_status(branch)`

**Módulo:** `facturacion_mexico.multi_sucursal.doctype.configuracion_fiscal_sucursal.configuracion_fiscal_sucursal`

API para obtener estado fiscal de una sucursal


### `sync_all_branch_configurations()`

**Módulo:** `facturacion_mexico.multi_sucursal.doctype.configuracion_fiscal_sucursal.configuracion_fiscal_sucursal`

Sincronizar todas las configuraciones fiscales con sus respectivas sucursales


## `facturacion_mexico/multi_sucursal/migration.py`


### `detect_legacy_system()`

**Módulo:** `facturacion_mexico.multi_sucursal.migration`

API para detectar sistema legacy


### `preview_migration()`

**Módulo:** `facturacion_mexico.multi_sucursal.migration`

API para previsualizar migración (dry run)


### `execute_migration(confirm)`

**Módulo:** `facturacion_mexico.multi_sucursal.migration`

API para ejecutar migración real


### `get_migration_status()`

**Módulo:** `facturacion_mexico.multi_sucursal.migration`

API para obtener estado de migración


## `facturacion_mexico/multi_sucursal/utils.py`


### `refresh_all_branch_configurations()`

**Módulo:** `facturacion_mexico.multi_sucursal.utils`

API para refrescar todas las configuraciones fiscales de sucursales


## `facturacion_mexico/validaciones/api.py`


### `validate_rfc(rfc, use_cache)`

**Módulo:** `facturacion_mexico.validaciones.api`

Validar RFC con SAT usando cache inteligente.


### `validate_customer_rfc_with_facturapi(customer_name)`

**Módulo:** `facturacion_mexico.validaciones.api`

Validar RFC de Customer con FacturAPI incluyendo verificación de dirección.


### `validate_lista_69b(rfc, use_cache)`

**Módulo:** `facturacion_mexico.validaciones.api`

Validar si RFC está en Lista 69B (Contribuyentes no localizados).


### `bulk_validate_rfc(rfc_list)`

**Módulo:** `facturacion_mexico.validaciones.api`

Validar múltiples RFCs en lote.


### `get_cache_stats()`

**Módulo:** `facturacion_mexico.validaciones.api`

Obtener estadísticas del cache SAT.


### `cleanup_expired_cache(days_to_keep)`

**Módulo:** `facturacion_mexico.validaciones.api`

Limpiar cache expirado más antiguo que X días.


### `force_refresh_cache(validation_key, validation_type)`

**Módulo:** `facturacion_mexico.validaciones.api`

Forzar actualización de un cache específico.


### `validate_customers_bulk(customer_names, max_validations_per_run)`

**Módulo:** `facturacion_mexico.validaciones.api`

Validar múltiples customers en lote (para scheduled job).


### `get_nightly_validation_stats()`

**Módulo:** `facturacion_mexico.validaciones.api`

Obtener estadísticas de las últimas ejecuciones nocturnas.


### `get_customers_validation_summary()`

**Módulo:** `facturacion_mexico.validaciones.api`

Obtener resumen del estado de validación de todos los customers.


## `facturacion_mexico/validaciones/doctype/sat_validation_cache/sat_validation_cache.py`


### `cleanup_expired_cache()`

**Módulo:** `facturacion_mexico.validaciones.doctype.sat_validation_cache.sat_validation_cache`

Limpiar cache expirado (llamada por scheduler).


### `get_cache_statistics()`

**Módulo:** `facturacion_mexico.validaciones.doctype.sat_validation_cache.sat_validation_cache`

Obtener estadísticas del cache.


## `facturacion_mexico/validaciones/sales_invoice_cancel_guard.py`


### `can_cancel_sales_invoice(si_name)`

**Módulo:** `facturacion_mexico.validaciones.sales_invoice_cancel_guard`

Para el cliente: responde si se puede cancelar y por qué.


## `facturacion_mexico/validation/architecture_validator.py`


### `validate_resilient_architecture(factura_fiscal_name)`

**Módulo:** `facturacion_mexico.validation.architecture_validator`

API pública para validar arquitectura resiliente de una factura específica.


### `validate_shadow_mode_invoices()`

**Módulo:** `facturacion_mexico.validation.architecture_validator`

API pública para validar todas las facturas SHADOW MODE (20 facturas).
