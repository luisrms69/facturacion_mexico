import frappe
from frappe import _


@frappe.whitelist()
def get_ereceipt_summary(ereceipt_name: str) -> dict:
	"""Resumen del E-Receipt para el widget en Sales Invoice.

	Sigue el mismo patrón que get_ffm_summary: lee del DocType vinculado sin
	copiar datos en Sales Invoice. UUID/folio/invoice_id viven en EReceipt MX
	o en Factura Global MX — nunca en Sales Invoice.
	"""
	if not ereceipt_name:
		return {}

	try:
		if not frappe.has_permission("EReceipt MX", doc=ereceipt_name, ptype="read"):
			frappe.throw(_("Sin permiso de lectura sobre EReceipt MX"), frappe.PermissionError)

		er = frappe.get_doc("EReceipt MX", ereceipt_name).as_dict()

		result = {
			"name": er.get("name"),
			"status": er.get("status"),
			"self_invoice_url": er.get("self_invoice_url"),
			"expires_at": er.get("expiry_date"),
			"invoice_uuid": er.get("invoice_uuid"),
			"invoice_folio": er.get("invoice_folio"),
			"invoiced_at": er.get("invoiced_at"),
			"factura_global_mx": er.get("factura_global_mx"),
			"factura_global_uuid": None,
		}

		# Si fue incluido en Factura Global, leer UUID global desde FG (solo si tiene permiso)
		if er.get("factura_global_mx"):
			if frappe.has_permission("Factura Global MX", doc=er["factura_global_mx"], ptype="read"):
				fg_uuid = frappe.db.get_value("Factura Global MX", er["factura_global_mx"], "invoice_uuid")
				result["factura_global_uuid"] = fg_uuid

		return result

	except frappe.DoesNotExistError:
		return {}
	except Exception as e:
		frappe.log_error(f"Error en get_ereceipt_summary para {ereceipt_name}: {e}")
		return {}
