# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
DocType: Fiscal Recovery Task
Propósito: Cola de recuperación automática para estados fiscales inconsistentes
Principio: Recuperación automática con límites estrictos y escalación
"""

from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.model.document import Document


class FiscalRecoveryTask(Document):
	"""
	Cola de recuperación para estados fiscales inconsistentes y timeouts PAC.

	Funcionalidades principales:
	- Recuperación automática de timeouts PAC
	- Sincronización de estados desincronizados
	- Control estricto de reintentos (máximo 3)
	- Escalación automática a soporte manual
	- Priorización inteligente de tareas
	- Logging detallado de intentos

	Tipos de tareas soportadas:
	- timeout_recovery: Recuperar requests que dieron timeout
	- sync_error: Corregir desincronizaciones de estado
	- manual_fix: Tareas que requieren intervención manual
	- state_corruption: Estados fiscales corruptos
	- orphaned_response: Respuestas PAC sin documento asociado

	Flujo de procesamiento:
	1. Tarea creada automáticamente por sistema
	2. Recovery worker procesa según scheduled_time
	3. Si falla, incrementa attempts y reagenda
	4. Si excede max_attempts, escala a manual
	5. Log detallado de todos los intentos

	Ejemplo de uso:
		# Crear tarea de recovery para timeout
		recovery_task = frappe.get_doc({
			"doctype": "Fiscal Recovery Task",
			"task_type": "timeout_recovery",
			"reference_doctype": "FacturAPI Response Log",
			"reference_name": "PAC-LOG-2025-08-12345",
			"priority": "high",
			"max_attempts": 3,
			"scheduled_time": frappe.utils.add_to_date(frappe.utils.now(), minutes=5)
		})
		recovery_task.insert(ignore_permissions=True)
	"""

	def autoname(self):
		"""
		Generar nombre automático usando naming series.
		Formato: RECOVERY-YYYY-MM-#####
		"""
		pass  # Frappe maneja naming_series automáticamente

	def before_insert(self):
		"""
		Validaciones antes de crear la tarea.

		- Establecer created_by_system automáticamente
		- Validar que scheduled_time esté en el futuro
		- Establecer defaults inteligentes
		"""
		# Establecer usuario que creó la tarea
		if not self.created_by_system:
			self.created_by_system = frappe.session.user

		# Validar que scheduled_time esté en el futuro
		if self.scheduled_time:
			now = frappe.utils.now()
			if frappe.utils.get_datetime(self.scheduled_time) <= frappe.utils.get_datetime(now):
				frappe.throw(
					_("Scheduled time debe estar en el futuro. Actual: {0}").format(self.scheduled_time),
					frappe.ValidationError,
				)

		# Establecer defaults inteligentes según task_type
		if self.task_type == "timeout_recovery" and not self.priority:
			self.priority = "high"  # Timeouts son alta prioridad

		if not self.max_attempts:
			self.max_attempts = 3  # Default según arquitectura

	def validate(self):
		"""
		Validaciones de negocio críticas.

		- Validar que reference_doctype/reference_name existan
		- Validar max_attempts no exceda límites
		- Validar consistencia de estado
		- Prevenir tareas duplicadas
		"""
		# Validar que el documento de referencia existe
		if self.reference_doctype and self.reference_name:
			if not frappe.db.exists(self.reference_doctype, self.reference_name):
				frappe.throw(
					_("Documento de referencia {0} {1} no existe").format(
						self.reference_doctype, self.reference_name
					),
					frappe.ValidationError,
				)

		# Validar max_attempts dentro de límites razonables
		if self.max_attempts > 5:
			frappe.throw(
				_("max_attempts no puede exceder 5. Valor actual: {0}").format(self.max_attempts),
				frappe.ValidationError,
			)

		# Validar que attempts no exceda max_attempts
		if self.attempts > self.max_attempts:
			self.status = "exceeded_attempts"
			if not self.escalated_flag:
				self.escalate_to_manual()

		# Prevenir tareas duplicadas para el mismo documento
		if self.is_new() and self.status == "pending":
			existing = frappe.get_all(
				"Fiscal Recovery Task",
				filters={
					"reference_doctype": self.reference_doctype,
					"reference_name": self.reference_name,
					"task_type": self.task_type,
					"status": ["in", ["pending", "processing"]],
					"name": ["!=", self.name],
				},
			)

			if existing:
				frappe.throw(
					_("Ya existe una tarea de recuperación activa para {0} {1}").format(
						self.reference_doctype, self.reference_name
					),
					frappe.ValidationError,
				)

	def before_save(self):
		"""
		Validaciones finales antes de guardar.

		- Actualizar processing_notes con cambios
		- Validar transiciones de estado
		- Calcular próximo intento si es necesario
		"""
		# Actualizar processing_notes con cambios de estado
		if not self.is_new():
			old_doc = self.get_doc_before_save()
			if old_doc and old_doc.status != self.status:
				note = f"[{frappe.utils.now()}] Estado cambiado: {old_doc.status} → {self.status}"
				if self.processing_notes:
					self.processing_notes += f"\n{note}"
				else:
					self.processing_notes = note

		# Validar transiciones de estado válidas
		valid_transitions = {
			"pending": ["processing", "failed", "exceeded_attempts"],
			"processing": ["completed", "failed", "pending", "exceeded_attempts"],
			"failed": ["pending", "exceeded_attempts"],
			"completed": [],  # Estado final
			"exceeded_attempts": [],  # Estado final
		}

		if not self.is_new():
			old_doc = self.get_doc_before_save()
			if old_doc and old_doc.status in valid_transitions:
				if self.status not in valid_transitions[old_doc.status]:
					frappe.throw(
						_("Transición de estado inválida: {0} → {1}").format(old_doc.status, self.status),
						frappe.ValidationError,
					)

	def on_update(self):
		"""
		Acciones después de actualizar.

		- Log crítico de cambios de estado
		- Notificaciones para estados críticos
		- Programar próximo intento si es necesario
		"""
		# Log crítico de cambios
		frappe.logger("fiscal_recovery").info(
			f"Fiscal Recovery Task actualizada: {self.name} | "
			f"Type: {self.task_type} | Status: {self.status} | "
			f"Attempts: {self.attempts}/{self.max_attempts}"
		)

		# Notificación para estados críticos
		if self.status == "exceeded_attempts" and not self.escalated_flag:
			self.escalate_to_manual()

		# Si es high priority y falló, reagendar más rápido
		if self.status == "failed" and self.priority == "high":
			self.reschedule_urgent()

	def mark_as_processing(self):
		"""
		Marcar tarea como en procesamiento.

		Actualiza estado y timestamp para evitar procesamiento concurrente.
		"""
		self.status = "processing"
		self.last_attempt = frappe.utils.now()
		self.save(ignore_permissions=True)
		frappe.db.commit()

	def mark_as_completed(self, resolution_notes=None):
		"""
		Marcar tarea como completada exitosamente.

		Args:
			resolution_notes (str): Notas sobre cómo se resolvió
		"""
		self.status = "completed"
		if resolution_notes:
			self.resolution_notes = resolution_notes

		# Log final en processing_notes
		completion_note = (
			f"[{frappe.utils.now()}] ✅ COMPLETADO: {resolution_notes or 'Sin notas adicionales'}"
		)
		if self.processing_notes:
			self.processing_notes += f"\n{completion_note}"
		else:
			self.processing_notes = completion_note

		self.save(ignore_permissions=True)
		frappe.db.commit()

		frappe.logger("fiscal_recovery").info(f"Recovery task completada: {self.name} - {self.task_type}")

	def mark_as_failed(self, error_message, error_details=None, should_retry=True):
		"""
		Marcar tarea como fallida e incrementar contador.

		Args:
			error_message (str): Mensaje de error legible
			error_details (dict): Detalles técnicos del error
			should_retry (bool): Si debe reagendarse para reintento
		"""
		self.attempts += 1
		self.last_error = error_message
		self.last_attempt = frappe.utils.now()

		if error_details:
			import json

			self.error_details = json.dumps(error_details, ensure_ascii=False, indent=2)

		# Determinar siguiente acción
		if self.attempts >= self.max_attempts:
			self.status = "exceeded_attempts"
			if not self.escalated_flag:
				self.escalate_to_manual()
		elif should_retry:
			self.status = "pending"
			self.reschedule_for_retry()
		else:
			self.status = "failed"

		# Log en processing_notes
		error_note = f"[{frappe.utils.now()}] ❌ FALLO #{self.attempts}: {error_message}"
		if self.processing_notes:
			self.processing_notes += f"\n{error_note}"
		else:
			self.processing_notes = error_note

		self.save(ignore_permissions=True)
		frappe.db.commit()

		frappe.logger("fiscal_recovery").error(
			f"Recovery task falló: {self.name} - Intento {self.attempts}/{self.max_attempts} - {error_message}"
		)

	def reschedule_for_retry(self):
		"""
		Reagendar tarea para próximo intento con backoff exponencial.

		- Intento 1: +2 minutos
		- Intento 2: +5 minutos
		- Intento 3: +10 minutos
		"""
		backoff_minutes = {1: 2, 2: 5, 3: 10}

		delay_minutes = backoff_minutes.get(self.attempts, 10)

		# Para tareas high priority, reducir delay
		if self.priority == "high":
			delay_minutes = max(1, delay_minutes // 2)

		new_scheduled_time = frappe.utils.add_to_date(frappe.utils.now(), minutes=delay_minutes)

		self.scheduled_time = new_scheduled_time

		frappe.logger("fiscal_recovery").info(
			f"Recovery task reagendada: {self.name} para {new_scheduled_time} (delay: {delay_minutes}min)"
		)

	def reschedule_urgent(self):
		"""
		Reagendar tarea urgente para procesamiento inmediato.

		Para tareas críticas que fallaron y necesitan procesamiento rápido.
		"""
		urgent_delay = 1  # 1 minuto
		new_scheduled_time = frappe.utils.add_to_date(frappe.utils.now(), minutes=urgent_delay)

		self.scheduled_time = new_scheduled_time
		self.save(ignore_permissions=True)
		frappe.db.commit()

		frappe.logger("fiscal_recovery").warning(
			f"Recovery task URGENT reagendada: {self.name} para procesamiento en {urgent_delay}min"
		)

	def escalate_to_manual(self):
		"""
		Escalar tarea a intervención manual.

		Se llama automáticamente cuando se exceden max_attempts.
		"""
		self.escalated_flag = 1

		# Asignar a Fiscal Manager si no hay asignado
		if not self.assigned_to:
			fiscal_managers = frappe.get_all(
				"Has Role", filters={"role": "Fiscal Manager"}, fields=["parent"]
			)

			if fiscal_managers:
				self.assigned_to = fiscal_managers[0].parent

		# Log de escalación
		escalation_note = f"[{frappe.utils.now()}] 🚨 ESCALADO: Excedidos {self.max_attempts} intentos - Requiere intervención manual"
		if self.processing_notes:
			self.processing_notes += f"\n{escalation_note}"
		else:
			self.processing_notes = escalation_note

		# TODO: Enviar notificación/email al Fiscal Manager
		# frappe.sendmail(...)

		frappe.logger("fiscal_recovery").warning(
			f"Recovery task ESCALADA: {self.name} - {self.task_type} requiere intervención manual"
		)

	@staticmethod
	def create_timeout_recovery_task(response_log_name, original_request_id=None):
		"""
		Crear tarea de recuperación específica para timeouts PAC.

		Args:
			response_log_name (str): Nombre del FacturAPI Response Log con timeout
			original_request_id (str): UUID del request original

		Returns:
			FiscalRecoveryTask: Tarea creada
		"""
		try:
			recovery_task = frappe.get_doc(
				{
					"doctype": "Fiscal Recovery Task",
					"task_type": "timeout_recovery",
					"reference_doctype": "FacturAPI Response Log",
					"reference_name": response_log_name,
					"priority": "high",  # Timeouts son alta prioridad
					"max_attempts": 3,
					"scheduled_time": frappe.utils.add_to_date(frappe.utils.now(), minutes=2),
					"original_request_id": original_request_id,
					"recovery_data": {"created_reason": "timeout_detected", "original_timeout_ms": 30000},
				}
			)

			recovery_task.insert(ignore_permissions=True)
			frappe.db.commit()

			return recovery_task

		except Exception as e:
			frappe.logger("fiscal_recovery").error(f"Error creando timeout recovery task: {e!s}")
			raise

	@staticmethod
	def create_sync_error_task(doctype, name, error_description):
		"""
		Crear tarea para corregir errores de sincronización.

		Args:
			doctype (str): DocType con error de sync
			name (str): Nombre del documento
			error_description (str): Descripción del problema

		Returns:
			FiscalRecoveryTask: Tarea creada
		"""
		try:
			recovery_task = frappe.get_doc(
				{
					"doctype": "Fiscal Recovery Task",
					"task_type": "sync_error",
					"reference_doctype": doctype,
					"reference_name": name,
					"priority": "medium",
					"max_attempts": 3,
					"scheduled_time": frappe.utils.add_to_date(frappe.utils.now(), minutes=5),
					"last_error": error_description,
					"recovery_data": {
						"created_reason": "sync_error_detected",
						"sync_error_type": "state_mismatch",
					},
				}
			)

			recovery_task.insert(ignore_permissions=True)
			frappe.db.commit()

			return recovery_task

		except Exception as e:
			frappe.logger("fiscal_recovery").error(f"Error creando sync error task: {e!s}")
			raise

	def get_processing_summary(self):
		"""
		Obtener resumen del procesamiento para debugging.

		Returns:
			dict: Resumen con métricas y estado
		"""
		return {
			"name": self.name,
			"task_type": self.task_type,
			"status": self.status,
			"priority": self.priority,
			"attempts": f"{self.attempts}/{self.max_attempts}",
			"reference": f"{self.reference_doctype}: {self.reference_name}",
			"scheduled_for": self.scheduled_time,
			"last_attempt": self.last_attempt,
			"escalated": self.escalated_flag,
			"assigned_to": self.assigned_to,
			"last_error_summary": self.last_error[:100] if self.last_error else None,
		}
