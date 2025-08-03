import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class FacturAPIResponseLog(Document):
	"""Registro de respuestas de FacturAPI para auditoría y cálculo de estados."""

	def before_insert(self):
		"""Configurar metadatos antes de insertar."""
		# Establecer timestamp si no está configurado
		if not self.timestamp:
			self.timestamp = now_datetime()

		# Capturar información del usuario
		if not self.user_role:
			user_roles = frappe.get_roles(frappe.session.user)
			self.user_role = user_roles[0] if user_roles else "Guest"

		# Capturar IP address
		if not self.ip_address:
			self.ip_address = getattr(frappe.local, "request_ip", None) or "Unknown"

	def after_insert(self):
		"""Actualizar estado fiscal después de insertar log."""
		if self.factura_fiscal_mexico and self.success:
			self.update_fiscal_status()

	def update_fiscal_status(self):
		"""Actualizar estado fiscal basado en el tipo de operación exitosa."""
		if not self.success:
			return

		# Mapear operaciones a estados fiscales
		status_map = {
			"Timbrado": "Timbrada",
			"Confirmación Cancelación": "Cancelada",
			"Solicitud Cancelación": "Solicitud Cancelación",  # Estado intermedio
		}

		new_status = status_map.get(self.operation_type)
		if not new_status:
			return

		try:
			# Actualizar estado en Factura Fiscal Mexico
			frappe.db.set_value(
				"Factura Fiscal Mexico", self.factura_fiscal_mexico, "fm_fiscal_status", new_status
			)

			# Log del cambio
			frappe.logger().info(
				f"Estado fiscal actualizado: {self.factura_fiscal_mexico} → {new_status} "
				f"(basado en log {self.name})"
			)

		except Exception as e:
			frappe.log_error(
				f"Error actualizando estado fiscal para {self.factura_fiscal_mexico}: {e!s}",
				"FacturAPI Response Log Update Error",
			)

	@staticmethod
	def create_log(
		factura_fiscal_mexico,
		operation_type,
		success,
		facturapi_response=None,
		status_code=None,
		error_message=None,
	):
		"""Método estático para crear logs de respuesta FacturAPI."""
		try:
			log_doc = frappe.new_doc("FacturAPI Response Log")
			log_doc.factura_fiscal_mexico = factura_fiscal_mexico
			log_doc.operation_type = operation_type
			log_doc.success = success
			log_doc.status_code = str(status_code) if status_code else None

			# Manejar respuesta JSON
			if facturapi_response:
				if isinstance(facturapi_response, dict):
					log_doc.facturapi_response = facturapi_response
				else:
					# Si es string, intentar parsear
					import json

					try:
						log_doc.facturapi_response = json.loads(facturapi_response)
					except Exception:
						log_doc.facturapi_response = {"raw_response": str(facturapi_response)}

			# Error message
			if error_message:
				log_doc.error_message = str(error_message)[:500]  # Limitar longitud

			log_doc.insert(ignore_permissions=True)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required for API response logging to persist immediately

			return log_doc

		except Exception as e:
			frappe.log_error(
				f"Error creando FacturAPI Response Log: {e!s}", "FacturAPI Response Log Creation Error"
			)
			return None

	@staticmethod
	def get_latest_status(factura_fiscal_mexico):
		"""Obtener el último estado basado en logs exitosos."""
		try:
			latest_log = frappe.db.get_value(
				"FacturAPI Response Log",
				{
					"factura_fiscal_mexico": factura_fiscal_mexico,
					"success": 1,
					"operation_type": ("in", ["Timbrado", "Confirmación Cancelación"]),
				},
				["operation_type", "timestamp"],
				order_by="timestamp desc",
			)

			if latest_log:
				operation_type = latest_log[0] if isinstance(latest_log, tuple) else latest_log
				status_map = {"Timbrado": "Timbrada", "Confirmación Cancelación": "Cancelada"}
				return status_map.get(operation_type, "Pendiente")

			return "Pendiente"

		except Exception as e:
			frappe.log_error(
				f"Error obteniendo último estado para {factura_fiscal_mexico}: {e!s}",
				"FacturAPI Response Log Status Error",
			)
			return "Error"

	def validate(self):
		"""Validaciones del documento."""
		# Validar que factura_fiscal_mexico existe
		if self.factura_fiscal_mexico and not frappe.db.exists(
			"Factura Fiscal Mexico", self.factura_fiscal_mexico
		):
			frappe.throw(_("La Factura Fiscal Mexico {0} no existe").format(self.factura_fiscal_mexico))

		# Si es exitoso, validar que tenga respuesta
		if self.success and not self.facturapi_response:
			frappe.throw(_("Respuesta FacturAPI es requerida para operaciones exitosas"))

		# Si no es exitoso, validar que tenga mensaje de error
		if not self.success and not self.error_message:
			frappe.throw(_("Mensaje de error es requerido para operaciones fallidas"))
