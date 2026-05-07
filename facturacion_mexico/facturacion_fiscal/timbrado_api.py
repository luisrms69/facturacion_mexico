import json
import re
import traceback
import unicodedata
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, today

from facturacion_mexico.config.sat_objeto_impuesto import SATObjetoImpuesto
from facturacion_mexico.config.sat_tax_rates import FacturAPITaxRates
from facturacion_mexico.config.sat_tipo_factor import SATTipoFactor

# Import para conversión UOM (IEPS Cuota en litros)
try:
	from erpnext.stock.get_item_details import get_conversion_factor
except ImportError:
	get_conversion_factor = None


def _log_text(label, s: str):
	if s is None:
		s = ""
	frappe.logger("facturapi-wire").info(
		{
			"label": label,
			"text": s,
			"repr": repr(s),
			"codepoints": [hex(ord(ch)) for ch in s],
			"is_nfc": s == unicodedata.normalize("NFC", s),
		}
	)


def _log_payload_checkpoint(tag, payload: dict):
	name = payload.get("customer", {}).get("legal_name") or payload.get("legal_name")
	_log_text(f"{tag}.customer.legal_name", name)


from facturacion_mexico.config.fiscal_states_config import FiscalStates, OperationTypes

from .api import write_pac_response  # PAC Response Writer - Arquitectura resiliente activada
from .api_client import get_facturapi_client
from .doctype.facturapi_response_log.facturapi_response_log import FacturAPIResponseLog


