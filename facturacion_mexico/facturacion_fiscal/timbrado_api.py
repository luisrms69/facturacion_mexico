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
				event_type="stamp",
				reference_doctype="Factura Fiscal Mexico",
				reference_name=factura_fiscal.name,
				event_data={"sales_invoice": sales_invoice_name},
				status="pending",
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

			# Procesar error específico del PAC
			error_details = self._process_pac_error(e)

			# Registrar intento fallido en tabla de logs
			self._log_timbrado_attempt(
				sales_invoice_name=sales_invoice_name,
				attempt_type="Timbrado",
				status="Error",
				error_details=error_details["user_message"],
				pac_message=str(e),
			)

			# Actualizar estado en Sales Invoice
			frappe.db.set_value("Sales Invoice", sales_invoice_name, "fm_fiscal_status", "Error")
			frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure error state is persisted

			# Log error técnico
			frappe.logger().error(f"Error timbrado factura {sales_invoice_name}: {e!s}")

			return {
				"success": False,
				"error": str(e),
				"user_error": error_details["user_message"],
				"corrective_action": error_details["corrective_action"],
				"message": error_details["user_message"],
			}

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
		# Usar tax_id como único campo RFC
		customer_rfc = customer.get("tax_id")
		if not customer_rfc:
			frappe.throw(_("El cliente debe tener RFC configurado en Tax ID"))

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

		# Sprint 6 Phase 2: Obtener datos de sucursal si está configurada
		branch_data = self._get_branch_data_for_invoice(sales_invoice)

		# Datos del cliente
		customer_data = {
			"legal_name": customer.customer_name,
			"tax_id": customer.get("tax_id"),
			"email": customer.email_id or "cliente@example.com",
		}

		# VALIDACIÓN CRÍTICA: Dirección del cliente es REQUERIDA por PAC
		primary_address = self._get_customer_primary_address(customer)
		if not primary_address:
			# Error sin enviar al PAC - manejado por _process_pac_error()
			raise Exception(
				f"customer.address_required: El cliente {customer.customer_name} no tiene dirección primaria configurada"
			)

		customer_data["address"] = {
			"street": primary_address.get("address_line1") or "",
			"exterior": primary_address.get("address_line2") or "",
			"neighborhood": primary_address.get("city") or "",
			"city": primary_address.get("city") or "",
			"municipality": primary_address.get("city") or "",
			"state": primary_address.get("state") or "",
			"country": primary_address.get("country") or "MEX",
			"zip": primary_address.get("pincode") or "",
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
			"folio_number": branch_data.get("folio_number", sales_invoice.name),
			"series": branch_data.get("series", "F"),
			"use": sales_invoice.fm_cfdi_use,
		}

		# Sprint 6 Phase 2: Agregar datos específicos de sucursal
		if branch_data.get("lugar_expedicion"):
			invoice_data["place_of_issue"] = branch_data["lugar_expedicion"]

		if branch_data.get("branch_name"):
			invoice_data["branch_office"] = branch_data["branch_name"]

		return invoice_data

	def _get_branch_data_for_invoice(self, sales_invoice) -> dict[str, Any]:
		"""
		Obtener datos de sucursal para la factura
		Sprint 6 Phase 2: Integración multi-sucursal
		"""
		try:
			# Datos por defecto
			branch_data = {
				"folio_number": sales_invoice.name,
				"series": "F",
				"lugar_expedicion": None,
				"branch_name": None,
			}

			# Si no hay sucursal configurada, usar datos por defecto
			if not hasattr(sales_invoice, "fm_branch") or not sales_invoice.fm_branch:
				return branch_data

			# Obtener datos de la sucursal
			branch_doc = frappe.get_cached_doc("Branch", sales_invoice.fm_branch)

			# Actualizar con datos de la sucursal
			branch_data.update(
				{
					"lugar_expedicion": sales_invoice.get("fm_lugar_expedicion")
					or branch_doc.get("fm_lugar_expedicion"),
					"branch_name": branch_doc.branch,
					"series": self._extract_series_from_pattern(branch_doc.get("fm_serie_pattern", "F")),
				}
			)

			# Si hay serie y folio específicos de la sucursal, usarlos
			if hasattr(sales_invoice, "fm_serie_folio") and sales_invoice.fm_serie_folio:
				branch_data["folio_number"] = sales_invoice.fm_serie_folio

			return branch_data

		except Exception as e:
			frappe.log_error(
				f"Error getting branch data for invoice {sales_invoice.name}: {e!s}", "Branch Invoice Data"
			)
			# Retornar datos por defecto en caso de error
			return {
				"folio_number": sales_invoice.name,
				"series": "F",
				"lugar_expedicion": None,
				"branch_name": None,
			}

	def _extract_series_from_pattern(self, serie_pattern: str) -> str:
		"""
		Extraer serie del patrón de serie
		Ejemplo: A{####} -> A
		"""
		try:
			if "{" in serie_pattern:
				return serie_pattern.split("{")[0]
			return serie_pattern[:1] if serie_pattern else "F"
		except Exception:
			return "F"

	def _process_timbrado_success(self, sales_invoice, factura_fiscal, response, event_doc):
		"""Procesar respuesta exitosa de timbrado."""
		# Actualizar Factura Fiscal
		factura_fiscal.uuid = response.get("uuid")
		factura_fiscal.facturapi_id = response.get("id")
		factura_fiscal.fm_fiscal_status = "stamped"
		factura_fiscal.stamped_at = now_datetime()
		factura_fiscal.save()

		# Registrar intento exitoso en tabla de logs
		self._log_timbrado_attempt(
			sales_invoice_name=sales_invoice.name,
			attempt_type="Timbrado",
			status="Exitoso",
			pac_response_code="200",
			pac_message="Timbrado exitoso",
			response_data=response,
		)

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

	def _process_pac_error(self, error) -> dict[str, str]:
		"""Procesar errores del PAC y generar mensajes útiles para el usuario."""
		error_str = str(error).lower()

		# Errores específicos de customer.address
		if "customer.address" in error_str or "address_required" in error_str:
			# Extraer nombre del cliente del mensaje si está disponible
			customer_name = "el cliente"
			if "El cliente" in str(error):
				try:
					customer_name = str(error).split("El cliente ")[1].split(" no tiene")[0]
				except Exception:
					customer_name = "el cliente"

			return {
				"user_message": f"ERROR FISCAL: {customer_name} debe tener una dirección primaria configurada para el timbrado fiscal.",
				"corrective_action": f"Ir a Customer '{customer_name}' → Addresses → Agregar dirección primaria con todos los campos requeridos",
			}

		# Errores de RFC
		if "tax_id" in error_str or "rfc" in error_str:
			return {
				"user_message": "ERROR FISCAL: RFC del cliente inválido o faltante. Verifique que el campo Tax ID del cliente tenga un RFC válido.",
				"corrective_action": "Ir a Customer → Tax ID → Configurar RFC válido",
			}

		# Errores de productos SAT
		if "product_key" in error_str or "clave" in error_str:
			return {
				"user_message": "ERROR FISCAL: Algunos productos no tienen configurada la Clave de Producto/Servicio SAT requerida.",
				"corrective_action": "Ir a Item → Configurar Clave Producto/Servicio SAT",
			}

		# Errores de unidades de medida
		if "unit_key" in error_str or "unidad" in error_str:
			return {
				"user_message": "ERROR FISCAL: Algunas unidades de medida no tienen configurada la Clave de Unidad SAT requerida.",
				"corrective_action": "Ir a UOM → Configurar Clave Unidad SAT",
			}

		# Errores de uso CFDI
		if "uso" in error_str or "cfdi" in error_str:
			return {
				"user_message": "ERROR FISCAL: Uso CFDI faltante o inválido. Configure el Uso CFDI en la factura.",
				"corrective_action": "Configurar campo 'Uso CFDI' en la factura",
			}

		# Errores de API key o autenticación
		if "unauthorized" in error_str or "api" in error_str or "token" in error_str:
			return {
				"user_message": "ERROR DE AUTENTICACIÓN: Problema con las credenciales del PAC. Verifique la configuración de API keys.",
				"corrective_action": "Verificar Facturacion Mexico Settings → API Keys",
			}

		# Error genérico
		return {
			"user_message": f"ERROR FISCAL: {str(error)[:200]}...",
			"corrective_action": "Revisar los datos fiscales de la factura y el cliente",
		}

	def _log_timbrado_attempt(
		self,
		sales_invoice_name,
		attempt_type,
		status,
		pac_response_code=None,
		pac_message=None,
		request_data=None,
		response_data=None,
		error_details=None,
	):
		"""Registrar intento de timbrado en tabla de logs."""
		try:
			from facturacion_mexico.facturacion_fiscal.doctype.fiscal_attempt_log.fiscal_attempt_log import (
				FiscalAttemptLog,
			)

			# Obtener documento Sales Invoice
			sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)

			# Crear log de intento
			FiscalAttemptLog.create_attempt_log(
				parent_doc=sales_invoice,
				attempt_type=attempt_type,
				status=status,
				pac_response_code=pac_response_code,
				pac_message=pac_message,
				request_data=request_data,
				response_data=response_data,
				error_details=error_details,
			)

			frappe.logger().info(
				f"Log de intento {attempt_type} registrado para {sales_invoice_name}: {status}"
			)

		except Exception as e:
			frappe.logger().error(f"Error registrando log de intento: {e!s}")
			# No fallar el proceso principal por errores de logging

	def _get_customer_primary_address(self, customer):
		"""Obtener dirección primaria del customer."""
		try:
			# Buscar dirección primaria
			primary_address = frappe.db.sql(
				"""
				SELECT addr.name, addr.address_line1, addr.address_line2, addr.city,
				       addr.state, addr.country, addr.pincode
				FROM `tabAddress` addr
				INNER JOIN `tabDynamic Link` dl ON dl.parent = addr.name
				WHERE dl.link_doctype = 'Customer'
				AND dl.link_name = %s
				AND addr.is_primary_address = 1
				LIMIT 1
			""",
				customer.name,
				as_dict=True,
			)

			if primary_address:
				return primary_address[0]

			# Si no hay primaria, buscar cualquier dirección
			any_address = frappe.db.sql(
				"""
				SELECT addr.name, addr.address_line1, addr.address_line2, addr.city,
				       addr.state, addr.country, addr.pincode
				FROM `tabAddress` addr
				INNER JOIN `tabDynamic Link` dl ON dl.parent = addr.name
				WHERE dl.link_doctype = 'Customer'
				AND dl.link_name = %s
				LIMIT 1
			""",
				customer.name,
				as_dict=True,
			)

			if any_address:
				frappe.msgprint(
					_(
						"Advertencia: El cliente no tiene dirección primaria. Usando la primera dirección disponible."
					),
					indicator="orange",
				)
				return any_address[0]

			return None

		except Exception as e:
			frappe.logger().error(f"Error obteniendo dirección del customer {customer.name}: {e!s}")
			return None


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
