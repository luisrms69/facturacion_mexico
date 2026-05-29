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
		if not self.is_new() and not frappe.flags.get("in_cfdi_builder"):
			old_status = frappe.db.get_value("CFDI Recibido", self.name, "status")
			if old_status == "Convertido a PI":
				frappe.throw(
					_("CFDI Recibido en estado 'Convertido a PI' no puede modificarse."),
					frappe.ValidationError,
				)
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
