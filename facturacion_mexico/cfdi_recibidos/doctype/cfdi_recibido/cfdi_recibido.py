import frappe
from frappe import _
from frappe.model.document import Document

from facturacion_mexico.cfdi_recibidos.services.item_validator import validate_expense_item
from facturacion_mexico.cfdi_recibidos.services.status_manager import compute_stage

_TERMINAL_STAGES = frozenset(
	["XML inválido", "No aplicable", "No procesar", "Convertido a PI", "Error conversión"]
)


class CFDIRecibido(Document):
	def validate(self):
		for concepto in self.conceptos or []:
			if not concepto.item_code:
				continue
			ok, reason = validate_expense_item(concepto.item_code)
			if not ok:
				frappe.throw(
					_("Concepto '{0}': {1}").format(concepto.item_code, reason),
					frappe.ValidationError,
				)
			concepto.item_group = frappe.db.get_value("Item", concepto.item_code, "item_group")
		if self.status not in _TERMINAL_STAGES:
			self.status = compute_stage(self)
