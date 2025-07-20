"""
APIs para Validaciones SAT México - Sprint 2
Sistema de validación con cache inteligente
"""

import re
from datetime import datetime

import frappe
import requests
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
		rfc = rfc.upper().strip()

		# Validar formato básico
		if not _is_valid_rfc_format(rfc):
			return {"success": False, "valid": False, "message": _("Formato de RFC inválido"), "rfc": rfc}

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
		rfc = rfc.upper().strip()

		# Buscar en cache si está habilitado
		if use_cache:
			cached_result = _get_cached_lista_69b_validation(rfc)
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
						"rfc": rfc,
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
			rfc = validation_key.replace("RFC_", "")
			result = validate_rfc(rfc, use_cache=False)
		elif validation_type == "lista_69b":
			rfc = validation_key.replace("L69B_", "")
			result = validate_lista_69b(rfc, use_cache=False)
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
				"rfc": rfc,
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
				"rfc": rfc,
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
				"rfc": rfc,
				"api_response": {"codigo": "404", "mensaje": "RFC no encontrado"},
			}
		else:
			return {
				"success": True,
				"valid": True,
				"status": "Activo",
				"message": _("RFC válido según SAT"),
				"rfc": rfc,
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
			"rfc": rfc,
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
