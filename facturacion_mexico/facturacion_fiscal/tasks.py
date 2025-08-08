"""
Tareas programadas para Facturación Fiscal México
Incluye Recovery Worker para arquitectura resiliente
"""

import json
import os
from datetime import datetime
from typing import Any

import frappe
from frappe.utils import add_days, add_to_date, now, today


def cleanup_old_fiscal_events():
	"""Limpiar eventos fiscales antiguos - scheduled task."""
	try:
		frappe.logger().info("Ejecutando limpieza de eventos fiscales antiguos...")

		# TODO: Implementar lógica real cuando esté disponible
		# Por ejemplo: eliminar eventos fiscales de más de 30 días
		cutoff_date = add_days(today(), -30)

		frappe.logger().info(f"Limpieza configurada para eventos anteriores a: {cutoff_date}")

		return {"status": "success", "message": "Limpieza completada (placeholder)"}

	except Exception as e:
		frappe.log_error(f"Error en limpieza de eventos fiscales: {e}")
		return {"status": "error", "message": str(e)}


# =============================================================================
# RECOVERY WORKER - ARQUITECTURA RESILIENTE ESTADOS FISCALES
# =============================================================================


def process_timeout_recovery():
	"""
	Procesar recovery de timeouts PAC.
	Scheduled: cada 5 minutos
	"""
	try:
		frappe.logger().info("Iniciando proceso de recovery de timeouts PAC...")

		# Obtener recovery tasks pendientes de tipo timeout
		recovery_tasks = frappe.db.sql(
			"""
			SELECT name, reference_name, attempts, max_attempts, recovery_data
			FROM `tabFiscal Recovery Task`
			WHERE task_type = 'timeout_recovery'
			AND status = 'pending'
			AND scheduled_time <= %s
			AND attempts < max_attempts
			ORDER BY priority DESC, scheduled_time ASC
			LIMIT 100
		""",
			(now(),),
			as_dict=True,
		)

		processed = 0
		recovered = 0
		failed = 0

		for task in recovery_tasks:
			try:
				# Marcar como en procesamiento
				frappe.db.set_value("Fiscal Recovery Task", task.name, "status", "processing")
				frappe.db.commit()

				# Intentar recovery del timeout
				recovery_result = _attempt_timeout_recovery(task)

				# Actualizar task según resultado
				if recovery_result["success"]:
					frappe.db.set_value(
						"Fiscal Recovery Task",
						task.name,
						{"status": "completed", "completed_at": now(), "last_success": now()},
					)
					recovered += 1
					frappe.logger().info(f"✅ Recovery exitoso: {task.name}")
				else:
					# OPTIMIZACIÓN P2.2.2: Backoff más suave - Incrementar intentos y reprogramar
					new_attempts = task.attempts + 1
					next_scheduled = add_to_date(now(), minutes=2 * new_attempts)  # Backoff lineal suave

					if new_attempts >= task.max_attempts:
						# Máximo intentos alcanzado, marcar como failed
						frappe.db.set_value(
							"Fiscal Recovery Task",
							task.name,
							{
								"status": "failed",
								"last_error": recovery_result.get("error", "Max attempts reached"),
								"failed_at": now(),
							},
						)
						failed += 1
						frappe.logger().error(f"❌ Recovery fallido definitivamente: {task.name}")
					else:
						# Reprogramar para siguiente intento
						frappe.db.set_value(
							"Fiscal Recovery Task",
							task.name,
							{
								"status": "pending",
								"attempts": new_attempts,
								"scheduled_time": next_scheduled,
								"last_error": recovery_result.get("error", "Recovery attempt failed"),
							},
						)
						frappe.logger().warning(f"⚠️ Recovery fallido, reintentando: {task.name}")

				processed += 1
				frappe.db.commit()

			except Exception as e:
				frappe.log_error(
					f"Error procesando recovery task {task.name}: {e!s}", "Recovery Worker Error"
				)
				failed += 1

		result = {
			"status": "completed",
			"processed": processed,
			"recovered": recovered,
			"failed": failed,
			"timestamp": now(),
		}

		frappe.logger().info(
			f"Recovery de timeouts completado: {processed} procesados, {recovered} recuperados, {failed} fallidos"
		)
		return result

	except Exception as e:
		frappe.log_error(f"Error en process_timeout_recovery: {e!s}", "Recovery Worker Critical Error")
		return {"status": "error", "message": str(e)}


