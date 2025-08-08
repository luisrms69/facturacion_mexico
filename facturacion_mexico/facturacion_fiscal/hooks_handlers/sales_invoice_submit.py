import frappe
from frappe import _
from frappe.utils import flt

from facturacion_mexico.config.fiscal_states_config import FiscalStates


def create_fiscal_event(doc, method):
	"""Crear evento fiscal cuando se envía Sales Invoice."""
	import frappe

	frappe.log_error(f"🚀 INICIO create_fiscal_event para {doc.name}", "TIMBRADO TRACE")

	# Solo para facturas con datos fiscales
	if not _should_create_fiscal_event(doc):
		frappe.log_error(f"❌ _should_create_fiscal_event = False para {doc.name}", "TIMBRADO TRACE")
		return

	frappe.log_error(f"✅ _should_create_fiscal_event = True para {doc.name}", "TIMBRADO TRACE")

	# Crear evento de emisión
	_create_emission_event(doc)
	frappe.log_error(f"📄 _create_emission_event completado para {doc.name}", "TIMBRADO TRACE")

	# NUEVO FLUJO: No auto-timbrar, usar botón manual
	frappe.log_error(
		f"✅ Evento fiscal creado para {doc.name}. Usar botón 'Timbrar Factura' para procesar.",
		"SUBMIT FISCAL",
	)


def _should_create_fiscal_event(doc):
	"""Determinar si se debe crear evento fiscal - Estrategia Híbrida."""
	# Solo para facturas enviadas
	if doc.docstatus != 1:
		return False

	# Solo si hay datos fiscales mínimos
	if not doc.customer:
		return False

	customer = frappe.get_doc("Customer", doc.customer)

	# Usar tax_id como único campo RFC
	has_rfc = bool(customer.get("tax_id"))
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

	# Crear evento con parametros correctos: (event_type, reference_doctype, reference_name, event_data, status)
	event_doc = FiscalEventMX.create_event(
		"create", "Factura Fiscal Mexico", factura_fiscal.name, event_data, "pending"
	)

	# Marcar como exitoso solo si el evento se creó correctamente
	if event_doc:
		FiscalEventMX.mark_event_success(event_doc.name, {"status": "emitted"})
	else:
		frappe.log_error(
			message=f"create_event retornó None para factura_fiscal {factura_fiscal.name}",
			title="Sales Invoice Fiscal Event Failed",
		)

	# Actualizar estado fiscal
	frappe.db.set_value("Sales Invoice", doc.name, "fm_fiscal_status", FiscalStates.BORRADOR)


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
	factura_fiscal.fm_fiscal_status = FiscalStates.BORRADOR

	# Agregar montos del Sales Invoice para validación posterior
	frappe.log_error(
		f"DEBUG: doc.net_total={doc.net_total}, doc.grand_total={doc.grand_total}", "MONTOS DEBUG"
	)
	factura_fiscal.si_total_antes_iva = flt(doc.net_total)
	factura_fiscal.si_total_neto = flt(doc.grand_total)

	# Calcular IVA y otros impuestos
	iva_total = 0
	otros_impuestos = 0

	if doc.get("taxes"):
		frappe.log_error(f"DEBUG: Taxes count={len(doc.taxes)}", "MONTOS DEBUG")
		for tax in doc.taxes:
			tax_amount = flt(tax.tax_amount)
			frappe.log_error(
				f"DEBUG: tax.account_head={tax.account_head}, tax_amount={tax_amount}", "MONTOS DEBUG"
			)
			# Identificar IVA por el account_head
			if tax.account_head and ("IVA" in tax.account_head.upper()):
				iva_total += tax_amount
			else:
				otros_impuestos += tax_amount

	factura_fiscal.si_iva = iva_total
	factura_fiscal.si_otros_impuestos = otros_impuestos
	frappe.log_error(
		f"DEBUG: Final values - si_total_antes_iva={factura_fiscal.si_total_antes_iva}, si_iva={factura_fiscal.si_iva}, si_total_neto={factura_fiscal.si_total_neto}",
		"MONTOS DEBUG",
	)

	factura_fiscal.save()

	# Actualizar referencia en Sales Invoice
	frappe.db.set_value("Sales Invoice", doc.name, "fm_factura_fiscal_mx", factura_fiscal.name)

	return factura_fiscal


def _should_auto_timbrar(doc):
	"""Determinar si se debe auto-timbrar facturas normales VS ereceipts."""
	import frappe

	frappe.log_error(f"🔍 EVALUANDO auto-timbrado para {doc.name}", "Auto-Timbrado Check")

	settings = frappe.get_single("Facturacion Mexico Settings")

	# LÓGICA CORRECTA: Si ereceipts está habilitado, NO timbrar (usar ereceipts)
	if settings.auto_generate_ereceipts:
		frappe.log_error(
			f"📱 EReceipts HABILITADO para {doc.name} - NO timbrar, usar ereceipts", "Auto-Timbrado Check"
		)
		return False

	frappe.log_error(
		f"📄 EReceipts DESHABILITADO para {doc.name} - Proceder con timbrado normal", "Auto-Timbrado Check"
	)

	# Solo si hay datos fiscales completos
	if not doc.fm_cfdi_use:
		frappe.log_error(f"❌ Sin fm_cfdi_use para {doc.name}", "Auto-Timbrado Check")
		return False

	# Solo si el cliente tiene RFC en tax_id
	customer = frappe.get_doc("Customer", doc.customer)
	has_rfc = bool(customer.get("tax_id"))
	if not has_rfc:
		frappe.log_error(
			f"❌ Cliente {doc.customer} sin RFC en tax_id: {customer.get('tax_id')}",
			"Auto-Timbrado Check",
		)
		return False

	frappe.log_error(f"✅ TIMBRADO NORMAL APROBADO para {doc.name}", "Auto-Timbrado Check")
	return True


def _auto_timbrar_factura(doc):
	"""Auto-timbrar factura si está configurado."""
	import frappe

	frappe.log_error(f"🎯 EJECUTANDO _auto_timbrar_factura para {doc.name}", "TIMBRADO TRACE")

	try:
		from facturacion_mexico.facturacion_fiscal.timbrado_api import TimbradoAPI

		frappe.log_error(f"📦 TimbradoAPI importado para {doc.name}", "TIMBRADO TRACE")

		# Crear instancia de API
		_api = TimbradoAPI()
		frappe.log_error(f"🔧 TimbradoAPI instanciado para {doc.name}", "TIMBRADO TRACE")

		# Timbrar en background job para no bloquear el submit
		frappe.log_error(f"⏳ ENQUEUE timbrado para {doc.name}", "TIMBRADO TRACE")
		frappe.enqueue(
			method="facturacion_mexico.facturacion_fiscal.timbrado_api.timbrar_factura",
			queue="default",
			timeout=300,
			sales_invoice_name=doc.name,
		)

		frappe.log_error(f"✅ ENQUEUE exitoso para {doc.name}", "TIMBRADO TRACE")
		frappe.msgprint(_("La factura se está timbrando automáticamente"))

	except Exception as e:
		frappe.log_error(f"💥 ERROR en _auto_timbrar_factura para {doc.name}: {e!s}", "TIMBRADO TRACE")
		frappe.logger().error(f"Error auto-timbrando factura {doc.name}: {e!s}")
		# No lanzar error para no bloquear el submit
		frappe.msgprint(_("Error al auto-timbrar:") + str(e))
