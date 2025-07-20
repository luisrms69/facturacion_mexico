"""
Payment Tracking MX - DocType para control de secuencia de pagos
Sprint 2 - Sistema de Facturación México
"""

import frappe
from frappe import _
from frappe.model.document import Document


class PaymentTrackingMX(Document):
	def before_save(self):
		"""Calcular saldo posterior y validaciones."""
		self.calculate_balance_after()
		self.validate_payment_sequence()
		self.set_validation_info()

	def calculate_balance_after(self):
		"""Calcular saldo posterior al pago."""
		self.balance_after = self.balance_before - self.amount_paid

	def validate_payment_sequence(self):
		"""Validar secuencia de pagos y detectar retroactivos."""
		if not self.sales_invoice or not self.payment_date:
			return

		# Buscar pagos posteriores en fecha
		posterior_payments = frappe.db.sql(
			"""
			SELECT name, payment_date, parcialidad_number
			FROM `tabPayment Tracking MX`
			WHERE sales_invoice = %s
			AND payment_date > %s
			AND name != %s
			ORDER BY payment_date ASC
		""",
			(self.sales_invoice, self.payment_date, self.name or ""),
			as_dict=True,
		)

		if posterior_payments:
			self.is_retroactive = 1
			self.sequence_warning = _(
				"ADVERTENCIA: Existen {0} pagos posteriores a esta fecha. "
				"Esto puede afectar la secuencia de parcialidades."
			).format(len(posterior_payments))
		else:
			self.is_retroactive = 0
			self.sequence_warning = ""

	def set_validation_info(self):
		"""Establecer información de validación."""
		if not self.validation_date:
			self.validation_date = frappe.utils.now()
		if not self.validated_by:
			self.validated_by = frappe.session.user

	def validate(self):
		"""Validaciones del documento."""
		self.validate_amounts()
		self.validate_parcialidad_sequence()
		self.validate_duplicate_parcialidad()

	def validate_amounts(self):
		"""Validar que los montos sean correctos."""
		if self.amount_paid <= 0:
			frappe.throw(_("El monto pagado debe ser mayor a cero"))

		if self.balance_before <= 0:
			frappe.throw(_("El saldo anterior debe ser mayor a cero"))

		if self.amount_paid > self.balance_before:
			frappe.throw(_("El monto pagado no puede ser mayor al saldo anterior"))

	def validate_parcialidad_sequence(self):
		"""Validar que el número de parcialidad sea secuencial."""
		if not self.parcialidad_number or self.parcialidad_number <= 0:
			frappe.throw(_("El número de parcialidad debe ser mayor a cero"))

		# Verificar que sea secuencial (permitir algunas excepciones para pagos retroactivos)
		max_parcialidad = frappe.db.sql(
			"""
			SELECT COALESCE(MAX(parcialidad_number), 0) as max_num
			FROM `tabPayment Tracking MX`
			WHERE sales_invoice = %s
			AND name != %s
		""",
			(self.sales_invoice, self.name or ""),
		)[0][0]

		if not self.is_retroactive and self.parcialidad_number != max_parcialidad + 1:
			frappe.throw(
				_("El número de parcialidad debe ser secuencial. Siguiente esperado: {0}").format(
					max_parcialidad + 1
				)
			)

	def validate_duplicate_parcialidad(self):
		"""Validar que no exista duplicado de parcialidad."""
		duplicate = frappe.db.sql(
			"""
			SELECT name
			FROM `tabPayment Tracking MX`
			WHERE sales_invoice = %s
			AND parcialidad_number = %s
			AND name != %s
		""",
			(self.sales_invoice, self.parcialidad_number, self.name or ""),
		)

		if duplicate:
			frappe.throw(
				_("Ya existe una parcialidad número {0} para esta factura").format(self.parcialidad_number)
			)

	@staticmethod
	def create_tracking_record(sales_invoice, payment_entry, amount_paid):
		"""Crear registro de tracking desde Payment Entry."""
		try:
			# Obtener saldo anterior
			balance_before = get_invoice_balance(sales_invoice)

			# Calcular número de parcialidad
			parcialidad_number = get_next_parcialidad_number(sales_invoice)

			# Crear registro
			tracking = frappe.new_doc("Payment Tracking MX")
			tracking.sales_invoice = sales_invoice
			tracking.payment_entry = payment_entry
			tracking.payment_date = frappe.get_value("Payment Entry", payment_entry, "posting_date")
			tracking.parcialidad_number = parcialidad_number
			tracking.amount_paid = amount_paid
			tracking.balance_before = balance_before

			tracking.insert()
			tracking.submit()

			return tracking.name

		except Exception as e:
			frappe.log_error(message=str(e), title="Error creando Payment Tracking")
			raise


