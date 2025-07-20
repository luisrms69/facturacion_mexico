import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def create_sales_invoice_custom_fields():
	"""Crear custom fields para Sales Invoice."""
	custom_fields = {
		"Sales Invoice": [
			{
				"fieldname": "informacion_fiscal_mx_section",
				"fieldtype": "Section Break",
				"label": "Información Fiscal MX",
				"insert_after": "customer",
				"collapsible": 1,
			},
			{
				"fieldname": "cfdi_use",
				"fieldtype": "Link",
				"label": "Uso del CFDI",
				"options": "Uso CFDI SAT",
				"insert_after": "informacion_fiscal_mx_section",
				"reqd": 1,
			},
			{
				"fieldname": "payment_method_sat",
				"fieldtype": "Select",
				"label": "Método de Pago SAT",
				"options": "PUE\nPPD",
				"default": "PUE",
				"insert_after": "cfdi_use",
			},
			{
				"fieldname": "column_break_fiscal_mx",
				"fieldtype": "Column Break",
				"insert_after": "payment_method_sat",
			},
			{
				"fieldname": "fiscal_status",
				"fieldtype": "Select",
				"label": "Estado Fiscal",
				"options": "Pendiente\nTimbrada\nCancelada\nError",
				"default": "Pendiente",
				"read_only": 1,
				"insert_after": "column_break_fiscal_mx",
			},
			{
				"fieldname": "uuid_fiscal",
				"fieldtype": "Data",
				"label": "UUID Fiscal",
				"read_only": 1,
				"insert_after": "fiscal_status",
			},
			{
				"fieldname": "factura_fiscal_mx",
				"fieldtype": "Link",
				"label": "Factura Fiscal México",
				"options": "Factura Fiscal Mexico",
				"read_only": 1,
				"insert_after": "uuid_fiscal",
			},
		]
	}

	create_custom_fields(custom_fields)


def create_customer_custom_fields():
	"""Crear custom fields para Customer."""
	custom_fields = {
		"Customer": [
			{
				"fieldname": "informacion_fiscal_mx_section",
				"fieldtype": "Section Break",
				"label": "Información Fiscal MX",
				"insert_after": "customer_details",
				"collapsible": 1,
			},
			{
				"fieldname": "rfc",
				"fieldtype": "Data",
				"label": "RFC",
				"insert_after": "informacion_fiscal_mx_section",
			},
			{"fieldname": "column_break_fiscal_customer", "fieldtype": "Column Break", "insert_after": "rfc"},
			{
				"fieldname": "regimen_fiscal",
				"fieldtype": "Link",
				"label": "Régimen Fiscal",
				"options": "Regimen Fiscal SAT",
				"insert_after": "column_break_fiscal_customer",
			},
			{
				"fieldname": "uso_cfdi_default",
				"fieldtype": "Link",
				"label": "Uso CFDI por Defecto",
				"options": "Uso CFDI SAT",
				"insert_after": "regimen_fiscal",
			},
		]
	}

	create_custom_fields(custom_fields)


def create_item_custom_fields():
	"""Crear custom fields para Item."""
	custom_fields = {
		"Item": [
			{
				"fieldname": "clasificacion_sat_section",
				"fieldtype": "Section Break",
				"label": "Clasificación SAT",
				"insert_after": "item_defaults",
				"collapsible": 1,
			},
			{
				"fieldname": "producto_servicio_sat",
				"fieldtype": "Data",
				"label": "Código Producto/Servicio SAT",
				"insert_after": "clasificacion_sat_section",
			},
			{
				"fieldname": "column_break_item_sat",
				"fieldtype": "Column Break",
				"insert_after": "producto_servicio_sat",
			},
			{
				"fieldname": "unidad_sat",
				"fieldtype": "Data",
				"label": "Código Unidad SAT",
				"insert_after": "column_break_item_sat",
			},
		]
	}

	create_custom_fields(custom_fields)


def create_payment_entry_custom_fields():
	"""Crear custom fields para Payment Entry - Sprint 2."""
	custom_fields = {
		"Payment Entry": [
			{
				"fieldname": "informacion_fiscal_mx_section",
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
				"insert_after": "informacion_fiscal_mx_section",
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
				"insert_after": "payment_method_sat",
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
				"insert_after": "rfc",
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
	frappe.msgprint(_("Custom Fields para facturación México creados exitosamente"))


def remove_custom_fields():
	"""Remover custom fields (para desinstalación)."""
	fields_to_remove = [
		# Sales Invoice
		"Sales Invoice-informacion_fiscal_mx_section",
		"Sales Invoice-cfdi_use",
		"Sales Invoice-payment_method_sat",
		"Sales Invoice-column_break_fiscal_mx",
		"Sales Invoice-fiscal_status",
		"Sales Invoice-uuid_fiscal",
		"Sales Invoice-factura_fiscal_mx",
		# Sprint 2 - Sales Invoice
		"Sales Invoice-fm_payment_status",
		"Sales Invoice-fm_pending_amount",
		"Sales Invoice-fm_complementos_count",
		# Customer
		"Customer-informacion_fiscal_mx_section",
		"Customer-rfc",
		"Customer-column_break_fiscal_customer",
		"Customer-regimen_fiscal",
		"Customer-uso_cfdi_default",
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
		"Item-clasificacion_sat_section",
		"Item-producto_servicio_sat",
		"Item-column_break_item_sat",
		"Item-unidad_sat",
	]

	for field_name in fields_to_remove:
		if frappe.db.exists("Custom Field", field_name):
			frappe.delete_doc("Custom Field", field_name)

	frappe.msgprint(_("Custom Fields para facturación México removidos"))