def process_sync_errors():
	"""
	Procesar errores de sincronización de estados.
	Scheduled: cada 10 minutos
	"""
	try:
		frappe.logger().info("Iniciando proceso de corrección de errores de sync...")

		# Obtener recovery tasks de sync pendientes
		sync_tasks = frappe.db.sql(
			"""
			SELECT name, reference_name, attempts, max_attempts, last_error
			FROM `tabFiscal Recovery Task`
			WHERE task_type = 'sync_error'
			AND status = 'pending'
			AND scheduled_time <= %s
			AND attempts < max_attempts
			ORDER BY priority DESC, scheduled_time ASC
			LIMIT 50
		""",
			(now(),),
			as_dict=True,
		)

		processed = 0
		synced = 0
		failed = 0

		for task in sync_tasks:
			try:
				# Marcar como en procesamiento
				frappe.db.set_value("Fiscal Recovery Task", task.name, "status", "processing")
				frappe.db.commit()

				# Intentar re-sync del documento
				sync_result = _attempt_sync_recovery(task)

				if sync_result["success"]:
					frappe.db.set_value(
						"Fiscal Recovery Task",
						task.name,
						{"status": "completed", "completed_at": now(), "last_success": now()},
					)
					synced += 1
					frappe.logger().info(f"✅ Sync recovery exitoso: {task.name}")
				else:
					# Incrementar intentos
					new_attempts = task.attempts + 1

					if new_attempts >= task.max_attempts:
						frappe.db.set_value(
							"Fiscal Recovery Task",
							task.name,
							{
								"status": "failed",
								"last_error": sync_result.get("error", "Max sync attempts reached"),
								"failed_at": now(),
							},
						)
						failed += 1
					else:
						# Reprogramar
						next_scheduled = add_to_date(now(), minutes=10 * new_attempts)
						frappe.db.set_value(
							"Fiscal Recovery Task",
							task.name,
							{
								"status": "pending",
								"attempts": new_attempts,
								"scheduled_time": next_scheduled,
								"last_error": sync_result.get("error", "Sync retry needed"),
							},
						)

				processed += 1
				frappe.db.commit()

			except Exception as e:
				frappe.log_error(f"Error procesando sync task {task.name}: {e!s}", "Sync Recovery Error")
				failed += 1

		result = {
			"status": "completed",
			"processed": processed,
			"synced": synced,
			"failed": failed,
			"timestamp": now(),
		}

		frappe.logger().info(
			f"Sync recovery completado: {processed} procesados, {synced} sincronizados, {failed} fallidos"
		)
		return result

	except Exception as e:
		frappe.log_error(f"Error en process_sync_errors: {e!s}", "Sync Recovery Critical Error")
		return {"status": "error", "message": str(e)}


def cleanup_old_logs():
	"""
	Limpiar logs antiguos de FacturAPI Response Log.
	Scheduled: diario a las 2 AM
	"""
	try:
		frappe.logger().info("Iniciando limpieza de logs antiguos...")

		# Obtener configuración de retención (default 90 días)
		retention_days = frappe.db.get_single_value("Facturacion Mexico Settings", "log_retention_days") or 90
		cutoff_date = add_days(today(), -retention_days)

		# Contar logs a archivar
		logs_to_archive = frappe.db.count("FacturAPI Response Log", filters={"timestamp": ["<", cutoff_date]})

		if logs_to_archive == 0:
			frappe.logger().info("No hay logs antiguos para archivar")
			return {"status": "completed", "archived": 0, "timestamp": now()}

		# Procesar en lotes para evitar timeout
		batch_size = 1000
		total_archived = 0

		while total_archived < logs_to_archive:
			# Obtener lote de logs antiguos
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

			# Crear resúmenes antes de eliminar (opcional)
			_create_log_summaries(old_logs)

			# Eliminar logs del lote
			log_names = [log.name for log in old_logs]
			frappe.db.sql(
				"""
				DELETE FROM `tabFacturAPI Response Log`
				WHERE name IN ({})
			""".format(", ".join(["%s"] * len(log_names))),
				log_names,
			)

			total_archived += len(old_logs)
			frappe.db.commit()

			frappe.logger().info(f"Archivados {total_archived} de {logs_to_archive} logs...")

			# Evitar timeout
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


# =============================================================================
# FUNCIONES HELPER RECOVERY WORKER
# =============================================================================


