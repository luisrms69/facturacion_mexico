# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import json
import re
from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document


class FiscalAlertRule(Document):
	"""Regla de alerta fiscal con evaluación automática"""

	def validate(self):
		"""Validar configuración de la regla de alerta"""
		self.validate_alert_code()
		self.validate_condition_configuration()
		self.validate_message_template()
		self.validate_priority_range()

	def validate_alert_code(self):
		"""Validar que el código de alerta sea único y válido"""
		if not self.alert_code:
			frappe.throw(_("Código de alerta es requerido"))

		# Validar formato del código (solo alfanumérico y guiones bajos)
		if not re.match(r"^[a-zA-Z0-9_]+$", self.alert_code):
			frappe.throw(_("El código de alerta solo puede contener letras, números y guiones bajos"))

		# Verificar unicidad
		existing = frappe.get_all(
			"Fiscal Alert Rule", filters={"alert_code": self.alert_code, "name": ["!=", self.name]}, limit=1
		)

		if existing:
			frappe.throw(_("Ya existe una regla de alerta con el código: {0}").format(self.alert_code))

	def validate_condition_configuration(self):
		"""Validar configuración de condiciones"""
		if not self.condition_type:
			return

		if self.condition_type == "Custom":
			if not self.custom_condition:
				frappe.throw(_("Se requiere condición personalizada cuando el tipo es 'Custom'"))

			# Validar sintaxis básica de Python
			try:
				compile(self.custom_condition, "<string>", "eval")
			except SyntaxError as e:
				frappe.throw(_("Error de sintaxis en condición personalizada: {0}").format(str(e)))

		else:
			# Validar campos requeridos para condiciones estándar
			required_fields = ["condition_field", "condition_operator", "condition_value"]
			for field in required_fields:
				if not getattr(self, field, None):
					frappe.throw(_("Campo requerido para condición estándar: {0}").format(field))

	def validate_message_template(self):
		"""Validar plantilla de mensaje"""
		if not self.message_template:
			frappe.throw(_("Plantilla de mensaje es requerida"))

		# Verificar que las variables en el template sean válidas
		# Buscar patrones {variable_name}
		variables = re.findall(r"\{([^}]+)\}", self.message_template)

		# Validar que las variables no contengan caracteres peligrosos
		for var in variables:
			if not re.match(r"^[a-zA-Z0-9_]+$", var):
				frappe.throw(
					_(
						"Variable de template inválida: {0}. Solo se permiten letras, números y guiones bajos"
					).format(var)
				)

	def validate_priority_range(self):
		"""Validar que la prioridad esté en rango válido"""
		if self.priority and (self.priority < 1 or self.priority > 10):
			frappe.throw(_("La prioridad debe estar entre 1 y 10"))

	def evaluate_condition(self, context_data=None):
		"""
		Evaluar si la condición de la alerta se cumple

		Args:
			context_data: Datos del contexto para evaluar la condición

		Returns:
			bool: True si la condición se cumple, False si no
		"""
		try:
			if not self.is_active:
				return False

			if not context_data:
				context_data = {}

			if self.condition_type == "Custom":
				return self._evaluate_custom_condition(context_data)
			else:
				return self._evaluate_standard_condition(context_data)

		except Exception as e:
			frappe.log_error(
				title=f"Error evaluando alerta {self.alert_code}",
				message=f"Error: {e!s}\nContext: {context_data}",
			)
			return False

	def _evaluate_custom_condition(self, context_data):
		"""Evaluar condición personalizada de Python"""
		try:
			# Preparar namespace seguro para eval
			safe_namespace = {
				"context": context_data,
				"frappe": frappe,
				"datetime": datetime,
				"len": len,
				"int": int,
				"float": float,
				"str": str,
				"bool": bool,
				"max": max,
				"min": min,
				"sum": sum,
				"abs": abs,
			}

			# Evaluar condición
			result = eval(self.custom_condition, {"__builtins__": {}}, safe_namespace)
			return bool(result)

		except Exception as e:
			frappe.log_error(
				title=f"Error en condición personalizada - {self.alert_code}",
				message=f"Condición: {self.custom_condition}\nError: {e!s}",
			)
			return False

	def _evaluate_standard_condition(self, context_data):
		"""Evaluar condición estándar"""
		try:
			# Obtener valor del campo
			field_value = context_data.get(self.condition_field)

			if field_value is None:
				return False

			# Convertir valores para comparación
			try:
				field_value = float(field_value)
				condition_value = float(self.condition_value)
			except (ValueError, TypeError):
				# Si no son números, comparar como strings
				field_value = str(field_value)
				condition_value = str(self.condition_value)

			# Evaluar según operador
			operator_map = {
				">": lambda a, b: a > b,
				"<": lambda a, b: a < b,
				"=": lambda a, b: a == b,
				"!=": lambda a, b: a != b,
				">=": lambda a, b: a >= b,
				"<=": lambda a, b: a <= b,
			}

			operator_func = operator_map.get(self.condition_operator)
			if not operator_func:
				return False

			return operator_func(field_value, condition_value)

		except Exception as e:
			frappe.log_error(
				title=f"Error en condición estándar - {self.alert_code}",
				message=f"Field: {self.condition_field}, Operator: {self.condition_operator}, Value: {self.condition_value}\nError: {e!s}",
			)
			return False

	def format_message(self, context_data=None):
		"""
		Formatear mensaje de alerta con datos del contexto

		Args:
			context_data: Datos para reemplazar variables en el template

		Returns:
			str: Mensaje formateado
		"""
		try:
			if not context_data:
				context_data = {}

			# Reemplazar variables en el template
			formatted_message = self.message_template

			# Buscar y reemplazar variables {variable_name}
			variables = re.findall(r"\{([^}]+)\}", formatted_message)

			for var in variables:
				value = context_data.get(var, f"[{var}]")  # Placeholder si no hay valor
				formatted_message = formatted_message.replace(f"{{{var}}}", str(value))

			return formatted_message

		except Exception as e:
			frappe.log_error(
				title=f"Error formateando mensaje - {self.alert_code}",
				message=f"Template: {self.message_template}\nError: {e!s}",
			)
			return self.message_template  # Retornar template original en caso de error

	def trigger_alert(self, context_data=None):
		"""
		Activar la alerta y registrar el trigger

		Args:
			context_data: Datos del contexto que activó la alerta

		Returns:
			dict: Información de la alerta activada
		"""
		try:
			# Actualizar contador y timestamp
			self.trigger_count = (self.trigger_count or 0) + 1
			self.last_triggered = datetime.now()
			self.save(ignore_permissions=True)

			# Formatear mensaje
			formatted_message = self.format_message(context_data)

			# Crear datos de la alerta
			alert_data = {
				"alert_code": self.alert_code,
				"alert_name": self.alert_name,
				"alert_type": self.alert_type,
				"module": self.module,
				"message": formatted_message,
				"priority": self.priority,
				"triggered_at": self.last_triggered.isoformat(),
				"trigger_count": self.trigger_count,
				"context_data": context_data or {},
			}

			# Procesar notificaciones si están configuradas
			if self.send_email:
				self._send_email_notifications(alert_data)

			frappe.logger().info(f"Alerta activada: {self.alert_code} - {formatted_message}")

			return alert_data

		except Exception as e:
			frappe.log_error(
				title=f"Error activando alerta {self.alert_code}",
				message=f"Error: {e!s}\nContext: {context_data}",
			)
			return None

	def _send_email_notifications(self, alert_data):
		"""Enviar notificaciones por email"""
		try:
			# Obtener destinatarios
			recipients = self._get_notification_recipients()

			if not recipients:
				return

			# Preparar email
			subject = f"Alerta Fiscal: {alert_data['alert_name']}"
			message = f"""
			<h3>Alerta Fiscal Activada</h3>
			<p><strong>Tipo:</strong> {alert_data["alert_type"]}</p>
			<p><strong>Módulo:</strong> {alert_data["module"]}</p>
			<p><strong>Mensaje:</strong> {alert_data["message"]}</p>
			<p><strong>Prioridad:</strong> {alert_data["priority"]}</p>
			<p><strong>Fecha:</strong> {alert_data["triggered_at"]}</p>
			"""

			# Enviar email
			frappe.sendmail(
				recipients=recipients, subject=subject, message=message, header=["Alerta Fiscal", "orange"]
			)

		except Exception as e:
			frappe.log_error(
				title=f"Error enviando notificación email - {self.alert_code}", message=f"Error: {e!s}"
			)

	def _get_notification_recipients(self):
		"""Obtener lista de destinatarios para notificaciones"""
		recipients = []

		try:
			# Agregar usuarios específicos
			if self.notify_users:
				for user_row in self.notify_users:
					if user_row.user:
						recipients.append(user_row.user)

			# Agregar usuarios de roles
			if self.notify_roles:
				for role_row in self.notify_roles:
					if role_row.role:
						role_users = frappe.get_all(
							"Has Role",
							filters={"role": role_row.role, "parenttype": "User"},
							fields=["parent"],
						)
						recipients.extend([u.parent for u in role_users])

			# Remover duplicados y usuarios inactivos
			recipients = list(set(recipients))
			active_recipients = []

			for recipient in recipients:
				user = frappe.get_cached_doc("User", recipient)
				if user.enabled and user.email:
					active_recipients.append(user.email)

			return active_recipients

		except Exception as e:
			frappe.log_error(
				title=f"Error obteniendo destinatarios - {self.alert_code}", message=f"Error: {e!s}"
			)
			return []

	@staticmethod
	def get_active_rules(module=None):
		"""Obtener reglas activas, opcionalmente filtradas por módulo"""
		filters = {"is_active": 1}
		if module:
			filters["module"] = module

		return frappe.get_all(
			"Fiscal Alert Rule", filters=filters, fields=["*"], order_by="priority DESC, alert_name"
		)

	@staticmethod
	def evaluate_all_rules(context_data=None, module=None):
		"""
		Evaluar todas las reglas activas

		Args:
			context_data: Datos del contexto
			module: Módulo específico (opcional)

		Returns:
			list: Lista de alertas activadas
		"""
		activated_alerts = []

		try:
			active_rules = FiscalAlertRule.get_active_rules(module)

			for rule_data in active_rules:
				rule = frappe.get_doc("Fiscal Alert Rule", rule_data.name)

				if rule.evaluate_condition(context_data):
					alert_data = rule.trigger_alert(context_data)
					if alert_data:
						activated_alerts.append(alert_data)

			return activated_alerts

		except Exception as e:
			frappe.log_error(
				title="Error evaluando reglas de alerta",
				message=f"Error: {e!s}\nModule: {module}\nContext: {context_data}",
			)
			return []


# Child Tables para notificaciones


class FiscalAlertNotifyRole(Document):
	"""Tabla hijo para roles a notificar"""

	pass


class FiscalAlertNotifyUser(Document):
	"""Tabla hijo para usuarios a notificar"""

	pass
