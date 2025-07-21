"""
Rule Parser - Sprint 4 Semana 2
Componente para parsear y validar sintaxis de reglas fiscales
"""

import json
import re

from frappe import _


class RuleParser:
	"""Parser para sintaxis y validación de reglas fiscales."""

	def __init__(self):
		self.supported_operators = [
			"equals",
			"not_equals",
			"greater_than",
			"less_than",
			"greater_equal",
			"less_equal",
			"contains",
			"not_contains",
			"in_list",
			"not_in_list",
			"is_set",
			"is_not_set",
			"regex_match",
		]

		self.supported_action_types = [
			"Set Field",
			"Show Error",
			"Show Warning",
			"Show Message",
			"Call API",
			"Execute Script",
			"Send Email",
			"Create Document",
		]

		self.supported_value_types = ["Static", "Dynamic", "Formula", "Field Reference"]

	def validate_rule_syntax(self, rule_doc):
		"""Validar sintaxis completa de una regla."""
		errors = []

		# Validar condiciones
		if rule_doc.conditions:
			for condition in rule_doc.conditions:
				condition_validation = self.validate_condition_syntax(condition)
				if not condition_validation["valid"]:
					errors.extend(condition_validation["errors"])

		# Validar acciones
		if rule_doc.actions:
			for action in rule_doc.actions:
				action_validation = self.validate_action_syntax(action)
				if not action_validation["valid"]:
					errors.extend(action_validation["errors"])

		return {"valid": len(errors) == 0, "errors": errors}

	def parse_conditions(self, conditions):
		"""Parsear condiciones a estructura AST."""
		if not conditions:
			return {"type": "empty", "result": True}

		try:
			ast_nodes = []

			for condition in conditions:
				node = self.parse_single_condition(condition)
				ast_nodes.append(node)

			# Construir AST con operadores lógicos
			ast = self.build_logical_ast(ast_nodes)

			return ast

		except Exception as e:
			return {"type": "error", "error": str(e)}

	def parse_single_condition(self, condition):
		"""Parsear una condición individual."""
		node = {
			"type": "condition",
			"condition_type": condition.condition_type,
			"field_name": condition.field_name,
			"operator": condition.operator,
			"value": condition.value,
			"value_type": condition.value_type,
			"logical_operator": condition.logical_operator,
			"group_start": condition.group_start,
			"group_end": condition.group_end,
			"validation": self.validate_condition_syntax(condition),
		}

		return node

	def build_logical_ast(self, condition_nodes):
		"""Construir AST lógico desde nodos de condiciones."""
		if not condition_nodes:
			return {"type": "empty", "result": True}

		if len(condition_nodes) == 1:
			return condition_nodes[0]

		# Construir árbol de operadores lógicos
		# Por simplicidad, procesamos de izquierda a derecha
		ast = {"type": "logical_expression", "nodes": condition_nodes}

		return ast

	def validate_condition_syntax(self, condition):
		"""Validar sintaxis de una condición individual."""
		errors = []
		warnings = []

		# Validar tipo de condición
		if condition.condition_type == "Field":
			if not condition.field_name:
				errors.append("Field name is required for Field conditions")

		elif condition.condition_type == "Expression":
			if not condition.value:
				errors.append("Expression is required for Expression conditions")
			else:
				# Validar sintaxis básica de expresión
				expr_validation = self.validate_expression_syntax(condition.value)
				if not expr_validation["valid"]:
					errors.extend(expr_validation["errors"])

		elif condition.condition_type == "Custom":
			if not condition.value:
				errors.append("Script is required for Custom conditions")
			warnings.append("Custom conditions are currently disabled for security")

		# Validar operador
		if condition.operator not in self.supported_operators:
			errors.append(f"Unsupported operator: {condition.operator}")

		# Validar compatibilidad operador-valor
		if condition.operator in ["is_set", "is_not_set"] and condition.value:
			warnings.append("Operators 'is_set' and 'is_not_set' do not require a value")

		if condition.operator in ["in_list", "not_in_list"] and condition.value:
			list_validation = self.validate_list_value(condition.value)
			if not list_validation["valid"]:
				errors.extend(list_validation["errors"])

		if condition.operator == "regex_match" and condition.value:
			regex_validation = self.validate_regex_syntax(condition.value)
			if not regex_validation["valid"]:
				errors.append(f"Invalid regex: {regex_validation['error']}")

		# Validar tipo de valor
		if condition.value_type not in self.supported_value_types:
			errors.append(f"Unsupported value type: {condition.value_type}")

		return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

	def validate_expression_syntax(self, expression):
		"""Validar sintaxis de expresión."""
		# Implementación básica - solo expresiones muy simples
		safe_patterns = [
			r"^[a-zA-Z_][a-zA-Z0-9_]*$",  # Solo nombres de campo
			r"^[a-zA-Z_][a-zA-Z0-9_]*\s*[<>=!]+\s*\d+$",  # Campo operador número
		]

		for pattern in safe_patterns:
			if re.match(pattern, expression.strip()):
				return {"valid": True, "errors": []}

		return {"valid": False, "errors": ["Expression syntax not supported in current implementation"]}

	def validate_list_value(self, value):
		"""Validar valor de lista."""
		try:
			if value.startswith("["):
				# JSON list
				parsed = json.loads(value)
				if not isinstance(parsed, list):
					return {"valid": False, "errors": ["JSON value must be a list"]}
			else:
				# Comma-separated list
				if "," not in value:
					return {"valid": False, "errors": ["List values must be comma-separated or JSON array"]}

			return {"valid": True, "errors": []}

		except json.JSONDecodeError:
			return {"valid": False, "errors": ["Invalid JSON list format"]}

	def validate_regex_syntax(self, regex_pattern):
		"""Validar sintaxis de expresión regular."""
		try:
			re.compile(regex_pattern)
			return {"valid": True, "error": None}
		except re.error as e:
			return {"valid": False, "error": str(e)}

	def parse_actions(self, actions):
		"""Parsear acciones a estructura AST."""
		if not actions:
			return {"type": "empty", "actions": []}

		try:
			action_nodes = []

			for action in actions:
				node = self.parse_single_action(action)
				action_nodes.append(node)

			return {"type": "action_sequence", "actions": action_nodes, "total_actions": len(action_nodes)}

		except Exception as e:
			return {"type": "error", "error": str(e)}

	def parse_single_action(self, action):
		"""Parsear una acción individual."""
		node = {
			"type": "action",
			"action_type": action.action_type,
			"target_field": action.target_field,
			"action_value": action.action_value,
			"continue_on_error": action.continue_on_error,
			"log_action": action.log_action,
			"description": action.description,
			"validation": self.validate_action_syntax(action),
		}

		return node

	def validate_action_syntax(self, action):
		"""Validar sintaxis de una acción individual."""
		errors = []
		warnings = []

		# Validar tipo de acción
		if action.action_type not in self.supported_action_types:
			errors.append(f"Unsupported action type: {action.action_type}")

		# Validaciones específicas por tipo
		if action.action_type == "Set Field":
			if not action.target_field:
				errors.append("Target field is required for Set Field actions")
			if not action.action_value:
				warnings.append("No value specified for Set Field action")

		elif action.action_type in ["Show Error", "Show Warning", "Show Message"]:
			if not action.action_value:
				errors.append(f"Message is required for {action.action_type} actions")

		elif action.action_type == "Call API":
			if not action.action_value:
				errors.append("API URL is required for Call API actions")
			elif not self.validate_url_format(action.action_value):
				errors.append("Invalid URL format")
			warnings.append("API calls are currently disabled for security")

		elif action.action_type == "Execute Script":
			if not action.action_value:
				errors.append("Script is required for Execute Script actions")
			warnings.append("Script execution is currently disabled for security")

		elif action.action_type == "Send Email":
			if action.action_value:
				email_validation = self.validate_email_config(action.action_value)
				if not email_validation["valid"]:
					errors.extend(email_validation["errors"])

		elif action.action_type == "Create Document":
			warnings.append("Document creation is currently disabled for security")

		return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

	def validate_url_format(self, url):
		"""Validar formato de URL."""
		url_pattern = re.compile(
			r"^https?://"  # http:// o https://
			r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
			r"localhost|"  # localhost...
			r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
			r"(?::\d+)?"  # optional port
			r"(?:/?|[/?]\S+)$",
			re.IGNORECASE,
		)

		return url_pattern.match(url) is not None

	def validate_email_config(self, config_json):
		"""Validar configuración de email."""
		try:
			config = json.loads(config_json)

			if not isinstance(config, dict):
				return {"valid": False, "errors": ["Email config must be a JSON object"]}

			errors = []

			if "to" not in config:
				errors.append("Email config must include 'to' field")

			# Validar formato de email básico
			if "to" in config:
				email_pattern = re.compile(r"^[^@]+@[^@]+\.[^@]+$")
				emails = config["to"].split(",") if isinstance(config["to"], str) else [config["to"]]

				for email in emails:
					if not email_pattern.match(email.strip()):
						errors.append(f"Invalid email format: {email.strip()}")

			return {"valid": len(errors) == 0, "errors": errors}

		except json.JSONDecodeError:
			return {"valid": False, "errors": ["Invalid JSON format"]}

	def validate_rule_complete(self, rule):
		"""Validar regla completa (condiciones + acciones)."""
		validation_result = {
			"valid": True,
			"errors": [],
			"warnings": [],
			"conditions_validation": None,
			"actions_validation": None,
		}

		# Validar condiciones
		if rule.conditions:
			conditions_ast = self.parse_conditions(rule.conditions)
			if conditions_ast.get("type") == "error":
				validation_result["valid"] = False
				validation_result["errors"].append(f"Conditions error: {conditions_ast['error']}")
			else:
				validation_result["conditions_validation"] = conditions_ast

		# Validar acciones
		if rule.actions:
			actions_ast = self.parse_actions(rule.actions)
			if actions_ast.get("type") == "error":
				validation_result["valid"] = False
				validation_result["errors"].append(f"Actions error: {actions_ast['error']}")
			else:
				validation_result["actions_validation"] = actions_ast

		# Recopilar advertencias de condiciones y acciones
		if validation_result["conditions_validation"]:
			for node in validation_result["conditions_validation"].get("nodes", []):
				if node.get("validation", {}).get("warnings"):
					validation_result["warnings"].extend(node["validation"]["warnings"])

		if validation_result["actions_validation"]:
			for node in validation_result["actions_validation"].get("actions", []):
				if node.get("validation", {}).get("warnings"):
					validation_result["warnings"].extend(node["validation"]["warnings"])

		return validation_result

	def get_rule_complexity_score(self, rule):
		"""Calcular score de complejidad de regla."""
		score = 0

		# Complejidad por condiciones
		if rule.conditions:
			score += len(rule.conditions) * 2

			# Complejidad adicional por operadores complejos
			for condition in rule.conditions:
				if condition.operator in ["regex_match", "in_list", "not_in_list"]:
					score += 3
				elif condition.condition_type in ["Expression", "Custom"]:
					score += 5

		# Complejidad por acciones
		if rule.actions:
			score += len(rule.actions) * 1.5

			# Complejidad adicional por acciones complejas
			for action in rule.actions:
				if action.action_type in ["Call API", "Execute Script", "Create Document"]:
					score += 5
				elif action.action_type == "Send Email":
					score += 3

		# Clasificación de complejidad
		if score <= 5:
			complexity = "Simple"
		elif score <= 15:
			complexity = "Medium"
		elif score <= 30:
			complexity = "Complex"
		else:
			complexity = "Very Complex"

		return {
			"score": score,
			"complexity": complexity,
			"estimated_execution_time": score * 10,  # ms aproximado
		}
