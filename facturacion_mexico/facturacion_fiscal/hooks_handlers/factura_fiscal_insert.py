import frappe
from frappe import _


def create_fiscal_event(doc, method):
	"""Crear evento fiscal cuando se inserta Factura Fiscal Mexico."""
	from facturacion_mexico.facturacion_fiscal.doctype.fiscal_event_mx.fiscal_event_mx import FiscalEventMX

	# Crear evento de creación de factura fiscal
	event_data = {
		"sales_invoice": doc.sales_invoice,
		"customer": doc.customer,
		"total_amount": doc.total_amount,
		"fiscal_status": doc.fiscal_status,
	}

	event_doc = FiscalEventMX.create_event(doc.name, "factura_fiscal_created", event_data)

	# Marcar como exitoso
	FiscalEventMX.mark_event_success(event_doc.name, {"status": "created"})
