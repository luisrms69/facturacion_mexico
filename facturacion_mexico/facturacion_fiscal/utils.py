"""
Utilidades para Facturación Fiscal México
Funciones puente para acceso a datos fiscales sin duplicación
Incluye Status Calculator para arquitectura resiliente
"""

import json
from typing import Any

import frappe
from frappe.utils import now

from facturacion_mexico.config.fiscal_states_config import FiscalStates


def get_invoice_uuid(sales_invoice_name):
	"""
	Obtener UUID fiscal desde Factura Fiscal Mexico vía referencia.
	Reemplaza el campo duplicado fm_uuid_fiscal en Sales Invoice.

	Args:
		sales_invoice_name (str): Nombre del documento Sales Invoice

	Returns:
		str|None: UUID fiscal si existe, None si no hay documento fiscal asociado
	"""
	try:
		# Obtener referencia al documento fiscal
		fiscal_doc_name = frappe.db.get_value("Sales Invoice", sales_invoice_name, "fm_factura_fiscal_mx")

		if not fiscal_doc_name:
			return None

		# Obtener UUID desde Factura Fiscal Mexico
		uuid = frappe.db.get_value("Factura Fiscal Mexico", fiscal_doc_name, "uuid")

		return uuid

	except Exception as e:
		frappe.log_error(
			f"Error obteniendo UUID fiscal para {sales_invoice_name}: {e!s}", "Get Invoice UUID Error"
		)
		return None


def get_invoice_fiscal_data(sales_invoice_name):
	"""
	Obtener datos fiscales completos desde Factura Fiscal Mexico.
	Preparado para extensión futura con serie, folio, totales, etc.

	Args:
		sales_invoice_name (str): Nombre del documento Sales Invoice

	Returns:
		dict: Datos fiscales o dict vacío si no existe
	"""
	try:
		# Obtener referencia al documento fiscal
		fiscal_doc_name = frappe.db.get_value("Sales Invoice", sales_invoice_name, "fm_factura_fiscal_mx")

		if not fiscal_doc_name:
			return {}

		# Obtener datos fiscales completos
		fiscal_data = frappe.db.get_value(
			"Factura Fiscal Mexico",
			fiscal_doc_name,
			["uuid", "serie", "folio", "total_fiscal", "fm_fiscal_status", "facturapi_id", "fecha_timbrado"],
			as_dict=True,
		)

		return fiscal_data or {}

	except Exception as e:
		frappe.log_error(
			f"Error obteniendo datos fiscales para {sales_invoice_name}: {e!s}",
			"Get Invoice Fiscal Data Error",
		)
		return {}


def has_fiscal_document(sales_invoice_name):
	"""
	Verificar si Sales Invoice tiene documento fiscal asociado.

	Args:
		sales_invoice_name (str): Nombre del documento Sales Invoice

	Returns:
		bool: True si tiene documento fiscal, False en caso contrario
	"""
	try:
		fiscal_doc_name = frappe.db.get_value("Sales Invoice", sales_invoice_name, "fm_factura_fiscal_mx")

		return bool(fiscal_doc_name)

	except Exception:
		return False


def is_invoice_stamped(sales_invoice_name):
	"""
	Verificar si la factura está timbrada fiscalmente.
	Reemplaza verificación de fm_uuid_fiscal.

	Args:
		sales_invoice_name (str): Nombre del documento Sales Invoice

	Returns:
		bool: True si está timbrada, False en caso contrario
	"""
	try:
		fiscal_data = get_invoice_fiscal_data(sales_invoice_name)

		# Verificar que tenga UUID y estado TIMBRADO
		return fiscal_data.get("uuid") and fiscal_data.get("fm_fiscal_status") == FiscalStates.TIMBRADO

	except Exception:
		return False


# =============================================================================
# STATUS CALCULATOR - ARQUITECTURA RESILIENTE ESTADOS FISCALES
# =============================================================================


