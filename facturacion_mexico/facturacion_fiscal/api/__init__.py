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
# Usar directorio sites para compatibilidad multi-sitio
FALLBACK_DIR = None  # Se calcula dinámicamente por sitio


def _get_fallback_dir():
	"""Calcular directorio fallback por sitio para compatibilidad multi-sitio."""
	try:
		base = frappe.utils.get_site_path("private", "files", "facturacion_mexico_pac_fallback")
		frappe.create_folder(base)
		return base
	except Exception:
		# Fallback a directorio temporal como último recurso
		fallback_path = "/tmp/facturacion_mexico_pac_fallback"
		os.makedirs(fallback_path, exist_ok=True)
		return fallback_path


class FiscalCorrelationError(frappe.ValidationError):
	"""La respuesta del PAC no puede asociarse de forma inequívoca al FFM de origen.

	No debe degradarse al fallback de filesystem: representa una contradicción de
	integridad fiscal, no una indisponibilidad de BD.
	"""


def _alerta_correlacion_critica(motivo: str, contexto: dict) -> None:
	"""Registrar alerta crítica de correlación fiscal (Corrección 1).

	Se invoca cuando la respuesta del PAC no puede asociarse de forma inequívoca
	al FFM que inició la operación. No modifica ningún documento.
	"""
	try:
		frappe.log_error(
			message=json.dumps({"motivo": motivo, "contexto": contexto}, default=str, indent=2),
			title="PAC Correlación Crítica FFM",
		)
	except Exception:
		# El logging nunca debe enmascarar el error de correlación original.
		pass


def _extract_response_identifiers(response_data: dict) -> tuple[str, str]:
	"""Extraer (uuid, facturapi_id) de una respuesta PAC, si están presentes.

	Busca tanto a nivel superior como dentro de raw_response. Devuelve cadenas
	vacías cuando el identificador no viene en la respuesta (p. ej. timbrado que
	aún no devuelve UUID, o errores). La comparación de contradicción solo aplica
	cuando ambos lados (FFM y respuesta) tienen valor.
	"""
	if not isinstance(response_data, dict):
		return "", ""
	raw = response_data.get("raw_response")
	raw = raw if isinstance(raw, dict) else {}
	uuid = (response_data.get("uuid") or raw.get("uuid") or "").strip()
	facturapi_id = (
		response_data.get("facturapi_id") or response_data.get("id") or raw.get("id") or ""
	).strip()
	return uuid, facturapi_id


def _derive_sync_status_from_response(response_data: dict, operation_type: str) -> str | None:
	"""Derivar fm_sync_status según si el PAC dio una respuesta CONCLUYENTE persistida (7A1).

	Semántica: fm_sync_status indica si el FFM local refleja de forma verificable la última
	respuesta conocida del PAC. NO se confunde con el estado fiscal (PENDIENTE_CANCELACION es
	'synced' si la respuesta del PAC ya se reflejó localmente).

	Devuelve:
	- 'synced'  → hubo una respuesta concluyente del PAC (éxito, rechazo conocido o estado de
	  cancelación) interpretable; el estado local la refleja.
	- 'pending' → la respuesta es realmente inconclusa (timeout o sin información suficiente).
	- None      → la llamada NO representa una respuesta del PAC (fallback de logging de eventos
	  desde create_fiscal_event); en ese caso el caller NO debe alterar fm_sync_status.
	"""
	# Fallback no-PAC (create_fiscal_event → _log_event_to_response_log): no es una respuesta
	# del PAC. operation_type viene como "fiscal_event_*". No tocar fm_sync_status.
	if isinstance(operation_type, str) and operation_type.startswith("fiscal_event_"):
		return None

	if not isinstance(response_data, dict):
		return "pending"

	# Timeout u operación realmente inconclusa.
	if response_data.get("timeout_flag"):
		return "pending"

	# Identificadores del CFDI o estado de cancelación (top-level o en raw_response) → el PAC dio
	# una respuesta concluyente interpretable.
	uuid, facturapi_id = _extract_response_identifiers(response_data)
	if uuid or facturapi_id:
		return "synced"
	raw = response_data.get("raw_response")
	raw = raw if isinstance(raw, dict) else {}
	for d in (response_data, raw):
		if d.get("status") or d.get("cancellation_status"):
			return "synced"

	# Código HTTP: 2xx (aceptado) y 4xx (rechazo conocido del PAC) son concluyentes. 5xx (error de
	# servidor/transporte) y 0/ausente NO son concluyentes solo por tener código → no marcar synced.
	sc = response_data.get("status_code")
	try:
		code = int(sc) if sc is not None else 0
	except (TypeError, ValueError):
		code = 0
	if 200 <= code < 500:
		return "synced"
	if code >= 500:
		return "pending"

	# Sin código concluyente: solo un 'success' explícitamente True cuenta como concluyente.
	# success=False sin 4xx (timeout/transporte) o sin información → realmente pendiente.
	if response_data.get("success") is True:
		return "synced"

	return "pending"


