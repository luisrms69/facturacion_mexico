import frappe
from frappe import _
from frappe.model.document import Document


class UsoCFDISAT(Document):
	"""Catálogo de Usos del CFDI según SAT."""

	def validate(self):
		"""Validar antes de guardar."""
		self.validate_code_format()
		self.validate_at_least_one_applies()
		self.validate_vigencia()

	def validate_code_format(self):
		"""Validar formato del código."""
		if self.code:
			self.code = self.code.strip().upper()

			# Validar que no esté vacío después del strip
			if not self.code:
				frappe.throw(_("El código no puede estar vacío"))

	def validate_at_least_one_applies(self):
		"""Validar que aplique al menos a un tipo de persona."""
		if not self.aplica_fisica and not self.aplica_moral:
			frappe.throw(_("Debe aplicar al menos a persona física o moral"))

	def validate_vigencia(self):
		"""Validar fechas de vigencia."""
		if self.vigencia_desde and self.vigencia_hasta:
			if self.vigencia_desde > self.vigencia_hasta:
				frappe.throw(_("La fecha de inicio no puede ser mayor a la fecha fin"))

	@staticmethod
	def get_for_customer_type(customer_type):
		"""Obtener usos CFDI válidos para tipo de cliente."""
		filters = {}

		if customer_type == "Individual":
			filters["aplica_fisica"] = 1
		elif customer_type == "Company":
			filters["aplica_moral"] = 1

		# Agregar filtro de vigencia activa
		from frappe.utils import today

		filters.update(
			{"or_filters": [{"vigencia_hasta": ["is", "not set"]}, {"vigencia_hasta": [">=", today()]}]}
		)

		return frappe.get_all(
			"Uso CFDI SAT", filters=filters, fields=["name", "code", "description"], order_by="code"
		)

	@staticmethod
	def get_active_codes():
		"""Obtener códigos activos."""
		from frappe.utils import today

		filters = {"or_filters": [{"vigencia_hasta": ["is", "not set"]}, {"vigencia_hasta": [">=", today()]}]}

		return frappe.get_all(
			"Uso CFDI SAT", filters=filters, fields=["code", "description"], order_by="code"
		)

	def is_active(self):
		"""Verificar si el uso CFDI está activo."""
		if not self.vigencia_hasta:
			return True

		from frappe.utils import today

		return self.vigencia_hasta >= today()
