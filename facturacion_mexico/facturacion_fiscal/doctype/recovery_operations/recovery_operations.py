# Copyright (c) 2025, Buzola and contributors
# For license information, please see license.txt

import os
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, now, now_datetime


class RecoveryOperations(Document):
	def before_insert(self):
		"""Set default values before insert"""
		if not self.status:
			self.status = "Pending"

	def validate(self):
		"""Validate Recovery Operation before save"""
		if self.operation_type == "Manual Recovery Invoice" and not self.target_invoice:
			frappe.throw(_("Invoice Objetivo es requerida para Manual Recovery Invoice"))

	@staticmethod
	@frappe.whitelist()
	def manual_recovery_invoice(invoice_name):
		"""
		Forzar recovery manual de invoice específica.
		Migrado desde admin_tools.py manteniendo lógica exacta.

		Args:
			invoice_name (str): Nombre de Sales Invoice

		Returns:
			dict: Resultado operación
		"""
		try:
			# Verificar permisos
			if not frappe.has_permission("Fiscal Recovery Task", "create"):
				frappe.throw(_("Permisos insuficientes para recovery manual"))

			# Validar invoice existe
			if not frappe.db.exists("Sales Invoice", invoice_name):
				frappe.throw(_("Sales Invoice no encontrada: {0}").format(invoice_name))

			# Crear Recovery Operation document
			recovery_op = frappe.get_doc(
				{
					"doctype": "Recovery Operations",
					"operation_name": f"Manual Recovery - {invoice_name}",
					"operation_type": "Manual Recovery Invoice",
					"target_invoice": invoice_name,
					"status": "In Progress",
				}
			)
			recovery_op.insert()

			# Crear recovery task manual (lógica original)
			from facturacion_mexico.facturacion_fiscal.doctype.fiscal_recovery_task.fiscal_recovery_task import (
				FiscalRecoveryTask,
			)

			# Buscar FacturAPI Response Log asociado
			response_log = frappe.db.get_value(
				"FacturAPI Response Log", {"factura_fiscal_mexico": ["like", f"%{invoice_name}%"]}, "name"
			)

			if response_log:
				recovery_task = FiscalRecoveryTask.create_timeout_recovery_task(
					response_log, f"MANUAL_RECOVERY_{invoice_name}"
				)
			else:
				# Crear recovery task genérico
				recovery_task = frappe.get_doc(
					{
						"doctype": "Fiscal Recovery Task",
						"task_type": "manual_recovery",
						"reference_doctype": "Sales Invoice",
						"reference_name": invoice_name,
						"priority": "high",
						"max_attempts": 1,
						"scheduled_time": now(),
						"created_by_system": 0,  # Manual
						"recovery_data": frappe.as_json(
							{
								"manual_recovery": True,
								"requested_by": frappe.session.user,
								"requested_at": now(),
							}
						),
					}
				)
				recovery_task.insert()

			# Actualizar Recovery Operation con resultado
			recovery_op.result_message = f"Recovery task creada: {recovery_task.name}"
			recovery_op.status = "Completed"
			recovery_op.executed_at = now_datetime()
			recovery_op.save()

			return {
				"success": True,
				"recovery_task": recovery_task.name,
				"recovery_operation": recovery_op.name,
				"message": _("Recovery manual iniciado para {0}").format(invoice_name),
			}

		except Exception as e:
			frappe.log_error(f"Error recovery manual {invoice_name}: {e}", "Recovery Operations")
			frappe.throw(_("Error iniciando recovery manual: {0}").format(str(e)))

	@staticmethod
	@frappe.whitelist()
	def reprocess_pac_failures():
		"""
		Reprocesar todas las respuestas PAC fallidas recientes.
		Migrado desde admin_tools.py manteniendo lógica exacta.

		Returns:
			dict: Resultado operación
		"""
		try:
			# Verificar permisos System Manager
			if not frappe.has_permission("System Settings", "write"):
				frappe.throw(_("Permisos System Manager requeridos"))

			# Crear Recovery Operation document
			recovery_op = frappe.get_doc(
				{
					"doctype": "Recovery Operations",
					"operation_name": f"Reprocess PAC Failures - {now()}",
					"operation_type": "Reprocess PAC Failures",
					"status": "In Progress",
				}
			)
			recovery_op.insert()

			# Buscar PAC responses fallidas último 24h (lógica original)
			yesterday = add_days(now(), -1)
			failed_responses = frappe.get_all(
				"FacturAPI Response Log",
				filters={"success": 0, "creation": [">=", yesterday]},
				fields=["name", "factura_fiscal_mexico"],
			)

			recovery_tasks_created = 0

			for failed_response in failed_responses:
				try:
					# Crear recovery task para cada failure
					recovery_task = frappe.get_doc(
						{
							"doctype": "Fiscal Recovery Task",
							"task_type": "reprocess_failure",
							"reference_doctype": "FacturAPI Response Log",
							"reference_name": failed_response["name"],
							"priority": "medium",
							"max_attempts": 3,
							"scheduled_time": now(),
							"created_by_system": 0,  # Manual
							"recovery_data": frappe.as_json(
								{
									"reprocess_failure": True,
									"original_response": failed_response["name"],
									"requested_by": frappe.session.user,
									"requested_at": now(),
								}
							),
						}
					)
					recovery_task.insert()
					recovery_tasks_created += 1

				except Exception as task_error:
					frappe.log_error(
						f"Error creando recovery task para {failed_response['name']}: {task_error}",
						"Recovery Operations",
					)

			# Actualizar Recovery Operation con resultado
			message = _("Creadas {0} tareas de recovery para {1} failures").format(
				recovery_tasks_created, len(failed_responses)
			)
			recovery_op.result_message = message
			recovery_op.status = "Completed"
			recovery_op.executed_at = now_datetime()
			recovery_op.save()

			return {
				"success": True,
				"failures_found": len(failed_responses),
				"recovery_tasks_created": recovery_tasks_created,
				"recovery_operation": recovery_op.name,
				"message": message,
			}

		except Exception as e:
			frappe.log_error(f"Error reprocesando PAC failures: {e}", "Recovery Operations")
			frappe.throw(_("Error reprocesando PAC failures: {0}").format(str(e)))

	@staticmethod
	@frappe.whitelist()
	def cleanup_filesystem_fallback():
		"""
		Limpiar archivos filesystem fallback antiguos.
		Migrado desde admin_tools.py manteniendo lógica exacta.

		Returns:
			dict: Resultado operación
		"""
		try:
			# Verificar permisos System Manager
			if not frappe.has_permission("System Settings", "write"):
				frappe.throw(_("Permisos System Manager requeridos"))

			# Crear Recovery Operation document
			recovery_op = frappe.get_doc(
				{
					"doctype": "Recovery Operations",
					"operation_name": f"Cleanup Filesystem Fallback - {now()}",
					"operation_type": "Cleanup Filesystem Fallback",
					"status": "In Progress",
				}
			)
			recovery_op.insert()

			fallback_dir = "/tmp/facturacion_mexico_pac_fallback"

			if not os.path.exists(fallback_dir):
				message = _("Directorio fallback no existe")
				recovery_op.result_message = message
				recovery_op.status = "Completed"
				recovery_op.executed_at = now_datetime()
				recovery_op.save()

				return {
					"success": True,
					"files_cleaned": 0,
					"recovery_operation": recovery_op.name,
					"message": message,
				}

			files_cleaned = 0
			total_size_cleaned = 0

			# Limpiar archivos más antiguos de 7 días (lógica original)
			cutoff_date = datetime.now() - timedelta(days=7)

			for filename in os.listdir(fallback_dir):
				filepath = os.path.join(fallback_dir, filename)

				if os.path.isfile(filepath):
					file_modified = datetime.fromtimestamp(os.path.getmtime(filepath))

					if file_modified < cutoff_date:
						try:
							file_size = os.path.getsize(filepath)
							os.remove(filepath)
							files_cleaned += 1
							total_size_cleaned += file_size

						except Exception as file_error:
							frappe.log_error(
								f"Error eliminando archivo {filepath}: {file_error}",
								"Recovery Operations",
							)

			# Actualizar Recovery Operation con resultado
			message = _("Limpiados {0} archivos ({1} KB)").format(
				files_cleaned, round(total_size_cleaned / 1024, 2)
			)
			recovery_op.result_message = message
			recovery_op.status = "Completed"
			recovery_op.executed_at = now_datetime()
			recovery_op.save()

			return {
				"success": True,
				"files_cleaned": files_cleaned,
				"size_cleaned": round(total_size_cleaned / 1024, 2),  # KB
				"recovery_operation": recovery_op.name,
				"message": message,
			}

		except Exception as e:
			frappe.log_error(f"Error limpiando filesystem fallback: {e}", "Recovery Operations")
			frappe.throw(_("Error limpiando filesystem fallback: {0}").format(str(e)))

	@staticmethod
	@frappe.whitelist()
	def reset_recovery_tasks():
		"""
		Reset recovery tasks bloqueadas/stuck.
		Migrado desde admin_tools.py manteniendo lógica exacta.

		Returns:
			dict: Resultado operación
		"""
		try:
			# Verificar permisos System Manager
			if not frappe.has_permission("System Settings", "write"):
				frappe.throw(_("Permisos System Manager requeridos"))

			# Crear Recovery Operation document
			recovery_op = frappe.get_doc(
				{
					"doctype": "Recovery Operations",
					"operation_name": f"Reset Recovery Tasks - {now()}",
					"operation_type": "Reset Recovery Tasks",
					"status": "In Progress",
				}
			)
			recovery_op.insert()

			# Buscar tasks stuck (en progreso > 1 hora) - lógica original
			one_hour_ago = datetime.now() - timedelta(hours=1)

			stuck_tasks = frappe.get_all(
				"Fiscal Recovery Task",
				filters={
					"status": "In Progress",
					"modified": ["<", one_hour_ago.strftime("%Y-%m-%d %H:%M:%S")],
				},
				fields=["name", "task_type", "modified"],
			)

			tasks_reset = 0

			for task in stuck_tasks:
				try:
					# Reset task a Pending
					frappe.db.set_value(
						"Fiscal Recovery Task",
						task["name"],
						{
							"status": "Pending",
							"attempts": 0,
							"scheduled_time": now(),
							"last_error": "RESET: Task was stuck in progress > 1 hour",
						},
					)

					tasks_reset += 1

				except Exception as task_error:
					frappe.log_error(
						f"Error reseteando task {task['name']}: {task_error}", "Recovery Operations"
					)

			frappe.db.commit()

			# Actualizar Recovery Operation con resultado
			message = _("Reset {0} recovery tasks stuck").format(tasks_reset)
			recovery_op.result_message = message
			recovery_op.status = "Completed"
			recovery_op.executed_at = now_datetime()
			recovery_op.save()

			return {
				"success": True,
				"stuck_tasks_found": len(stuck_tasks),
				"tasks_reset": tasks_reset,
				"recovery_operation": recovery_op.name,
				"message": message,
			}

		except Exception as e:
			frappe.log_error(f"Error reseteando recovery tasks: {e}", "Recovery Operations")
			frappe.throw(_("Error reseteando recovery tasks: {0}").format(str(e)))
