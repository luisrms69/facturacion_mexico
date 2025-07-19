import frappe
from frappe import _
from frappe.model.document import Document


class FormaPagoSAT(Document):
	"""Catálogo de Formas de Pago según SAT."""

	def validate(self):
		"""Validar antes de guardar."""
		self.validate_code_format()
		self.validate_vigencia()

	def validate_code_format(self):
		"""Validar formato del código."""
		if self.code:
			self.code = self.code.strip()

			# Validar que no esté vacío después del strip
			if not self.code:
				frappe.throw(_("El código no puede estar vacío"))

			# Validar que sea de 2 dígitos (formato SAT)
			if not (len(self.code) == 2 and self.code.isdigit()):
				frappe.throw(_("El código de forma de pago debe ser de 2 dígitos"))

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
			"Forma Pago SAT", filters=filters, fields=["code", "description"], order_by="code"
		)

	@staticmethod
	def get_common_payment_forms():
		"""Obtener formas de pago más comunes."""
		common_codes = ["01", "02", "03", "04", "28", "99"]  # Efectivo, Cheque, Transferencia, etc.

		return frappe.get_all(
			"Forma Pago SAT",
			filters={"code": ["in", common_codes]},
			fields=["code", "description"],
			order_by="code",
		)

	def is_active(self):
		"""Verificar si la forma de pago está activa."""
		if not self.vigencia_hasta:
			return True

		from frappe.utils import today

		return self.vigencia_hasta >= today()
