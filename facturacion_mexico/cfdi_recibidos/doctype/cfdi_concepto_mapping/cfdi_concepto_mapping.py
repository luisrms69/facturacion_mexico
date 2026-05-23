from frappe import _
from frappe.model.document import Document


class CFDIConceptoMapping(Document):
	def validate(self):
		if self.target_type == "Item" and not self.target_item:
			from frappe import throw

			throw(_("El campo 'Item' es obligatorio cuando el tipo de destino es 'Item'"))
		if self.target_type == "ExpenseAccount" and not self.target_account:
			from frappe import throw

			throw(
				_("El campo 'Cuenta de Gasto' es obligatorio cuando el tipo de destino es 'ExpenseAccount'")
			)
