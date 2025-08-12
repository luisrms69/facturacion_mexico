# API module for facturacion fiscal
"""
PAC Response Writer API - Sistema Resiliente Estados Fiscales
APIs ultra-resilientes para manejo de respuestas PAC con filesystem fallback
CRÍTICO: Garantiza 0% pérdida respuestas PAC bajo cualquier circunstancia
Incluye endpoints para exponer configuración de estados a JavaScript
"""

import json
import os
import re
import traceback
from pathlib import Path
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_to_date, now, now_datetime

# Directorio fallback para respuestas PAC cuando DB no disponible
FALLBACK_DIR = "/tmp/facturacion_mexico_pac_fallback"


def _derive_http_status(data: dict, default=500) -> int:
	# 1) Si ya viene numérico
	for k in ("status_code", "code"):
		val = data.get(k)
		try:
			if val is not None:
				n = int(val)
				if 100 <= n <= 599:
					return n
		except Exception:
			pass

	# 2) Parsear del mensaje: "Error FacturAPI 400: ..."
	for k in ("error_message", "error", "message", "raw_response"):
		msg = (data.get(k) or "").strip()
		m = re.search(r"\b(\d{3})\b", msg)
		if m:
			try:
				n = int(m.group(1))
				if 100 <= n <= 599:
					return n
			except Exception:
				pass
	return default


def _derive_error_message(data: dict) -> str:
	return (
		(data.get("error_message") or "").strip()
		or (data.get("error") or "").strip()
		or (data.get("message") or "").strip()
		or (data.get("raw_response") or "").strip()
	)


def _norm_status(s: str) -> str:
	return (s or "").strip().upper()


