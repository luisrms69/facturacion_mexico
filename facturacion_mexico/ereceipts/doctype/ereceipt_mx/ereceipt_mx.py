"""
EReceipt MX - DocType para recibos electrónicos con autofacturación
Sprint 2 - Sistema de Facturación México
"""

import calendar
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.model.document import Document


class EReceiptMX(Document):
	def before_save(self):
		"""Procesar antes de guardar."""
		self.calculate_expiry_date()
		self.calculate_days_to_expire()
		self.set_customer_info()
		self.set_creation_metadata()

	def calculate_expiry_date(self):
		"""Calcular fecha de vencimiento según configuración."""
		if self.expiry_date:
			return  # Ya está establecida manualmente

		if self.expiry_type == "Fixed Days":
			days = self.expiry_days or self.get_default_expiry_days()
			self.expiry_date = frappe.utils.add_days(self.date_issued, days)

		elif self.expiry_type == "End of Month":
			# Último día del mes actual
			date_obj = frappe.utils.getdate(self.date_issued)
			year = date_obj.year
			month = date_obj.month
			last_day = calendar.monthrange(year, month)[1]
			self.expiry_date = datetime(year, month, last_day).date()

		elif self.expiry_type == "Custom Date":
			# Se debe proporcionar expiry_date manualmente
			if not self.expiry_date:
				frappe.throw(_("Debe especificar la fecha de vencimiento para tipo 'Custom Date'"))

	def calculate_days_to_expire(self):
		"""Calcular días restantes para vencer."""
		if self.expiry_date:
			today = frappe.utils.today()
			days_diff = frappe.utils.date_diff(self.expiry_date, today)
			self.days_to_expire = max(0, days_diff)

	def set_customer_info(self):
		"""Establecer información del customer desde Sales Invoice."""
		if self.sales_invoice and not self.customer:
			invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)
			self.customer = invoice.customer
			self.customer_name = invoice.customer_name

	def set_creation_metadata(self):
		"""Establecer metadata de creación."""
		if not self.created_by_user:
			self.created_by_user = frappe.session.user

	def get_default_expiry_days(self):
		"""Obtener días de vencimiento por defecto."""
		settings = frappe.get_single("Facturacion Mexico Settings")
		return settings.get("default_expiry_days", 3)

	def validate(self):
		"""Validaciones del documento."""
		self.validate_sales_invoice()
		self.validate_expiry_configuration()
		self.validate_duplicate_ereceipt()

	def validate_sales_invoice(self):
		"""Validar Sales Invoice si está presente."""
		if self.sales_invoice:
			# Verificar que exista
			if not frappe.db.exists("Sales Invoice", self.sales_invoice):
				frappe.throw(_("Sales Invoice no existe: {0}").format(self.sales_invoice))

			# Verificar que no tenga factura fiscal
			invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)
			if invoice.get("factura_fiscal_mx"):
				frappe.throw(_("Esta Sales Invoice ya tiene factura fiscal asociada"))

	def validate_expiry_configuration(self):
		"""Validar configuración de vencimiento."""
		if self.expiry_type == "Fixed Days" and not self.expiry_days:
			self.expiry_days = self.get_default_expiry_days()

		if self.expiry_date and self.expiry_date < self.date_issued:
			frappe.throw(_("La fecha de vencimiento no puede ser anterior a la fecha de emisión"))

	def validate_duplicate_ereceipt(self):
		"""Validar que no exista E-Receipt duplicado."""
		if self.sales_invoice:
			existing = frappe.db.get_value(
				"EReceipt MX", {"sales_invoice": self.sales_invoice, "name": ["!=", self.name or ""]}
			)

			if existing:
				frappe.throw(_("Ya existe un E-Receipt para esta Sales Invoice: {0}").format(existing))

	def after_insert(self):
		"""Procesar después de insertar."""
		if frappe.db.get_single_value("Facturacion Mexico Settings", "enable_ereceipts"):
			self.generate_facturapi_ereceipt()

	def generate_facturapi_ereceipt(self):
		"""Generar E-Receipt en FacturAPI."""
		try:
			from facturacion_mexico.ereceipts.api import _generar_facturapi_ereceipt

			_generar_facturapi_ereceipt(self)

		except Exception as e:
			frappe.log_error(message=str(e), title=f"Error generando E-Receipt en FacturAPI: {self.name}")
			# No fallar la creación del documento por error de API externa

	def check_expiry_status(self):
		"""Verificar y actualizar status de vencimiento."""
		if self.status == "open" and self.is_expired():
			self.status = "expired"
			self.last_status_check = frappe.utils.now()
			self.save()
			return True
		return False

	def is_expired(self):
		"""Verificar si el E-Receipt ha expirado."""
		if not self.expiry_date:
			return False
		return frappe.utils.getdate(self.expiry_date) < frappe.utils.today()

	def mark_as_invoiced(self, factura_fiscal_name):
		"""Marcar como facturado."""
		self.status = "invoiced"
		self.invoiced = 1
		self.related_factura_fiscal = factura_fiscal_name
		self.last_status_check = frappe.utils.now()
		self.save()

	def mark_as_global_invoice(self, global_invoice_date):
		"""Marcar como incluido en factura global."""
		self.included_in_global = 1
		self.global_invoice_date = global_invoice_date
		self.status = "invoiced"
		self.last_status_check = frappe.utils.now()
		self.save()

	def cancel_ereceipt(self, reason=""):
		"""Cancelar E-Receipt."""
		if self.status in ["invoiced", "expired"]:
			frappe.throw(_("No se puede cancelar un E-Receipt que ya está {0}").format(self.status))

		# Cancelar en FacturAPI si existe
		if self.facturapi_id:
			try:
				from facturacion_mexico.facturacion_fiscal.api_client import FacturapiClient

				client = FacturapiClient()
				client.cancel_receipt(self.facturapi_id, reason)
			except Exception as e:
				frappe.log_error(
					message=str(e), title=f"Error cancelando E-Receipt en FacturAPI: {self.name}"
				)

		self.status = "cancelled"
		self.last_status_check = frappe.utils.now()
		if reason:
			self.notes = f"Cancelado: {reason}"
		self.save()

	@staticmethod
	def create_from_sales_invoice(sales_invoice_name, expiry_type=None, expiry_days=None):
		"""Crear E-Receipt desde Sales Invoice."""
		try:
			# Validar que no exista E-Receipt previo
			existing = frappe.db.exists("EReceipt MX", {"sales_invoice": sales_invoice_name})
			if existing:
				frappe.throw(_("Ya existe un E-Receipt para esta factura: {0}").format(existing))

			sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)

			# Validar que no tenga factura fiscal
			if sales_invoice.get("factura_fiscal_mx"):
				frappe.throw(_("Esta factura ya tiene factura fiscal asociada"))

			# Crear E-Receipt
			ereceipt = frappe.new_doc("EReceipt MX")
			ereceipt.sales_invoice = sales_invoice_name
			ereceipt.company = sales_invoice.company
			ereceipt.customer = sales_invoice.customer
			ereceipt.customer_name = sales_invoice.customer_name
			ereceipt.total = sales_invoice.grand_total
			ereceipt.date_issued = frappe.utils.today()
			ereceipt.creation_method = "API"

			# Configurar vencimiento
			if expiry_type:
				ereceipt.expiry_type = expiry_type
			if expiry_days:
				ereceipt.expiry_days = expiry_days

			ereceipt.insert()
			ereceipt.submit()

			return ereceipt.name

		except Exception as e:
			frappe.log_error(message=str(e), title="Error creando E-Receipt desde Sales Invoice")
			raise


