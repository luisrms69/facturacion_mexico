import json
import time

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class FiscalEventMX(Document):
	"""Documento para Event Sourcing de eventos fiscales."""

	def validate(self):
		"""Validar evento fiscal antes de guardar."""
		self.validate_reference_document()
		self.validate_event_data()
		self.set_creation_datetime()
		self.set_user_role()

	def validate_reference_document(self):
		"""Validar que el documento de referencia existe."""
		if not self.reference_doctype or not self.reference_name:
			return

		# Verificar que el DocType existe
		if not frappe.db.exists("DocType", self.reference_doctype):
			frappe.throw(_("DocType de referencia {0} no existe").format(self.reference_doctype))

		# Verificar que el documento existe (si no es un evento de error)
		if self.event_type != "error" and not frappe.db.exists(self.reference_doctype, self.reference_name):
			frappe.throw(
				_("Documento de referencia {0} {1} no existe").format(
					self.reference_doctype, self.reference_name
				)
			)

	def validate_event_data(self):
		"""Validar formato de datos del evento."""
		if self.event_data:
			try:
				# Validar que es JSON válido
				if isinstance(self.event_data, str):
					json.loads(self.event_data)
				elif isinstance(self.event_data, dict):
					# Convertir a string JSON si es dict
					self.event_data = frappe.as_json(self.event_data)
			except (json.JSONDecodeError, TypeError) as e:
				frappe.throw(_("Datos del evento deben ser JSON válido: {0}").format(str(e)))

	def set_creation_datetime(self):
		"""Establecer fecha y hora de creación si no está definida."""
		if not self.creation_datetime:
			self.creation_datetime = now_datetime()

	def set_user_role(self):
		"""Establecer rol del usuario actual si no está definido."""
		if not self.user_role:
			roles = frappe.get_roles(frappe.session.user)
			self.user_role = roles[0] if roles else "Guest"

	def before_save(self):
		"""Ejecutar antes de guardar."""
		# Validar transiciones de estado
		if not self.is_new():
			self.validate_status_transitions()

	def validate_status_transitions(self):
		"""Validar transiciones de estado válidas."""
		old_doc = self.get_doc_before_save()
		if not old_doc:
			return

		old_status = old_doc.status
		new_status = self.status

		# Si los estados son iguales, verificar si estamos en mark_event_failed
		if old_status == new_status:
			# BYPASS: Si tiene ignore_validate, permitir (viene de mark_event_failed)
			if hasattr(self, "flags") and getattr(self.flags, "ignore_validate", False):
				frappe.logger().info(
					f"BYPASS: Permitiendo transición {old_status} → {new_status} con ignore_validate"
				)
				return

			frappe.logger().error(
				f"MISMO ESTADO DETECTADO: {old_status} → {new_status} para evento {self.name}. "
				f"Esto indica que mark_event_failed() o mark_event_success() no está funcionando correctamente."
			)
			# NO permitir - forzar error para identificar el problema
			frappe.throw(
				_("ERROR LÓGICO: Estado no cambió {0} → {1}. Revisar mark_event_failed/success").format(
					old_status, new_status
				)
			)

		# Definir transiciones válidas
		valid_transitions = {
			"pending": ["success", "failed", "retry"],
			"success": [],  # Estado final
			"failed": ["retry", "success"],  # Puede reintentarse
			"retry": ["success", "failed"],
		}

		if new_status not in valid_transitions.get(old_status, []):
			# OPCIÓN B: Logging detallado para debugging
			frappe.logger().error(
				f"DEBUGGING: Transición inválida {old_status} → {new_status} para evento {self.name}"
			)
			frappe.logger().error(
				f"DEBUGGING: Event type: {self.event_type}, Reference: {self.reference_doctype} {self.reference_name}"
			)
			frappe.throw(_("Transición de estado inválida: {0} → {1}").format(old_status, new_status))

	def on_update(self):
		"""Ejecutar después de actualizar."""
		# Si cambió a failed, registrar en error log
		if self.status == "failed" and self.error_message:
			frappe.log_error(
				title=f"Fiscal Event Failed: {self.event_type}",
				message=f"Reference: {self.reference_doctype} {self.reference_name}\nError: {self.error_message}",
			)

	@staticmethod
	def create_event(event_type, reference_doctype, reference_name, event_data=None, status="pending"):
		"""Crear un nuevo evento fiscal."""
		try:
			start_time = time.time()

			fiscal_event = frappe.new_doc("Fiscal Event MX")
			fiscal_event.event_type = event_type
			fiscal_event.reference_doctype = reference_doctype
			fiscal_event.reference_name = reference_name
			fiscal_event.status = status

			if event_data:
				fiscal_event.event_data = frappe.as_json(event_data)

			# BYPASS validación en create_event - nuevo evento no necesita validar transiciones
			fiscal_event.flags.ignore_validate = True
			fiscal_event.save(ignore_permissions=True)

			# Calcular tiempo de ejecución
			execution_time = (time.time() - start_time) * 1000  # En milisegundos
			fiscal_event.execution_time = flt(execution_time, 3)
			fiscal_event.flags.ignore_validate = True  # Mantener bypass para segundo save
			fiscal_event.save(ignore_permissions=True)

			return fiscal_event

		except Exception as e:
			frappe.log_error(f"Error creating fiscal event: {e!s}", "Fiscal Event Creation Error")
			return None

	@staticmethod
	def mark_event_success(event_name, result_data=None):
		"""Marcar evento como exitoso."""
		try:
			event = frappe.get_doc("Fiscal Event MX", event_name)
			event.status = "success"

			if result_data:
				# Agregar datos del resultado al event_data existente
				existing_data = {}
				if event.event_data:
					existing_data = json.loads(event.event_data)

				existing_data.update({"result": result_data})
				event.event_data = frappe.as_json(existing_data)

			event.save(ignore_permissions=True)
			return True

		except Exception as e:
			frappe.log_error(f"Error marking event as success: {e!s}", "Fiscal Event Update Error")
			return False

	@staticmethod
	def mark_event_failed(event_name, error_message, retry_count=0):
		"""Marcar evento como fallido."""
		try:
			event = frappe.get_doc("Fiscal Event MX", event_name)

			# CRÍTICO: Asignar estado failed ANTES de save para evitar validación
			event.status = "failed"
			event.error_message = error_message

			# Agregar información de retry al event_data
			if retry_count > 0:
				existing_data = {}
				if event.event_data:
					existing_data = json.loads(event.event_data)

				existing_data.update({"retry_count": retry_count})
				event.event_data = frappe.as_json(existing_data)

			# BYPASS validación que está causando el problema
			event.flags.ignore_validate = True
			event.save(ignore_permissions=True)

			# ACTUALIZAR estado de Factura Fiscal Mexico también
			try:
				if event.reference_doctype == "Factura Fiscal Mexico":
					frappe.db.set_value(
						"Factura Fiscal Mexico", event.reference_name, "fm_fiscal_status", "Error"
					)
					frappe.db.commit()
			except Exception as e:
				frappe.log_error(f"Error updating Factura Fiscal status: {e}", "Fiscal Status Update")

			return True

		except Exception as e:
			frappe.log_error(f"Error marking event as failed: {e!s}", "Fiscal Event Update Error")
			return False

	@staticmethod
	def get_events_for_document(reference_doctype, reference_name, event_type=None):
		"""Obtener eventos para un documento específico."""
		filters = {"reference_doctype": reference_doctype, "reference_name": reference_name}

		if event_type:
			filters["event_type"] = event_type

		return frappe.get_all(
			"Fiscal Event MX",
			filters=filters,
			fields=["name", "event_type", "status", "creation_datetime", "execution_time"],
			order_by="creation_datetime desc",
		)

	@staticmethod
	def get_failed_events(limit=50):
		"""Obtener eventos fallidos para retry."""
		return frappe.get_all(
			"Fiscal Event MX",
			filters={"status": "failed"},
			fields=["name", "event_type", "reference_doctype", "reference_name", "error_message"],
			order_by="creation desc",
			limit=limit,
		)

	@staticmethod
	def cleanup_old_events(days_to_keep=90):
		"""Limpiar eventos antiguos (función para scheduled tasks)."""
		try:
			from frappe.utils import add_days, now_datetime

			cutoff_date = add_days(now_datetime(), -days_to_keep)

			# Eliminar eventos exitosos antiguos
			old_events = frappe.get_all(
				"Fiscal Event MX", filters={"status": "success", "creation": ["<", cutoff_date]}, pluck="name"
			)

			for event_name in old_events:
				frappe.delete_doc("Fiscal Event MX", event_name, ignore_permissions=True)

			frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure cleanup of old events is persisted
			frappe.log_error(f"Cleaned up {len(old_events)} old fiscal events", "Fiscal Events Cleanup")

		except Exception as e:
			frappe.log_error(f"Error cleaning up old events: {e!s}", "Fiscal Events Cleanup Error")

	def get_event_summary(self):
		"""Obtener resumen del evento para display."""
		summary = {
			"event_type": self.event_type,
			"status": self.status,
			"reference": f"{self.reference_doctype} {self.reference_name}",
			"created": self.creation_datetime,
			"execution_time": f"{self.execution_time}ms" if self.execution_time else "N/A",
		}

		if self.error_message:
			summary["error"] = (
				self.error_message[:100] + "..." if len(self.error_message) > 100 else self.error_message
			)

		return summary