def _attempt_timeout_recovery(task: dict[str, Any]) -> dict[str, Any]:
	"""Intentar recovery de un timeout PAC específico."""
	try:
		# Obtener datos del recovery task
		response_log_name = task.get("reference_name")

		# Obtener log original
		response_log = frappe.get_doc("FacturAPI Response Log", response_log_name)

		# Consultar estado actual en PAC usando API
		try:
			from facturacion_mexico.facturacion_fiscal.api_client import query_pac_status

			pac_result = query_pac_status(response_log.factura_fiscal_mexico)
		except ImportError:
			# Si la función no existe aún, marcar como pendiente para implementación
			frappe.logger().warning(
				f"query_pac_status no implementado aún. Recovery task {task.name} se reprogramará."
			)
			return {
				"success": False,
				"error": "query_pac_status no está implementado. Pendiente de desarrollo.",
			}
		except Exception as e:
			# Cualquier otro error al consultar PAC
			frappe.logger().error(f"Error consultando PAC para recovery: {e!s}")
			return {"success": False, "error": f"Error al consultar PAC: {e!s}"}

		if pac_result.get("success"):
			# PAC respondió, actualizar estado
			from facturacion_mexico.facturacion_fiscal.api import write_pac_response

			# Simular response exitoso
			recovery_response = {
				"status_code": 200,
				"recovered_from_timeout": True,
				"original_timeout_log": response_log_name,
				**pac_result.get("data", {}),
			}

			write_pac_response(
				sales_invoice_name="RECOVERY",  # Placeholder
				request_data={"recovery": True},
				response_data=json.dumps(recovery_response),
				operation_type="consulta",
			)

			return {"success": True, "method": "pac_query_success"}
		else:
			return {"success": False, "error": pac_result.get("error", "PAC query failed")}

	except Exception as e:
		return {"success": False, "error": str(e)}


def _attempt_sync_recovery(task: dict[str, Any]) -> dict[str, Any]:
	"""Intentar recovery de un error de sincronización."""
	try:
		factura_fiscal_name = task.get("reference_name")

		# Recalcular estado usando Status Calculator
		from facturacion_mexico.facturacion_fiscal.utils import (
			calculate_current_status,
			should_override_status,
		)

		calculated = calculate_current_status(factura_fiscal_name)

		if calculated.get("status") != "Error":
			# Estado calculado exitosamente
			current_status = frappe.db.get_value(
				"Factura Fiscal Mexico", factura_fiscal_name, "fm_fiscal_status"
			)

			if should_override_status(current_status, calculated["status"], factura_fiscal_name):
				# Actualizar estado
				frappe.db.set_value(
					"Factura Fiscal Mexico",
					factura_fiscal_name,
					{
						"fm_fiscal_status": calculated["status"],
						"fm_sub_status": calculated.get("sub_status"),
						"fm_last_pac_sync": now(),
						"fm_sync_status": "synced",
					},
				)
				frappe.db.commit()

				return {"success": True, "method": "status_recalculated"}

		return {"success": False, "error": "Unable to calculate valid status"}

	except Exception as e:
		return {"success": False, "error": str(e)}


def _create_log_summaries(logs: list[dict[str, Any]]):
	"""Crear resúmenes de logs antes de archivar (opcional)."""
	try:
		# Agrupar por factura fiscal y crear estadísticas
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

			# Actualizar fechas
			if log.get("timestamp") < summary["first_operation"]:
				summary["first_operation"] = log.get("timestamp")
			if log.get("timestamp") > summary["last_operation"]:
				summary["last_operation"] = log.get("timestamp")

		# TODO: Guardar resúmenes si se requiere auditoría histórica
		# Por ahora solo logging
		frappe.logger().info(f"Creados resúmenes para {len(summaries)} documentos fiscales")

	except Exception as e:
		frappe.log_error(f"Error creando resúmenes de logs: {e!s}", "Log Summary Error")


def process_bulk_sync():
	"""
	Procesar sincronización masiva automática.
	Scheduled: cada 5 minutos junto con recovery jobs
	"""
	try:
		frappe.logger().info("Iniciando sincronización masiva automática...")

		# Importar función de sync
		from facturacion_mexico.facturacion_fiscal.utils import bulk_sync_invoices

		# Procesar lote de 50 documentos por vez
		result = bulk_sync_invoices(limit=50)

		if result.get("processed", 0) > 0:
			frappe.logger().info(
				f"Sync automático completado: {result.get('synced', 0)} sincronizados de {result.get('processed', 0)} procesados"
			)

		return result

	except Exception as e:
		frappe.log_error(f"Error en process_bulk_sync: {e!s}", "Auto Sync Error")
		return {"status": "error", "message": str(e)}
