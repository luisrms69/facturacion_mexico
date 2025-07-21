"""
Rule Action - Sprint 4 Semana 2
Child DocType para acciones de reglas fiscales
"""

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class RuleAction(Document):
	"""Acción individual dentro de una regla fiscal."""

	def validate(self):
		"""Validaciones de la acción."""
		self.validate_action_syntax()
		self.validate_target_field()
		self.validate_action_value()

	def validate_action_syntax(self):
		"""Validar sintaxis de la acción."""
		if self.action_type == "Set Field" and not self.target_field:
			frappe.throw(_("Campo objetivo es requerido para acciones 'Set Field'"))

		if self.action_type in ["Show Error", "Show Warning", "Show Message"] and not self.action_value:
			frappe.throw(_("Mensaje es requerido para acciones de tipo '{0}'").format(self.action_type))

		if self.action_type == "Call API" and not self.action_value:
			frappe.throw(_("URL del API es requerida para acciones 'Call API'"))

		if self.action_type == "Execute Script" and not self.action_value:
			frappe.throw(_("Script es requerido para acciones 'Execute Script'"))

	def validate_target_field(self):
		"""Validar que el campo objetivo existe."""
		if self.action_type == "Set Field" and self.target_field:
			# Obtener el DocType padre para validar el campo
			parent_doc = self.get_parent_doc()
			if parent_doc and parent_doc.apply_to_doctype:
				doctype = parent_doc.apply_to_doctype

				# Verificar que el campo existe en el DocType
				if not frappe.db.exists("DocField", {"parent": doctype, "fieldname": self.target_field}):
					# Verificar si es un campo personalizado
					if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": self.target_field}):
						frappe.msgprint(
							_("Advertencia: El campo '{0}' no existe en {1}").format(
								self.target_field, doctype
							),
							indicator="orange",
						)

	def validate_action_value(self):
		"""Validar valor de la acción."""
		if self.action_type == "Call API" and self.action_value:
			# Validar que sea una URL válida
			if not self.action_value.startswith(("http://", "https://")):
				frappe.throw(_("URL del API debe comenzar con http:// o https://"))

		if self.action_type == "Send Email" and self.action_value:
			# Validar que contenga información de email
			try:
				email_config = json.loads(self.action_value)
				if not isinstance(email_config, dict):
					raise ValueError("Email config must be a dictionary")
				if "to" not in email_config:
					frappe.throw(_("Configuración de email debe incluir campo 'to'"))
			except json.JSONDecodeError:
				frappe.throw(_("Configuración de email debe ser JSON válido"))

	def execute_action(self, document, rule=None):
		"""Ejecutar la acción contra un documento."""
		try:
			execution_start = now_datetime()

			if self.action_type == "Set Field":
				result = self.execute_set_field(document)
			elif self.action_type == "Show Error":
				result = self.execute_show_error(document)
			elif self.action_type == "Show Warning":
				result = self.execute_show_warning(document)
			elif self.action_type == "Show Message":
				result = self.execute_show_message(document)
			elif self.action_type == "Call API":
				result = self.execute_call_api(document)
			elif self.action_type == "Execute Script":
				result = self.execute_script(document)
			elif self.action_type == "Send Email":
				result = self.execute_send_email(document)
			elif self.action_type == "Create Document":
				result = self.execute_create_document(document)
			else:
				result = {"success": False, "error": f"Action type '{self.action_type}' not implemented"}

			# Log de ejecución si está habilitado
			if self.log_action and rule:
				self.log_action_execution(rule, document, result, execution_start)

			return result

		except Exception as e:
			error_msg = str(e)

			# Log del error
			if self.log_action and rule:
				self.log_action_execution(
					rule, document, {"success": False, "error": error_msg}, execution_start
				)

			# Decidir si continuar o fallar
			if self.continue_on_error:
				return {"success": False, "error": error_msg, "continued": True}
			else:
				raise e

	def execute_set_field(self, document):
		"""Ejecutar acción Set Field."""
		if not self.target_field:
			return {"success": False, "error": "Target field not specified"}

		try:
			# Evaluar valor a establecer
			value_to_set = self.evaluate_action_value(document)

			# Establecer el valor
			if hasattr(document, self.target_field):
				setattr(document, self.target_field, value_to_set)
			elif isinstance(document, dict):
				document[self.target_field] = value_to_set
			else:
				return {"success": False, "error": f"Cannot set field {self.target_field} on document"}

			return {"success": True, "action": "set_field", "field": self.target_field, "value": value_to_set}

		except Exception as e:
			return {"success": False, "error": str(e)}

	def execute_show_error(self, document):
		"""Ejecutar acción Show Error."""
		message = self.evaluate_action_value(document)
		frappe.throw(_(message))

	def execute_show_warning(self, document):
		"""Ejecutar acción Show Warning."""
		message = self.evaluate_action_value(document)
		frappe.msgprint(_(message), indicator="orange", alert=True)
		return {"success": True, "action": "show_warning", "message": message}

	def execute_show_message(self, document):
		"""Ejecutar acción Show Message."""
		message = self.evaluate_action_value(document)
		frappe.msgprint(_(message), indicator="blue")
		return {"success": True, "action": "show_message", "message": message}

	def execute_call_api(self, document):
		"""Ejecutar acción Call API."""
		# Por seguridad, limitamos llamadas API en la implementación inicial
		return {"success": False, "error": "API calls not yet implemented for security reasons"}

	def execute_script(self, document):
		"""Ejecutar acción Execute Script."""
		# Por seguridad, deshabilitamos ejecución de scripts en la implementación inicial
		return {"success": False, "error": "Script execution not yet implemented for security reasons"}

	def execute_send_email(self, document):
		"""Ejecutar acción Send Email."""
		try:
			email_config = json.loads(self.action_value)

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

	def execute_create_document(self, document):
		"""Ejecutar acción Create Document."""
		# Por seguridad, limitamos creación de documentos en implementación inicial
		return {"success": False, "error": "Document creation not yet implemented"}

	def evaluate_action_value(self, document):
		"""Evaluar valor de la acción con sustituciones dinámicas."""
		if not self.action_value:
			return ""

		return self.evaluate_dynamic_value(self.action_value, document)

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

	def log_action_execution(self, rule, document, result, execution_start):
		"""Log de ejecución de la acción."""
		try:
			execution_time = (now_datetime() - execution_start).total_seconds() * 1000

			log_doc = frappe.get_doc(
				{
					"doctype": "Rule Execution Log",
					"rule": rule.name if hasattr(rule, "name") else str(rule),
					"document_type": document.get("doctype")
					if isinstance(document, dict)
					else document.doctype,
					"document_name": document.get("name") if isinstance(document, dict) else document.name,
					"action_type": self.action_type,
					"action_idx": self.idx,
					"execution_time": execution_time,
					"result": "Success" if result.get("success") else "Failed",
					"error_details": result.get("error") if not result.get("success") else None,
					"action_details": json.dumps(result),
				}
			)

			log_doc.insert(ignore_permissions=True)

		except Exception as e:
			frappe.log_error(f"Error logging action execution: {e}")

	def get_parent_doc(self):
		"""Obtener documento padre."""
		try:
			return frappe.get_doc("Fiscal Validation Rule", self.parent)
		except frappe.DoesNotExistError:
			return None

	def get_action_summary(self):
		"""Obtener resumen de la acción."""
		return {
			"action_type": self.action_type,
			"target_field": self.target_field,
			"has_value": bool(self.action_value),
			"continue_on_error": self.continue_on_error,
			"log_action": self.log_action,
			"description": self.description,
		}
