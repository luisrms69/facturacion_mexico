def register_status_changes(doc, method):
	"""Registrar cambios de estado en Factura Fiscal Mexico."""
	import frappe

	# LEGACY: FiscalEventMX eliminado - reemplazado por FacturAPIResponseLog

	# Skip para documentos nuevos para evitar conflictos con validaciones
	if doc.is_new():
		return

	# Solo registrar si hay cambios en el estado fiscal
	if doc.has_value_changed("fm_fiscal_status"):
		old_doc = doc.get_doc_before_save()
		old_status = old_doc.fm_fiscal_status if old_doc else None
		new_status = doc.fm_fiscal_status

		# Skip si no hay cambio real
		if old_status == new_status:
			return

		# LEGACY: FiscalEventMX eliminado - solo logging
		frappe.log_error(
			f"Cambio estado fiscal {old_status} → {new_status} para {doc.name}",
			"Factura Fiscal Status Change",
		)
