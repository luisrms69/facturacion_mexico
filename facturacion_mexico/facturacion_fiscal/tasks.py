"""
Tareas programadas para Facturación Fiscal México
"""

from typing import Any

import frappe
from frappe.utils import add_days, now, today


def cleanup_old_logs():
	"""
	Limpiar logs antiguos de FacturAPI Response Log.
	Scheduled: diario a las 2 AM
	"""
	try:
		frappe.logger().info("Iniciando limpieza de logs antiguos...")

		retention_days = frappe.db.get_single_value("Facturacion Mexico Settings", "log_retention_days") or 90
		cutoff_date = add_days(today(), -retention_days)

		logs_to_archive = frappe.db.count("FacturAPI Response Log", filters={"timestamp": ["<", cutoff_date]})

		if logs_to_archive == 0:
			frappe.logger().info("No hay logs antiguos para archivar")
			return {"status": "completed", "archived": 0, "timestamp": now()}

		batch_size = 1000
		total_archived = 0

		while total_archived < logs_to_archive:
			old_logs = frappe.db.sql(
				"""
				SELECT name, timestamp, operation_type, success, factura_fiscal_mexico
				FROM `tabFacturAPI Response Log`
				WHERE timestamp < %s
				ORDER BY timestamp ASC
				LIMIT %s
			""",
				(cutoff_date, batch_size),
				as_dict=True,
			)

			if not old_logs:
				break

			_create_log_summaries(old_logs)

			log_names = [log.name for log in old_logs]
			frappe.db.sql(
				"""
				DELETE FROM `tabFacturAPI Response Log`
				WHERE name IN ({})
			""".format(", ".join(["%s"] * len(log_names))),
				log_names,
			)

			total_archived += len(old_logs)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required for batch deletion to release locks between iterations

			frappe.logger().info(f"Archivados {total_archived} de {logs_to_archive} logs...")

			if total_archived % 5000 == 0:
				break

		result = {
			"status": "completed",
			"archived": total_archived,
			"retention_days": retention_days,
			"cutoff_date": str(cutoff_date),
			"timestamp": now(),
		}

		frappe.logger().info(
			f"Limpieza completada: {total_archived} logs archivados (retención: {retention_days} días)"
		)
		return result

	except Exception as e:
		frappe.log_error(f"Error en cleanup_old_logs: {e!s}", "Log Cleanup Critical Error")
		return {"status": "error", "message": str(e)}


def _create_log_summaries(logs: list[dict[str, Any]]):
	"""Create summaries of logs before archiving (optional)."""
	try:
		summaries = {}

		for log in logs:
			factura = log.get("factura_fiscal_mexico")
			if not factura:
				continue

			if factura not in summaries:
				summaries[factura] = {
					"total_operations": 0,
					"successful_operations": 0,
					"failed_operations": 0,
					"operation_types": set(),
					"first_operation": log.get("timestamp"),
					"last_operation": log.get("timestamp"),
				}

			summary = summaries[factura]
			summary["total_operations"] += 1

			if log.get("success"):
				summary["successful_operations"] += 1
			else:
				summary["failed_operations"] += 1

			summary["operation_types"].add(log.get("operation_type", "unknown"))

			if log.get("timestamp") < summary["first_operation"]:
				summary["first_operation"] = log.get("timestamp")
			if log.get("timestamp") > summary["last_operation"]:
				summary["last_operation"] = log.get("timestamp")

		frappe.logger().info(f"Creados resúmenes para {len(summaries)} documentos fiscales")

	except Exception as e:
		frappe.log_error(f"Error creando resúmenes de logs: {e!s}", "Log Summary Error")