def _nfc_collapse_upper(s: str) -> str:
	"""PASO 3: Normaliza a NFC, colapsa espacios, preserva Ñ y comillas."""
	if not s:
		return ""
	s = unicodedata.normalize("NFC", s)
	s = re.sub(r"\s+", " ", s.strip())
	return s.upper()  # Si requieres mayúsculas


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
		# TODO: Integrar branch_data cuando se implemente Sprint 6 Phase 2
		# branch_data = self._get_branch_data_for_invoice(sales_invoice)

		# Datos del cliente
		customer_data = {
			"legal_name": _nfc_collapse_upper(
				customer.customer_name
			),  # ← SIN mapas de acentos, PRESERVA Ñ y comillas
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

		# Items de la factura - E4-RO: Puente SI → Payload PAC
		items = []
		for item in sales_invoice.items:
			item_doc = frappe.get_doc("Item", item.item_code)

			# E4.1: Leer taxes desde SI (NO calcular)
			item_taxes_data = self._read_taxes_from_sales_invoice_item(item, sales_invoice)

			# E4.3: Resolver ObjetoImp desde catálogo SAT
			objeto_imp = self._resolve_objeto_impuesto(item_doc)

			# E4.4: Mapear taxes a estructura FacturAPI
			taxes_payload = []
			for tax_data in item_taxes_data:
				sat_mapping = self._map_tax_account_to_sat(tax_data["account_head"])

				# Construir tax payload base
				tax_item = {
					"type": sat_mapping["nombre_sat"],  # "IVA", "ISR", "IEPS"
					"factor": sat_mapping["tipo_factor"],  # "Tasa" o "Cuota"
					"withholding": sat_mapping["es_retencion"],
				}

				# CRÍTICO: FacturAPI requiere campos específicos según tipo_factor
				if sat_mapping["tipo_factor"] == "Tasa":
					# Tasa: enviar porcentaje como decimal (16% → 0.16)
					rate_decimal = abs(tax_data["rate"]) / 100
					tax_item["rate"] = rate_decimal

					# FIX E4.1: Para IVA, enviar base UNITARIA (FacturAPI multiplica x qty)
					# Esto controla integración IEPS: bebidas integran, combustibles NO
					if sat_mapping["nombre_sat"] == "IVA":
						# Determinar si IEPS integra base IVA (buscar en taxes del item)
						integra_base = True  # Default: sí integra (bebidas/tabaco/alcohol)

						for tax_check in item_taxes_data:
							sat_map_check = self._map_tax_account_to_sat(tax_check["account_head"])
							if (
								sat_map_check["tipo_factor"] == "Cuota"
								and sat_map_check["nombre_sat"] == "IEPS"
								and not sat_map_check.get("integra_base_iva", True)
							):
								integra_base = False
								break

						# Calcular base IVA UNITARIA según integración
						if integra_base:
							# Bebidas/Tabaco/Alcohol: base unitaria = precio + IEPS por unidad
							ieps_cuota_unitario = 0.0
							ieps_tasa_unitario = 0.0

							for tax_check in item_taxes_data:
								sat_map_check = self._map_tax_account_to_sat(tax_check["account_head"])
								if sat_map_check["nombre_sat"] == "IEPS":
									if sat_map_check["tipo_factor"] == "Cuota":
										# IEPS Cuota: ya es por unidad ($/litro)
										if item.qty > 0:
											ieps_cuota_unitario = flt(tax_check["amount"]) / flt(item.qty)
									elif sat_map_check["tipo_factor"] == "Tasa":
										# IEPS Tasa: porcentaje sobre precio
										ieps_tasa_unitario = flt(item.rate) * (
											abs(flt(tax_check["rate"])) / 100
										)

							base_iva_unitaria = flt(item.rate) + ieps_cuota_unitario + ieps_tasa_unitario
						else:
							# Combustibles: base unitaria = solo precio (sin IEPS)
							base_iva_unitaria = flt(item.rate)

						tax_item["base"] = flt(base_iva_unitaria, 6)

				elif sat_mapping["tipo_factor"] == "Cuota":
					# IEPS CUOTA: TODOS se serializan al payload (combustibles Y bebidas)
					# E4-RO: Base=qty física, TasaOCuota=cuota/unidad
					# NOTA: integra_base_iva solo afecta cálculo base IVA (hook separado),
					#       NO la inclusión del IEPS en el payload PAC

					# FIX E4.1: Obtener cuota ORIGINAL de tabla SAT (no calcularla desde amount)
					# RAZÓN: amount ya está multiplicado por qty, dividirlo causa error de precisión
					# Ejemplo: Refresco 30 piezas x 0.6L x $1.27/L = $22.86
					#          Si dividimos: $22.86 / 30 piezas = $0.762/pieza (INCORRECTO)
					#          Debe ser: $1.27/litro (cuota original de tabla SAT)
					cuota_por_uom_base = self._get_cuota_from_tabla_sat(item_doc, tax_data["account_head"])

					if not cuota_por_uom_base:
						frappe.throw(
							_(
								"No se encontró cuota IEPS en tabla 'IEPS Cuota SAT' para item {0}.\n\n"
								"Verifique que exista un registro vigente para:\n"
								"- Clave SAT: {1}\n"
								"- Cuenta IEPS: {2}\n"
								"- Fecha: {3}"
							).format(
								item_doc.item_code,
								item_doc.get("fm_producto_servicio_sat") or "N/A",
								tax_data["account_head"],
								today(),
							),
							title=_("Cuota IEPS No Encontrada"),
						)

					# Obtener UOM base desde tabla IEPS Cuota SAT (dinámico: LTR, H87, etc.)
					uom_base = self._get_uom_base_from_tabla_sat(item_doc, tax_data["account_head"])
					if not uom_base:
						frappe.throw(
							_(
								"No se encontró UOM base en tabla IEPS Cuota SAT para item {0}.\n\n"
								"Verifique que exista un registro vigente en 'IEPS Cuota SAT' para:\n"
								"- Clave SAT: {1}\n"
								"- Cuenta IEPS: {2}\n"
								"- Fecha: {3}"
							).format(
								item_doc.item_code,
								item_doc.get("fm_producto_servicio_sat") or "N/A",
								tax_data["account_head"],
								today(),
							),
							title=_("UOM Base No Encontrada"),
						)

					# Calcular factor conversión: item.uom → uom_base
					# Ejemplo: Combustible LTR→LTR factor=1.0, Refresco 600ml→LTR factor=0.6, Tabaco H87→H87 factor=1.0
					factor_conversion = self._get_uom_conversion_factor(item_doc, item.uom, uom_base)

					tax_item["rate"] = flt(
						cuota_por_uom_base, 6
					)  # TasaOCuota (cuota/unidad base desde tabla SAT)
					tax_item["base"] = flt(
						factor_conversion, 6
					)  # Factor conversión (FacturAPI x qty = unidades base)

				taxes_payload.append(tax_item)

			# E4.6: Validación estricta ObjetoImp vs taxes (CAMBIO 2)
			self._validate_objeto_imp_consistency(objeto_imp, taxes_payload, item)

			# Construir concepto
			item_payload = {
				"quantity": abs(item.qty),  # SIs de devolución tienen qty negativa por diseño ERPNext
				"product": {
					"description": item.description or item.item_name,
					"product_key": item_doc.fm_producto_servicio_sat or "01010101",
					"price": flt(item.rate),
					"tax_included": False,
					"unit_key": _extract_sat_code_from_uom(item.uom),
					"unit_name": item.uom or "Pieza",
					"taxability": objeto_imp,  # E4.3: ObjetoImp desde catálogo SAT
				},
			}

			# E4-RO: Solo agregar taxes[] si hay impuestos
			if taxes_payload:
				item_payload["product"]["taxes"] = taxes_payload

			items.append(item_payload)

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
			"payment_method": factura_fiscal.get("fm_payment_method_sat", "PUE"),  # PUE/PPD explícito
			# MILESTONE 1: NO enviar folio_number - deja autoincremento del PAC
			"series": serie_for_pac,  # Serie resuelta por Branch o default
			"use": cfdi_use,
		}

		# TIPO DE COMPROBANTE: Obtener desde Factura Fiscal Mexico
		tipo_comprobante = factura_fiscal.get("fm_tipo_comprobante", "I").strip()
		if tipo_comprobante:
			# Extraer solo el código (formato "I - Ingreso" -> "I")
			tipo_code = (
				tipo_comprobante.split(" - ")[0].strip() if " - " in tipo_comprobante else tipo_comprobante
			)
			invoice_data["type"] = tipo_code

		# DOCUMENTOS RELACIONADOS: Para tipo Egreso (E), incluir relación SAT y UUID relacionado
		if invoice_data.get("type") == "E":
			tipo_relacion = factura_fiscal.get("fm_tipo_relacion_sat", "").strip()
			uuid_relacionado = factura_fiscal.get("fm_uuid_relacionado", "").strip()

			if tipo_relacion and uuid_relacionado:
				# Extraer código de relación (formato "01 - Descripción" -> "01")
				relacion_code = (
					tipo_relacion.split(" - ")[0].strip() if " - " in tipo_relacion else tipo_relacion
				)

				invoice_data["related_documents"] = [
					{
						"relationship": relacion_code,
						"documents": [uuid_relacionado],
					}
				]

		# [Milestone 3] Inyectar relación 04 si el SI trae 'ffm_substitution_source_uuid'
		src_uuid = (sales_invoice.get("ffm_substitution_source_uuid") or "").strip()
		if src_uuid:
			# FacturAPI (relación CFDI): estructura correcta para sustitución CFDI previo
			# NOTA: Si ya hay related_documents de tipo E, agregar a la lista
			if "related_documents" not in invoice_data:
				invoice_data["related_documents"] = []

			invoice_data["related_documents"].append(
				{
					"relationship": "04",  # Sustitución de los CFDI previos
					"documents": [src_uuid],
				}
			)

		# Sprint 6 Phase 2: Datos específicos de sucursal
		# NOTA: place_of_issue y branch_office removidos
		# RAZÓN: Deben coincidir exactamente con CSD registrado en PAC
		# FacturAPI auto-calcula estos campos desde configuración del emisor en PAC
		# Incluirlos manualmente puede causar rechazo por inconsistencia con CSD

		# E4.7: Validación moneda (CAMBIO 3 APROBADO)
		self._validate_currency_consistency(invoice_data, sales_invoice)

		# E4.8: Validación completitud payload
		self._validate_payload_completeness_ro(invoice_data, sales_invoice)

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
				"status": FiscalStates.TIMBRADO,
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
			es_ppd = 1 if (factura_fiscal.get("fm_payment_method_sat") or "").upper() == "PPD" else 0
			frappe.set_value(
				"Sales Invoice",
				sales_invoice.name,
				{
					"fm_fiscal_status": FiscalStates.TIMBRADO,
					"fm_es_ppd": es_ppd,
				},
			)

			# Descargar archivos si está configurado
			if self.settings.download_files_default:
				self._download_fiscal_files(factura_fiscal, response.get("id"))

			# Enviar email si está configurado (ESPEJO EXACTO de descarga archivos)
			email_flag = getattr(factura_fiscal, "fm_enviar_email_timbrado", 0)
			if email_flag:
				self._send_fiscal_email(factura_fiscal, response.get("id"))
			else:
				pass

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

	def _send_fiscal_email(self, factura_fiscal, facturapi_id):
		"""Enviar email CFDI - ESPEJO de _download_fiscal_files."""
		try:
			# Resolver destinatario usando la misma función que el botón manual
			from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
				_resolve_recipient_email,
			)

			to_email = _resolve_recipient_email(factura_fiscal)
			if not to_email:
				frappe.logger().warning(f"[FFM email] No recipient for {factura_fiscal.name}")
				# Notificar al usuario que no se envió el email
				frappe.msgprint(
					f"No se pudo enviar el email automático para {factura_fiscal.name}: "
					f"Configure el email en el campo 'Email Facturación' del documento.",
					title="Email no enviado",
					indicator="orange",
				)
				return

			# Llamada API FacturAPI
			self.client.send_invoice_email(facturapi_id, to_email)
			frappe.logger().info(f"[FFM email] Enviado a {to_email} para {factura_fiscal.name}")

		except Exception as e:
			frappe.logger().error(f"[FFM email] Error enviando: {e}")
			import traceback

			frappe.logger().error(f"[FFM email] Traceback: {traceback.format_exc()}")

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

	def _download_cancellation_receipt_files(self, factura_fiscal, facturapi_id):
		"""Descargar PDF y XML del acuse de cancelación."""
		try:
			# Descargar PDF del acuse
			pdf_content = self.client.download_cancellation_receipt_pdf(facturapi_id)
			self._save_file_attachment(
				factura_fiscal.name,
				f"{factura_fiscal.name}_acuse_cancelacion.pdf",
				pdf_content,
				"application/pdf",
			)

			# Descargar XML del acuse
			xml_content = self.client.download_cancellation_receipt_xml(facturapi_id)
			self._save_file_attachment(
				factura_fiscal.name,
				f"{factura_fiscal.name}_acuse_cancelacion.xml",
				xml_content.encode("utf-8"),
				"application/xml",
			)

		except Exception as e:
			frappe.logger().error(f"Error descargando archivos de acuse de cancelación: {e!s}")

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

				# CORRECCIÓN BUG: Mapear estado fiscal según respuesta real del PAC
				raw_response = pac_response.get("raw_response", {})
				response_status = raw_response.get("status", "")
				cancellation_status = raw_response.get("cancellation_status", "")

				# Log respuesta para auditoría
				frappe.logger().info(
					f"Respuesta PAC para FFM {factura_fiscal.name}: status='{response_status}', cancellation_status='{cancellation_status}'"
				)

				# Mapeo correcto según documentación FacturAPI
				if response_status == "canceled" or cancellation_status == "accepted":
					fiscal_status = FiscalStates.CANCELADO
					cancellation_date = now_datetime()
				elif cancellation_status == "pending":
					fiscal_status = FiscalStates.PENDIENTE_CANCELACION
					cancellation_date = None
				elif cancellation_status == "rejected":
					# Mantener como timbrado - no cambiar estado fiscal
					fiscal_status = FiscalStates.TIMBRADO
					cancellation_date = None
				else:
					# Fallback conservador para respuestas inesperadas
					fiscal_status = FiscalStates.PENDIENTE_CANCELACION
					cancellation_date = None
					frappe.logger().warning(
						f"Respuesta PAC inesperada para FFM {factura_fiscal.name}: status='{response_status}', cancellation_status='{cancellation_status}'. Usando fallback PENDIENTE_CANCELACION"
					)

				# Actualizar FFM con estado correcto
				update_data = {
					"status": fiscal_status,
					"cancellation_reason": motivo_completo,
				}
				if cancellation_date:
					update_data["cancellation_date"] = cancellation_date

				# Limpiar motivo de cancelación si PAC rechazó la solicitud
				if fiscal_status != FiscalStates.CANCELADO:
					update_data["fm_motivo_cancelacion"] = None

				frappe.set_value("Factura Fiscal Mexico", factura_fiscal.name, update_data)

				# Actualizar Sales Invoice con mismo estado fiscal
				frappe.set_value("Sales Invoice", sales_invoice_name, {"fm_fiscal_status": fiscal_status})

				frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure cancellation transaction is committed

				# Notificar al formulario SI si está abierto en otro tab
				frappe.publish_realtime(
					event="fiscal_status_changed",
					message={
						"sales_invoice": sales_invoice_name,
						"fm_fiscal_status": fiscal_status,
						"ffm": factura_fiscal.name,
					},
					doctype="Sales Invoice",
					docname=sales_invoice_name,
				)

				# Descargar acuse de cancelación automáticamente
				try:
					self._download_cancellation_receipt_files(factura_fiscal, factura_fiscal.facturapi_id)
					frappe.logger().info(f"Acuse cancelación descargado para FFM {factura_fiscal.name}")
				except Exception as e:
					frappe.logger().error(f"Error descargando acuse cancelación: {e}")
					# No fallar el flujo principal por error de descarga

				# Obtener estados actualizados para response coherente
				si_doc = frappe.get_doc("Sales Invoice", sales_invoice_name)

				return {
					"ok": True,  # Para consistencia con propuesta UX
					"success": True,  # Backward compatibility
					"ffm": factura_fiscal.name,
					"sales_invoice": sales_invoice_name,
					"status_ffm": fiscal_status,  # Estado correcto basado en respuesta PAC
					"status_si": si_doc.fm_fiscal_status,
					"uuid": factura_fiscal.fm_uuid,
					"cancellation_date": cancellation_date.strftime("%Y-%m-%d %H:%M:%S")
					if cancellation_date
					else None,
					"message": "Solicitud de cancelación procesada exitosamente",
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
		import json

		# PRIORIDAD: Intentar extraer mensaje directo del JSON del PAC
		if hasattr(error, "response"):
			try:
				pac_json = error.response.json()
				if isinstance(pac_json, dict) and "message" in pac_json:
					# Retornar mensaje directo del PAC
					return {
						"user_message": f"ERROR PAC: {pac_json['message']}",
						"corrective_action": pac_json.get("path", "Revisar datos de la factura"),
						"status_code": str(getattr(error.response, "status_code", 400)),
					}
			except Exception:
				pass  # Si falla parsing, continuar con lógica legacy

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
				# Intentar repoblar desde customer.fm_tax_regime
				customer = frappe.get_doc("Customer", factura_fiscal.customer)
				if customer and customer.fm_tax_regime:
					# Extraer código del fm_tax_regime (formato: "601 - Descripción" -> "601")
					tax_code = customer.fm_tax_regime.split(" - ")[0].strip()

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

	# ========================================================================
	# E4-RO: FUNCIONES PUENTE SALES INVOICE → PAYLOAD PAC (READ-ONLY)
	# ========================================================================

	def _read_taxes_from_sales_invoice_item(self, item, sales_invoice):
		"""
		E4.1: Leer impuestos de un item desde Sales Invoice.

		E4-RO: Solo lectura, sin cálculos.

		FUENTES (prioridad):
		1. item.item_tax_rate (cuando ITT explícito)
		2. FALLBACK: sales_invoice.taxes con item_wise_tax_detail (template global)

		Precisiones read-only:
		- P1: Si item_wise_tax_detail trae amount pero rate=0, usar tax.rate de la fila SI
		- P2: Duplicados por account_head se serializan ambos (sin consolidar)

		Args:
			item: Row de Sales Invoice.items
			sales_invoice: Documento Sales Invoice completo

		Returns:
			List[dict]: [
				{
					"account_head": str,
					"rate": float,
					"amount": float
				}
			]
		"""
		import json

		# E4-RO: Leer TODOS los taxes directamente desde sales_invoice.taxes
		# NO usar item.item_tax_rate como filtro - solo leer lo que SI ya calculó
		taxes_dict = {}  # Usar dict para deduplicar por account_head

		for tax in sales_invoice.taxes:
			if not tax.item_wise_tax_detail:
				# Fallback para On Net Total sin item_wise_tax_detail (p.ej. SI creada via API
				# o cuando ERPNext v16 no persistió el desglose por item).
				# Solo aplica a tasas sobre base neta: amount = net_amount x rate / 100.
				if getattr(tax, "charge_type", None) == "On Net Total" and flt(tax.rate):
					amount = flt(item.net_amount) * flt(tax.rate) / 100
					if amount and tax.account_head not in taxes_dict:
						taxes_dict[tax.account_head] = {
							"account_head": tax.account_head,
							"rate": flt(tax.rate),
							"amount": amount,
						}
						frappe.logger().info(
							f"E4-RO - Item {item.item_code}: Tax {tax.account_head} "
							f"calculado por fallback On Net Total (rate={tax.rate}, amount={amount})"
						)
				continue

			# Parse item_wise_tax_detail
			try:
				item_wise = json.loads(tax.item_wise_tax_detail)
			except (json.JSONDecodeError, TypeError):
				continue

			# Buscar este item con fallback de llaves:
			# ERPNext v16 usa item.name (row UUID); versiones anteriores usan item.item_code.
			rate_from_json = 0.0
			amount = 0.0
			key_used = None

			for key in [item.name, item.item_code, item.item_name]:
				if key in item_wise:
					rate_from_json = float(item_wise[key][0])  # Position 0 = rate
					amount = float(item_wise[key][1])  # Position 1 = amount
					key_used = key
					break

			# Solo agregar si hay rate o amount != 0
			if rate_from_json != 0 or amount != 0:
				# E4-RO: Usar rate exacto de item_wise_tax_detail (NO fallback a tax.rate)
				# Para IEPS Cuota, hook guardó [0, amount], así que rate=0.0
				final_rate = rate_from_json

				# DEDUPLICAR: Solo guardar si NO existe ya esta cuenta
				if tax.account_head not in taxes_dict:
					taxes_dict[tax.account_head] = {
						"account_head": tax.account_head,
						"rate": final_rate,
						"amount": amount,
					}

					frappe.logger().info(
						f"E4-RO - Item {item.item_code}: Tax {tax.account_head} "
						f"leído desde SI item_wise_tax_detail (llave={key_used}, rate={final_rate}, amount={amount})"
					)

		# Convertir dict a list
		taxes_data = list(taxes_dict.values())

		if taxes_data:
			frappe.logger().info(
				f"E4-RO - Item {item.item_code}: {len(taxes_data)} impuestos leídos (READ-ONLY desde SI)"
			)

		return taxes_data

	def _get_tax_amount_for_item_robust(self, sales_invoice, account_head, item_code, item_name, row_name):
		"""
		E4.2: Extraer amount con fallback de llaves.

		CAMBIO 3 APROBADO: Lectura robusta según versión ERPNext.

		Prioridad llaves en item_wise_tax_detail:
		1. row.name (row interno SI)
		2. item_code
		3. item_name

		Args:
			sales_invoice: Documento SI
			account_head: Cuenta impuesto
			item_code: Código item
			item_name: Nombre item
			row_name: row.name interno

		Returns:
			float: Tax amount para el item
		"""
		import json

		# Buscar tax row en SI
		tax_row = None
		for tax in sales_invoice.taxes:
			if tax.account_head == account_head:
				tax_row = tax
				break

		if not tax_row or not tax_row.item_wise_tax_detail:
			return 0.0

		# Parse JSON
		item_wise = json.loads(tax_row.item_wise_tax_detail)

		# CAMBIO 3: Fallback de llaves (row.name → item_code → item_name)
		for key in [row_name, item_code, item_name]:
			if key in item_wise:
				# item_wise[key] = [rate, amount]
				return float(item_wise[key][1])  # Posición 1 = amount

		# No encontrado
		frappe.logger().warning(f"Tax amount no encontrado para item {item_code} en {account_head}")
		return 0.0

	def _resolve_objeto_impuesto(self, item_doc):
		"""
		E4.3: Resolver ObjetoImp desde catálogo SAT Producto Servicio.

		E4-RO: Solo lookup, sin inferencias.

		Pipeline:
		1. Leer Item.fm_producto_servicio_sat
		2. Lookup SAT Producto Servicio.incluye_objeto_impuesto
		3. Retornar "01", "02", "03", o "04"

		Returns:
			str: ObjetoImp
		"""
		clave_prod_serv = item_doc.get("fm_producto_servicio_sat")

		if not clave_prod_serv:
			frappe.throw(
				f"Item {item_doc.name} no tiene ClaveProdServ (fm_producto_servicio_sat) configurada.\n"
				f"Configure el campo SAT en Item.",
				title="ClaveProdServ Faltante",
			)

		# Lookup en catálogo interno
		sat_producto = frappe.db.get_value(
			"SAT Producto Servicio", clave_prod_serv, "incluye_objeto_impuesto"
		)

		if not sat_producto:
			frappe.throw(
				f"ClaveProdServ '{clave_prod_serv}' no encontrada en catálogo SAT.\n"
				f"Verifique que existe en DocType 'SAT Producto Servicio'.",
				title="ClaveProdServ No Encontrada",
			)

		return sat_producto

	def _map_tax_account_to_sat(self, account_head):
		"""
		E4.4: Mapear cuenta ERPNext → metadata SAT.

		CAMBIO 4 APROBADO: Usar campo es_retencion del mapeo.

		Fuente: Configuración Fiscal México → mapeos (child table)

		Args:
			account_head: Nombre cuenta (ej: "123456 - iva 16% - _TC")

		Returns:
			{
				"impuesto_sat": str,      # "002"
				"tipo_factor": str,       # "Tasa"
				"nombre_sat": str,        # "IVA"
				"es_retencion": bool      # True/False
			}

		Raises:
			frappe.ValidationError: Si cuenta no mapeada
		"""
		# Obtener company desde settings (asumiendo que está configurado)
		settings = frappe.get_single("Facturacion Mexico Settings")
		company = (
			settings.company
			if hasattr(settings, "company")
			else frappe.defaults.get_global_default("company")
		)

		if not company:
			frappe.throw(
				"<div style='font-family: -apple-system, BlinkMacSystemFont, sans-serif;'>"
				"<p style='margin: 0 0 15px 0;'>No se pudo determinar la empresa para buscar configuración fiscal.</p>"
				"<p style='margin: 15px 0 8px 0; font-weight: 600;'>Solución:</p>"
				"<ol style='margin: 0; padding-left: 20px;'>"
				"<li>Configurar empresa en <strong>Facturacion Mexico Settings</strong></li>"
				"</ol>"
				"</div>",
				title="Empresa No Configurada",
			)

		# Buscar en configuración fiscal por company
		config_name = frappe.db.get_value("Configuracion Fiscal Mexico", {"company": company}, "name")

		if not config_name:
			frappe.throw(
				f"<div style='font-family: -apple-system, BlinkMacSystemFont, sans-serif;'>"
				f"<p style='margin: 0 0 15px 0;'>No existe configuración fiscal para la empresa <strong>{company}</strong>.</p>"
				f"<div style='background: #f8d7da; border-left: 4px solid #dc3545; padding: 12px; margin: 15px 0;'>"
				f"<p style='margin: 5px 0; font-size: 13px;'><strong>Cuenta a mapear:</strong> <code>{account_head}</code></p>"
				f"</div>"
				f"<p style='margin: 15px 0 8px 0; font-weight: 600;'>Solución:</p>"
				f"<ol style='margin: 0; padding-left: 20px;'>"
				f"<li>Crear documento: <strong>Configuración Fiscal México</strong></li>"
				f"<li>Seleccionar empresa: <strong>{company}</strong></li>"
				f"<li>Usar el wizard para generar mapeos automáticamente</li>"
				f"</ol>"
				f"</div>",
				title="Configuración Fiscal No Existe",
			)

		config = frappe.get_doc("Configuracion Fiscal Mexico", config_name)

		# Buscar en child table mapeo_cuentas (no "mapeos")
		if hasattr(config, "mapeo_cuentas") and config.mapeo_cuentas:
			for mapeo in config.mapeo_cuentas:
				if mapeo.cuenta_impuesto == account_head:
					# Determinar metadata SAT desde rol_fiscal
					# IMPORTANTE: Convertir explícitamente a bool (Frappe Check fields son 0/1)
					es_retencion = bool(mapeo.get("es_retencion", 0))
					integra_base_iva = bool(mapeo.get("integra_base_iva", 1))  # Default True
					return self._extract_sat_metadata_from_rol(
						mapeo.rol_fiscal, es_retencion, integra_base_iva
					)

		# Cuenta no mapeada = error (datos incompletos)
		frappe.throw(
			f"<div style='font-family: -apple-system, BlinkMacSystemFont, sans-serif;'>"
			f"<p style='margin: 0 0 15px 0;'>Cuenta de impuesto sin mapeo SAT.</p>"
			f"<div style='background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px; margin: 15px 0;'>"
			f"<p style='margin: 5px 0; font-size: 13px;'><strong>Cuenta:</strong> <code>{account_head}</code></p>"
			f"<p style='margin: 5px 0; font-size: 13px;'><strong>Empresa:</strong> {company}</p>"
			f"</div>"
			f"<p style='margin: 15px 0 8px 0; font-weight: 600;'>Solución:</p>"
			f"<ol style='margin: 0; padding-left: 20px;'>"
			f"<li>Ir a: <strong>Configuración Fiscal México</strong> (empresa {company})</li>"
			f"<li>Sección: <strong>Mapeos</strong></li>"
			f"<li>Usar el wizard para generar mapeos automáticamente</li>"
			f"<li>O agregar mapeo manual para esta cuenta</li>"
			f"</ol>"
			f"</div>",
			title="Mapeo SAT Faltante",
		)

	def _get_uom_base_from_tabla_sat(self, item_doc, account_head):
		"""
		Obtener UOM base desde tabla IEPS Cuota SAT.

		Args:
			item_doc: Item doc
			account_head: Cuenta IEPS

		Returns:
			str: UOM base (ej: "LTR", "H87") o None si no encuentra

		Ejemplo:
			>>> uom_base = self._get_uom_base_from_tabla_sat(item_doc, "2117002 - IEPS Azucar Bebidas")
			>>> # Retorna "LTR" para bebidas azucaradas
		"""
		clave_sat = item_doc.get("fm_producto_servicio_sat")
		if not clave_sat:
			return None

		# Buscar en tabla IEPS Cuota SAT
		result = frappe.db.sql(
			"""
			SELECT uom
			FROM `tabIEPS Cuota SAT`
			WHERE clave_prod_serv = %(clave_sat)s
			  AND cuenta_ieps = %(cuenta_ieps)s
			  AND vigencia_desde <= %(fecha)s
			  AND IFNULL(vigencia_hasta, '2099-12-31') >= %(fecha)s
			  AND docstatus < 2
			LIMIT 1
			""",
			{
				"clave_sat": clave_sat,
				"cuenta_ieps": account_head,
				"fecha": today(),
			},
			as_dict=True,
		)

		if result and len(result) > 0:
			return result[0].get("uom")

		return None

	def _get_cuota_from_tabla_sat(self, item_doc, account_head):
		"""
		Obtener cuota IEPS por UOM base desde tabla IEPS Cuota SAT.

		Args:
			item_doc: Item doc
			account_head: Cuenta IEPS

		Returns:
			float: Cuota por UOM base (ej: $1.27/litro, $5.49/litro) o None si no encuentra

		Ejemplo:
			>>> cuota = self._get_cuota_from_tabla_sat(item_doc, "2117002 - IEPS Azucar Bebidas")
			>>> # Retorna 1.27 para bebidas azucaradas ($1.27/litro)
		"""
		clave_sat = item_doc.get("fm_producto_servicio_sat")
		if not clave_sat:
			return None

		# Buscar en tabla IEPS Cuota SAT
		result = frappe.db.sql(
			"""
			SELECT cuota
			FROM `tabIEPS Cuota SAT`
			WHERE clave_prod_serv = %(clave_sat)s
			  AND cuenta_ieps = %(cuenta_ieps)s
			  AND vigencia_desde <= %(fecha)s
			  AND IFNULL(vigencia_hasta, '2099-12-31') >= %(fecha)s
			  AND docstatus < 2
			LIMIT 1
			""",
			{
				"clave_sat": clave_sat,
				"cuenta_ieps": account_head,
				"fecha": today(),
			},
			as_dict=True,
		)

		if result and len(result) > 0:
			return flt(result[0].get("cuota"))

		return None

	def _get_uom_conversion_factor(self, item_doc, item_uom, target_uom):
		"""
		Obtener factor conversión entre UOMs para IEPS Cuota.

		FIX E4.1: FacturAPI multiplica 'base' por cantidad, entonces necesitamos
		enviar factor conversión unitario (unidades_base por unidad_venta).

		Args:
			item_doc: Item doc
			item_uom: UOM del item en la factura (ej: "H87 - Pieza", "Nos")
			target_uom: UOM base desde tabla SAT (ej: "LTR", "H87")

		Returns:
			float: Factor conversión (ejemplo: 0.6 para botella 600ml, 1.0 si mismo UOM)

		Raises:
			ValidationError: Si UOM no tiene conversión configurada

		Ejemplo:
			>>> factor = self._get_uom_conversion_factor(item_doc, "Nos", "LTR")
			>>> # Retorna 0.6 si item tiene configurado 600ml por unidad
		"""
		# Si ya está en UOM base, factor = 1.0
		if item_uom == target_uom:
			return 1.0

		# Intentar obtener conversión desde ERPNext
		if get_conversion_factor:
			try:
				conversion_data = get_conversion_factor(item_doc.name, target_uom)
				factor = flt(conversion_data.get("conversion_factor", 0))

				if factor > 0:
					return factor
			except Exception:
				pass

		# Si no hay conversión configurada, ERROR
		frappe.throw(
			_(
				"No se puede calcular IEPS Cuota: falta configurar conversión de UOM '{item_uom}' a '{target_uom}' para el item '{item}'.\n\n"
				"Soluciones:\n"
				"1. Configurar 'UOM Conversion Factor' en el Item para convertir {item_uom} → {target_uom}\n"
				"2. O cambiar el UOM del item en la factura a '{target_uom}' directamente"
			).format(item_uom=item_uom, target_uom=target_uom, item=item_doc.item_name or item_doc.name),
			title=_("Factor Conversión UOM Requerido"),
		)

	def _extract_sat_metadata_from_rol(self, rol_fiscal, es_retencion, integra_base_iva=True):
		"""
		Helper: Extraer metadata SAT desde rol_fiscal usando catálogo oficial.

		Args:
			rol_fiscal: str (ej: "IVA por Pagar (16%)")
			es_retencion: bool
			integra_base_iva: bool - Si este impuesto integra la base del IVA (default True)

		Returns:
			dict con impuesto_sat, tipo_factor, nombre_sat, es_retencion, integra_base_iva
		"""
		# Obtener metadata desde catálogo oficial (single source of truth)
		try:
			config = SATTipoFactor.get_metadata_completa(rol_fiscal)
			return {
				"impuesto_sat": config["impuesto_sat"],
				"tipo_factor": config["tipo_factor"],  # "Tasa" o "Cuota" desde catálogo
				"nombre_sat": config["nombre_sat"],
				"es_retencion": es_retencion,
				"integra_base_iva": integra_base_iva,  # IEPS Combustibles = False, resto = True
			}
		except ValueError as e:
			frappe.throw(str(e), title="Rol Fiscal No Configurado")

	def _validate_objeto_imp_consistency(self, objeto_imp, taxes_payload, item):
		"""
		E4.6: Validar coherencia ObjetoImp vs presencia de impuestos.

		CAMBIO 2 APROBADO: Validación estricta sin arreglos automáticos.

		Reglas (según catálogo SAT c_ObjetoImp):
		- ObjetoImp que NO permiten desglose → NO debe tener taxes
		- ObjetoImp que REQUIEREN desglose (02) → DEBE tener taxes

		Args:
			objeto_imp: str - Código ObjetoImp ("01"-"08")
			taxes_payload: list de impuestos
			item: Row de Sales Invoice.items

		Raises:
			frappe.ValidationError: Si inconsistencia detectada
		"""
		# Si ObjetoImp prohíbe desglose pero SI tiene taxes
		if SATObjetoImpuesto.forbids_tax_breakdown(objeto_imp) and taxes_payload:
			frappe.throw(
				f"<div style='font-family: -apple-system, BlinkMacSystemFont, sans-serif;'>"
				f"<p style='margin: 0 0 15px 0; font-size: 14px;'><strong>Item:</strong> <code>{item.item_code}</code> - {item.item_name or item.description}</p>"
				f"<div style='background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px; margin: 15px 0;'>"
				f"<p style='margin: 5px 0; font-size: 13px;'><strong>ObjetoImp (Catálogo SAT):</strong> <code>{objeto_imp}</code> - No objeto de impuesto</p>"
				f"<p style='margin: 5px 0; font-size: 13px;'><strong>Sales Invoice:</strong> {len(taxes_payload)} impuesto(s) configurado(s)</p>"
				f"</div>"
				f"<p style='margin: 15px 0 8px 0; font-weight: 600;'>Soluciones:</p>"
				f"<ol style='margin: 0; padding-left: 20px;'>"
				f"<li style='margin-bottom: 8px;'><strong>Si el item SÍ causa impuestos:</strong> Actualizar catálogo SAT a ObjetoImp <code>02</code></li>"
				f"<li style='margin-bottom: 8px;'><strong>Si el item NO causa impuestos:</strong> Quitar Item Tax Template</li>"
				f"</ol>"
				f"<p style='margin: 15px 0 0 0; color: #6c757d; font-size: 12px;'>📘 CFDI 4.0 c_ObjetoImp - SAT Anexo 20</p>"
				f"</div>",
				title="Validación Fiscal CFDI 4.0",
			)

		# Si ObjetoImp requiere desglose pero NO tiene taxes
		if SATObjetoImpuesto.requires_tax_breakdown(objeto_imp) and not taxes_payload:
			frappe.throw(
				f"<div style='font-family: -apple-system, BlinkMacSystemFont, sans-serif;'>"
				f"<p style='margin: 0 0 15px 0; font-size: 14px;'><strong>Item:</strong> <code>{item.item_code}</code> - {item.item_name or item.description}</p>"
				f"<div style='background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px; margin: 15px 0;'>"
				f"<p style='margin: 5px 0; font-size: 13px;'><strong>ObjetoImp (Catálogo SAT):</strong> <code>02</code> - Sí objeto de impuesto</p>"
				f"<p style='margin: 5px 0; font-size: 13px;'><strong>Sales Invoice:</strong> Sin impuestos configurados</p>"
				f"</div>"
				f"<p style='margin: 15px 0 8px 0; font-weight: 600;'>Soluciones:</p>"
				f"<ol style='margin: 0; padding-left: 20px;'>"
				f"<li style='margin-bottom: 8px;'><strong>Si el item causa impuestos:</strong> Configurar Item Tax Template o verificar template por defecto del branch</li>"
				f"<li style='margin-bottom: 8px;'><strong>Si el item NO causa impuestos:</strong> Actualizar catálogo SAT a ObjetoImp <code>01</code></li>"
				f"</ol>"
				f"<p style='margin: 15px 0 0 0; color: #6c757d; font-size: 12px;'>📘 CFDI 4.0 c_ObjetoImp - SAT Anexo 20</p>"
				f"</div>",
				title="Validación Fiscal CFDI 4.0",
			)

	def _validate_currency_consistency(self, invoice_data, sales_invoice):
		"""
		E4.7: Validar consistencia moneda payload vs SI.

		CAMBIO 3 APROBADO: Validación simplificada sin conversiones.

		Args:
			invoice_data: Payload FacturAPI
			sales_invoice: Documento Sales Invoice

		Raises:
			frappe.ValidationError: Si moneda inconsistente
		"""
		payload_currency = invoice_data.get("currency", "MXN")
		si_currency = sales_invoice.currency

		if payload_currency != si_currency:
			frappe.throw(
				f"Moneda inconsistente:\n\n"
				f"• Payload: {payload_currency}\n"
				f"• Sales Invoice: {si_currency}\n\n"
				f"El payload debe usar la misma moneda que Sales Invoice.",
				title="Moneda Inconsistente",
			)

		# Log informativo si hay tipo de cambio
		if sales_invoice.conversion_rate and sales_invoice.conversion_rate != 1.0:
			frappe.logger().info(
				f"SI {sales_invoice.name} con tipo cambio {sales_invoice.conversion_rate}. "
				f"Amounts ya están convertidos a {si_currency}."
			)

	def _validate_payload_completeness_ro(self, invoice_data, sales_invoice):
		"""
		E4.8: Validar completitud payload E4-RO antes de envío al PAC.

		CONTEXTO:
		Esta función implementa la validación crítica de completitud del payload
		generado por las funciones E4.1-E4.7. No realiza cálculos, solo verifica
		que todos los campos requeridos por FacturAPI estén presentes.

		VALIDACIONES:
		1. Datos del cliente (customer): legal_name, tax_id, tax_system
		2. Datos de la factura: payment_form, use (Uso CFDI)
		3. Estructura items[]: presencia de conceptos
		4. Por cada item: product_key, unit_key, description, tax_object
		5. Por cada tax del item: type, factor, rate, withholding

		Args:
			invoice_data: Payload completo generado para FacturAPI
			sales_invoice: Documento Sales Invoice (referencia para logs)

		Raises:
			frappe.ValidationError: Si encuentra campos faltantes

		Returns:
			bool: True si validación exitosa

		Ejemplo de error:
			Payload incompleto (3 errores):
			❌ customer.tax_system faltante
			❌ payment_form faltante
			❌ Item 1: product.tax_object faltante
		"""
		errors = []

		# Mapeo de campos técnicos a nombres amigables para el usuario
		field_labels = {
			"legal_name": "Razón Social del Cliente",
			"tax_id": "RFC del Cliente",
			"tax_system": "Régimen Fiscal del Cliente",
			"payment_form": "Forma de Pago",
			"use": "Uso CFDI",
			"product_key": "Clave Producto/Servicio SAT",
			"unit_key": "Clave Unidad SAT",
			"description": "Descripción del Producto",
			"taxability": "Objeto de Impuesto (ObjetoImp)",
		}

		# === DATOS CLIENTE ===
		customer_data = invoice_data.get("customer", {})
		required_customer_fields = ["legal_name", "tax_id", "tax_system"]

		for field in required_customer_fields:
			if not customer_data.get(field):
				label = field_labels.get(field, field)
				errors.append(f"❌ {label} faltante en el Cliente")

		# === DATOS FACTURA ===
		if not invoice_data.get("payment_form"):
			errors.append(f"❌ {field_labels['payment_form']} faltante en la Factura")

		if not invoice_data.get("use"):
			errors.append(f"❌ {field_labels['use']} faltante en el Cliente")

		# === ITEMS Y CONCEPTOS ===
		items = invoice_data.get("items", [])

		if not items:
			errors.append("❌ La factura no tiene productos/conceptos para timbrar")

		for idx, item_payload in enumerate(items, 1):
			product = item_payload.get("product", {})

			# Campos requeridos del producto
			required_product_fields = ["product_key", "unit_key", "description", "taxability"]
			for field in required_product_fields:
				if not product.get(field):
					label = field_labels.get(field, field)
					# Obtener nombre del item si está disponible
					item_name = product.get("description", f"Item {idx}")
					errors.append(f"❌ {label} faltante en '{item_name}'")

			# Validar taxes si existen
			taxes_payload = product.get("taxes", [])
			for tax_idx, tax in enumerate(taxes_payload, 1):
				if not tax.get("type"):
					errors.append(f"❌ Item {idx}, Tax {tax_idx}: type faltante")
				if not tax.get("factor"):
					errors.append(f"❌ Item {idx}, Tax {tax_idx}: factor faltante")

				# Validar rate según tipo de factor
				factor = tax.get("factor")
				rate = tax.get("rate")

				if factor == "Tasa":
					# Para Tasa, rate es obligatorio
					if rate is None:
						errors.append(f"❌ Item {idx}, Tax {tax_idx}: rate faltante (requerido para Tasa)")
					elif not FacturAPITaxRates.validar_rate_por_tipo(
						tax.get("type", ""),
						rate,
						tax.get("withholding", False),
					):
						# Rate no está en lista permitida FacturAPI
						rates_permitidas = FacturAPITaxRates.get_rates_permitidas(
							tax.get("type", ""), tax.get("withholding", False)
						)
						rates_str = ", ".join([f"{r * 100:.2f}%" for r in rates_permitidas[:5]])
						if len(rates_permitidas) > 5:
							rates_str += "..."
						errors.append(
							f"❌ Item {idx}, Tax {tax_idx}: rate {rate * 100:.2f}% no permitido por FacturAPI "
							f"(permitidos: {rates_str})"
						)
				elif factor == "Cuota":
					# Para Cuota, FacturAPI requiere rate=cuota/unidad y base=cantidad física
					if rate is None:
						errors.append(
							f"❌ Item {idx}, Tax {tax_idx}: rate faltante (debe ser cuota por unidad)"
						)
					elif rate < 0:
						errors.append(
							f"❌ Item {idx}, Tax {tax_idx}: Cuota debe tener rate > 0 (cuota/unidad), encontrado {rate}"
						)
					# Validar que base existe para Cuota
					if "base" not in tax:
						errors.append(
							f"❌ Item {idx}, Tax {tax_idx}: base faltante (cantidad física requerida para Cuota)"
						)
					elif flt(tax.get("base", 0)) <= 0:
						errors.append(
							f"❌ Item {idx}, Tax {tax_idx}: base debe ser > 0 para Cuota, encontrado {tax.get('base')}"
						)

				if "withholding" not in tax:  # withholding puede ser False, validar presencia
					errors.append(f"❌ Item {idx}, Tax {tax_idx}: withholding faltante")

		# === RESULTADO ===
		if errors:
			# Construir lista de errores en HTML (máximo 10)
			error_items = ""
			for error in errors[:10]:
				error_items += f"<li style='margin-bottom: 8px; font-size: 13px;'>{error}</li>"

			if len(errors) > 10:
				error_items += f"<li style='margin-bottom: 8px; font-size: 13px; color: #6c757d;'>... y {len(errors) - 10} errores más</li>"

			# Mensaje de ayuda según tipo de error
			help_items = ""
			if any("Cliente" in e for e in errors):
				help_items += "<li style='margin-bottom: 8px;'>Revise los datos fiscales del Cliente (RFC, Régimen Fiscal, Uso CFDI)</li>"
			if any("Forma de Pago" in e for e in errors):
				help_items += (
					"<li style='margin-bottom: 8px;'>Configure la Forma de Pago en la Factura Fiscal</li>"
				)
			if any("Clave Producto" in e or "ObjetoImp" in e for e in errors):
				help_items += "<li style='margin-bottom: 8px;'>Revise que todos los productos tengan configurada la Clave Producto/Servicio SAT</li>"
			if any("Cuota" in e for e in errors):
				help_items += "<li style='margin-bottom: 8px;'>IEPS Cuota: Verificar que hook calcule correctamente el monto (cuota/unidad x cantidad)</li>"

			frappe.throw(
				f"<div style='font-family: -apple-system, BlinkMacSystemFont, sans-serif;'>"
				f"<p style='margin: 0 0 15px 0;'>No se puede timbrar <strong>{sales_invoice.name}</strong> porque faltan datos requeridos:</p>"
				f"<div style='background: #f8d7da; border-left: 4px solid #dc3545; padding: 12px; margin: 15px 0;'>"
				f"<ul style='margin: 0; padding-left: 20px;'>{error_items}</ul>"
				f"</div>"
				f"<p style='margin: 15px 0 8px 0; font-weight: 600;'>💡 Para corregir estos errores:</p>"
				f"<ol style='margin: 0; padding-left: 20px;'>{help_items}</ol>"
				f"</div>",
				title="Datos Incompletos para Timbrado CFDI",
			)

		# Log éxito validación
		frappe.logger().info(
			f"E4.8: Payload validado OK para {sales_invoice.name} "
			f"({len(items)} items, cliente: {customer_data.get('legal_name', 'N/A')})"
		)

		return True


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
		_("No se encontró opción válida para motivo {0}. Ajusta DocType u opciones.").format(motive_code),
		title=_("Opciones de cancelación inválidas"),
	)