def calculate_current_status(factura_fiscal_name: str) -> dict[str, Any]:
	"""
	Calcular estado fiscal actual basado en TODOS los logs PAC.
	Función STATELESS - no modifica datos, solo calcula.

	Args:
		factura_fiscal_name: Nombre del documento Factura Fiscal Mexico

	Returns:
		Dict con estado calculado y metadatos
	"""
	try:
		# Verificar que existe el documento
		if not frappe.db.exists("Factura Fiscal Mexico", factura_fiscal_name):
			return {
				"status": FiscalStates.ERROR,
				"sub_status": "document_not_found",
				"calculated_at": frappe.utils.now(),
				"source": "status_calculator",
				"logs_analyzed": 0,
			}

		# Obtener TODOS los logs relacionados ordenados cronológicamente
		logs = frappe.db.sql(
			"""
			SELECT
				name, timestamp, operation_type, success,
				facturapi_response, timeout_flag, status_code
			FROM `tabFacturAPI Response Log`
			WHERE factura_fiscal_mexico = %s
			ORDER BY timestamp DESC
		""",
			(factura_fiscal_name,),
			as_dict=True,
		)

		if not logs:
			return {
				"status": FiscalStates.BORRADOR,
				"sub_status": "no_pac_interaction",
				"calculated_at": frappe.utils.now(),
				"source": "status_calculator",
				"logs_analyzed": 0,
			}

		# Analizar logs desde el más reciente
		latest_log = logs[0]

		# Si hay timeout pendiente, estado es PROCESANDO
		if latest_log.get("timeout_flag"):
			return {
				"status": FiscalStates.PROCESANDO,
				"sub_status": "timeout_waiting_pac",
				"calculated_at": frappe.utils.now(),
				"source": "status_calculator",
				"logs_analyzed": len(logs),
				"latest_log": latest_log.get("name"),
			}

		# Si última operación fue exitosa, determinar estado desde respuesta
		if latest_log.get("success"):
			try:
				response_data = json.loads(latest_log.get("facturapi_response", "{}"))
				status_from_response = get_status_from_response(response_data)

				return {
					"status": status_from_response["status"],
					"sub_status": status_from_response.get("sub_status"),
					"calculated_at": frappe.utils.now(),
					"source": "status_calculator",
					"logs_analyzed": len(logs),
					"latest_log": latest_log.get("name"),
					"pac_response_status": response_data.get("status"),
				}
			except (json.JSONDecodeError, Exception):
				# Si no puede parsear respuesta pero success=True, asumir timbrado
				return {
					"status": FiscalStates.TIMBRADO,
					"sub_status": "success_unparseable_response",
					"calculated_at": frappe.utils.now(),
					"source": "status_calculator",
					"logs_analyzed": len(logs),
					"latest_log": latest_log.get("name"),
				}

		# Si última operación falló, determinar tipo de error
		else:
			status_code = latest_log.get("status_code", 0)
			# Convertir status_code a int si viene como string
			if isinstance(status_code, str):
				try:
					status_code = int(status_code)
				except (ValueError, TypeError):
					status_code = 0

			if status_code >= 400 and status_code < 500:
				# Errores del cliente (validación, autenticación)
				return {
					"status": FiscalStates.ERROR,
					"sub_status": f"validation_error_{status_code}",
					"calculated_at": frappe.utils.now(),
					"source": "status_calculator",
					"logs_analyzed": len(logs),
					"latest_log": latest_log.get("name"),
				}
			elif status_code >= 500:
				# Errores del servidor PAC
				return {
					"status": FiscalStates.ERROR,
					"sub_status": f"pac_error_{status_code}",
					"calculated_at": frappe.utils.now(),
					"source": "status_calculator",
					"logs_analyzed": len(logs),
					"latest_log": latest_log.get("name"),
				}
			else:
				# Error genérico
				return {
					"status": FiscalStates.ERROR,
					"sub_status": "unknown_error",
					"calculated_at": frappe.utils.now(),
					"source": "status_calculator",
					"logs_analyzed": len(logs),
					"latest_log": latest_log.get("name"),
				}

	except Exception as e:
		frappe.log_error(f"Error calculando estado fiscal: {e!s}", "Status Calculator Error")
		return {
			"status": "ERROR",
			"sub_status": "calculation_failed",
			"calculated_at": frappe.utils.now(),
			"source": "status_calculator",
			"logs_analyzed": 0,
			"error": str(e),
		}


