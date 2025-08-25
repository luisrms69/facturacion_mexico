import frappe
from frappe import _

from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
	FacturaFiscalMexico as FFMBase,
)

# Set de estados equivalentes a "fiscalmente cancelado"
CANCELADO_FISCAL = {"CANCELADO", "CANCELADA", "CANCELED", "CANCELLED", "CANCELLED_OK"}


class FacturaFiscalMexico(FFMBase):
	"""Override class para Factura Fiscal Mexico - Manejo LinkExistsError múltiples FFMs"""

	def cancel(self):
		"""Override cancel para evitar LinkExistsError cuando FFM fiscalmente cancelada"""
		# Guard: Solo permitir cancelar en Frappe si el estado fiscal ya es "cancelado" (PAC)
		status = (self.get("fm_fiscal_status") or "").strip().upper()
		if status not in CANCELADO_FISCAL:
			frappe.throw(
				_(
					"No puedes cancelar esta Factura Fiscal en Frappe: estado fiscal '{0}'. "
					"Primero cancela en el PAC."
				).format(status or "SIN_ESTADO")
			)

		# Clave: Evitar LinkExistsError cuando hay enlace a Sales Invoice (cancel_all_linked_docs)
		self.flags.ignore_links = True

		# Auditoría automática para trazabilidad
		if hasattr(self, "sales_invoice") and self.sales_invoice:
			self.add_comment(
				"Info",
				_(
					"FFM cancelada en Frappe tras cancelación fiscal PAC (estado: {0}, workflow múltiples FFMs)."
				).format(status),
			)

		# Logging para debugging
		frappe.logger("facturacion_mexico").info(
			{
				"event": "ffm_override_cancel",
				"ffm": self.name,
				"fiscal_status": status,
				"sales_invoice": getattr(self, "sales_invoice", None),
			}
		)

		# Proceder con cancelación normal (sin tocar enlaces; auditoría intacta)
		return super().cancel()
