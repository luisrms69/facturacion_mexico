def register_status_changes(doc, method):
	"""Registrar cambios de estado en Factura Fiscal Mexico."""
	import frappe

	from facturacion_mexico.facturacion_fiscal.doctype.fiscal_event_mx.fiscal_event_mx import FiscalEventMX

	# Solo registrar si hay cambios en el estado fiscal
	if doc.has_value_changed("fm_fiscal_status"):
		old_status = doc.get_doc_before_save().fm_fiscal_status if doc.get_doc_before_save() else None
		new_status = doc.fm_fiscal_status

		# Usar customer directo del DocType (no de Sales Invoice)
		event_data = {
			"old_status": old_status,
			"new_status": new_status,
			"sales_invoice": doc.sales_invoice,
			"customer": doc.customer,  # Usar customer directo del DocType
			"company": doc.company,
		}

		# Crear evento con parametros correctos: (event_type, reference_doctype, reference_name, event_data)
		event_doc = FiscalEventMX.create_event("status_change", "Factura Fiscal Mexico", doc.name, event_data)

		# Marcar como exitoso solo si el evento se creó correctamente
		if event_doc:
			FiscalEventMX.mark_event_success(event_doc.name, {"status": "status_changed"})
