# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
DocType: FacturAPI Response Log
Propósito: Registro INMUTABLE de todas las respuestas PAC/FacturAPI
Principio: PAC Response First - NUNCA se puede perder una respuesta del PAC
"""

import uuid
from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document


class FacturAPIResponseLog(Document):
	"""
	Registro inmutable de todas las interacciones con PAC/FacturAPI.

	Funcionalidades principales:
	- Registro automático de request_id único (UUID)
	- Inmutabilidad garantizada (no edición post-creación)
	- Single Source of Truth para estados fiscales
	- Trazabilidad completa de reintentos
	- Resistencia a fallos del sistema

	Campos críticos:
	- request_id: UUID único para idempotencia
	- request_payload: Request completo a FacturAPI
	- response_payload: Respuesta completa de FacturAPI
	- timeout_flag: Marca si hubo timeout
	- retry_of: Cadena de reintentos para trazabilidad

	Validaciones de inmutabilidad:
	- Solo se puede crear, NUNCA modificar
	- Solo Admin con override puede eliminar
	- Automáticamente marca is_immutable = 1

	Ejemplo de uso:
		# Crear log antes de enviar request
		log_doc = frappe.new_doc("FacturAPI Response Log")
		log_doc.request_id = str(uuid.uuid4())
		log_doc.request_timestamp = frappe.utils.now()
		log_doc.request_type = "timbrado"
		log_doc.insert(ignore_permissions=True)

		# Actualizar con respuesta (solo una vez)
		log_doc.response_timestamp = frappe.utils.now()
		log_doc.response_payload = response_data
		log_doc.save(ignore_permissions=True)
	"""

	def autoname(self):
		"""
		Generar nombre automático usando naming series.
		Formato: PAC-LOG-YYYY-MM-#####
		"""
		pass  # Frappe maneja naming_series automáticamente

	def before_insert(self):
		"""
		Validaciones antes de crear el registro.

		- Generar request_id único si no existe
		- Establecer timestamp de request
		- Marcar como inmutable
		- Validar campos obligatorios
		"""
		# Generar request_id único si no existe
		if not self.request_id:
			self.request_id = str(uuid.uuid4())

		# Establecer timestamp de request si no existe
		if not self.request_timestamp:
			self.request_timestamp = frappe.utils.now()

		# Marcar como inmutable automáticamente
		self.is_immutable = 1
		self.immutable_reason = "PAC Response - Single Source of Truth"

		# Establecer usuario que creó el registro
		if not self.created_by_system:
			self.created_by_system = frappe.session.user

		# Validar que request_id sea único
		existing = frappe.db.exists("FacturAPI Response Log", {"request_id": self.request_id})
		if existing and existing != self.name:
			frappe.throw(
				_("Request ID {0} ya existe. Cada solicitud debe tener un ID único.").format(self.request_id),
				frappe.UniqueValidationError,
			)

	def validate(self):
		"""
		Validaciones de negocio críticas.

		- Inmutabilidad estricta (solo admin con override puede modificar)
		- Consistencia de timestamps
		- Validación de retry chain
		- Validación de campos críticos
		"""
		# INMUTABILIDAD ESTRICTA
		if not self.is_new() and not self.admin_override_flag:
			# Solo permitir actualización si admin activó override
			if frappe.session.user != "Administrator":
				frappe.throw(
					_("Este registro es INMUTABLE. Solo Administrator con override puede modificar."),
					frappe.PermissionError,
				)

		# Validar consistencia de timestamps
		if self.response_timestamp and self.request_timestamp:
			if self.response_timestamp < self.request_timestamp:
				frappe.throw(
					_("Timestamp de respuesta no puede ser anterior al de solicitud"), frappe.ValidationError
				)

		# Validar retry chain
		if self.retry_of:
			retry_parent = frappe.get_doc("FacturAPI Response Log", self.retry_of)
			if not retry_parent:
				frappe.throw(
					_("Registro padre de reintento {0} no existe").format(self.retry_of),
					frappe.ValidationError,
				)

			# Validar que no se excedan reintentos máximos
			if self.retry_count > 3:
				frappe.throw(
					_("Máximo 3 reintentos permitidos. Reintento #{0} excede límite").format(
						self.retry_count
					),
					frappe.ValidationError,
				)

		# Validar campos críticos según tipo de request
		if self.request_type in ["timbrado", "cancelacion"]:
			if not self.reference_doctype or not self.reference_name:
				frappe.throw(
					_("Tipo de solicitud {0} requiere reference_doctype y reference_name").format(
						self.request_type
					),
					frappe.ValidationError,
				)

	def before_save(self):
		"""
		Validaciones finales antes de guardar.

		- Calcular response_time_ms automáticamente
		- Detectar timeout automáticamente
		- Validar estructura de payloads JSON
		"""
		# Calcular tiempo de respuesta automáticamente
		if self.response_timestamp and self.request_timestamp and not self.response_time_ms:
			request_dt = frappe.utils.get_datetime(self.request_timestamp)
			response_dt = frappe.utils.get_datetime(self.response_timestamp)
			time_diff = (response_dt - request_dt).total_seconds() * 1000
			self.response_time_ms = round(time_diff, 2)

		# Detectar timeout automáticamente
		if self.response_time_ms and self.response_time_ms > 30000:  # 30 segundos
			self.timeout_flag = 1

		# Validar que payloads JSON sean válidos
		if self.request_payload:
			try:
				import json

				if isinstance(self.request_payload, str):
					json.loads(self.request_payload)
			except (json.JSONDecodeError, TypeError):
				frappe.throw(_("request_payload debe ser JSON válido"), frappe.ValidationError)

		if self.response_payload:
			try:
				import json

				if isinstance(self.response_payload, str):
					json.loads(self.response_payload)
			except (json.JSONDecodeError, TypeError):
				frappe.throw(_("response_payload debe ser JSON válido"), frappe.ValidationError)

	def on_update(self):
		"""
		Acciones después de actualizar.

		- Log de cambios críticos
		- Notificación de timeouts
		- Trigger de recovery tasks si necesario
		"""
		# Log crítico de cambios
		frappe.logger("facturapi_response").info(
			f"FacturAPI Response Log actualizado: {self.name} | "
			f"Request ID: {self.request_id} | "
			f"Type: {self.request_type} | "
			f"HTTP Code: {self.response_http_code}"
		)

		# Si es timeout, crear recovery task
		if self.timeout_flag and not self.retry_of:
			self.create_recovery_task_for_timeout()

	def create_recovery_task_for_timeout(self):
		"""
		Crear tarea de recuperación automática para timeouts.

		Solo para requests originales (no reintentos) que dieron timeout.
		"""
		try:
			recovery_task = frappe.get_doc(
				{
					"doctype": "Fiscal Recovery Task",
					"task_type": "timeout_recovery",
					"reference_doctype": "FacturAPI Response Log",
					"reference_name": self.name,
					"priority": "high",
					"status": "pending",
					"max_attempts": 3,
					"scheduled_time": frappe.utils.add_to_date(frappe.utils.now(), minutes=2),
				}
			)
			recovery_task.insert(ignore_permissions=True)

			frappe.logger("facturapi_response").info(
				f"Recovery task creada para timeout: {recovery_task.name}"
			)
		except Exception as e:
			frappe.logger("facturapi_response").error(f"Error creando recovery task para {self.name}: {e!s}")

	def before_cancel(self):
		"""
		Prevenir cancelación de registros.
		Solo Admin con override puede cancelar.
		"""
		if not self.admin_override_flag:
			frappe.throw(
				_("Registros FacturAPI Response Log no pueden ser cancelados. Son inmutables."),
				frappe.PermissionError,
			)

	def on_trash(self):
		"""
		Prevenir eliminación de registros.
		Solo Admin con override puede eliminar.
		"""
		if not self.admin_override_flag:
			frappe.throw(
				_("Registros FacturAPI Response Log no pueden ser eliminados. Son inmutables."),
				frappe.PermissionError,
			)

	@staticmethod
	def create_request_log(
		request_type, reference_doctype=None, reference_name=None, request_payload=None, company=None
	):
		"""
		Método estático para crear log de request de forma segura.

		Args:
			request_type (str): Tipo de solicitud (timbrado, cancelacion, etc.)
			reference_doctype (str): DocType que origina la solicitud
			reference_name (str): Nombre del documento que origina
			request_payload (dict/str): Payload del request
			company (str): Empresa asociada

		Returns:
			FacturAPIResponseLog: Documento creado

		Raises:
			Exception: Si no se puede crear el log
		"""
		try:
			log_doc = frappe.new_doc("FacturAPI Response Log")
			log_doc.request_id = str(uuid.uuid4())
			log_doc.request_timestamp = frappe.utils.now()
			log_doc.request_type = request_type
			log_doc.reference_doctype = reference_doctype
			log_doc.reference_name = reference_name
			log_doc.reference_company = company
			log_doc.created_by_system = frappe.session.user

			if request_payload:
				import json

				if isinstance(request_payload, dict):
					log_doc.request_payload = json.dumps(request_payload, ensure_ascii=False)
				else:
					log_doc.request_payload = request_payload

			log_doc.insert(ignore_permissions=True)
			frappe.db.commit()  # CRÍTICO: Commit inmediato para asegurar persistencia

			return log_doc

		except Exception as e:
			frappe.logger("facturapi_response").error(
				f"CRÍTICO: No se pudo crear FacturAPI Response Log: {e!s}"
			)
			raise

	def update_with_response(self, response_data, http_code=200, system_error=None):
		"""
		Actualizar log con respuesta del PAC de forma segura.

		Args:
			response_data (dict/str): Respuesta del PAC
			http_code (int): Código HTTP de respuesta
			system_error (str): Error interno del sistema si lo hubo

		Esta es la ÚNICA forma segura de actualizar la respuesta.
		"""
		try:
			self.response_timestamp = frappe.utils.now()
			self.response_http_code = http_code

			if response_data:
				import json

				if isinstance(response_data, dict):
					self.response_payload = json.dumps(response_data, ensure_ascii=False)
				else:
					self.response_payload = response_data

			if system_error:
				self.system_error = system_error

			self.save(ignore_permissions=True)
			frappe.db.commit()  # CRÍTICO: Commit inmediato

		except Exception as e:
			frappe.logger("facturapi_response").error(
				f"CRÍTICO: No se pudo actualizar FacturAPI Response Log {self.name}: {e!s}"
			)
			raise
