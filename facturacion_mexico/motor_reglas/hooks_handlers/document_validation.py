"""
Document Validation Hooks - Sprint 4 Semana 2
Hooks para ejecutar reglas de validación en eventos de documentos
"""

import json
import time

import frappe
from frappe import _


def execute_validation_rules(doc, method):
	"""Ejecutar reglas de validación en documento."""
	try:
		# Verificar si el DocType tiene reglas configuradas
		doctype = doc.doctype

		# Obtener reglas activas para este DocType
		rules = frappe.get_all(
			"Fiscal Validation Rule",
			filters={
				"apply_to_doctype": doctype,
				"is_active": 1,
				"rule_type": "Validation",
				"docstatus": ["!=", 2],
			},
			fields=["name", "rule_name", "rule_code", "priority", "severity"],
			order_by="priority ASC, creation ASC",
		)

		if not rules:
			# No hay reglas, actualizar status como pasado
			update_validation_tracking(doc, "Passed", [])
			return

		# Ejecutar reglas
		execution_results = []
		has_errors = False
		has_warnings = False
		total_execution_time = 0

		for rule_info in rules:
			try:
				rule_doc = frappe.get_doc("Fiscal Validation Rule", rule_info.name)

				start_time = time.time()
				result = rule_doc.execute_rule(doc)
				execution_time = (time.time() - start_time) * 1000

				total_execution_time += execution_time

				# Preparar resultado para tracking
				rule_result = {
					"rule_name": rule_info.rule_name,
					"rule_code": rule_info.rule_code,
					"severity": rule_info.severity,
					"success": result.get("success", False),
					"executed": result.get("executed", False),
					"conditions_met": result.get("conditions_met", False),
					"execution_time": execution_time,
					"timestamp": frappe.utils.now_datetime().isoformat(),
				}

				if not result.get("success"):
					rule_result["error"] = result.get("error", "Unknown error")
					if rule_info.severity == "Error":
						has_errors = True
					elif rule_info.severity == "Warning":
						has_warnings = True

				execution_results.append(rule_result)

				# Si es una regla de error que falló, detener ejecución
				if not result.get("success") and rule_info.severity == "Error":
					break

			except Exception as rule_error:
				has_errors = True
				execution_results.append(
					{
						"rule_name": rule_info.rule_name,
						"rule_code": rule_info.rule_code,
						"severity": rule_info.severity,
						"success": False,
						"error": str(rule_error),
						"execution_time": 0,
						"timestamp": frappe.utils.now_datetime().isoformat(),
					}
				)

				# Error en regla crítica, detener
				if rule_info.severity == "Error":
					break

		# Determinar estado final
		if has_errors:
			final_status = "Failed"
		elif has_warnings:
			final_status = "Warnings"
		else:
			final_status = "Passed"

		# Actualizar tracking
		update_validation_tracking(doc, final_status, execution_results)

		# Crear log de ejecución si hay resultados
		if execution_results:
			log_rule_execution_batch(doc, execution_results, total_execution_time)

	except Exception as e:
		frappe.log_error(f"Error executing validation rules for {doc.doctype} {doc.name}: {e}")
		# En caso de error del sistema, marcar como failed
		try:
			update_validation_tracking(doc, "Failed", [{"error": f"System error: {e!s}"}])
		except Exception:
			pass


def update_validation_tracking(doc, status, results):
	"""Actualizar campos de tracking de validación en documento."""
	try:
		if hasattr(doc, "fm_validation_status"):
			doc.fm_validation_status = status

		if hasattr(doc, "fm_validation_timestamp"):
			doc.fm_validation_timestamp = frappe.utils.now_datetime()

		if hasattr(doc, "fm_validation_rules_applied"):
			doc.fm_validation_rules_applied = json.dumps(results, indent=2, default=str)

		# Para EReceipt MX, actualizar contador
		if doc.doctype == "EReceipt MX":
			if hasattr(doc, "fm_rules_validation_count"):
				current_count = getattr(doc, "fm_rules_validation_count", 0) or 0
				doc.fm_rules_validation_count = current_count + 1

			if hasattr(doc, "fm_last_validation_result"):
				doc.fm_last_validation_result = status

	except Exception as e:
		frappe.log_error(f"Error updating validation tracking: {e}")


