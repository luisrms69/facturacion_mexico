"""
APIs para Validaciones SAT México - Sprint 2
Sistema de validación con cache inteligente
"""

import re
from datetime import datetime

import frappe
from frappe import _


def bulk_validate_customers():
	"""Validar clientes en lote - scheduled task."""
	try:
		frappe.logger().info("Ejecutando validación en lote de clientes...")
		# TODO: Implementar lógica real cuando esté disponible
		return {"status": "success", "message": "Validación completada (placeholder)"}
	except Exception as e:
		frappe.log_error(f"Error en validación de clientes: {e}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def validate_rfc(rfc, use_cache=True):
	"""
	Validar RFC con SAT usando cache inteligente.

	Args:
		rfc (str): RFC a validar
		use_cache (bool): Si usar cache o forzar validación nueva

	Returns:
		dict: Resultado de la validación
	"""
	try:
		if not rfc:
			return {"success": False, "message": _("RFC es requerido")}

		# Normalizar RFC
		fm_rfc = rfc.upper().strip()

		# Validar formato básico
		if not _is_valid_rfc_format(fm_rfc):
			return {"success": False, "valid": False, "message": _("Formato de RFC inválido"), "fm_rfc": rfc}

		# Buscar en cache si está habilitado
		if use_cache:
			cached_result = _get_cached_rfc_validation(rfc)
			if cached_result:
				return cached_result

		# Validar con API externa
		validation_result = _validate_rfc_with_external_api(rfc)

		# Guardar en cache
		if validation_result.get("success"):
			_cache_rfc_validation(rfc, validation_result)

		return validation_result

	except Exception as e:
		frappe.log_error(message=str(e), title="RFC Validation API Error")
		return {"success": False, "message": _("Error interno validando RFC: {0}").format(str(e))}


@frappe.whitelist()
def validate_customer_rfc_with_facturapi(customer_name):
	"""
	Validar RFC de Customer con FacturAPI incluyendo verificación de dirección.
	Actualiza los campos fm_rfc_validated y fm_rfc_validation_date del Customer.

	Args:
		customer_name (str): Nombre del Customer a validar

	Returns:
		dict: Resultado completo de la validación
	"""
	try:
		if not customer_name:
			return {"success": False, "error": "Customer name is required", "data": None}

		# Obtener Customer
		customer_doc = frappe.get_doc("Customer", customer_name)
		rfc = customer_doc.get("tax_id") or ""

		if not rfc:
			return {"success": False, "error": "Customer no tiene RFC configurado en Tax ID", "data": None}

		# Resultado de validación
		validation_result = {
			"customer": customer_name,
			"customer_name": customer_doc.customer_name,
			"rfc": rfc,
			"rfc_format_valid": False,
			"address_configured": False,
			"address_valid_for_facturapi": False,
			"postal_code_format_valid": False,
			"rfc_exists_in_sat": False,
			"rfc_active_in_sat": False,
			"sat_name": None,
			"name_matches": False,
			"validation_successful": False,
			"warnings": [],
			"recommendations": [],
		}

		# 1. VALIDAR FORMATO RFC
		if not _is_valid_rfc_format(rfc):
			validation_result["recommendations"].append(
				f"RFC '{rfc}' tiene formato inválido. Debe ser formato RFC mexicano válido."
			)
			return {"success": True, "data": validation_result}

		validation_result["rfc_format_valid"] = True

		# 2. VALIDAR DIRECCIÓN REQUERIDA PARA FACTURAPI
		primary_address = _get_customer_primary_address(customer_doc)

		if not primary_address:
			validation_result["recommendations"].append(
				"Customer necesita dirección primaria configurada. "
				"Ir a Customer → Addresses → Agregar dirección marcada como 'Primary Address'."
			)
			return {"success": True, "data": validation_result}

		validation_result["address_configured"] = True

		# Validar que la dirección tenga campos requeridos para FacturAPI
		required_address_fields = {
			"address_line1": "Dirección Línea 1",
			"city": "Ciudad",
			"state": "Estado",
			"country": "País",
			"pincode": "Código Postal",
		}
		missing_fields = []

		for field, label in required_address_fields.items():
			if not primary_address.get(field) or str(primary_address.get(field)).strip() == "":
				missing_fields.append(label)

		if missing_fields:
			validation_result["warnings"].append(
				f"Dirección incompleta. Campos faltantes: {', '.join(missing_fields)}"
			)
			validation_result["recommendations"].append(
				f"Para validar RFC con SAT/FacturAPI necesita completar la dirección primaria del Customer: {', '.join(missing_fields)}. "
				"Ir a Customer → Addresses → Editar dirección principal."
			)
			return {"success": True, "data": validation_result}

		validation_result["address_valid_for_facturapi"] = True

		# Validar formato de código postal mexicano
		postal_code = primary_address.get("pincode", "").strip()
		if _is_valid_postal_code_format(postal_code):
			validation_result["postal_code_format_valid"] = True
		else:
			validation_result["warnings"].append(
				f"Código postal '{postal_code}' no tiene formato válido (debe ser 5 dígitos)"
			)
			validation_result["recommendations"].append(
				"Corregir el código postal en la dirección principal: debe tener exactamente 5 dígitos numéricos."
			)

		# 3. VALIDAR RFC CON FACTURAPI
		facturapi_result = _validate_rfc_with_facturapi_full(rfc, customer_doc, primary_address)

		if not facturapi_result["success"]:
			# Verificar diferentes tipos de errores de FacturAPI
			error_msg = facturapi_result.get("error", "")

			if "nombre o razón social del receptor no coincide" in error_msg.lower():
				# RFC existe y está activo, solo el nombre no coincide
				validation_result["validation_error"] = error_msg
				validation_result["rfc_exists_in_sat"] = True
				validation_result["rfc_active_in_sat"] = True
				validation_result["sat_name"] = "Consultar constancia SAT"
				validation_result["name_matches"] = False
			elif "domiciliofiscalreceptor" in error_msg.lower():
				# RFC existe y está activo, nombre SÍ coincide, pero código postal no coincide con SAT
				validation_result["validation_error"] = error_msg
				validation_result["rfc_exists_in_sat"] = True
				validation_result["rfc_active_in_sat"] = True
				validation_result["sat_name"] = "Verificado en SAT"
				validation_result["name_matches"] = True  # Nombre sí coincide en este caso
				validation_result["address_matches"] = False  # NUEVO: dirección no coincide
			else:
				# Error real - RFC no existe o está inactivo
				validation_result["validation_error"] = error_msg
				validation_result["rfc_exists_in_sat"] = False
				validation_result["rfc_active_in_sat"] = False
				validation_result["sat_name"] = None
				validation_result["name_matches"] = False
		else:
			# Procesar resultado exitoso de FacturAPI
			facturapi_data = facturapi_result["data"]
			validation_result.update(
				{
					"rfc_exists_in_sat": facturapi_data.get("rfc_exists", False),
					"rfc_active_in_sat": facturapi_data.get("rfc_active", False),
					"sat_name": facturapi_data.get("sat_name"),
					"name_matches": facturapi_data.get("name_matches", False),
				}
			)

		# 4. DETERMINAR SI VALIDACIÓN ES EXITOSA
		# La validación es exitosa si completamos el proceso, independientemente del resultado SAT
		validation_successful = (
			validation_result["rfc_format_valid"] and validation_result["address_valid_for_facturapi"]
		)

		# Si no existe en SAT, es información válida, no un error
		if not validation_result["rfc_exists_in_sat"]:
			validation_result["warnings"].append(
				"Este RFC no está registrado en el SAT o no está activo. "
				"Esto puede ser normal para RFCs nuevos o inactivos."
			)

		validation_result["validation_successful"] = validation_successful

		# 5. ACTUALIZAR CUSTOMER CON RESULTADOS
		# Solo marcar como validado si el RFC existe, está activo, el nombre coincide Y la dirección coincide
		rfc_is_valid_in_sat = (
			validation_result["rfc_exists_in_sat"]
			and validation_result["rfc_active_in_sat"]
			and validation_result["name_matches"]
			and validation_result.get("address_matches")
			is not False  # Solo es válido si address_matches no es False
		)

		try:
			customer_updates = {}

			if rfc_is_valid_in_sat:
				# RFC válido en SAT - marcar como validado
				customer_updates["fm_rfc_validated"] = 1
				customer_updates["fm_rfc_validation_date"] = frappe.utils.today()
			else:
				# RFC no válido en SAT - limpiar validación anterior si existe
				customer_updates["fm_rfc_validated"] = 0
				customer_updates["fm_rfc_validation_date"] = None

			frappe.db.set_value("Customer", customer_name, customer_updates)
			frappe.db.commit()

			validation_result["customer_updated"] = True

		except Exception as e:
			frappe.log_error(f"Error updating Customer {customer_name}: {e!s}", "Customer RFC Update Error")
			validation_result["warnings"].append(f"Error actualizando Customer: {e!s}")

		# 6. GENERAR RECOMENDACIONES FINALES
		if not validation_result["name_matches"] and validation_result["sat_name"]:
			validation_result["recommendations"].append(
				f"Nombre en SAT ('{validation_result['sat_name']}') no coincide exactamente "
				f"con nombre del Customer ('{customer_doc.customer_name}'). "
				"Verificar que coincidan para evitar problemas de timbrado."
			)

		if rfc_is_valid_in_sat:
			validation_result["recommendations"].append(
				"✅ RFC completamente válido: existe en SAT, está activo, nombre y dirección coinciden. Customer listo para facturación."
			)
		elif validation_result["rfc_exists_in_sat"] and validation_result["rfc_active_in_sat"]:
			if not validation_result["name_matches"]:
				validation_result["recommendations"].append(
					"⚠️ RFC existe en SAT pero el nombre no coincide exactamente. "
					"Actualizar nombre del Customer para que coincida con el registro SAT."
				)
			elif not validation_result.get("address_matches"):
				validation_result["recommendations"].append(
					"⚠️ RFC y nombre válidos en SAT pero el código postal no coincide con el registro fiscal. "
					"Verificar y corregir el código postal en la dirección del Customer."
				)
		else:
			validation_result["recommendations"].append(
				"❌ RFC no está registrado o activo en SAT. Verificar que el RFC sea correcto."
			)

		return {"success": True, "data": validation_result}

	except frappe.DoesNotExistError:
		return {"success": False, "error": f"Customer '{customer_name}' not found", "data": None}
	except Exception as e:
		frappe.log_error(
			f"Error validating Customer RFC for {customer_name}: {e!s}", "Customer RFC Validation Error"
		)
		return {"success": False, "error": f"Error validating Customer RFC: {e!s}", "data": None}


@frappe.whitelist()
def validate_lista_69b(rfc, use_cache=True):
	"""
	Validar si RFC está en Lista 69B (Contribuyentes no localizados).

	Args:
		rfc (str): RFC a validar
		use_cache (bool): Si usar cache o forzar validación nueva

	Returns:
		dict: Resultado de la validación
	"""
	try:
		if not rfc:
			return {"success": False, "message": _("RFC es requerido")}

		# Normalizar RFC
		fm_rfc = rfc.upper().strip()

		# Buscar en cache si está habilitado
		if use_cache:
			cached_result = _get_cached_lista_69b_validation(fm_rfc)
			if cached_result:
				return cached_result

		# Validar con API externa
		validation_result = _validate_lista_69b_with_external_api(rfc)

		# Guardar en cache
		if validation_result.get("success"):
			_cache_lista_69b_validation(rfc, validation_result)

		return validation_result

	except Exception as e:
		frappe.log_error(message=str(e), title="Lista 69B Validation API Error")
		return {"success": False, "message": _("Error interno validando Lista 69B: {0}").format(str(e))}


@frappe.whitelist()
def bulk_validate_rfc(rfc_list):
	"""
	Validar múltiples RFCs en lote.

	Args:
		rfc_list (str): Lista de RFCs separados por coma

	Returns:
		dict: Resultados de validación en lote
	"""
	try:
		if not rfc_list:
			return {"success": False, "message": _("Lista de RFCs es requerida")}

		# Procesar lista
		if isinstance(rfc_list, str):
			rfcs = [rfc.strip().upper() for rfc in rfc_list.split(",")]
		else:
			rfcs = rfc_list

		results = []
		for rfc in rfcs:
			if rfc:  # Evitar RFCs vacíos
				result = validate_rfc(rfc, use_cache=True)
				results.append(
					{
						"fm_rfc": rfc,
						"valid": result.get("valid", False),
						"message": result.get("message", ""),
						"status": result.get("status", ""),
					}
				)

		return {"success": True, "total_processed": len(results), "results": results}

	except Exception as e:
		frappe.log_error(message=str(e), title="Bulk RFC Validation API Error")
		return {"success": False, "message": _("Error interno en validación masiva: {0}").format(str(e))}


@frappe.whitelist()
def get_cache_stats():
	"""
	Obtener estadísticas del cache SAT.

	Returns:
		dict: Estadísticas del cache
	"""
	try:
		# Estadísticas generales
		total_cache = frappe.db.count("SAT Validation Cache")
		active_cache = frappe.db.count("SAT Validation Cache", {"is_active": 1})
		expired_cache = frappe.db.count("SAT Validation Cache", {"is_active": 0})

		# Estadísticas por tipo
		rfc_cache = frappe.db.count("SAT Validation Cache", {"validation_type": "rfc_validation"})
		lista69b_cache = frappe.db.count("SAT Validation Cache", {"validation_type": "lista_69b"})

		# Cache más antiguos
		oldest_cache = frappe.db.sql(
			"""
			SELECT validation_key, validated_at, expires_at
			FROM `tabSAT Validation Cache`
			WHERE is_active = 1
			ORDER BY validated_at ASC
			LIMIT 5
		""",
			as_dict=True,
		)

		# Cache que expiran pronto
		expiring_soon = frappe.db.sql(
			"""
			SELECT validation_key, expires_at, validation_type
			FROM `tabSAT Validation Cache`
			WHERE is_active = 1
			AND expires_at <= DATE_ADD(CURDATE(), INTERVAL 3 DAY)
			ORDER BY expires_at ASC
			LIMIT 10
		""",
			as_dict=True,
		)

		return {
			"success": True,
			"stats": {
				"total_entries": total_cache,
				"active_entries": active_cache,
				"expired_entries": expired_cache,
				"rfc_validations": rfc_cache,
				"lista_69b_validations": lista69b_cache,
				"oldest_cache": oldest_cache,
				"expiring_soon": expiring_soon,
			},
		}

	except Exception as e:
		frappe.log_error(message=str(e), title="Cache Stats API Error")
		return {"success": False, "message": _("Error obteniendo estadísticas del cache: {0}").format(str(e))}


@frappe.whitelist()
def cleanup_expired_cache(days_to_keep=90):
	"""
	Limpiar cache expirado más antiguo que X días.

	Args:
		days_to_keep (int): Días de cache expirado a mantener

	Returns:
		dict: Resultado de la limpieza
	"""
	try:
		from facturacion_mexico.validaciones.doctype.sat_validation_cache.sat_validation_cache import (
			SATValidationCache,
		)

		# Ejecutar limpieza
		deleted_count = SATValidationCache.cleanup_expired_caches(int(days_to_keep))

		# Desactivar caches expirados
		SATValidationCache.deactivate_expired_caches()

		return {
			"success": True,
			"deleted_entries": deleted_count,
			"message": _("Cache limpiado exitosamente. {0} registros eliminados.").format(deleted_count),
		}

	except Exception as e:
		frappe.log_error(message=str(e), title="Cache Cleanup API Error")
		return {"success": False, "message": _("Error limpiando cache: {0}").format(str(e))}


@frappe.whitelist()
def force_refresh_cache(validation_key, validation_type):
	"""
	Forzar actualización de un cache específico.

	Args:
		validation_key (str): Key del cache a refrescar
		validation_type (str): Tipo de validación

	Returns:
		dict: Resultado de la actualización
	"""
	try:
		# Desactivar cache actual
		frappe.db.sql(
			"""
			UPDATE `tabSAT Validation Cache`
			SET is_active = 0
			WHERE validation_key = %s AND validation_type = %s
		""",
			(validation_key, validation_type),
		)

		# Crear nueva validación
		if validation_type == "rfc_validation":
			fm_rfc = validation_key.replace("RFC_", "")
			result = validate_rfc(fm_rfc, use_cache=False)
		elif validation_type == "lista_69b":
			fm_rfc = validation_key.replace("L69B_", "")
			result = validate_lista_69b(fm_rfc, use_cache=False)
		else:
			return {
				"success": False,
				"message": _("Tipo de validación no soportado: {0}").format(validation_type),
			}

		return {"success": True, "message": _("Cache actualizado exitosamente"), "validation_result": result}

	except Exception as e:
		frappe.log_error(message=str(e), title="Force Refresh Cache API Error")
		return {"success": False, "message": _("Error actualizando cache: {0}").format(str(e))}


# ═══════════════════════════════════════════════════════════════════
# FUNCIONES HELPER PRIVADAS
# ═══════════════════════════════════════════════════════════════════


def _is_valid_rfc_format(rfc):
	"""
	Validar formato básico de RFC.

	Args:
		rfc (str): RFC a validar

	Returns:
		bool: True si el formato es válido
	"""
	if not rfc:
		return False

	# RFC persona física: 4 letras + 6 dígitos + 3 caracteres
	# RFC persona moral: 3 letras + 6 dígitos + 3 caracteres
	rfc_pattern = r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$"

	return bool(re.match(rfc_pattern, rfc.upper()))


def _is_valid_postal_code_format(postal_code):
	"""
	Validar formato de código postal mexicano.

	Args:
		postal_code (str): Código postal a validar

	Returns:
		bool: True si el formato es válido (5 dígitos)
	"""
	if not postal_code:
		return False

	postal_code_str = str(postal_code).strip()

	# Debe tener exactamente 5 caracteres y ser todos dígitos
	return len(postal_code_str) == 5 and postal_code_str.isdigit()


def _get_cached_rfc_validation(rfc):
	"""
	Obtener validación RFC desde cache.

	Args:
		rfc (str): RFC a buscar

	Returns:
		dict: Resultado del cache o None
	"""
	try:
		from facturacion_mexico.validaciones.doctype.sat_validation_cache.sat_validation_cache import (
			SATValidationCache,
		)

		cache_key = f"RFC_{rfc}"
		cached_result = SATValidationCache.get_valid_cache(cache_key, "rfc_validation")

		if cached_result:
			result_data = frappe.parse_json(cached_result.get("result_data", "{}"))
			return {
				"success": True,
				"valid": result_data.get("valid", False),
				"status": result_data.get("status", ""),
				"message": result_data.get("message", ""),
				"fm_rfc": rfc,
				"cached": True,
				"cache_date": cached_result.get("validated_at"),
				"expires_at": cached_result.get("expires_at"),
			}

		return None

	except Exception as e:
		frappe.log_error(message=str(e), title="Get Cached RFC Validation Error")
		return None


def _get_cached_lista_69b_validation(rfc):
	"""
	Obtener validación Lista 69B desde cache.

	Args:
		rfc (str): RFC a buscar

	Returns:
		dict: Resultado del cache o None
	"""
	try:
		from facturacion_mexico.validaciones.doctype.sat_validation_cache.sat_validation_cache import (
			SATValidationCache,
		)

		cache_key = f"L69B_{rfc}"
		cached_result = SATValidationCache.get_valid_cache(cache_key, "lista_69b")

		if cached_result:
			result_data = frappe.parse_json(cached_result.get("result_data", "{}"))
			return {
				"success": True,
				"in_lista_69b": result_data.get("in_lista_69b", False),
				"status": result_data.get("status", ""),
				"message": result_data.get("message", ""),
				"fm_rfc": rfc,
				"cached": True,
				"cache_date": cached_result.get("validated_at"),
				"expires_at": cached_result.get("expires_at"),
			}

		return None

	except Exception as e:
		frappe.log_error(message=str(e), title="Get Cached Lista 69B Validation Error")
		return None


def _validate_rfc_with_external_api(rfc):
	"""
	Validar RFC con API externa (simulación).

	Args:
		rfc (str): RFC a validar

	Returns:
		dict: Resultado de la validación
	"""
	try:
		# TODO: Implementar integración real con API SAT
		# Por ahora simular validación

		# Simular algunos RFCs inválidos
		invalid_rfcs = ["XAXX010101000", "XXXX010101XXX"]

		if rfc in invalid_rfcs:
			return {
				"success": True,
				"valid": False,
				"status": "Inactivo",
				"message": _("RFC no válido según SAT"),
				"fm_rfc": rfc,
				"api_response": {"codigo": "404", "mensaje": "RFC no encontrado"},
			}
		else:
			return {
				"success": True,
				"valid": True,
				"status": "Activo",
				"message": _("RFC válido según SAT"),
				"fm_rfc": rfc,
				"api_response": {
					"codigo": "200",
					"mensaje": "RFC válido",
					"fecha_actualizacion": datetime.now().isoformat(),
				},
			}

	except Exception as e:
		frappe.log_error(message=str(e), title="External RFC API Validation Error")
		return {"success": False, "message": _("Error consultando API externa: {0}").format(str(e))}


def _validate_lista_69b_with_external_api(rfc):
	"""
	Validar RFC contra Lista 69B con API externa (simulación).

	Args:
		rfc (str): RFC a validar

	Returns:
		dict: Resultado de la validación
	"""
	try:
		# TODO: Implementar integración real con Lista 69B SAT
		# Por ahora simular validación

		# Simular algunos RFCs en lista 69B
		lista_69b_rfcs = ["TEST010101ABC", "PROB010101XYZ"]

		in_lista = rfc in lista_69b_rfcs

		return {
			"success": True,
			"in_lista_69b": in_lista,
			"status": "En Lista" if in_lista else "No encontrado",
			"message": _("RFC {'en' if in_lista else 'NO en'} Lista 69B").format(**locals()),
			"fm_rfc": rfc,
			"api_response": {
				"codigo": "200",
				"en_lista": in_lista,
				"fecha_consulta": datetime.now().isoformat(),
			},
		}

	except Exception as e:
		frappe.log_error(message=str(e), title="External Lista 69B API Validation Error")
		return {"success": False, "message": _("Error consultando Lista 69B: {0}").format(str(e))}


def _cache_rfc_validation(rfc, validation_result):
	"""
	Guardar resultado de validación RFC en cache.

	Args:
		rfc (str): RFC validado
		validation_result (dict): Resultado a cachear
	"""
	try:
		from facturacion_mexico.validaciones.doctype.sat_validation_cache.sat_validation_cache import (
			SATValidationCache,
		)

		cache_key = f"RFC_{rfc}"

		SATValidationCache.create_cache_record(
			validation_key=cache_key,
			validation_type="rfc_validation",
			result_data=validation_result,
			source_system="SAT_API",
		)

	except Exception as e:
		frappe.log_error(message=str(e), title="Cache RFC Validation Error")


def _cache_lista_69b_validation(rfc, validation_result):
	"""
	Guardar resultado de validación Lista 69B en cache.

	Args:
		rfc (str): RFC validado
		validation_result (dict): Resultado a cachear
	"""
	try:
		from facturacion_mexico.validaciones.doctype.sat_validation_cache.sat_validation_cache import (
			SATValidationCache,
		)

		cache_key = f"L69B_{rfc}"

		SATValidationCache.create_cache_record(
			validation_key=cache_key,
			validation_type="lista_69b",
			result_data=validation_result,
			source_system="SAT_LISTA_69B_API",
		)

	except Exception as e:
		frappe.log_error(message=str(e), title="Cache Lista 69B Validation Error")


# ═══════════════════════════════════════════════════════════════════
# FUNCIONES HELPER PARA VALIDACIÓN CUSTOMER RFC
# ═══════════════════════════════════════════════════════════════════


def _get_customer_primary_address(customer_doc):
	"""
	Obtener dirección primaria del Customer.

	Args:
		customer_doc: Document de Customer

	Returns:
		dict: Dirección primaria o None
	"""
	try:
		# Buscar dirección principal
		primary_address = frappe.db.sql(
			"""
			SELECT addr.name, addr.address_line1, addr.address_line2, addr.city,
			       addr.state, addr.country, addr.pincode, addr.email_id
			FROM `tabAddress` addr
			INNER JOIN `tabDynamic Link` dl ON dl.parent = addr.name
			WHERE dl.link_doctype = 'Customer'
			AND dl.link_name = %s
			AND addr.is_primary_address = 1
			AND addr.disabled = 0
			LIMIT 1
		""",
			customer_doc.name,
			as_dict=True,
		)

		if primary_address:
			return primary_address[0]

		# Si no hay primaria, buscar cualquier dirección activa
		any_address = frappe.db.sql(
			"""
			SELECT addr.name, addr.address_line1, addr.address_line2, addr.city,
			       addr.state, addr.country, addr.pincode, addr.email_id
			FROM `tabAddress` addr
			INNER JOIN `tabDynamic Link` dl ON dl.parent = addr.name
			WHERE dl.link_doctype = 'Customer'
			AND dl.link_name = %s
			AND addr.disabled = 0
			LIMIT 1
		""",
			customer_doc.name,
			as_dict=True,
		)

		if any_address:
			frappe.logger().warning(
				f"Customer {customer_doc.name} no tiene dirección primaria. Usando primera dirección disponible."
			)
			return any_address[0]

		return None

	except Exception as e:
		frappe.log_error(
			f"Error obteniendo dirección del Customer {customer_doc.name}: {e!s}", "Get Address Error"
		)
		return None


def _validate_rfc_with_facturapi_full(rfc, customer_doc, primary_address):
	"""
	Validar RFC con FacturAPI usando datos reales del Customer.
	Versión simplificada y robusta que crea customer temporal, valida y borra.

	Args:
		rfc (str): RFC a validar
		customer_doc: Document de Customer
		primary_address (dict): Dirección primaria del Customer

	Returns:
		dict: Resultado de validación FacturAPI
	"""
	try:
		from facturacion_mexico.facturacion_fiscal.api_client import get_facturapi_client

		# Obtener cliente FacturAPI
		client = get_facturapi_client()

		# Determinar tax_system según tipo de RFC
		# RFC 13 caracteres = Persona Física, RFC 12 caracteres = Persona Moral
		is_persona_fisica = len(rfc) == 13
		tax_system = (
			"605" if is_persona_fisica else "601"
		)  # 605=Sueldos y Salarios, 601=General Ley Personas Morales

		# Normalizar nombre para FacturAPI (sin acentos, sin régimen societario, mayúsculas)
		normalized_name = _normalize_company_name_for_facturapi(customer_doc.customer_name)

		# Construir datos del customer temporal usando datos REALES
		temp_customer_data = {
			"legal_name": normalized_name,
			"tax_id": rfc,
			"tax_system": tax_system,
			"email": customer_doc.email_id or primary_address.get("email_id") or "temp@validation.com",
			"address": {
				"street": primary_address.get("address_line1") or "Sin especificar",
				"exterior": primary_address.get("address_line2") or "S/N",
				"neighborhood": "Centro",  # No siempre disponible en ERPNext
				"city": primary_address.get("city") or "Sin especificar",
				"municipality": primary_address.get("city") or "Sin especificar",
				"state": primary_address.get("state") or "Sin especificar",
				"country": _normalize_country_code(primary_address.get("country")),
				"zip": primary_address.get("pincode") or "00000",
			},
		}

		# PASO 1: Crear customer temporal en FacturAPI
		# Usar método silencioso para evitar frappe.throw()
		try:
			temp_customer_response = client._make_request_silent("POST", "/customers", temp_customer_data)
		except Exception as e:
			return {"success": False, "error": str(e), "data": {}}

		if not temp_customer_response or "id" not in temp_customer_response:
			return {"success": False, "error": "No se pudo crear customer temporal en FacturAPI", "data": {}}

		customer_id = temp_customer_response["id"]

		try:
			# PASO 2: Validar información fiscal con SAT
			validation_response = client.validate_customer_tax_info(customer_id)

			# PASO 3: Procesar respuesta de validación
			if validation_response:
				# Extraer información real del SAT
				sat_name = "No disponible"

				if isinstance(validation_response, dict):
					sat_name = (
						validation_response.get("legal_name")
						or validation_response.get("name")
						or temp_customer_response.get("legal_name")
						or "Nombre no disponible"
					)

				# Comparar nombres - usar el nombre normalizado que se envió a FacturAPI
				name_matches = _compare_customer_names(sat_name, normalized_name)

				return {
					"success": True,
					"data": {
						"rfc_exists": True,
						"rfc_active": True,
						"sat_name": sat_name,
						"name_matches": name_matches,
						"validation_response": validation_response,
					},
				}
			else:
				return {
					"success": False,
					"error": "RFC no válido según FacturAPI",
					"data": {"rfc_exists": False, "rfc_active": False},
				}

		finally:
			# PASO 4: Eliminar customer temporal (siempre)
			try:
				client.delete_customer(customer_id)
			except Exception as cleanup_error:
				frappe.log_error(
					f"Could not delete temp customer {customer_id}: {cleanup_error!s}",
					"FacturAPI Cleanup Warning",
				)

	except Exception as e:
		error_message = str(e)

		# Manejar errores específicos de FacturAPI
		if "nombre o razón social del receptor no coincide" in error_message.lower():
			return {
				"success": True,  # RFC válido pero nombre no coincide
				"data": {
					"rfc_exists": True,
					"rfc_active": True,
					"sat_name": "Verificar en constancia SAT",
					"name_matches": False,
					"validation_error": error_message,  # Incluir mensaje completo
				},
			}
		elif (
			"tax_id" in error_message.lower()
			or "rfc" in error_message.lower()
			or "no existe en la lista" in error_message.lower()
		):
			return {
				"success": True,  # RFC inválido pero manejamos en modal
				"data": {
					"rfc_exists": False,
					"rfc_active": False,
					"sat_name": None,
					"name_matches": False,
					"validation_error": error_message,  # Incluir mensaje específico
				},
			}

		# Para errores generales, devolver error específico SIN propagar
		return {
			"success": False,
			"error": error_message,  # Solo el mensaje, sin "Error FacturAPI:"
			"data": {},
		}


def _compare_customer_names(sat_name, customer_name):
	"""
	Comparar nombres del SAT vs Customer (tolerante a diferencias menores).

	Args:
		sat_name (str): Nombre según SAT
		customer_name (str): Nombre del Customer

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


def _normalize_company_name_for_facturapi(company_name):
	"""
	Normalizar nombre de empresa para FacturAPI según CFDI 4.0.
	- Sin acentos
	- Sin régimen societario
	- En mayúsculas

	Args:
		company_name (str): Nombre original de la empresa

	Returns:
		str: Nombre normalizado para FacturAPI
	"""
	if not company_name:
		return ""

	# Normalizar a mayúsculas
	normalized = company_name.upper()

	# Remover acentos y caracteres especiales
	accent_map = {
		"Á": "A",
		"É": "E",
		"Í": "I",
		"Ó": "O",
		"Ú": "U",
		"Ñ": "N",
		"á": "A",
		"é": "E",
		"í": "I",
		"ó": "O",
		"ú": "U",
		"ñ": "N",
	}

	for accented, plain in accent_map.items():
		normalized = normalized.replace(accented, plain)

	# Remover regímenes societarios comunes
	regimes_to_remove = [
		", S.A. DE C.V.",
		", S.A.B. DE C.V.",
		", S. DE R.L. DE C.V.",
		", S.C.",
		", A.C.",
		" S.A. DE C.V.",
		" S.A.B. DE C.V.",
		" S. DE R.L. DE C.V.",
		" S.C.",
		" A.C.",
		", SA DE CV",
		", SAB DE CV",
		", S DE RL DE CV",
		" SA DE CV",
		" SAB DE CV",
		" S DE RL DE CV",
	]

	for regime in regimes_to_remove:
		if normalized.endswith(regime):
			normalized = normalized[: -len(regime)]
			break

	# Limpiar espacios extra
	normalized = " ".join(normalized.split())

	return normalized


def _normalize_country_code(country):
	"""
	Normalizar código de país para FacturAPI (requiere 3 caracteres ISO).

	Args:
		country (str): País desde ERPNext

	Returns:
		str: Código de país de 3 caracteres para FacturAPI
	"""
	if not country:
		return "MEX"  # Default México

	# Mapeo de nombres/códigos comunes a códigos ISO 3166-1 alpha-3
	country_mapping = {
		# Nombres en español
		"México": "MEX",
		"Mexico": "MEX",
		"méxico": "MEX",
		"mexico": "MEX",
		"Estados Unidos": "USA",
		"United States": "USA",
		"Canada": "CAN",
		"Canadá": "CAN",
		"España": "ESP",
		"Spain": "ESP",
		# Códigos ISO alpha-2 a alpha-3
		"MX": "MEX",
		"US": "USA",
		"CA": "CAN",
		"ES": "ESP",
		"GB": "GBR",
		"FR": "FRA",
		"DE": "DEU",
		"IT": "ITA",
		"JP": "JPN",
		"CN": "CHN",
		"BR": "BRA",
		"AR": "ARG",
		"CL": "CHL",
		"CO": "COL",
		"PE": "PER",
		# Códigos ya correctos (3 caracteres)
		"MEX": "MEX",
		"USA": "USA",
		"CAN": "CAN",
		"ESP": "ESP",
		"GBR": "GBR",
		"FRA": "FRA",
		"DEU": "DEU",
		"ITA": "ITA",
		"JPN": "JPN",
		"CHN": "CHN",
		"BRA": "BRA",
		"ARG": "ARG",
		"CHL": "CHL",
		"COL": "COL",
		"PER": "PER",
	}

	# Limpiar y buscar en mapeo
	country_clean = country.strip()

	if country_clean in country_mapping:
		return country_mapping[country_clean]

	# Si no encontramos mapeo y ya tiene 3 caracteres, mantener
	if len(country_clean) == 3 and country_clean.isupper():
		return country_clean

	# Default a México si no podemos mapear
	frappe.logger().warning(f"País '{country}' no mapeado, usando MEX por defecto")
	return "MEX"


# ═══════════════════════════════════════════════════════════════════
# SISTEMA DE VALIDACIÓN MASIVA AUTOMÁTICA
# ═══════════════════════════════════════════════════════════════════


def is_rfc_validation_expired(customer_name):
	"""
	Verificar si la validación RFC de un Customer ha expirado (>1 año).

	Args:
		customer_name (str): Nombre del Customer

	Returns:
		bool: True si la validación ha expirado o no existe
	"""
	try:
		customer_doc = frappe.get_doc("Customer", customer_name)

		# Si no está validado, considerar "expirado"
		if not customer_doc.get("fm_rfc_validated"):
			return True

		# Si no hay fecha de validación, considerar expirado
		validation_date = customer_doc.get("fm_rfc_validation_date")
		if not validation_date:
			return True

		# Calcular si han pasado más de 1 año
		from datetime import date, timedelta

		if isinstance(validation_date, str):
			validation_date = frappe.utils.getdate(validation_date)

		expiration_date = validation_date + timedelta(days=365)
		today = date.today()

		return today > expiration_date

	except Exception as e:
		frappe.log_error(
			f"Error checking RFC validation expiration for {customer_name}: {e!s}", "RFC Expiration Check"
		)
		return True  # En caso de error, considerar expirado para re-validar


def get_customers_needing_rfc_validation(limit=30):
	"""
	Obtener lista de Customers que necesitan validación RFC ordenados por prioridad.

	Args:
		limit (int): Máximo número de customers a retornar

	Returns:
		list: Lista de customers ordenados por prioridad
	"""
	try:
		# Query con priorización inteligente
		query = """
			SELECT
				c.name,
				c.customer_name,
				c.tax_id,
				c.fm_rfc_validated,
				c.fm_rfc_validation_date,
				COALESCE(c.fm_rfc_validated, 0) as is_validated,
				COALESCE(
					DATEDIFF(CURDATE(), c.fm_rfc_validation_date),
					9999
				) as days_since_validation,
				COUNT(si.name) as invoice_count,
				SUM(si.grand_total) as total_invoiced,
				MAX(si.posting_date) as last_invoice_date,

				-- Calcular prioridad
				CASE
					WHEN c.tax_id IS NULL OR c.tax_id = '' THEN 999  -- Sin RFC = baja prioridad
					WHEN COALESCE(c.fm_rfc_validated, 0) = 0 THEN 1  -- Sin validar = máxima prioridad
					WHEN c.fm_rfc_validation_date IS NULL THEN 1     -- Sin fecha = máxima prioridad
					WHEN DATEDIFF(CURDATE(), c.fm_rfc_validation_date) > 365 THEN 2  -- Expirado = alta prioridad
					ELSE 3  -- Validado y vigente = baja prioridad
				END as priority_level

			FROM `tabCustomer` c
			LEFT JOIN `tabSales Invoice` si ON si.customer = c.name
				AND si.docstatus = 1
				AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 2 YEAR)  -- Facturas últimos 2 años
			WHERE c.disabled = 0
				AND c.tax_id IS NOT NULL
				AND c.tax_id != ''
			GROUP BY c.name
			HAVING priority_level <= 2  -- Solo customers que necesitan validación
			ORDER BY
				priority_level ASC,           -- Prioridad principal
				invoice_count DESC,           -- Customers con más facturas primero
				total_invoiced DESC,          -- Customers con más facturación primero
				days_since_validation DESC,   -- Validaciones más antiguas primero
				last_invoice_date DESC        -- Customers más activos primero
			LIMIT %s
		"""

		customers = frappe.db.sql(query, (limit,), as_dict=True)

		# Enriquecer datos con información adicional
		for customer in customers:
			# Verificar si tiene dirección primaria
			customer["has_primary_address"] = bool(_get_customer_primary_address_exists(customer["name"]))

			# Determinar razón de validación
			if customer["priority_level"] == 1:
				if not customer["is_validated"]:
					customer["validation_reason"] = "Sin validar"
				else:
					customer["validation_reason"] = "Sin fecha de validación"
			elif customer["priority_level"] == 2:
				customer["validation_reason"] = f"Expirado ({customer['days_since_validation']} días)"
			else:
				customer["validation_reason"] = "Vigente"

		return customers

	except Exception as e:
		frappe.log_error(f"Error getting customers needing RFC validation: {e!s}", "Bulk RFC Validation")
		return []


def _get_customer_primary_address_exists(customer_name):
	"""
	Verificar si Customer tiene dirección primaria (versión optimizada).

	Args:
		customer_name (str): Nombre del Customer

	Returns:
		bool: True si tiene dirección primaria
	"""
	try:
		result = frappe.db.sql(
			"""
			SELECT 1
			FROM `tabAddress` addr
			INNER JOIN `tabDynamic Link` dl ON dl.parent = addr.name
			WHERE dl.link_doctype = 'Customer'
			AND dl.link_name = %s
			AND addr.is_primary_address = 1
			AND addr.disabled = 0
			LIMIT 1
		""",
			(customer_name,),
		)

		return bool(result)

	except Exception:
		return False


@frappe.whitelist()
def validate_customers_bulk(customer_names, max_validations_per_run=30):
	"""
	Validar múltiples customers en lote (para scheduled job).

	Args:
		customer_names (list): Lista de nombres de Customer a validar
		max_validations_per_run (int): Máximo validaciones por ejecución

	Returns:
		dict: Resumen de resultados de validación masiva
	"""
	try:
		if isinstance(customer_names, str):
			customer_names = frappe.parse_json(customer_names)

		if not isinstance(customer_names, list):
			return {"success": False, "error": "customer_names debe ser una lista"}

		# Limitar número de validaciones
		customer_names = customer_names[:max_validations_per_run]

		results = {
			"success": True,
			"total_requested": len(customer_names),
			"results": [],
			"summary": {
				"successful_validations": 0,
				"failed_validations": 0,
				"skipped_validations": 0,
				"customers_now_validated": 0,
				"errors": [],
			},
		}

		for customer_name in customer_names:
			try:
				# Validar customer individual
				validation_result = validate_customer_rfc_with_facturapi(customer_name)

				customer_result = {
					"customer": customer_name,
					"success": validation_result.get("success", False),
					"validation_successful": False,
					"error": None,
				}

				if validation_result.get("success") and validation_result.get("data"):
					data = validation_result["data"]
					customer_result.update(
						{
							"validation_successful": data.get("validation_successful", False),
							"rfc": data.get("rfc"),
							"sat_name": data.get("sat_name"),
							"warnings": data.get("warnings", []),
							"recommendations": data.get("recommendations", []),
						}
					)

					if data.get("validation_successful"):
						results["summary"]["customers_now_validated"] += 1

					results["summary"]["successful_validations"] += 1

				else:
					customer_result["error"] = validation_result.get("error", "Error desconocido")
					results["summary"]["failed_validations"] += 1
					results["summary"]["errors"].append(f"{customer_name}: {customer_result['error']}")

				results["results"].append(customer_result)

				# Pausa pequeña entre validaciones para no saturar FacturAPI
				import time

				time.sleep(1)

			except Exception as e:
				error_msg = f"Error validating {customer_name}: {e!s}"
				frappe.log_error(error_msg, "Bulk RFC Validation Error")

				results["results"].append(
					{
						"customer": customer_name,
						"success": False,
						"validation_successful": False,
						"error": str(e),
					}
				)

				results["summary"]["failed_validations"] += 1
				results["summary"]["errors"].append(error_msg)

		# Log resumen de la ejecución masiva
		frappe.logger().info(
			f"Bulk RFC Validation completed: {results['summary']['successful_validations']} successful, "
			f"{results['summary']['failed_validations']} failed, "
			f"{results['summary']['customers_now_validated']} now validated"
		)

		return results

	except Exception as e:
		frappe.log_error(f"Error in bulk RFC validation: {e!s}", "Bulk RFC Validation Critical Error")
		return {"success": False, "error": f"Error crítico en validación masiva: {e!s}", "results": []}


def run_nightly_rfc_validation():
	"""
	SCHEDULED JOB PRINCIPAL: Validación automática nocturna de RFCs.
	Se ejecuta cada noche a las 2:00 AM.
	Valida máximo 30 customers por día priorizados inteligentemente.
	"""
	try:
		frappe.logger().info("🌙 Iniciando validación RFC nocturna automática...")

		# Obtener configuración del límite diario (configurable via Settings)
		try:
			settings = frappe.get_single("Facturacion Mexico Settings")
			daily_validation_limit = getattr(settings, "daily_rfc_validation_limit", 30)
		except Exception:
			daily_validation_limit = 30  # Fallback por defecto

		# Obtener customers candidatos priorizados
		candidates = get_customers_needing_rfc_validation(limit=daily_validation_limit)

		if not candidates:
			frappe.logger().info("✅ No hay customers pendientes de validación RFC")
			return {"success": True, "message": "No customers needing validation", "total_processed": 0}

		frappe.logger().info(f"🎯 Encontrados {len(candidates)} customers candidatos para validación")

		# Extraer solo los nombres para la validación masiva
		customer_names = [c["name"] for c in candidates]

		# Ejecutar validación masiva
		bulk_result = validate_customers_bulk(customer_names, daily_validation_limit)

		# Crear log de auditoría de la ejecución
		create_nightly_validation_log(candidates, bulk_result)

		# Log resumen final
		summary = bulk_result.get("summary", {})
		frappe.logger().info(
			f"🌙 Validación RFC nocturna completada: "
			f"{summary.get('customers_now_validated', 0)} customers validados exitosamente, "
			f"{summary.get('failed_validations', 0)} fallos"
		)

		return {
			"success": True,
			"message": "Nightly RFC validation completed",
			"total_processed": len(candidates),
			"results": bulk_result,
		}

	except Exception as e:
		error_msg = f"Error crítico en validación RFC nocturna: {e!s}"
		frappe.log_error(error_msg, "Nightly RFC Validation Critical Error")
		frappe.logger().error(f"🚨 {error_msg}")

		return {"success": False, "error": error_msg, "total_processed": 0}


def create_nightly_validation_log(candidates, bulk_result):
	"""
	Crear log de auditoría para la ejecución nocturna.

	Args:
		candidates (list): Lista de customers candidatos
		bulk_result (dict): Resultado de la validación masiva
	"""
	try:
		# Crear documento de log (usando Error Log como base para auditoría)
		log_data = {
			"doctype": "Error Log",
			"method": "Nightly RFC Validation",
			"error": frappe.as_json(
				{
					"execution_timestamp": frappe.utils.now(),
					"candidates_count": len(candidates),
					"candidates": [
						{
							"customer": c["name"],
							"rfc": c["tax_id"],
							"priority_level": c["priority_level"],
							"validation_reason": c["validation_reason"],
							"has_address": c["has_primary_address"],
							"invoice_count": c["invoice_count"],
						}
						for c in candidates
					],
					"validation_results": bulk_result,
					"summary": {
						"total_candidates": len(candidates),
						"successful_validations": bulk_result.get("summary", {}).get(
							"successful_validations", 0
						),
						"failed_validations": bulk_result.get("summary", {}).get("failed_validations", 0),
						"customers_now_validated": bulk_result.get("summary", {}).get(
							"customers_now_validated", 0
						),
						"errors": bulk_result.get("summary", {}).get("errors", []),
					},
				},
				indent=2,
			),
		}

		# Insertar log
		log_doc = frappe.get_doc(log_data)
		log_doc.insert(ignore_permissions=True)

		frappe.logger().info(f"📋 Log de auditoría creado: {log_doc.name}")

	except Exception as e:
		frappe.log_error(f"Error creating nightly validation log: {e!s}", "Nightly Validation Log Error")


@frappe.whitelist()
def get_nightly_validation_stats():
	"""
	Obtener estadísticas de las últimas ejecuciones nocturnas.
	Para dashboard y monitoreo.

	Returns:
		dict: Estadísticas de validaciones nocturnas
	"""
	try:
		# Buscar logs de validación nocturna de los últimos 30 días
		logs = frappe.db.sql(
			"""
			SELECT creation, error
			FROM `tabError Log`
			WHERE method = 'Nightly RFC Validation'
			AND creation >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
			ORDER BY creation DESC
			LIMIT 30
		""",
			as_dict=True,
		)

		stats = {
			"total_executions": len(logs),
			"last_execution": None,
			"avg_customers_processed": 0,
			"avg_success_rate": 0,
			"recent_executions": [],
		}

		if not logs:
			return {"success": True, "stats": stats}

		# Procesar logs para extraer estadísticas
		total_processed = 0
		total_validated = 0

		for log in logs:
			try:
				log_data = frappe.parse_json(log.error)
				execution_data = {
					"date": log.creation,
					"candidates": log_data.get("candidates_count", 0),
					"validated": log_data.get("summary", {}).get("customers_now_validated", 0),
					"success_rate": 0,
				}

				if execution_data["candidates"] > 0:
					execution_data["success_rate"] = (
						execution_data["validated"] / execution_data["candidates"]
					) * 100

				stats["recent_executions"].append(execution_data)
				total_processed += execution_data["candidates"]
				total_validated += execution_data["validated"]

			except Exception:
				continue

		# Calcular promedios
		if len(stats["recent_executions"]) > 0:
			stats["last_execution"] = stats["recent_executions"][0]["date"]
			stats["avg_customers_processed"] = total_processed / len(stats["recent_executions"])
			if total_processed > 0:
				stats["avg_success_rate"] = (total_validated / total_processed) * 100

		return {"success": True, "stats": stats}

	except Exception as e:
		frappe.log_error(f"Error getting nightly validation stats: {e!s}", "Nightly Validation Stats Error")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_customers_validation_summary():
	"""
	Obtener resumen del estado de validación de todos los customers.
	Para dashboard y reportes.

	Returns:
		dict: Resumen de estado de validación
	"""
	try:
		# Query resumen general
		summary_query = """
			SELECT
				COUNT(*) as total_customers,
				SUM(CASE WHEN tax_id IS NOT NULL AND tax_id != '' THEN 1 ELSE 0 END) as customers_with_rfc,
				SUM(CASE WHEN fm_rfc_validated = 1 THEN 1 ELSE 0 END) as customers_validated,
				SUM(CASE
					WHEN fm_rfc_validated = 1
					AND fm_rfc_validation_date IS NOT NULL
					AND DATEDIFF(CURDATE(), fm_rfc_validation_date) <= 365 THEN 1
					ELSE 0
				END) as customers_valid_current,
				SUM(CASE
					WHEN fm_rfc_validated = 1
					AND fm_rfc_validation_date IS NOT NULL
					AND DATEDIFF(CURDATE(), fm_rfc_validation_date) > 365 THEN 1
					ELSE 0
				END) as customers_expired,
				SUM(CASE
					WHEN (tax_id IS NULL OR tax_id = '') THEN 1
					ELSE 0
				END) as customers_without_rfc
			FROM `tabCustomer`
			WHERE disabled = 0
		"""

		summary = frappe.db.sql(summary_query, as_dict=True)[0]

		# Calcular customers pendientes
		customers_pending = summary["customers_with_rfc"] - summary["customers_valid_current"]

		# Calcular porcentajes
		total_with_rfc = summary["customers_with_rfc"]
		percentages = {}

		if total_with_rfc > 0:
			percentages = {
				"validated_percentage": (summary["customers_valid_current"] / total_with_rfc) * 100,
				"pending_percentage": (customers_pending / total_with_rfc) * 100,
				"expired_percentage": (summary["customers_expired"] / total_with_rfc) * 100,
			}
		else:
			percentages = {"validated_percentage": 0, "pending_percentage": 0, "expired_percentage": 0}

		# Obtener próximos customers para validar
		next_candidates = get_customers_needing_rfc_validation(limit=10)

		result = {
			"success": True,
			"summary": {**summary, "customers_pending": customers_pending, **percentages},
			"next_candidates": [
				{
					"name": c["name"],
					"customer_name": c["customer_name"],
					"rfc": c["tax_id"],
					"reason": c["validation_reason"],
					"priority": c["priority_level"],
					"invoices": c["invoice_count"],
				}
				for c in next_candidates
			],
		}

		return result

	except Exception as e:
		frappe.log_error(f"Error getting customers validation summary: {e!s}", "Validation Summary Error")
		return {"success": False, "error": str(e)}
