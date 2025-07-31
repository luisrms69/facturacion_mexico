# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class SATProductoServicio(Document):
	def validate(self):
		"""Validar formato del código SAT."""
		self.validate_codigo_format()

	def validate_codigo_format(self):
		"""Validar que el código tenga exactamente 8 dígitos."""
		if not self.codigo:
			frappe.throw(_("Código es requerido"))

		# Limpiar espacios y convertir a string
		codigo_clean = str(self.codigo).strip()

		# Validar que tenga exactamente 8 dígitos
		if not codigo_clean.isdigit():
			frappe.throw(_("Código debe contener solo números"))

		if len(codigo_clean) != 8:
			frappe.throw(
				_("Código debe tener exactamente 8 dígitos. Código actual: {0} ({1} dígitos)").format(
					codigo_clean, len(codigo_clean)
				)
			)

		# Normalizar el código
		self.codigo = codigo_clean
