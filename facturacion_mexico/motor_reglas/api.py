"""
Motor de Reglas API - Sprint 4 Semana 2
APIs para gestión y ejecución de reglas fiscales declarativas
"""

import json
import time

import frappe
from frappe import _


@frappe.whitelist()
def get_applicable_rules(doctype, context=None):
	"""Obtener reglas aplicables a un DocType específico."""
	try:
		# Validar parámetros
		if not doctype:
			return {"success": False, "message": "DocType es requerido"}

		# Obtener reglas activas para el DocType
		rules = frappe.get_all(
			"Fiscal Validation Rule",
			filters={"apply_to_doctype": doctype, "is_active": 1, "docstatus": ["!=", 2]},
			fields=[
				"name",
				"rule_name",
				"rule_code",
				"rule_type",
				"priority",
				"effective_date",
				"expiry_date",
				"severity",
				"description",
				"execution_count",
				"average_execution_time",
				"last_execution",
			],
			order_by="priority ASC, creation ASC",
		)

		# Filtrar por fecha de vigencia
		current_date = frappe.utils.today()
		active_rules = []

		for rule in rules:
			# Verificar fecha de vigencia
			if rule.effective_date and current_date < rule.effective_date:
				continue
			if rule.expiry_date and current_date > rule.expiry_date:
				continue

			# Aplicar contexto si se proporciona
			if context:
				# TODO: Implementar filtrado por contexto específico
				pass

			active_rules.append(rule)

		# Estadísticas agregadas
		stats = {"total_rules": len(active_rules), "by_type": {}, "by_priority": {}, "avg_execution_time": 0}

		if active_rules:
			# Agrupar por tipo
			for rule in active_rules:
				rule_type = rule.rule_type
				if rule_type not in stats["by_type"]:
					stats["by_type"][rule_type] = 0
				stats["by_type"][rule_type] += 1

			# Calcular tiempo promedio
			execution_times = [r.average_execution_time for r in active_rules if r.average_execution_time]
			if execution_times:
				stats["avg_execution_time"] = sum(execution_times) / len(execution_times)

		return {
			"success": True,
			"data": active_rules,
			"stats": stats,
			"doctype": doctype,
			"total_rules": len(active_rules),
		}

	except Exception as e:
		frappe.log_error(f"Error getting applicable rules: {e}")
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def test_rule(rule_name, document_name):
	"""Probar regla en documento específico sin afectar el documento."""
	try:
		# Validar parámetros
		if not rule_name or not document_name:
			return {"success": False, "message": "Rule name y document name son requeridos"}

		# Obtener regla
		rule_doc = frappe.get_doc("Fiscal Validation Rule", rule_name)

		# Obtener documento
		document = frappe.get_doc(rule_doc.apply_to_doctype, document_name)

		# Ejecutar prueba
		start_time = time.time()
		test_result = rule_doc.test_rule(document_name)
		execution_time = (time.time() - start_time) * 1000

		# Obtener detalles de evaluación
		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator

		evaluator = RuleEvaluator()

		conditions_summary = evaluator.get_evaluation_summary(rule_doc.conditions, document)

		# Obtener detalles de acciones
		from facturacion_mexico.motor_reglas.engine.rule_executor import RuleExecutor

		executor = RuleExecutor()

		actions_summary = executor.get_execution_summary(rule_doc.actions, document, rule_doc)

		return {
			"success": True,
			"test_result": test_result,
			"execution_time": execution_time,
			"rule_info": {
				"rule_name": rule_doc.rule_name,
				"rule_code": rule_doc.rule_code,
				"rule_type": rule_doc.rule_type,
				"priority": rule_doc.priority,
			},
			"document_info": {
				"doctype": document.doctype,
				"name": document.name,
				"title": document.get_title() if hasattr(document, "get_title") else document.name,
			},
			"conditions_detail": conditions_summary,
			"actions_detail": actions_summary,
		}

	except Exception as e:
		frappe.log_error(f"Error testing rule: {e}")
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def create_rule_from_template(template_name, customizations=None):
	"""Crear regla desde template predefinido."""
	try:
		# Templates predefinidos comunes para SAT
		templates = {
			"rfc_required_ppd": {
				"rule_name": "RFC Obligatorio para PPD",
				"rule_code": "RFC_PPD_REQ",
				"description": "Validar que el RFC del cliente sea requerido para método de pago PPD",
				"rule_type": "Validation",
				"apply_to_doctype": "Sales Invoice",
				"severity": "Error",
				"error_message": "RFC del cliente es obligatorio para facturas con método de pago PPD",
				"conditions": [
					{
						"condition_type": "Field",
						"field_name": "fm_payment_method_sat",
						"operator": "equals",
						"value": "PPD",
						"value_type": "Static",
						"logical_operator": "AND",
					},
					{
						"condition_type": "Field",
						"field_name": "tax_id",
						"operator": "is_not_set",
						"value": "",
						"value_type": "Static",
					},
				],
				"actions": [
					{
						"action_type": "Show Error",
						"action_value": "RFC del cliente es obligatorio para facturas con método de pago PPD (Pago en Parcialidades o Diferido)",
					}
				],
			},
			"limit_global_amount": {
				"rule_name": "Límite Montos Factura Global",
				"rule_code": "GLOBAL_LIMIT",
				"description": "Validar que facturas globales no excedan límites SAT",
				"rule_type": "Validation",
				"apply_to_doctype": "Factura Global MX",
				"severity": "Warning",
				"warning_message": "El monto de la factura global se acerca al límite mensual permitido",
				"conditions": [
					{
						"condition_type": "Field",
						"field_name": "total_periodo",
						"operator": "greater_than",
						"value": "250000",
						"value_type": "Static",
					}
				],
				"actions": [
					{
						"action_type": "Show Warning",
						"action_value": "ATENCIÓN: El monto de ${total_periodo} se acerca al límite mensual de facturas globales. Verifique con su contador.",
					}
				],
			},
			"customer_required_pue": {
				"rule_name": "Cliente Requerido PUE",
				"rule_code": "CUSTOMER_PUE_REQ",
				"description": "Validar identificación de cliente para facturas PUE mayores a cierto monto",
				"rule_type": "Validation",
				"apply_to_doctype": "Sales Invoice",
				"severity": "Error",
				"error_message": "Cliente debe estar identificado para facturas PUE mayores a $5,000",
				"conditions": [
					{
						"condition_type": "Field",
						"field_name": "fm_payment_method_sat",
						"operator": "equals",
						"value": "PUE",
						"value_type": "Static",
						"logical_operator": "AND",
					},
					{
						"condition_type": "Field",
						"field_name": "grand_total",
						"operator": "greater_than",
						"value": "5000",
						"value_type": "Static",
						"logical_operator": "AND",
					},
					{
						"condition_type": "Field",
						"field_name": "customer_name",
						"operator": "contains",
						"value": "PUBLICO",
						"value_type": "Static",
					},
				],
				"actions": [
					{
						"action_type": "Show Error",
						"action_value": "Para facturas PUE mayores a $5,000 debe identificar al cliente (no puede ser PUBLICO GENERAL)",
					}
				],
			},
		}

		# Validar template
		if template_name not in templates:
			available_templates = list(templates.keys())
			return {
				"success": False,
				"message": f"Template '{template_name}' no encontrado",
				"available_templates": available_templates,
			}

		# Obtener template base
		template = templates[template_name].copy()

		# Aplicar personalizaciones
		if customizations:
			if isinstance(customizations, str):
				customizations = json.loads(customizations)

			# Merge personalizations
			template.update(customizations)

		# Crear documento de regla
		rule_doc = frappe.get_doc({"doctype": "Fiscal Validation Rule", **template})

		# Insertar regla
		rule_doc.insert()

		return {
			"success": True,
			"rule_name": rule_doc.name,
			"rule_code": rule_doc.rule_code,
			"message": f"Regla '{rule_doc.rule_name}' creada exitosamente desde template '{template_name}'",
			"template_used": template_name,
		}

	except Exception as e:
		frappe.log_error(f"Error creating rule from template: {e}")
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_rule_execution_stats(rule_name=None, date_range=None):
	"""Obtener estadísticas de ejecución de reglas."""
	try:
		# Parsear date_range si viene como string
		if date_range and isinstance(date_range, str):
			date_range = json.loads(date_range)

		# Obtener estadísticas desde Rule Execution Log
		from facturacion_mexico.motor_reglas.doctype.rule_execution_log.rule_execution_log import (
			RuleExecutionLog,
		)

		stats = RuleExecutionLog.get_execution_stats(rule_name, date_range)

		# Obtener insights de performance
		performance_insights = RuleExecutionLog.get_performance_insights(rule_name)

		# Estadísticas adicionales por DocType si no se especifica regla
		doctype_stats = {}
		if not rule_name:
			doctype_data = frappe.db.sql(
				"""
				SELECT
					r.apply_to_doctype,
					COUNT(l.name) as executions,
					AVG(l.execution_time) as avg_time,
					SUM(CASE WHEN l.result = 'Success' THEN 1 ELSE 0 END) as successful
				FROM `tabRule Execution Log` l
				JOIN `tabFiscal Validation Rule` r ON l.rule = r.name
				GROUP BY r.apply_to_doctype
				ORDER BY executions DESC
			""",
				as_dict=True,
			)

			for row in doctype_data:
				doctype_stats[row.apply_to_doctype] = {
					"total_executions": row.executions,
					"avg_execution_time": row.avg_time or 0,
					"success_rate": (row.successful / row.executions * 100) if row.executions > 0 else 0,
				}

		return {
			"success": True,
			"stats": stats,
			"performance_insights": performance_insights,
			"doctype_breakdown": doctype_stats,
			"period": date_range,
			"rule": rule_name,
		}

	except Exception as e:
		frappe.log_error(f"Error getting rule execution stats: {e}")
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def bulk_apply_rules(doctype, filters=None, dry_run=True):
	"""Aplicar reglas masivamente a documentos existentes."""
	try:
		# Validar parámetros
		if not doctype:
			return {"success": False, "message": "DocType es requerido"}

		# Parsear filtros
		if filters and isinstance(filters, str):
			filters = json.loads(filters)

		# Obtener reglas aplicables
		rules = frappe.get_all(
			"Fiscal Validation Rule",
			filters={"apply_to_doctype": doctype, "is_active": 1, "docstatus": ["!=", 2]},
			fields=["name", "rule_name", "rule_code", "priority"],
			order_by="priority ASC",
		)

		if not rules:
			return {"success": False, "message": f"No hay reglas activas para DocType '{doctype}'"}

		# Obtener documentos a procesar
		document_filters = filters or {}
		documents = frappe.get_all(
			doctype,
			filters=document_filters,
			fields=["name"],
			limit=1000 if dry_run else 5000,  # Limitar para evitar timeout
		)

		if not documents:
			return {
				"success": False,
				"message": f"No hay documentos que coincidan con los filtros para DocType '{doctype}'",
			}

		# Procesar documentos
		results = {
			"processed_documents": 0,
			"successful_rules": 0,
			"failed_rules": 0,
			"total_execution_time": 0,
			"rule_results": {},
			"errors": [],
		}

		for doc_data in documents:
			try:
				# Obtener documento completo
				doc = frappe.get_doc(doctype, doc_data.name)

				# Aplicar cada regla
				for rule_info in rules:
					try:
						rule_doc = frappe.get_doc("Fiscal Validation Rule", rule_info.name)

						start_time = time.time()

						if dry_run:
							# Solo simular ejecución
							rule_result = rule_doc.test_rule(doc.name)
						else:
							# Ejecutar regla real
							rule_result = rule_doc.execute_rule(doc)

						execution_time = (time.time() - start_time) * 1000
						results["total_execution_time"] += execution_time

						# Registrar resultado
						rule_key = f"{rule_info.rule_code}_{rule_info.name}"
						if rule_key not in results["rule_results"]:
							results["rule_results"][rule_key] = {
								"rule_name": rule_info.rule_name,
								"successful": 0,
								"failed": 0,
								"total_time": 0,
								"documents": [],
							}

						rule_stats = results["rule_results"][rule_key]
						rule_stats["total_time"] += execution_time
						rule_stats["documents"].append(
							{
								"document": doc.name,
								"success": rule_result.get("success", False),
								"execution_time": execution_time,
							}
						)

						if rule_result.get("success"):
							rule_stats["successful"] += 1
							results["successful_rules"] += 1
						else:
							rule_stats["failed"] += 1
							results["failed_rules"] += 1

					except Exception as rule_error:
						results["failed_rules"] += 1
						results["errors"].append(
							f"Error en regla {rule_info.name} para documento {doc.name}: {rule_error}"
						)

				results["processed_documents"] += 1

			except Exception as doc_error:
				results["errors"].append(f"Error procesando documento {doc_data.name}: {doc_error}")

		# Calcular estadísticas finales
		if results["processed_documents"] > 0:
			results["avg_execution_time"] = results["total_execution_time"] / results["processed_documents"]

		return {
			"success": True,
			"dry_run": dry_run,
			"doctype": doctype,
			"total_documents": len(documents),
			"total_rules": len(rules),
			"results": results,
		}

	except Exception as e:
		frappe.log_error(f"Error in bulk apply rules: {e}")
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def validate_rule_syntax(rule_name):
	"""Validar sintaxis completa de una regla."""
	try:
		# Obtener regla
		rule_doc = frappe.get_doc("Fiscal Validation Rule", rule_name)

		# Usar parser para validar sintaxis
		from facturacion_mexico.motor_reglas.engine.rule_parser import RuleParser

		parser = RuleParser()

		# Validar regla completa
		validation = parser.validate_rule_complete(rule_doc)

		# Obtener score de complejidad
		complexity = parser.get_rule_complexity_score(rule_doc)

		return {
			"success": True,
			"rule_name": rule_doc.rule_name,
			"rule_code": rule_doc.rule_code,
			"validation": validation,
			"complexity": complexity,
		}

	except Exception as e:
		frappe.log_error(f"Error validating rule syntax: {e}")
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def execute_validation_rules(doctype, document_name):
	"""Ejecutar todas las reglas de validación para un documento específico."""
	try:
		# Obtener reglas aplicables
		rules_response = get_applicable_rules(doctype)
		if not rules_response.get("success"):
			return rules_response

		rules = rules_response["data"]
		if not rules:
			return {
				"success": True,
				"message": f"No hay reglas activas para DocType '{doctype}'",
				"rules_executed": 0,
			}

		# Obtener documento
		document = frappe.get_doc(doctype, document_name)

		# Ejecutar reglas
		execution_results = []
		total_execution_time = 0
		successful_rules = 0
		failed_rules = 0

		for rule_info in rules:
			try:
				rule_doc = frappe.get_doc("Fiscal Validation Rule", rule_info.name)

				start_time = time.time()
				result = rule_doc.execute_rule(document)
				execution_time = (time.time() - start_time) * 1000

				total_execution_time += execution_time

				result.update(
					{
						"rule_name": rule_info.rule_name,
						"rule_code": rule_info.rule_code,
						"execution_time": execution_time,
					}
				)

				execution_results.append(result)

				if result.get("success"):
					successful_rules += 1
				else:
					failed_rules += 1

			except Exception as rule_error:
				failed_rules += 1
				execution_results.append(
					{
						"success": False,
						"error": str(rule_error),
						"rule_name": rule_info.rule_name,
						"rule_code": rule_info.rule_code,
						"execution_time": 0,
					}
				)

		return {
			"success": True,
			"document": {
				"doctype": doctype,
				"name": document_name,
				"title": document.get_title() if hasattr(document, "get_title") else document_name,
			},
			"rules_executed": len(rules),
			"successful_rules": successful_rules,
			"failed_rules": failed_rules,
			"total_execution_time": total_execution_time,
			"avg_execution_time": total_execution_time / len(rules) if rules else 0,
			"results": execution_results,
		}

	except Exception as e:
		frappe.log_error(f"Error executing validation rules: {e}")
		return {"success": False, "message": str(e)}