def get_status_from_response(response_payload: dict[str, Any]) -> dict[str, Any]:
	"""
	Parsear respuesta PAC y mapear a estados internos.
	Implementa mapeo completo FacturAPI → Estados español.

	Args:
		response_payload: Respuesta JSON de FacturAPI

	Returns:
		Dict con status y sub_status mapeados
	"""
	try:
		if not response_payload:
			return {"status": "ERROR", "sub_status": "empty_response"}

		# Obtener status de FacturAPI
		facturapi_status = response_payload.get("status", "").lower()

		# Mapeo según arquitectura resiliente (ARQUITECTURA RESILIENTE)
		status_mapping = {
			"valid": {"status": FiscalStates.TIMBRADO, "sub_status": None},
			"canceled": {"status": FiscalStates.CANCELADO, "sub_status": None},
			"pending_cancellation": {"status": "PENDIENTE_CANCELACION", "sub_status": None},
			"draft": {"status": FiscalStates.BORRADOR, "sub_status": "ereceipt_draft"},
			"expired": {"status": "ARCHIVADO", "sub_status": "ereceipt_expired"},
			"invoiced": {"status": FiscalStates.TIMBRADO, "sub_status": "ereceipt_converted"},
		}

		# Si hay mapeo directo, usarlo
		if facturapi_status in status_mapping:
			return status_mapping[facturapi_status]

		# Si no hay status pero hay UUID, asumir timbrado
		if response_payload.get("uuid") or response_payload.get("id"):
			return {"status": FiscalStates.TIMBRADO, "sub_status": None}

		# Si hay error específico de validación
		if "error" in response_payload:
			error_type = response_payload.get("error", {}).get("type", "")
			if "validation" in error_type.lower():
				return {"status": "ERROR", "sub_status": f"validation_{error_type}"}

		# Si no se puede determinar, marcar como desconocido
		return {"status": "ERROR", "sub_status": "unknown_pac_status"}

	except Exception as e:
		frappe.log_error(f"Error parseando respuesta PAC: {e!s}", "Status Mapping Error")
		return {"status": "ERROR", "sub_status": "parse_error"}


def should_override_status(current_status: str, calculated_status: str, factura_fiscal_name: str) -> bool:
	"""
	Determinar si debe actualizarse el estado actual.
	Respeta manual_override y aplica lógica de precedencia.

	Args:
		current_status: Estado actual en Factura Fiscal Mexico
		calculated_status: Estado calculado desde logs
		factura_fiscal_name: Nombre del documento

	Returns:
		bool: True si debe actualizarse, False si mantener actual
	"""
	try:
		# Verificar si hay override manual activo
		manual_override = frappe.db.get_value(
			"Factura Fiscal Mexico", factura_fiscal_name, "fm_manual_override"
		)

		if manual_override:
			# No actualizar si hay override manual
			return False

		# Si no hay estado actual, siempre actualizar
		if not current_status:
			return True

		# Si estados son iguales, no actualizar
		if current_status == calculated_status:
			return False

		# Lógica de precedencia de estados
		precedence_order = [
			FiscalStates.BORRADOR,  # 0 - Estado inicial
			FiscalStates.PROCESANDO,  # 1 - En proceso
			FiscalStates.ERROR,  # 2 - Error recuperable
			FiscalStates.TIMBRADO,  # 3 - Éxito final
			"PENDIENTE_CANCELACION",  # 4 - Cancelación en proceso
			FiscalStates.CANCELADO,  # 5 - Cancelación final
			"ARCHIVADO",  # 6 - Estado final archivado
		]

		try:
			current_idx = precedence_order.index(current_status)
		except ValueError:
			# Estado actual desconocido, permitir actualización
			return True

		try:
			calculated_idx = precedence_order.index(calculated_status)
		except ValueError:
			# Estado calculado desconocido, no actualizar
			return False

		# Solo actualizar si el estado calculado tiene mayor precedencia
		# O si vamos de Error -> cualquier estado exitoso
		if calculated_idx > current_idx:
			return True
		elif current_status == FiscalStates.ERROR and calculated_status in [
			FiscalStates.TIMBRADO,
			FiscalStates.CANCELADO,
		]:
			# Permitir recuperación de errores a estados exitosos
			return True

		return False

	except Exception as e:
		frappe.log_error(f"Error evaluando override de estado: {e!s}", "Status Override Error")
		# En caso de error, ser conservador y no actualizar
		return False


# =============================================================================
# SYNC SERVICE - ARQUITECTURA RESILIENTE ESTADOS FISCALES
# =============================================================================


