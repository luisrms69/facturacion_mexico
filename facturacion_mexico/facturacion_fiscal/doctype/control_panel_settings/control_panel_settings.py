# Copyright (c) 2025, Buzola and contributors
# For license information, please see license.txt

import json
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now


class ControlPanelSettings(Document):
	pass

	@staticmethod
	@frappe.whitelist()
	def get_alerts_configuration():
		"""
		Obtener configuración actual de alertas.
		Migrado desde admin_tools.py manteniendo lógica exacta.

		Returns:
			dict: Configuración alertas
		"""
		try:
			# Obtener de System Settings o crear default
			config = frappe.db.get_singles_dict("System Settings").get("fiscal_alerts_config")

			if config:
				return json.loads(config)
			else:
				# Configuración por defecto
				return {
					"pac_failure_threshold": 5,
					"recovery_tasks_threshold": 10,
					"response_time_threshold": 5000,
					"filesystem_usage_threshold": 80,
					"email_notifications": 1,
					"email_recipients": frappe.session.user,
					"system_notifications": 1,
					"webhook_notifications": 0,
					"webhook_url": "",
					"check_interval": "10 minutos",
					"alert_cooldown": 30,
				}
		except Exception as e:
			frappe.log_error(f"Error obteniendo configuración alertas: {e}", "Control Panel Settings")
			return {}

	@staticmethod
	@frappe.whitelist()
	def save_alerts_configuration(config):
		"""
		Guardar configuración de alertas.
		Migrado desde admin_tools.py manteniendo lógica exacta.

		Args:
			config (dict): Configuración alertas

		Returns:
			dict: Resultado operación
		"""
		try:
			# Verificar permisos System Manager
			if not frappe.has_permission("System Settings", "write"):
				frappe.throw(_("Permisos System Manager requeridos"))

			# Guardar en System Settings
			frappe.db.set_value(
				"System Settings", "System Settings", "fiscal_alerts_config", json.dumps(config)
			)
			frappe.db.commit()

			return {"success": True, "message": _("Configuración de alertas guardada correctamente")}

		except Exception as e:
			frappe.log_error(f"Error guardando configuración alertas: {e}", "Control Panel Settings")
			frappe.throw(_("Error guardando configuración de alertas: {0}").format(str(e)))

	@staticmethod
	@frappe.whitelist()
	def test_alerts_system():
		"""
		Test del sistema de alertas.
		Migrado desde admin_tools.py manteniendo lógica exacta.

		Returns:
			dict: Resultado test
		"""
		try:
			# Verificar permisos
			if not frappe.has_permission("System Settings", "read"):
				frappe.throw(_("Permisos insuficientes para test de alertas"))

			config = ControlPanelSettings.get_alerts_configuration()

			test_results = {"success": True, "tests": []}

			# Test email notifications
			if config.get("email_notifications"):
				try:
					frappe.sendmail(
						recipients=config.get("email_recipients", frappe.session.user).split(","),
						subject=_("Test Alerta Sistema Fiscal - {0}").format(frappe.utils.now()),
						message=_(
							"Esta es una alerta de prueba del sistema de estados fiscales resiliente.<br><br>Si recibes este email, las notificaciones están funcionando correctamente."
						),
						header=_("Test Alerta Sistema"),
					)
					test_results["tests"].append(
						{"type": "email", "status": "success", "message": _("Email de prueba enviado")}
					)
				except Exception as email_error:
					test_results["tests"].append(
						{
							"type": "email",
							"status": "error",
							"message": f"Error enviando email: {email_error}",
						}
					)

			# Test system notifications
			if config.get("system_notifications"):
				try:
					frappe.publish_realtime(
						event="fiscal_system_alert",
						message={
							"type": "test",
							"title": _("Test Alerta Sistema"),
							"message": _("Alerta de prueba del sistema fiscal"),
							"timestamp": now(),
						},
						user=frappe.session.user,
					)
					test_results["tests"].append(
						{"type": "system", "status": "success", "message": _("Notificación sistema enviada")}
					)
				except Exception as system_error:
					test_results["tests"].append(
						{
							"type": "system",
							"status": "error",
							"message": f"Error notificación sistema: {system_error}",
						}
					)

			# Test webhook notifications
			if config.get("webhook_notifications") and config.get("webhook_url"):
				try:
					import requests

					webhook_payload = {
						"text": f"🚨 Test Alerta Sistema Fiscal - {frappe.utils.now()}",
						"username": "Sistema Fiscal",
						"icon_emoji": ":warning:",
					}

					response = requests.post(config["webhook_url"], json=webhook_payload, timeout=5)

					if response.status_code == 200:
						test_results["tests"].append(
							{
								"type": "webhook",
								"status": "success",
								"message": _("Webhook enviado correctamente"),
							}
						)
					else:
						test_results["tests"].append(
							{
								"type": "webhook",
								"status": "error",
								"message": f"Webhook error: {response.status_code}",
							}
						)

				except Exception as webhook_error:
					test_results["tests"].append(
						{
							"type": "webhook",
							"status": "error",
							"message": f"Error webhook: {webhook_error}",
						}
					)

			return test_results

		except Exception as e:
			frappe.log_error(f"Error test sistema alertas: {e}", "Control Panel Settings")
			return {"success": False, "error": str(e)}

	@staticmethod
	@frappe.whitelist()
	def check_alert_conditions():
		"""
		Verificar condiciones de alerta y disparar si es necesario.
		Migrado desde admin_tools.py manteniendo lógica exacta.

		Returns:
			dict: Resultado verificación
		"""
		try:
			config = ControlPanelSettings.get_alerts_configuration()

			# Importar método migrado
			from facturacion_mexico.facturacion_fiscal.doctype.system_health_monitor.system_health_monitor import (
				SystemHealthMonitor,
			)

			metrics = SystemHealthMonitor.get_system_health_metrics()

			alerts_triggered = []

			# Verificar cada condición (lógica original exacta)

			# PAC Failure Rate
			if metrics["pac_success_rate"] < (100 - config["pac_failure_threshold"]):
				alerts_triggered.append(
					{
						"type": "pac_failure_rate",
						"severity": "critical",
						"title": _("PAC Failure Rate Crítica"),
						"message": _("Tasa de éxito PAC: {0}% (umbral: {1}%)").format(
							metrics["pac_success_rate"], 100 - config["pac_failure_threshold"]
						),
					}
				)

			# Recovery Tasks
			if metrics["recovery_tasks_pending"] > config["recovery_tasks_threshold"]:
				alerts_triggered.append(
					{
						"type": "recovery_tasks",
						"severity": "warning",
						"title": _("Recovery Tasks Acumuladas"),
						"message": _("{0} recovery tasks pendientes (umbral: {1})").format(
							metrics["recovery_tasks_pending"], config["recovery_tasks_threshold"]
						),
					}
				)

			# Response Time
			if metrics["avg_response_time"] > config["response_time_threshold"]:
				alerts_triggered.append(
					{
						"type": "response_time",
						"severity": "warning",
						"title": _("Tiempo Respuesta Alto"),
						"message": _("Tiempo promedio: {0}ms (umbral: {1}ms)").format(
							metrics["avg_response_time"], config["response_time_threshold"]
						),
					}
				)

			# Filesystem Usage
			if metrics["filesystem_usage"] > config["filesystem_usage_threshold"]:
				alerts_triggered.append(
					{
						"type": "filesystem_usage",
						"severity": "warning",
						"title": _("Filesystem Fallback Alto"),
						"message": _("Uso filesystem: {0}% (umbral: {1}%)").format(
							metrics["filesystem_usage"], config["filesystem_usage_threshold"]
						),
					}
				)

			# Procesar alertas disparadas
			new_alerts = 0
			for alert in alerts_triggered:
				if ControlPanelSettings.should_send_alert(alert["type"], config["alert_cooldown"]):
					ControlPanelSettings.send_alert(alert, config)
					ControlPanelSettings.record_alert_sent(alert["type"])
					new_alerts += 1

			return {"success": True, "alerts_checked": len(alerts_triggered), "new_alerts": new_alerts}

		except Exception as e:
			frappe.log_error(f"Error verificando condiciones alerta: {e}", "Control Panel Settings")
			return {"success": False, "error": str(e)}

	@staticmethod
	def should_send_alert(alert_type, cooldown_minutes):
		"""Verificar si debe enviarse alerta basado en cooldown - lógica original exacta"""
		try:
			# Buscar última alerta del mismo tipo
			last_alert = frappe.db.sql(
				"""
				SELECT creation FROM `tabError Log`
				WHERE method = 'Control Panel Settings Alert Sent'
				AND error = %s
				ORDER BY creation DESC
				LIMIT 1
			""",
				(alert_type,),
				as_dict=1,
			)

			if not last_alert:
				return True

			# Verificar cooldown
			last_alert_time = last_alert[0]["creation"]
			cooldown_time = datetime.now() - timedelta(minutes=cooldown_minutes)

			return last_alert_time < cooldown_time

		except Exception:
			return True  # En caso de error, permitir alerta

	@staticmethod
	def send_alert(alert, config):
		"""Enviar alerta por los canales configurados - lógica original exacta"""
		try:
			# Email
			if config.get("email_notifications"):
				frappe.sendmail(
					recipients=config.get("email_recipients", "").split(","),
					subject=f"🚨 {alert['title']} - Sistema Fiscal",
					message=f"""
						<h3>{alert['title']}</h3>
						<p><strong>Severidad:</strong> {alert['severity'].upper()}</p>
						<p><strong>Mensaje:</strong> {alert['message']}</p>
						<p><strong>Timestamp:</strong> {now()}</p>
						<hr>
						<p><small>Sistema de Estados Fiscales Resiliente</small></p>
					""",
				)

			# Sistema Frappe
			if config.get("system_notifications"):
				frappe.publish_realtime(
					event="fiscal_system_alert",
					message=alert,
					user=config.get("email_recipients", frappe.session.user).split(","),
				)

			# Webhook
			if config.get("webhook_notifications") and config.get("webhook_url"):
				import requests

				webhook_payload = {
					"text": f"🚨 {alert['title']}: {alert['message']}",
					"username": "Sistema Fiscal Resiliente",
				}

				requests.post(config["webhook_url"], json=webhook_payload, timeout=5)

		except Exception as e:
			frappe.log_error(f"Error enviando alerta: {e}", "Control Panel Settings")

	@staticmethod
	def record_alert_sent(alert_type):
		"""Registrar que se envió alerta para cooldown - lógica original exacta"""
		try:
			frappe.log_error(
				f"Alert sent: {alert_type} at {now()}", "Control Panel Settings Alert Sent", alert_type
			)
		except Exception:
			pass
