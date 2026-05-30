<!--
  ARCHIVO GENERADO AUTOMÁTICAMENTE. NO EDITAR MANUALMENTE.
  Regenerar con: python3 scripts/generate_reference.py
  Fecha generación: 2026-05-30 02:32
-->


# Referencia — Hooks

Hooks activos en el app. Fuente: `hooks.py`.


## doc_events

| DocType | Evento | Handler |
|---|---|---|
| `Branch` | `validate` | `validate_branch_fiscal_configuration` |
|  |  | `facturacion_mexico.multi_sucursal.custom_fields.branch_fiscal_fields.validate_branch_fiscal_configuration` |
| `Branch` | `after_insert` | `after_branch_insert` |
|  |  | `facturacion_mexico.multi_sucursal.custom_fields.branch_fiscal_fields.after_branch_insert` |
| `Branch` | `on_update` | `on_branch_update` |
|  |  | `facturacion_mexico.multi_sucursal.custom_fields.branch_fiscal_fields.on_branch_update` |
| `Customer` | `validate` | `validate_rfc_format` |
|  |  | `facturacion_mexico.validaciones.hooks_handlers.customer_validate.validate_rfc_format` |
| `Customer` | `before_save` | `validate_rfc_format` |
|  |  | `facturacion_mexico.validaciones.hooks_handlers.customer_validate.validate_rfc_format` |
| `Customer` | `after_insert` | `schedule_rfc_validation` |
|  |  | `facturacion_mexico.validaciones.hooks_handlers.customer_validate.schedule_rfc_validation` |
| `EReceipt MX` | `before_save` | `calculate_expiry_date` |
|  |  | `facturacion_mexico.ereceipts.hooks_handlers.ereceipt_validate.calculate_expiry_date` |
| `EReceipt MX` | `after_insert` | `generate_facturapi_ereceipt` |
|  |  | `facturacion_mexico.ereceipts.hooks_handlers.ereceipt_insert.generate_facturapi_ereceipt` |
| `Payment Entry` | `validate` | `check_ppd_requirement` |
|  |  | `facturacion_mexico.complementos_pago.hooks_handlers.payment_entry_validate.check_ppd_requirement` |
| `Payment Entry` | `validate` | `cargar_impuestos_en_payment_entry` |
|  |  | `facturacion_mexico.facturacion_fiscal.services.payment_entry_reclasificacion.cargar_impuestos_en_payment_entry` |
| `Payment Entry` | `on_submit` | `create_complement_if_required` |
|  |  | `facturacion_mexico.complementos_pago.hooks_handlers.payment_entry_submit.create_complement_if_required` |
| `Payment Entry` | `before_cancel` | `block_cancel_if_complemento_activo` |
|  |  | `facturacion_mexico.complementos_pago.hooks_handlers.payment_entry_cancel.block_cancel_if_complemento_activo` |
| `Payment Entry` | `on_cancel` | `cancel_related_complement` |
|  |  | `facturacion_mexico.complementos_pago.hooks_handlers.payment_entry_cancel.cancel_related_complement` |
| `Sales Invoice` | `before_validate` | `before_validate` |
|  |  | `facturacion_mexico.hooks_handlers.sales_invoice_automated_tax.before_validate` |
| `Sales Invoice` | `validate` | `validate` |
|  |  | `facturacion_mexico.hooks_handlers.sales_invoice_automated_tax.validate` |
| `Sales Invoice` | `validate` | `propagate_addenda_from_customer` |
|  |  | `facturacion_mexico.addendas.hooks_handlers.sales_invoice_addenda_propagate.propagate_addenda_from_customer` |


## after_install

- `facturacion_mexico.install.after_install`
- `facturacion_mexico.setup.enforce_sat_uom.enforce_sat_uom_policy_on_install`


## after_migrate

- `facturacion_mexico.setup.enforce_sat_uom.enforce_sat_uom_policy`
- `facturacion_mexico.setup.item_groups.ensure_fiscal_item_groups`
- `facturacion_mexico.setup.cfdi_received_expense_item_groups.ensure_cfdi_received_expense_item_groups`
- `facturacion_mexico.setup.cfdi_received_expense_items.ensure_cfdi_received_expense_items`


## fixtures

Fixtures exportados con `bench export-fixtures`:

- `{'dt': 'Custom Field'}`
- `{'dt': 'Mode of Payment'}`
- `{'dt': 'UOM'}`
- `{'dt': 'Role'}`
- `{'dt': 'DocPerm'}`