def log_rule_execution_batch(doc, execution_results, total_execution_time):
	"""Crear logs de ejecución para múltiples reglas."""
	try:
		for result in execution_results:
			# Crear log individual
			log_doc = frappe.get_doc(
				{
					"doctype": "Rule Execution Log",
					"rule": result.get("rule_name"),  # Usar rule_name como referencia
					"document_type": doc.doctype,
					"document_name": doc.name,
					"execution_time": result.get("execution_time", 0),
					"result": "Success" if result.get("success") else "Failed",
					"conditions_evaluated": 1,  # Asumimos al menos 1 condición
					"actions_executed": 1 if result.get("executed") else 0,
					"error_details": result.get("error") if not result.get("success") else None,
					"action_details": json.dumps(result, indent=2, default=str),
				}
			)

			try:
				log_doc.insert(ignore_permissions=True, ignore_mandatory=True)
			except Exception as log_error:
				frappe.log_error(f"Error creating individual rule log: {log_error}")

	except Exception as e:
		frappe.log_error(f"Error creating rule execution logs: {e}")


# Hooks específicos por DocType
def validate_sales_invoice(doc, method):
	"""Hook específico para Sales Invoice."""
	execute_validation_rules(doc, method)


def validate_payment_entry(doc, method):
	"""Hook específico para Payment Entry."""
	execute_validation_rules(doc, method)


def validate_customer(doc, method):
	"""Hook específico para Customer."""
	execute_validation_rules(doc, method)


def validate_ereceipt_mx(doc, method):
	"""Hook específico para EReceipt MX."""
	execute_validation_rules(doc, method)


def validate_factura_global_mx(doc, method):
	"""Hook específico para Factura Global MX."""
	execute_validation_rules(doc, method)


# Hook para limpiar datos de validación al cancelar
def on_cancel_clear_validation(doc, method):
	"""Limpiar datos de validación al cancelar documento."""
	try:
		if hasattr(doc, "fm_validation_status"):
			doc.fm_validation_status = "Pending"

		if hasattr(doc, "fm_validation_timestamp"):
			doc.fm_validation_timestamp = None

		if hasattr(doc, "fm_validation_rules_applied"):
			doc.fm_validation_rules_applied = None

	except Exception as e:
		frappe.log_error(f"Error clearing validation data on cancel: {e}")


# Utilidades para testing y debugging
def get_validation_preview(doctype, document_name):
	"""Obtener preview de validación sin ejecutar realmente."""
	try:
		# Obtener documento (se usa más adelante para validaciones)
		# doc = frappe.get_doc(doctype, document_name)

		# Obtener reglas aplicables
		rules = frappe.get_all(
			"Fiscal Validation Rule",
			filters={
				"apply_to_doctype": doctype,
				"is_active": 1,
				"rule_type": "Validation",
				"docstatus": ["!=", 2],
			},
			fields=["name", "rule_name", "rule_code", "priority", "severity", "description"],
			order_by="priority ASC",
		)

		preview_results = []

		for rule_info in rules:
			rule_doc = frappe.get_doc("Fiscal Validation Rule", rule_info.name)

			# Usar test_rule para preview
			test_result = rule_doc.test_rule(document_name)

			preview_results.append(
				{
					"rule_name": rule_info.rule_name,
					"rule_code": rule_info.rule_code,
					"severity": rule_info.severity,
					"description": rule_info.description,
					"priority": rule_info.priority,
					"test_result": test_result,
				}
			)

		return {
			"success": True,
			"document": {"doctype": doctype, "name": document_name},
			"rules_found": len(rules),
			"preview_results": preview_results,
		}

	except Exception as e:
		return {"success": False, "error": str(e)}


def force_revalidate_document(doctype, document_name):
	"""Forzar revalidación de documento existente."""
	try:
		doc = frappe.get_doc(doctype, document_name)

		# Ejecutar validación
		execute_validation_rules(doc, "manual_revalidation")

		# Guardar cambios en tracking fields
		doc.save(ignore_permissions=True)

		return {"success": True, "message": f"Document {document_name} revalidated successfully"}

	except Exception as e:
		return {"success": False, "error": str(e)}


def validate_document_with_rules(doc):
	"""Wrapper function for testing integration."""
	try:
		execute_validation_rules(doc, "test_validation")
		return {"success": True, "message": "Validation completed"}
	except Exception as e:
		return {"success": False, "error": str(e)}
