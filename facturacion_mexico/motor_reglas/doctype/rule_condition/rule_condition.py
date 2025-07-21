"""
Rule Condition - Sprint 4 Semana 2
Child DocType para condiciones de reglas fiscales
"""

import re

import frappe
from frappe import _
from frappe.model.document import Document


class RuleCondition(Document):
	"""Condición individual dentro de una regla fiscal."""

	def validate(self):
		"""Validaciones de la condición."""
		self.validate_condition_syntax()
		self.validate_field_reference()
		self.validate_operator_value_compatibility()

	def validate_condition_syntax(self):
		"""Validar sintaxis de la condición."""
		if self.condition_type == "Field" and not self.field_name:
			frappe.throw(_("Campo es requerido para condiciones de tipo 'Field'"))

		if self.condition_type == "Expression" and not self.value:
			frappe.throw(_("Expresión es requerida para condiciones de tipo 'Expression'"))

		if self.condition_type == "Custom" and not self.value:
			frappe.throw(_("Script es requerido para condiciones de tipo 'Custom'"))

	def validate_field_reference(self):
		"""Validar que el campo referenciado existe."""
		if self.condition_type == "Field" and self.field_name:
			# Obtener el DocType padre para validar el campo
			parent_doc = self.get_parent_doc()
			if parent_doc and parent_doc.apply_to_doctype:
				doctype = parent_doc.apply_to_doctype

				# Verificar que el campo existe en el DocType
				if not frappe.db.exists("DocField", {"parent": doctype, "fieldname": self.field_name}):
					# Verificar si es un campo personalizado
					if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": self.field_name}):
						frappe.msgprint(
							_("Advertencia: El campo '{0}' no existe en {1}").format(
								self.field_name, doctype
							),
							indicator="orange",
						)

	def validate_operator_value_compatibility(self):
		"""Validar compatibilidad entre operador y valor."""
		if self.operator in ["is_set", "is_not_set"] and self.value:
			frappe.msgprint(
				_("Advertencia: Operadores 'is_set' e 'is_not_set' no requieren valor"), indicator="orange"
			)

		if self.operator in ["in_list", "not_in_list"] and self.value:
			# Validar que el valor sea una lista válida
			try:
				if self.value_type == "Static":
					# Debe ser una lista separada por comas o JSON
					if not ("," in self.value or self.value.startswith("[")):
						frappe.msgprint(
							_("Advertencia: Para operadores de lista, use valores separados por comas"),
							indicator="orange",
						)
			except Exception:
				pass

		if self.operator == "regex_match" and self.value:
			# Validar que sea una expresión regular válida
			try:
				re.compile(self.value)
			except re.error:
				frappe.throw(_("Expresión regular inválida: {0}").format(self.value))

	def evaluate_condition(self, document):
		"""Evaluar la condición contra un documento."""
		try:
			if self.condition_type == "Field":
				return self.evaluate_field_condition(document)
			elif self.condition_type == "Expression":
				return self.evaluate_expression_condition(document)
			elif self.condition_type == "Custom":
				return self.evaluate_custom_condition(document)
			else:
				return False
		except Exception as e:
			frappe.log_error(f"Error evaluando condición {self.idx}: {e}")
			return False

	def evaluate_field_condition(self, document):
		"""Evaluar condición de campo."""
		if not self.field_name:
			return False

		# Obtener valor del documento
		doc_value = self.get_document_field_value(document, self.field_name)
		comparison_value = self.get_comparison_value(document)

		return self.apply_operator(doc_value, comparison_value)

	def evaluate_expression_condition(self, document):
		"""Evaluar condición de expresión."""
		# TODO: Implementar evaluación de expresiones seguras
		# Por seguridad, por ahora retornamos False
		frappe.log_error("Expression evaluation not yet implemented")
		return False

	def evaluate_custom_condition(self, document):
		"""Evaluar condición personalizada."""
		# TODO: Implementar evaluación de scripts personalizados de forma segura
		# Por seguridad, por ahora retornamos False
		frappe.log_error("Custom condition evaluation not yet implemented")
		return False

	def get_document_field_value(self, document, field_name):
		"""Obtener valor de campo del documento."""
		try:
			if hasattr(document, field_name):
				return getattr(document, field_name)
			elif isinstance(document, dict) and field_name in document:
				return document[field_name]
			else:
				return None
		except (AttributeError, KeyError):
			return None

	def get_comparison_value(self, document):
		"""Obtener valor de comparación según el tipo."""
		if not self.value:
			return None

		if self.value_type == "Static":
			return self.value
		elif self.value_type == "Dynamic":
			# Valor dinámico como fecha actual, usuario, etc.
			return self.resolve_dynamic_value()
		elif self.value_type == "Formula":
			# TODO: Implementar evaluación de fórmulas
			return self.value
		elif self.value_type == "Field Reference":
			# Referencia a otro campo del mismo documento
			return self.get_document_field_value(document, self.value)
		else:
			return self.value

	def resolve_dynamic_value(self):
		"""Resolver valores dinámicos."""
		dynamic_values = {
			"TODAY": frappe.utils.today(),
			"NOW": frappe.utils.now(),
			"CURRENT_USER": frappe.session.user,
			"CURRENT_COMPANY": frappe.defaults.get_user_default("Company"),
		}

		return dynamic_values.get(self.value, self.value)

	def apply_operator(self, doc_value, comparison_value):
		"""Aplicar operador de comparación."""
		try:
			if self.operator == "equals":
				return doc_value == comparison_value
			elif self.operator == "not_equals":
				return doc_value != comparison_value
			elif self.operator == "greater_than":
				return self.safe_numeric_compare(doc_value, comparison_value, ">")
			elif self.operator == "less_than":
				return self.safe_numeric_compare(doc_value, comparison_value, "<")
			elif self.operator == "greater_equal":
				return self.safe_numeric_compare(doc_value, comparison_value, ">=")
			elif self.operator == "less_equal":
				return self.safe_numeric_compare(doc_value, comparison_value, "<=")
			elif self.operator == "contains":
				return comparison_value in str(doc_value) if doc_value else False
			elif self.operator == "not_contains":
				return comparison_value not in str(doc_value) if doc_value else True
			elif self.operator == "in_list":
				return self.value_in_list(doc_value, comparison_value)
			elif self.operator == "not_in_list":
				return not self.value_in_list(doc_value, comparison_value)
			elif self.operator == "is_set":
				return doc_value is not None and doc_value != ""
			elif self.operator == "is_not_set":
				return doc_value is None or doc_value == ""
			elif self.operator == "regex_match":
				return bool(re.match(comparison_value, str(doc_value))) if doc_value else False
			else:
				return False
		except Exception as e:
			frappe.log_error(f"Error aplicando operador {self.operator}: {e}")
			return False

	def safe_numeric_compare(self, doc_value, comparison_value, operator):
		"""Comparación numérica segura."""
		try:
			doc_num = float(doc_value) if doc_value is not None else 0
			comp_num = float(comparison_value) if comparison_value is not None else 0

			if operator == ">":
				return doc_num > comp_num
			elif operator == "<":
				return doc_num < comp_num
			elif operator == ">=":
				return doc_num >= comp_num
			elif operator == "<=":
				return doc_num <= comp_num
		except (ValueError, TypeError):
			# Si no son números, comparar como strings
			return self.safe_string_compare(doc_value, comparison_value, operator)

	def safe_string_compare(self, doc_value, comparison_value, operator):
		"""Comparación de strings segura."""
		try:
			doc_str = str(doc_value) if doc_value is not None else ""
			comp_str = str(comparison_value) if comparison_value is not None else ""

			if operator == ">":
				return doc_str > comp_str
			elif operator == "<":
				return doc_str < comp_str
			elif operator == ">=":
				return doc_str >= comp_str
			elif operator == "<=":
				return doc_str <= comp_str
		except (ValueError, TypeError):
			return False

	def value_in_list(self, doc_value, list_value):
		"""Verificar si valor está en lista."""
		try:
			if isinstance(list_value, str):
				# Parsear lista desde string
				if list_value.startswith("["):
					import json

					value_list = json.loads(list_value)
				else:
					value_list = [v.strip() for v in list_value.split(",")]
			else:
				value_list = list_value if isinstance(list_value, list) else [list_value]

			return doc_value in value_list
		except (json.JSONDecodeError, ValueError, TypeError):
			return False

	def get_parent_doc(self):
		"""Obtener documento padre."""
		try:
			return frappe.get_doc("Fiscal Validation Rule", self.parent)
		except frappe.DoesNotExistError:
			return None
