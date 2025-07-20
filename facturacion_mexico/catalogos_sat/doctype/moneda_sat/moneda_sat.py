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
		self.validate_duplicate_code()

	def validate_code_format(self):
		"""Validar formato del código SAT."""
		if not self.code:
			return

		# Los códigos de moneda SAT son de 3 caracteres alfabéticos (ISO 4217)
		if len(self.code) != 3 or not self.code.isalpha():
			frappe.throw(frappe._("El código de moneda debe ser de 3 caracteres alfabéticos (ej: MXN, USD)"))

		# Convertir a mayúsculas
		self.code = self.code.upper()

	def validate_duplicate_code(self):
		"""Validar que no exista código duplicado."""
		if not self.code:
			return

		existing = frappe.db.get_value(
			"Moneda SAT", {"code": self.code, "name": ["!=", self.name or ""]}, "name"
		)

		if existing:
			frappe.throw(
				frappe._("Ya existe una moneda SAT con el código {0}").format(self.code),
				frappe.DuplicateEntryError,
			)
