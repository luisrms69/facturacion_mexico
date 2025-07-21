"""
Rule Execution Log - Sprint 4 Semana 2
DocType para logging de ejecuciones de reglas fiscales
"""

import json

import frappe
from frappe import _
from frappe.model.document import Document


class RuleExecutionLog(Document):
	"""Log de ejecución de reglas fiscales."""

	def validate(self):
		"""Validaciones del log."""
		self.populate_rule_name()

	def populate_rule_name(self):
		"""Poblar nombre de regla desde el link."""
		if self.rule and not self.rule_name:
			rule_doc = frappe.get_doc("Fiscal Validation Rule", self.rule)
			self.rule_name = rule_doc.rule_name

	@staticmethod
	def log_rule_execution(rule, document, result, execution_time_ms, conditions_count=0, actions_count=0):
		"""Crear log de ejecución de regla."""
		try:
			log_doc = frappe.get_doc(
				{
					"doctype": "Rule Execution Log",
					"rule": rule.name if hasattr(rule, "name") else str(rule),
					"document_type": document.get("doctype")
					if isinstance(document, dict)
					else document.doctype,
					"document_name": document.get("name") if isinstance(document, dict) else document.name,
					"execution_time": execution_time_ms,
					"result": "Success"
					if result.get("success")
					else ("Skipped" if result.get("skipped") else "Failed"),
					"conditions_evaluated": conditions_count,
					"actions_executed": actions_count,
					"error_details": result.get("error") if not result.get("success") else None,
					"action_details": json.dumps(result, indent=2, default=str),
				}
			)

			log_doc.insert(ignore_permissions=True, ignore_mandatory=True)
			return log_doc.name

		except Exception as e:
			frappe.log_error(f"Error creating rule execution log: {e}")
			return None

	@staticmethod
	def get_execution_stats(rule_name=None, date_range=None, limit=100):
		"""Obtener estadísticas de ejecución."""
		filters = {}

		if rule_name:
			filters["rule"] = rule_name

		if date_range:
			if isinstance(date_range, dict):
				if date_range.get("from_date"):
					filters["creation"] = [">=", date_range["from_date"]]
				if date_range.get("to_date"):
					if "creation" in filters:
						filters["creation"] = ["between", [date_range["from_date"], date_range["to_date"]]]
					else:
						filters["creation"] = ["<=", date_range["to_date"]]

		logs = frappe.get_all(
			"Rule Execution Log",
			filters=filters,
			fields=[
				"name",
				"rule",
				"rule_name",
				"document_type",
				"document_name",
				"execution_time",
				"result",
				"creation",
				"conditions_evaluated",
				"actions_executed",
				"error_details",
			],
			order_by="creation DESC",
			limit=limit,
		)

		# Calcular estadísticas agregadas
		if logs:
			total_executions = len(logs)
			successful = len([l for l in logs if l.result == "Success"])
			failed = len([l for l in logs if l.result == "Failed"])
			skipped = len([l for l in logs if l.result == "Skipped"])

			execution_times = [l.execution_time for l in logs if l.execution_time]
			avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
			max_execution_time = max(execution_times) if execution_times else 0
			min_execution_time = min(execution_times) if execution_times else 0

			stats = {
				"total_executions": total_executions,
				"successful": successful,
				"failed": failed,
				"skipped": skipped,
				"success_rate": (successful / total_executions * 100) if total_executions > 0 else 0,
				"avg_execution_time": round(avg_execution_time, 3),
				"max_execution_time": max_execution_time,
				"min_execution_time": min_execution_time,
				"recent_logs": logs[:10],  # Últimos 10 logs
			}
		else:
			stats = {
				"total_executions": 0,
				"successful": 0,
				"failed": 0,
				"skipped": 0,
				"success_rate": 0,
				"avg_execution_time": 0,
				"max_execution_time": 0,
				"min_execution_time": 0,
				"recent_logs": [],
			}

		return stats

	@staticmethod
	def cleanup_old_logs(days_to_keep=30):
		"""Limpiar logs antiguos para evitar acumulación excesiva."""
		try:
			cutoff_date = frappe.utils.add_days(frappe.utils.today(), -days_to_keep)

			old_logs = frappe.get_all(
				"Rule Execution Log", filters={"creation": ["<", cutoff_date]}, pluck="name"
			)

			deleted_count = 0
			for log_name in old_logs:
				try:
					frappe.delete_doc("Rule Execution Log", log_name, force=True, ignore_permissions=True)
					deleted_count += 1
				except Exception as e:
					frappe.log_error(f"Error deleting log {log_name}: {e}")

			return {"success": True, "deleted_logs": deleted_count, "cutoff_date": cutoff_date}

		except Exception as e:
			frappe.log_error(f"Error during log cleanup: {e}")
			return {"success": False, "error": str(e)}

	@staticmethod
	def get_performance_insights(rule_name=None):
		"""Obtener insights de performance de reglas."""
		filters = {}
		if rule_name:
			filters["rule"] = rule_name

		# Query para estadísticas de performance
		performance_data = frappe.db.sql(
			"""
			SELECT
				rule,
				rule_name,
				COUNT(*) as total_executions,
				AVG(execution_time) as avg_execution_time,
				MAX(execution_time) as max_execution_time,
				MIN(execution_time) as min_execution_time,
				SUM(CASE WHEN result = 'Success' THEN 1 ELSE 0 END) as successful,
				SUM(CASE WHEN result = 'Failed' THEN 1 ELSE 0 END) as failed,
				SUM(CASE WHEN result = 'Skipped' THEN 1 ELSE 0 END) as skipped
			FROM `tabRule Execution Log`
			{where_clause}
			GROUP BY rule, rule_name
			ORDER BY avg_execution_time DESC
		""".format(where_clause="WHERE rule = %(rule)s" if rule_name else ""),
			filters,
			as_dict=True,
		)

		# Calcular métricas adicionales
		for row in performance_data:
			if row.total_executions > 0:
				row["success_rate"] = (row.successful / row.total_executions) * 100
				row["failure_rate"] = (row.failed / row.total_executions) * 100
				row["skip_rate"] = (row.skipped / row.total_executions) * 100
			else:
				row["success_rate"] = 0
				row["failure_rate"] = 0
				row["skip_rate"] = 0

			# Clasificación de performance
			if row.avg_execution_time < 50:
				row["performance_grade"] = "Excellent"
			elif row.avg_execution_time < 100:
				row["performance_grade"] = "Good"
			elif row.avg_execution_time < 200:
				row["performance_grade"] = "Fair"
			else:
				row["performance_grade"] = "Needs Optimization"

		return performance_data

	def get_log_summary(self):
		"""Obtener resumen del log."""
		action_details_parsed = None
		try:
			if self.action_details:
				action_details_parsed = json.loads(self.action_details)
		except json.JSONDecodeError:
			pass

		return {
			"rule": self.rule,
			"rule_name": self.rule_name,
			"document_type": self.document_type,
			"document_name": self.document_name,
			"execution_time": self.execution_time,
			"result": self.result,
			"creation": self.creation,
			"has_error": bool(self.error_details),
			"conditions_evaluated": self.conditions_evaluated,
			"actions_executed": self.actions_executed,
			"action_summary": action_details_parsed.get("action") if action_details_parsed else None,
		}
