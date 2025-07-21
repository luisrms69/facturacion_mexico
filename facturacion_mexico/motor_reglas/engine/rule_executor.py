"""
Rule Executor - Sprint 4 Semana 2
Componente para ejecutar acciones de reglas fiscales
"""

import json
import time

import frappe
from frappe import _


class RuleExecutor:
	"""Ejecutor de acciones de reglas fiscales."""

	def __init__(self):
		self.execution_context = {}

	def execute_actions(self, actions, document, rule):
		"""Ejecutar todas las acciones de una regla."""
		if not actions:
			return {"actions_executed": 0, "success": True}

		execution_results = []
		successful_actions = 0
		failed_actions = 0

		for i, action in enumerate(actions):
			try:
				start_time = time.time()

				# Ejecutar acción individual
				if hasattr(action, "execute_action"):
					# Si la acción tiene su propio método de ejecución
					result = action.execute_action(document, rule)
				else:
					# Ejecución manual para compatibilidad
					result = self.manual_action_execution(action, document, rule)

				execution_time = (time.time() - start_time) * 1000

				# Agregar metadata de ejecución
				result["action_index"] = i + 1
				result["execution_time"] = execution_time
				result["action_type"] = action.action_type

				execution_results.append(result)

				if result.get("success"):
					successful_actions += 1
				else:
					failed_actions += 1

				# Si la acción falla y no debe continuar, detener ejecución
				if not result.get("success") and not action.continue_on_error:
					break

			except Exception as e:
				error_result = {
					"success": False,
					"error": str(e),
					"action_index": i + 1,
					"action_type": action.action_type,
					"execution_time": 0,
				}

				execution_results.append(error_result)
				failed_actions += 1

				# Si no debe continuar en error, detener
				if not action.continue_on_error:
					break

		return {
			"success": failed_actions == 0,
			"actions_executed": successful_actions + failed_actions,
			"successful_actions": successful_actions,
			"failed_actions": failed_actions,
			"results": execution_results,
		}

	def manual_action_execution(self, action, document, rule):
		"""Ejecución manual de acción para compatibilidad."""
		try:
			if action.action_type == "Set Field":
				return self.execute_set_field_manual(action, document)
			elif action.action_type == "Show Error":
				return self.execute_show_error_manual(action, document)
			elif action.action_type == "Show Warning":
				return self.execute_show_warning_manual(action, document)
			elif action.action_type == "Show Message":
				return self.execute_show_message_manual(action, document)
			elif action.action_type == "Call API":
				return self.execute_call_api_manual(action, document)
			elif action.action_type == "Execute Script":
				return self.execute_script_manual(action, document)
			elif action.action_type == "Send Email":
				return self.execute_send_email_manual(action, document)
			elif action.action_type == "Create Document":
				return self.execute_create_document_manual(action, document)
			else:
				return {"success": False, "error": f"Action type '{action.action_type}' not supported"}

		except Exception as e:
			return {"success": False, "error": str(e)}

	def execute_set_field_manual(self, action, document):
		"""Ejecutar acción Set Field manualmente."""
		if not action.target_field:
			return {"success": False, "error": "Target field not specified"}

		try:
			# Evaluar valor a establecer
			value_to_set = self.evaluate_action_value(action.action_value, document)

			# Establecer el valor
			if hasattr(document, action.target_field):
				setattr(document, action.target_field, value_to_set)
			elif isinstance(document, dict):
				document[action.target_field] = value_to_set
			else:
				return {"success": False, "error": f"Cannot set field {action.target_field} on document"}

			return {
				"success": True,
				"action": "set_field",
				"field": action.target_field,
				"value": value_to_set,
			}

		except Exception as e:
			return {"success": False, "error": str(e)}

	def execute_show_error_manual(self, action, document):
		"""Ejecutar acción Show Error manualmente."""
		message = self.evaluate_action_value(action.action_value, document)
		frappe.throw(_(message))

	def execute_show_warning_manual(self, action, document):
		"""Ejecutar acción Show Warning manualmente."""
		message = self.evaluate_action_value(action.action_value, document)
		frappe.msgprint(_(message), indicator="orange", alert=True)
		return {"success": True, "action": "show_warning", "message": message}

	def execute_show_message_manual(self, action, document):
		"""Ejecutar acción Show Message manualmente."""
		message = self.evaluate_action_value(action.action_value, document)
		frappe.msgprint(_(message), indicator="blue")
		return {"success": True, "action": "show_message", "message": message}

	def execute_call_api_manual(self, action, document):
		"""Ejecutar acción Call API manualmente."""
		# Por seguridad, limitamos llamadas API en implementación inicial
		return {"success": False, "error": "API calls not yet implemented for security reasons"}

	def execute_script_manual(self, action, document):
		"""Ejecutar acción Execute Script manualmente."""
		# Por seguridad, deshabilitamos ejecución de scripts
		return {"success": False, "error": "Script execution not yet implemented for security reasons"}

	def execute_send_email_manual(self, action, document):
		"""Ejecutar acción Send Email manualmente."""
		try:
			email_config = json.loads(action.action_value)

			# Evaluar campos dinámicos
			to_emails = self.evaluate_dynamic_value(email_config.get("to", ""), document)
			subject = self.evaluate_dynamic_value(email_config.get("subject", "Notification"), document)
			message = self.evaluate_dynamic_value(email_config.get("message", ""), document)

			# Enviar email
			frappe.sendmail(
				recipients=to_emails.split(",") if isinstance(to_emails, str) else [to_emails],
				subject=subject,
				message=message,
			)

			return {"success": True, "action": "send_email", "recipients": to_emails, "subject": subject}

		except Exception as e:
			return {"success": False, "error": str(e)}

	def execute_create_document_manual(self, action, document):
		"""Ejecutar acción Create Document manualmente."""
		# Por seguridad, limitamos creación de documentos
		return {"success": False, "error": "Document creation not yet implemented"}

	def evaluate_action_value(self, value, document):
		"""Evaluar valor de acción con sustituciones dinámicas."""
		if not value:
			return ""

		return self.evaluate_dynamic_value(value, document)

	def evaluate_dynamic_value(self, value, document):
		"""Evaluar valor dinámico con sustituciones."""
		if not isinstance(value, str):
			return value

		# Sustituciones de campos del documento
		import re

		field_pattern = r"\{([^}]+)\}"

		def replace_field(match):
			field_name = match.group(1)

			# Valores especiales
			if field_name == "TODAY":
				return frappe.utils.today()
			elif field_name == "NOW":
				return frappe.utils.now()
			elif field_name == "USER":
				return frappe.session.user
			elif field_name == "COMPANY":
				return frappe.defaults.get_user_default("Company") or ""

			# Campo del documento
			try:
				if hasattr(document, field_name):
					field_value = getattr(document, field_name)
				elif isinstance(document, dict) and field_name in document:
					field_value = document[field_name]
				else:
					return f"{{{field_name}}}"  # No reemplazar si no existe

				return str(field_value) if field_value is not None else ""
			except (AttributeError, KeyError):
				return f"{{{field_name}}}"

		return re.sub(field_pattern, replace_field, value)

	def validate_actions_syntax(self, actions):
		"""Validar sintaxis de todas las acciones."""
		validation_results = []

		for i, action in enumerate(actions):
			result = {"action_index": i + 1, "action_type": action.action_type, "valid": True, "errors": []}

			# Validaciones específicas por tipo
			if action.action_type == "Set Field":
				if not action.target_field:
					result["valid"] = False
					result["errors"].append("Target field is required")

			elif action.action_type in ["Show Error", "Show Warning", "Show Message"]:
				if not action.action_value:
					result["valid"] = False
					result["errors"].append("Message is required")

			elif action.action_type == "Call API":
				if not action.action_value:
					result["valid"] = False
					result["errors"].append("API URL is required")
				elif not action.action_value.startswith(("http://", "https://")):
					result["valid"] = False
					result["errors"].append("API URL must start with http:// or https://")

			elif action.action_type == "Send Email":
				if action.action_value:
					try:
						email_config = json.loads(action.action_value)
						if not isinstance(email_config, dict):
							result["valid"] = False
							result["errors"].append("Email config must be a JSON object")
						elif "to" not in email_config:
							result["valid"] = False
							result["errors"].append("Email config must include 'to' field")
					except json.JSONDecodeError:
						result["valid"] = False
						result["errors"].append("Email config must be valid JSON")

			validation_results.append(result)

		return {"all_valid": all(r["valid"] for r in validation_results), "results": validation_results}

	def get_execution_summary(self, actions, document, rule):
		"""Obtener resumen de ejecución sin ejecutar realmente."""
		summary = {
			"total_actions": len(actions) if actions else 0,
			"action_types": {},
			"estimated_execution_time": 0,
			"potential_issues": [],
		}

		if not actions:
			return summary

		# Contar tipos de acciones
		for action in actions:
			action_type = action.action_type
			if action_type not in summary["action_types"]:
				summary["action_types"][action_type] = 0
			summary["action_types"][action_type] += 1

		# Estimar tiempo de ejecución (muy aproximado)
		execution_time_estimates = {
			"Set Field": 10,  # ms
			"Show Error": 5,
			"Show Warning": 5,
			"Show Message": 5,
			"Call API": 500,
			"Execute Script": 100,
			"Send Email": 1000,
			"Create Document": 200,
		}

		for action_type, count in summary["action_types"].items():
			estimated_time = execution_time_estimates.get(action_type, 50)
			summary["estimated_execution_time"] += estimated_time * count

		# Detectar problemas potenciales
		if "Show Error" in summary["action_types"]:
			summary["potential_issues"].append(
				"Rule contains error actions that will stop document processing"
			)

		if "Execute Script" in summary["action_types"]:
			summary["potential_issues"].append(
				"Rule contains script execution (currently disabled for security)"
			)

		if "Call API" in summary["action_types"]:
			summary["potential_issues"].append("Rule contains API calls (currently disabled for security)")

		# Validar sintaxis
		validation = self.validate_actions_syntax(actions)
		if not validation["all_valid"]:
			summary["potential_issues"].append("Rule contains actions with syntax errors")
			summary["validation_errors"] = validation["results"]

		return summary
