def create_fiscal_event(doc, method):
	"""Crear evento fiscal cuando se inserta Factura Fiscal Mexico."""
	import frappe

	from facturacion_mexico.facturacion_fiscal.doctype.fiscal_event_mx.fiscal_event_mx import FiscalEventMX

	# Crear evento de creación de factura fiscal usando customer directo del DocType
	event_data = {
		"sales_invoice": doc.sales_invoice,
		"customer": doc.customer,  # Usar customer directo del DocType
		"total_amount": getattr(doc, "total_fiscal", 0),
		"fm_fiscal_status": doc.fm_fiscal_status,
		"company": doc.company,
	}

	# Crear evento con parametros correctos: (event_type, reference_doctype, reference_name, event_data)
	event_doc = FiscalEventMX.create_event("create", "Factura Fiscal Mexico", doc.name, event_data)

	# Marcar como exitoso solo si el evento se creó correctamente
	if event_doc:
		FiscalEventMX.mark_event_success(event_doc.name, {"status": "created"})
