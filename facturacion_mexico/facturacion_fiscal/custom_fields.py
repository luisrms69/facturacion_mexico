import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def create_sales_invoice_custom_fields():
	"""Crear custom fields para Sales Invoice."""
	custom_fields = {
		"Sales Invoice": [
			{
				"fieldname": "fm_informacion_fiscal_section",
				"fieldtype": "Section Break",
				"label": "Información Fiscal MX",
				"insert_after": "customer",
				"collapsible": 1,
			},
			{
				"fieldname": "fm_cfdi_use",
				"fieldtype": "Link",
				"label": "Uso del CFDI",
				"options": "Uso CFDI SAT",
				"insert_after": "fm_informacion_fiscal_section",
				"reqd": 1,
			},
			{
				"fieldname": "fm_payment_method_sat",
				"fieldtype": "Select",
				"label": "Método de Pago SAT",
				"options": "PUE\nPPD",
				"default": "PUE",
				"insert_after": "fm_cfdi_use",
			},
			{
				"fieldname": "fm_column_break_fiscal",
				"fieldtype": "Column Break",
				"insert_after": "fm_payment_method_sat",
			},
			{
				"fieldname": "fm_fiscal_status",
				"fieldtype": "Select",
				"label": "Estado Fiscal",
				"options": "Pendiente\nTimbrada\nCancelada\nError",
				"default": "Pendiente",
				"read_only": 1,
				"insert_after": "fm_column_break_fiscal",
			},
			{
				"fieldname": "fm_uuid_fiscal",
				"fieldtype": "Data",
				"label": "UUID Fiscal",
				"read_only": 1,
				"insert_after": "fm_fiscal_status",
			},
			{
				"fieldname": "fm_factura_fiscal_mx",
				"fieldtype": "Link",
				"label": "Factura Fiscal México",
				"options": "Factura Fiscal Mexico",
				"read_only": 1,
				"insert_after": "fm_uuid_fiscal",
			},
		]
	}

	create_custom_fields(custom_fields)


def create_customer_custom_fields():
	"""Crear custom fields para Customer."""
	custom_fields = {
		"Customer": [
			{
				"fieldname": "fm_informacion_fiscal_section_customer",
				"fieldtype": "Section Break",
				"label": "Información Fiscal MX",
				"insert_after": "customer_details",
				"collapsible": 1,
			},
			{
				"fieldname": "fm_rfc",
				"fieldtype": "Data",
				"label": "RFC",
				"insert_after": "fm_informacion_fiscal_section_customer",
			},
			{
				"fieldname": "fm_column_break_fiscal_customer",
				"fieldtype": "Column Break",
				"insert_after": "fm_rfc",
			},
			{
				"fieldname": "fm_regimen_fiscal",
				"fieldtype": "Link",
				"label": "Régimen Fiscal",
				"options": "Regimen Fiscal SAT",
				"insert_after": "fm_column_break_fiscal_customer",
			},
			{
				"fieldname": "fm_uso_cfdi_default",
				"fieldtype": "Link",
				"label": "Uso CFDI por Defecto",
				"options": "Uso CFDI SAT",
				"insert_after": "fm_regimen_fiscal",
			},
		]
	}

	create_custom_fields(custom_fields)


def create_item_custom_fields():
	"""Crear custom fields para Item."""
	custom_fields = {
		"Item": [
			{
				"fieldname": "fm_clasificacion_sat_section",
				"fieldtype": "Section Break",
				"label": "Clasificación SAT",
				"insert_after": "item_defaults",
				"collapsible": 1,
			},
			{
				"fieldname": "fm_producto_servicio_sat",
				"fieldtype": "Data",
				"label": "Código Producto/Servicio SAT",
				"insert_after": "fm_clasificacion_sat_section",
			},
			{
				"fieldname": "fm_column_break_item_sat",
				"fieldtype": "Column Break",
				"insert_after": "fm_producto_servicio_sat",
			},
			{
				"fieldname": "fm_unidad_sat",
				"fieldtype": "Data",
				"label": "Código Unidad SAT",
				"insert_after": "fm_column_break_item_sat",
			},
		]
	}

	create_custom_fields(custom_fields)


def create_payment_entry_custom_fields():
	"""Crear custom fields para Payment Entry - Sprint 2."""
	custom_fields = {
		"Payment Entry": [
			{
				"fieldname": "fm_informacion_fiscal_section",
				"fieldtype": "Section Break",
				"label": "Información Fiscal MX",
				"insert_after": "references",
				"collapsible": 1,
			},
			{
				"fieldname": "fm_complemento_pago",
				"fieldtype": "Link",
				"label": "Complemento Pago Generado",
				"options": "Complemento Pago MX",
				"read_only": 1,
				"insert_after": "fm_informacion_fiscal_section",
			},
			{
				"fieldname": "fm_require_complement",
				"fieldtype": "Check",
				"label": "Requiere Complemento",
				"insert_after": "fm_complemento_pago",
			},
			{
				"fieldname": "column_break_payment_mx",
				"fieldtype": "Column Break",
				"insert_after": "fm_require_complement",
			},
			{
				"fieldname": "fm_complement_generated",
				"fieldtype": "Check",
				"label": "Complemento Generado",
				"read_only": 1,
				"insert_after": "column_break_payment_mx",
			},
			{
				"fieldname": "fm_forma_pago_sat",
				"fieldtype": "Link",
				"label": "Forma de Pago SAT",
				"options": "Forma Pago SAT",
				"insert_after": "fm_complement_generated",
			},
		]
	}

	create_custom_fields(custom_fields)


