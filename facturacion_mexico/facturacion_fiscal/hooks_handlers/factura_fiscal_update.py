def register_status_changes(doc, method):
	"""Registrar cambios de estado en Factura Fiscal Mexico."""
	from facturacion_mexico.facturacion_fiscal.doctype.fiscal_event_mx.fiscal_event_mx import FiscalEventMX

	# Solo registrar si hay cambios en el estado fiscal
	if doc.has_value_changed("fiscal_status"):
		old_status = doc.get_doc_before_save().fiscal_status if doc.get_doc_before_save() else None
		new_status = doc.fiscal_status

		event_data = {
			"old_status": old_status,
			"new_status": new_status,
			"sales_invoice": doc.sales_invoice,
			"customer": doc.customer,
		}

		event_doc = FiscalEventMX.create_event(doc.name, "status_change", event_data)

		# Marcar como exitoso
		FiscalEventMX.mark_event_success(event_doc.name, {"status": "status_changed"})