class PACResponseWriter:
	"""
	Writer ultra-resiliente para respuestas PAC.

	Principios de diseño:
	1. PAC Response First - NADA impide registro respuesta PAC
	2. Triple redundancia: DB -> Filesystem -> Log
	3. Degradación elegante bajo cualquier falla
	4. Recovery automático cuando DB vuelve disponible
	"""

	def __init__(self):
		"""Inicializar writer con preparación filesystem."""
		self.ensure_fallback_directory()

	def ensure_fallback_directory(self):
		"""Garantizar que directorio fallback existe con permisos correctos."""
		try:
			Path(FALLBACK_DIR).mkdir(parents=True, exist_ok=True)
			os.chmod(FALLBACK_DIR, 0o700)  # Owner-only permissions for security
		except Exception as e:
			# Incluso si falla crear directorio, continuamos
			frappe.log_error(f"Error creando directorio fallback: {e!s}", "PAC Writer Fallback")

	def write_pac_response(
		self,
		sales_invoice_name: str,
		request_data: dict[str, Any],
		response_data: dict[str, Any],
		operation_type: str = "timbrado",
	) -> dict[str, Any]:
		"""
		Escribir respuesta PAC con máxima resilencia.

		Args:
			sales_invoice_name: Nombre de Sales Invoice
			request_data: Datos del request enviado
			response_data: Respuesta completa de FacturAPI
			operation_type: Tipo operación (timbrado/cancelacion/consulta)

		Returns:
			Dict con status y referencias creadas
		"""
		result = {
			"success": False,
			"response_log_name": None,
			"fallback_file": None,
			"errors": [],
			"timestamp": now(),
		}

		try:
			# PASO 1: Intentar escritura a BD (principal)
			response_log = self._write_to_database(
				sales_invoice_name, request_data, response_data, operation_type
			)

			if response_log:
				result["success"] = True
				result["response_log_name"] = response_log.name
				result["method"] = "database"

				# PASO 2: Actualizar Factura Fiscal Mexico si existe
				self._update_factura_fiscal(sales_invoice_name, response_data, response_log.name)

				return result

		except Exception as db_error:
			result["errors"].append(f"DB Error: {db_error!s}")
			frappe.log_error(f"Error escritura BD PAC: {traceback.format_exc()}", "PAC Writer DB Error")

		# PASO 3: Fallback a filesystem si BD falla
		try:
			fallback_file = self._write_to_filesystem(
				sales_invoice_name, request_data, response_data, operation_type
			)

			result["success"] = True
			result["fallback_file"] = fallback_file
			result["method"] = "filesystem_fallback"
			result["errors"].append("BD no disponible - guardado en filesystem para recovery")

			# Programar recovery automático
			self._schedule_recovery_task(fallback_file)

			return result

		except Exception as fs_error:
			result["errors"].append(f"Filesystem Error: {fs_error!s}")
			frappe.log_error(
				f"Error filesystem fallback: {traceback.format_exc()}", "PAC Writer Filesystem Error"
			)

		# PASO 4: Si todo falla, log crítico pero NO falla silenciosamente
		result["errors"].append("CRÍTICO: Falló escritura BD y filesystem - respuesta PAC en riesgo")
		frappe.log_error(
			f"CRÍTICO PAC Response Writer: {json.dumps(result, indent=2)}", "PAC Writer CRITICAL FAILURE"
		)

		# Incluso en falla completa, intentamos un último log de emergencia
		try:
			emergency_log = {
				"sales_invoice": sales_invoice_name,
				"response_data": response_data,
				"timestamp": now(),
				"emergency_flag": True,
			}

			emergency_file = (
				f"/tmp/pac_emergency_{sales_invoice_name}_{now().replace(' ', '_').replace(':', '-')}.json"
			)
			with open(emergency_file, "w") as f:
				json.dump(emergency_log, f, indent=2, default=str)

			result["emergency_file"] = emergency_file

		except Exception:
			# Si incluso el log de emergencia falla, al menos tenemos el error en result
			pass

		return result

	def _write_to_database(
		self,
		sales_invoice_name: str,
		request_data: dict[str, Any],
		response_data: dict[str, Any],
		operation_type: str,
	) -> Any | None:
		"""Escribir a FacturAPI Response Log en BD."""
		# Obtener referencia a Factura Fiscal Mexico si existe
		factura_fiscal = frappe.db.get_value(
			"Factura Fiscal Mexico", {"sales_invoice": sales_invoice_name}, "name"
		)

		# Mapear operation_type a valores válidos del DocType (ARQUITECTURA RESILIENTE)
		operation_type_mapping = {
			"timbrado": "Timbrado",
			"cancelacion": "PENDIENTE_CANCELACION",
			"consulta": "Consulta Estado",
			"timeout_recovery": "Consulta Estado",
		}

		# Helper para extraer código de estado del mensaje de error
		def _extract_status_code(err_text: str) -> int:
			if not err_text:
				return 500
			import re

			m = re.search(r"FacturAPI\s+(\d{3})", err_text)
			if m:
				try:
					return int(m.group(1))
				except Exception:
					pass
			return 500

		# Helper para mapeo inteligente de mensaje de error
		def _coalesce_error_message(d: dict) -> str:
			# Orden de preferencia más robusto
			return (
				(d.get("error_message") or "").strip()
				or (d.get("error") or "").strip()
				or (d.get("message") or "").strip()
				or (d.get("detail") or "").strip()
				or (d.get("error_description") or "").strip()
				or ""
			)

		status_code = response_data.get("status_code") or response_data.get("data", {}).get("status_code")
		if not status_code:
			# Fallback por si algo llega sin status
			import re

			m = re.search(
				r"Error\s+FacturAPI\s+(\d{3})",
				(response_data.get("error_message") or response_data.get("error") or ""),
			)
			status_code = int(m.group(1)) if m else 500

		# Log para confirmar qué se insertará
		frappe.logger().info({"tag": "PAC_LOG_BUILD", "status_code_to_insert": status_code})

		# Crear log entry usando campos arquitecturales correctos
		response_log = frappe.get_doc(
			{
				"doctype": "FacturAPI Response Log",
				"factura_fiscal_mexico": factura_fiscal,
				"operation_type": operation_type_mapping.get(operation_type, "Consulta Estado"),
				"timestamp": now_datetime(),
				"success": self._is_success_response(response_data),
				"status_code": status_code,
				"error_message": response_data.get("error_message") or response_data.get("error") or "",
				"facturapi_response": json.dumps(
					response_data.get("raw_response")
					if response_data.get("raw_response") is not None
					else None,
					default=str,
				),
				"user_role": frappe.session.user if frappe.session else "System",
				"ip_address": frappe.local.request.environ.get("REMOTE_ADDR", "localhost")
				if hasattr(frappe.local, "request") and frappe.local.request
				else "system",
				# Campos arquitectura resiliente
				"request_id": request_data.get("request_id", frappe.generate_hash(length=16)),
				"request_timestamp": request_data.get("request_timestamp", now_datetime()),
				"request_payload": json.dumps(request_data, default=str),
				"response_time_ms": response_data.get("response_time_ms", 0),
				"timeout_flag": response_data.get("timeout_flag", 0),
			}
		)

		response_log.insert()

		# Adjuntar JSON response como File para compatibilidad dfp_external_storage
		try:
			from frappe.utils.file_manager import save_file

			filename = f"pac_response_{sales_invoice_name}_{operation_type}.json"
			file_content = {
				"sales_invoice": sales_invoice_name,
				"operation_type": operation_type,
				"request_data": request_data,
				"response_data": response_data,
				"timestamp": now(),
			}

			save_file(
				fname=filename,
				content=json.dumps(file_content, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
				dt="FacturAPI Response Log",
				dn=response_log.name,
				is_private=1,
			)
		except Exception as file_error:
			# No fallar si no se puede adjuntar archivo - datos críticos ya están en BD
			frappe.log_error(
				f"Error adjuntando archivo PAC response: {file_error}", "PAC File Attachment Error"
			)

		# Manual commit required: PAC Response critical data must persist immediately to guarantee 0% loss
		frappe.db.commit()  # nosemgrep

		return response_log

	def _write_to_filesystem(
		self,
		sales_invoice_name: str,
		request_data: dict[str, Any],
		response_data: dict[str, Any],
		operation_type: str,
	) -> str:
		"""Escribir respuesta a filesystem como fallback."""
		timestamp = now().replace(" ", "_").replace(":", "-")
		filename = f"pac_response_{sales_invoice_name}_{operation_type}_{timestamp}.json"
		filepath = os.path.join(FALLBACK_DIR, filename)

		fallback_data = {
			"sales_invoice": sales_invoice_name,
			"operation_type": operation_type,
			"request_data": request_data,
			"response_data": response_data,
			"timestamp": now(),
			"recovery_status": "pending",
			"created_by": frappe.session.user if frappe.session else "System",
		}

		with open(filepath, "w") as f:
			json.dump(fallback_data, f, indent=2, default=str)

		return filepath

	def _update_factura_fiscal(
		self, sales_invoice_name: str, response_data: dict[str, Any], response_log_name: str
	):
		"""Actualizar Factura Fiscal Mexico con datos de respuesta."""
		try:
			factura_fiscal_name = frappe.db.get_value(
				"Factura Fiscal Mexico", {"sales_invoice": sales_invoice_name}, "name"
			)

			if not factura_fiscal_name:
				return

			# Determinar nuevo estado con reglas estrictas
			new_status, status_code, uuid = self._derive_status_from_response(response_data)

			# Preparar campos a actualizar - NORMALIZACIÓN CRÍTICA A MAYÚSCULAS
			normalized_status = _norm_status(new_status)
			update_fields = {
				"fm_last_response_log": response_log_name,
				"fm_last_pac_sync": now_datetime(),
				"fm_sync_status": _norm_status("synced" if normalized_status == "TIMBRADO" else "ERROR"),
				"fm_fiscal_status": normalized_status,
			}

			# Actualizar UUID solo si es exitoso
			if uuid:
				update_fields["fm_uuid"] = uuid
			elif new_status == "ERROR":
				# Limpiar UUID si hay error para higiene
				update_fields["fm_uuid"] = None

			# Actualizar URLs si están en respuesta
			if "download" in response_data:
				download = response_data["download"]
				if download.get("xml"):
					update_fields["fm_xml_url"] = download["xml"]
				if download.get("pdf"):
					update_fields["fm_pdf_url"] = download["pdf"]

			# Actualizar usando set_value para evitar triggers pesados
			for field, value in update_fields.items():
				frappe.db.set_value("Factura Fiscal Mexico", factura_fiscal_name, field, value)

			frappe.db.commit()

		except Exception as e:
			# No fallar si actualización Factura Fiscal falla - respuesta PAC ya guardada
			frappe.log_error(f"Error actualizando Factura Fiscal: {e!s}", "PAC Writer Update Error")

	def _is_success_response(self, response_data: dict[str, Any]) -> bool:
		"""Determinar si respuesta PAC fue exitosa."""
		# Convertir status_code a int si viene como string
		status_code = response_data.get("status_code", 0)
		if isinstance(status_code, str):
			try:
				status_code = int(status_code)
			except (ValueError, TypeError):
				status_code = 0

		# FacturAPI considera exitoso si tiene UUID o status válido
		return bool(
			response_data.get("id")
			or response_data.get("uuid")
			or response_data.get("status") == "valid"
			or (status_code >= 200 and status_code < 300)
		)

	def _determine_fiscal_status(self, response_data: dict[str, Any]) -> str | None:
		"""Determinar estado fiscal basado en respuesta PAC con reglas estrictas."""
		# REGLA ESTRICTA: TIMBRADO solo si success=True, status_code 200/201 Y uuid presente
		status, _status_code, _uuid = self._derive_status_from_response(response_data)
		return status

	def _derive_status_from_response(self, resp: dict[str, Any]) -> tuple[str, int, str]:
		"""Derivar (fiscal_status, status_code, uuid) con reglas canónicas estrictas."""
		import re

		from frappe.utils import cint

		ok = bool(resp.get("success"))

		# Extraer status_code del response o del mensaje de error
		status_code = resp.get("status_code")
		if not status_code:
			error_text = resp.get("error") or resp.get("error_message") or resp.get("raw_response") or ""
			m = re.search(r"FacturAPI\s+(\d{3})", error_text)
			status_code = cint(m.group(1)) if m else 500

		uuid = (resp.get("uuid") or "").strip()

		# REGLA CANÓNICA: TIMBRADO solo si éxito real + código válido + UUID
		if ok and status_code in (200, 201) and uuid:
			return "TIMBRADO", status_code, uuid

		# Cualquier otra combinación es ERROR
		return "ERROR", status_code or 500, ""

	def _schedule_recovery_task(self, fallback_file: str):
		"""Programar tarea de recovery para archivo fallback."""
		try:
			# Crear Fiscal Recovery Task para procesar archivo cuando BD vuelva
			recovery_task = frappe.get_doc(
				{
					"doctype": "Fiscal Recovery Task",
					"task_type": "filesystem_recovery",
					"reference_doctype": "FacturAPI Response Log",
					"reference_name": fallback_file,
					"priority": "high",
					"max_attempts": 5,
					"scheduled_time": add_to_date(now_datetime(), minutes=2),
					"created_by_system": 1,
					"recovery_data": json.dumps(
						{
							"fallback_file": fallback_file,
							"created_timestamp": now(),
							"recovery_type": "pac_response_fallback",
						}
					),
				}
			)

			recovery_task.insert()
			frappe.db.commit()

		except Exception:
			# Si no podemos crear recovery task, al menos el archivo está guardado
			pass


@frappe.whitelist()
def write_pac_response(
	sales_invoice_name: str, request_data: str, response_data: str, operation_type: str = "timbrado"
) -> dict[str, Any]:
	"""
	API pública para escribir respuesta PAC.
	Ultra-resiliente con filesystem fallback.

	Args:
		sales_invoice_name: Nombre Sales Invoice
		request_data: JSON string con datos request
		response_data: JSON string con respuesta FacturAPI
		operation_type: timbrado/cancelacion/consulta

	Returns:
		Dict con resultado operación
	"""
	try:
		# Parse JSON strings
		request_dict = json.loads(request_data) if isinstance(request_data, str) else request_data
		response_dict = json.loads(response_data) if isinstance(response_data, str) else response_data

		# Usar writer resiliente
		writer = PACResponseWriter()
		result = writer.write_pac_response(sales_invoice_name, request_dict, response_dict, operation_type)

		return result

	except Exception as e:
		frappe.log_error(f"Error en write_pac_response API: {traceback.format_exc()}", "PAC API Error")
		return {"success": False, "error": str(e), "timestamp": now()}


@frappe.whitelist()
def write_pac_timeout(
	sales_invoice_name: str, request_data: str, timeout_seconds: int = 30
) -> dict[str, Any]:
	"""
	Registrar timeout de PAC y programar recovery.

	Args:
		sales_invoice_name: Nombre Sales Invoice
		request_data: JSON string con datos request original
		timeout_seconds: Segundos de timeout

	Returns:
		Dict con resultado y recovery task creado
	"""
	try:
		request_dict = json.loads(request_data) if isinstance(request_data, str) else request_data

		# Crear respuesta synthetic para timeout
		timeout_response = {
			"timeout_flag": 1,  # Usar 1 para Check field
			"status_code": 0,
			"error_message": f"Timeout después de {timeout_seconds} segundos",
			"timeout_seconds": timeout_seconds,
			"timestamp": now(),
		}

		# Escribir usando writer resiliente
		writer = PACResponseWriter()
		result = writer.write_pac_response(
			sales_invoice_name, request_dict, timeout_response, "timeout_recovery"
		)

		# Crear recovery task específico para timeout
		try:
			from facturacion_mexico.facturacion_fiscal.doctype.fiscal_recovery_task.fiscal_recovery_task import (
				FiscalRecoveryTask,
			)

			recovery_task = FiscalRecoveryTask.create_timeout_recovery_task(
				response_log_name=result.get("response_log_name"),
				original_request_id=request_dict.get("request_id"),
			)

			result["recovery_task"] = recovery_task.name

		except Exception as recovery_error:
			result["recovery_error"] = str(recovery_error)

		return result

	except Exception as e:
		frappe.log_error(f"Error en write_pac_timeout: {traceback.format_exc()}", "PAC Timeout Error")
		return {"success": False, "error": str(e), "timestamp": now()}


@frappe.whitelist()
def recover_from_file(fallback_file_path: str) -> dict[str, Any]:
	"""
	Recuperar respuesta PAC desde archivo fallback cuando BD vuelve disponible.

	Args:
		fallback_file_path: Path al archivo fallback

	Returns:
		Dict con resultado recovery
	"""
	try:
		# Verificar que archivo existe
		if not os.path.exists(fallback_file_path):
			return {"success": False, "error": f"Archivo fallback no encontrado: {fallback_file_path}"}

		# Leer datos del archivo
		with open(fallback_file_path) as f:
			fallback_data = json.load(f)

		# Verificar que no ha sido ya recuperado
		if fallback_data.get("recovery_status") == "completed":
			return {
				"success": True,
				"message": "Archivo ya fue recuperado previamente",
				"already_recovered": True,
			}

		# Procesar con writer (que intentará BD primero)
		writer = PACResponseWriter()
		result = writer.write_pac_response(
			fallback_data["sales_invoice"],
			fallback_data["request_data"],
			fallback_data["response_data"],
			fallback_data["operation_type"],
		)

		if result["success"] and result.get("method") == "database":
			# Marcar archivo como recuperado
			fallback_data["recovery_status"] = "completed"
			fallback_data["recovered_at"] = now()
			fallback_data["response_log_name"] = result.get("response_log_name")

			with open(fallback_file_path, "w") as f:
				json.dump(fallback_data, f, indent=2, default=str)

			result["recovered_from_fallback"] = True

		return result

	except Exception as e:
		frappe.log_error(f"Error en recover_from_file: {traceback.format_exc()}", "PAC Recovery Error")
		return {"success": False, "error": str(e), "timestamp": now()}


@frappe.whitelist()
def get_fallback_files() -> list[dict[str, Any]]:
	"""
	Listar archivos fallback pendientes de recovery.

	Returns:
		Lista de archivos fallback con metadata
	"""
	try:
		if not os.path.exists(FALLBACK_DIR):
			return []

		fallback_files = []

		for filename in os.listdir(FALLBACK_DIR):
			if filename.startswith("pac_response_") and filename.endswith(".json"):
				filepath = os.path.join(FALLBACK_DIR, filename)

				try:
					with open(filepath) as f:
						data = json.load(f)

					fallback_files.append(
						{
							"filename": filename,
							"filepath": filepath,
							"sales_invoice": data.get("sales_invoice"),
							"operation_type": data.get("operation_type"),
							"timestamp": data.get("timestamp"),
							"recovery_status": data.get("recovery_status", "pending"),
							"file_size": os.path.getsize(filepath),
						}
					)

				except Exception:
					# Skip archivos corruptos
					continue

		# Ordenar por timestamp
		fallback_files.sort(key=lambda x: x["timestamp"], reverse=True)

		return fallback_files

	except Exception as e:
		frappe.log_error(f"Error listando archivos fallback: {e!s}", "PAC Fallback List Error")
		return []


# =============================================================================
# CONFIGURACIÓN DE ESTADOS FISCALES PARA JAVASCRIPT
# =============================================================================


@frappe.whitelist()
def get_fiscal_states_config():
	"""
	Obtener configuración completa de estados fiscales para JavaScript.

	Returns:
		dict: Configuración completa de estados fiscales
	"""
	from facturacion_mexico.config.fiscal_states_config import get_complete_config

	return get_complete_config()


@frappe.whitelist()
def get_fiscal_states():
	"""
	Obtener solo los estados fiscales principales.
	Endpoint simplificado para JavaScript.

	Returns:
		dict: Estados fiscales principales
	"""
	from facturacion_mexico.config.fiscal_states_config import FiscalStates

	return FiscalStates.to_dict()


@frappe.whitelist()
def validate_fiscal_state(state):
	"""
	Validar si un estado fiscal es válido.

	Args:
		state: Estado a validar

	Returns:
		dict: {"valid": bool, "state": str}
	"""
	from facturacion_mexico.config.fiscal_states_config import FiscalStates

	return {"valid": FiscalStates.is_valid(state), "state": state}


@frappe.whitelist()
def get_next_fiscal_state(current_state, action):
	"""
	Obtener el siguiente estado basado en la acción.

	Args:
		current_state: Estado actual
		action: Acción a realizar (timbrar, cancelar, etc.)

	Returns:
		dict: {"current": str, "action": str, "next": str|None}
	"""
	from facturacion_mexico.config.fiscal_states_config import FiscalStates

	next_state = FiscalStates.get_next_state(current_state, action)

	return {"current": current_state, "action": action, "next": next_state}
