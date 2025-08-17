import json
import traceback
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from facturacion_mexico.config.fiscal_states_config import FiscalStates, OperationTypes
from facturacion_mexico.validaciones.api import _normalize_company_name_for_facturapi

from .api import write_pac_response  # PAC Response Writer - Arquitectura resiliente activada
from .api_client import get_facturapi_client
from .doctype.facturapi_response_log.facturapi_response_log import FacturAPIResponseLog


def _extract_sat_code_from_uom(uom_name):
	"""
	Extraer código SAT de UOM con formato 'CODIGO - Descripción'

	Args:
		uom_name (str): UOM name como "H87 - Pieza" o "KGM - Kilogramo"

	Returns:
		str: Código SAT extraído como "H87" o fallback "H87"
	"""
	if not uom_name:
		return "H87"  # Fallback por defecto

	# Verificar si tiene formato SAT: "CODIGO - Descripción"
	if " - " in uom_name:
		parts = uom_name.split(" - ")
		if len(parts) >= 2 and parts[0].strip():
			return parts[0].strip()

	# Si no tiene formato SAT, intentar mapear UOMs genéricas comunes
	uom_mapping = {
		"Pieza": "H87",
		"Piece": "H87",
		"Unit": "H87",
		"Nos": "H87",
		"Kg": "KGM",
		"Kilogram": "KGM",
		"Gram": "GRM",
		"Liter": "LTR",
		"Litre": "LTR",
		"Meter": "MTR",
		"Hour": "HUR",
		"Service": "E48",
		"Activity": "ACT",
	}

	return uom_mapping.get(uom_name, "H87")


