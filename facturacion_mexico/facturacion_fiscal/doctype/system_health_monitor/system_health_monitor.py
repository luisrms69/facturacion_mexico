# Copyright (c) 2025, Buzola and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, now


class SystemHealthMonitor(Document):
	pass

	@staticmethod
	@frappe.whitelist()
	def get_system_health_metrics():
		"""
		Obtener métricas de salud del sistema resiliente.
		Migrado desde admin_tools.py manteniendo lógica exacta.

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
			total_responses = frappe.db.count(
				"FacturAPI Response Log", filters={"creation": [">=", yesterday]}
			)
			successful_responses = frappe.db.count(
				"FacturAPI Response Log", filters={"creation": [">=", yesterday], "success": 1}
			)

			metrics["pac_success_rate"] = (
				round((successful_responses / total_responses * 100), 2) if total_responses > 0 else 100
			)

			# Recovery Tasks Pendientes
			metrics["recovery_tasks_pending"] = frappe.db.count(
				"Fiscal Recovery Task", filters={"status": ["in", ["Pending", "In Progress"]]}
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

			metrics["avg_response_time"] = (
				int(avg_response[0]["avg_time"]) if avg_response[0]["avg_time"] else 0
			)

			# Failed Transactions (último 24h)
			metrics["failed_transactions"] = frappe.db.count(
				"FacturAPI Response Log", filters={"creation": [">=", yesterday], "success": 0}
			)

			# Filesystem Fallback Usage
			fallback_dir = "/tmp/facturacion_mexico_pac_fallback"
			from facturacion_mexico.facturacion_fiscal.api.admin_tools import get_filesystem_usage

			filesystem_usage = get_filesystem_usage(fallback_dir)
			metrics["filesystem_usage"] = filesystem_usage

			# Last Updated
			metrics["last_updated"] = now()

			return metrics

		except Exception as e:
			frappe.log_error(f"Error obteniendo métricas sistema: {str(e)}", "System Health Monitor")
			frappe.throw(_("Error obteniendo métricas de salud del sistema"))

	@staticmethod
	@frappe.whitelist()
	def get_os_health_metrics():
		"""
		Obtener métricas de salud del sistema operativo.
		Migrado desde admin_tools.py manteniendo lógica exacta.

		Returns:
			dict: Métricas OS completas
		"""
		try:
			# Verificar permisos System Manager
			if not frappe.has_permission("System Settings", "read"):
				frappe.throw(_("Permisos System Manager requeridos"))

			try:
				import psutil
			except ImportError:
				# psutil no disponible, métricas básicas
				return {
					"memory_usage": {"total": 0, "used": 0, "percent": 0},
					"disk_usage": {"total": 0, "used": 0, "percent": 0},
					"database_health": "unknown",
					"background_jobs": {"total": 0, "failed": 0, "success_rate": 100},
				}

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

		except Exception as e:
			frappe.log_error(f"Error obteniendo métricas OS: {str(e)}", "System Health Monitor")
			frappe.throw(_("Error obteniendo métricas sistema operativo"))
