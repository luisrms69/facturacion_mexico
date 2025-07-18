import frappe
from frappe import _
from frappe.model.document import Document


class FacturacionMexicoSettings(Document):
	"""Configuración principal para el sistema de facturación fiscal de México."""

	def validate(self):
		"""Validar configuración antes de guardar."""
		self.validate_rfc_format()
		self.validate_lugar_expedicion()
		self.validate_api_keys()

	def validate_rfc_format(self):
		"""Validar formato del RFC emisor."""
		if self.rfc_emisor:
			rfc = self.rfc_emisor.strip().upper()

			# Validar longitud
			if len(rfc) not in [12, 13]:
				frappe.throw(_("El RFC debe tener 12 o 13 caracteres"))

			# Validar que sea alfanumérico
			if not rfc.isalnum():
				frappe.throw(_("El RFC debe contener solo letras y números"))

			# Actualizar con formato correcto
			self.rfc_emisor = rfc

	def validate_lugar_expedicion(self):
		"""Validar código postal de lugar de expedición."""
		if self.lugar_expedicion:
			cp = self.lugar_expedicion.strip()

			# Validar longitud (código postal mexicano)
			if len(cp) != 5:
				frappe.throw(_("El código postal debe tener 5 dígitos"))

			# Validar que sea numérico
			if not cp.isdigit():
				frappe.throw(_("El código postal debe contener solo números"))

			# Actualizar con formato correcto
			self.lugar_expedicion = cp

	def validate_api_keys(self):
		"""Validar que al menos una API key esté configurada."""
		if not self.api_key and not self.test_api_key:
			frappe.throw(_("Debe configurar al menos una API Key (producción o pruebas)"))

		# Si está en modo sandbox, validar que exista test_api_key
		if self.sandbox_mode and not self.test_api_key:
			frappe.throw(_("En modo sandbox es requerida la API Key de pruebas"))

	def get_api_key(self):
		"""Obtener la API key correcta según el modo."""
		if self.sandbox_mode:
			return self.get_password("test_api_key")
		else:
			return self.get_password("api_key")

	def get_api_base_url(self):
		"""Obtener la URL base de la API según el modo."""
		if self.sandbox_mode:
			return "https://www.facturapi.io/v2"  # URL sandbox
		else:
			return "https://www.facturapi.io/v2"  # URL producción

	@staticmethod
	def get_settings():
		"""Obtener configuración de facturación México."""
		if not frappe.db.exists("Facturacion Mexico Settings", "Facturacion Mexico Settings"):
			# Crear configuración por defecto si no existe
			settings = frappe.new_doc("Facturacion Mexico Settings")
			settings.sandbox_mode = 1
			settings.timeout = 30
			settings.auto_generate_ereceipts = 1
			settings.send_email_default = 0
			settings.download_files_default = 1
			settings.save()
			return settings

		return frappe.get_doc("Facturacion Mexico Settings", "Facturacion Mexico Settings")

	def on_update(self):
		"""Ejecutar después de actualizar configuración."""
		# Limpiar cache de configuración
		frappe.cache().delete_value("facturacion_mexico_settings")

		# Log del cambio
		frappe.log_error(
			f"Configuración de Facturación México actualizada por {frappe.session.user}",
			"Facturacion Mexico Settings Updated",
		)
