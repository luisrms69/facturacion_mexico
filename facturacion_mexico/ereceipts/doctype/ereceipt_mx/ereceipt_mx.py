"""
EReceipt MX — espejo local del receipt en FacturAPI.
No es motor fiscal: FacturAPI hace el timbrado, autofactura y factura global.
ERPNext solo mantiene trazabilidad, control y sincronización.
"""

import calendar
from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document


class EReceiptMX(Document):
	def before_save(self):
		self.calculate_expiry_date()
		self.calculate_days_to_expire()
		self.set_customer_info()

	def calculate_expiry_date(self):
		if self.expiry_date:
			return

		if self.expiry_type == "Fixed Days":
			days = self.expiry_days or self.get_default_expiry_days()
			self.expiry_date = frappe.utils.add_days(self.date_issued, days)

		elif self.expiry_type == "End of Month":
			date_obj = frappe.utils.getdate(self.date_issued)
			year = date_obj.year
			month = date_obj.month
			last_day = calendar.monthrange(year, month)[1]
			self.expiry_date = datetime(year, month, last_day).date()

		elif self.expiry_type == "Custom Date":
			if not self.expiry_date:
				self.expiry_date = frappe.utils.add_days(self.date_issued, 3)

	def calculate_days_to_expire(self):
		if self.expiry_date:
			today = frappe.utils.today()
			days_diff = frappe.utils.date_diff(self.expiry_date, today)
			self.days_to_expire = max(0, days_diff)

	def set_customer_info(self):
		if self.sales_invoice and not self.customer:
			invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)
			self.customer = invoice.customer
			self.customer_name = invoice.customer_name

	def get_default_expiry_days(self):
		company = self.company or frappe.defaults.get_global_default("company")
		days = frappe.db.get_value(
			"Facturacion Mexico Company Settings",
			{"company": company},
			"ereceipt_expiry_days_default",
		)
		return days or 3

	def validate(self):
		self.validate_sales_invoice()
		self.validate_expiry_configuration()
		self.validate_duplicate_ereceipt()

	def validate_sales_invoice(self):
		if self.sales_invoice:
			if not frappe.db.exists("Sales Invoice", self.sales_invoice):
				frappe.throw(_("Sales Invoice no existe: {0}").format(self.sales_invoice))

			invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)
			if invoice.get("fm_factura_fiscal_mx"):
				frappe.throw(_("Esta Sales Invoice ya tiene factura fiscal asociada"))

	def validate_expiry_configuration(self):
		if self.expiry_type == "Fixed Days" and not self.expiry_days:
			self.expiry_days = self.get_default_expiry_days()

		if self.expiry_date and self.expiry_date < self.date_issued:
			frappe.throw(_("La fecha de vencimiento no puede ser anterior a la fecha de emisión"))

	def validate_duplicate_ereceipt(self):
		if self.sales_invoice:
			existing = frappe.db.get_value(
				"EReceipt MX", {"sales_invoice": self.sales_invoice, "name": ["!=", self.name or ""]}
			)
			if existing:
				frappe.throw(_("Ya existe un E-Receipt para esta Sales Invoice: {0}").format(existing))

	def after_insert(self):
		self.generate_facturapi_ereceipt()

	def generate_facturapi_ereceipt(self):
		try:
			from facturacion_mexico.ereceipts.api import _generar_facturapi_ereceipt

			_generar_facturapi_ereceipt(self)

		except Exception as e:
			frappe.log_error(message=str(e), title=f"Error generando E-Receipt en FacturAPI: {self.name}")

	def is_expired(self):
		if not self.expiry_date:
			return False
		expiry_date = frappe.utils.getdate(self.expiry_date)
		today = frappe.utils.getdate(frappe.utils.today())
		return expiry_date <= today

	def cancel_ereceipt(self, reason=""):
		"""Cancelar E-Receipt en FacturAPI y localmente."""
		if self.status in ["invoiced_to_customer", "invoiced_globally"]:
			frappe.throw(
				_("No se puede cancelar un E-Receipt que ya fue facturado ({0})").format(self.status)
			)

		if self.facturapi_id:
			try:
				from facturacion_mexico.facturacion_fiscal.api_client import get_facturapi_client

				client = get_facturapi_client(company=self.company)
				client.cancel_receipt(self.facturapi_id)
			except Exception as e:
				frappe.log_error(
					message=str(e), title=f"Error cancelando E-Receipt en FacturAPI: {self.name}"
				)

		self.status = "cancelled"
		if reason:
			self.notes = (self.notes or "") + f"\nCancelado: {reason}"
		self.save()


@frappe.whitelist()
def bulk_expire_ereceipts():
	"""Marcar E-Receipts expirados en lote (scheduler)."""
	try:
		today = frappe.utils.today()
		expired_receipts = frappe.db.get_list(
			"EReceipt MX", filters={"status": "open", "expiry_date": ["<", today]}, pluck="name"
		)

		count = 0
		for receipt_name in expired_receipts:
			try:
				receipt = frappe.get_doc("EReceipt MX", receipt_name)
				receipt.status = "expired"
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
def get_ereceipts_for_period(
	date_from: str | None = None,
	date_to: str | None = None,
	company: str | None = None,
	customer: str | None = None,
):
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
				"invoice_uuid",
				"factura_global_mx",
			],
			order_by="date_issued DESC",
		)

		return {"success": True, "ereceipts": ereceipts, "count": len(ereceipts)}

	except Exception as e:
		frappe.log_error(message=str(e), title="Error obteniendo E-Receipts por período")
		return {"success": False, "message": str(e)}