class TimbradoAPI:
	"""API para timbrado de facturas usando FacturAPI.io."""

	def __init__(self):
		"""Inicializar API de timbrado."""
		self.client = get_facturapi_client()
		self.settings = frappe.get_single("Facturacion Mexico Settings")

	def timbrar_factura(self, sales_invoice_name: str) -> dict[str, Any]:
		"""Timbrar factura de Sales Invoice con arquitectura resiliente de 3 fases.

		Arquitectura de manejo de respuestas:
		- FASE 1: Preparación - Validaciones y creación de documentos
		- FASE 2: Comunicación PAC - Captura respuesta RAW inmediatamente
		- FASE 3: Actualización Frappe - Puede fallar sin contaminar Response Log

		Principio clave: Response Log SIEMPRE guarda la respuesta RAW del PAC,
		nunca mensajes sanitizados o errores de Frappe.

		Args:
			sales_invoice_name: Nombre del Sales Invoice a timbrar

		Returns:
			dict con:
			- success: bool indicando éxito
			- uuid: UUID del timbrado si exitoso
			- message: Mensaje para UI
			- user_error: Mensaje amigable si hay error
			- error: Error técnico si hay falla

		Raises:
			Exception: Solo si hay error antes de contactar PAC

		Nota:
			Los errores post-PAC exitoso retornan dict con success=False
			pero incluyen UUID para recuperación manual.
		"""
		pac_response = None
		pac_request = None
		factura_fiscal = None

		try:
			# FASE 1: PREPARACIÓN (puede fallar antes de contactar PAC)
			# Obtener Sales Invoice
			sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)

			# Validar que se pueda timbrar
			self._validate_invoice_for_timbrado(sales_invoice)

			# Obtener Factura Fiscal existente
			factura_fiscal = self._get_factura_fiscal(sales_invoice)

			# VALIDACIÓN CRÍTICA: Documento fiscal debe estar submitted
			if factura_fiscal.docstatus != 1:
				frappe.throw(
					_(
						"No se puede timbrar: el documento fiscal debe estar submitted (enviado). Use el botón Submit en Factura Fiscal Mexico primero."
					),
					title=_("Documento Fiscal Draft"),
				)

			# Preparar datos para FacturAPI
			invoice_data = self._prepare_facturapi_data(sales_invoice, factura_fiscal)

			# FASE 2: COMUNICACIÓN CON PAC - Captura respuesta REAL
			# Preparar request para auditoría
			pac_request = {
				"factura_fiscal": factura_fiscal.name,
				"request_id": f"{OperationTypes.TIMBRADO}_{frappe.generate_hash()[:8]}",
				"action": "timbrado",
				"sales_invoice": sales_invoice_name,
				"timestamp": frappe.utils.now(),
				"payload": invoice_data,
			}

			try:
				# CRÍTICO: Capturar respuesta RAW del PAC
				pac_response = self.client.create_invoice(invoice_data)

				# Crear response_data limpio para éxito
				response_data = {
					"success": True,
					"status_code": 200,
					"error_message": "",
					"raw_response": pac_response,  # el dict que te regresó FacturAPI
				}

				# Guardar Response Log INMEDIATAMENTE con respuesta REAL del PAC
				write_pac_response(
					sales_invoice_name,
					json.dumps(pac_request),
					json.dumps(response_data),
					"timbrado",
				)

			except Exception as pac_error:
				# Error DURANTE comunicación con PAC
				# Construir respuesta de error con datos RAW
				pac_response = {
					"success": False,
					"status_code": getattr(pac_error.response, "status_code", 500)
					if hasattr(pac_error, "response")
					else 500,
					"error": str(pac_error),
					"raw_response": getattr(pac_error.response, "text", "")
					if hasattr(pac_error, "response")
					else str(pac_error),
					"timestamp": frappe.utils.now(),
				}

				# Guardar respuesta de error RAW del PAC
				write_pac_response(
					sales_invoice_name,
					json.dumps(pac_request),
					json.dumps(pac_response),  # ✅ Error REAL del PAC
					"timbrado",
				)

				# Re-lanzar para manejo de UI
				raise pac_error

			# FASE 3: ACTUALIZACIÓN FRAPPE (puede fallar DESPUÉS de PAC exitoso)
			try:
				self._process_timbrado_success(sales_invoice, factura_fiscal, pac_response)

				# Mostrar mensaje de éxito formateado
				# Asegurarse de desempaquetar el wrapper del PAC response
				raw_pac = None
				if isinstance(pac_response, dict):
					raw_pac = (
						pac_response.get("raw_response") if "raw_response" in pac_response else pac_response
					)
				raw_pac = raw_pac if isinstance(raw_pac, dict) else {}

				uuid = raw_pac.get("uuid") or (
					factura_fiscal.fm_uuid if hasattr(factura_fiscal, "fm_uuid") else None
				)

				folio_completo = raw_pac.get("folio_number", sales_invoice.name)
				# Extraer solo el número del folio
				folio = folio_completo.split("-")[-1] if "-" in str(folio_completo) else folio_completo
				serie = raw_pac.get("series", "F")

				# Tomamos el total del JSON real del PAC; si aún no está, caemos al total ya guardado en el DocType
				total = raw_pac.get("total")
				if total is None:
					try:
						total = factura_fiscal.total_fiscal
					except Exception:
						total = None
				if total is None:
					try:
						total = sales_invoice.grand_total
					except Exception:
						total = 0

				total = flt(total or 0)

				frappe.msgprint(
					msg=f"""
					<div style="background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 5px; padding: 15px;">
						<h4 style="color: #155724; margin-top: 0;">✅ Factura Timbrada Exitosamente</h4>
						<p style="color: #155724; margin: 5px 0;"><strong>UUID:</strong> {uuid}</p>
						<p style="color: #155724; margin: 5px 0;"><strong>Serie-Folio:</strong> {serie}-{folio}</p>
						<p style="color: #155724; margin: 5px 0;"><strong>Total:</strong> ${total:,.2f}</p>
					</div>
					""",
					title=_("Timbrado Exitoso"),
					indicator="green",
					as_list=False,
					primary_action={
						"label": _("Cerrar"),
						"client_action": "frappe.hide_msgprint()",
						"hide_on_success": True,
					},
				)

				return {
					"success": True,
					"status_code": 200,
					"raw_response": pac_response,
					"uuid": uuid,
					"factura_fiscal": factura_fiscal.name,
					"message": "Factura timbrada exitosamente",  # Mensaje para UI
				}

			except Exception as frappe_error:
				# PAC exitoso pero Frappe falló al actualizar
				# Response Log YA tiene la respuesta correcta del PAC
				frappe.log_error(
					f"Error post-timbrado actualizando Frappe: {frappe_error}\nUUID: {pac_response.get('uuid')}",
					"Post-Timbrado Error",
				)

				# Actualizar estado a ERROR pero mantener UUID
				frappe.db.set_value(
					"Sales Invoice", sales_invoice_name, "fm_fiscal_status", FiscalStates.ERROR
				)
				frappe.db.commit()

				# Retornar éxito parcial para UI
				return {
					"success": False,
					"uuid": pac_response.get("uuid"),  # ¡Tenemos UUID!
					"facturapi_id": pac_response.get("id"),
					"error": str(frappe_error),
					"message": f"Timbrado exitoso (UUID: {pac_response.get('uuid')}) pero error al actualizar sistema",
					"user_error": "La factura se timbró correctamente pero hubo un error actualizando el sistema. Contacte soporte con el UUID mostrado.",
				}

		except Exception as e:
			# Error ANTES del PAC o error del PAC ya manejado arriba
			if not pac_response:
				# Error antes de llamar al PAC - NO guardar en Response Log (no es respuesta PAC)
				frappe.log_error(
					f"Error pre-timbrado (antes de contactar PAC): {e}\nSales Invoice: {sales_invoice_name}",
					"Pre-Timbrado Error",
				)
			else:
				# Error del PAC ya fue guardado en Response Log arriba
				frappe.log_error(
					f"Error timbrado PAC: {e}\nSales Invoice: {sales_invoice_name}", "PAC Timbrado Error"
				)

			# Actualizar estado a ERROR
			frappe.db.set_value("Sales Invoice", sales_invoice_name, "fm_fiscal_status", FiscalStates.ERROR)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure error state is persisted

			# Generar mensaje amigable SOLO para UI (nunca para Response Log)
			error_details = self._process_pac_error(e)

			# --- INICIO NORMALIZACIÓN ERROR FACTURAPI ---
			status_code = 500
			error_text = str(e)

			resp = getattr(e, "response", None)
			if resp is not None:
				try:
					status_code = getattr(resp, "status_code", 500) or 500
				except Exception:
					status_code = 500

			# Extraer de la cadena "Error FacturAPI 400:" si existe
			import re

			m = re.search(r"Error\s+FacturAPI\s+(\d{3})", error_text)
			if m:
				try:
					status_code = int(m.group(1))
				except Exception:
					pass

			# Capturar respuesta cruda del PAC sin duplicar 'error_message'
			raw_response = None
			if resp is not None:
				try:
					raw_response = resp.json()
				except Exception:
					raw_response = getattr(resp, "text", None)

			payload = {
				"success": False,
				"status_code": status_code,
				"error_message": error_text,  # legible para UI/log
				"raw_response": raw_response,  # JSON/texto crudo; no dupliques error_message aquí
				"user_error": error_details["user_message"],  # MENSAJE AMIGABLE PARA UX
				"corrective_action": error_details["corrective_action"],
				"message": error_details["user_message"],  # UI usa este para mostrar al usuario
			}

			frappe.logger().info(
				{
					"tag": "PAC_TIMBRADO_EXTRACT",
					"status_code_final": status_code,
					"had_response_obj": bool(resp),
					"error_text": error_text[:300],
				}
			)

			return payload
			# --- FIN NORMALIZACIÓN ERROR FACTURAPI ---

	def _validate_invoice_for_timbrado(self, sales_invoice):
		"""Validar que la factura se puede timbrar."""
		# Verificar que esté submitted
		if sales_invoice.docstatus != 1:
			frappe.throw(_("La factura debe estar enviada para timbrar"))

		# Verificar que no esté ya timbrada - MIGRADO A ARQUITECTURA RESILIENTE
		if sales_invoice.fm_fiscal_status == FiscalStates.TIMBRADO:
			frappe.throw(_("La factura ya está timbrada"))

		# Verificar datos del cliente
		if not sales_invoice.customer:
			frappe.throw(_("Se requiere cliente para timbrar"))

		customer = frappe.get_doc("Customer", sales_invoice.customer)
		# Usar tax_id como único campo RFC
		customer_rfc = customer.get("tax_id")
		if not customer_rfc:
			frappe.throw(_("El cliente debe tener RFC configurado en Tax ID"))

		# NUEVA VALIDACIÓN: País del cliente ANTES del timbrado
		primary_address = self._get_customer_primary_address(customer)
		if primary_address:
			country = primary_address.get("country")
			if not self._is_valid_country_for_facturapi(country):
				frappe.throw(
					_(
						"ERROR FISCAL: El país '{0}' en la dirección del cliente no es reconocido por el sistema. "
						"Para facturación fiscal mexicana, configure el campo Country como: 'México', 'Mexico', 'MEX' o 'MX'. "
						"Países soportados: México, Estados Unidos, Canada. "
						"Corrija el campo Country en la dirección primaria del cliente."
					).format(country or "Sin especificar"),
					title=_("País No Soportado para Timbrado"),
					exc=frappe.ValidationError,
				)

		# Verificar uso de CFDI - validación temprana en datos fiscales
		fiscal_doc = self._get_factura_fiscal_doc(sales_invoice)
		if fiscal_doc and not fiscal_doc.get("fm_cfdi_use"):
			frappe.throw(_("Se requiere configurar Uso de CFDI en los datos fiscales"))

		# Verificar que tenga items
		if not sales_invoice.items:
			frappe.throw(_("La factura debe tener al menos un item"))

	def _get_factura_fiscal(self, sales_invoice):
		"""Obtener Factura Fiscal México existente."""
		if not sales_invoice.fm_factura_fiscal_mx:
			frappe.throw(
				_(
					"No existe Factura Fiscal asociada. Debe crear y hacer submit de la Factura Fiscal antes de timbrar."
				),
				title=_("Factura Fiscal No Encontrada"),
			)

		return frappe.get_doc("Factura Fiscal Mexico", sales_invoice.fm_factura_fiscal_mx)

	def _prepare_facturapi_data(self, sales_invoice, factura_fiscal) -> dict[str, Any]:
		"""Preparar datos para FacturAPI."""
		customer = frappe.get_doc("Customer", sales_invoice.customer)

		# Sprint 6 Phase 2: Obtener datos de sucursal si está configurada
		branch_data = self._get_branch_data_for_invoice(sales_invoice)

		# Datos del cliente
		customer_data = {
			"legal_name": _normalize_company_name_for_facturapi(
				customer.customer_name
			),  # CFDI 4.0: función idéntica a validación RFC/CSF
			"tax_id": customer.get("tax_id"),
			"email": customer.email_id or self.settings.get("customer_email_fallback"),
		}

		# TODO: Email fallback configurable desde Facturacion Mexico Settings
		# Si no hay email del cliente ni configurado en settings, email queda None (sin envío correos)

		# MIGRACIÓN ARQUITECTURAL: Tax system OBLIGATORIO desde Factura Fiscal
		tax_system_code = self._get_tax_system_for_timbrado(factura_fiscal, customer)
		if not tax_system_code:
			# ERROR CRÍTICO: Sin tax_system no se puede enviar a FacturAPI
			raise Exception(
				f"customer.tax_system_required: El cliente {customer.customer_name} no tiene Tax Category configurada. "
				f"Configure Tax Category en el cliente para que se popule fm_tax_system en Factura Fiscal Mexico."
			)

		customer_data["tax_system"] = tax_system_code

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
			"country": self._convert_country_to_iso3(primary_address.get("country")) or "MEX",
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
						"tax_included": False,  # Indicar que el precio NO incluye impuestos
						"unit_key": _extract_sat_code_from_uom(item.uom),
						"unit_name": item.uom or "Pieza",
					},
				}
			)

		# Obtener forma de pago desde Factura Fiscal Mexico
		payment_form = self._get_payment_form_for_invoice(sales_invoice)

		# Obtener uso CFDI desde Factura Fiscal Mexico
		fiscal_doc = self._get_factura_fiscal_doc(sales_invoice)
		cfdi_use = fiscal_doc.get("fm_cfdi_use") if fiscal_doc else None

		if not cfdi_use:
			frappe.throw(
				_(
					"No se puede timbrar: falta configurar 'Uso CFDI Default' en el Customer. Configure el campo en Customer → Fiscal → Uso CFDI Default."
				),
				title=_("Uso CFDI Requerido en Customer"),
			)

		# Datos de la factura
		invoice_data = {
			"customer": customer_data,
			"items": items,
			"payment_form": payment_form,
			"folio_number": branch_data.get("folio_number", sales_invoice.name),
			"series": branch_data.get("series", "F"),
			"use": cfdi_use,
		}

		# Sprint 6 Phase 2: Agregar datos específicos de sucursal
		if branch_data.get("lugar_expedicion"):
			invoice_data["place_of_issue"] = branch_data["lugar_expedicion"]

		if branch_data.get("branch_name"):
			invoice_data["branch_office"] = branch_data["branch_name"]

		return invoice_data

	def _get_payment_form_for_invoice(self, sales_invoice) -> str:
		"""
		Obtener forma de pago SAT para timbrado desde Factura Fiscal Mexico.
		NUEVA ARQUITECTURA: Lee datos fiscales desde documento separado.
		"""
		# Obtener documento Factura Fiscal Mexico
		fiscal_doc = self._get_factura_fiscal_doc(sales_invoice)
		if not fiscal_doc:
			frappe.throw(
				_(
					"No se puede timbrar: no existe documento fiscal asociado. "
					"Configure los datos fiscales primero."
				),
				title=_("Documento Fiscal Requerido"),
			)

		# Prioridad 1: Campo fm_forma_pago_timbrado de Factura Fiscal Mexico
		if fiscal_doc.get("fm_forma_pago_timbrado"):
			# Extraer código SAT del formato "01 - Efectivo"
			mode_parts = fiscal_doc.fm_forma_pago_timbrado.split(" - ")
			if len(mode_parts) >= 2 and mode_parts[0].strip().isdigit():
				return mode_parts[0].strip()

		# Prioridad 2: Lógica basada en método de pago SAT SOLO para PPD
		if fiscal_doc.get("fm_payment_method_sat"):
			if fiscal_doc.fm_payment_method_sat == "PPD":
				# PPD siempre usa "99 - Por definir"
				return "99"

		# Si no hay forma de pago definida, lanzar error - NO usar defaults
		frappe.throw(
			_(
				"No se puede timbrar: falta definir la forma de pago en los datos fiscales. "
				"Configure 'Forma de Pago para Timbrado' en el documento Factura Fiscal Mexico."
			),
			title=_("Forma de Pago Requerida"),
		)

	def _get_factura_fiscal_doc(self, sales_invoice):
		"""Obtener documento Factura Fiscal Mexico asociado"""
		if not sales_invoice.fm_factura_fiscal_mx:
			return None

		try:
			return frappe.get_doc("Factura Fiscal Mexico", sales_invoice.fm_factura_fiscal_mx)
		except frappe.DoesNotExistError:
			return None

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

	def _process_timbrado_success(self, sales_invoice, factura_fiscal, response):
		"""Procesar respuesta exitosa de timbrado.

		NOTA: El Response Log ya fue guardado ANTES de llamar este método.
		Este método solo actualiza los documentos Frappe con los datos del timbrado.
		"""
		# --- QUIRÚRGICO: asegurar que 'response' sea SIEMPRE el JSON crudo del PAC ---
		if isinstance(response, dict) and "raw_response" in response:
			# venía envuelto en response_data (wrapper); extraemos el JSON del PAC
			response = response.get("raw_response") or {}
		elif not isinstance(response, dict):
			# por seguridad, que sea dict
			response = {}
		# -------------------------------------------------------------------------------

		try:
			# Log inicial para debugging
			frappe.logger().info(f"Iniciando _process_timbrado_success para {factura_fiscal.name}")
			frappe.logger().info(
				f"Response contiene: uuid={response.get('uuid')}, total={response.get('total')}"
			)

			# Preparar campos a actualizar
			fields_to_update = {
				"fm_uuid": response.get("uuid"),
				"facturapi_id": response.get("id"),
				"fm_fiscal_status": FiscalStates.TIMBRADO,
				"fecha_timbrado": response.get("stamp", {}).get("date") or now_datetime(),
			}

			# Agregar campos opcionales si vienen en respuesta
			if response.get("series"):
				fields_to_update["serie"] = response.get("series")
				frappe.logger().info(f"Serie a actualizar: {response.get('series')}")

			if response.get("folio_number"):
				# TODO: Revisar Formación de Folio con FacturAPI
				# La lógica actual extrae solo el número del Sales Invoice ID
				# Ej: "ACC-SINV-2025-00965" -> "00965"
				# Verificar si FacturAPI espera/devuelve el folio de otra manera
				folio_completo = str(response.get("folio_number"))
				folio_numero = folio_completo.split("-")[-1] if "-" in folio_completo else folio_completo
				fields_to_update["folio"] = folio_numero
				frappe.logger().info(f"Folio a actualizar: {folio_numero} (de {folio_completo})")

			if response.get("total"):
				fields_to_update["total_fiscal"] = flt(response.get("total"))
				frappe.logger().info(f"Total fiscal a actualizar: {response.get('total')}")

			# Guardar URLs de archivos si vienen en respuesta
			if response.get("xml_url"):
				fields_to_update["fm_xml_url"] = response.get("xml_url")
			if response.get("pdf_url"):
				fields_to_update["fm_pdf_url"] = response.get("pdf_url")

			# IMPORTANTE: Logging antes de actualizar
			frappe.logger().info(f"Actualizando Factura Fiscal {factura_fiscal.name} con: {fields_to_update}")

			# Usar frappe.set_value que maneja correctamente documentos submitted
			# Este método internamente usa el ORM y respeta allow_on_submit
			frappe.set_value("Factura Fiscal Mexico", factura_fiscal.name, fields_to_update)

			frappe.logger().info("Factura Fiscal actualizada exitosamente via frappe.set_value")

			# Validar discrepancias de montos
			self._validate_amount_discrepancies(factura_fiscal, response)

			# Actualizar Sales Invoice
			frappe.set_value("Sales Invoice", sales_invoice.name, {"fm_fiscal_status": FiscalStates.TIMBRADO})

			# Descargar archivos si está configurado
			if self.settings.download_files_default:
				self._download_fiscal_files(factura_fiscal, response.get("id"))

			frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure fiscal transaction is committed after successful stamping

			frappe.logger().info("_process_timbrado_success completado exitosamente")

		except Exception as e:
			frappe.logger().error(f"Error en _process_timbrado_success: {e}\n{traceback.format_exc()}")
			raise  # Re-lanzar para que se maneje arriba

	def _validate_amount_discrepancies(self, factura_fiscal, response):
		"""Validar discrepancias entre montos del Sales Invoice y respuesta del PAC."""
		from frappe.utils import flt

		# Obtener total fiscal del PAC
		total_pac = flt(response.get("total", 0))

		# Obtener totales del Sales Invoice guardados en Factura Fiscal
		si_total_sin_iva = flt(factura_fiscal.si_total_antes_iva)
		si_total_con_iva = flt(factura_fiscal.si_total_neto)

		# Calcular diferencias
		diff_sin_iva = abs(total_pac - si_total_sin_iva)
		diff_con_iva = abs(total_pac - si_total_con_iva)

		# Determinar cuál es la diferencia relevante (la menor)
		# Si el PAC recibió sin IVA, debería coincidir con si_total_antes_iva
		# Si el PAC recibió con IVA, debería coincidir con si_total_neto
		min_diff = min(diff_sin_iva, diff_con_iva)

		# Validar discrepancias
		if min_diff > 1.0:  # Diferencia mayor a 1 peso
			frappe.msgprint(
				msg=f"""
				<div style="color: red; font-weight: bold;">
					⚠️ ADVERTENCIA: Discrepancia significativa en montos<br>
					Total PAC: ${total_pac:,.2f}<br>
					Total ERPNext (sin IVA): ${si_total_sin_iva:,.2f}<br>
					Total ERPNext (con IVA): ${si_total_con_iva:,.2f}<br>
					Diferencia: ${min_diff:,.2f}
				</div>
				""",
				title="Discrepancia de Montos",
				indicator="red",
			)
		elif min_diff > 0.01:  # Diferencia entre 0.01 y 1 peso
			frappe.msgprint(
				msg=f"""
				<div style="color: orange;">
					⚠️ Advertencia: Diferencia menor en montos<br>
					Total PAC: ${total_pac:,.2f}<br>
					Total ERPNext: ${si_total_sin_iva:,.2f} (sin IVA) / ${si_total_con_iva:,.2f} (con IVA)<br>
					Diferencia: ${min_diff:,.2f}
				</div>
				""",
				title="Diferencia de Redondeo",
				indicator="orange",
			)

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

	def cancelar_factura(
		self, sales_invoice_name: str, motivo: str, substitution_uuid: str | None = None
	) -> dict[str, Any]:
		"""Cancelar factura timbrada con arquitectura resiliente de 3 fases.

		Sigue la misma arquitectura que timbrar_factura:
		- Response Log guarda respuesta RAW del PAC
		- Errores Frappe no contaminan el log de auditoría
		- Mensajes UI se generan separadamente

		Args:
			sales_invoice_name: Nombre del Sales Invoice a cancelar
			motivo: Código de motivo de cancelación SAT (default: "02")
				- "01": Comprobantes emitidos con errores con relación
				- "02": Comprobantes emitidos con errores sin relación
				- "03": No se llevó a cabo la operación
				- "04": Operación nominativa relacionada en factura global

		Returns:
			dict con:
			- success: bool indicando éxito
			- message: Mensaje para UI
			- error: Error técnico si hay falla

		Raises:
			Exception: Solo si hay error antes de contactar PAC
		"""
		pac_response = None
		pac_request = None
		factura_fiscal = None

		try:
			# FASE 1: PREPARACIÓN Y VALIDACIONES
			sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)

			# Validar que se pueda cancelar
			if sales_invoice.fm_fiscal_status != FiscalStates.TIMBRADO:
				frappe.throw(_("Solo se pueden cancelar facturas timbradas"))

			if not sales_invoice.fm_factura_fiscal_mx:
				frappe.throw(_("No se encontró factura fiscal asociada"))

			factura_fiscal = frappe.get_doc("Factura Fiscal Mexico", sales_invoice.fm_factura_fiscal_mx)

			# FASE 2: COMUNICACIÓN CON PAC
			# Preparar request para auditoría
			pac_request = {
				"factura_fiscal": factura_fiscal.name,
				"request_id": f"CANCELACION_{frappe.generate_hash()[:8]}",
				"action": "cancelacion",
				"sales_invoice": sales_invoice_name,
				"facturapi_id": factura_fiscal.facturapi_id,  # ID enviado a FacturAPI
				"motive": motivo,
				"timestamp": frappe.utils.now(),
			}

			try:
				# Debug logging para verificar parámetros
				frappe.logger().info(
					f"Enviando cancelación a FacturAPI: invoice_id={factura_fiscal.facturapi_id}, motivo='{motivo}', substitution_uuid='{substitution_uuid}'"
				)

				# CRÍTICO: Capturar respuesta RAW del PAC
				pac_response = self.client.cancel_invoice(
					factura_fiscal.facturapi_id, motivo, substitution_uuid
				)

				# Guardar Response Log INMEDIATAMENTE con respuesta REAL del PAC
				write_pac_response(
					sales_invoice_name,
					json.dumps(pac_request),
					json.dumps(pac_response),  # ✅ Respuesta REAL del PAC
					"cancelacion",
				)

			except Exception as pac_error:
				# Error DURANTE comunicación con PAC
				pac_response = {
					"success": False,
					"status_code": getattr(pac_error.response, "status_code", 500)
					if hasattr(pac_error, "response")
					else 500,
					"error": str(pac_error),
					"raw_response": getattr(pac_error.response, "text", "")
					if hasattr(pac_error, "response")
					else str(pac_error),
					"timestamp": frappe.utils.now(),
				}

				# Guardar respuesta de error RAW del PAC
				write_pac_response(
					sales_invoice_name,
					json.dumps(pac_request),
					json.dumps(pac_response),  # ✅ Error REAL del PAC
					"cancelacion",
				)

				# Re-lanzar para manejo de UI
				raise pac_error

			# FASE 3: ACTUALIZACIÓN FRAPPE
			try:
				# Construir valor EXACTO esperado por campo Select del DocType
				motivo_completo = _build_cancellation_reason_for_select(motivo)

				frappe.set_value(
					"Factura Fiscal Mexico",
					factura_fiscal.name,
					{
						"fm_fiscal_status": FiscalStates.CANCELADO,
						"cancellation_date": now_datetime(),
						"cancellation_reason": motivo_completo,
					},
				)

				# Actualizar Sales Invoice
				frappe.set_value(
					"Sales Invoice", sales_invoice_name, {"fm_fiscal_status": FiscalStates.CANCELADO}
				)

				frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure cancellation transaction is committed

				# Obtener estados actualizados para response coherente
				si_doc = frappe.get_doc("Sales Invoice", sales_invoice_name)

				return {
					"ok": True,  # Para consistencia con propuesta UX
					"success": True,  # Backward compatibility
					"ffm": factura_fiscal.name,
					"sales_invoice": sales_invoice_name,
					"status_ffm": "CANCELADO",
					"status_si": si_doc.fm_fiscal_status,
					"uuid": factura_fiscal.fm_uuid,
					"cancellation_date": frappe.utils.now_datetime().strftime("%Y-%m-%d %H:%M:%S"),
					"message": "Factura cancelada exitosamente",
				}

			except Exception as frappe_error:
				# PAC canceló exitosamente pero Frappe falló - CREAR RECOVERY TASK
				frappe.log_error(
					f"Error post-cancelación actualizando Frappe: {frappe_error}", "Post-Cancelación Error"
				)

				# CRÍTICO: Crear Recovery Task para que jobs automáticos corrijan el estado
				try:
					recovery_task = frappe.get_doc(
						{
							"doctype": "Fiscal Recovery Task",
							"task_type": "sync_error",
							"reference_name": factura_fiscal.name,
							"priority": 5,  # Alta prioridad
							"status": "pending",
							"attempts": 0,
							"max_attempts": 5,
							"scheduled_time": frappe.utils.now(),
							"last_error": str(frappe_error),
							"recovery_data": frappe.as_json(
								{
									"sales_invoice": sales_invoice_name,
									"motivo": motivo,
									"pac_success": True,
									"error_type": "frappe_validation",
								}
							),
						}
					)
					recovery_task.insert(ignore_permissions=True)
					frappe.db.commit()

					frappe.logger().info(
						f"✅ Recovery Task creado: {recovery_task.name} para {factura_fiscal.name}"
					)

				except Exception as recovery_error:
					frappe.log_error(
						f"Error creando Recovery Task: {recovery_error}", "Recovery Task Creation Error"
					)

				return {
					"success": False,
					"error": str(frappe_error),
					"message": "Cancelación exitosa en PAC pero error actualizando sistema. Recovery automático programado.",
					"user_error": "La factura se canceló correctamente en el SAT. El sistema se corregirá automáticamente en unos minutos.",
				}

		except Exception as e:
			# Error ANTES del PAC o error del PAC ya manejado
			if not pac_response:
				# Error antes de llamar al PAC - NO guardar en Response Log
				frappe.log_error(
					f"Error pre-cancelación (antes de contactar PAC): {e}\nSales Invoice: {sales_invoice_name}",
					"Pre-Cancelación Error",
				)
			else:
				# Error del PAC ya fue guardado en Response Log
				frappe.log_error(
					f"Error cancelación PAC: {e}\nSales Invoice: {sales_invoice_name}",
					"PAC Cancelación Error",
				)

			# Generar mensaje amigable SOLO para UI
			error_details = self._process_pac_error(e)

			return {
				"success": False,
				"error": str(e),
				"message": error_details["user_message"],
				"corrective_action": error_details["corrective_action"],
			}

	def _process_pac_error(self, error) -> dict[str, str]:
		"""Procesar errores y generar mensajes amigables SOLO para UI.

		IMPORTANTE: Los mensajes generados aquí son para mejorar UX,
		NUNCA deben guardarse en Response Log que es solo auditoría.

		Args:
			error: Exception o error string a procesar

		Returns:
			dict con:
			- user_message: Mensaje amigable para mostrar al usuario
			- corrective_action: Acción sugerida para resolver el problema
			- status_code: Código HTTP estimado del error

		Nota:
			Esta función interpreta errores técnicos y los convierte
			en mensajes comprensibles para usuarios no técnicos.
		"""
		error_str = str(error).lower()

		# Intentar extraer status code de diferentes tipos de errores
		status_code = "500"  # default
		try:
			# Si es HTTPError o similar, intentar extraer status code
			if hasattr(error, "response") and hasattr(error.response, "status_code"):
				status_code = str(error.response.status_code)
			elif "400" in str(error):
				status_code = "400"
			elif "401" in str(error):
				status_code = "401"
			elif "403" in str(error):
				status_code = "403"
			elif "404" in str(error):
				status_code = "404"
		except Exception:
			pass

		# Errores específicos de país (más específico primero)
		# NOTA: Este error NO debería ocurrir ahora gracias a la validación preventiva
		if "customer.address.country" in error_str and "3 characters" in error_str:
			return {
				"user_message": "ERROR FISCAL: País del cliente no válido. La validación previa falló - esto indica un error en el sistema.",
				"corrective_action": "Contactar soporte técnico - la validación previa debió prevenir este error",
				"status_code": status_code,
			}

		# Errores específicos de customer.address (dirección primaria)
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
				"status_code": status_code,
			}

		# Errores de RFC
		if "tax_id" in error_str or "rfc" in error_str:
			return {
				"user_message": "ERROR FISCAL: RFC del cliente inválido o faltante. Verifique que el campo Tax ID del cliente tenga un RFC válido.",
				"corrective_action": "Ir a Customer → Tax ID → Configurar RFC válido",
				"status_code": status_code,
			}

		# Errores de productos SAT
		if "product_key" in error_str or "clave" in error_str:
			return {
				"user_message": "ERROR FISCAL: Algunos productos no tienen configurada la Clave de Producto/Servicio SAT requerida.",
				"corrective_action": "Ir a Item → Configurar Clave Producto/Servicio SAT",
				"status_code": status_code,
			}

		# Errores de unidades de medida
		if "unit_key" in error_str or "unidad" in error_str:
			return {
				"user_message": "ERROR FISCAL: Algunas unidades de medida no tienen configurada la Clave de Unidad SAT requerida.",
				"corrective_action": "Ir a UOM → Configurar Clave Unidad SAT",
				"status_code": status_code,
			}

		# Errores de uso CFDI
		if "uso" in error_str or "cfdi" in error_str:
			return {
				"user_message": "ERROR FISCAL: Uso CFDI faltante o inválido. Configure el Uso CFDI en la factura.",
				"corrective_action": "Configurar campo 'Uso CFDI' en la factura",
				"status_code": status_code,
			}

		# Errores de API key o autenticación
		if "unauthorized" in error_str or "api" in error_str or "token" in error_str:
			return {
				"user_message": "ERROR DE AUTENTICACIÓN: Problema con las credenciales del PAC. Verifique la configuración de API keys.",
				"corrective_action": "Verificar Facturacion Mexico Settings → API Keys",
				"status_code": status_code,
			}

		# Error genérico
		return {
			"user_message": f"ERROR FISCAL: {str(error)[:200]}...",
			"corrective_action": "Revisar los datos fiscales de la factura y el cliente",
			"status_code": status_code,
		}

	# Método _log_timbrado_attempt eliminado - funcionalidad duplicada con FacturAPI Response Log

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

	def _is_valid_country_for_facturapi(self, country):
		"""Validar si podemos convertir el país para FacturAPI."""
		return self._convert_country_to_iso3(country) is not None

	def _convert_country_to_iso3(self, country):
		"""Convertir país a código ISO3 para FacturAPI."""
		if not country:
			return None

		country_mapping = {
			# Nombres en español
			"México": "MEX",
			"Mexico": "MEX",
			"méxico": "MEX",
			"mexico": "MEX",
			# Códigos ISO alpha-2 a alpha-3
			"MX": "MEX",
			# Códigos ya correctos (3 caracteres)
			"MEX": "MEX",
			# Otros países comunes
			"Estados Unidos": "USA",
			"United States": "USA",
			"US": "USA",
			"USA": "USA",
			"Canada": "CAN",
			"Canadá": "CAN",
			"CA": "CAN",
			"CAN": "CAN",
		}

		return country_mapping.get(country.strip())

	def _get_tax_system_for_timbrado(self, factura_fiscal, customer):
		"""
		Obtener tax_system ESTRICTAMENTE desde Factura Fiscal.

		MIGRACIÓN ARQUITECTURAL: Solo usar fm_tax_system de Factura Fiscal Mexico.
		NO hay fallback a customer.tax_category directamente.

		Args:
			factura_fiscal: Documento Factura Fiscal Mexico
			customer: Documento Customer (solo para logging)

		Returns:
			str: tax_system code (ej: "601") o None si no disponible
		"""
		# ÚNICA FUENTE: Campo fm_tax_system en Factura Fiscal Mexico
		if hasattr(factura_fiscal, "fm_tax_system"):
			raw_value = factura_fiscal.fm_tax_system

			# CORRECCIÓN: Detectar None (null) y repoblar automáticamente ANTES de validaciones
			if raw_value is None:
				# Intentar repoblar desde customer.tax_category
				customer = frappe.get_doc("Customer", factura_fiscal.customer)
				if customer and customer.tax_category:
					# Extraer código del tax_category (formato: "601 - Descripción" -> "601")
					tax_code = customer.tax_category.split(" - ")[0].strip()

					# Actualizar el campo en la Factura Fiscal
					factura_fiscal.fm_tax_system = tax_code
					factura_fiscal.save()
					# Manual commit required: Auto-repopulation must persist immediately during timbrado process
					# to ensure data correction survives if subsequent timbrado operations fail
					frappe.db.commit()  # nosemgrep

					raw_value = tax_code
				else:
					return None

			# Validación normal para valores reales (incluyendo valores repoblados)
			if raw_value:
				# Limpiar posibles mensajes de error como "⚠️ FALTA TAX CATEGORY"
				tax_system = raw_value.strip()

				if not tax_system.startswith("⚠️") and not tax_system.startswith("❌"):
					# Validar rango SAT antes de retornar
					if self._validate_tax_system_sat_range(tax_system):
						return tax_system
					else:
						# Tax system fuera de rango SAT válido - log para debugging
						frappe.logger().warning(
							f"Tax system {tax_system} fuera de rango SAT válido (600-630) para factura {factura_fiscal.name}"
						)

		return None

	def _validate_tax_system_sat_range(self, tax_system_code):
		"""
		Validar que el código de régimen fiscal sea válido según SAT.

		CAMBIO 4: Validación de rango 600-630 para regímenes fiscales SAT.

		Args:
			tax_system_code (str): Código como "601"

		Returns:
			bool: True si válido, False si inválido
		"""
		if not tax_system_code:
			return False

		try:
			# Convertir a número para validación de rango
			code_num = int(tax_system_code.strip())

			# Validar rango SAT: 600-630 (regímenes fiscales válidos)
			return 600 <= code_num <= 630

		except (ValueError, TypeError):
			# No es número válido
			return False


