"""
Addenda Field Value DocType - Sprint 3
Child table para valores de campos de addenda
"""

import re
from datetime import datetime
from typing import Any, Optional

import frappe
from frappe import _
from frappe.model.document import Document


class AddendaFieldValue(Document):
	"""Child table para valores de campos en configuraciones de addenda."""

	def validate(self):
		"""Validaciones del valor de campo."""
		self.validate_field_definition()
		self.validate_dynamic_configuration()
		self.validate_field_value()
		self.validate_transformation()

	def validate_field_definition(self):
		"""Validar que la definición de campo existe y es válida."""
		if not self.field_definition:
			frappe.throw(_("Definición de campo es requerida"))

		try:
			field_def = frappe.get_doc("Addenda Field Definition", self.field_definition)

			# Validar que la definición pertenece al mismo tipo de addenda
			if hasattr(self.parent_doc, "addenda_type") and field_def.parent != self.parent_doc.addenda_type:
				frappe.throw(_("La definición de campo no pertenece al tipo de addenda correcto"))

		except frappe.DoesNotExistError:
			frappe.throw(_("Definición de campo no encontrada: {0}").format(self.field_definition))

	def validate_dynamic_configuration(self):
		"""Validar configuración para campos dinámicos."""
		if self.is_dynamic:
			if not self.dynamic_source:
				frappe.throw(_("Fuente dinámica es requerida para campos dinámicos"))

			if not self.dynamic_field:
				frappe.throw(_("Campo dinámico es requerido para campos dinámicos"))

			# Validar que el campo dinámico existe en la fuente especificada
			self._validate_dynamic_field_exists()

		elif self.dynamic_source or self.dynamic_field:
			frappe.msgprint(
				_("Configuración dinámica será ignorada porque el campo no está marcado como dinámico"),
				indicator="orange",
			)

	def _validate_dynamic_field_exists(self):
		"""Validar que el campo dinámico existe en la fuente."""
		source_mapping = {
			"Sales Invoice": "Sales Invoice",
			"Customer": "Customer",
			"Item": "Item",
			"CFDI": None,  # Los campos CFDI son dinámicos del parser
			"Custom": None,  # Los campos custom son definidos por el usuario
		}

		doctype = source_mapping.get(self.dynamic_source)

		if doctype:
			# Verificar que el campo existe en el DocType
			meta = frappe.get_meta(doctype)
			if not meta.has_field(self.dynamic_field):
				frappe.msgprint(
					_("Campo '{0}' no encontrado en {1}").format(self.dynamic_field, doctype),
					indicator="orange",
				)

	def validate_field_value(self):
		"""Validar el valor del campo."""
		if not self.is_dynamic and self.is_required and not self.field_value:
			frappe.throw(_("Valor es requerido para campos no dinámicos obligatorios"))

		# Validar patrón si está definido
		if self.validation_pattern and self.field_value:
			try:
				if not re.match(self.validation_pattern, str(self.field_value)):
					frappe.throw(
						_("El valor '{0}' no cumple con el patrón de validación '{1}'").format(
							self.field_value, self.validation_pattern
						)
					)
			except re.error as e:
				frappe.throw(_("Patrón de validación inválido: {0}").format(str(e)))

	def validate_transformation(self):
		"""Validar configuración de transformación."""
		valid_transformations = [
			"",
			"Uppercase",
			"Lowercase",
			"Title",
			"Trim",
			"Number Format",
			"Date Format",
		]

		if self.transformation and self.transformation not in valid_transformations:
			frappe.throw(_("Transformación inválida: {0}").format(self.transformation))

	def get_resolved_value(self, context_data: dict | None = None) -> str:
		"""Resolver el valor final del campo."""
		if context_data is None:
			context_data = {}

		# Si es dinámico, obtener valor de la fuente
		if self.is_dynamic:
			value = self._get_dynamic_value(context_data)
		else:
			value = self.field_value or self.default_value or ""

		# Aplicar transformación
		if self.transformation and value:
			value = self._apply_transformation(str(value))

		return str(value) if value is not None else ""

	def _get_dynamic_value(self, context_data: dict) -> Any:
		"""Obtener valor dinámico de la fuente especificada."""
		try:
			source = self.dynamic_source
			field = self.dynamic_field

			if source == "Sales Invoice" and "sales_invoice" in context_data:
				return getattr(context_data["sales_invoice"], field, self.default_value)

			elif source == "Customer" and "customer" in context_data:
				return getattr(context_data["customer"], field, self.default_value)

			elif source == "Item" and "item" in context_data:
				return getattr(context_data["item"], field, self.default_value)

			elif source == "CFDI" and "cfdi_data" in context_data:
				return context_data["cfdi_data"].get(field, self.default_value)

			elif source == "Custom" and "custom_data" in context_data:
				return context_data["custom_data"].get(field, self.default_value)

			return self.default_value or ""

		except Exception as e:
			frappe.log_error(f"Error obteniendo valor dinámico: {e!s}")
			return self.default_value or ""

	def _apply_transformation(self, value: str) -> str:
		"""Aplicar transformación al valor."""
		try:
			if self.transformation == "Uppercase":
				return value.upper()

			elif self.transformation == "Lowercase":
				return value.lower()

			elif self.transformation == "Title":
				return value.title()

			elif self.transformation == "Trim":
				return value.strip()

			elif self.transformation == "Number Format":
				# Intentar formatear como número
				try:
					num = float(value)
					return f"{num:.2f}"
				except ValueError:
					return value

			elif self.transformation == "Date Format":
				# Intentar formatear como fecha
				try:
					if isinstance(value, datetime):
						return value.strftime("%Y-%m-%d")
					else:
						# Intentar parsear string como fecha
						date_obj = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
						return date_obj.strftime("%Y-%m-%d")
				except ValueError:
					return value

			return value

		except Exception as e:
			frappe.log_error(f"Error aplicando transformación: {e!s}")
			return value

	def get_field_definition_info(self) -> dict:
		"""Obtener información de la definición del campo."""
		try:
			field_def = frappe.get_doc("Addenda Field Definition", self.field_definition)
			return {
				"field_name": field_def.field_name,
				"field_type": field_def.field_type,
				"field_label": field_def.field_label,
				"xml_element": field_def.xml_element,
				"xml_attribute": field_def.xml_attribute,
				"is_required": field_def.is_required,
				"validation_pattern": field_def.validation_pattern,
			}
		except Exception:
			return {}

	def validate_against_definition(self) -> tuple[bool, list]:
		"""Validar valor contra la definición del campo."""
		errors = []

		try:
			field_def = frappe.get_doc("Addenda Field Definition", self.field_definition)
			value = self.get_resolved_value()

			# Verificar si es requerido
			if field_def.is_required and not value:
				errors.append(_("Campo requerido no puede estar vacío"))

			# Validar tipo de campo
			if value and field_def.field_type:
				type_valid, type_error = self._validate_field_type(value, field_def.field_type)
				if not type_valid:
					errors.append(type_error)

			# Validar patrón de la definición
			if value and field_def.validation_pattern:
				try:
					if not re.match(field_def.validation_pattern, str(value)):
						errors.append(
							_("Valor no cumple con patrón de definición: {0}").format(
								field_def.validation_pattern
							)
						)
				except re.error:
					errors.append(_("Patrón de validación inválido en definición"))

			return len(errors) == 0, errors

		except Exception as e:
			return False, [_("Error validando contra definición: {0}").format(str(e))]

	def _validate_field_type(self, value: str, field_type: str) -> tuple[bool, str]:
		"""Validar valor contra tipo de campo."""
		try:
			if field_type == "Int":
				int(value)
			elif field_type == "Float":
				float(value)
			elif field_type == "Date":
				datetime.strptime(value, "%Y-%m-%d")
			elif field_type == "Check":
				if value.lower() not in ["0", "1", "true", "false", "yes", "no"]:
					return False, _("Valor booleano inválido")

			return True, ""

		except (ValueError, TypeError):
			return False, _("Valor no válido para tipo {0}").format(field_type)

	@property
	def parent_doc(self):
		"""Obtener documento padre."""
		if hasattr(self, "_parent_doc"):
			return self._parent_doc

		# Intentar obtener desde parent
		if self.parent and self.parenttype:
			try:
				self._parent_doc = frappe.get_doc(self.parenttype, self.parent)
				return self._parent_doc
			except Exception:
				pass

		return None
