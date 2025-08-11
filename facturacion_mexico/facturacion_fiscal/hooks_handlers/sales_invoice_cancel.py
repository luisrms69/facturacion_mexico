import frappe
from frappe import _


def handle_fiscal_cancellation(doc, method):
	"""Manejar cancelación fiscal cuando se cancela Sales Invoice."""

	# Solo para facturas con datos fiscales
	if not _should_handle_fiscal_cancellation(doc):
		return

	# Manejar cancelación según estado fiscal
	_handle_cancellation_by_status(doc)


def _should_handle_fiscal_cancellation(doc):
	"""Determinar si se debe manejar cancelación fiscal."""
	# Solo para facturas canceladas
	if doc.docstatus != 2:
		return False

	# Solo si tiene datos fiscales
	if not doc.customer:
		return False

	customer = frappe.get_doc("Customer", doc.customer)
	return bool(customer.tax_id)


def _handle_cancellation_by_status(doc):
	"""Manejar cancelación según estado fiscal actual."""
	fm_fiscal_status = doc.fm_fiscal_status

	if fm_fiscal_status == "TIMBRADO":
		# Factura timbrada: solicitar cancelación fiscal
		_request_fiscal_cancellation(doc)
	elif fm_fiscal_status == "BORRADOR":
		# Factura pendiente: marcar como cancelada sin timbrar
		_mark_as_cancelled_without_stamping(doc)
	elif fm_fiscal_status == "ERROR":
		# Factura con error: solo marcar como cancelada
		_mark_as_cancelled_with_error(doc)
	else:
		# Otros estados: registro de evento
		_create_cancellation_event(doc)


def _request_fiscal_cancellation(doc):
	"""Solicitar cancelación fiscal para factura timbrada."""
	# LEGACY: FiscalEventMX eliminado - reemplazado por FacturAPIResponseLog

	try:
		# Obtener Factura Fiscal
		if not doc.fm_factura_fiscal_mx:
			frappe.throw(_("No se encontró factura fiscal para cancelar"))

		factura_fiscal = frappe.get_doc("Factura Fiscal Mexico", doc.fm_factura_fiscal_mx)

		# LEGACY: FiscalEventMX eliminado - solo actualizar estados
		# Actualizar estado a PENDIENTE_CANCELACION
		factura_fiscal.fm_fiscal_status = "PENDIENTE_CANCELACION"
		factura_fiscal.save()

		# Actualizar Sales Invoice
		frappe.db.set_value("Sales Invoice", doc.name, "fm_fiscal_status", "PENDIENTE_CANCELACION")

		# Intentar cancelación automática si está configurado
		if _should_auto_cancel():
			_auto_cancel_fiscal_invoice(doc)

	except Exception as e:
		frappe.logger().error(f"Error solicitando cancelación fiscal {doc.name}: {e!s}")
		frappe.msgprint(_("Error al solicitar cancelación fiscal:") + str(e))


def _mark_as_cancelled_without_stamping(doc):
	"""Marcar como cancelada sin timbrar."""
	# LEGACY: FiscalEventMX eliminado - reemplazado por FacturAPIResponseLog

	# Actualizar estado fiscal
	frappe.db.set_value("Sales Invoice", doc.name, "fm_fiscal_status", "CANCELADO")

	# Crear evento de cancelación
	if doc.fm_factura_fiscal_mx:
		factura_fiscal = frappe.get_doc("Factura Fiscal Mexico", doc.fm_factura_fiscal_mx)
		factura_fiscal.fm_fiscal_status = "CANCELADO"
		factura_fiscal.save()

		# LEGACY: FiscalEventMX eliminado - solo logging
		frappe.log_error(
			f"Factura {doc.name} cancelada sin timbrar",
			"Sales Invoice Cancelled Without Stamping",
		)


def _mark_as_cancelled_with_error(doc):
	"""Marcar como cancelada con error previo."""
	# Actualizar estado fiscal
	frappe.db.set_value("Sales Invoice", doc.name, "fm_fiscal_status", "CANCELADO")

	# Registrar evento si hay factura fiscal
	if doc.fm_factura_fiscal_mx:
		_create_cancellation_event(doc)


def _create_cancellation_event(doc):
	"""Crear evento de cancelación genérico."""
	# LEGACY: FiscalEventMX eliminado - reemplazado por FacturAPIResponseLog

	if not doc.fm_factura_fiscal_mx:
		return

	# LEGACY: FiscalEventMX eliminado - solo logging
	frappe.log_error(
		f"Evento cancelación creado para {doc.name}",
		"Sales Invoice Cancellation Event",
	)


def _should_auto_cancel():
	"""Determinar si se debe auto-cancelar fiscalmente."""
	settings = frappe.get_single("Facturacion Mexico Settings")
	return getattr(settings, "auto_cancel_fiscal", False)


def _auto_cancel_fiscal_invoice(doc):
	"""Auto-cancelar factura fiscal si está configurado."""
	try:
		from facturacion_mexico.facturacion_fiscal.timbrado_api import TimbradoAPI

		# Crear instancia de API
		_api = TimbradoAPI()

		# Cancelar en background job
		frappe.enqueue(
			method="facturacion_mexico.facturacion_fiscal.timbrado_api.cancelar_factura",
			queue="default",
			timeout=300,
			sales_invoice_name=doc.name,
			motivo="02",
		)

		frappe.msgprint(_("La factura se está cancelando fiscalmente"))

	except Exception as e:
		frappe.logger().error(f"Error auto-cancelando factura {doc.name}: {e!s}")
		# No lanzar error para no bloquear la cancelación
		frappe.msgprint(_("Error al auto-cancelar fiscalmente:") + str(e))