def _build_cancellation_reason_for_select(motive_code: str) -> str:
	"""Devuelve el texto EXACTO esperado por el campo Select, validando contra el DocType."""
	from facturacion_mexico.config.sat_cancellation_motives import SATCancellationMotives

	desc = SATCancellationMotives.get_description(
		motive_code
	)  # p.ej. "Comprobantes emitidos con errores sin relación"
	candidate = f"{motive_code} - {desc}"  # con guión, no con tab

	# Validar contra opciones del DocType (evita drift)
	meta = frappe.get_meta("Factura Fiscal Mexico")
	field = meta.get_field("cancellation_reason")
	opts = [(o or "").strip() for o in (field.options or "").split("\n") if (o or "").strip()]

	# Si existe exactamente, úsalo. Si no, intenta por prefijo "NN -"
	if candidate in opts:
		return candidate
	for o in opts:
		if o.startswith(f"{motive_code} -"):
			return o

	# Último recurso: lanza error claro para ajustar catálogo/doctype
	frappe.throw(
		f"No se encontró opción válida para motivo {motive_code}. Ajusta DocType u opciones.",
		title="Opciones de cancelación inválidas",
	)


# API endpoints para uso desde interfaz
@frappe.whitelist()
def timbrar_factura(sales_invoice: str):
	"""API para timbrar factura desde interfaz."""
	api = TimbradoAPI()
	return api.timbrar_factura(sales_invoice)


