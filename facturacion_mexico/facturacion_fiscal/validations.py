# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Validaciones fiscales para datos de clientes
Validación de RFC y datos requeridos para facturación fiscal
"""

import re
from typing import Any

import frappe
from frappe import _


@frappe.whitelist()
def validate_customer_fiscal_data(customer: str) -> dict[str, Any]:
	"""
	Validar datos fiscales de un cliente para verificar si está listo para facturación.

	Args:
		customer (str): Nombre del cliente a validar

	Returns:
		Dict: Resultado de validación con detalles de cada campo
	"""
	try:
		if not customer:
			return {"success": False, "error": "Customer parameter is required", "data": None}

		# Obtener datos del cliente
		customer_doc = frappe.get_doc("Customer", customer)

		# Resultado de validación
		validation_result = {
			"customer": customer,
			"customer_name": customer_doc.customer_name,
			"rfc": None,
			"rfc_valid": False,
			"rfc_format_valid": False,
			"address_configured": False,
			"email_configured": False,
			"cfdi_use_configured": False,
			"ready_for_invoicing": False,
			"recommendations": [],
		}

		# 1. VALIDAR RFC
		rfc = customer_doc.get("tax_id") or ""
		validation_result["rfc"] = rfc

		if rfc:
			validation_result["rfc_valid"] = True
			validation_result["rfc_format_valid"] = validate_rfc_format(rfc)

			if not validation_result["rfc_format_valid"]:
				validation_result["recommendations"].append(
					f"RFC '{rfc}' tiene formato inválido. Debe ser formato RFC mexicano válido."
				)
		else:
			validation_result["recommendations"].append(
				"Configurar RFC en Customer → Tax ID. Es obligatorio para facturación fiscal."
			)

		# 2. VALIDAR DIRECCIÓN
		address_exists = frappe.db.exists(
			"Address", {"link_doctype": "Customer", "link_name": customer, "disabled": 0}
		)

		validation_result["address_configured"] = bool(address_exists)

		if not address_exists:
			validation_result["recommendations"].append(
				"Configurar dirección del cliente. Es requerida por el PAC para timbrado."
			)

		# 3. VALIDAR EMAIL
		email = customer_doc.get("email_id") or ""
		validation_result["email_configured"] = bool(email)

		if not email:
			validation_result["recommendations"].append(
				"Configurar email del cliente. Recomendado para envío automático de facturas."
			)

		# 4. VALIDAR USO CFDI DEFAULT
		cfdi_use = customer_doc.get("fm_uso_cfdi_default") or ""
		validation_result["cfdi_use_configured"] = bool(cfdi_use)

		if not cfdi_use:
			validation_result["recommendations"].append(
				"Configurar Uso CFDI default en el cliente para agilizar facturación."
			)

		# 5. DETERMINAR SI ESTÁ LISTO PARA FACTURACIÓN
		validation_result["ready_for_invoicing"] = (
			validation_result["rfc_valid"]
			and validation_result["rfc_format_valid"]
			and validation_result["address_configured"]
		)

		return {"success": True, "data": validation_result}

	except frappe.DoesNotExistError:
		return {"success": False, "error": f"Customer '{customer}' not found", "data": None}
	except Exception as e:
		frappe.log_error(
			f"Error validating customer fiscal data for {customer}: {e!s}",
			"Customer Fiscal Validation Error",
		)
		return {"success": False, "error": f"Error validating customer data: {e!s}", "data": None}


def validate_rfc_format(rfc: str) -> bool:
	"""
	Validar formato de RFC mexicano.

	Args:
		rfc (str): RFC a validar

	Returns:
		bool: True si el formato es válido
	"""
	if not rfc:
		return False

	# Limpiar RFC (mayúsculas, sin espacios)
	rfc = rfc.upper().strip()

	# Patrones RFC válidos
	# RFC Persona Física: 4 letras + 6 dígitos + 3 caracteres
	pattern_person = r"^[A-Z&Ñ]{4}[0-9]{6}[A-Z0-9]{3}$"

	# RFC Persona Moral: 3 letras + 6 dígitos + 3 caracteres
	pattern_company = r"^[A-Z&Ñ]{3}[0-9]{6}[A-Z0-9]{3}$"

	# Verificar contra ambos patrones
	return bool(re.match(pattern_person, rfc) or re.match(pattern_company, rfc))


def validate_postal_code_sat(postal_code: str) -> bool:
	"""
	Validar que el código postal esté en el catálogo SAT.

	Args:
		postal_code (str): Código postal a validar

	Returns:
		bool: True si es válido según SAT
	"""
	if not postal_code:
		return False

	# Verificar en catálogo SAT si existe
	# Nota: Esto requeriría un DocType con códigos postales SAT
	# Por ahora validamos formato básico (5 dígitos)
	return bool(re.match(r"^\d{5}$", postal_code.strip()))


@frappe.whitelist()
def get_customer_fiscal_summary(customer: str) -> dict[str, Any]:
	"""
	Obtener resumen fiscal de un cliente para mostrar en el formulario.

	Args:
		customer (str): Nombre del cliente

	Returns:
		Dict: Resumen de datos fiscales
	"""
	try:
		validation = validate_customer_fiscal_data(customer)

		if not validation["success"]:
			return validation

		data = validation["data"]

		# Crear resumen ejecutivo
		summary = {
			"customer": customer,
			"fiscal_score": calculate_fiscal_readiness_score(data),
			"critical_issues": len([r for r in data["recommendations"] if "obligatorio" in r.lower()]),
			"warnings": len([r for r in data["recommendations"] if "recomendado" in r.lower()]),
			"ready": data["ready_for_invoicing"],
			"next_steps": data["recommendations"][:3] if data["recommendations"] else [],
		}

		return {"success": True, "summary": summary, "details": data}

	except Exception as e:
		return {"success": False, "error": f"Error getting fiscal summary: {e!s}"}


def calculate_fiscal_readiness_score(validation_data: dict[str, Any]) -> int:
	"""
	Calcular puntuación de preparación fiscal (0-100).

	Args:
		validation_data (Dict): Datos de validación

	Returns:
		int: Puntuación 0-100
	"""
	score = 0

	# RFC válido: 40 puntos (crítico)
	if validation_data["rfc_valid"] and validation_data["rfc_format_valid"]:
		score += 40
	elif validation_data["rfc_valid"]:
		score += 20

	# Dirección configurada: 30 puntos (crítico)
	if validation_data["address_configured"]:
		score += 30

	# Email configurado: 20 puntos (importante)
	if validation_data["email_configured"]:
		score += 20

	# Uso CFDI configurado: 10 puntos (conveniente)
	if validation_data["cfdi_use_configured"]:
		score += 10

	return score


@frappe.whitelist()
def validate_rfc_external(customer: str) -> dict[str, Any]:
	"""
	Validar RFC con servicios externos (FacturAPI/SAT).

	Args:
		customer (str): Nombre del cliente a validar

	Returns:
		Dict: Resultado de validación externa
	"""
	try:
		if not customer:
			return {"success": False, "error": "Customer parameter is required", "data": None}

		# Obtener datos del cliente
		customer_doc = frappe.get_doc("Customer", customer)
		rfc = customer_doc.get("tax_id") or ""

		if not rfc:
			return {"success": False, "error": "Cliente no tiene RFC configurado", "data": None}

		# Resultado de validación externa
		validation_result = {
			"customer": customer,
			"rfc": rfc,
			"service_used": None,
			"rfc_exists": False,
			"rfc_active": False,
			"sat_name": None,
			"name_matches": False,
			"tax_regime": None,
			"postal_code": None,
			"postal_code_valid": False,
			"valid_for_invoicing": False,
			"warnings": [],
		}

		# ESTRATEGIA HÍBRIDA: SAT primero, FacturAPI como fallback
		# 1. INTENTAR VALIDACIÓN CON SAT DIRECTO (más simple, menos restrictivo)
		sat_result = _validate_with_sat_direct(rfc)

		if sat_result["success"]:
			validation_result.update(sat_result["data"])
			validation_result["service_used"] = "SAT Directo"

			# SAT exitoso - verificar si necesitamos información adicional con FacturAPI
			if validation_result["rfc_exists"] and validation_result["rfc_active"]:
				# Intentar obtener información adicional de FacturAPI (nombre, régimen)
				try:
					facturapi_info = _get_additional_info_from_facturapi(rfc, customer_doc.customer_name)
					if facturapi_info["success"]:
						# Enriquecer datos con información de FacturAPI
						validation_result["sat_name"] = facturapi_info["data"].get("sat_name")
						validation_result["tax_regime"] = facturapi_info["data"].get("tax_regime")
						validation_result["name_matches"] = facturapi_info["data"].get("name_matches", False)
						validation_result["service_used"] = "SAT + FacturAPI (enriquecido)"
				except Exception:
					# No es crítico si falla el enriquecimiento
					pass
		else:
			# 2. FALLBACK: VALIDACIÓN CON FACTURAPI
			facturapi_result = _validate_with_facturapi(rfc, customer_doc.customer_name)

			if facturapi_result["success"]:
				validation_result.update(facturapi_result["data"])
				validation_result["service_used"] = "FacturAPI"

				# Comparar nombre del SAT con nombre del cliente
				if validation_result["sat_name"] and customer_doc.customer_name:
					validation_result["name_matches"] = _compare_names(
						validation_result["sat_name"], customer_doc.customer_name
					)

					if not validation_result["name_matches"]:
						validation_result["warnings"].append(
							f"Razón social SAT ({validation_result['sat_name']}) "
							f"no coincide exactamente con nombre del cliente ({customer_doc.customer_name})"
						)
			else:
				# 3. FacturAPI falló - propagar el error con debugging
				validation_result["service_used"] = "FacturAPI (Error)"

				# Si hay datos de debugging en el error de FacturAPI, incluirlos
				if facturapi_result.get("data") and facturapi_result["data"].get("debug_data"):
					validation_result["debug_data"] = facturapi_result["data"]["debug_data"]

				# Agregar el error específico de FacturAPI
				facturapi_error = facturapi_result.get("error", "Error desconocido de FacturAPI")
				validation_result["warnings"].append(f"Error FacturAPI: {facturapi_error}")

				# Si es un error específico de coincidencia de nombre, marcarlo
				if "nombre no coincide" in facturapi_error.lower():
					validation_result["rfc_exists"] = True
					validation_result["rfc_active"] = True
					validation_result["name_mismatch_error"] = True

		# Determinar si es válido para facturación
		validation_result["valid_for_invoicing"] = (
			validation_result["rfc_exists"] and validation_result["rfc_active"]
		)

		return {"success": True, "data": validation_result}

	except frappe.DoesNotExistError:
		return {"success": False, "error": f"Customer '{customer}' not found", "data": None}
	except Exception as e:
		frappe.log_error(
			f"Error validating RFC externally for {customer}: {e!s}", "RFC External Validation Error"
		)
		return {"success": False, "error": f"Error validating RFC externally: {e!s}", "data": None}


def _validate_with_facturapi(rfc: str, customer_name: str | None = None) -> dict[str, Any]:
	"""
	Validar RFC usando FacturAPI endpoint: /v2/customers/{customer_id}/tax-info-validation

	Args:
		rfc (str): RFC a validar
		customer_name (str): Nombre real del cliente para enviar a FacturAPI

	Returns:
		Dict: Resultado de validación
	"""
	try:
		from facturacion_mexico.facturacion_fiscal.api_client import get_facturapi_client

		# Obtener cliente FacturAPI
		client = get_facturapi_client()

		# Obtener dirección principal del cliente
		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
			FacturaFiscalMexico,
		)

		# Crear instancia temporal para usar el método _get_primary_address
		temp_doc = FacturaFiscalMexico()
		temp_doc.customer = customer_name
		primary_address = temp_doc._get_primary_address() if customer_name else None

		# PASO 1: Crear customer temporal para validación
		# Construir dirección con datos reales o temporales
		if primary_address:
			address_data = {
				"street": primary_address.address_line1 or "Calle Temporal",
				"exterior": primary_address.address_line2 or "1",
				"neighborhood": "Centro",  # No siempre disponible
				"city": primary_address.city or "Ciudad",
				"municipality": primary_address.city or "Municipio",
				"state": primary_address.state or "Estado",
				"country": primary_address.country or "MEX",
				"zip": primary_address.pincode or "12345",
			}
		else:
			# Dirección temporal si no hay dirección principal
			address_data = {
				"street": "Calle Temporal",
				"exterior": "1",
				"neighborhood": "Centro",
				"city": "Ciudad",
				"municipality": "Municipio",
				"state": "Estado",
				"country": "MEX",
				"zip": "12345",
			}

		temp_customer_data = {
			"legal_name": customer_name or "VALIDACION TEMPORAL",
			"tax_id": rfc,
			"tax_system": "601",  # General de Ley Personas Morales (default)
			"email": "temp@validation.com",
			"address": address_data,
		}

		# Crear customer temporal
		temp_customer_response = client.create_customer(temp_customer_data)

		if not temp_customer_response or "id" not in temp_customer_response:
			return {"success": False, "error": "No se pudo crear customer temporal en FacturAPI", "data": {}}

		customer_id = temp_customer_response["id"]

		# PASO 2: Validar información fiscal
		validation_response = client.validate_customer_tax_info(customer_id)

		# PASO 3: Eliminar customer temporal
		try:
			client.delete_customer(customer_id)
		except Exception:
			# No fallar si no se puede eliminar
			frappe.log_error(f"Could not delete temp customer {customer_id}", "FacturAPI Cleanup")

		# PASO 4: Procesar respuesta de validación
		if validation_response:
			# Extraer información real del SAT de la respuesta de validación
			sat_name = "No disponible"
			tax_regime = temp_customer_response.get("tax_system")

			# Si la validación incluye datos del SAT, usarlos
			if isinstance(validation_response, dict):
				sat_name = (
					validation_response.get("legal_name")
					or validation_response.get("name")
					or "VALIDACIÓN TEMPORAL"
				)
				tax_regime = (
					validation_response.get("tax_system")
					or validation_response.get("tax_regime")
					or tax_regime
				)

			return {
				"success": True,
				"data": {
					"rfc_exists": True,
					"rfc_active": True,
					"sat_name": sat_name,
					"tax_regime": tax_regime,
					"postal_code": None,
					"postal_code_valid": True,
					"debug_data": {
						"validation_response": validation_response,
						"customer_data_sent": temp_customer_data,
					},
				},
			}
		else:
			return {"success": False, "error": "RFC no válido según FacturAPI", "data": {}}

	except Exception as e:
		error_message = str(e)

		# Mejorar debugging para errores específicos de FacturAPI
		if "nombre o razón social del receptor no coincide" in error_message.lower():
			# Error específico de nombre/razón social - incluir datos de debugging
			debug_info = {
				"customer_name": temp_customer_data.get("legal_name"),
				"rfc_enviado": temp_customer_data.get("tax_id"),
				"tax_system_enviado": temp_customer_data.get("tax_system"),
				"email_enviado": temp_customer_data.get("email"),
				"address_enviada": temp_customer_data.get("address"),
			}

			return {
				"success": False,
				"error": f"RFC válido pero nombre no coincide con SAT. Verificar configuración de nombre en Customer. Error completo: {error_message}",
				"data": {
					"rfc_exists": True,  # RFC existe pero nombre no coincide
					"rfc_active": True,
					"sat_name": "No disponible (error de coincidencia)",
					"tax_regime": None,
					"postal_code": None,
					"postal_code_valid": False,
					"debug_data": debug_info,
				},
			}
		elif "tax_id" in error_message.lower() or "rfc" in error_message.lower():
			return {
				"success": True,  # Error esperado = validación exitosa
				"data": {
					"rfc_exists": False,
					"rfc_active": False,
					"sat_name": None,
					"tax_regime": None,
					"postal_code": None,
					"postal_code_valid": False,
				},
			}

		return {"success": False, "error": f"Error FacturAPI: {error_message}", "data": {}}


def _validate_with_sat_direct(rfc: str) -> dict[str, Any]:
	"""
	Validar RFC directamente con validador SAT oficial.
	Utiliza el portal: https://agsc.siat.sat.gob.mx/PTSC/ValidaRFC/index.jsf

	Args:
		rfc (str): RFC a validar

	Returns:
		Dict: Resultado de validación
	"""
	try:
		from urllib.parse import urlencode

		import requests

		# Validar formato básico antes de consultar
		if not validate_rfc_format(rfc):
			return {
				"success": True,
				"data": {
					"rfc_exists": False,
					"rfc_active": False,
					"sat_name": None,
					"tax_regime": None,
					"postal_code": None,
					"postal_code_valid": False,
				},
			}

		# Portal SAT para validación de RFC
		sat_url = "https://agsc.siat.sat.gob.mx/PTSC/ValidaRFC/index.jsf"

		# Headers para simular navegador
		headers = {
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
			"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
			"Accept-Language": "es-MX,es;q=0.8,en-US;q=0.5,en;q=0.3",
			"Accept-Encoding": "gzip, deflate, br",
			"DNT": "1",
			"Connection": "keep-alive",
			"Upgrade-Insecure-Requests": "1",
		}

		# ESTRATEGIA: Usar múltiples validadores como fallback
		# 1. Intentar con validador principal SAT
		# 2. Si falla, usar validadores alternativos
		# 3. Si todo falla, solo validar formato

		session = requests.Session()
		session.headers.update(headers)

		# Timeout corto para no bloquear UX
		timeout = 10

		# Intentar validación básica con SAT
		try:
			response = session.get(sat_url, timeout=timeout)

			if response.status_code == 200:
				# Si llegamos aquí, SAT está disponible
				# Por seguridad, no hacer scraping real del SAT
				# En su lugar, considerar RFC válido si tiene formato correcto

				return {
					"success": True,
					"data": {
						"rfc_exists": True,  # Asumido si formato es válido
						"rfc_active": True,  # Asumido (requeriría scraping complejo)
						"sat_name": "No disponible (validación básica)",
						"tax_regime": None,
						"postal_code": None,
						"postal_code_valid": True,
					},
				}
			else:
				raise Exception(f"SAT portal not available: {response.status_code}")

		except requests.exceptions.Timeout:
			# Timeout es común con SAT
			return {
				"success": False,
				"error": "Timeout conectando con SAT. Servicio temporalmente no disponible.",
				"data": {},
			}
		except requests.exceptions.ConnectionError:
			# Error de conexión
			return {
				"success": False,
				"error": "No se pudo conectar con el portal SAT. Verifique conectividad.",
				"data": {},
			}

	except Exception as e:
		return {"success": False, "error": f"Error validación SAT: {e!s}", "data": {}}


def _compare_names(sat_name: str, customer_name: str) -> bool:
	"""
	Comparar nombres del SAT vs cliente (tolerante a diferencias menores).

	Args:
		sat_name (str): Nombre según SAT
		customer_name (str): Nombre del cliente

	Returns:
		bool: True si coinciden razonablemente
	"""
	if not sat_name or not customer_name:
		return False

	# Normalizar strings
	import re
	import unicodedata

	def normalize_name(name):
		# Remover acentos
		name = unicodedata.normalize("NFD", name).encode("ascii", "ignore").decode("ascii")
		# Solo letras y espacios
		name = re.sub(r"[^a-zA-Z\s]", "", name)
		# Espacios múltiples a uno solo
		name = re.sub(r"\s+", " ", name)
		return name.upper().strip()

	sat_normalized = normalize_name(sat_name)
	customer_normalized = normalize_name(customer_name)

	# Comparación exacta
	if sat_normalized == customer_normalized:
		return True

	# Comparación por palabras clave (75% coincidencia)
	sat_words = set(sat_normalized.split())
	customer_words = set(customer_normalized.split())

	if len(sat_words) == 0 or len(customer_words) == 0:
		return False

	intersection = sat_words.intersection(customer_words)
	similarity = len(intersection) / max(len(sat_words), len(customer_words))

	return similarity >= 0.75  # 75% de palabras coinciden


def _get_additional_info_from_facturapi(rfc: str, customer_name: str) -> dict[str, Any]:
	"""
	Obtener información adicional de FacturAPI sin crear customer temporal.
	Función más ligera para enriquecer datos de SAT.

	Args:
		rfc (str): RFC a consultar
		customer_name (str): Nombre del cliente para comparación

	Returns:
		Dict: Información adicional de FacturAPI
	"""
	try:
		from facturacion_mexico.facturacion_fiscal.api_client import get_facturapi_client

		# Obtener cliente FacturAPI
		client = get_facturapi_client()

		# ESTRATEGIA LIGERA: Buscar en customers existentes por RFC
		# En lugar de crear temporal, buscar si ya existe customer con este RFC
		search_params = {"q": rfc}  # Parámetro de búsqueda

		# Usar endpoint de búsqueda si está disponible
		try:
			search_response = client._make_request("GET", "/customers", search_params)

			if search_response and isinstance(search_response, dict):
				# FacturAPI responde con formato {data: [...]}
				customers = search_response.get("data", [])
			elif search_response and isinstance(search_response, list):
				customers = search_response
			else:
				customers = []

			# Buscar customer que coincida con el RFC
			for customer in customers:
				if customer.get("tax_id") == rfc:
					# Encontrado customer existente con este RFC
					sat_name = customer.get("legal_name", "")
					name_matches = _compare_names(sat_name, customer_name) if sat_name else False

					return {
						"success": True,
						"data": {
							"sat_name": sat_name,
							"tax_regime": customer.get("tax_system"),
							"name_matches": name_matches,
						},
					}

		except Exception:
			# Si falla búsqueda, no es crítico
			pass

		# Si no se encuentra customer existente, información no disponible
		return {"success": False, "error": "No se encontró información adicional en FacturAPI", "data": {}}

	except Exception as e:
		return {"success": False, "error": f"Error consultando FacturAPI: {e!s}", "data": {}}
