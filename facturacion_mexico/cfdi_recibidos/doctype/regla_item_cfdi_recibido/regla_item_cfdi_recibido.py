import frappe
from frappe import _
from frappe.model.document import Document


class ReglaItemCFDIRecibido(Document):
	def validate(self):
		self._validar_filtros()

	def _validar_filtros(self):
		if not self.supplier_rfc and not self.sat_product_key and not self.keywords:
			frappe.throw(
				_("La regla debe tener al menos un filtro: RFC Proveedor, Clave SAT o Palabras clave."),
				frappe.ValidationError,
			)
