"""
Payment Entry Submit Hook Handler - Sprint 2
Sistema de Complementos de Pago México - Generación automática de complementos
"""

import frappe
from frappe import _


def create_complement_if_required(doc, method):
	"""
	Hook handler para crear complemento de pago automáticamente al enviar Payment Entry.

	Se ejecuta después de submit del Payment Entry y crea automáticamente
	los complementos de pago requeridos para facturas PPD.

	Args:
		doc: Payment Entry document
		method: Hook method name ('on_submit')
	"""
	try:
		# Solo procesar pagos de clientes
		if doc.party_type != "Customer" or doc.payment_type != "Receive":
			return

		# Verificar que tenga referencias de facturas
		if not doc.references:
			return

		# Crear tracking records y complementos según sea necesario
		complements_created = []

		for reference in doc.references:
			if reference.reference_doctype == "Sales Invoice":
				complement_name = _process_sales_invoice_payment(doc, reference)
				if complement_name:
					complements_created.append(complement_name)

		# Actualizar Payment Entry con los complementos creados
		if complements_created:
			_update_payment_entry_with_complements(doc, complements_created)

		# Notificar al usuario
		if complements_created:
			frappe.msgprint(
				_("Se crearon {0} complemento(s) de pago: {1}").format(
					len(complements_created), ", ".join(complements_created)
				),
				alert=True,
				indicator="green",
			)

	except Exception as e:
		frappe.log_error(
			message=f"Error en create_complement_if_required: {e!s}",
			title="Payment Entry Submit Hook Error",
		)
		# Log error pero no fallar el submit principal
		frappe.msgprint(
			_("Advertencia: Error al crear complemento de pago automático. Revisar logs."),
			alert=True,
			indicator="red",
		)


def _process_sales_invoice_payment(payment_doc, reference):
	"""
	Procesar pago de una factura específica y crear complemento si es necesario.

	Args:
		payment_doc: Payment Entry document
		reference: Reference row con Sales Invoice

	Returns:
		str: Nombre del complemento creado o None
	"""
	try:
		# Obtener la Sales Invoice
		sales_invoice = frappe.get_doc("Sales Invoice", reference.reference_name)

		# Verificar si requiere complemento PPD
		if not _requires_ppd_complement(sales_invoice):
			return None

		# Crear Payment Tracking record
		tracking_name = _create_payment_tracking_record(payment_doc, reference, sales_invoice)

		# Crear Complemento de Pago
		complement_name = _create_complemento_pago(payment_doc, reference, sales_invoice, tracking_name)

		return complement_name

	except Exception as e:
		frappe.log_error(
			message=f"Error procesando pago de factura {reference.reference_name}: {e!s}",
			title="Payment Entry Submit - Sales Invoice Processing Error",
		)
		raise


def _requires_ppd_complement(sales_invoice):
	"""
	Determinar si una factura requiere complemento PPD.

	Args:
		sales_invoice: Sales Invoice document

	Returns:
		bool: True si requiere complemento PPD
	"""
	# Verificar forma de pago PPD (99 = Por definir)
	if sales_invoice.get("fm_forma_pago") != "99":
		return False

	# Verificar que esté timbrada
	if sales_invoice.get("fiscal_status") != "Timbrada":
		return False

	# Verificar que tenga UUID fiscal
	if not sales_invoice.get("uuid_fiscal"):
		return False

	return True


def _create_payment_tracking_record(payment_doc, reference, sales_invoice):
	"""
	Crear registro de Payment Tracking MX.

	Args:
		payment_doc: Payment Entry document
		reference: Reference row
		sales_invoice: Sales Invoice document

	Returns:
		str: Nombre del tracking record creado
	"""
	try:
		from facturacion_mexico.complementos_pago.doctype.payment_tracking_mx.payment_tracking_mx import (
			PaymentTrackingMX,
		)

		tracking_name = PaymentTrackingMX.create_tracking_record(
			sales_invoice=reference.reference_name,
			payment_entry=payment_doc.name,
			amount_paid=reference.allocated_amount,
		)

		return tracking_name

	except Exception as e:
		frappe.log_error(
			message=f"Error creando Payment Tracking para {reference.reference_name}: {e!s}",
			title="Payment Entry Submit - Payment Tracking Creation Error",
		)
		raise


def _create_complemento_pago(payment_doc, reference, sales_invoice, tracking_name):
	"""
	Crear Complemento de Pago MX.

	Args:
		payment_doc: Payment Entry document
		reference: Reference row
		sales_invoice: Sales Invoice document
		tracking_name: Nombre del tracking record

	Returns:
		str: Nombre del complemento creado
	"""
	try:
		# Crear nuevo Complemento de Pago
		complement = frappe.new_doc("Complemento Pago MX")

		# Datos básicos
		complement.company = payment_doc.company
		complement.customer = payment_doc.party
		complement.payment_entry = payment_doc.name
		complement.payment_date = payment_doc.posting_date
		complement.currency = payment_doc.paid_to_account_currency
		complement.exchange_rate = payment_doc.get("exchange_rate", 1.0)

		# Información del pago
		complement.payment_amount = reference.allocated_amount
		complement.payment_method = _get_sat_payment_method(payment_doc)
		complement.payment_reference = payment_doc.get("reference_no", "")

		# Relacionar con la factura
		complement.append(
			"related_invoices",
			{
				"sales_invoice": reference.reference_name,
				"invoice_uuid": sales_invoice.get("uuid_fiscal"),
				"invoice_currency": sales_invoice.currency,
				"invoice_exchange_rate": sales_invoice.get("conversion_rate", 1.0),
				"previous_balance": _get_invoice_balance_before_payment(
					reference.reference_name, reference.allocated_amount
				),
				"paid_amount": reference.allocated_amount,
				"payment_number": _get_payment_number_for_invoice(reference.reference_name),
				"payment_tracking": tracking_name,
			},
		)

		# Información fiscal adicional
		complement.rfc_emisor = frappe.get_value("Company", payment_doc.company, "tax_id")
		complement.rfc_receptor = frappe.get_value("Customer", payment_doc.party, "tax_id")

		# Estado inicial
		complement.complement_status = "Pendiente"
		complement.requires_stamp = 1

		# Insertar y enviar
		complement.insert()
		complement.submit()

		return complement.name

	except Exception as e:
		frappe.log_error(
			message=f"Error creando Complemento de Pago: {e!s}",
			title="Payment Entry Submit - Complement Creation Error",
		)
		raise


