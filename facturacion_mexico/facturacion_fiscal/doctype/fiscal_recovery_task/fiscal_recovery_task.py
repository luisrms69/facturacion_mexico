# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Fiscal Recovery Task
Propósito: Cola de recuperación automática para estados fiscales inconsistentes y timeouts PAC
"""

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, now


class FiscalRecoveryTask(Document):
	"""
	Cola de recuperación automática para estados fiscales inconsistentes.

	Funcionalidades principales:
	- Manejo de timeouts PAC con reintentos automáticos
	- Recuperación de estados inconsistentes
	- Escalamiento automático después de máximo de intentos
	- Scheduling inteligente con backoff exponencial
	"""

	def validate(self):
		"""Validaciones antes de guardar."""
		if self.attempts > self.max_attempts:
			frappe.throw("Intentos realizados no pueden exceder el máximo permitido")

		if not self.scheduled_time:
			self.scheduled_time = now()

	def before_save(self):
		"""Lógica antes de guardar."""
		if self.status == "failed" and self.attempts >= self.max_attempts:
			self.escalated_flag = 1

	@staticmethod
	def create_timeout_recovery_task(response_log_name, original_request_id=None):
		"""
		Crear tarea de recuperación por timeout PAC.

		Args:
		    response_log_name: Nombre del FacturAPI Response Log
		    original_request_id: ID original de la solicitud
		"""
		recovery_task = frappe.get_doc(
			{
				"doctype": "Fiscal Recovery Task",
				"task_type": "timeout_recovery",
				"reference_doctype": "FacturAPI Response Log",
				"reference_name": response_log_name,
				"priority": "high",
				"max_attempts": 3,
				"scheduled_time": add_to_date(now(), minutes=2),
				"created_by_system": 1,
				"recovery_data": frappe.as_json(
					{"original_request_id": original_request_id, "timeout_detected": now()}
				),
			}
		)
		recovery_task.insert()
		return recovery_task

	@staticmethod
	def create_sync_error_task(factura_fiscal_name, error_details):
		"""
		Crear tarea de recuperación por error de sincronización.

		Args:
		    factura_fiscal_name: Nombre de la Factura Fiscal Mexico
		    error_details: Detalles del error
		"""
		recovery_task = frappe.get_doc(
			{
				"doctype": "Fiscal Recovery Task",
				"task_type": "sync_error",
				"reference_doctype": "Factura Fiscal Mexico",
				"reference_name": factura_fiscal_name,
				"priority": "medium",
				"max_attempts": 5,
				"scheduled_time": add_to_date(now(), minutes=5),
				"created_by_system": 1,
				"last_error": str(error_details),
				"recovery_data": frappe.as_json({"sync_error_detected": now()}),
			}
		)
		recovery_task.insert()
		return recovery_task
