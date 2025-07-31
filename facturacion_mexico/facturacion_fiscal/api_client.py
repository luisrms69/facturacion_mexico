from typing import Any

import frappe
import requests
from frappe import _


class FacturAPIClient:
	"""Cliente para FacturAPI.io usando requests (ya incluido en Frappe)."""

	def __init__(self, settings_doc=None):
		"""Inicializar cliente con configuración."""
		if not settings_doc:
			settings_doc = frappe.get_single("Facturacion Mexico Settings")

		self.settings = settings_doc
		self.base_url = self._get_base_url()
		self.api_key = self._get_api_key()
		self.timeout = self.settings.timeout or 30

		# Headers estándar
		self.headers = {
			"Authorization": f"Bearer {self.api_key}",
			"Content-Type": "application/json",
			"Accept": "application/json",
		}

	def _get_base_url(self) -> str:
		"""Obtener URL base según modo sandbox/producción."""
		if self.settings.sandbox_mode:
			return "https://www.facturapi.io/v2"
		else:
			return "https://www.facturapi.io/v2"

	def _get_api_key(self) -> str:
		"""Obtener API key según modo sandbox/producción."""
		if self.settings.sandbox_mode:
			return self.settings.get_password("test_api_key")
		else:
			return self.settings.get_password("api_key")

	def _make_request(self, method: str, endpoint: str, data: dict | None = None) -> dict[str, Any]:
		"""Realizar petición HTTP a FacturAPI."""
		url = f"{self.base_url}{endpoint}"

		try:
			# Usar requests que ya viene con Frappe
			response = requests.request(
				method=method, url=url, headers=self.headers, json=data, timeout=self.timeout
			)

			# Log de la petición
			frappe.logger().info(f"FacturAPI {method} {endpoint}: {response.status_code}")

			# Verificar respuesta exitosa
			if response.status_code >= 400:
				error_msg = self._parse_error_response(response)
				frappe.throw(_(f"Error FacturAPI {response.status_code}: {error_msg}"))

			return response.json()

		except requests.exceptions.Timeout:
			frappe.throw(_("Timeout al conectar con FacturAPI"))
		except requests.exceptions.ConnectionError:
			frappe.throw(_("Error de conexión con FacturAPI"))
		except requests.exceptions.RequestException as e:
			frappe.throw(_(f"Error en petición FacturAPI: {e!s}"))

		return None

	def _parse_error_response(self, response) -> str:
		"""Parsear respuesta de error de FacturAPI."""
		try:
			error_data = response.json()
			if "message" in error_data:
				return error_data["message"]
			elif "error" in error_data:
				return error_data["error"]
			else:
				return str(error_data)
		except Exception:
			return response.text or "Error desconocido"

	def create_customer(self, customer_data: dict) -> dict[str, Any]:
		"""Crear cliente en FacturAPI."""
		return self._make_request("POST", "/customers", customer_data)

	def get_customer(self, customer_id: str) -> dict[str, Any]:
		"""Obtener cliente de FacturAPI."""
		return self._make_request("GET", f"/customers/{customer_id}")

	def update_customer(self, customer_id: str, customer_data: dict) -> dict[str, Any]:
		"""Actualizar cliente en FacturAPI."""
		return self._make_request("PUT", f"/customers/{customer_id}", customer_data)

	def create_invoice(self, invoice_data: dict) -> dict[str, Any]:
		"""Crear factura en FacturAPI."""
		return self._make_request("POST", "/invoices", invoice_data)

	def get_invoice(self, invoice_id: str) -> dict[str, Any]:
		"""Obtener factura de FacturAPI."""
		return self._make_request("GET", f"/invoices/{invoice_id}")

	def cancel_invoice(self, invoice_id: str, motive: str = "02") -> dict[str, Any]:
		"""Cancelar factura en FacturAPI."""
		cancel_data = {"motive": motive}
		return self._make_request("DELETE", f"/invoices/{invoice_id}", cancel_data)

	def download_pdf(self, invoice_id: str) -> bytes:
		"""Descargar PDF de factura."""
		url = f"{self.base_url}/invoices/{invoice_id}/pdf"

		try:
			response = requests.get(
				url, headers={"Authorization": f"Bearer {self.api_key}"}, timeout=self.timeout
			)

			if response.status_code >= 400:
				frappe.throw(_(f"Error al descargar PDF: {response.status_code}"))

			return response.content

		except Exception as e:
			frappe.throw(_(f"Error descargando PDF: {e!s}"))

	def download_xml(self, invoice_id: str) -> str:
		"""Descargar XML de factura."""
		url = f"{self.base_url}/invoices/{invoice_id}/xml"

		try:
			response = requests.get(
				url, headers={"Authorization": f"Bearer {self.api_key}"}, timeout=self.timeout
			)

			if response.status_code >= 400:
				frappe.throw(_(f"Error al descargar XML: {response.status_code}"))

			return response.text

		except Exception as e:
			frappe.throw(_(f"Error descargando XML: {e!s}"))

	def create_receipt(self, receipt_data: dict) -> dict[str, Any]:
		"""Crear E-Receipt (recibo electrónico) en FacturAPI.

		Args:
			receipt_data: Datos del recibo con estructura:
			{
				"type": "receipt",
				"customer": {"legal_name": str, "email": str},
				"items": [{"quantity": float, "product": {...}}],
				"payment_form": str,
				"folio_number": str,
				"expires_at": str (ISO format)
			}

		Returns:
			dict: Respuesta de FacturAPI con id, key, self_invoice_url
		"""
		try:
			# Validar estructura mínima
			required_fields = ["type", "customer", "items"]
			for field in required_fields:
				if field not in receipt_data:
					frappe.throw(_(f"Campo requerido para E-Receipt: {field}"))

			# Configurar valores por defecto para ambiente de prueba
			if self.settings.sandbox_mode:
				# En sandbox, usar datos de prueba seguros
				receipt_data.setdefault("payment_form", "28")  # Tarjeta de crédito

				# Validar que el customer tenga los campos mínimos
				customer = receipt_data["customer"]
				customer.setdefault("legal_name", "Cliente Público en General")
				customer.setdefault("email", "test@example.com")
				customer.setdefault("tax_id", "XAXX010101000")  # RFC genérico para pruebas

			# Log para debugging en ambiente de prueba
			if self.settings.sandbox_mode:
				frappe.logger().info(
					f"Creando E-Receipt en SANDBOX: {receipt_data.get('folio_number', 'N/A')}"
				)

			return self._make_request("POST", "/receipts", receipt_data)

		except Exception as e:
			frappe.log_error(
				message=f"Error creando E-Receipt: {e!s}\nData: {receipt_data}",
				title="FacturAPI E-Receipt Error",
			)
			raise

	def get_receipt(self, receipt_id: str) -> dict[str, Any]:
		"""Obtener E-Receipt de FacturAPI."""
		return self._make_request("GET", f"/receipts/{receipt_id}")

	def cancel_receipt(self, receipt_id: str) -> dict[str, Any]:
		"""Cancelar E-Receipt en FacturAPI."""
		return self._make_request("DELETE", f"/receipts/{receipt_id}")

	def test_connection(self) -> bool:
		"""Probar conexión con FacturAPI."""
		try:
			# Test simple: obtener información de la organización
			self._make_request("GET", "/organizations/me")
			return True
		except Exception as e:
			frappe.logger().error(f"Test conexión FacturAPI falló: {e!s}")
			return False


def get_facturapi_client(settings_doc=None) -> FacturAPIClient:
	"""Factory function para obtener cliente FacturAPI."""
	return FacturAPIClient(settings_doc)


@frappe.whitelist()
def test_facturapi_connection():
	"""API para probar conexión desde interfaz."""
	try:
		client = get_facturapi_client()
		if client.test_connection():
			frappe.msgprint(_("Conexión exitosa con FacturAPI"))
			return {"success": True, "message": "Conexión exitosa"}
		else:
			frappe.msgprint(_("Error al conectar con FacturAPI"))
			return {"success": False, "message": "Error de conexión"}
	except Exception as e:
		frappe.msgprint(_(f"Error: {e!s}"))
		return {"success": False, "message": str(e)}
