"""
Factura Global Detail - Sprint 4 Semana 1
Child DocType para detalles de E-Receipts incluidos en factura global
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class FacturaGlobalDetail(Document):
	"""Factura Global Detail - Detalle de E-Receipts incluidos."""

	def validate(self):
		"""Validaciones del detalle."""
		if self.ereceipt:
			self.populate_receipt_data()

	def populate_receipt_data(self):
		"""Poblar datos del E-Receipt automáticamente."""
		if not self.ereceipt:
			return

		try:
			receipt_doc = frappe.get_doc("EReceipt MX", self.ereceipt)

			# Poblar campos con datos del receipt usando los campos reales
			self.folio_receipt = receipt_doc.name  # Use name as folio
			self.fecha_receipt = receipt_doc.get("date_issued")
			self.monto = flt(receipt_doc.get("total", 0))
			self.customer_name = receipt_doc.get("customer_name") or "Público General"

			# Por defecto se incluye en CFDI
			self.included_in_cfdi = 1

		except Exception as e:
			frappe.log_error(f"Error poblando datos del receipt {self.ereceipt}: {e}")
			frappe.throw(_("Error obteniendo datos del E-Receipt {0}: {1}").format(self.ereceipt, str(e)))

	def get_receipt_details(self):
		"""Obtener detalles completos del receipt."""
		if not self.ereceipt:
			return {}

		try:
			receipt_doc = frappe.get_doc("EReceipt MX", self.ereceipt)
			return {
				"name": receipt_doc.name,
				"folio": receipt_doc.get("folio"),
				"receipt_date": receipt_doc.get("receipt_date"),
				"total_amount": receipt_doc.get("total_amount"),
				"tax_amount": receipt_doc.get("tax_amount"),
				"customer_name": receipt_doc.get("customer_name"),
				"currency": receipt_doc.get("currency", "MXN"),
				"status": receipt_doc.get("status"),
				"facturapi_id": receipt_doc.get("facturapi_id"),
			}
		except Exception:
			return {}

	@staticmethod
	def create_from_receipt(ereceipt_name):
		"""Crear detalle desde nombre de E-Receipt."""
		detail = {"ereceipt": ereceipt_name}

		# Crear documento temporal para poblar datos
		temp_detail = frappe.get_doc({"doctype": "Factura Global Detail", **detail})
		temp_detail.populate_receipt_data()

		return {
			"ereceipt": temp_detail.ereceipt,
			"folio_receipt": temp_detail.folio_receipt,
			"fecha_receipt": temp_detail.fecha_receipt,
			"monto": temp_detail.monto,
			"customer_name": temp_detail.customer_name,
			"included_in_cfdi": temp_detail.included_in_cfdi,
		}
