"""
Moneda SAT DocType
Catálogo SAT c_Moneda
"""

import frappe
from frappe.model.document import Document


class MonedaSAT(Document):
	"""Catálogo SAT de Monedas (c_Moneda)."""

	def validate(self):
		"""Validaciones del DocType."""
		self.validate_code_format()

	def validate_code_format(self):
		"""Validar formato del código SAT."""
		if not self.code:
			return

		# Los códigos de moneda SAT son de 3 caracteres alfabéticos (ISO 4217)
		if len(self.code) != 3 or not self.code.isalpha():
			frappe.throw(frappe._("El código de moneda debe ser de 3 caracteres alfabéticos (ej: MXN, USD)"))

		# Convertir a mayúsculas
		self.code = self.code.upper()
