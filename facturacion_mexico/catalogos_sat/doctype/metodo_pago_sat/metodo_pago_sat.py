import frappe
from frappe import _
from frappe.model.document import Document


class MetodoPagoSAT(Document):
	"""Catálogo de Métodos de Pago según SAT."""

	def validate(self):
		"""Validar antes de guardar."""
		self.validate_code_format()
		self.validate_vigencia()

	def validate_code_format(self):
		"""Validar formato del código."""
		if self.code:
			self.code = self.code.strip().upper()

			# Validar que no esté vacío después del strip
			if not self.code:
				frappe.throw(_("El código no puede estar vacío"))

			# Validar que sea de 3 caracteres (formato SAT: PUE, PPD)
			if len(self.code) != 3:
				frappe.throw(_("El código de método de pago debe ser de 3 caracteres"))

	def validate_vigencia(self):
		"""Validar fechas de vigencia."""
		if self.vigencia_desde and self.vigencia_hasta:
			if self.vigencia_desde > self.vigencia_hasta:
				frappe.throw(_("La fecha de inicio no puede ser mayor a la fecha fin"))

	@staticmethod
	def get_active_codes():
		"""Obtener códigos activos."""
		from frappe.utils import today

		filters = {"or_filters": [{"vigencia_hasta": ["is", "not set"]}, {"vigencia_hasta": [">=", today()]}]}

		return frappe.get_all(
			"Metodo Pago SAT", filters=filters, fields=["code", "description"], order_by="code"
		)

	@staticmethod
	def get_default_method():
		"""Obtener método de pago por defecto."""
		# PUE = Pago en una sola exhibición (más común)
		if frappe.db.exists("Metodo Pago SAT", "PUE"):
			return frappe.get_doc("Metodo Pago SAT", "PUE")

		# Si no existe PUE, retornar el primer activo
		active_methods = MetodoPagoSAT.get_active_codes()
		if active_methods:
			return frappe.get_doc("Metodo Pago SAT", active_methods[0].code)

		return None

	def is_active(self):
		"""Verificar si el método de pago está activo."""
		if not self.vigencia_hasta:
			return True

		from frappe.utils import today

		return self.vigencia_hasta >= today()

	def requires_payment_details(self):
		"""Verificar si requiere detalles de pago."""
		# PPD (Pago en parcialidades o diferido) requiere más detalles
		return self.code == "PPD"
