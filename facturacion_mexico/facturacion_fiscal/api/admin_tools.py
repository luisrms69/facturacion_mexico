"""
Admin Tools API - Backend para Panel Control Estados Fiscales
Sistema centralizado de administración arquitectura resiliente
"""

import json
import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import add_days, now, now_datetime


@frappe.whitelist()
def get_system_health_metrics():
	"""
	Obtener métricas de salud del sistema resiliente.

	Returns:
		dict: Métricas completas sistema
	"""
	try:
		# Verificar permisos
		if not frappe.has_permission("FacturAPI Response Log", "read"):
			frappe.throw(_("Permisos insuficientes para acceder métricas sistema"))

		metrics = {}

		# PAC Success Rate (último 24h)
		yesterday = add_days(now(), -1)
		total_responses = frappe.db.count("FacturAPI Response Log", filters={"creation": [">=", yesterday]})
		successful_responses = frappe.db.count(
			"FacturAPI Response Log", filters={"creation": [">=", yesterday], "success": 1}
		)

		metrics["pac_success_rate"] = (
			round((successful_responses / total_responses * 100), 2) if total_responses > 0 else 100
		)

		# Average Response Time (último 24h)
		avg_response = frappe.db.sql(
			"""
			SELECT AVG(response_time_ms) as avg_time
			FROM `tabFacturAPI Response Log`
			WHERE creation >= %s AND response_time_ms > 0
		""",
			(yesterday,),
			as_dict=1,
		)

		metrics["avg_response_time"] = int(avg_response[0]["avg_time"]) if avg_response[0]["avg_time"] else 0

		# Failed Transactions (último 24h)
		metrics["failed_transactions"] = frappe.db.count(
			"FacturAPI Response Log", filters={"creation": [">=", yesterday], "success": 0}
		)

		# Last Updated
		metrics["last_updated"] = now()

		return metrics

	except Exception as e:
		frappe.log_error(f"Error obteniendo métricas sistema: {e}", "Admin Tools Health Metrics")
		frappe.throw(_("Error obteniendo métricas de salud del sistema"))


@frappe.whitelist()
def get_os_health_metrics():
	"""
	Obtener métricas de salud del sistema operativo.

	Returns:
		dict: Métricas OS completas
	"""
	try:
		# Verificar permisos System Manager
		if not frappe.has_permission("System Settings", "read"):
			frappe.throw(_("Permisos System Manager requeridos"))

		import psutil

		metrics = {}

		# Memory Usage
		memory = psutil.virtual_memory()
		metrics["memory_usage"] = {
			"total": round(memory.total / (1024**3), 2),  # GB
			"used": round(memory.used / (1024**3), 2),  # GB
			"percent": memory.percent,
		}

		# Disk Usage /tmp/
		disk_usage = psutil.disk_usage("/tmp")
		metrics["disk_usage"] = {
			"total": round(disk_usage.total / (1024**3), 2),  # GB
			"used": round(disk_usage.used / (1024**3), 2),  # GB
			"percent": round((disk_usage.used / disk_usage.total) * 100, 2),
		}

		# Database Connection Health
		try:
			frappe.db.sql("SELECT 1", as_dict=1)
			metrics["database_health"] = "healthy"
		except Exception:
			metrics["database_health"] = "unhealthy"

		# Background Jobs Status
		try:
			jobs_count = frappe.db.count("RQ Job")
			failed_jobs = frappe.db.count("RQ Job", filters={"status": "failed"})
			metrics["background_jobs"] = {
				"total": jobs_count,
				"failed": failed_jobs,
				"success_rate": round(((jobs_count - failed_jobs) / jobs_count * 100), 2)
				if jobs_count > 0
				else 100,
			}
		except Exception:
			metrics["background_jobs"] = {"total": 0, "failed": 0, "success_rate": 100}

		return metrics

	except ImportError:
		# psutil no disponible, métricas básicas
		return {
			"memory_usage": {"total": 0, "used": 0, "percent": 0},
			"disk_usage": {"total": 0, "used": 0, "percent": 0},
			"database_health": "unknown",
			"background_jobs": {"total": 0, "failed": 0, "success_rate": 100},
		}
	except Exception as e:
		frappe.log_error(f"Error obteniendo métricas OS: {e}", "Admin Tools OS Metrics")
		frappe.throw(_("Error obteniendo métricas sistema operativo"))


@frappe.whitelist()
def get_audit_trail(filters=None):
	"""
	Obtener audit trail con filtros.

	Args:
		filters (dict): Filtros búsqueda

	Returns:
		dict: Audit trail data
	"""
	try:
		# Verificar permisos
		if not frappe.has_permission("FacturAPI Response Log", "read"):
			frappe.throw(_("Permisos insuficientes para audit trail"))

		if filters:
			filters = json.loads(filters) if isinstance(filters, str) else filters
		else:
			filters = {}

		# Query base audit trail
		query_filters = {}

		# Aplicar filtros
		if filters.get("search"):
			search_term = f"%{filters['search']}%"
			query_filters["factura_fiscal_mexico"] = ["like", search_term]

		if filters.get("status"):
			query_filters["success"] = 1 if filters["status"] == "success" else 0

		if filters.get("date_from"):
			query_filters["creation"] = [">=", filters["date_from"]]

		# Obtener audit trail
		audit_entries = frappe.get_all(
			"FacturAPI Response Log",
			filters=query_filters,
			fields=[
				"name",
				"factura_fiscal_mexico",
				"success",
				"response_time_ms",
				"creation",
				"request_id",
				"operation_type",
				"error_message",
			],
			order_by="creation desc",
			limit=100,
		)

		# Enriquecer con información adicional
		for entry in audit_entries:
			# Status amigable
			entry["status_label"] = "Éxito" if entry["success"] else "Error"
			entry["status_color"] = "green" if entry["success"] else "red"

		return {"success": True, "audit_entries": audit_entries, "total_count": len(audit_entries)}

	except Exception as e:
		frappe.log_error(f"Error obteniendo audit trail: {e}", "Admin Tools Audit Trail")
		frappe.throw(_("Error obteniendo audit trail: {0}").format(str(e)))


