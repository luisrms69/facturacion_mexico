"""
Fiscal Validation Rule - Sprint 4 Semana 2
DocType para definir reglas de validación fiscal declarativas
"""

import json
import time

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class FiscalValidationRule(Document):
	"""Regla de validación fiscal declarativa."""

	def autoname(self):
		"""Generar nombre automático basado en rule_code."""
		if not self.rule_code:
			frappe.throw(_("Código de regla es requerido"))
		self.name = self.rule_code

	def validate(self):
		"""Validaciones del documento."""
		self.validate_rule_syntax()
		self.validate_dates()
		self.validate_priority()
		self.check_circular_dependencies()

	def before_save(self):
		"""Antes de guardar - preparar regla."""
		self.compile_rule_cache()

	def after_insert(self):
		"""Después de insertar - compilar caché."""
		self.compile_rule_cache()

	def on_update(self):
		"""Al actualizar - invalidar caché."""
		self.invalidate_rule_cache()

	def validate_rule_syntax(self):
		"""Validar sintaxis de la regla."""
		if not self.conditions:
			frappe.throw(_("La regla debe tener al menos una condición"))

		if not self.actions:
			frappe.throw(_("La regla debe tener al menos una acción"))

		# Validar condiciones
		for condition in self.conditions:
			if condition.condition_type == "Field" and not condition.field_name:
				frappe.throw(_("Campo es requerido para condiciones de tipo 'Field'"))

			if not condition.operator:
				frappe.throw(_("Operador es requerido en todas las condiciones"))

		# Validar acciones
		for action in self.actions:
			if not action.action_type:
				frappe.throw(_("Tipo de acción es requerido"))

			if action.action_type == "Set Field" and not action.target_field:
				frappe.throw(_("Campo objetivo es requerido para acciones 'Set Field'"))

	def validate_dates(self):
		"""Validar fechas de vigencia."""
		if self.effective_date and self.expiry_date:
			if self.effective_date > self.expiry_date:
				frappe.throw(_("Fecha de vigencia no puede ser posterior a fecha de expiración"))

	def validate_priority(self):
		"""Validar prioridad."""
		if self.priority and (self.priority < 1 or self.priority > 100):
			frappe.throw(_("Prioridad debe estar entre 1 y 100"))

	def check_circular_dependencies(self):
		"""Verificar que no existan dependencias circulares."""
		# TODO: Implementar lógica de detección de dependencias circulares
		# Por ahora, placeholder para evitar loops infinitos
		pass

	def compile_rule_cache(self):
		"""Compilar regla en caché para optimización."""
		cache_key = f"fiscal_rule_cache_{self.name}"

		rule_data = {
			"rule_code": self.rule_code,
			"rule_type": self.rule_type,
			"apply_to_doctype": self.apply_to_doctype,
			"is_active": self.is_active,
			"priority": self.priority or 50,
			"effective_date": self.effective_date,
			"expiry_date": self.expiry_date,
			"severity": self.severity,
			"error_message": self.error_message,
			"warning_message": self.warning_message,
			"conditions": [],
			"actions": [],
		}

		# Compilar condiciones
		for condition in self.conditions:
			rule_data["conditions"].append(
				{
					"condition_type": condition.condition_type,
					"field_name": condition.field_name,
					"operator": condition.operator,
					"value": condition.value,
					"value_type": condition.value_type,
					"logical_operator": condition.logical_operator,
					"group_start": condition.group_start,
					"group_end": condition.group_end,
				}
			)

		# Compilar acciones
		for action in self.actions:
			rule_data["actions"].append(
				{
					"action_type": action.action_type,
					"target_field": action.target_field,
					"action_value": action.action_value,
					"continue_on_error": action.continue_on_error,
					"log_action": action.log_action,
				}
			)

		# Guardar en caché
		frappe.cache().set_value(cache_key, json.dumps(rule_data), expires_in_sec=3600)

	def invalidate_rule_cache(self):
		"""Invalidar caché de la regla."""
		cache_key = f"fiscal_rule_cache_{self.name}"
		frappe.cache().delete_value(cache_key)

		# También invalidar caché global de reglas por DocType
		if self.apply_to_doctype:
			doctype_cache_key = f"fiscal_rules_{self.apply_to_doctype.lower().replace(' ', '_')}"
			frappe.cache().delete_value(doctype_cache_key)

	def execute_rule(self, document):
		"""Ejecutar regla contra un documento específico."""
		start_time = time.time()

		try:
			# Verificar si la regla está activa
			if not self.is_active:
				return {"success": True, "skipped": True, "reason": "Rule not active"}

			# Verificar fechas de vigencia
			current_date = frappe.utils.today()
			if self.effective_date and current_date < self.effective_date:
				return {"success": True, "skipped": True, "reason": "Rule not yet effective"}

			if self.expiry_date and current_date > self.expiry_date:
				return {"success": True, "skipped": True, "reason": "Rule expired"}

			# Evaluar condiciones
			conditions_result = self.evaluate_conditions(document)

			if conditions_result:
				# Ejecutar acciones
				actions_result = self.execute_actions(document)

				# Actualizar estadísticas
				self.update_execution_stats(time.time() - start_time, True)

				return {
					"success": True,
					"executed": True,
					"conditions_met": True,
					"actions_result": actions_result,
				}
			else:
				return {"success": True, "executed": False, "conditions_met": False}

		except Exception as e:
			# Actualizar estadísticas de error
			self.update_execution_stats(time.time() - start_time, False, str(e))

			return {"success": False, "error": str(e), "execution_time": time.time() - start_time}

	def evaluate_conditions(self, document):
		"""Evaluar todas las condiciones de la regla."""
		if not self.conditions:
			return True

		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator

		evaluator = RuleEvaluator()

		return evaluator.evaluate_conditions(self.conditions, document)

	def execute_actions(self, document):
		"""Ejecutar todas las acciones de la regla."""
		if not self.actions:
			return {"actions_executed": 0}

		from facturacion_mexico.motor_reglas.engine.rule_executor import RuleExecutor

		executor = RuleExecutor()

		return executor.execute_actions(self.actions, document, self)

	def update_execution_stats(self, execution_time_seconds, success=True, error_message=None):
		"""Actualizar estadísticas de ejecución."""
		execution_time_ms = execution_time_seconds * 1000

		# Actualizar contadores
		current_count = self.execution_count or 0
		current_avg = self.average_execution_time or 0

		new_count = current_count + 1
		new_avg = ((current_avg * current_count) + execution_time_ms) / new_count

		# Actualizar campos sin triggerar hooks
		frappe.db.set_value(
			"Fiscal Validation Rule",
			self.name,
			{
				"execution_count": new_count,
				"last_execution": now_datetime(),
				"average_execution_time": flt(new_avg, 3),
				"last_error": error_message if not success else None,
			},
			update_modified=False,
		)

	@staticmethod
	def get_active_rules_for_doctype(doctype):
		"""Obtener reglas activas para un DocType específico."""
		cache_key = f"fiscal_rules_{doctype.lower().replace(' ', '_')}"

		# Intentar desde caché
		cached_rules = frappe.cache().get_value(cache_key)
		if cached_rules:
			return json.loads(cached_rules)

		# Consultar base de datos
		rules = frappe.get_all(
			"Fiscal Validation Rule",
			filters={"apply_to_doctype": doctype, "is_active": 1, "docstatus": ["!=", 2]},
			fields=["name", "rule_code", "priority", "rule_type"],
			order_by="priority ASC, creation ASC",
		)

		# Guardar en caché por 30 minutos
		frappe.cache().set_value(cache_key, json.dumps(rules), expires_in_sec=1800)

		return rules

	def test_rule(self, document_name):
		"""Probar regla en un documento específico sin afectar el documento."""
		if not document_name:
			frappe.throw(_("Nombre del documento es requerido para testing"))

		try:
			# Obtener documento
			doc = frappe.get_doc(self.apply_to_doctype, document_name)

			# Ejecutar regla en modo test
			result = self.execute_rule(doc)

			return {"success": True, "test_result": result, "document": document_name, "rule": self.rule_code}

		except Exception as e:
			return {"success": False, "error": str(e), "document": document_name, "rule": self.rule_code}

	def get_rule_summary(self):
		"""Obtener resumen de la regla para APIs."""
		return {
			"rule_code": self.rule_code,
			"rule_name": self.rule_name,
			"rule_type": self.rule_type,
			"apply_to_doctype": self.apply_to_doctype,
			"is_active": self.is_active,
			"priority": self.priority or 50,
			"conditions_count": len(self.conditions) if self.conditions else 0,
			"actions_count": len(self.actions) if self.actions else 0,
			"execution_count": self.execution_count or 0,
			"average_execution_time": self.average_execution_time or 0,
			"last_execution": self.last_execution,
			"has_error": bool(self.last_error),
		}
