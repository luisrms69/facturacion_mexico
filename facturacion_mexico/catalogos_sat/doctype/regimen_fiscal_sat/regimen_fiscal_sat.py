import frappe
from frappe import _
from frappe.model.document import Document


class RegimenFiscalSAT(Document):
	"""Catálogo de Regímenes Fiscales según SAT."""

	def validate(self):
		"""Validar antes de guardar."""
		self.validate_code_format()
		self.validate_at_least_one_applies()
		self.validate_vigencia()

	def validate_code_format(self):
		"""Validar formato del código."""
		if self.code:
			self.code = self.code.strip()

			# Validar que no esté vacío después del strip
			if not self.code:
				frappe.throw(_("El código no puede estar vacío"))

			# Validar que sea numérico (códigos de régimen son números)
			if not self.code.isdigit():
				frappe.throw(_("El código de régimen fiscal debe ser numérico"))

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
		"""Obtener regímenes fiscales válidos para tipo de cliente."""
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
			"Regimen Fiscal SAT", filters=filters, fields=["name", "code", "description"], order_by="code"
		)

	@staticmethod
	def get_active_codes():
		"""Obtener códigos activos."""
		from frappe.utils import today

		filters = {"or_filters": [{"vigencia_hasta": ["is", "not set"]}, {"vigencia_hasta": [">=", today()]}]}

		return frappe.get_all(
			"Regimen Fiscal SAT", filters=filters, fields=["code", "description"], order_by="code"
		)

	@staticmethod
	def get_default_for_customer_type(customer_type):
		"""Obtener régimen fiscal por defecto según tipo de cliente."""
		default_codes = {
			"Individual": "612",  # Personas Físicas con Actividades Empresariales
			"Company": "601",  # General de Ley Personas Morales
		}

		code = default_codes.get(customer_type)
		if code and frappe.db.exists("Regimen Fiscal SAT", code):
			return frappe.get_doc("Regimen Fiscal SAT", code)

		return None

	def is_active(self):
		"""Verificar si el régimen fiscal está activo."""
		if not self.vigencia_hasta:
			return True

		from frappe.utils import today

		return self.vigencia_hasta >= today()

	def is_valid_for_customer_type(self, customer_type):
		"""Verificar si es válido para tipo de cliente."""
		if customer_type == "Individual":
			return self.aplica_fisica
		elif customer_type == "Company":
			return self.aplica_moral

		return False
