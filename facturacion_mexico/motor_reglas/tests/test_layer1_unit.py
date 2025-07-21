"""
Layer 1: Unit Tests - Motor de Reglas
Tests unitarios para componentes individuales del motor de reglas
"""

import json
import unittest
from unittest.mock import MagicMock, patch

import frappe

from facturacion_mexico.motor_reglas.tests.test_base_motor_reglas import MotorReglasTestBase


class TestMotorReglasUnit(MotorReglasTestBase):
	"""Tests unitarios para motor de reglas."""

	def test_fiscal_validation_rule_creation(self):
		"""Test creación básica de regla fiscal."""
		rule_doc = self.create_test_rule(
			{
				"rule_name": "Test Unit Rule",
				"rule_code": "UNIT_TEST_001",
				"description": "Unit test rule",
				"rule_type": "Validation",
				"apply_to_doctype": "Sales Invoice",
			}
		)

		# Validar campos básicos
		self.assertEqual(rule_doc.rule_name, "Test Unit Rule")
		self.assertEqual(rule_doc.rule_code, "UNIT_TEST_001")
		self.assertEqual(rule_doc.apply_to_doctype, "Sales Invoice")
		self.assertTrue(rule_doc.is_active)
		self.assertEqual(rule_doc.priority, 50)

	def test_rule_condition_validation(self):
		"""Test validación de condiciones de regla."""
		rule_doc = self.create_test_rule(
			{
				"rule_name": "Condition Test Rule",
				"rule_code": "COND_TEST_001",
				"conditions": [
					{
						"condition_type": "Field",
						"field_name": "grand_total",
						"operator": "greater_than",
						"value": "1000",
						"value_type": "Static",
					}
				],  # Specific condition for test
				"actions": [
					{"action_type": "Show Error", "action_value": "Test validation"}
				],  # Minimal action required
			}
		)

		# Verificar condición fue agregada
		self.assertEqual(len(rule_doc.conditions), 1)
		condition = rule_doc.conditions[0]
		self.assertEqual(condition.condition_type, "Field")
		self.assertEqual(condition.field_name, "grand_total")
		self.assertEqual(condition.operator, "greater_than")

	def test_rule_action_validation(self):
		"""Test validación de acciones de regla."""
		rule_doc = self.create_test_rule(
			{
				"rule_name": "Action Test Rule",
				"rule_code": "ACTION_TEST_001",
				"conditions": [
					{
						"condition_type": "Field",
						"field_name": "grand_total",
						"operator": "greater_than",
						"value": "1000",
						"value_type": "Static",
					}
				],  # Minimal condition required
				"actions": [
					{"action_type": "Show Error", "action_value": "Test error message"}
				],  # Specific action for test
			}
		)

		# Verificar acción fue agregada
		self.assertEqual(len(rule_doc.actions), 1)
		action = rule_doc.actions[0]
		self.assertEqual(action.action_type, "Show Error")
		self.assertEqual(action.action_value, "Test error message")

	def test_rule_evaluator_field_conditions(self):
		"""Test evaluación de condiciones de campo."""
		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator

		evaluator = RuleEvaluator()

		# Mock document
		mock_doc = MagicMock()
		mock_doc.grand_total = 1500
		mock_doc.customer_name = "Test Customer"
		mock_doc.status = "Draft"

		# Test condición simple - mayor que
		condition = MagicMock()
		condition.condition_type = "Field"
		condition.field_name = "grand_total"
		condition.operator = "greater_than"
		condition.value = "1000"
		condition.value_type = "Static"

		result = evaluator.evaluate_single_condition(condition, mock_doc)
		self.assertTrue(result, "Should evaluate to True when grand_total > 1000")

		# Test condición - igual
		condition.operator = "equals"
		condition.value = "1500"
		result = evaluator.evaluate_single_condition(condition, mock_doc)
		self.assertTrue(result, "Should evaluate to True when grand_total equals 1500")

		# Test condición - contiene
		condition.field_name = "customer_name"
		condition.operator = "contains"
		condition.value = "Test"
		result = evaluator.evaluate_single_condition(condition, mock_doc)
		self.assertTrue(result, "Should evaluate to True when customer_name contains 'Test'")

	def test_rule_evaluator_logical_operators(self):
		"""Test operadores lógicos en evaluación."""
		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator

		evaluator = RuleEvaluator()

		# Expresión simple: "true and false"
		result = evaluator.evaluate_logical_expression("true and false")
		self.assertFalse(result)

		# Expresión simple: "true or false"
		result = evaluator.evaluate_logical_expression("true or false")
		self.assertTrue(result)

		# Expresión compleja: "(true and true) or false"
		result = evaluator.evaluate_logical_expression("(true and true) or false")
		self.assertTrue(result)

	def test_rule_executor_set_field_action(self):
		"""Test ejecución de acción Set Field."""
		from facturacion_mexico.motor_reglas.engine.rule_executor import RuleExecutor

		executor = RuleExecutor()

		# Mock document
		mock_doc = MagicMock()
		mock_doc.remarks = ""

		# Mock action
		mock_action = MagicMock()
		mock_action.action_type = "Set Field"
		mock_action.target_field = "remarks"
		mock_action.action_value = "Updated by rule"
		mock_action.continue_on_error = False
		mock_action.log_action = False

		# Mock rule
		mock_rule = MagicMock()

		# Ejecutar acción
		result = executor.manual_action_execution(mock_action, mock_doc, mock_rule)

		self.assertTrue(result.get("success"))
		self.assertEqual(result.get("action"), "set_field")
		self.assertEqual(result.get("field"), "remarks")
		self.assertEqual(result.get("value"), "Updated by rule")

	def test_rule_parser_condition_syntax_validation(self):
		"""Test validación de sintaxis de condiciones."""
		from facturacion_mexico.motor_reglas.engine.rule_parser import RuleParser

		parser = RuleParser()

		# Condición válida
		mock_condition = MagicMock()
		mock_condition.condition_type = "Field"
		mock_condition.field_name = "grand_total"
		mock_condition.operator = "greater_than"
		mock_condition.value = "1000"
		mock_condition.value_type = "Static"

		validation = parser.validate_condition_syntax(mock_condition)
		self.assertTrue(validation["valid"])
		self.assertEqual(len(validation["errors"]), 0)

		# Condición inválida - sin field_name
		mock_condition.field_name = None
		validation = parser.validate_condition_syntax(mock_condition)
		self.assertFalse(validation["valid"])
		self.assertGreater(len(validation["errors"]), 0)

	def test_rule_parser_action_syntax_validation(self):
		"""Test validación de sintaxis de acciones."""
		from facturacion_mexico.motor_reglas.engine.rule_parser import RuleParser

		parser = RuleParser()

		# Acción válida
		mock_action = MagicMock()
		mock_action.action_type = "Show Error"
		mock_action.action_value = "Error message"
		mock_action.target_field = None

		validation = parser.validate_action_syntax(mock_action)
		self.assertTrue(validation["valid"])

		# Acción inválida - Set Field sin target_field
		mock_action.action_type = "Set Field"
		mock_action.target_field = None
		validation = parser.validate_action_syntax(mock_action)
		self.assertFalse(validation["valid"])

	def test_rule_complexity_calculation(self):
		"""Test cálculo de complejidad de reglas."""
		from facturacion_mexico.motor_reglas.engine.rule_parser import RuleParser

		parser = RuleParser()

		# Crear regla simple
		rule_doc = self.create_test_rule({"rule_name": "Simple Rule", "rule_code": "SIMPLE_001"})

		self.create_test_condition(
			rule_doc,
			{
				"condition_type": "Field",
				"field_name": "grand_total",
				"operator": "greater_than",
				"value": "1000",
			},
		)

		self.create_test_action(rule_doc, {"action_type": "Show Error", "action_value": "Simple error"})

		complexity = parser.get_rule_complexity_score(rule_doc)
		self.assertIn("score", complexity)
		self.assertIn("complexity", complexity)
		self.assertGreaterEqual(complexity["score"], 0)

	def test_rule_cache_operations(self):
		"""Test operaciones de caché de reglas."""
		rule_doc = self.create_test_rule({"rule_name": "Cache Test Rule", "rule_code": "CACHE_TEST_001"})

		# Test compilación de caché
		rule_doc.compile_rule_cache()

		# Verificar que caché fue creado
		cache_key = f"fiscal_rule_cache_{rule_doc.name}"
		cached_data = frappe.cache().get_value(cache_key)
		self.assertIsNotNone(cached_data)

		# Test invalidación de caché
		rule_doc.invalidate_rule_cache()
		cached_data = frappe.cache().get_value(cache_key)
		self.assertIsNone(cached_data)

	def test_dynamic_value_resolution(self):
		"""Test resolución de valores dinámicos."""
		from facturacion_mexico.motor_reglas.engine.rule_executor import RuleExecutor

		executor = RuleExecutor()

		# Mock document
		mock_doc = MagicMock()
		mock_doc.customer_name = "Test Customer"
		mock_doc.grand_total = 1500

		# Test sustitución de campo
		template = "Customer: {customer_name}, Total: {grand_total}"
		result = executor.evaluate_dynamic_value(template, mock_doc)
		expected = "Customer: Test Customer, Total: 1500"
		self.assertEqual(result, expected)

		# Test valores especiales
		template = "Date: {TODAY}, User: {USER}"
		result = executor.evaluate_dynamic_value(template, mock_doc)
		self.assertIn(frappe.utils.today(), result)
		self.assertIn(frappe.session.user, result)

	def test_operator_compatibility_validation(self):
		"""Test validación de compatibilidad entre operadores y valores."""
		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator

		evaluator = RuleEvaluator()

		# Test operadores numéricos
		result = evaluator.safe_numeric_compare("1500", "1000", ">")
		self.assertTrue(result)

		result = evaluator.safe_numeric_compare("500", "1000", "<")
		self.assertTrue(result)

		# Test operadores de lista
		result = evaluator.value_in_list("Test", "Test,Demo,Sample")
		self.assertTrue(result)

		result = evaluator.value_in_list("Other", "Test,Demo,Sample")
		self.assertFalse(result)

		# Test operadores de lista JSON
		result = evaluator.value_in_list("Test", '["Test", "Demo", "Sample"]')
		self.assertTrue(result)

	def test_rule_execution_statistics_update(self):
		"""Test actualización de estadísticas de ejecución."""
		rule_doc = self.create_test_rule({"rule_name": "Stats Test Rule", "rule_code": "STATS_TEST_001"})

		# Ejecutar actualización de estadísticas
		initial_count = rule_doc.execution_count or 0
		execution_time = 0.1  # 100ms

		rule_doc.update_execution_stats(execution_time, success=True)

		# Verificar que las estadísticas se actualizaron
		updated_rule = frappe.get_doc("Fiscal Validation Rule", rule_doc.name)
		self.assertEqual(updated_rule.execution_count, initial_count + 1)
		self.assertIsNotNone(updated_rule.last_execution)
		self.assertGreater(updated_rule.average_execution_time, 0)

	def test_regex_pattern_validation(self):
		"""Test validación de patrones regex en condiciones."""
		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator

		evaluator = RuleEvaluator()

		# Mock document con RFC
		mock_doc = MagicMock()
		mock_doc.tax_id = "RFC123456789"

		# Test condición regex válida
		result = evaluator.apply_operator("RFC123456789", r"^RFC\d+", "regex_match")
		self.assertTrue(result, "Should match RFC pattern")

		# Test condición regex que no coincide
		result = evaluator.apply_operator("INVALID", r"^RFC\d+", "regex_match")
		self.assertFalse(result, "Should not match RFC pattern")

	def test_date_condition_evaluation(self):
		"""Test evaluación de condiciones con fechas."""
		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator

		evaluator = RuleEvaluator()

		# Mock document con fecha
		mock_doc = MagicMock()
		mock_doc.posting_date = frappe.utils.today()

		# Condición de fecha - igual a hoy
		condition = MagicMock()
		condition.condition_type = "Field"
		condition.field_name = "posting_date"
		condition.operator = "equals"
		condition.value = frappe.utils.today()
		condition.value_type = "Static"

		result = evaluator.evaluate_single_condition(condition, mock_doc)
		self.assertTrue(result, "Should evaluate date equality correctly")

	def test_numeric_condition_precision(self):
		"""Test precisión en condiciones numéricas."""
		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator

		evaluator = RuleEvaluator()

		# Test comparaciones numéricas con decimales
		self.assertTrue(evaluator.safe_numeric_compare("1500.50", "1500.49", ">"))
		self.assertFalse(evaluator.safe_numeric_compare("1500.50", "1500.51", ">"))
		self.assertTrue(evaluator.safe_numeric_compare("1500.00", "1500.00", ">="))

	def test_error_handling_in_rule_execution(self):
		"""Test manejo de errores durante ejecución de reglas."""
		rule_doc = self.create_test_rule({"rule_name": "Error Test Rule", "rule_code": "ERROR_TEST_001"})

		# Condición que causará error (campo inexistente)
		self.create_test_condition(
			rule_doc,
			{
				"condition_type": "Field",
				"field_name": "nonexistent_field",
				"operator": "equals",
				"value": "test",
			},
		)

		self.create_test_action(
			rule_doc, {"action_type": "Show Error", "action_value": "This should handle gracefully"}
		)

		rule_doc.save()

		# Mock document sin el campo
		mock_doc = MagicMock()
		mock_doc.doctype = "Sales Invoice"
		mock_doc.name = "TEST-001"

		# La ejecución debe manejar el error gracefully
		result = rule_doc.execute_rule(mock_doc)
		# Debe retornar un resultado, no crash
		self.assertIsInstance(result, dict)
		self.assertIn("success", result)

	def test_rule_priority_validation(self):
		"""Test validación de prioridades de reglas."""
		# Prioridad válida
		rule_doc = self.create_test_rule(
			{"rule_name": "Priority Test Rule", "rule_code": "PRIORITY_TEST_001", "priority": 25}
		)

		# No debe lanzar error
		rule_doc.save()
		self.assertEqual(rule_doc.priority, 25)

		# Test prioridad inválida (fuera de rango)
		with self.assertRaises(frappe.ValidationError):
			rule_doc.priority = 150  # Fuera del rango 1-100
			rule_doc.validate()

	def test_rule_effective_date_validation(self):
		"""Test validación de fechas de vigencia."""
		from frappe.utils import add_days, today

		rule_doc = self.create_test_rule(
			{
				"rule_name": "Date Test Rule",
				"rule_code": "DATE_TEST_001",
				"effective_date": add_days(today(), -1),
				"expiry_date": add_days(today(), 1),
			}
		)

		# Fechas válidas no deben causar error
		rule_doc.save()

		# Test fechas inválidas (inicio después de fin)
		with self.assertRaises(frappe.ValidationError):
			rule_doc.effective_date = add_days(today(), 2)
			rule_doc.expiry_date = add_days(today(), 1)
			rule_doc.validate()

	def test_condition_grouping_logic(self):
		"""Test lógica de agrupación de condiciones."""
		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator

		evaluator = RuleEvaluator()

		# Mock condiciones con agrupación
		conditions = []

		# (condition1 AND condition2) OR condition3
		cond1 = MagicMock()
		cond1.group_start = True
		cond1.logical_operator = "AND"
		conditions.append(cond1)

		cond2 = MagicMock()
		cond2.group_end = True
		cond2.logical_operator = "OR"
		conditions.append(cond2)

		cond3 = MagicMock()
		cond3.group_start = False
		cond3.group_end = False
		conditions.append(cond3)

		# Mock document
		mock_doc = MagicMock()

		# Test construcción de expresión lógica
		expression = evaluator.build_logical_expression(conditions, mock_doc)
		self.assertIn("(", expression)
		self.assertIn(")", expression)
		self.assertIn("and", expression.lower())
		self.assertIn("or", expression.lower())

	def test_evaluation_summary_complete(self):
		"""Test resumen completo de evaluación."""
		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator

		evaluator = RuleEvaluator()

		# Mock document
		mock_doc = MagicMock()
		mock_doc.grand_total = 1500
		mock_doc.customer_name = "Test Customer"

		# Mock conditions
		conditions = []
		cond1 = MagicMock()
		cond1.condition_type = "Field"
		cond1.field_name = "grand_total"
		cond1.operator = "greater_than"
		cond1.value = "1000"
		cond1.logical_operator = "AND"
		conditions.append(cond1)

		cond2 = MagicMock()
		cond2.condition_type = "Field"
		cond2.field_name = "customer_name"
		cond2.operator = "contains"
		cond2.value = "Test"
		cond2.logical_operator = None
		conditions.append(cond2)

		# Test summary generation
		summary = evaluator.get_evaluation_summary(conditions, mock_doc)

		self.assertIn("total_conditions", summary)
		self.assertIn("conditions_detail", summary)
		self.assertIn("final_result", summary)
		self.assertIn("logical_expression", summary)
		self.assertEqual(summary["total_conditions"], 2)
		self.assertEqual(len(summary["conditions_detail"]), 2)

	def test_string_comparison_operators(self):
		"""Test operadores de comparación de strings."""
		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator

		evaluator = RuleEvaluator()

		# Test comparaciones de strings
		self.assertTrue(evaluator.safe_string_compare("B", "A", ">"))
		self.assertTrue(evaluator.safe_string_compare("A", "B", "<"))
		self.assertTrue(evaluator.safe_string_compare("A", "A", ">="))
		self.assertTrue(evaluator.safe_string_compare("A", "A", "<="))

		# Test case sensitivity
		self.assertFalse(evaluator.safe_string_compare("a", "A", ">"))
		self.assertTrue(evaluator.safe_string_compare("b", "A", ">"))

	def test_formula_evaluation_edge_cases(self):
		"""Test evaluación de fórmulas - casos especiales."""
		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator

		evaluator = RuleEvaluator()

		# Mock document sin atributos esperados
		mock_doc = MagicMock()
		mock_doc.grand_total = None

		# Test fórmulas con documentos incompletos
		result = evaluator.evaluate_formula("GRAND_TOTAL", mock_doc)
		self.assertEqual(result, 0)

		result = evaluator.evaluate_formula("INVALID_FORMULA", mock_doc)
		self.assertEqual(result, "INVALID_FORMULA")

		# Test con documento que tiene items
		mock_doc_with_items = MagicMock()
		mock_doc_with_items.items = [{"item": 1}, {"item": 2}]
		result = evaluator.evaluate_formula("ITEM_COUNT", mock_doc_with_items)
		self.assertEqual(result, 2)

	def test_dynamic_values_comprehensive(self):
		"""Test valores dinámicos completos."""
		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator

		evaluator = RuleEvaluator()

		# Test todos los valores dinámicos disponibles
		result_today = evaluator.resolve_dynamic_value("TODAY")
		self.assertEqual(result_today, frappe.utils.today())

		result_now = evaluator.resolve_dynamic_value("NOW")
		self.assertEqual(result_now, frappe.utils.now())

		result_user = evaluator.resolve_dynamic_value("CURRENT_USER")
		self.assertEqual(result_user, frappe.session.user)

		# Test valor dinámico inexistente
		result_invalid = evaluator.resolve_dynamic_value("INVALID_DYNAMIC")
		self.assertEqual(result_invalid, "INVALID_DYNAMIC")

	def test_field_value_extraction_edge_cases(self):
		"""Test extracción de valores de campo - casos especiales."""
		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator

		evaluator = RuleEvaluator()

		# Test con documento None
		result = evaluator.get_document_field_value(None, "field_name")
		self.assertIsNone(result)

		# Test con campo inexistente
		mock_doc = MagicMock()
		del mock_doc.nonexistent_field  # Ensure it doesn't exist
		result = evaluator.get_document_field_value(mock_doc, "nonexistent_field")
		self.assertIsNone(result)

		# Test con diccionario
		dict_doc = {"existing_field": "value"}
		result = evaluator.get_document_field_value(dict_doc, "existing_field")
		self.assertEqual(result, "value")

		result = evaluator.get_document_field_value(dict_doc, "nonexistent_field")
		self.assertIsNone(result)

	def test_comparison_value_types(self):
		"""Test diferentes tipos de valores de comparación."""
		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator

		evaluator = RuleEvaluator()

		# Mock condition y document
		mock_condition = MagicMock()
		mock_doc = MagicMock()
		mock_doc.reference_field = "reference_value"

		# Test Static value
		mock_condition.value = "static_value"
		mock_condition.value_type = "Static"
		result = evaluator.get_comparison_value(mock_condition, mock_doc)
		self.assertEqual(result, "static_value")

		# Test Dynamic value
		mock_condition.value = "TODAY"
		mock_condition.value_type = "Dynamic"
		result = evaluator.get_comparison_value(mock_condition, mock_doc)
		self.assertEqual(result, frappe.utils.today())

		# Test Formula value
		mock_condition.value = "GRAND_TOTAL"
		mock_condition.value_type = "Formula"
		mock_doc.grand_total = 1000
		result = evaluator.get_comparison_value(mock_condition, mock_doc)
		self.assertEqual(result, 1000)

		# Test Field Reference
		mock_condition.value = "reference_field"
		mock_condition.value_type = "Field Reference"
		result = evaluator.get_comparison_value(mock_condition, mock_doc)
		self.assertEqual(result, "reference_value")

	def test_list_operations_comprehensive(self):
		"""Test operaciones de lista completas."""
		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator

		evaluator = RuleEvaluator()

		# Test lista comma-separated
		self.assertTrue(evaluator.value_in_list("Test", "Test,Demo,Sample"))
		self.assertFalse(evaluator.value_in_list("Other", "Test,Demo,Sample"))

		# Test lista JSON válida
		self.assertTrue(evaluator.value_in_list("Test", '["Test", "Demo", "Sample"]'))
		self.assertFalse(evaluator.value_in_list("Other", '["Test", "Demo", "Sample"]'))

		# Test lista JSON inválida (fallback a comma-separated)
		self.assertTrue(evaluator.value_in_list("Test", '["Test", "Demo"'))  # JSON malformado

		# Test con lista vacía
		self.assertFalse(evaluator.value_in_list("Test", ""))
		self.assertFalse(evaluator.value_in_list("Test", "[]"))

		# Test con valor None
		self.assertFalse(evaluator.value_in_list(None, "Test,Demo"))

	def test_rule_summary_and_active_rules(self):
		"""Test resumen de reglas y obtener reglas activas."""
		# Test get_rule_summary
		rule_doc = self.create_test_rule({"rule_name": "Summary Test Rule", "rule_code": "SUMMARY_001"})

		summary = rule_doc.get_rule_summary()
		self.assertIn("rule_code", summary)
		self.assertIn("rule_name", summary)
		self.assertIn("is_active", summary)
		self.assertIn("conditions_count", summary)
		self.assertIn("actions_count", summary)
		self.assertEqual(summary["rule_code"], "SUMMARY_001")

		# Test get_active_rules_for_doctype
		from facturacion_mexico.motor_reglas.doctype.fiscal_validation_rule.fiscal_validation_rule import (
			FiscalValidationRule,
		)

		active_rules = FiscalValidationRule.get_active_rules_for_doctype("Sales Invoice")
		self.assertIsInstance(active_rules, list)

	def test_rule_test_function(self):
		"""Test función de testing de reglas."""
		rule_doc = self.create_test_rule({"rule_name": "Test Function Rule", "rule_code": "TESTFUNC_001"})

		# Crear un Sales Invoice de prueba
		invoice_doc = self.create_test_sales_invoice()

		# Test la función test_rule
		test_result = rule_doc.test_rule(invoice_doc.name)
		self.assertIn("success", test_result)
		self.assertIn("test_result", test_result)
		self.assertIn("rule", test_result)
		self.assertEqual(test_result["rule"], "TESTFUNC_001")

		# Test con documento inexistente
		with self.assertRaises(frappe.ValidationError):
			rule_doc.test_rule(None)

	def test_security_validations(self):
		"""Test validaciones de seguridad básicas."""
		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator

		evaluator = RuleEvaluator()

		# Test regex pattern injection
		mock_doc = MagicMock()
		mock_doc.test_field = "test_value"

		# Pattern potencialmente peligroso pero válido
		result = evaluator.apply_operator("test_value", r"^test.*", "regex_match")
		self.assertTrue(result)

		# Test expression evaluation security
		# Solo debe evaluar expresiones seguras
		safe_expr = "true and false"
		result = evaluator.evaluate_logical_expression(safe_expr)
		self.assertFalse(result)

		# Expression con tokens no seguros debe retornar False
		unsafe_expr = "true and import_os"
		result = evaluator.evaluate_logical_expression(unsafe_expr)
		self.assertFalse(result)

	def test_error_handling_comprehensive(self):
		"""Test manejo de errores comprehensivo."""
		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator

		evaluator = RuleEvaluator()

		# Test con documento que lanza AttributeError
		class BadDocument:
			@property
			def bad_field(self):
				raise AttributeError("Field not accessible")

		bad_doc = BadDocument()

		# Debe manejar AttributeError gracefully
		result = evaluator.get_document_field_value(bad_doc, "bad_field")
		self.assertIsNone(result)

		# Test numeric comparison con valores inválidos
		result = evaluator.safe_numeric_compare("invalid", "also_invalid", ">")
		self.assertFalse(result)  # Fallback a string comparison

		# Test value_in_list con JSON extremadamente malformado
		result = evaluator.value_in_list("test", "{invalid[json")
		self.assertFalse(result)

	def test_cache_operations_detailed(self):
		"""Test operaciones de caché detalladas."""
		rule_doc = self.create_test_rule({"rule_name": "Cache Detail Rule", "rule_code": "CACHE_DETAIL_001"})

		# Test compilación de caché con datos específicos
		rule_doc.compile_rule_cache()

		cache_key = f"fiscal_rule_cache_{rule_doc.name}"
		cached_data = frappe.cache().get_value(cache_key)
		self.assertIsNotNone(cached_data)

		# Verificar estructura del caché
		cache_content = json.loads(cached_data)
		self.assertIn("rule_code", cache_content)
		self.assertIn("conditions", cache_content)
		self.assertIn("actions", cache_content)
		self.assertEqual(cache_content["rule_code"], "CACHE_DETAIL_001")

		# Test invalidación y limpieza
		rule_doc.invalidate_rule_cache()
		cached_data_after = frappe.cache().get_value(cache_key)
		self.assertIsNone(cached_data_after)


if __name__ == "__main__":
	unittest.main()
