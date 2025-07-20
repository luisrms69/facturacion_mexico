"""
Payment Entry Validate Hook Handler - Sprint 2
Sistema de Complementos de Pago México
"""

import frappe
from frappe import _


def check_ppd_requirement(doc, method):
	"""
	Hook handler para validar requerimientos de PPD en Payment Entry.

	Valida si el payment entry requiere generar complemento de pago
	según las reglas de CFDI 4.0 para pagos en parcialidades diferido (PPD).

	Args:
		doc: Payment Entry document
		method: Hook method name ('validate')
	"""
	try:
		# Solo procesar si es pago de cliente
		if doc.party_type != "Customer" or doc.payment_type != "Receive":
			return

		# Verificar que tenga referencias de facturas
		if not doc.references:
			return

		# Procesar cada referencia de factura
		for reference in doc.references:
			if reference.reference_doctype == "Sales Invoice":
				_validate_sales_invoice_ppd_requirement(doc, reference)

	except Exception as e:
		frappe.log_error(
			message=f"Error en check_ppd_requirement: {e!s}", title="Payment Entry Validate Hook Error"
		)
		# No lanzar error para no bloquear el flujo principal
		frappe.msgprint(_("Advertencia: No se pudo validar requerimientos PPD para este pago"), alert=True)


def _validate_sales_invoice_ppd_requirement(payment_doc, reference):
	"""
	Validar si una Sales Invoice requiere complemento PPD.

	Args:
		payment_doc: Payment Entry document
		reference: Reference row con Sales Invoice
	"""
	try:
		# Obtener la Sales Invoice
		sales_invoice = frappe.get_doc("Sales Invoice", reference.reference_name)

		# Verificar si la factura tiene forma de pago PPD
		forma_pago = sales_invoice.get("fm_forma_pago")
		if not forma_pago or forma_pago != "99":  # 99 = Por definir (PPD)
			return

		# Verificar que sea factura con CFDI
		if not sales_invoice.get("fm_uso_cfdi") or sales_invoice.get("fiscal_status") != "Timbrada":
			return

		# Validar que el monto del pago no exceda el saldo de la factura
		invoice_balance = _get_invoice_remaining_balance(reference.reference_name)
		if reference.allocated_amount > invoice_balance:
			frappe.throw(
				_("El monto asignado ({0}) excede el saldo pendiente ({1}) de la factura {2}").format(
					frappe.format_value(reference.allocated_amount, {"fieldtype": "Currency"}),
					frappe.format_value(invoice_balance, {"fieldtype": "Currency"}),
					reference.reference_name,
				)
			)

		# Validar fecha del pago no sea anterior a la factura
		if payment_doc.posting_date < sales_invoice.posting_date:
			frappe.throw(
				_("La fecha del pago ({0}) no puede ser anterior a la fecha de la factura ({1})").format(
					frappe.format_value(payment_doc.posting_date, {"fieldtype": "Date"}),
					frappe.format_value(sales_invoice.posting_date, {"fieldtype": "Date"}),
				)
			)

		# Marcar que requiere complemento PPD
		if not hasattr(payment_doc, "_ppd_required"):
			payment_doc._ppd_required = []

		payment_doc._ppd_required.append(
			{
				"sales_invoice": reference.reference_name,
				"allocated_amount": reference.allocated_amount,
				"currency": sales_invoice.currency,
			}
		)

		# Mostrar mensaje informativo
		if not payment_doc.get("fm_generate_complement"):
			frappe.msgprint(
				_("Este pago genera complemento de pago PPD para la factura {0}").format(
					reference.reference_name
				),
				alert=True,
				indicator="blue",
			)

	except frappe.DoesNotExistError:
		frappe.log_error(
			message=f"Sales Invoice {reference.reference_name} no encontrada",
			title="Payment Entry Validate - Invoice Not Found",
		)
	except Exception as e:
		frappe.log_error(
			message=f"Error validando PPD para {reference.reference_name}: {e!s}",
			title="Payment Entry Validate - PPD Validation Error",
		)
		raise