def _get_sat_payment_method(payment_doc):
	"""
	Obtener método de pago SAT desde el Mode of Payment.

	Args:
		payment_doc: Payment Entry document

	Returns:
		str: Código SAT del método de pago
	"""
	try:
		if not payment_doc.mode_of_payment:
			return "99"  # Por definir

		sat_method = frappe.get_value("Mode of Payment", payment_doc.mode_of_payment, "custom_sat_forma_pago")

		return sat_method or "99"

	except Exception:
		return "99"


def _get_invoice_balance_before_payment(sales_invoice_name, payment_amount):
	"""
	Obtener saldo de la factura antes del pago actual.

	Args:
		sales_invoice_name: Nombre de la Sales Invoice
		payment_amount: Monto del pago actual

	Returns:
		float: Saldo antes del pago
	"""
	try:
		# Obtener total de la factura
		invoice_total = frappe.get_value("Sales Invoice", sales_invoice_name, "grand_total")

		# Obtener total pagado previamente (excluyendo el pago actual)
		previous_paid = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(pt.amount_paid), 0) as total_paid
			FROM `tabPayment Tracking MX` pt
			WHERE pt.sales_invoice = %s
			AND pt.docstatus = 1
		""",
			(sales_invoice_name,),
		)[0][0]

		return invoice_total - (previous_paid or 0)

	except Exception as e:
		frappe.log_error(
			message=f"Error calculando saldo previo para {sales_invoice_name}: {e!s}",
			title="Payment Entry Submit - Balance Calculation Error",
		)
		return 0


def _get_payment_number_for_invoice(sales_invoice_name):
	"""
	Obtener número de parcialidad para la factura.

	Args:
		sales_invoice_name: Nombre de la Sales Invoice

	Returns:
		int: Número de parcialidad
	"""
	try:
		from facturacion_mexico.complementos_pago.doctype.payment_tracking_mx.payment_tracking_mx import (
			get_next_parcialidad_number,
		)

		return get_next_parcialidad_number(sales_invoice_name)

	except Exception:
		return 1


def _update_payment_entry_with_complements(payment_doc, complements_created):
	"""
	Actualizar Payment Entry con los complementos creados.

	Args:
		payment_doc: Payment Entry document
		complements_created: Lista de nombres de complementos
	"""
	try:
		# Actualizar campo personalizado si existe
		complement_names = ", ".join(complements_created)

		frappe.db.set_value("Payment Entry", payment_doc.name, "fm_complementos_generated", complement_names)

		frappe.db.commit()

	except Exception as e:
		frappe.log_error(
			message=f"Error actualizando Payment Entry con complementos: {e!s}",
			title="Payment Entry Submit - Update Error",
		)


def auto_stamp_complements(doc, method):
	"""
	Hook para timbrar automáticamente complementos de pago si está configurado.

	Args:
		doc: Payment Entry document
		method: Hook method name
	"""
	try:
		# Verificar configuración de timbrado automático
		auto_stamp = frappe.db.get_single_value("Facturacion Mexico Settings", "auto_stamp_complements")

		if not auto_stamp:
			return

		# Obtener complementos relacionados con este pago
		complements = frappe.get_all(
			"Complemento Pago MX",
			filters={"payment_entry": doc.name, "complement_status": "Pendiente", "docstatus": 1},
			pluck="name",
		)

		# Timbrar cada complemento
		for complement_name in complements:
			_auto_stamp_complement(complement_name)

	except Exception as e:
		frappe.log_error(
			message=f"Error en auto_stamp_complements: {e!s}",
			title="Payment Entry Submit - Auto Stamp Error",
		)


def _auto_stamp_complement(complement_name):
	"""
	Timbrar un complemento de pago automáticamente.

	Args:
		complement_name: Nombre del complemento a timbrar
	"""
	try:
		complement = frappe.get_doc("Complemento Pago MX", complement_name)

		# Llamar al método de timbrado
		if hasattr(complement, "stamp_complement"):
			complement.stamp_complement()

		frappe.msgprint(
			_("Complemento {0} timbrado automáticamente").format(complement_name),
			alert=True,
			indicator="green",
		)

	except Exception as e:
		frappe.log_error(
			message=f"Error timbrar complemento {complement_name}: {e!s}",
			title="Auto Stamp Complement Error",
		)
		frappe.msgprint(
			_("Error al timbrar automáticamente complemento {0}").format(complement_name),
			alert=True,
			indicator="orange",
		)
