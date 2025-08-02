import frappe


def execute():
	doctype_name = "FacturAPI Response Item"
	module = "Facturacion Fiscal"

	# Verificar si existe
	if frappe.db.exists("DocType", doctype_name):
		frappe.msgprint(f"{doctype_name} ya existe. Se forzará recarga desde JSON.")
		frappe.db.set_value("DocType", doctype_name, "module", module)
	else:
		frappe.msgprint(f"{doctype_name} no encontrado. Se cargará por primera vez.")

	# Forzar recarga del esquema
	frappe.reload_doc("facturacion_mexico", "facturacion_fiscal", "facturapi_response_item", force=True)

	# Validación de referencia padre
	if not frappe.db.exists("DocType", "Factura Fiscal Mexico"):
		frappe.throw("DocType padre 'Factura Fiscal Mexico' no existe.")

	# Verificación rápida de campo
	meta = frappe.get_meta("Factura Fiscal Mexico")
	if not meta.get_field("respuestas_facturapi"):
		frappe.msgprint("⚠️ El campo 'respuestas_facturapi' no está presente.")
	else:
		frappe.msgprint("✅ Referencia a tabla hija verificada correctamente.")