def sync_status_to_sales_invoice(factura_fiscal_name: str) -> dict[str, Any]:
	"""
	Sincronizar estado de Factura Fiscal Mexico hacia Sales Invoice.
	One-way sync usando db.set_value para evitar triggers pesados.

	Args:
		factura_fiscal_name: Nombre del documento Factura Fiscal Mexico

	Returns:
		Dict con resultado de sincronización
	"""
	try:
		# Verificar que existe el documento fiscal
		if not frappe.db.exists("Factura Fiscal Mexico", factura_fiscal_name):
			return {
				"success": False,
				"error": "Documento fiscal no encontrado",
				"factura_fiscal": factura_fiscal_name,
			}

		# Obtener datos actuales del documento fiscal
		fiscal_data = frappe.db.get_value(
			"Factura Fiscal Mexico",
			factura_fiscal_name,
			[
				"sales_invoice",
				"fm_fiscal_status",
				"fm_sub_status",
				"fm_last_pac_sync",
				"fm_sync_status",
				"fm_manual_override",
			],
			as_dict=True,
		)

		if not fiscal_data or not fiscal_data.get("sales_invoice"):
			return {
				"success": False,
				"error": "Sales Invoice no encontrado en documento fiscal",
				"factura_fiscal": factura_fiscal_name,
			}

		sales_invoice_name = fiscal_data["sales_invoice"]

		# Verificar si Sales Invoice existe
		if not frappe.db.exists("Sales Invoice", sales_invoice_name):
			return {
				"success": False,
				"error": "Sales Invoice referenciado no existe",
				"sales_invoice": sales_invoice_name,
				"factura_fiscal": factura_fiscal_name,
			}

		# Obtener estado actual en Sales Invoice para comparar
		current_si_status = frappe.db.get_value("Sales Invoice", sales_invoice_name, "fm_fiscal_status")

		# Preparar datos para sincronización
		sync_data = {
			"fm_fiscal_status": fiscal_data.get("fm_fiscal_status", "Borrador"),
			"fm_last_status_update": now(),
		}

		# Solo actualizar si hay cambio real
		if current_si_status != sync_data["fm_fiscal_status"]:
			# Actualizar usando db.set_value para evitar triggers
			for field, value in sync_data.items():
				frappe.db.set_value("Sales Invoice", sales_invoice_name, field, value)

			frappe.db.commit()

			# Actualizar timestamp de última sincronización en Factura Fiscal
			frappe.db.set_value(
				"Factura Fiscal Mexico",
				factura_fiscal_name,
				{"fm_last_pac_sync": now(), "fm_sync_status": "synced"},
			)
			frappe.db.commit()

			return {
				"success": True,
				"synced": True,
				"previous_status": current_si_status,
				"new_status": sync_data["fm_fiscal_status"],
				"sales_invoice": sales_invoice_name,
				"factura_fiscal": factura_fiscal_name,
				"timestamp": now(),
			}
		else:
			# Sin cambios, pero actualizar timestamp de sync exitoso
			frappe.db.set_value(
				"Factura Fiscal Mexico",
				factura_fiscal_name,
				{"fm_last_pac_sync": now(), "fm_sync_status": "synced"},
			)
			frappe.db.commit()

			return {
				"success": True,
				"synced": False,
				"reason": "no_changes_needed",
				"current_status": current_si_status,
				"sales_invoice": sales_invoice_name,
				"factura_fiscal": factura_fiscal_name,
				"timestamp": now(),
			}

	except Exception as e:
		frappe.log_error(f"Error sincronizando estado fiscal: {e!s}", "Sync Service Error")
		return {"success": False, "error": str(e), "factura_fiscal": factura_fiscal_name, "timestamp": now()}


def bulk_sync_invoices(limit: int = 100, filters: dict[str, Any] | None = None) -> dict[str, Any]:
	"""
	Sincronización masiva de estados fiscales.
	Procesa en lotes para evitar timeouts y permite filtros específicos.

	Args:
		limit: Número máximo de documentos a procesar
		filters: Filtros adicionales para selección de documentos

	Returns:
		Dict con estadísticas de sincronización masiva
	"""
	try:
		frappe.logger().info(f"Iniciando sincronización masiva (límite: {limit})")

		# Preparar filtros base
		base_filters = {"fm_sync_status": ["in", ["pending", "error"]], "sales_invoice": ["!=", ""]}

		# Agregar filtros adicionales si se proporcionan
		if filters:
			base_filters.update(filters)

		# Obtener documentos fiscales que necesitan sincronización
		fiscal_docs = frappe.db.sql(
			"""
			SELECT name, sales_invoice, fm_fiscal_status, fm_last_pac_sync
			FROM `tabFactura Fiscal Mexico`
			WHERE fm_sync_status IN ('pending', 'error')
			AND sales_invoice IS NOT NULL
			AND sales_invoice != ''
			ORDER BY modified DESC
			LIMIT %s
		""",
			(limit,),
			as_dict=True,
		)

		if not fiscal_docs:
			return {
				"success": True,
				"processed": 0,
				"synced": 0,
				"skipped": 0,
				"errors": 0,
				"message": "No hay documentos pendientes de sincronización",
			}

		# Contadores para estadísticas
		processed = 0
		synced = 0
		skipped = 0
		errors = 0

		# Procesar cada documento
		for doc in fiscal_docs:
			try:
				sync_result = sync_status_to_sales_invoice(doc.name)
				processed += 1

				if sync_result.get("success"):
					if sync_result.get("synced"):
						synced += 1
					else:
						skipped += 1
				else:
					errors += 1
					frappe.logger().error(f"Error sincronizando {doc.name}: {sync_result.get('error')}")

				# Commit cada 10 documentos para evitar locks largos
				if processed % 10 == 0:
					frappe.db.commit()

			except Exception as e:
				errors += 1
				frappe.log_error(f"Error procesando documento {doc.name}: {e!s}", "Bulk Sync Error")

		# Commit final
		frappe.db.commit()

		result = {
			"success": True,
			"processed": processed,
			"synced": synced,
			"skipped": skipped,
			"errors": errors,
			"timestamp": now(),
		}

		frappe.logger().info(
			f"Sincronización masiva completada: {processed} procesados, {synced} sincronizados, {skipped} sin cambios, {errors} errores"
		)
		return result

	except Exception as e:
		frappe.log_error(f"Error en sincronización masiva: {e!s}", "Bulk Sync Critical Error")
		return {
			"success": False,
			"error": str(e),
			"processed": 0,
			"synced": 0,
			"skipped": 0,
			"errors": 0,
			"timestamp": now(),
		}


