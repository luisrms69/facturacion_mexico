import frappe
from frappe import _
from frappe.model.document import Document


class CFDIRecibido(Document):
	def validate(self):
		for concepto in self.conceptos or []:
			if concepto.item_code and concepto.item_group:
				item_group_item = frappe.db.get_value("Item", concepto.item_code, "item_group")
				if item_group_item and concepto.item_group != item_group_item:
					frappe.throw(
						_("El Item {0} pertenece al grupo '{1}', no a '{2}'.").format(
							concepto.item_code, item_group_item, concepto.item_group
						)
					)
