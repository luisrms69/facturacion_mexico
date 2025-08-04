import frappe


def create_custom_fields():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	custom_fields = {
		"Sales Invoice": [
			dict(
				fieldname="fm_factura_fiscal_mx",
				label="Factura Fiscal MX",
				fieldtype="Link",
				options="Factura Fiscal Mexico",
				insert_after="customer",
				hidden=0,
				read_only=1,
				no_copy=1,
			)
		]
	}

	create_custom_fields(custom_fields)
