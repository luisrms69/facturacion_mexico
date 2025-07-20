"""
Addenda Field Definition DocType - Sprint 3
Child table para definir campos disponibles en cada tipo de addenda
"""

import re

import frappe
from frappe import _
from frappe.model.document import Document


class AddendaFieldDefinition(Document):
	"""Definición de campos para tipos de addenda."""

	def validate(self):
		"""Validaciones del DocType."""
		self.validate_field_name()
		self.validate_field_type_options()
		self.validate_validation_pattern()
		self.validate_xml_mapping()
		self.validate_default_value()

	def validate_field_name(self):
		"""Validar nombre del campo."""
		if not self.field_name:
			return

		# Nombre debe ser alfanumérico con guiones bajos
		if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", self.field_name):
			frappe.throw(
				_("Nombre de campo debe comenzar con letra y solo contener letras, números y guiones bajos")
			)

		# Convertir a snake_case
		self.field_name = self.field_name.lower()

	def validate_field_type_options(self):
		"""Validar opciones según tipo de campo."""
		if self.field_type == "Select" and not self.options:
			frappe.throw(_("Campo tipo Select requiere opciones definidas"))

		if self.field_type == "Link" and not self.options:
			frappe.throw(_("Campo tipo Link requiere especificar el DocType en opciones"))

		# Limpiar opciones para tipos que no las necesitan
		if self.field_type not in ["Select", "Link"] and self.options:
			self.options = ""

	def validate_validation_pattern(self):
		"""Validar patrón de expresión regular."""
		if not self.validation_pattern:
			return

		try:
			re.compile(self.validation_pattern)
		except re.error as e:
			frappe.throw(_("Patrón de validación inválido: {0}").format(str(e)))

	def validate_xml_mapping(self):
		"""Validar mapeo XML."""
		# Al menos uno debe estar definido
		if not self.xml_attribute and not self.xml_element:
			frappe.throw(_("Debe especificar al menos un mapeo XML (atributo o elemento)"))

		# Validar nombres XML válidos
		if self.xml_attribute and not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", self.xml_attribute):
			frappe.throw(_("Nombre de atributo XML inválido: {0}").format(self.xml_attribute))

		if self.xml_element and not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", self.xml_element):
			frappe.throw(_("Nombre de elemento XML inválido: {0}").format(self.xml_element))

	def validate_default_value(self):
		"""Validar valor por defecto según tipo de campo."""
		if not self.default_value:
			return

		# Validaciones específicas por tipo
		if self.field_type == "Int":
			try:
				int(self.default_value)
			except ValueError:
				frappe.throw(_("Valor por defecto debe ser un número entero"))

		elif self.field_type == "Float" or self.field_type == "Currency":
			try:
				float(self.default_value)
			except ValueError:
				frappe.throw(_("Valor por defecto debe ser un número decimal"))

		elif self.field_type == "Date":
			try:
				frappe.utils.getdate(self.default_value)
			except Exception:
				frappe.throw(_("Valor por defecto debe ser una fecha válida (YYYY-MM-DD)"))

		elif self.field_type == "Check":
			if self.default_value.lower() not in ["0", "1", "true", "false"]:
				frappe.throw(_("Valor por defecto para Check debe ser 0, 1, true o false"))

		elif self.field_type == "Select":
			if self.options and self.default_value not in [
				opt.strip() for opt in self.options.split("\n") if opt.strip()
			]:
				frappe.throw(_("Valor por defecto debe estar en las opciones disponibles"))

	def get_field_options_list(self):
		"""Obtener lista de opciones para campos Select."""
		if not self.options:
			return []

		return [opt.strip() for opt in self.options.split("\n") if opt.strip()]

	def validate_field_value(self, value):
		"""Validar un valor contra esta definición de campo."""
		if not value and self.is_mandatory:
			return False, _("Campo '{0}' es obligatorio").format(self.field_label)

		if not value:
			return True, ""

		# Validar por tipo
		try:
			if self.field_type == "Int":
				int(value)
			elif self.field_type == "Float" or self.field_type == "Currency":
				float(value)
			elif self.field_type == "Date":
				frappe.utils.getdate(value)
			elif self.field_type == "Datetime":
				frappe.utils.get_datetime(value)
			elif self.field_type == "Check":
				if str(value).lower() not in ["0", "1", "true", "false"]:
					return False, _("Valor inválido para campo Check")
			elif self.field_type == "Select":
				options = self.get_field_options_list()
				if options and value not in options:
					return False, _("Valor '{0}' no está en las opciones disponibles").format(value)

		except Exception as e:
			return False, _("Valor inválido para tipo {0}: {1}").format(self.field_type, str(e))

		# Validar patrón si existe
		if self.validation_pattern:
			if not re.match(self.validation_pattern, str(value)):
				return False, _("Valor no cumple con el patrón de validación")

		return True, ""

	def get_default_value_typed(self):
		"""Obtener valor por defecto convertido al tipo correcto."""
		if not self.default_value:
			return None

		try:
			if self.field_type == "Int":
				return int(self.default_value)
			elif self.field_type == "Float" or self.field_type == "Currency":
				return float(self.default_value)
			elif self.field_type == "Date":
				return frappe.utils.getdate(self.default_value)
			elif self.field_type == "Datetime":
				return frappe.utils.get_datetime(self.default_value)
			elif self.field_type == "Check":
				return str(self.default_value).lower() in ["1", "true"]
			else:
				return self.default_value
		except Exception:
			return self.default_value

	def to_dict_for_template(self):
		"""Convertir a diccionario para uso en templates."""
		return {
			"name": self.field_name,
			"label": self.field_label,
			"type": self.field_type,
			"mandatory": self.is_mandatory,
			"default": self.get_default_value_typed(),
			"options": self.get_field_options_list() if self.field_type == "Select" else None,
			"help": self.help_text,
			"xml_attribute": self.xml_attribute,
			"xml_element": self.xml_element,
			"validation_pattern": self.validation_pattern,
		}

	def generate_xml_for_value(self, value, parent_element=None):
		"""Generar XML para un valor usando esta definición."""
		if not value and not self.is_mandatory:
			return ""

		# Usar valor por defecto si no se proporciona y es obligatorio
		if not value and self.is_mandatory and self.default_value:
			value = self.get_default_value_typed()

		if not value:
			return ""

		# Generar XML según mapeo
		if self.xml_attribute:
			# Como atributo
			return f'{self.xml_attribute}="{frappe.utils.escape_html(str(value))}"'
		elif self.xml_element:
			# Como elemento
			return f"<{self.xml_element}>{frappe.utils.escape_html(str(value))}</{self.xml_element}>"

		return ""