@frappe.whitelist()
def bulk_expire_ereceipts():
	"""Marcar E-Receipts expirados en lote (scheduler)."""
	try:
		today = frappe.utils.today()

		# Obtener E-Receipts expirados
		expired_receipts = frappe.db.get_list(
			"EReceipt MX", filters={"status": "open", "expiry_date": ["<", today]}, pluck="name"
		)

		count = 0
		for receipt_name in expired_receipts:
			try:
				receipt = frappe.get_doc("EReceipt MX", receipt_name)
				receipt.status = "expired"
				receipt.last_status_check = frappe.utils.now()
				receipt.save()
				count += 1
			except Exception as e:
				frappe.log_error(message=str(e), title=f"Error expirando E-Receipt: {receipt_name}")

		frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to persist bulk expiry status updates for scheduled operation

		return {
			"success": True,
			"expired_count": count,
			"message": _("E-Receipts expirados procesados: {0}").format(count),
		}

	except Exception as e:
		frappe.log_error(message=str(e), title="Error en bulk expire E-Receipts")
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_ereceipts_for_period(date_from, date_to, company=None, customer=None):
	"""Obtener E-Receipts para un período."""
	try:
		filters = {"date_issued": ["between", [date_from, date_to]]}

		if company:
			filters["company"] = company
		if customer:
			filters["customer"] = customer

		ereceipts = frappe.db.get_list(
			"EReceipt MX",
			filters=filters,
			fields=[
				"name",
				"sales_invoice",
				"customer",
				"customer_name",
				"total",
				"date_issued",
				"expiry_date",
				"status",
				"key",
				"self_invoice_url",
			],
			order_by="date_issued DESC",
		)

		return {"success": True, "ereceipts": ereceipts, "count": len(ereceipts)}

	except Exception as e:
		frappe.log_error(message=str(e), title="Error obteniendo E-Receipts por período")
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_expiring_ereceipts(days_ahead=3):
	"""Obtener E-Receipts que vencen pronto."""
	try:
		future_date = frappe.utils.add_days(frappe.utils.today(), days_ahead)

		expiring_receipts = frappe.db.get_list(
			"EReceipt MX",
			filters={"status": "open", "expiry_date": ["between", [frappe.utils.today(), future_date]]},
			fields=[
				"name",
				"sales_invoice",
				"customer_name",
				"total",
				"expiry_date",
				"days_to_expire",
				"self_invoice_url",
			],
			order_by="expiry_date ASC",
		)

		return {"success": True, "expiring_receipts": expiring_receipts, "count": len(expiring_receipts)}

	except Exception as e:
		frappe.log_error(message=str(e), title="Error obteniendo E-Receipts próximos a vencer")
		return {"success": False, "message": str(e)}