def get_invoice_balance(sales_invoice_name):
	"""Obtener saldo actual de la factura."""
	try:
		# Obtener total de la factura
		invoice_total = frappe.get_value("Sales Invoice", sales_invoice_name, "grand_total")

		# Obtener total pagado
		paid_amount = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(amount_paid), 0) as total_paid
			FROM `tabPayment Tracking MX`
			WHERE sales_invoice = %s
			AND docstatus = 1
		""",
			(sales_invoice_name,),
		)[0][0]

		return invoice_total - paid_amount

	except Exception as e:
		frappe.log_error(message=str(e), title="Error calculando saldo de factura")
		return 0


def get_next_parcialidad_number(sales_invoice_name):
	"""Obtener siguiente número de parcialidad."""
	try:
		max_parcialidad = frappe.db.sql(
			"""
			SELECT COALESCE(MAX(parcialidad_number), 0) as max_num
			FROM `tabPayment Tracking MX`
			WHERE sales_invoice = %s
		""",
			(sales_invoice_name,),
		)[0][0]

		return max_parcialidad + 1

	except Exception as e:
		frappe.log_error(message=str(e), title="Error obteniendo número de parcialidad")
		return 1


@frappe.whitelist()
def get_payment_tracking_for_invoice(sales_invoice_name):
	"""Obtener historial de tracking para una factura."""
	try:
		tracking_records = frappe.db.get_list(
			"Payment Tracking MX",
			filters={"sales_invoice": sales_invoice_name},
			fields=[
				"name",
				"payment_date",
				"parcialidad_number",
				"amount_paid",
				"balance_before",
				"balance_after",
				"is_retroactive",
				"sequence_warning",
			],
			order_by="parcialidad_number ASC",
		)

		return {"success": True, "tracking_records": tracking_records, "count": len(tracking_records)}

	except Exception as e:
		frappe.log_error(message=str(e), title="Error obteniendo payment tracking")
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def validate_payment_sequence_for_invoice(sales_invoice_name):
	"""Validar secuencia completa de pagos para una factura."""
	try:
		tracking_records = frappe.db.get_list(
			"Payment Tracking MX",
			filters={"sales_invoice": sales_invoice_name, "docstatus": 1},
			fields=["parcialidad_number", "payment_date", "is_retroactive"],
			order_by="payment_date ASC",
		)

		issues = []
		expected_parcialidad = 1

		for record in tracking_records:
			if record.parcialidad_number != expected_parcialidad:
				issues.append(
					{
						"type": "sequence_gap",
						"message": _("Salto en secuencia: esperado {0}, encontrado {1}").format(
							expected_parcialidad, record.parcialidad_number
						),
						"parcialidad": record.parcialidad_number,
						"date": record.payment_date,
					}
				)

			if record.is_retroactive:
				issues.append(
					{
						"type": "retroactive_payment",
						"message": _("Pago retroactivo detectado en parcialidad {0}").format(
							record.parcialidad_number
						),
						"parcialidad": record.parcialidad_number,
						"date": record.payment_date,
					}
				)

			expected_parcialidad = record.parcialidad_number + 1

		return {
			"success": True,
			"is_valid": len(issues) == 0,
			"issues": issues,
			"total_records": len(tracking_records),
		}

	except Exception as e:
		frappe.log_error(message=str(e), title="Error validando secuencia de pagos")
		return {"success": False, "message": str(e)}
