import frappe
from frappe import _
from frappe.model.document import Document

from facturacion_mexico.cfdi_recibidos.services.item_validator import validate_expense_item


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
