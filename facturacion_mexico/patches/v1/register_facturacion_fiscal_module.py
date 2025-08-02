import frappe


def execute():
	if not frappe.db.exists("Module Def", "Facturacion Fiscal"):
		module = frappe.get_doc(
			{
				"doctype": "Module Def",
				"module_name": "Facturacion Fiscal",
				"app_name": "facturacion_mexico",
				"custom": 0,
			}
		)
		module.insert(ignore_permissions=True)
		frappe.db.commit()
		frappe.msgprint("✅ Módulo 'Facturacion Fiscal' registrado en BD")
	else:
		frappe.msgprint("INFO: Módulo 'Facturacion Fiscal' ya existe en BD")
