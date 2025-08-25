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

		# MILESTONE 1: Usar sistema multisucursal existente para resolver serie
		serie_for_pac = "F"  # Default básico

		# Si el SI tiene Branch configurado, usar su serie
		if sales_invoice.get("branch"):
			branch_doc = frappe.get_cached_doc("Branch", sales_invoice.branch)
			if branch_doc.get("fm_enable_fiscal") and branch_doc.get("fm_serie_pattern"):
				# Extraer solo la parte alfabética del patrón para enviar al PAC
				serie_for_pac = self._extract_series_from_pattern(branch_doc.fm_serie_pattern)

		# Datos de la factura
		invoice_data = {
			"customer": customer_data,
			"items": items,
			"payment_form": payment_form,
			# MILESTONE 1: NO enviar folio_number - deja autoincremento del PAC
			"series": serie_for_pac,  # Serie resuelta por Branch o default
			"use": cfdi_use,
		}

		# [Milestone 3] Inyectar relación 04 si el SI trae 'ffm_substitution_source_uuid'
		src_uuid = (sales_invoice.get("ffm_substitution_source_uuid") or "").strip()
		if src_uuid:
			# FacturAPI (relación CFDI): estructura correcta para sustitución CFDI previo
			invoice_data["related_documents"] = [
				{
					"relationship": "04",  # Sustitución de los CFDI previos
					"documents": [src_uuid],
				}
			]

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
				# MILESTONE 1: Eliminado folio_number - el PAC asigna autoincremental
				"series": "F",  # Será sobrescrito por series_resolver
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

			# MILESTONE 1: Eliminado asignación folio_number específico
			# El PAC manejará autoincremento de folios por serie

			return branch_data

		except Exception as e:
			frappe.log_error(
				f"Error getting branch data for invoice {sales_invoice.name}: {e!s}", "Branch Invoice Data"
			)
			# Retornar datos por defecto en caso de error
			return {
				# MILESTONE 1: Eliminado folio_number - el PAC asigna autoincremental
				"series": "F",  # Será sobrescrito por series_resolver
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

			# [Milestone 3] Cascada post-timbrado: cancelar CFDI previo y SI original si es sustitución
			try:
				# Solo si hay UUID de origen en la SI (indica sustitución 01)
				si = frappe.get_doc("Sales Invoice", sales_invoice.name)
				if (getattr(si, "ffm_substitution_source_uuid", "") or "").strip():
					cascade_result = _cascade_cancel_previous_after_substitute(factura_fiscal.name)
					if cascade_result.get("cascade") == "completed":
						frappe.logger().info(f"Cascada sustitución completada para FFM {factura_fiscal.name}")
					else:
						frappe.logger().warning(f"Cascada sustitución con warnings: {cascade_result}")
			except Exception as e:
				# CONCURRENCY FIX: No re-raise - timbrado ya fue exitoso
				frappe.log_error(frappe.get_traceback(), "Post-Timbrado: cascada sustitución")
				frappe.logger().error(f"Cascada sustitución falló para FFM {factura_fiscal.name}: {e}")
				# NO usar frappe.throw aquí - preservar timbrado exitoso

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

	# [Milestone 3] Guard backend: motivo 01 solo desde flujo sustitución
	# Obtener FFM doc para el guard
	ffm_doc = None
	if sales_invoice:
		ffm_list = frappe.get_all("Factura Fiscal Mexico", filters={"sales_invoice": sales_invoice}, limit=1)
		if ffm_list:
			ffm_doc = frappe.get_doc("Factura Fiscal Mexico", ffm_list[0].name)

	if ffm_doc:
		_guard_motive_01_only_from_substitution(ffm_doc, motivo_code, substitution_uuid)

	api = TimbradoAPI()
	return api.cancelar_factura(sales_invoice, motivo_code, substitution_uuid)


# --- [BEGIN Milestone 2] Validación re-facturación con MISMA SI (02/03/04) ---

# Campos permitidos para cambiar en re-facturación con misma SI
ALLOWED_REFACT_SAME_SI_FIELDS = {
	"fm_customer_tax_regime",  # Régimen fiscal del receptor (c_RegimenFiscal)
	"fm_cfdi_uso",  # Uso CFDI (c_UsoCFDI)
}


def _extract_motive_code(ffm) -> str:
	"""De 'cancellation_reason' tipo '02 - ...' extrae '02' (seguro ante nulos)."""
	val = (ffm.get("cancellation_reason") or "").strip()
	if not val:
		return ""
	# Soporta formatos '02 - desc' o '02\tdesc'
	code = val.split("-")[0].split("\t")[0].strip()
	return code


def _get_last_cancelled_ffm_for_si(si_name: str):
	"""Devuelve la FFM cancelada más reciente para la SI dada."""
	# docstatus=2 (cancelado en ERP) y/o status fiscal cancelado; prioriza fecha de cancelación fiscal/doctype
	ffm_list = frappe.get_all(
		"Factura Fiscal Mexico",
		filters={"sales_invoice": si_name, "docstatus": ["in", [1, 2]]},
		fields=["name", "cancellation_date", "fm_fiscal_status", "cancellation_reason"],
		order_by="COALESCE(cancellation_date, modified) desc",
		limit_page_length=5,
	)
	# Devuelve la primera que realmente esté CANCELADA fiscalmente
	for r in ffm_list:
		if (r.fm_fiscal_status or "").upper() == "CANCELADO":
			return frappe.get_doc("Factura Fiscal Mexico", r.name)
	return None


def _get_ffm_timbrado_snapshot(ffm) -> dict | None:
	"""Intenta recuperar el snapshot de emisión usado para timbrar la FFM previa (desde logs inmutables).
	Retorna un dict con lo necesario para comparar; None si no es posible reconstruir.
	"""
	# Ajusta nombres de Doctype/campos si difieren:
	logs = frappe.get_all(
		"FacturAPI Response Log",
		filters={"factura_fiscal_mexico": ffm.name},
		fields=["name", "operation_type", "request_payload", "status_code"],
		order_by="creation desc",
		limit_page_length=20,
	)
	# Busca el último log de timbrado con payload:
	for lg in logs:
		op = (lg.operation_type or "").lower()
		if "timbr" in op or "emit" in op or "generate" in op:
			# request_payload puede ser JSON serializado (string). Intenta parsear.
			payload = {}
			raw = lg.request_payload or "{}"
			try:
				payload = frappe.parse_json(raw) if isinstance(raw, str) else (raw or {})
			except Exception:
				payload = {}
			# Proyecta a campos comparables (ajusta mapeos a tu payload real)
			return {
				"currency": (payload.get("currency") or "").upper(),
				"exchange_rate": payload.get("exchange_rate"),
				"items": [
					{
						"product_key": it.get("product_key"),
						"description": (it.get("description") or "").strip(),
						"quantity": float(it.get("quantity") or 0),
						"unit_price": float(it.get("unit_price") or 0),
						"discount": float(it.get("discount") or 0),
						# Impuestos (si existen en payload)
						"taxes": it.get("taxes") or it.get("tax_details") or [],
					}
					for it in (payload.get("items") or [])
				],
				"subtotal": float(payload.get("subtotal") or 0),
				"total": float(payload.get("total") or 0),
			}
	return None


def _make_items_signature(items: list[dict]) -> list[tuple]:
	"""Firma simple orden-insensible para comparar conceptos de forma robusta."""
	sig = []
	for it in items or []:
		taxes = it.get("taxes") or []
		# Normaliza impuestos (clave + tasa si disponible)
		tax_sig = []
		for t in taxes:
			rate = t.get("rate") if isinstance(t, dict) else None
			name = t.get("name") or t.get("tax") or t.get("type") if isinstance(t, dict) else str(t)
			tax_sig.append((str(name).strip().upper(), float(rate or 0)))
		tax_sig.sort()
		sig.append(
			(
				(it.get("product_key") or "").upper(),
				(it.get("description") or "").strip().upper(),
				float(it.get("quantity") or 0),
				float(it.get("unit_price") or 0),
				float(it.get("discount") or 0),
				tuple(tax_sig),
			)
		)
	sig.sort()
	return sig


def _project_current_si_snapshot(si) -> dict:
	"""Proyecta del Sales Invoice actual lo necesario para validar que no hubo cambios (salvo régimen/uso)."""
	# Ajusta fieldnames si difieren en tu SI:
	currency = (si.get("currency") or "").upper()
	exchange_rate = si.get("conversion_rate") or si.get("exchange_rate")
	# Items del SI (proyección a campos equivalentes al payload previo)
	items = []
	for it in si.get("items") or []:
		items.append(
			{
				"product_key": it.get("item_tax_template") or it.get("item_code") or it.get("item_name"),
				"description": (it.get("description") or "").strip(),
				"quantity": float(it.get("qty") or 0),
				"unit_price": float(it.get("rate") or 0),
				"discount": float(it.get("discount_amount") or 0),
				# Si tienes estructura de impuestos por línea, mapéala aquí:
				"taxes": [],  # opcional; si no los gestionas por línea, deja vacío
			}
		)
	return {
		"currency": currency,
		"exchange_rate": exchange_rate,
		"items": items,
		"subtotal": float(si.get("net_total") or 0),
		"total": float(si.get("grand_total") or 0),
	}


def _diff_invariants(si_snapshot: dict, ffm_snapshot: dict) -> list[str]:
	"""Compara los invariantes (lo que NO debería cambiar) y devuelve lista de campos distintos."""
	diffs = []
	# Moneda y tipo de cambio
	if (si_snapshot.get("currency") or "").upper() != (ffm_snapshot.get("currency") or "").upper():
		diffs.append("currency")
	if float(si_snapshot.get("exchange_rate") or 0) != float(ffm_snapshot.get("exchange_rate") or 0):
		diffs.append("exchange_rate")
	# Totales
	if abs(float(si_snapshot.get("subtotal") or 0) - float(ffm_snapshot.get("subtotal") or 0)) > 0.01:
		diffs.append("subtotal")
	if abs(float(si_snapshot.get("total") or 0) - float(ffm_snapshot.get("total") or 0)) > 0.01:
		diffs.append("total")
	# Conceptos
	if _make_items_signature(si_snapshot.get("items")) != _make_items_signature(ffm_snapshot.get("items")):
		diffs.append("items")
	return diffs


def validate_refacturacion_misma_si(si_name: str):
	"""Regla de negocio: re-facturar con MISMA SI sólo si:
	- Existe FFM previa CANCELADA por 02/03/04
	- Invariantes (items, totales, moneda, tc) no cambiaron
	- Cambios permitidos: ÚNICAMENTE régimen del receptor y uso CFDI
	"""
	si = frappe.get_doc("Sales Invoice", si_name)

	# 1) Debe existir FFM previa CANCELADA
	ffm_prev = _get_last_cancelled_ffm_for_si(si.name)
	if not ffm_prev:
		frappe.throw(_("No existe una Factura Fiscal cancelada para esta Sales Invoice."))

	# 2) Motivo debe ser 02/03/04 (no 01)
	motive = _extract_motive_code(ffm_prev)
	if motive not in {"02", "03", "04"}:
		frappe.throw(
			_(
				"Sólo se permite re-facturar con la misma Sales Invoice si el motivo de la cancelación previa fue 02/03/04. Motivo actual: {0}"
			).format(motive or "N/A")
		)

	# 3) Debemos poder comparar invariantes; si no hay snapshot confiable, bloquear (fail-safe)
	ffm_snapshot = _get_ffm_timbrado_snapshot(ffm_prev)
	if not ffm_snapshot:
		frappe.throw(
			_(
				"No se encontró snapshot fiscal confiable de la FFM cancelada. Para evitar discrepancias, genera un nuevo Sales Invoice."
			)
		)

	si_snapshot = _project_current_si_snapshot(si)
	invariant_diffs = _diff_invariants(si_snapshot, ffm_snapshot)
	if invariant_diffs:
		# Hay cambios no permitidos (conceptos/totales/moneda/tc). Obliga nuevo SI.
		raise frappe.ValidationError(
			_(
				"No se puede re-facturar con la misma Sales Invoice. Cambios detectados en: {0}. Crea un nuevo Sales Invoice."
			).format(", ".join(invariant_diffs))
		)

	# 4) (Opcional) Verificar explícitamente que sólo hayan cambiado régimen/uso
	#    Si manejas estos campos en SI/FFM, puedes listar diferencias detalladas aquí.
	#    En esta versión minimalista, con invariantes idénticos asumimos OK.

	return True


# --- [END Milestone 2] ---


# --- [BEGIN Milestone 3] Flujo 01 (Sustitución con CFDI sustituto) ---


@frappe.whitelist()
def create_substitution_si(si_name: str):
	"""Crear Sales Invoice de reemplazo para workflow 01 (sustitución).
	Copia el SI original y transporta el UUID del CFDI a sustituir.
	"""
	si = frappe.get_doc("Sales Invoice", si_name)

	# 1) Verificar que exista FFM vigente ligada (timbrada)
	ffm = frappe.db.get_value(
		"Factura Fiscal Mexico",
		{"sales_invoice": si.name, "fm_fiscal_status": "TIMBRADO"},
		["name", "fm_uuid"],
		as_dict=True,
	)
	if not ffm or not ffm.get("fm_uuid"):
		frappe.throw(_("No se encontró una Factura Fiscal vigente para sustituir."))

	# 2) Copiar SI a borrador (sin enviar, sin pagos)
	new_si = frappe.copy_doc(si)
	new_si.name = None  # forzar nuevo nombre
	new_si.docstatus = 0

	# 1) Fechas coherentes
	new_si.posting_date = frappe.utils.today()

	# 2) Limpiar vencimientos/schedules del SI original
	new_si.payment_schedule = []  # importante si usas Payment Schedule
	new_si.due_date = None  # recalcularemos o, mínimo, la igualamos a posting_date

	# 3) Recalcular due_date de forma simple (fail-safe)
	if new_si.payment_terms_template:
		# iguala al menos a posting_date para evitar validación:
		new_si.due_date = new_si.posting_date
	else:
		# sin plantilla, asegura mínimo válido:
		new_si.due_date = new_si.posting_date

	# 4) Limpiezas habituales de copia
	new_si.amended_from = None  # no usamos 'amend', flujo es independiente
	new_si.set_posting_time = 1  # opcional si permites fijar hora

	# Limpiar campos fiscales del SI nuevo
	new_si.fm_factura_fiscal_mx = None
	new_si.fm_fiscal_status = None
	new_si.fm_last_status_update = None

	# 3) Guardar el UUID a sustituir (campo custom ffm_substitution_source_uuid)
	new_si.set("ffm_substitution_source_uuid", ffm["fm_uuid"])

	new_si.insert(ignore_permissions=True)

	return {"new_si": new_si.name, "src_uuid": ffm["fm_uuid"]}


def _cascade_cancel_previous_after_substitute(new_ffm_name: str):
	"""Post-éxito: cancelar CFDI previo con motivo 01 y cancelar SI/FFM originales."""
	from frappe.utils import cstr

	try:
		new_ffm = frappe.get_doc("Factura Fiscal Mexico", new_ffm_name)
		new_uuid = (new_ffm.get("fm_uuid") or "").strip()
		if not new_uuid:
			return {"skipped": "no_new_uuid"}

		# Ubicar el SI de reemplazo y su uuid origen
		si = frappe.get_doc("Sales Invoice", new_ffm.sales_invoice)
		src_uuid = (si.get("ffm_substitution_source_uuid") or "").strip()
		if not src_uuid:
			return {"skipped": "no_source_uuid"}

		# Encontrar FFM original por UUID (previo a sustituir)
		orig_ffm_name = frappe.db.get_value("Factura Fiscal Mexico", {"fm_uuid": src_uuid}, "name")
		if not orig_ffm_name:
			frappe.logger().warning(f"No se encontró FFM original con UUID {src_uuid}")
			return {"skipped": "no_original_ffm"}

		# CRITICAL FIX: Resolver SI original a partir de la FFM original
		orig_si_name = frappe.db.get_value("Factura Fiscal Mexico", {"name": orig_ffm_name}, "sales_invoice")
		if not orig_si_name:
			frappe.log_error(f"Cascade01: no Sales Invoice for FFM {orig_ffm_name}", "Cascade01")
			return {"error": "no_original_si"}

		# IDEMPOTENCIA: Verificar si ambos ya están cancelados
		orig_ffm = frappe.get_doc("Factura Fiscal Mexico", orig_ffm_name)
		orig_si = frappe.get_doc("Sales Invoice", orig_si_name)

		if orig_si.docstatus == 2 and orig_ffm.docstatus == 2:
			return {"skipped": "already_cancelled"}

		orig_status = frappe.db.get_value("Factura Fiscal Mexico", orig_ffm_name, "fm_fiscal_status")
		if (orig_status or "").upper() in {"CANCELADO", "CANCELADA"}:
			return {"skipped": "already_cancelled"}

		# CONCURRENCY FIX: Lock per-document para evitar race conditions
		lock_key = f"ffm:cascade:{orig_ffm_name}"
		with frappe.cache().lock(lock_key, timeout=30):
			frappe.logger().info(
				f"Iniciando cascada REORDENADA con lock: FFM {orig_ffm_name} via SI {orig_si_name}"
			)

			cancel_result = None

			# 1) Cancelar fiscalmente el CFDI previo con motivo 01 (PAC)
			try:
				api = TimbradoAPI()
				# CRITICAL FIX: Usar orig_si_name en lugar de orig_ffm_name
				cancel_result = api.cancelar_factura(orig_si_name, "01", new_uuid)
				frappe.logger().info(f"Cancelación fiscal PAC exitosa: {cancel_result}")
			except Exception as e:
				frappe.logger().error(f"Error cancelando CFDI previo en PAC: {e}")
				# No fallar toda la operación por error en cancelación PAC
				cancel_result = None

			# 2) REORDER: Marcar FFM original con estado fiscal CANCELADO (sin cancelar DocType aún)
			try:
				orig_ffm.reload()
				orig_ffm.set("fm_fiscal_status", "CANCELADO")
				orig_ffm.save()
				frappe.logger().info(f"FFM {orig_ffm_name} marcada como CANCELADO fiscalmente")
			except Exception as e:
				frappe.logger().error(f"Error marcando FFM como CANCELADO: {e}")

			# 2.5) HARDENING PREVENTIVO - ANTES de cancelar (CONFIRMADO POR EXPERTO)
			try:
				orig_si.reload()
				orig_ffm.reload()

				# Limpiar SI → FFM link ANTES de cancel()
				if getattr(orig_si, "fm_factura_fiscal_mx", None):
					ffm_ref = orig_si.fm_factura_fiscal_mx
					orig_si.db_set("fm_factura_fiscal_mx", "")
					frappe.db.commit()  # Forzar commit inmediato
					orig_si.add_comment("Info", f"Link FFM limpiado preventivo: {ffm_ref}")
					frappe.logger().info(f"Hardening preventivo 1: SI {orig_si_name} → FFM link limpiado")

				# Limpiar FFM → SI link ANTES de cancel()
				if getattr(orig_ffm, "sales_invoice", None):
					si_ref = orig_ffm.sales_invoice
					orig_ffm.db_set("sales_invoice", "")
					frappe.db.commit()  # Forzar commit inmediato
					orig_ffm.add_comment("Info", f"Link SI limpiado preventivo: {si_ref}")
					frappe.logger().info(f"Hardening preventivo 2: FFM {orig_ffm_name} → SI link limpiado")

			except Exception as e:
				frappe.logger().error(f"Error en hardening preventivo: {e}")

			# 3) REORDER: Cancelar SI original PRIMERO (sin links que validen)
			try:
				orig_si.reload()  # CONCURRENCY FIX: reload antes de cancelar
				if cstr(orig_si.docstatus) == "1":
					orig_si.cancel()
					frappe.logger().info(f"SI {orig_si_name} cancelado (docstatus=2)")
			except Exception as e:
				frappe.logger().error(f"Error cancelando SI original: {e}")

			# 4) REORDER: Cancelar FFM original DESPUÉS (con reload)
			try:
				orig_ffm.reload()  # CONCURRENCY FIX: reload antes de cancelar
				if cstr(orig_ffm.docstatus) == "1":
					orig_ffm.cancel()
					frappe.logger().info(f"FFM {orig_ffm_name} cancelada (docstatus=2)")
			except Exception as e:
				frappe.logger().error(f"Error cancelando FFM original: {e}")

			# 5) Garantizar acuse de cancelación en FFM original (tras cancelar FFM)
			if cancel_result and cancel_result.get("status") in ["accepted", "accepted_with_details"]:
				try:
					_download_and_attach_cancellation_ack(
						ffm_name=orig_ffm_name,
						uuid=getattr(orig_ffm, "fm_uuid", src_uuid),
						cancel_result=cancel_result,
					)
				except Exception as e:
					frappe.log_error(f"Acuse cancelación pendiente o error descarga: {e}", "FFM Cancel Ack")
					# Marcar como pendiente para reintento manual
					try:
						orig_ffm.db_set("ack_pending", 1)
					except Exception:
						pass

		return {"cascade": "completed"}

	except Exception as e:
		frappe.logger().error(f"Error en cascada de cancelación: {e}")
		return {"cascade": "error", "message": str(e)}


def _download_and_attach_cancellation_ack(ffm_name: str, uuid: str, cancel_result: dict):
	"""Descargar y adjuntar acuse de cancelación del PAC a la FFM original."""
	import requests

	# Buscar URL del acuse en respuesta PAC (varios alias posibles)
	ack_url = None
	ack_aliases = [
		"cancellation_ack_url",
		"cancellation_pdf_url",
		"acuse_cancelacion_url",
		"ack_url",
		"cancellation_ack",
		"cancellation_receipt_url",
	]

	for alias in ack_aliases:
		if cancel_result.get(alias):
			ack_url = cancel_result[alias]
			break

	if not ack_url:
		# Si no viene inline, intentar consultar comprobante para obtener acuse
		frappe.logger().info(f"No acuse inline para {uuid}, marcando ack_pending")
		ffm_doc = frappe.get_doc("Factura Fiscal Mexico", ffm_name)
		ffm_doc.db_set("ack_pending", 1)
		return

	try:
		# Verificar si ya existe acuse adjunto (evitar duplicados)
		existing_files = frappe.get_all(
			"File",
			filters={
				"attached_to_doctype": "Factura Fiscal Mexico",
				"attached_to_name": ffm_name,
				"file_name": ["like", f"%AcuseCancelacion_{uuid[:8]}%"],
			},
		)

		if existing_files:
			frappe.logger().info(f"Acuse ya existe para FFM {ffm_name}, saltando descarga")
			return

		# Descargar acuse
		response = requests.get(ack_url, timeout=30)
		response.raise_for_status()

		# Determinar tipo de archivo por content-type o extensión
		content_type = response.headers.get("content-type", "").lower()
		if "pdf" in content_type:
			file_ext = "pdf"
		elif "xml" in content_type:
			file_ext = "xml"
		else:
			# Fallback: asumir PDF
			file_ext = "pdf"

		# Crear archivo adjunto
		file_name = f"AcuseCancelacion_{uuid[:8]}_SAT.{file_ext}"

		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": file_name,
				"attached_to_doctype": "Factura Fiscal Mexico",
				"attached_to_name": ffm_name,
				"content": response.content,
				"decode": False,
				"is_private": 1,
			}
		)

		file_doc.insert()
		frappe.logger().info(f"Acuse adjuntado exitosamente: {file_name} a FFM {ffm_name}")

	except Exception as e:
		frappe.logger().error(f"Error descargando acuse para FFM {ffm_name}: {e}")
		# Marcar como pendiente para reintento manual
		ffm_doc = frappe.get_doc("Factura Fiscal Mexico", ffm_name)
		ffm_doc.db_set("ack_pending", 1)