# API endpoints para uso desde interfaz
@frappe.whitelist()
def timbrar_factura(sales_invoice: str):
	"""API para timbrar factura desde interfaz."""
	cache_key = f"si:timbrando:{sales_invoice}"
	if frappe.cache().get_value(cache_key):
		frappe.throw(_("Ya hay un timbrado en proceso. Intente en unos segundos."))
	frappe.cache().set_value(cache_key, frappe.utils.now(), expires_in_sec=120)
	try:
		ffm_name = frappe.db.get_value(
			"Factura Fiscal Mexico", {"sales_invoice": sales_invoice, "docstatus": 1}, "name"
		)
		if ffm_name and frappe.db.get_value("Factura Fiscal Mexico", ffm_name, "fm_uuid"):
			frappe.throw(_("Esta factura fiscal ya está timbrada."))
		api = TimbradoAPI()
		return api.timbrar_factura(sales_invoice)
	finally:
		frappe.cache().delete_value(cache_key)


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
		frappe.throw(_("No se pudo determinar el Sales Invoice para cancelación"))

	# Importar enum de motivos SAT
	from facturacion_mexico.config.sat_cancellation_motives import SAT_MOTIVES

	# Validación motivo es obligatorio
	if not motivo:
		frappe.throw(_("El motivo de cancelación es obligatorio. Debe seleccionar una opción."))

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
	# Obtener FFM doc para el guard y persistencia
	ffm_doc = None
	ffm_name = None
	if sales_invoice:
		ffm_list = frappe.get_all("Factura Fiscal Mexico", filters={"sales_invoice": sales_invoice}, limit=1)
		if ffm_list:
			ffm_name = ffm_list[0].name
			ffm_doc = frappe.get_doc("Factura Fiscal Mexico", ffm_name)

	if ffm_doc:
		_guard_motive_01_only_from_substitution(ffm_doc, motivo_code, substitution_uuid)

	# Persistir motivo de cancelación antes de enviar al PAC
	if ffm_name:
		frappe.db.set_value("Factura Fiscal Mexico", ffm_name, {"fm_motivo_cancelacion": motivo_code})

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
		fields=["name", "cancellation_date", "status", "cancellation_reason"],
		order_by="COALESCE(cancellation_date, modified) desc",
		limit_page_length=5,
	)
	# Devuelve la primera que realmente esté CANCELADA fiscalmente
	for r in ffm_list:
		if (r.status or "").upper() == "CANCELADO":
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
		{"sales_invoice": si.name, "status": "TIMBRADO"},
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

		orig_status = frappe.db.get_value("Factura Fiscal Mexico", orig_ffm_name, "status")
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
				orig_ffm.set("status", "CANCELADO")
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

			# Restaurar link sales_invoice en FFM original (limpiado por hardening preventivo)
			try:
				orig_ffm.db_set("sales_invoice", orig_si_name)
				frappe.logger().info(f"Link sales_invoice restaurado en FFM {orig_ffm_name} → {orig_si_name}")
			except Exception as e:
				frappe.logger().warning(f"No se pudo restaurar link sales_invoice en FFM: {e}")

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
	status = (getattr(ffm_doc, "status", "") or "").upper()

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
def revisar_estatus_cancelacion(ffm_name: str) -> dict:
	"""Consulta FacturAPI para resolver estado PENDIENTE_CANCELACION."""
	ffm = frappe.get_doc("Factura Fiscal Mexico", ffm_name)

	if ffm.status != FiscalStates.PENDIENTE_CANCELACION:
		frappe.throw(_("El documento no está en estado PENDIENTE_CANCELACION"))

	from facturacion_mexico.facturacion_fiscal.api_client import query_pac_status

	result = query_pac_status(ffm_name)

	if not result.get("success"):
		frappe.throw(_("Error al consultar PAC: {0}").format(result.get("error")))

	data = result.get("data", {})
	pac_status = data.get("status", "")
	cancel_status = data.get("cancellation_status", "")

	if pac_status == "canceled" or cancel_status == "accepted":
		nuevo_estado = FiscalStates.CANCELADO
		update_data = {
			"status": nuevo_estado,
			"cancellation_date": now_datetime(),
		}
		msg = _("Cancelación confirmada por el receptor. CFDI cancelado.")
		indicator = "green"
	elif cancel_status == "rejected":
		nuevo_estado = FiscalStates.TIMBRADO
		update_data = {
			"status": nuevo_estado,
			"fm_motivo_cancelacion": None,
		}
		msg = _("El receptor rechazó la cancelación. CFDI sigue vigente.")
		indicator = "orange"
	else:
		nuevo_estado = FiscalStates.PENDIENTE_CANCELACION
		update_data = {"status": nuevo_estado}
		msg = _("Cancelación aún pendiente de aceptación por el receptor.")
		indicator = "blue"

	frappe.db.set_value("Factura Fiscal Mexico", ffm_name, update_data)
	if ffm.sales_invoice:
		frappe.db.set_value("Sales Invoice", ffm.sales_invoice, {"fm_fiscal_status": nuevo_estado})

	# Registrar consulta en FacturAPI Response Log para trazabilidad
	try:
		write_pac_response(
			sales_invoice_name=ffm.sales_invoice or "",
			request_data=json.dumps(
				{"action": "consulta_estatus", "ffm": ffm_name, "facturapi_id": ffm.facturapi_id}
			),
			response_data=json.dumps(
				{
					"success": True,
					"status_code": 200,
					"raw_response": data,
					"resultado_transicion": nuevo_estado,
				},
				default=str,
			),
			operation_type="consulta",
		)
	except Exception as log_err:
		frappe.logger().warning(f"No se pudo registrar log de consulta estatus {ffm_name}: {log_err}")

	frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to persist status transition immediately after PAC response

	return {
		"status": nuevo_estado,
		"message": msg,
		"indicator": indicator,
		"cancellation_status": cancel_status,
	}


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
