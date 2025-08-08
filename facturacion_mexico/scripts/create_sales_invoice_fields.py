import frappe


def apply_custom_fields():
	fields = [
		{
			"fieldname": "fm_fiscal_status",
			"label": "Estado Fiscal",
			"fieldtype": "Select",
			"options": "\nBORRADOR\nPROCESANDO\nTIMBRADO\nERROR\nCANCELADO\nPENDIENTE_CANCELACION\nARCHIVADO",
		},
		{
			"fieldname": "fm_factura_fiscal_mx",
			"label": "Factura Fiscal MX",
			"fieldtype": "Link",
			"options": "Factura Fiscal Mexico",
		},
		{
			"fieldname": "fm_last_status_update",
			"label": "Última Actualización",
			"fieldtype": "Datetime",
		},
		{
			"fieldname": "fm_quick_status",
			"label": "Estado Visual",
			"fieldtype": "HTML",
		},
		{
			"fieldname": "fm_fiscal_section",
			"label": "Información Fiscal México",
			"fieldtype": "Section Break",
		},
		{
			"fieldname": "fm_column_break_fiscal",
			"label": "",
			"fieldtype": "Column Break",
		},
	]

	for f in fields:
		f.update(
			{
				"doctype": "Custom Field",
				"dt": "Sales Invoice",
				"insert_after": "discount_amount",
				"read_only": 1,
				"allow_on_submit": 1,
				"depends_on": "eval:doc.docstatus == 1",
				"module": "Facturacion Fiscal",
				"no_copy": 1,
				"name": f"Sales Invoice-{f['fieldname']}",
			}
		)
		if not frappe.db.exists("Custom Field", f["name"]):
			doc = frappe.get_doc(f)
			doc.insert()
			print(f"✅ Campo creado: {f['fieldname']}")
		else:
			print(f"⚠️ Ya existe: {f['fieldname']}")

	# Manual commit required: Custom Fields setup script must persist changes immediately for next process steps # nosemgrep
	frappe.db.commit()
	print("🎉 Todos los Custom Fields aplicados")


# Ejecutar con:
# bench --site facturacion.dev execute facturacion_mexico.scripts.create_sales_invoice_fields