def create_sales_invoice_sprint2_custom_fields():
	"""Crear custom fields adicionales para Sales Invoice - Sprint 2."""
	custom_fields = {
		"Sales Invoice": [
			{
				"fieldname": "fm_payment_status",
				"fieldtype": "Select",
				"label": "Estado de Pago",
				"options": "Pagada\nParcial\nPendiente",
				"read_only": 1,
				"insert_after": "fm_payment_method_sat",
			},
			{
				"fieldname": "fm_pending_amount",
				"fieldtype": "Currency",
				"label": "Monto Pendiente",
				"read_only": 1,
				"insert_after": "fm_payment_status",
			},
			{
				"fieldname": "fm_complementos_count",
				"fieldtype": "Int",
				"label": "Número de Complementos",
				"read_only": 1,
				"insert_after": "fm_pending_amount",
			},
		]
	}

	create_custom_fields(custom_fields)


def create_customer_sprint2_custom_fields():
	"""Crear custom fields adicionales para Customer - Sprint 2."""
	custom_fields = {
		"Customer": [
			{
				"fieldname": "fm_rfc_validated",
				"fieldtype": "Check",
				"label": "RFC Validado con SAT",
				"read_only": 1,
				"insert_after": "fm_rfc",
			},
			{
				"fieldname": "fm_rfc_validation_date",
				"fieldtype": "Date",
				"label": "Fecha Validación RFC",
				"read_only": 1,
				"insert_after": "fm_rfc_validated",
			},
			{
				"fieldname": "fm_lista_69b_status",
				"fieldtype": "Select",
				"label": "Status Lista 69B",
				"options": "\nNo Listado\nPresunto\nDefinitivo",
				"read_only": 1,
				"insert_after": "fm_rfc_validation_date",
			},
		]
	}

	create_custom_fields(custom_fields)


def create_all_custom_fields():
	"""Crear todos los custom fields de una vez."""
	create_sales_invoice_custom_fields()
	create_customer_custom_fields()
	create_item_custom_fields()
	# Sprint 2 fields
	create_payment_entry_custom_fields()
	create_sales_invoice_sprint2_custom_fields()
	create_customer_sprint2_custom_fields()
	# Sprint 6 Addenda fields
	create_addenda_custom_fields()
	frappe.msgprint(_("Custom Fields para facturación México creados exitosamente"))


def create_addenda_custom_fields():
	"""Crear custom fields para sistema de addendas Sprint 6."""
	try:
		# Import and call addenda custom fields creation
		from facturacion_mexico.custom_fields.sales_invoice_addenda_fields import (
			install_addenda_custom_fields,
		)

		install_addenda_custom_fields()
		print("✅ Custom fields de addendas creados exitosamente")
	except Exception as e:
		print(f"⚠️ Error creando custom fields de addendas: {e}")
		frappe.log_error(f"Error creating addenda custom fields: {e}", "Addenda Custom Fields")


def remove_custom_fields():
	"""Remover custom fields (para desinstalación)."""
	fields_to_remove = [
		# Sales Invoice
		"Sales Invoice-fm_informacion_fiscal_section",
		"Sales Invoice-fm_cfdi_use",
		"Sales Invoice-fm_payment_method_sat",
		"Sales Invoice-fm_column_break_fiscal",
		"Sales Invoice-fm_fiscal_status",
		"Sales Invoice-fm_uuid_fiscal",
		"Sales Invoice-fm_factura_fiscal_mx",
		# Sprint 2 - Sales Invoice
		"Sales Invoice-fm_payment_status",
		"Sales Invoice-fm_pending_amount",
		"Sales Invoice-fm_complementos_count",
		# Customer
		"Customer-fm_informacion_fiscal_section_customer",
		"Customer-fm_rfc",
		"Customer-fm_column_break_fiscal_customer",
		"Customer-fm_regimen_fiscal",
		"Customer-fm_uso_cfdi_default",
		# Sprint 2 - Customer
		"Customer-fm_rfc_validated",
		"Customer-fm_rfc_validation_date",
		"Customer-fm_lista_69b_status",
		# Sprint 2 - Payment Entry
		"Payment Entry-informacion_fiscal_mx_section",
		"Payment Entry-fm_complemento_pago",
		"Payment Entry-fm_require_complement",
		"Payment Entry-column_break_payment_mx",
		"Payment Entry-fm_complement_generated",
		"Payment Entry-fm_forma_pago_sat",
		# Item
		"Item-fm_clasificacion_sat_section",
		"Item-fm_producto_servicio_sat",
		"Item-fm_column_break_item_sat",
		"Item-fm_unidad_sat",
	]

	for field_name in fields_to_remove:
		if frappe.db.exists("Custom Field", field_name):
			frappe.delete_doc("Custom Field", field_name)

	frappe.msgprint(_("Custom Fields para facturación México removidos"))
