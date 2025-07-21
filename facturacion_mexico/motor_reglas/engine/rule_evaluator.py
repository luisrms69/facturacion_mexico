"""
Rule Evaluator - Sprint 4 Semana 2
Componente para evaluar condiciones de reglas fiscales
"""

import json

import frappe
from frappe import _


class RuleEvaluator:
	"""Evaluador de condiciones de reglas fiscales."""

	def __init__(self):
		self.evaluation_context = {}

	def evaluate_conditions(self, conditions, document):
		"""Evaluar todas las condiciones de una regla."""
		if not conditions:
			return True

		try:
			# Construir expresión lógica completa
			logical_expression = self.build_logical_expression(conditions, document)

			# Evaluar expresión final
			return self.evaluate_logical_expression(logical_expression)

		except Exception as e:
			frappe.log_error(f"Error evaluando condiciones: {e}")
			return False

	def build_logical_expression(self, conditions, document):
		"""Construir expresión lógica desde condiciones."""
		expression_parts = []
		group_stack = []

		for i, condition in enumerate(conditions):
			# Evaluar condición individual
			condition_result = self.evaluate_single_condition(condition, document)

			# Manejar inicio de grupo
			if condition.group_start:
				group_stack.append(len(expression_parts))
				expression_parts.append("(")

			# Agregar resultado de condición
			expression_parts.append(str(condition_result).lower())

			# Manejar fin de grupo
			if condition.group_end:
				if group_stack:
					group_stack.pop()
					expression_parts.append(")")

			# Agregar operador lógico (excepto en la última condición)
			if i < len(conditions) - 1 and condition.logical_operator:
				expression_parts.append(condition.logical_operator.lower())

		# Cerrar grupos abiertos
		while group_stack:
			expression_parts.append(")")
			group_stack.pop()

		return " ".join(expression_parts)

	def evaluate_single_condition(self, condition, document):
		"""Evaluar una condición individual."""
		try:
			if hasattr(condition, "evaluate_condition"):
				# Si la condición tiene su propio método de evaluación
				return condition.evaluate_condition(document)
			else:
				# Evaluación manual para compatibilidad
				return self.manual_condition_evaluation(condition, document)

		except Exception as e:
			frappe.log_error(f"Error evaluando condición individual: {e}")
			return False

	def manual_condition_evaluation(self, condition, document):
		"""Evaluación manual de condición para compatibilidad."""
		if condition.condition_type == "Field":
			return self.evaluate_field_condition_manual(condition, document)
		elif condition.condition_type == "Expression":
			return self.evaluate_expression_condition_manual(condition, document)
		elif condition.condition_type == "Custom":
			return self.evaluate_custom_condition_manual(condition, document)
		else:
			return False

	def evaluate_field_condition_manual(self, condition, document):
		"""Evaluación manual de condición de campo."""
		if not condition.field_name:
			return False

		# Obtener valor del documento
		doc_value = self.get_document_field_value(document, condition.field_name)
		comparison_value = self.get_comparison_value(condition, document)

		return self.apply_operator(doc_value, comparison_value, condition.operator)

	def evaluate_expression_condition_manual(self, condition, document):
		"""Evaluación manual de condición de expresión."""
		# Por seguridad, solo evaluaciones básicas
		return False

	def evaluate_custom_condition_manual(self, condition, document):
		"""Evaluación manual de condición personalizada."""
		# Por seguridad, deshabilitado
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

	def get_comparison_value(self, condition, document):
		"""Obtener valor de comparación."""
		if not condition.value:
			return None

		if condition.value_type == "Static":
			return condition.value
		elif condition.value_type == "Dynamic":
			return self.resolve_dynamic_value(condition.value)
		elif condition.value_type == "Formula":
			return self.evaluate_formula(condition.value, document)
		elif condition.value_type == "Field Reference":
			return self.get_document_field_value(document, condition.value)
		else:
			return condition.value

	def resolve_dynamic_value(self, value):
		"""Resolver valores dinámicos."""
		dynamic_values = {
			"TODAY": frappe.utils.today(),
			"NOW": frappe.utils.now(),
			"CURRENT_USER": frappe.session.user,
			"CURRENT_COMPANY": frappe.defaults.get_user_default("Company"),
		}

		return dynamic_values.get(value, value)

	def evaluate_formula(self, formula, document):
		"""Evaluar fórmula (implementación básica y segura)."""
		# Por seguridad, solo fórmulas básicas predefinidas
		safe_formulas = {
			"GRAND_TOTAL": lambda doc: getattr(doc, "grand_total", 0),
			"NET_TOTAL": lambda doc: getattr(doc, "net_total", 0),
			"TOTAL_TAXES": lambda doc: getattr(doc, "total_taxes_and_charges", 0),
			"ITEM_COUNT": lambda doc: len(getattr(doc, "items", [])),
		}

		if formula in safe_formulas:
			try:
				return safe_formulas[formula](document)
			except (AttributeError, TypeError, KeyError):
				return 0
		else:
			return formula

	def apply_operator(self, doc_value, comparison_value, operator):
		"""Aplicar operador de comparación."""
		try:
			if operator == "equals":
				return doc_value == comparison_value
			elif operator == "not_equals":
				return doc_value != comparison_value
			elif operator == "greater_than":
				return self.safe_numeric_compare(doc_value, comparison_value, ">")
			elif operator == "less_than":
				return self.safe_numeric_compare(doc_value, comparison_value, "<")
			elif operator == "greater_equal":
				return self.safe_numeric_compare(doc_value, comparison_value, ">=")
			elif operator == "less_equal":
				return self.safe_numeric_compare(doc_value, comparison_value, "<=")
			elif operator == "contains":
				return comparison_value in str(doc_value) if doc_value else False
			elif operator == "not_contains":
				return comparison_value not in str(doc_value) if doc_value else True
			elif operator == "in_list":
				return self.value_in_list(doc_value, comparison_value)
			elif operator == "not_in_list":
				return not self.value_in_list(doc_value, comparison_value)
			elif operator == "is_set":
				return doc_value is not None and doc_value != ""
			elif operator == "is_not_set":
				return doc_value is None or doc_value == ""
			elif operator == "regex_match":
				import re

				return bool(re.match(comparison_value, str(doc_value))) if doc_value else False
			else:
				return False
		except Exception as e:
			frappe.log_error(f"Error aplicando operador {operator}: {e}")
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

	def evaluate_logical_expression(self, expression):
		"""Evaluar expresión lógica de forma segura."""
		try:
			# Reemplazar operadores para Python
			python_expression = expression.replace(" and ", " and ").replace(" or ", " or ")

			# Validar que solo contenga tokens seguros
			import re

			# Tokenizar la expresión para validar solo palabras completas
			tokens = re.findall(r"\w+|\(|\)|and|or", python_expression.lower())
			safe_tokens = ["true", "false", "and", "or"]

			for token in tokens:
				if token.isalpha() and token not in safe_tokens:
					return False

			# Evaluar expresión de forma segura
			# Reemplazar true/false por valores booleanos de Python
			safe_expression = python_expression.lower().replace("true", "True").replace("false", "False")
			return frappe.safe_eval(safe_expression)

		except Exception as e:
			frappe.log_error(f"Error evaluando expresión lógica '{expression}': {e}")
			return False

	def get_evaluation_summary(self, conditions, document):
		"""Obtener resumen detallado de evaluación."""
		summary = {
			"total_conditions": len(conditions) if conditions else 0,
			"conditions_detail": [],
			"final_result": False,
			"logical_expression": "",
		}

		if not conditions:
			summary["final_result"] = True
			return summary

		try:
			# Evaluar cada condición individualmente
			for i, condition in enumerate(conditions):
				condition_result = self.evaluate_single_condition(condition, document)

				condition_detail = {
					"index": i + 1,
					"condition_type": condition.condition_type,
					"field_name": condition.field_name,
					"operator": condition.operator,
					"value": condition.value,
					"result": condition_result,
					"logical_operator": condition.logical_operator,
				}

				summary["conditions_detail"].append(condition_detail)

			# Construir y evaluar expresión lógica
			logical_expression = self.build_logical_expression(conditions, document)
			summary["logical_expression"] = logical_expression
			summary["final_result"] = self.evaluate_logical_expression(logical_expression)

		except Exception as e:
			summary["error"] = str(e)
			frappe.log_error(f"Error en resumen de evaluación: {e}")

		return summary
