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

	# after_insert() ELIMINADO - Nueva arquitectura usa PAC Response Writer + Status Calculator
	# Hooks legacy eliminados - sistema ahora stateless

	# update_fiscal_status() ELIMINADO - Nueva arquitectura usa Status Calculator stateless

	# create_log() ELIMINADO - Nueva arquitectura usa write_pac_response() del PAC Response Writer

	# get_latest_status() ELIMINADO - Nueva arquitectura usa calculate_current_status() del Status Calculator

	def validate(self):
		"""Validaciones del documento con auto-reparación."""
		import json

		# Validar que factura_fiscal_mexico existe
		if self.factura_fiscal_mexico and not frappe.db.exists(
			"Factura Fiscal Mexico", self.factura_fiscal_mexico
		):
			frappe.throw(_("La Factura Fiscal Mexico {0} no existe").format(self.factura_fiscal_mexico))

		# Si es exitoso, validar que tenga respuesta
		if self.success and not self.facturapi_response:
			frappe.throw(_("Respuesta FacturAPI es requerida para operaciones exitosas"))

		# Si no es exitoso, validar que tenga mensaje de error O respuesta FacturAPI
		if not self.success:
			if not (self.error_message or self.facturapi_response):
				frappe.throw(_("Mensaje de error o respuesta FacturAPI requerida para operaciones fallidas"))

		# Auto-reparar mensaje de error si está vacío pero hay respuesta JSON
		if not self.success and not (self.error_message or "").strip() and self.facturapi_response:
			# Intentar extraer del payload de respuesta
			msg = None
			try:
				payload = json.loads(self.facturapi_response) if self.facturapi_response else {}
				msg = (
					(payload.get("error_message") or "").strip()
					or (payload.get("error") or "").strip()
					or (payload.get("message") or "").strip()
					or (payload.get("detail") or "").strip()
					or (payload.get("error_description") or "").strip()
				)
			except Exception:
				pass

			# Auto-rellenar con mensaje por defecto si no se encuentra nada
			self.error_message = msg or _("Error desconocido del PAC")