def enqueue_bulk_sync(limit: int = 500, filters: dict[str, Any] | None = None) -> dict[str, Any]:
	"""
	Enqueue sincronización masiva como background job.
	Non-blocking para operaciones grandes.

	Args:
		limit: Número máximo de documentos a procesar
		filters: Filtros adicionales para selección

	Returns:
		Dict con información del job enqueueado
	"""
	try:
		# Validar límite
		if limit > 1000:
			limit = 1000  # Cap máximo por seguridad

		# Enqueue usando sistema de background jobs de Frappe
		job = frappe.enqueue(
			"facturacion_mexico.facturacion_fiscal.utils.bulk_sync_invoices",
			queue="long",  # Queue para trabajos largos
			timeout=3600,  # 1 hora timeout
			limit=limit,
			filters=filters,
		)

		return {
			"success": True,
			"job_id": job.id,
			"queue": "long",
			"status": "enqueued",
			"limit": limit,
			"estimated_time": "5-15 minutos",
			"timestamp": now(),
		}

	except Exception as e:
		frappe.log_error(f"Error enqueuing bulk sync: {e!s}", "Enqueue Sync Error")
		return {"success": False, "error": str(e), "timestamp": now()}


def sync_single_invoice_status(sales_invoice_name: str, recalculate: bool = True) -> dict[str, Any]:
	"""
	Sincronizar estado de una factura específica.
	Función de conveniencia para uso individual.

	Args:
		sales_invoice_name: Nombre de Sales Invoice
		recalculate: Si debe recalcular estado desde logs antes de sincronizar

	Returns:
		Dict con resultado de sincronización individual
	"""
	try:
		# Obtener Factura Fiscal Mexico asociada
		factura_fiscal_name = frappe.db.get_value("Sales Invoice", sales_invoice_name, "fm_factura_fiscal_mx")

		if not factura_fiscal_name:
			return {
				"success": False,
				"error": "Sales Invoice no tiene documento fiscal asociado",
				"sales_invoice": sales_invoice_name,
			}

		# Si se solicita recálculo, hacerlo antes de sincronizar
		if recalculate:
			calculated_status = calculate_current_status(factura_fiscal_name)
			current_status = frappe.db.get_value(
				"Factura Fiscal Mexico", factura_fiscal_name, "fm_fiscal_status"
			)

			# Actualizar estado si debe overridearse
			if should_override_status(current_status, calculated_status.get("status"), factura_fiscal_name):
				frappe.db.set_value(
					"Factura Fiscal Mexico",
					factura_fiscal_name,
					{
						"fm_fiscal_status": calculated_status.get("status"),
						"fm_sub_status": calculated_status.get("sub_status"),
						"fm_sync_status": "pending",  # Marcar para sincronizar
					},
				)
				frappe.db.commit()

		# Sincronizar hacia Sales Invoice
		sync_result = sync_status_to_sales_invoice(factura_fiscal_name)
		sync_result["recalculated"] = recalculate

		return sync_result

	except Exception as e:
		frappe.log_error(f"Error sincronizando factura individual: {e!s}", "Individual Sync Error")
		return {"success": False, "error": str(e), "sales_invoice": sales_invoice_name, "timestamp": now()}