def _get_invoice_remaining_balance(sales_invoice_name):
	"""
	Obtener saldo pendiente de una factura.

	Args:
		sales_invoice_name: Nombre de la Sales Invoice

	Returns:
		float: Saldo pendiente de la factura
	"""
	try:
		# Obtener total de la factura
		invoice_total = frappe.get_value("Sales Invoice", sales_invoice_name, "grand_total")

		# Obtener total pagado desde Payment Tracking
		paid_amount = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(pt.amount_paid), 0) as total_paid
			FROM `tabPayment Tracking MX` pt
			WHERE pt.sales_invoice = %s
			AND pt.docstatus = 1
		""",
			(sales_invoice_name,),
		)[0][0]

		return invoice_total - (paid_amount or 0)

	except Exception as e:
		frappe.log_error(
			message=f"Error calculando saldo de factura {sales_invoice_name}: {e!s}",
			title="Payment Entry - Balance Calculation Error",
		)
		return 0


def validate_payment_method_compatibility(doc, method):
	"""
	Validar compatibilidad del método de pago con CFDI 4.0.

	Args:
		doc: Payment Entry document
		method: Hook method name
	"""
	try:
		if doc.party_type != "Customer":
			return

		# Verificar si el modo de pago es compatible con CFDI
		if doc.mode_of_payment:
			payment_method = frappe.get_doc("Mode of Payment", doc.mode_of_payment)

			# Validar que tenga configuración de forma de pago SAT
			sat_forma_pago = payment_method.get("custom_sat_forma_pago")
			if not sat_forma_pago:
				frappe.msgprint(
					_("Advertencia: El modo de pago '{0}' no tiene configurada la forma de pago SAT").format(
						doc.mode_of_payment
					),
					alert=True,
					indicator="orange",
				)
				return

			# Validar formas de pago que requieren información adicional
			if sat_forma_pago in ["02", "03", "04", "05"]:  # Cheque, transferencia, tarjeta, etc.
				_validate_additional_payment_info(doc, sat_forma_pago)

	except Exception as e:
		frappe.log_error(
			message=f"Error validando método de pago: {e!s}",
			title="Payment Entry - Payment Method Validation Error",
		)


def _validate_additional_payment_info(payment_doc, sat_forma_pago):
	"""
	Validar información adicional requerida según forma de pago SAT.

	Args:
		payment_doc: Payment Entry document
		sat_forma_pago: Código SAT de forma de pago
	"""
	warnings = []

	# Validaciones específicas por forma de pago
	if sat_forma_pago == "02":  # Cheque nominativo
		if not payment_doc.get("reference_no"):
			warnings.append("Número de cheque (Reference No) requerido")

	elif sat_forma_pago in ["03", "04"]:  # Transferencia o tarjeta
		if not payment_doc.get("reference_no"):
			warnings.append("Número de autorización/referencia requerido")

	elif sat_forma_pago == "05":  # Monedero electrónico
		if not payment_doc.get("reference_no"):
			warnings.append("Número de autorización del monedero requerido")

	# Mostrar advertencias si las hay
	if warnings:
		frappe.msgprint(
			_("Información adicional recomendada para complemento de pago:<br>{0}").format(
				"<br>".join([f"• {w}" for w in warnings])
			),
			alert=True,
			indicator="orange",
		)


def validate_multi_currency_payment(doc, method):
	"""
	Validar pagos en múltiples monedas para complementos de pago.

	Args:
		doc: Payment Entry document
		method: Hook method name
	"""
	try:
		if not doc.references or doc.party_type != "Customer":
			return

		# Verificar si hay facturas en diferentes monedas
		currencies = set()
		for reference in doc.references:
			if reference.reference_doctype == "Sales Invoice":
				invoice_currency = frappe.get_value("Sales Invoice", reference.reference_name, "currency")
				currencies.add(invoice_currency)

		# Si hay múltiples monedas, validar tipo de cambio
		if len(currencies) > 1:
			if not doc.get("exchange_rate") or doc.exchange_rate == 1:
				frappe.msgprint(
					_("Advertencia: Pago con múltiples monedas requiere tipo de cambio específico"),
					alert=True,
					indicator="orange",
				)

	except Exception as e:
		frappe.log_error(
			message=f"Error validando multi-moneda: {e!s}",
			title="Payment Entry - Multi Currency Validation Error",
		)
