import frappe
from frappe import _
from frappe.model.document import Document


class CFDIConceptoMapping(Document):
	def validate(self):
		self._validate_no_duplicado()
		self._validate_target()

	def _validate_no_duplicado(self):
		company_filter = self.company or ["in", ["", None]]
		duplicate = frappe.db.get_value(
			"CFDI Concepto Mapping",
			{
				"name": ["!=", self.name or ""],
				"company": company_filter,
				"supplier_rfc": self.supplier_rfc or "",
				"sat_product_key": self.sat_product_key or "",
			},
			"name",
		)
		if duplicate:
			frappe.throw(_("Ya existe una regla con la misma combinación empresa + RFC + clave SAT"))

	def _validate_target(self):
		if self.target_type == "Item" and not self.target_item:
			frappe.throw(_("El campo 'Item' es obligatorio cuando el tipo de destino es 'Item'"))
		if self.target_type == "ExpenseAccount" and not self.target_account:
			frappe.throw(
				_("El campo 'Cuenta de Gasto' es obligatorio cuando el tipo de destino es 'ExpenseAccount'")
			)