@frappe.whitelist()
def get_alerts_configuration():
	"""
	Obtener configuración actual de alertas.

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
				"response_time_threshold": 5000,
				"email_notifications": 1,
				"email_recipients": frappe.session.user,
				"system_notifications": 1,
				"webhook_notifications": 0,
				"webhook_url": "",
				"check_interval": "10 minutos",
				"alert_cooldown": 30,
			}
	except Exception as e:
		frappe.log_error(f"Error obteniendo configuración alertas: {e}", "Admin Tools Alerts Config")
		return {}


@frappe.whitelist()
def save_alerts_configuration(config):
	"""
	Guardar configuración de alertas.

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
		frappe.db.set_single_value("System Settings", "fiscal_alerts_config", json.dumps(config))
		frappe.db.commit()

		return {"success": True, "message": _("Configuración de alertas guardada correctamente")}

	except Exception as e:
		frappe.log_error(f"Error guardando configuración alertas: {e}", "Admin Tools Save Alerts Config")
		frappe.throw(_("Error guardando configuración de alertas: {0}").format(str(e)))


@frappe.whitelist()
def test_alerts_system():
	"""
	Test del sistema de alertas.

	Returns:
		dict: Resultado test
	"""
	try:
		# Verificar permisos
		if not frappe.has_permission("System Settings", "read"):
			frappe.throw(_("Permisos insuficientes para test de alertas"))

		config = get_alerts_configuration()

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
					{"type": "webhook", "status": "error", "message": f"Error webhook: {webhook_error}"}
				)

		return test_results

	except Exception as e:
		frappe.log_error(f"Error test sistema alertas: {e}", "Admin Tools Test Alerts")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def check_alert_conditions():
	"""
	Verificar condiciones de alerta y disparar si es necesario.

	Returns:
		dict: Resultado verificación
	"""
	try:
		config = get_alerts_configuration()
		metrics = get_system_health_metrics()

		alerts_triggered = []

		# Verificar cada condición

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
			if should_send_alert(alert["type"], config["alert_cooldown"]):
				send_alert(alert, config)
				record_alert_sent(alert["type"])
				new_alerts += 1

		return {"success": True, "alerts_checked": len(alerts_triggered), "new_alerts": new_alerts}

	except Exception as e:
		frappe.log_error(f"Error verificando condiciones alerta: {e}", "Admin Tools Check Alerts")
		return {"success": False, "error": str(e)}


def should_send_alert(alert_type, cooldown_minutes):
	"""Verificar si debe enviarse alerta basado en cooldown."""
	try:
		# Buscar última alerta del mismo tipo
		last_alert = frappe.db.sql(
			"""
			SELECT creation FROM `tabError Log`
			WHERE method = 'Admin Tools Alert Sent'
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


def send_alert(alert, config):
	"""Enviar alerta por los canales configurados."""
	try:
		# Email
		if config.get("email_notifications"):
			frappe.sendmail(
				recipients=config.get("email_recipients", "").split(","),
				subject=f"🚨 {alert['title']} - Sistema Fiscal",
				message=f"""
					<h3>{alert["title"]}</h3>
					<p><strong>Severidad:</strong> {alert["severity"].upper()}</p>
					<p><strong>Mensaje:</strong> {alert["message"]}</p>
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
		frappe.log_error(f"Error enviando alerta: {e}", "Admin Tools Send Alert")


def record_alert_sent(alert_type):
	"""Registrar que se envió alerta para cooldown."""
	try:
		frappe.log_error(f"Alert sent: {alert_type} at {now()}", "Admin Tools Alert Sent", alert_type)
	except Exception:
		pass


def get_filesystem_usage(directory):
	"""
	Calcular porcentaje de uso del directorio filesystem.

	Args:
		directory (str): Path directorio

	Returns:
		float: Porcentaje uso
	"""
	try:
		if not os.path.exists(directory):
			return 0

		# Calcular tamaño total archivos
		total_size = 0
		for dirpath, _dirnames, filenames in os.walk(directory):
			for filename in filenames:
				filepath = os.path.join(dirpath, filename)
				try:
					total_size += os.path.getsize(filepath)
				except OSError:
					pass

		# Límite máximo 100MB para fallback
		max_size = 100 * 1024 * 1024  # 100MB
		usage_percent = (total_size / max_size) * 100

		return min(usage_percent, 100)  # Cap at 100%

	except Exception:
		return 0
