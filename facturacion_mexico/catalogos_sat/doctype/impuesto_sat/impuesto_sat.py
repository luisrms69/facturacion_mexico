"""
Impuesto SAT DocType
Catálogo SAT c_Impuesto
"""

import frappe
from frappe.model.document import Document


class ImpuestoSAT(Document):
	"""Catálogo SAT de Impuestos (c_Impuesto)."""

	def validate(self):
		"""Validaciones del DocType."""
		self.validate_code_format()

	def validate_code_format(self):
		"""Validar formato del código SAT."""
		if not self.code:
			return

		# Los códigos de impuesto SAT son de 3 dígitos
		if len(self.code) != 3 or not self.code.isdigit():
			frappe.throw(frappe._("El código del impuesto debe ser de 3 dígitos numéricos"))