# --- [END Milestone 3] ---


# --- [BEGIN Milestone 3] Guard backend motivo 01 ---


# [M3-BE] Obtener código de sustitución desde ENUM SAT (sin hardcode)
def _get_substitution_code() -> str:
	"""
	Intenta obtener el código de 'Sustitución' desde SATCancellationMotives.
	Fallback: '01' (no rompe si cambia estructura).
	"""
	try:
		from facturacion_mexico.config.sat_cancellation_motives import SATCancellationMotives
	except Exception:
		return "01"

	# Intentos comunes sin asumir API exacta del enum:
	# 1) Atributo directo tipo constante (e.g. SATCancellationMotives.SUSTITUCION == '01')
	for attr in ("SUSTITUCION", "SUBSTITUCION", "ERRORES_CON_RELACION"):
		val = getattr(SATCancellationMotives, attr, None)
		if isinstance(val, str) and val.strip():
			return val.strip()
		# Si es un objeto con 'code'
		if hasattr(val, "code"):
			try:
				code = val.code
				if isinstance(code, str) and code.strip():
					return code.strip()
			except Exception:
				pass

	# 2) Método utilitario (si existiera) para obtener por clave
	for candidate in ("get_code", "code_for", "get"):
		if hasattr(SATCancellationMotives, candidate):
			try:
				meth = getattr(SATCancellationMotives, candidate)
				code = meth("SUSTITUCION")
				if isinstance(code, str) and code.strip():
					return code.strip()
			except Exception:
				pass

	# 3) Fallback seguro
	return "01"


# [M3-BE] Guard de negocio para 01
def _guard_motive_01_only_from_substitution(ffm_doc, motive: str, substitution_uuid: str | None):
	from frappe import _

	code_01 = _get_substitution_code()
	motive = (motive or "").strip()
	if motive != code_01:
		return

	has_linked_si = bool(getattr(ffm_doc, "sales_invoice", None))
	status = (getattr(ffm_doc, "fm_fiscal_status", "") or "").upper()

	# Regla: si FFM pertenece a un SI y está TIMBRADO, 01 solo desde flujo de sustitución (debe traer substitution_uuid)
	if has_linked_si and status == "TIMBRADO" and not (substitution_uuid or "").strip():
		frappe.throw(
			_(
				"La cancelación con motivo {0} (Sustitución) solo se permite desde el Sales Invoice (flujo de sustitución), proporcionando 'substitution_uuid'."
			).format(code_01)
		)


# --- [END Milestone 3] Guard backend motivo 01 ---


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