def _derive_http_status(data: dict, default=500) -> int:
	# Éxito explícito → 200 fijo, ignorar 'status_code' dentro del payload y cualquier regex
	if isinstance(data, dict) and data.get("success") is True:
		return 200

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
			fallback_dir = _get_fallback_dir()
			Path(fallback_dir).mkdir(parents=True, exist_ok=True)
			os.chmod(fallback_dir, 0o700)  # Owner-only permissions for security
		except Exception as e:
			# Incluso si falla crear directorio, continuamos
			frappe.log_error(f"Error creando directorio fallback: {e!s}", "PAC Writer Fallback")

	def write_pac_response(
		self,
		sales_invoice_name: str,
		request_data: dict[str, Any],
		response_data: dict[str, Any],
		operation_type: str = "timbrado",
		*,
		factura_fiscal_name: str | None = None,
	) -> dict[str, Any]:
		"""
		Escribir respuesta PAC con máxima resilencia.

		Args:
			sales_invoice_name: Nombre de Sales Invoice (solo para validación cruzada)
			request_data: Datos del request enviado
			response_data: Respuesta completa de FacturAPI
			operation_type: Tipo operación (timbrado/cancelacion/consulta)
			factura_fiscal_name: Nombre EXPLÍCITO del FFM que inició la operación.
				Obligatorio. La respuesta se asocia exclusivamente a este FFM —
				nunca se resuelve por Sales Invoice. Ver Corrección 1 (integridad fiscal).

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

		# Corrección 2: el ESTADO FISCAL se persiste PRIMERO e independientemente del
		# Response Log. El log es auditoría; su fallo no debe revertir ni ocultar el
		# resultado fiscal confirmado por el PAC, ni degradar a filesystem.

		# PASO 1: Actualizar y persistir el FFM (estado fiscal, UUID, facturapi_id,
		# fm_sync_status). Valida correlación estricta (Corrección 1) y commitea el FFM.
		# - FiscalCorrelationError → propaga (no se toca nada).
		# - Otro fallo de actualización → _update_factura_fiscal alerta y relanza:
		#   NO se crea el Response Log y NO se presenta como persistido (punto 3).
		self._update_factura_fiscal(
			sales_invoice_name,
			response_data,
			None,  # fm_last_response_log se asigna después, cuando el log exista
			operation_type,
			factura_fiscal_name=factura_fiscal_name,
		)
		result["success"] = True
		result["method"] = "database"
		result["fiscal_updated"] = True

		# PASO 2: Response Log de auditoría, AISLADO con savepoint. Si su inserción
		# falla, se revierte SOLO el log (rollback al savepoint); el FFM ya persistido
		# permanece intacto. No se relanza y no se degrada a filesystem (prueba 4).
		try:
			frappe.db.savepoint("pac_audit_log")
			response_log = self._write_to_database(
				sales_invoice_name,
				request_data,
				response_data,
				operation_type,
				factura_fiscal_name=factura_fiscal_name,
			)
			result["response_log_name"] = response_log.name

			# PASO 3: enlazar la referencia de auditoría tras crear el log. Su fallo no
			# revierte ni el FFM fiscal ni el log ya creado.
			try:
				frappe.db.set_value(
					"Factura Fiscal Mexico",
					factura_fiscal_name,
					"fm_last_response_log",
					response_log.name,
				)
			except Exception as ref_error:
				result["audit_log_ref_failed"] = True
				_alerta_correlacion_critica(
					"No se pudo enlazar fm_last_response_log; FFM y Response Log conservados",
					{
						"factura_fiscal_name": factura_fiscal_name,
						"response_log": response_log.name,
						"error": str(ref_error),
					},
				)

		except FiscalCorrelationError:
			# El log también valida correlación; si contradice, propagar.
			raise
		except Exception as log_error:
			frappe.db.rollback(save_point="pac_audit_log")
			result["audit_log_failed"] = True
			result["errors"].append(f"Audit log error: {log_error!s}")
			_alerta_correlacion_critica(
				"Fallo al guardar Response Log; estado fiscal ya persistido se conserva",
				{
					"factura_fiscal_name": factura_fiscal_name,
					"sales_invoice": sales_invoice_name,
					"operation_type": operation_type,
					"error": str(log_error),
				},
			)
			frappe.log_error(
				f"Error guardando Response Log (estado fiscal conservado): {traceback.format_exc()}",
				"PAC Writer Audit Log Error",
			)

		return result

	def _resolve_validated_ffm(
		self,
		factura_fiscal_name: str | None,
		sales_invoice_name: str,
		response_data: dict[str, Any],
		operation_type: str,
	) -> str:
		"""Validar y devolver el FFM EXPLÍCITO que inició la operación.

		Corrección 1 — Correlación estricta por FFM.name:
		- Nunca resuelve el FFM por Sales Invoice ni por UUID/facturapi_id.
		- Si falta el nombre, el FFM no existe, pertenece a otra SI, o hay
		  contradicción de UUID/facturapi_id → registra alerta crítica y lanza
		  error controlado SIN modificar ningún documento.

		Returns:
			El factura_fiscal_name validado.
		"""
		if not factura_fiscal_name:
			_alerta_correlacion_critica(
				"Falta factura_fiscal_name en persistencia de respuesta PAC",
				{
					"sales_invoice": sales_invoice_name,
					"operation_type": operation_type,
				},
			)
			frappe.throw(
				_("No se puede registrar la respuesta del PAC: falta el FFM de origen."),
				title=_("Correlación fiscal requerida"),
				exc=FiscalCorrelationError,
			)

		ffm = frappe.db.get_value(
			"Factura Fiscal Mexico",
			factura_fiscal_name,
			["name", "sales_invoice", "fm_uuid", "facturapi_id"],
			as_dict=True,
		)
		if not ffm:
			_alerta_correlacion_critica(
				"FFM explícito inexistente en persistencia de respuesta PAC",
				{
					"factura_fiscal_name": factura_fiscal_name,
					"sales_invoice": sales_invoice_name,
					"operation_type": operation_type,
				},
			)
			frappe.throw(
				_("No se puede registrar la respuesta del PAC: el FFM {0} no existe.").format(
					factura_fiscal_name
				),
				title=_("Correlación fiscal inválida"),
				exc=FiscalCorrelationError,
			)

		# El FFM debe pertenecer a la Sales Invoice indicada (cuando se provee).
		if sales_invoice_name and ffm.get("sales_invoice") and ffm["sales_invoice"] != sales_invoice_name:
			_alerta_correlacion_critica(
				"FFM explícito pertenece a otra Sales Invoice",
				{
					"factura_fiscal_name": factura_fiscal_name,
					"ffm_sales_invoice": ffm.get("sales_invoice"),
					"sales_invoice_param": sales_invoice_name,
					"operation_type": operation_type,
				},
			)
			frappe.throw(
				_("No se puede registrar la respuesta del PAC: el FFM {0} pertenece a otra factura.").format(
					factura_fiscal_name
				),
				title=_("Correlación fiscal inválida"),
				exc=FiscalCorrelationError,
			)

		# Contradicción de UUID/facturapi_id: solo se valida cuando AMBOS lados
		# tienen valor (en timbrado el FFM aún no los tiene → no aplica).
		resp_uuid, resp_facturapi_id = _extract_response_identifiers(response_data)
		if resp_uuid and ffm.get("fm_uuid") and resp_uuid != ffm["fm_uuid"]:
			_alerta_correlacion_critica(
				"UUID de la respuesta PAC no coincide con el FFM explícito",
				{
					"factura_fiscal_name": factura_fiscal_name,
					"ffm_uuid": ffm.get("fm_uuid"),
					"response_uuid": resp_uuid,
					"operation_type": operation_type,
				},
			)
			frappe.throw(
				_("Respuesta del PAC con UUID contradictorio para el FFM {0}.").format(factura_fiscal_name),
				title=_("Correlación fiscal inválida"),
				exc=FiscalCorrelationError,
			)
		if resp_facturapi_id and ffm.get("facturapi_id") and resp_facturapi_id != ffm["facturapi_id"]:
			_alerta_correlacion_critica(
				"facturapi_id de la respuesta PAC no coincide con el FFM explícito",
				{
					"factura_fiscal_name": factura_fiscal_name,
					"ffm_facturapi_id": ffm.get("facturapi_id"),
					"response_facturapi_id": resp_facturapi_id,
					"operation_type": operation_type,
				},
			)
			frappe.throw(
				_("Respuesta del PAC con facturapi_id contradictorio para el FFM {0}.").format(
					factura_fiscal_name
				),
				title=_("Correlación fiscal inválida"),
				exc=FiscalCorrelationError,
			)

		return ffm["name"]

	def _write_to_database(
		self,
		sales_invoice_name: str,
		request_data: dict[str, Any],
		response_data: dict[str, Any],
		operation_type: str,
		*,
		factura_fiscal_name: str | None = None,
	) -> Any | None:
		"""Escribir a FacturAPI Response Log en BD."""
		# Correlación estricta: el FFM es SIEMPRE el explícito de la operación.
		# Nunca se resuelve por Sales Invoice.
		factura_fiscal = self._resolve_validated_ffm(
			factura_fiscal_name, sales_invoice_name, response_data, operation_type
		)

		# Mapear operation_type a valores válidos del DocType (ARQUITECTURA RESILIENTE)
		operation_type_mapping = {
			"timbrado": "Timbrado",
			"cancelacion": "Solicitud Cancelación",
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

		success = bool(response_data.get("success"))

		if success:
			# ÉXITO REAL → NO usar regex ni derivaciones
			status_code = 200
			error_message = ""
		else:
			# SOLO en error usar derivación/regex
			status_code = response_data.get("status_code")
			if not status_code:
				# mantener tu método auxiliar si lo tienes:
				try:
					status_code = _derive_http_status(response_data, default=500)
				except Exception:
					status_code = 500
			error_message = (
				response_data.get("error_message")
				or response_data.get("error")
				or "Error desconocido del PAC"
			)

		# Guardar JSON completo SIEMPRE que exista, y si no, raw_response; nunca null en éxito
		full_payload = response_data.get("raw_response")
		if full_payload is None:
			full_payload = response_data

		facturapi_response_json = json.dumps(full_payload, ensure_ascii=False, default=str)

		# Log para confirmar qué se insertará
		frappe.logger().info(
			{"tag": "PAC_LOG_BUILD", "status_code_to_insert": status_code, "success": success}
		)

		# Crear log entry usando campos arquitecturales correctos
		response_log = frappe.get_doc(
			{
				"doctype": "FacturAPI Response Log",
				"factura_fiscal_mexico": factura_fiscal,
				"operation_type": operation_type_mapping.get(operation_type, "Consulta Estado"),
				"timestamp": now_datetime(),
				"success": 1 if success else 0,
				"status_code": status_code,
				"error_message": error_message,
				"facturapi_response": facturapi_response_json,
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

		response_log.insert(ignore_permissions=True)

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
		*,
		factura_fiscal_name: str | None = None,
	) -> str:
		"""Escribir respuesta a filesystem como fallback."""
		timestamp = now().replace(" ", "_").replace(":", "-")
		filename = f"pac_response_{sales_invoice_name}_{operation_type}_{timestamp}.json"
		fallback_dir = _get_fallback_dir()
		filepath = os.path.join(fallback_dir, filename)

		fallback_data = {
			"sales_invoice": sales_invoice_name,
			# FFM explícito de origen — necesario para recuperar con correlación estricta.
			"factura_fiscal_name": factura_fiscal_name,
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
		self,
		sales_invoice_name: str,
		response_data: dict[str, Any],
		response_log_name: str,
		operation_type: str = "Timbrado",
		*,
		factura_fiscal_name: str | None = None,
	):
		"""Actualizar Factura Fiscal Mexico con datos de respuesta."""
		try:
			# Correlación estricta: actualizar SOLO el FFM explícito de la operación.
			# Nunca se resuelve por Sales Invoice.
			factura_fiscal_name = self._resolve_validated_ffm(
				factura_fiscal_name, sales_invoice_name, response_data, operation_type
			)

			# Normalize operation_type to match _derive_status_from_response expectations
			_normalized_op = {
				"timbrado": "Timbrado",
				"cancelacion": "Solicitud Cancelación",
				"consulta": "Consulta Estado",
				"timeout_recovery": "Consulta Estado",
			}.get(operation_type, operation_type)
			new_status, _status_code, uuid = self._derive_status_from_response(response_data, _normalized_op)

			# Preparar campos a actualizar - NORMALIZACIÓN CRÍTICA A MAYÚSCULAS
			# Corrección 2: NO se establece aquí fm_last_response_log. El estado fiscal
			# debe persistir ANTES e independientemente del Response Log; la referencia
			# al log se asigna después, cuando el log ya existe.
			# Corrección 7A1: fm_sync_status refleja si hubo una respuesta CONCLUYENTE del PAC
			# persistida (no `response_data.get("success")`, que el raw de cancelación no trae).
			# Si la llamada es un fallback no-PAC (fiscal_event_*), no se altera fm_sync_status.
			# M1 (CodeRabbit): tampoco se refresca fm_last_pac_sync en eventos internos no-PAC;
			# hacerlo haría que un fallback interno parezca una sincronización fresca con el PAC.
			_is_fiscal_event = isinstance(operation_type, str) and operation_type.startswith("fiscal_event_")
			update_fields = {}
			if not _is_fiscal_event:
				update_fields["fm_last_pac_sync"] = now_datetime()
			sync_status = _derive_sync_status_from_response(response_data, operation_type)
			if sync_status is not None:
				update_fields["fm_sync_status"] = sync_status

			# Solo actualizar estado fiscal si la operación lo requiere (new_status no es None)
			if new_status is not None:
				normalized_status = _norm_status(new_status)
				update_fields["status"] = normalized_status

			# Actualizar UUID solo si es exitoso
			if uuid:
				update_fields["fm_uuid"] = uuid
			elif new_status == "ERROR":
				# Limpiar UUID si hay error de timbrado para higiene
				update_fields["fm_uuid"] = None

			# Corrección 6B0: en timbrado exitoso, persistir también facturapi_id si la respuesta
			# lo trae (top-level o dentro de raw_response). Se limita a TIMBRADO para no alterar
			# la semántica de cancelación/consulta.
			if new_status == "TIMBRADO":
				_resp_uuid, facturapi_id = _extract_response_identifiers(response_data)
				if facturapi_id:
					update_fields["facturapi_id"] = facturapi_id

			# Actualizar URLs si están en respuesta
			if "download" in response_data:
				download = response_data["download"]
				if download.get("xml"):
					update_fields["fm_xml_url"] = download["xml"]
				if download.get("pdf"):
					update_fields["fm_pdf_url"] = download["pdf"]

				# Email automático ahora se maneja directamente en timbrado_api.py durante el timbrado

			# Actualizar usando set_value para evitar triggers pesados
			for field, value in update_fields.items():
				frappe.db.set_value("Factura Fiscal Mexico", factura_fiscal_name, field, value)

			# Persistir el estado fiscal confirmado por el PAC ANTES e independientemente
			# del Response Log (Corrección 2). Commit ya existente — no se agrega ninguno.
			frappe.db.commit()

		except FiscalCorrelationError:
			# Contradicción de correlación (Corrección 1): propagar sin tocar nada.
			raise
		except Exception as e:
			# Corrección 2: un fallo al persistir el estado fiscal NO debe ocultarse ni
			# presentarse como operación correcta. Se alerta de forma crítica y se relanza
			# para que el orquestador NO cree el Response Log ni reporte éxito.
			_alerta_correlacion_critica(
				"Fallo al actualizar el estado fiscal del FFM tras respuesta PAC",
				{
					"factura_fiscal_name": factura_fiscal_name,
					"sales_invoice": sales_invoice_name,
					"operation_type": operation_type,
					"error": str(e),
				},
			)
			frappe.log_error(f"Error actualizando Factura Fiscal: {e!s}", "PAC Writer Update Error")
			raise

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
		status, _status_code, _uuid = self._derive_status_from_response(response_data, "timbrado")
		return status

	def _derive_status_from_response(
		self, resp: dict[str, Any], operation_type: str = "timbrado"
	) -> tuple[str, int, str]:
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

		# Corrección 6B0: el UUID del timbrado llega dentro de raw_response, no solo a nivel
		# superior. Reutilizar el extractor normalizado evita derivar ERROR en un timbrado
		# exitoso por no encontrar el UUID en el nivel equivocado.
		uuid, _facturapi_id = _extract_response_identifiers(resp)

		# REGLA CANÓNICA POR TIPO DE OPERACIÓN
		if operation_type == "Timbrado":
			# Para timbrado: TIMBRADO solo si éxito real + código válido + UUID
			if ok and status_code in (200, 201) and uuid:
				return "TIMBRADO", status_code, uuid
			# Error en timbrado = ERROR
			return "ERROR", status_code or 500, ""

		elif operation_type == "Solicitud Cancelación":
			# Para cancelación: éxito = CANCELADO, error = mantener estado actual (no cambiar)
			if ok and status_code in (200, 201):
				return "CANCELADO", status_code, ""
			# ERROR EN CANCELACIÓN: NO cambiar estado fiscal (return None = no update)
			return None, status_code or 500, ""

		else:
			# Otras operaciones (consulta, etc): no cambian estado fiscal
			return None, status_code or 500, ""

	def _schedule_recovery_task(self, fallback_file: str):
		"""No-op: recovery tasks removed. Fallback file serves as the record."""
		pass


@frappe.whitelist()
def write_pac_response(
	sales_invoice_name: str,
	request_data: str,
	response_data: str,
	operation_type: str = "timbrado",
	factura_fiscal_name: str | None = None,
) -> dict[str, Any]:
	"""
	API pública para escribir respuesta PAC.
	Ultra-resiliente con filesystem fallback.

	Args:
		sales_invoice_name: Nombre Sales Invoice (validación cruzada)
		request_data: JSON string con datos request
		response_data: JSON string con respuesta FacturAPI
		operation_type: timbrado/cancelacion/consulta
		factura_fiscal_name: Nombre EXPLÍCITO del FFM que inició la operación
			(obligatorio para correlación estricta — Corrección 1).

	Returns:
		Dict con resultado operación
	"""
	try:
		# Parse JSON strings
		request_dict = json.loads(request_data) if isinstance(request_data, str) else request_data
		response_dict = json.loads(response_data) if isinstance(response_data, str) else response_data

		# Usar writer resiliente
		writer = PACResponseWriter()
		result = writer.write_pac_response(
			sales_invoice_name,
			request_dict,
			response_dict,
			operation_type,
			factura_fiscal_name=factura_fiscal_name,
		)

		return result

	except FiscalCorrelationError:
		# Corrección 6A: la correlación crítica (Corrección 1) NO se degrada a {success:False}.
		# Se propaga para que el orquestador detenga el flujo (no reintentar, no continuar a
		# FASE 3, no re-llamar al PAC). La evidencia técnica ya quedó en la alerta del writer.
		raise
	except Exception as e:
		frappe.log_error(f"Error en write_pac_response API: {traceback.format_exc()}", "PAC API Error")
		return {"success": False, "error": str(e), "timestamp": now()}


@frappe.whitelist()
def write_pac_timeout(
	sales_invoice_name: str,
	request_data: str,
	timeout_seconds: int = 30,
	factura_fiscal_name: str | None = None,
) -> dict[str, Any]:
	"""
	Registrar timeout de PAC y programar recovery.

	Args:
		sales_invoice_name: Nombre Sales Invoice (validación cruzada)
		request_data: JSON string con datos request original
		timeout_seconds: Segundos de timeout
		factura_fiscal_name: Nombre EXPLÍCITO del FFM de origen (obligatorio para
			correlación estricta — Corrección 1).

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
			sales_invoice_name,
			request_dict,
			timeout_response,
			"timeout_recovery",
			factura_fiscal_name=factura_fiscal_name,
		)

		return result

	except FiscalCorrelationError:
		# Corrección 6A (consistencia): una contradicción de correlación debe DETENER el flujo,
		# no degradarse a {success: False} como un fallo ordinario de escritura de timeout.
		raise
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

		# Procesar con writer (que intentará BD primero). El FFM explícito viaja en
		# el archivo fallback; si falta (archivos previos a Corrección 1), el writer
		# generará alerta crítica de correlación en lugar de resolver por SI.
		writer = PACResponseWriter()
		result = writer.write_pac_response(
			fallback_data["sales_invoice"],
			fallback_data["request_data"],
			fallback_data["response_data"],
			fallback_data["operation_type"],
			factura_fiscal_name=fallback_data.get("factura_fiscal_name"),
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
		fallback_dir = _get_fallback_dir()
		if not os.path.exists(fallback_dir):
			return []

		fallback_files = []

		for filename in os.listdir(fallback_dir):
			if filename.startswith("pac_response_") and filename.endswith(".json"):
				filepath = os.path.join(fallback_dir, filename)

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
