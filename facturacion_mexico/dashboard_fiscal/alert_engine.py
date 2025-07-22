"""
Alert Engine - Dashboard Fiscal
Motor de evaluación y gestión de alertas del sistema fiscal
"""

import time
from datetime import datetime, timedelta

import frappe
from frappe import _

from .cache_manager import DashboardCache
from .dashboard_registry import DashboardRegistry


class AlertEngine:
	"""Motor de evaluación de alertas del dashboard fiscal"""

	def __init__(self, company=None):
		self.company = company or frappe.defaults.get_user_default("Company")
		self.cache_ttl = 900  # 15 minutos para alertas

	def evaluate_all_alerts(self, use_cache=True):
		"""Evaluar todas las alertas de todos los módulos"""
		try:
			cache_key = f"all_alerts_{self.company}"

			if use_cache:
				cached_result = DashboardCache.get(cache_key)
				if cached_result:
					return cached_result

			all_alerts = []

			# Evaluar reglas de alerta definidas en DocType
			rule_alerts = self.evaluate_rule_alerts()
			all_alerts.extend(rule_alerts)

			# Evaluar alertas de módulos registrados
			module_alerts = self.evaluate_module_alerts()
			all_alerts.extend(module_alerts)

			# Ordenar por prioridad (mayor prioridad primero)
			all_alerts.sort(key=lambda x: x.get("priority", 0), reverse=True)

			result = {
				"success": True,
				"alerts": all_alerts,
				"total_alerts": len(all_alerts),
				"critical_count": len([a for a in all_alerts if a.get("priority", 0) >= 8]),
				"warning_count": len([a for a in all_alerts if 5 <= a.get("priority", 0) < 8]),
				"info_count": len([a for a in all_alerts if a.get("priority", 0) < 5]),
				"company": self.company,
				"evaluated_at": datetime.now().isoformat(),
			}

			# Guardar en cache
			if use_cache:
				DashboardCache.set(cache_key, result, ttl=self.cache_ttl)

			return result

		except Exception as e:
			frappe.log_error(f"Error evaluando todas las alertas: {e!s}", "Alert Engine")
			return {"success": False, "error": str(e), "alerts": [], "total_alerts": 0}

	def evaluate_rule_alerts(self):
		"""Evaluar alertas basadas en reglas configuradas"""
		alerts = []

		try:
			# Obtener reglas de alerta activas
			rules = frappe.get_all(
				"Fiscal Alert Rule",
				filters={"is_active": 1},
				fields=[
					"name",
					"alert_name",
					"alert_code",
					"alert_type",
					"module",
					"condition_type",
					"condition_field",
					"condition_operator",
					"condition_value",
					"custom_condition",
					"message_template",
					"priority",
					"show_in_dashboard",
				],
			)

			for rule in rules:
				try:
					alert_result = self.evaluate_single_rule(rule)
					if alert_result and alert_result.get("triggered"):
						alert = self.format_rule_alert(rule, alert_result)
						alerts.append(alert)

						# Actualizar estadísticas de la regla
						self.update_rule_stats(rule["name"])

				except Exception as e:
					frappe.log_error(
						f"Error evaluando regla {rule.get('alert_name', rule.get('name'))}: {e!s}",
						"Alert Rule Evaluation",
					)

		except Exception as e:
			frappe.log_error(f"Error obteniendo reglas de alerta: {e!s}", "Alert Engine")

		return alerts

	def evaluate_single_rule(self, rule):
		"""Evaluar una regla de alerta individual"""
		try:
			if rule.get("custom_condition"):
				# Evaluar condición personalizada
				return self.evaluate_custom_condition(rule)
			else:
				# Evaluar condición estándar
				return self.evaluate_standard_condition(rule)

		except Exception as e:
			frappe.log_error(f"Error evaluando regla individual: {e!s}", "Alert Rule")
			return {"triggered": False, "error": str(e)}

	def evaluate_custom_condition(self, rule):
		"""Evaluar condición personalizada de Python"""
		try:
			# Preparar contexto de evaluación seguro
			context = {
				"frappe": frappe,
				"company": self.company,
				"datetime": datetime,
				"timedelta": timedelta,
				"rule": rule,
			}

			# Evaluar código personalizado de forma segura
			custom_code = rule.get("custom_condition", "").strip()

			if not custom_code:
				return {"triggered": False, "message": "No custom condition defined"}

			# Ejecutar condición personalizada
			exec(custom_code, {"__builtins__": {}}, context)

			# La condición debe definir una variable 'result'
			if "result" in context:
				return context["result"]
			else:
				return {"triggered": False, "message": "Custom condition did not return result"}

		except Exception as e:
			return {"triggered": False, "error": f"Custom condition error: {e!s}"}

	def evaluate_standard_condition(self, rule):
		"""Evaluar condición estándar basada en campos"""
		try:
			condition_type = rule.get("condition_type")
			condition_field = rule.get("condition_field")
			operator = rule.get("condition_operator")
			condition_value = rule.get("condition_value", 0)

			if not all([condition_type, condition_field, operator]):
				return {"triggered": False, "message": "Incomplete rule configuration"}

			# Obtener valor actual basado en el tipo de condición
			current_value = self.get_condition_value(rule, condition_type, condition_field)

			if current_value is None:
				return {"triggered": False, "message": "Could not retrieve condition value"}

			# Evaluar condición
			triggered = self.compare_values(current_value, operator, condition_value)

			return {
				"triggered": triggered,
				"current_value": current_value,
				"condition_value": condition_value,
				"operator": operator,
				"message": f"Current: {current_value}, Condition: {operator} {condition_value}",
			}

		except Exception as e:
			return {"triggered": False, "error": f"Standard condition error: {e!s}"}

	def get_condition_value(self, rule, condition_type, condition_field):
		"""Obtener valor actual para evaluar la condición"""
		try:
			if condition_type == "Count":
				return self.get_count_value(rule, condition_field)
			elif condition_type == "Percentage":
				return self.get_percentage_value(rule, condition_field)
			elif condition_type == "Amount":
				return self.get_amount_value(rule, condition_field)
			elif condition_type == "Days":
				return self.get_days_value(rule, condition_field)
			else:
				return None

		except Exception as e:
			frappe.log_error(f"Error obteniendo valor de condición: {e!s}", "Alert Condition")
			return None

	def get_count_value(self, rule, field):
		"""Obtener valor de conteo"""
		module = rule.get("module", "").lower()

		if "timbrado" in module:
			return frappe.db.count(
				"Sales Invoice",
				filters={
					"company": self.company,
					"docstatus": 1,
					"fm_timbrado_status": ["in", ["Error", "Pendiente"]],
				},
			)
		elif "ppd" in module:
			return frappe.db.count(
				"Payment Entry",
				filters={"company": self.company, "docstatus": 1, "fm_ppd_status": ["not in", ["Completed"]]},
			)
		else:
			# Conteo genérico
			return 0

	def get_percentage_value(self, rule, field):
		"""Obtener valor de porcentaje"""
		# Implementar cálculos de porcentaje específicos
		return 0.0

	def get_amount_value(self, rule, field):
		"""Obtener valor de monto"""
		# Implementar cálculos de montos específicos
		return 0.0

	def get_days_value(self, rule, field):
		"""Obtener valor de días"""
		# Implementar cálculos de días específicos
		return 0

	def compare_values(self, current_value, operator, condition_value):
		"""Comparar valores según el operador"""
		try:
			if operator == ">":
				return current_value > condition_value
			elif operator == "<":
				return current_value < condition_value
			elif operator == "=":
				return current_value == condition_value
			elif operator == "!=":
				return current_value != condition_value
			elif operator == ">=":
				return current_value >= condition_value
			elif operator == "<=":
				return current_value <= condition_value
			else:
				return False

		except Exception:
			return False

	def evaluate_module_alerts(self):
		"""Evaluar alertas de módulos registrados"""
		alerts = []

		try:
			# Obtener evaluadores de alerta registrados
			registered_alerts = DashboardRegistry.get_all_alert_evaluators()

			for module_name, evaluators in registered_alerts.items():
				for alert_name, evaluator_function in evaluators.items():
					try:
						alert_result = self.evaluate_module_alert(evaluator_function, module_name, alert_name)

						if alert_result and alert_result.get("triggered"):
							alert = self.format_module_alert(module_name, alert_name, alert_result)
							alerts.append(alert)

					except Exception as e:
						frappe.log_error(
							f"Error evaluando alerta {alert_name} de {module_name}: {e!s}",
							"Module Alert Evaluation",
						)

		except Exception as e:
			frappe.log_error(f"Error evaluando alertas de módulos: {e!s}", "Alert Engine")

		return alerts

	def evaluate_module_alert(self, evaluator_function, module_name, alert_name):
		"""Evaluar alerta de módulo individual"""
		try:
			# Preparar argumentos para el evaluador
			alert_args = {"company": self.company, "engine": self}

			# Ejecutar evaluador de alerta
			result = evaluator_function(**alert_args)

			if not isinstance(result, dict):
				return {"triggered": False}

			return result

		except Exception as e:
			return {"triggered": False, "error": str(e)}

	def format_rule_alert(self, rule, alert_result):
		"""Formatear alerta basada en regla"""
		try:
			# Procesar template del mensaje
			message = self.process_message_template(rule.get("message_template", ""), alert_result)

			return {
				"id": f"rule_{rule['name']}",
				"type": rule.get("alert_type", "warning").lower(),
				"module": rule.get("module", "Sistema"),
				"title": rule.get("alert_name", "Alerta"),
				"message": message,
				"priority": rule.get("priority", 5),
				"source": "rule",
				"rule_id": rule["name"],
				"timestamp": datetime.now().isoformat(),
				"data": alert_result.get("data", {}),
			}

		except Exception as e:
			return self.get_error_alert(f"Error formateando alerta: {e!s}")

	def format_module_alert(self, module_name, alert_name, alert_result):
		"""Formatear alerta de módulo"""
		try:
			return {
				"id": f"module_{module_name}_{alert_name}",
				"type": self.determine_alert_type(alert_result.get("priority", 5)),
				"module": module_name,
				"title": alert_name.replace("_", " ").title(),
				"message": alert_result.get("message", "Alerta del sistema"),
				"priority": alert_result.get("priority", 5),
				"source": "module",
				"timestamp": datetime.now().isoformat(),
				"data": alert_result.get("data", {}),
			}

		except Exception as e:
			return self.get_error_alert(f"Error formateando alerta de módulo: {e!s}")

	def process_message_template(self, template, alert_result):
		"""Procesar template de mensaje con variables"""
		try:
			if not template:
				return "Alerta activada"

			# Variables disponibles
			variables = {
				"company": self.company,
				"current_value": alert_result.get("current_value", ""),
				"condition_value": alert_result.get("condition_value", ""),
				"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
			}

			# Agregar datos adicionales de la alerta
			if "data" in alert_result:
				variables.update(alert_result["data"])

			# Reemplazar variables en el template
			message = template
			for key, value in variables.items():
				placeholder = "{" + str(key) + "}"
				message = message.replace(placeholder, str(value))

			return message

		except Exception as e:
			return f"Error procesando mensaje: {e!s}"

	def determine_alert_type(self, priority):
		"""Determinar tipo de alerta basado en prioridad"""
		if priority >= 8:
			return "error"
		elif priority >= 6:
			return "warning"
		elif priority >= 4:
			return "info"
		else:
			return "success"

	def update_rule_stats(self, rule_name):
		"""Actualizar estadísticas de una regla"""
		try:
			rule_doc = frappe.get_doc("Fiscal Alert Rule", rule_name)
			rule_doc.last_triggered = datetime.now()
			rule_doc.trigger_count = (rule_doc.trigger_count or 0) + 1
			rule_doc.save(ignore_permissions=True)

		except Exception as e:
			frappe.log_error(f"Error actualizando estadísticas de regla: {e!s}", "Alert Stats")

	def get_error_alert(self, error_message):
		"""Generar alerta de error estándar"""
		return {
			"id": f"error_{int(time.time())}",
			"type": "error",
			"module": "Sistema",
			"title": "Error del Sistema",
			"message": error_message,
			"priority": 9,
			"source": "system",
			"timestamp": datetime.now().isoformat(),
			"data": {},
		}

	def dismiss_alert(self, alert_id, user=None):
		"""Descartar una alerta"""
		try:
			if not user:
				user = frappe.session.user

			# Registrar que el usuario descartó la alerta
			dismissal_record = {
				"alert_id": alert_id,
				"dismissed_by": user,
				"dismissed_at": datetime.now(),
				"company": self.company,
			}

			# Guardar en cache temporal (1 hora) para no mostrar la alerta descartada
			cache_key = f"dismissed_alert_{alert_id}_{user}"
			DashboardCache.set(cache_key, dismissal_record, ttl=3600)

			return {"success": True, "message": _("Alerta descartada exitosamente")}

		except Exception as e:
			frappe.log_error(f"Error descartando alerta: {e!s}", "Alert Dismissal")
			return {"success": False, "error": str(e)}

	def is_alert_dismissed(self, alert_id, user=None):
		"""Verificar si una alerta fue descartada por el usuario"""
		try:
			if not user:
				user = frappe.session.user

			cache_key = f"dismissed_alert_{alert_id}_{user}"
			return DashboardCache.get(cache_key) is not None

		except Exception:
			return False

	def get_alert_summary(self):
		"""Obtener resumen de alertas para dashboard"""
		try:
			all_alerts_result = self.evaluate_all_alerts()

			if not all_alerts_result.get("success"):
				return {"error": "No se pudieron evaluar las alertas"}

			alerts = all_alerts_result.get("alerts", [])

			# Filtrar alertas descartadas para el usuario actual
			user = frappe.session.user
			active_alerts = [alert for alert in alerts if not self.is_alert_dismissed(alert["id"], user)]

			# Crear resumen por tipo
			summary = {
				"total": len(active_alerts),
				"critical": len([a for a in active_alerts if a.get("priority", 0) >= 8]),
				"warning": len([a for a in active_alerts if 5 <= a.get("priority", 0) < 8]),
				"info": len([a for a in active_alerts if a.get("priority", 0) < 5]),
				"by_module": {},
				"recent_alerts": active_alerts[:5],  # 5 más recientes
				"evaluated_at": all_alerts_result.get("evaluated_at"),
			}

			# Contar por módulo
			for alert in active_alerts:
				module = alert.get("module", "Sistema")
				summary["by_module"][module] = summary["by_module"].get(module, 0) + 1

			return summary

		except Exception as e:
			frappe.log_error(f"Error obteniendo resumen de alertas: {e!s}", "Alert Summary")
			return {"error": str(e)}

	@staticmethod
	def invalidate_cache(company=None):
		"""Invalidar cache de alertas"""
		pattern = f"*alerts_{company}*" if company else "*alerts_*"
		DashboardCache.invalidate_pattern(pattern)

	@staticmethod
	def schedule_alert_evaluation():
		"""Programar evaluación periódica de alertas"""
		try:
			companies = frappe.get_all("Company", pluck="name")

			for company in companies:
				engine = AlertEngine(company=company)
				engine.evaluate_all_alerts(use_cache=False)

			frappe.logger().info("Evaluación programada de alertas completada")

		except Exception as e:
			frappe.log_error(f"Error en evaluación programada: {e!s}", "Alert Scheduler")


# Funciones de utilidad para APIs
def get_alert_engine(company=None):
	"""Factory function para crear instancia del Alert Engine"""
	return AlertEngine(company=company)


def evaluate_all_alerts(company=None, use_cache=True):
	"""Función de conveniencia para evaluar todas las alertas"""
	engine = AlertEngine(company=company)
	return engine.evaluate_all_alerts(use_cache=use_cache)


def get_alert_summary(company=None):
	"""Función de conveniencia para obtener resumen de alertas"""
	engine = AlertEngine(company=company)
	return engine.get_alert_summary()


def dismiss_alert(alert_id, company=None, user=None):
	"""Función de conveniencia para descartar alerta"""
	engine = AlertEngine(company=company)
	return engine.dismiss_alert(alert_id, user=user)
