import frappe
from frappe import _


def create_fiscal_event(doc, method):
	"""Crear evento fiscal cuando se envía Sales Invoice."""

	# Solo para facturas con datos fiscales
	if not _should_create_fiscal_event(doc):
		return

	# Crear evento de emisión
	_create_emission_event(doc)

	# Auto-timbrar si está configurado
	if _should_auto_timbrar(doc):
		_auto_timbrar_factura(doc)


def _should_create_fiscal_event(doc):
	"""Determinar si se debe crear evento fiscal - Estrategia Híbrida."""
	# Solo para facturas enviadas
	if doc.docstatus != 1:
		return False

	# Solo si hay datos fiscales mínimos
	if not doc.customer:
		return False

	customer = frappe.get_doc("Customer", doc.customer)
	
	# ESTRATEGIA HÍBRIDA: Verificar tax_id primero, fm_rfc como fallback
	has_rfc = bool(customer.get('tax_id')) or bool(customer.get('fm_rfc'))
	return has_rfc


def _create_emission_event(doc):
	"""Crear evento de emisión de factura."""
	from facturacion_mexico.facturacion_fiscal.doctype.fiscal_event_mx.fiscal_event_mx import FiscalEventMX

	# Obtener o crear Factura Fiscal
	factura_fiscal = _get_or_create_factura_fiscal(doc)

	# Crear evento
	event_data = {
		"sales_invoice": doc.name,
		"customer": doc.customer,
		"total_amount": doc.grand_total,
		"currency": doc.currency,
	}

	# Crear evento con parametros correctos: (event_type, reference_doctype, reference_name, event_data)
	event_doc = FiscalEventMX.create_event("invoice_emission", "Factura Fiscal Mexico", factura_fiscal.name, event_data)

	# Marcar como exitoso inmediatamente
	FiscalEventMX.mark_event_success(event_doc.name, {"status": "emitted"})

	# Actualizar estado fiscal
	frappe.db.set_value("Sales Invoice", doc.name, "fm_fiscal_status", "Pendiente")


def _get_or_create_factura_fiscal(doc):
	"""Obtener o crear Factura Fiscal México."""
	if doc.fm_factura_fiscal_mx:
		return frappe.get_doc("Factura Fiscal Mexico", doc.fm_factura_fiscal_mx)

	# Crear nueva factura fiscal
	factura_fiscal = frappe.new_doc("Factura Fiscal Mexico")
	factura_fiscal.sales_invoice = doc.name
	factura_fiscal.customer = doc.customer
	factura_fiscal.total_amount = doc.grand_total
	factura_fiscal.currency = doc.currency
	factura_fiscal.fm_fiscal_status = "draft"
	factura_fiscal.save()

	# Actualizar referencia en Sales Invoice
	frappe.db.set_value("Sales Invoice", doc.name, "fm_factura_fiscal_mx", factura_fiscal.name)

	return factura_fiscal


def _should_auto_timbrar(doc):
	"""Determinar si se debe auto-timbrar - Estrategia Híbrida."""
	settings = frappe.get_single("Facturacion Mexico Settings")

	# Solo si está habilitado auto-timbrado
	if not settings.auto_generate_ereceipts:
		return False

	# Solo si hay datos fiscales completos
	if not doc.fm_cfdi_use:
		return False

	# Solo si el cliente tiene RFC (tax_id o fm_rfc)
	customer = frappe.get_doc("Customer", doc.customer)
	has_rfc = bool(customer.get('tax_id')) or bool(customer.get('fm_rfc'))
	if not has_rfc:
		return False

	return True


def _auto_timbrar_factura(doc):
	"""Auto-timbrar factura si está configurado."""
	try:
		from facturacion_mexico.facturacion_fiscal.timbrado_api import TimbradoAPI

		# Crear instancia de API
		_api = TimbradoAPI()

		# Timbrar en background job para no bloquear el submit
		frappe.enqueue(
			method="facturacion_mexico.facturacion_fiscal.timbrado_api.timbrar_factura",
			queue="default",
			timeout=300,
			sales_invoice_name=doc.name,
		)

		frappe.msgprint(_("La factura se está timbrando automáticamente"))

	except Exception as e:
		frappe.logger().error(f"Error auto-timbrando factura {doc.name}: {e!s}")
		# No lanzar error para no bloquear el submit
		frappe.msgprint(_("Error al auto-timbrar:") + str(e))