@frappe.whitelist()
def cancelar_factura(sales_invoice=None, uuid=None, ffm_name=None, motivo=None, substitution_uuid=None):
	"""API para cancelar factura desde interfaz - tolerante a múltiples parámetros."""
	# Si no se proporciona sales_invoice, intentar derivarlo
	if not sales_invoice:
		if uuid:
			# Buscar sales_invoice por UUID
			ffm_doc = frappe.get_all(
				"Factura Fiscal Mexico", filters={"fm_uuid": uuid}, fields=["sales_invoice"], limit=1
			)
			if ffm_doc:
				sales_invoice = ffm_doc[0].sales_invoice
		elif ffm_name:
			# Buscar sales_invoice por nombre FFM
			ffm_doc = frappe.get_doc("Factura Fiscal Mexico", ffm_name)
			sales_invoice = ffm_doc.sales_invoice

	if not sales_invoice:
		frappe.throw("No se pudo determinar el Sales Invoice para cancelación")

	# Importar enum de motivos SAT
	from facturacion_mexico.config.sat_cancellation_motives import SAT_MOTIVES

	# Validación motivo es obligatorio
	if not motivo:
		frappe.throw("El motivo de cancelación es obligatorio. Debe seleccionar una opción.")

	# Extraer solo el código del valor del select (formato: "02\tDescripción")
	motivo_code = motivo.split("\t")[0] if "\t" in motivo else motivo

	# Validación motivo es válido según SAT
	if not SAT_MOTIVES.is_valid_code(motivo_code):
		valid_codes = ", ".join(SAT_MOTIVES.VALID_CODES)
		frappe.throw(f"Motivo de cancelación '{motivo}' no es válido. Códigos válidos SAT: {valid_codes}")

	# Validación motivos que requieren UUID sustitución
	if SAT_MOTIVES.requires_substitution_uuid(motivo_code) and not substitution_uuid:
		description = SAT_MOTIVES.get_description(motivo_code)
		frappe.throw(f"El motivo '{motivo_code}' ({description}) requiere UUID de sustitución obligatorio")

	api = TimbradoAPI()
	return api.cancelar_factura(sales_invoice, motivo_code, substitution_uuid)


@frappe.whitelist()
def get_sat_cancellation_motives():
	"""API para obtener motivos de cancelación SAT para UI."""
	from facturacion_mexico.config.sat_cancellation_motives import SAT_MOTIVES

	return SAT_MOTIVES.get_config()


@frappe.whitelist()
def test_connection():
	"""Probar conexión con FacturAPI desde interfaz."""
	try:
		client = get_facturapi_client()
		if client.test_connection():
			return {"success": True, "message": "Conexión exitosa con FacturAPI"}
		else:
			return {
				"success": False,
				"message": "No se pudo conectar con FacturAPI. Verifique las credenciales.",
			}
	except Exception as e:
		return {"success": False, "message": f"Error de conexión: {e!s}"}
