"""
ResilienceArchitectureValidator - Sistema Validación Arquitectura Estados Fiscales
Implementación TAREA 2.3 según plan arquitectural resiliente

PROPÓSITO: Validar que la arquitectura resiliente esté funcionando correctamente
- Estados que deben cambiar (fm_fiscal_status, fm_sync_status, fm_sub_status)
- Variables actualizadas (PAC responses, timestamps, referencias)
- Servicios ejecutándose (Status Calculator, Recovery Worker, Sync Service)
- Flujos completos (Timbrado 4 etapas + Recovery)
"""

import json
from datetime import datetime
from typing import Any, Optional

import frappe
from frappe.utils import add_days, now


class ResilienceArchitectureValidator:
	"""
	Validador completo de la arquitectura resiliente de estados fiscales.

	Combina validación de arquitectura resiliente + monitoreo de flujos
	según especificación TAREA 2.2 del plan arquitectural.
	"""

	def __init__(self):
		"""Inicializar validador con configuraciones base."""
		self.validation_results = {
			"timestamp": now(),
			"validator_version": "1.0",
			"summary": {"total_validations": 0, "passed": 0, "failed": 0, "warnings": 0},
			"details": {},
		}

	def validate_complete_system(self, factura_fiscal_name: str) -> dict[str, Any]:
		"""
		Validación completa del sistema resiliente para una factura específica.

		Args:
		    factura_fiscal_name: Nombre del documento Factura Fiscal Mexico

		Returns:
		    Dict con resultados completos de validación
		"""
		try:
			frappe.logger().info(
				f"🔍 Iniciando validación completa sistema resiliente: {factura_fiscal_name}"
			)

			# 1. VALIDAR ESTADOS QUE DEBEN CAMBIAR
			status_validation = self.validate_status_transitions(factura_fiscal_name)
			self.validation_results["details"]["status_transitions"] = status_validation

			# 2. VALIDAR CADENA PAC RESPONSES
			pac_validation = self.validate_pac_response_chain(factura_fiscal_name)
			self.validation_results["details"]["pac_response_chain"] = pac_validation

			# 3. VALIDAR OPERACIONES SYNC
			sync_validation = self.validate_sync_operations(factura_fiscal_name)
			self.validation_results["details"]["sync_operations"] = sync_validation

			# 4. VALIDAR MECANISMOS RECOVERY
			recovery_validation = self.validate_recovery_mechanisms(factura_fiscal_name)
			self.validation_results["details"]["recovery_mechanisms"] = recovery_validation

			# 5. CALCULAR RESUMEN
			self._calculate_summary()

			frappe.logger().info(f"✅ Validación completa finalizada: {self.validation_results['summary']}")
			return self.validation_results

		except Exception as e:
			frappe.log_error(f"Error en validación completa: {e!s}", "Architecture Validator Error")
			return {"success": False, "error": str(e), "timestamp": now()}

	def validate_status_transitions(self, factura_fiscal_name: str) -> dict[str, Any]:
		"""
		Validar que los estados cambien correctamente según arquitectura.

		VALIDACIONES CRÍTICAS:
		- fm_fiscal_status progresión correcta
		- fm_sync_status actualizado
		- fm_sub_status coherente
		- Timestamps de cambios registrados
		"""
		validation = {
			"test_name": "Status Transitions Validation",
			"passed": True,
			"details": [],
			"warnings": [],
			"errors": [],
		}

		try:
			# Obtener estado actual Factura Fiscal
			fiscal_data = frappe.db.get_value(
				"Factura Fiscal Mexico",
				factura_fiscal_name,
				[
					"fm_fiscal_status",
					"fm_sync_status",
					"fm_sub_status",
					"fm_last_pac_sync",
					"modified",
					"creation",
				],
				as_dict=True,
			)

			if not fiscal_data:
				validation["passed"] = False
				validation["errors"].append(f"Factura Fiscal {factura_fiscal_name} no encontrada")
				return validation

			# VALIDACIÓN 1: fm_fiscal_status debe estar en valores válidos
			valid_statuses = [
				"Borrador",
				"Procesando",
				"Timbrada",
				"Error",
				"Cancelada",
				"Pendiente Cancelación",
				"Archivada",
			]
			current_status = fiscal_data.get("fm_fiscal_status")

			if current_status not in valid_statuses:
				validation["errors"].append(f"fm_fiscal_status inválido: {current_status}")
				validation["passed"] = False
			else:
				validation["details"].append(f"✅ fm_fiscal_status válido: {current_status}")

			# VALIDACIÓN 2: fm_sync_status coherencia
			sync_status = fiscal_data.get("fm_sync_status")
			valid_sync_statuses = ["pending", "synced", "error"]

			if sync_status not in valid_sync_statuses:
				validation["errors"].append(f"fm_sync_status inválido: {sync_status}")
				validation["passed"] = False
			else:
				validation["details"].append(f"✅ fm_sync_status válido: {sync_status}")

			# VALIDACIÓN 3: Timestamps lógicos
			last_sync = fiscal_data.get("fm_last_pac_sync")
			modified_time = fiscal_data.get("modified")

			if last_sync and modified_time:
				if last_sync > modified_time:
					validation["warnings"].append(
						"fm_last_pac_sync posterior a modified - posible inconsistencia"
					)

			# VALIDACIÓN 4: Obtener Sales Invoice asociado
			sales_invoice = frappe.db.get_value("Factura Fiscal Mexico", factura_fiscal_name, "sales_invoice")
			if sales_invoice:
				si_status = frappe.db.get_value("Sales Invoice", sales_invoice, "fm_fiscal_status")

				# Estados deben ser coherentes entre documentos
				if current_status != si_status:
					validation["warnings"].append(
						f"Estados desincronizados: FFM={current_status}, SI={si_status}"
					)
				else:
					validation["details"].append("✅ Estados sincronizados entre FFM y SI")

			self.validation_results["summary"]["total_validations"] += 1
			if validation["passed"]:
				self.validation_results["summary"]["passed"] += 1
			else:
				self.validation_results["summary"]["failed"] += 1

			if validation["warnings"]:
				self.validation_results["summary"]["warnings"] += len(validation["warnings"])

			return validation

		except Exception as e:
			validation["passed"] = False
			validation["errors"].append(f"Error en validación estados: {e!s}")
			return validation

	def validate_pac_response_chain(self, factura_fiscal_name: str) -> dict[str, Any]:
		"""
		Validar cadena completa de respuestas PAC.

		VALIDACIONES CRÍTICAS:
		- FacturAPI Response Log tiene registros
		- Respuestas están en orden cronológico
		- request_id, request_payload, response_time_ms poblados
		- timeout_flag usado correctamente
		"""
		validation = {
			"test_name": "PAC Response Chain Validation",
			"passed": True,
			"details": [],
			"warnings": [],
			"errors": [],
		}

		try:
			# Obtener TODOS los logs PAC para esta factura
			pac_logs = frappe.db.sql(
				"""
                SELECT
                    name, timestamp, operation_type, success,
                    request_id, request_payload, facturapi_response,
                    timeout_flag, status_code, response_time_ms
                FROM `tabFacturAPI Response Log`
                WHERE factura_fiscal_mexico = %s
                ORDER BY timestamp ASC
            """,
				(factura_fiscal_name,),
				as_dict=True,
			)

			if not pac_logs:
				validation["warnings"].append("No hay logs PAC encontrados - factura sin interacción PAC")
			else:
				validation["details"].append(f"✅ Encontrados {len(pac_logs)} logs PAC")

				# VALIDACIÓN 1: Arquitectura resiliente - campos obligatorios
				for i, log in enumerate(pac_logs):
					log_issues = []

					# request_id debe estar poblado
					if not log.get("request_id"):
						log_issues.append("request_id faltante")

					# request_payload debe estar poblado
					if not log.get("request_payload"):
						log_issues.append("request_payload faltante")

					# response_time_ms debe ser >= 0
					response_time = log.get("response_time_ms", 0)
					if response_time < 0:
						log_issues.append(f"response_time_ms inválido: {response_time}")

					if log_issues:
						validation["errors"].extend([f"Log {i+1}: {issue}" for issue in log_issues])
						validation["passed"] = False
					else:
						validation["details"].append(
							f"✅ Log {i+1}: Campos arquitectura resiliente correctos"
						)

				# VALIDACIÓN 2: Orden cronológico
				timestamps = [log["timestamp"] for log in pac_logs]
				if timestamps != sorted(timestamps):
					validation["warnings"].append("Logs PAC no están en orden cronológico")

				# VALIDACIÓN 3: timeout_flag lógico
				timeout_logs = [log for log in pac_logs if log.get("timeout_flag")]
				if timeout_logs:
					validation["details"].append(
						f"⚠️ {len(timeout_logs)} logs con timeout_flag - esperado en arquitectura resiliente"
					)

				# VALIDACIÓN 4: Último log debe reflejar estado actual
				latest_log = pac_logs[-1]
				factura_status = frappe.db.get_value(
					"Factura Fiscal Mexico", factura_fiscal_name, "fm_fiscal_status"
				)

				if latest_log.get("success") and factura_status == "Error":
					validation["warnings"].append("Último log exitoso pero estado actual es Error")
				elif not latest_log.get("success") and factura_status == "Timbrada":
					validation["warnings"].append("Último log falló pero estado actual es Timbrada")

			self.validation_results["summary"]["total_validations"] += 1
			if validation["passed"]:
				self.validation_results["summary"]["passed"] += 1
			else:
				self.validation_results["summary"]["failed"] += 1

			if validation["warnings"]:
				self.validation_results["summary"]["warnings"] += len(validation["warnings"])

			return validation

		except Exception as e:
			validation["passed"] = False
			validation["errors"].append(f"Error en validación cadena PAC: {e!s}")
			return validation

	def validate_sync_operations(self, factura_fiscal_name: str) -> dict[str, Any]:
		"""
		Validar que las operaciones de sincronización funcionen.

		VALIDACIONES CRÍTICAS:
		- Status Calculator funciona (función stateless)
		- Sync Service actualiza correctamente
		- Timestamps de última sincronización
		"""
		validation = {
			"test_name": "Sync Operations Validation",
			"passed": True,
			"details": [],
			"warnings": [],
			"errors": [],
		}

		try:
			# VALIDACIÓN 1: Probar Status Calculator (función stateless)
			try:
				from facturacion_mexico.facturacion_fiscal.utils import calculate_current_status

				calculated_status = calculate_current_status(factura_fiscal_name)

				if "status" in calculated_status and "source" in calculated_status:
					validation["details"].append("✅ Status Calculator funcionando correctamente")
					validation["details"].append(f"Estado calculado: {calculated_status.get('status')}")
				else:
					validation["errors"].append("Status Calculator retorna estructura inválida")
					validation["passed"] = False

			except Exception as calc_error:
				validation["errors"].append(f"Status Calculator falló: {calc_error!s}")
				validation["passed"] = False

			# VALIDACIÓN 2: Probar Sync Service
			try:
				from facturacion_mexico.facturacion_fiscal.utils import sync_status_to_sales_invoice

				# Probar sincronización (modo seguro - no modifica si no hay cambios)
				sync_result = sync_status_to_sales_invoice(factura_fiscal_name)

				if sync_result.get("success"):
					validation["details"].append("✅ Sync Service funcionando correctamente")
					if sync_result.get("synced"):
						validation["details"].append("Sincronización ejecutada")
					else:
						validation["details"].append("Sin cambios requeridos - consistente")
				else:
					validation["warnings"].append(f"Sync Service reporta error: {sync_result.get('error')}")

			except Exception as sync_error:
				validation["errors"].append(f"Sync Service falló: {sync_error!s}")
				validation["passed"] = False

			# VALIDACIÓN 3: Verificar timestamps sincronización
			fiscal_data = frappe.db.get_value(
				"Factura Fiscal Mexico",
				factura_fiscal_name,
				["fm_last_pac_sync", "fm_sync_status"],
				as_dict=True,
			)

			if fiscal_data:
				last_sync = fiscal_data.get("fm_last_pac_sync")
				sync_status = fiscal_data.get("fm_sync_status")

				if sync_status == "synced" and not last_sync:
					validation["warnings"].append("fm_sync_status=synced pero fm_last_pac_sync vacío")
				elif sync_status == "synced" and last_sync:
					validation["details"].append("✅ Timestamps sincronización coherentes")

			self.validation_results["summary"]["total_validations"] += 1
			if validation["passed"]:
				self.validation_results["summary"]["passed"] += 1
			else:
				self.validation_results["summary"]["failed"] += 1

			if validation["warnings"]:
				self.validation_results["summary"]["warnings"] += len(validation["warnings"])

			return validation

		except Exception as e:
			validation["passed"] = False
			validation["errors"].append(f"Error en validación sync operations: {e!s}")
			return validation

	def validate_recovery_mechanisms(self, factura_fiscal_name: str) -> dict[str, Any]:
		"""
		Validar mecanismos de recovery de la arquitectura.

		VALIDACIONES CRÍTICAS:
		- Recovery Worker tareas disponibles
		- Fallback filesystem (/tmp/facturacion_mexico_pac_fallback/)
		- Fiscal Recovery Task DocType funcional
		"""
		validation = {
			"test_name": "Recovery Mechanisms Validation",
			"passed": True,
			"details": [],
			"warnings": [],
			"errors": [],
		}

		try:
			# VALIDACIÓN 1: Verificar directorio fallback existe
			import os

			fallback_dir = "/tmp/facturacion_mexico_pac_fallback"

			if os.path.exists(fallback_dir):
				validation["details"].append("✅ Directorio fallback filesystem existe")

				# Verificar permisos
				if os.access(fallback_dir, os.W_OK):
					validation["details"].append("✅ Directorio fallback es escribible")
				else:
					validation["warnings"].append("Directorio fallback no es escribible")
			else:
				validation["warnings"].append("Directorio fallback no existe - se creará bajo demanda")

			# VALIDACIÓN 2: Verificar Recovery Worker funciones disponibles
			try:
				from facturacion_mexico.facturacion_fiscal.tasks import process_timeout_recovery

				validation["details"].append("✅ Recovery Worker (process_timeout_recovery) disponible")

				from facturacion_mexico.facturacion_fiscal.tasks import process_sync_errors

				validation["details"].append("✅ Recovery Worker (process_sync_errors) disponible")

				from facturacion_mexico.facturacion_fiscal.tasks import cleanup_old_logs

				validation["details"].append("✅ Recovery Worker (cleanup_old_logs) disponible")

			except ImportError as import_error:
				validation["errors"].append(f"Recovery Worker no disponible: {import_error!s}")
				validation["passed"] = False

			# VALIDACIÓN 3: Verificar Fiscal Recovery Task DocType
			try:
				if frappe.db.exists("DocType", "Fiscal Recovery Task"):
					validation["details"].append("✅ Fiscal Recovery Task DocType existe")

					# Verificar si hay tareas para esta factura
					recovery_tasks = frappe.db.count(
						"Fiscal Recovery Task", {"reference_doctype": "FacturAPI Response Log"}
					)
					validation["details"].append(f"📊 {recovery_tasks} recovery tasks en sistema")

				else:
					validation["warnings"].append("Fiscal Recovery Task DocType no encontrado")

			except Exception as doctype_error:
				validation["warnings"].append(f"Error verificando Fiscal Recovery Task: {doctype_error!s}")

			# VALIDACIÓN 4: Probar PAC Response Writer resilience
			try:
				from facturacion_mexico.facturacion_fiscal.api import get_fallback_files

				fallback_files = get_fallback_files()
				validation["details"].append(f"📊 {len(fallback_files)} archivos fallback en sistema")

			except Exception as fallback_error:
				validation["warnings"].append(f"Error accediendo fallback files: {fallback_error!s}")

			self.validation_results["summary"]["total_validations"] += 1
			if validation["passed"]:
				self.validation_results["summary"]["passed"] += 1
			else:
				self.validation_results["summary"]["failed"] += 1

			if validation["warnings"]:
				self.validation_results["summary"]["warnings"] += len(validation["warnings"])

			return validation

		except Exception as e:
			validation["passed"] = False
			validation["errors"].append(f"Error en validación recovery mechanisms: {e!s}")
			return validation

	def _calculate_summary(self):
		"""Calcular resumen final de validación."""
		details = self.validation_results["details"]

		# Contar validaciones por resultado
		all_validations = [details[key] for key in details if isinstance(details[key], dict)]

		for validation in all_validations:
			if validation.get("warnings"):
				self.validation_results["summary"]["warnings"] += len(validation["warnings"])

	def validate_shadow_mode_batch(
		self, start_invoice: str = "ACC-SINV-2025-00917", count: int = 20
	) -> dict[str, Any]:
		"""
		Validar lote completo de facturas SHADOW MODE.

		Args:
		    start_invoice: Primera factura del lote
		    count: Número de facturas a validar

		Returns:
		    Dict con resultados agregados de validación
		"""
		batch_results = {
			"timestamp": now(),
			"batch_summary": {
				"total_invoices": 0,
				"validated_invoices": 0,
				"failed_invoices": 0,
				"total_validations": 0,
				"total_passed": 0,
				"total_failed": 0,
				"total_warnings": 0,
			},
			"individual_results": [],
		}

		try:
			# Obtener las facturas SHADOW MODE
			shadow_invoices = frappe.db.sql(
				"""
                SELECT si.name, si.fm_factura_fiscal_mx
                FROM `tabSales Invoice` si
                WHERE si.name LIKE 'ACC-SINV-2025-%'
                AND si.creation >= '2025-08-06'
                ORDER BY si.name
                LIMIT %s
            """,
				(count,),
				as_dict=True,
			)

			batch_results["batch_summary"]["total_invoices"] = len(shadow_invoices)

			for invoice_data in shadow_invoices:
				if invoice_data.get("fm_factura_fiscal_mx"):
					# Validar cada factura individual
					individual_result = self.validate_complete_system(invoice_data["fm_factura_fiscal_mx"])

					batch_results["individual_results"].append(
						{
							"sales_invoice": invoice_data["name"],
							"factura_fiscal": invoice_data["fm_factura_fiscal_mx"],
							"validation_result": individual_result,
						}
					)

					# Agregar a contadores
					if individual_result.get("summary"):
						summary = individual_result["summary"]
						batch_results["batch_summary"]["total_validations"] += summary.get(
							"total_validations", 0
						)
						batch_results["batch_summary"]["total_passed"] += summary.get("passed", 0)
						batch_results["batch_summary"]["total_failed"] += summary.get("failed", 0)
						batch_results["batch_summary"]["total_warnings"] += summary.get("warnings", 0)

						if summary.get("failed", 0) == 0:
							batch_results["batch_summary"]["validated_invoices"] += 1
						else:
							batch_results["batch_summary"]["failed_invoices"] += 1
				else:
					batch_results["individual_results"].append(
						{
							"sales_invoice": invoice_data["name"],
							"factura_fiscal": None,
							"validation_result": {"error": "No tiene Factura Fiscal asociada"},
						}
					)
					batch_results["batch_summary"]["failed_invoices"] += 1

			frappe.logger().info(f"🔍 Validación SHADOW MODE completada: {batch_results['batch_summary']}")
			return batch_results

		except Exception as e:
			frappe.log_error(f"Error en validación batch SHADOW MODE: {e!s}", "Batch Validation Error")
			return {"success": False, "error": str(e), "timestamp": now()}


# API pública para uso desde bench execute
@frappe.whitelist()
def validate_resilient_architecture(factura_fiscal_name: str) -> dict[str, Any]:
	"""
	API pública para validar arquitectura resiliente de una factura específica.

	Uso: bench --site facturacion.dev execute facturacion_mexico.validation.architecture_validator.validate_resilient_architecture --args "['FFM-nombre']"
	"""
	validator = ResilienceArchitectureValidator()
	return validator.validate_complete_system(factura_fiscal_name)


@frappe.whitelist()
def validate_shadow_mode_invoices() -> dict[str, Any]:
	"""
	API pública para validar todas las facturas SHADOW MODE (20 facturas).

	Uso: bench --site facturacion.dev execute facturacion_mexico.validation.architecture_validator.validate_shadow_mode_invoices
	"""
	validator = ResilienceArchitectureValidator()
	return validator.validate_shadow_mode_batch()
