from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from .api_client import get_facturapi_client
from .doctype.fiscal_event_mx.fiscal_event_mx import FiscalEventMX


class TimbradoAPI:
	"""API para timbrado de facturas usando FacturAPI.io."""

	def __init__(self):
		"""Inicializar API de timbrado."""
		self.client = get_facturapi_client()
		self.settings = frappe.get_single("Facturacion Mexico Settings")

	def timbrar_factura(self, sales_invoice_name: str) -> dict[str, Any]:
		"""Timbrar factura de Sales Invoice."""
		try:
			# Obtener Sales Invoice
			sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)

			# Validar que se pueda timbrar
			self._validate_invoice_for_timbrado(sales_invoice)

			# Crear o actualizar Factura Fiscal
			factura_fiscal = self._get_or_create_factura_fiscal(sales_invoice)

			# Preparar datos para FacturAPI
			invoice_data = self._prepare_facturapi_data(sales_invoice, factura_fiscal)

			# Crear evento fiscal
			event_doc = FiscalEventMX.create_event(
				factura_fiscal.name, "timbrado_request", {"sales_invoice": sales_invoice_name}
			)

			# Llamar a FacturAPI
			response = self.client.create_invoice(invoice_data)

			# Procesar respuesta exitosa
			self._process_timbrado_success(sales_invoice, factura_fiscal, response, event_doc)

			return {
				"success": True,
				"uuid": response.get("uuid"),
				"factura_fiscal": factura_fiscal.name,
				"message": "Factura timbrada exitosamente",
			}

		except Exception as e:
			# Marcar evento como fallido
			if "event_doc" in locals():
				FiscalEventMX.mark_event_failed(event_doc.name, str(e))

			# Actualizar estado en Sales Invoice
			frappe.db.set_value("Sales Invoice", sales_invoice_name, "fm_fiscal_status", "Error")
			frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure error state is persisted

			frappe.logger().error(f"Error timbrado factura {sales_invoice_name}: {e!s}")
			return {"success": False, "error": str(e), "message": f"Error al timbrar factura: {e!s}"}

	def _validate_invoice_for_timbrado(self, sales_invoice):
		"""Validar que la factura se puede timbrar."""
		# Verificar que esté submitted
		if sales_invoice.docstatus != 1:
			frappe.throw(_("La factura debe estar enviada para timbrar"))

		# Verificar que no esté ya timbrada
		if sales_invoice.fm_fiscal_status == "Timbrada":
			frappe.throw(_("La factura ya está timbrada"))

		# Verificar datos del cliente
		if not sales_invoice.customer:
			frappe.throw(_("Se requiere cliente para timbrar"))

		customer = frappe.get_doc("Customer", sales_invoice.customer)
		if not customer.fm_rfc:
			frappe.throw(_("El cliente debe tener RFC configurado"))

		# Verificar uso de CFDI
		if not sales_invoice.fm_cfdi_use:
			frappe.throw(_("Se requiere Uso de CFDI para timbrar"))

		# Verificar que tenga items
		if not sales_invoice.items:
			frappe.throw(_("La factura debe tener al menos un item"))

	def _get_or_create_factura_fiscal(self, sales_invoice):
		"""Obtener o crear Factura Fiscal México."""
		if sales_invoice.fm_factura_fiscal_mx:
			return frappe.get_doc("Factura Fiscal Mexico", sales_invoice.fm_factura_fiscal_mx)

		# Crear nueva factura fiscal
		factura_fiscal = frappe.new_doc("Factura Fiscal Mexico")
		factura_fiscal.sales_invoice = sales_invoice.name
		factura_fiscal.customer = sales_invoice.customer
		factura_fiscal.total_amount = sales_invoice.grand_total
		factura_fiscal.currency = sales_invoice.currency
		factura_fiscal.fm_fiscal_status = "draft"
		factura_fiscal.save()

		# Actualizar referencia en Sales Invoice
		frappe.db.set_value("Sales Invoice", sales_invoice.name, "fm_factura_fiscal_mx", factura_fiscal.name)

		return factura_fiscal

	def _prepare_facturapi_data(self, sales_invoice, factura_fiscal) -> dict[str, Any]:
		"""Preparar datos para FacturAPI."""
		customer = frappe.get_doc("Customer", sales_invoice.customer)

		# Datos del cliente
		customer_data = {
			"legal_name": customer.customer_name,
			"tax_id": customer.fm_rfc,
			"email": customer.email_id or "cliente@example.com",
		}

		# Dirección del cliente si existe
		if customer.customer_primary_address:
			address = frappe.get_doc("Address", customer.customer_primary_address)
			customer_data["address"] = {
				"street": address.address_line1 or "",
				"exterior": address.address_line2 or "",
				"neighborhood": address.city or "",
				"city": address.city or "",
				"municipality": address.city or "",
				"state": address.state or "",
				"country": address.country or "MEX",
				"zip": address.pincode or "",
			}

		# Items de la factura
		items = []
		for item in sales_invoice.items:
			item_doc = frappe.get_doc("Item", item.item_code)

			items.append(
				{
					"quantity": item.qty,
					"product": {
						"description": item.description or item.item_name,
						"product_key": item_doc.fm_producto_servicio_sat or "01010101",
						"price": flt(item.rate),
						"unit_key": item_doc.fm_unidad_sat or "H87",
						"unit_name": item.uom or "Pieza",
					},
				}
			)

		# Datos de la factura
		invoice_data = {
			"customer": customer_data,
			"items": items,
			"payment_form": "99",  # Por definir
			"folio_number": sales_invoice.name,
			"series": "F",
			"use": sales_invoice.fm_cfdi_use,
		}

		return invoice_data

	def _process_timbrado_success(self, sales_invoice, factura_fiscal, response, event_doc):
		"""Procesar respuesta exitosa de timbrado."""
		# Actualizar Factura Fiscal
		factura_fiscal.uuid = response.get("uuid")
		factura_fiscal.facturapi_id = response.get("id")
		factura_fiscal.fm_fiscal_status = "stamped"
		factura_fiscal.stamped_at = now_datetime()
		factura_fiscal.save()

		# Actualizar Sales Invoice
		frappe.db.set_value(
			"Sales Invoice",
			sales_invoice.name,
			{"fm_fiscal_status": "Timbrada", "fm_uuid_fiscal": response.get("uuid")},
		)

		# Marcar evento como exitoso
		FiscalEventMX.mark_event_success(event_doc.name, response)

		# Descargar archivos si está configurado
		if self.settings.download_files_default:
			self._download_fiscal_files(factura_fiscal, response.get("id"))

		frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure fiscal transaction is committed after successful stamping

	def _download_fiscal_files(self, factura_fiscal, facturapi_id):
		"""Descargar PDF y XML de la factura."""
		try:
			# Descargar PDF
			pdf_content = self.client.download_pdf(facturapi_id)
			self._save_file_attachment(
				factura_fiscal.name, f"{factura_fiscal.name}.pdf", pdf_content, "application/pdf"
			)

			# Descargar XML
			xml_content = self.client.download_xml(facturapi_id)
			self._save_file_attachment(
				factura_fiscal.name,
				f"{factura_fiscal.name}.xml",
				xml_content.encode("utf-8"),
				"application/xml",
			)

		except Exception as e:
			frappe.logger().error(f"Error descargando archivos: {e!s}")

	def _save_file_attachment(self, docname, filename, content, content_type):
		"""Guardar archivo como attachment."""
		from frappe.utils.file_manager import save_file

		save_file(
			fname=filename,
			content=content,
			dt="Factura Fiscal Mexico",
			dn=docname,
			decode=False,
			is_private=1,
		)

	def cancelar_factura(self, sales_invoice_name: str, motivo: str = "02") -> dict[str, Any]:
		"""Cancelar factura timbrada."""
		try:
			sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)

			# Validar que se pueda cancelar
			if sales_invoice.fm_fiscal_status != "Timbrada":
				frappe.throw(_("Solo se pueden cancelar facturas timbradas"))

			if not sales_invoice.fm_factura_fiscal_mx:
				frappe.throw(_("No se encontró factura fiscal asociada"))

			factura_fiscal = frappe.get_doc("Factura Fiscal Mexico", sales_invoice.fm_factura_fiscal_mx)

			# Crear evento fiscal
			event_doc = FiscalEventMX.create_event(
				factura_fiscal.name,
				"cancellation_request",
				{"sales_invoice": sales_invoice_name, "motive": motivo},
			)

			# Llamar a FacturAPI
			response = self.client.cancel_invoice(factura_fiscal.facturapi_id, motivo)

			# Procesar respuesta exitosa
			factura_fiscal.fm_fiscal_status = "cancelled"
			factura_fiscal.cancelled_at = now_datetime()
			factura_fiscal.save()

			# Actualizar Sales Invoice
			frappe.db.set_value("Sales Invoice", sales_invoice_name, "fm_fiscal_status", "Cancelada")

			# Marcar evento como exitoso
			FiscalEventMX.mark_event_success(event_doc.name, response)

			frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure cancellation transaction is committed

			return {"success": True, "message": "Factura cancelada exitosamente"}

		except Exception as e:
			# Marcar evento como fallido
			if "event_doc" in locals():
				FiscalEventMX.mark_event_failed(event_doc.name, str(e))

			frappe.logger().error(f"Error cancelando factura {sales_invoice_name}: {e!s}")
			return {"success": False, "error": str(e), "message": f"Error al cancelar factura: {e!s}"}


# API endpoints para uso desde interfaz
@frappe.whitelist()
def timbrar_factura(sales_invoice_name: str):
	"""API para timbrar factura desde interfaz."""
	api = TimbradoAPI()
	return api.timbrar_factura(sales_invoice_name)


@frappe.whitelist()
def cancelar_factura(sales_invoice_name: str, motivo: str = "02"):
	"""API para cancelar factura desde interfaz."""
	api = TimbradoAPI()
	return api.cancelar_factura(sales_invoice_name, motivo)
