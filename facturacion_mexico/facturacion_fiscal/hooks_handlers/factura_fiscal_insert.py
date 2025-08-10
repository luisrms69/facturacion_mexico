def create_fiscal_event(doc, method):
	"""Crear evento fiscal cuando se inserta Factura Fiscal Mexico."""
	import frappe

	# LEGACY: FiscalEventMX eliminado - reemplazado por FacturAPIResponseLog

	# LEGACY: FiscalEventMX eliminado - solo logging
	frappe.log_error(
		f"Factura fiscal {doc.name} creada",
		"Factura Fiscal Creation Event",
	)
