"""
Layer 2: Integration Tests - Motor de Reglas
Tests de integración entre componentes del motor de reglas
"""

import json
import unittest
from unittest.mock import MagicMock, patch

import frappe

from facturacion_mexico.motor_reglas.tests.test_base_motor_reglas import MotorReglasTestBase


class TestMotorReglasIntegration(MotorReglasTestBase):
	"""Tests de integración para motor de reglas."""

	def test_complete_rule_execution_workflow(self):
		"""Test workflow completo de ejecución de regla."""
		# Crear regla compleja con múltiples condiciones y acciones
		rule_doc = self.create_test_rule(
			{
				"rule_name": "Integration Workflow Rule",
				"rule_code": "WORKFLOW_001",
				"description": "Test complete workflow",
				"rule_type": "Validation",
				"apply_to_doctype": "Sales Invoice",
				"severity": "Error",
				"conditions": [
					{
						"condition_type": "Field",
						"field_name": "grand_total",
						"operator": "greater_than",
						"value": "1000",
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
						"action_type": "Set Field",
						"target_field": "remarks",
						"action_value": "High value invoice for public customer",
					},
					{
						"action_type": "Show Warning",
						"action_value": "Review required for public customer",
					},
				],
			}
		)

		# Crear documento de prueba que cumple condiciones
		mock_doc = MagicMock()
		mock_doc.doctype = "Sales Invoice"
		mock_doc.name = "TEST-WORKFLOW-001"
		mock_doc.grand_total = 2000
		mock_doc.customer_name = "PUBLICO GENERAL"
		mock_doc.remarks = ""

		# Ejecutar regla completa
		execution_result = rule_doc.execute_rule(mock_doc)

		# Validar resultado
		self.assertTrue(execution_result.get("success"))
		self.assertTrue(execution_result.get("executed"))
		self.assertTrue(execution_result.get("conditions_met"))
		self.assertIn("actions_result", execution_result)

	def test_multiple_rules_execution_priority(self):
		"""Test ejecución de múltiples reglas con prioridades."""
		# Crear reglas con diferentes prioridades
		self.create_test_rule(
			{
				"rule_name": "High Priority Rule",
				"rule_code": "HIGH_PRIORITY_001",
				"priority": 10,  # Alta prioridad
				"apply_to_doctype": "Sales Invoice",
			}
		)

		self.create_test_rule(
			{
				"rule_name": "Low Priority Rule",
				"rule_code": "LOW_PRIORITY_001",
				"priority": 90,  # Baja prioridad
				"apply_to_doctype": "Sales Invoice",
			}
		)

		self.create_test_rule(
			{
				"rule_name": "Medium Priority Rule",
				"rule_code": "MEDIUM_PRIORITY_001",
				"priority": 50,  # Prioridad media
				"apply_to_doctype": "Sales Invoice",
			}
		)

		# Obtener reglas activas para Sales Invoice
		from facturacion_mexico.motor_reglas.doctype.fiscal_validation_rule.fiscal_validation_rule import (
			FiscalValidationRule,
		)

		active_rules = FiscalValidationRule.get_active_rules_for_doctype("Sales Invoice")

		# Validar que existen al menos nuestras 3 reglas
		rule_codes = [rule["rule_code"] for rule in active_rules]
		self.assertIn("HIGH_PRIORITY_001", rule_codes)
		self.assertIn("MEDIUM_PRIORITY_001", rule_codes)
		self.assertIn("LOW_PRIORITY_001", rule_codes)

	def test_rule_with_dynamic_values_integration(self):
		"""Test integración de reglas con valores dinámicos."""
		# Crear regla que usa valores dinámicos
		rule_doc = self.create_test_rule(
			{
				"rule_name": "Dynamic Values Rule",
				"rule_code": "DYNAMIC_001",
				"conditions": [
					{
						"condition_type": "Field",
						"field_name": "posting_date",
						"operator": "equals",
						"value": "TODAY",
						"value_type": "Dynamic",
					}
				],
				"actions": [
					{
						"action_type": "Set Field",
						"target_field": "remarks",
						"action_value": "Processed on {TODAY} by {CURRENT_USER}",
						"value_type": "Dynamic",
					}
				],
			}
		)

		# Mock document con fecha de hoy
		mock_doc = MagicMock()
		mock_doc.doctype = "Sales Invoice"
		mock_doc.name = "TEST-DYNAMIC-001"
		mock_doc.posting_date = frappe.utils.today()
		mock_doc.remarks = ""

		# Ejecutar regla
		result = rule_doc.execute_rule(mock_doc)

		# Validar que se ejecutó correctamente
		self.assertTrue(result.get("success"))
		self.assertTrue(result.get("executed"))

	def test_rule_cache_integration_performance(self):
		"""Test integración del sistema de caché para performance."""
		# Crear regla de prueba
		rule_doc = self.create_test_rule(
			{"rule_name": "Cache Performance Rule", "rule_code": "CACHE_PERF_001"}
		)

		# Primera ejecución - debe compilar caché
		cache_key = f"fiscal_rule_cache_{rule_doc.name}"

		# Verificar que caché no existe inicialmente
		frappe.cache().delete_value(cache_key)
		cached_data = frappe.cache().get_value(cache_key)
		self.assertIsNone(cached_data)

		# Compilar caché
		rule_doc.compile_rule_cache()

		# Verificar que caché fue creado
		cached_data = frappe.cache().get_value(cache_key)
		self.assertIsNotNone(cached_data)

		# Parsear contenido del caché
		cache_content = json.loads(cached_data)
		self.assertEqual(cache_content["rule_code"], "CACHE_PERF_001")
		self.assertIn("conditions", cache_content)
		self.assertIn("actions", cache_content)

	def test_rule_error_handling_integration(self):
		"""Test manejo de errores en integración completa."""
		# Crear regla con condición que causará error
		rule_doc = self.create_test_rule(
			{
				"rule_name": "Error Handling Rule",
				"rule_code": "ERROR_HANDLING_001",
				"conditions": [
					{
						"condition_type": "Field",
						"field_name": "nonexistent_field",  # Campo que no existe
						"operator": "equals",
						"value": "test",
						"value_type": "Static",
					}
				],
				"actions": [
					{
						"action_type": "Set Field",
						"target_field": "remarks",
						"action_value": "This should handle gracefully",
					}
				],
			}
		)

		# Mock document sin el campo requerido
		mock_doc = MagicMock()
		mock_doc.doctype = "Sales Invoice"
		mock_doc.name = "TEST-ERROR-001"
		# No incluir nonexistent_field

		# Ejecutar regla - debe manejar error gracefully
		result = rule_doc.execute_rule(mock_doc)

		# Debe retornar un resultado válido, no crash
		self.assertIsInstance(result, dict)
		self.assertIn("success", result)

	def test_rule_validation_with_custom_fields_integration(self):
		"""Test integración con custom fields de validación."""
		# Mock document con custom fields de validación
		mock_doc = MagicMock()
		mock_doc.doctype = "Sales Invoice"
		mock_doc.name = "TEST-CUSTOM-FIELDS-001"
		mock_doc.grand_total = 1500
		mock_doc.fm_validation_status = "Pending"
		mock_doc.fm_validation_timestamp = None
		mock_doc.fm_validation_rules_applied = None

		# Crear regla que modifique validation status
		rule_doc = self.create_test_rule(
			{
				"rule_name": "Custom Fields Integration Rule",
				"rule_code": "CUSTOM_FIELDS_001",
				"conditions": [
					{
						"condition_type": "Field",
						"field_name": "grand_total",
						"operator": "greater_than",
						"value": "1000",
						"value_type": "Static",
					}
				],
				"actions": [
					{
						"action_type": "Set Field",
						"target_field": "fm_validation_status",
						"action_value": "Validated",
					}
				],
			}
		)

		# Ejecutar regla
		result = rule_doc.execute_rule(mock_doc)

		# Validar ejecución exitosa
		self.assertTrue(result.get("success"))
		self.assertTrue(result.get("executed"))

	def test_evaluator_executor_parser_integration(self):
		"""Test integración entre RuleEvaluator, RuleExecutor y RuleParser."""
		from facturacion_mexico.motor_reglas.engine.rule_evaluator import RuleEvaluator
		from facturacion_mexico.motor_reglas.engine.rule_executor import RuleExecutor
		from facturacion_mexico.motor_reglas.engine.rule_parser import RuleParser

		# Crear instancias de los componentes
		evaluator = RuleEvaluator()
		executor = RuleExecutor()
		parser = RuleParser()

		# Crear regla para testing
		rule_doc = self.create_test_rule(
			{
				"rule_name": "Engine Integration Rule",
				"rule_code": "ENGINE_INTEGRATION_001",
				"conditions": [
					{
						"condition_type": "Field",
						"field_name": "grand_total",
						"operator": "greater_than",
						"value": "1000",
						"value_type": "Static",
					}
				],
				"actions": [
					{
						"action_type": "Set Field",
						"target_field": "remarks",
						"action_value": "Processed by integrated engine",
					}
				],
			}
		)

		# Mock document
		mock_doc = MagicMock()
		mock_doc.grand_total = 1500
		mock_doc.remarks = ""

		# Test Parser - validar sintaxis
		validation_result = parser.validate_rule_syntax(rule_doc)
		self.assertTrue(validation_result.get("valid", False))

		# Test Evaluator - evaluar condiciones
		conditions_result = evaluator.evaluate_conditions(rule_doc.conditions, mock_doc)
		self.assertTrue(conditions_result)

		# Test Executor - ejecutar acciones
		actions_result = executor.execute_actions(rule_doc.actions, mock_doc, rule_doc)
		self.assertIn("actions_executed", actions_result)

	def test_rule_execution_statistics_integration(self):
		"""Test integración de estadísticas de ejecución."""
		# Crear regla para statistics testing
		rule_doc = self.create_test_rule(
			{"rule_name": "Statistics Integration Rule", "rule_code": "STATS_INTEGRATION_001"}
		)

		# Verificar estadísticas iniciales
		initial_count = rule_doc.execution_count or 0

		# Mock document
		mock_doc = MagicMock()
		mock_doc.doctype = "Sales Invoice"
		mock_doc.name = "TEST-STATS-001"
		mock_doc.grand_total = 1500

		# Ejecutar regla múltiples veces
		for _ in range(3):
			result = rule_doc.execute_rule(mock_doc)
			self.assertTrue(result.get("success"))

		# Recargar regla para obtener estadísticas actualizadas
		rule_doc.reload()

		# Validar que estadísticas se actualizaron
		self.assertGreater(rule_doc.execution_count or 0, initial_count)
		self.assertIsNotNone(rule_doc.last_execution)

	def test_rule_with_formula_values_integration(self):
		"""Test integración de reglas con valores de fórmula."""
		# Crear regla que usa fórmulas
		rule_doc = self.create_test_rule(
			{
				"rule_name": "Formula Integration Rule",
				"rule_code": "FORMULA_INTEGRATION_001",
				"conditions": [
					{
						"condition_type": "Field",
						"field_name": "grand_total",
						"operator": "greater_than",
						"value": "GRAND_TOTAL",  # Usar fórmula como valor
						"value_type": "Formula",
					}
				],
				"actions": [
					{
						"action_type": "Set Field",
						"target_field": "remarks",
						"action_value": "Items count: {ITEM_COUNT}",
						"value_type": "Formula",
					}
				],
			}
		)

		# Mock document con items
		mock_doc = MagicMock()
		mock_doc.doctype = "Sales Invoice"
		mock_doc.name = "TEST-FORMULA-001"
		mock_doc.grand_total = 1500
		mock_doc.items = [{"item": "Test 1"}, {"item": "Test 2"}]
		mock_doc.remarks = ""

		# Ejecutar regla
		result = rule_doc.execute_rule(mock_doc)

		# Validar resultado
		self.assertTrue(result.get("success"))

	def test_multi_doctype_rules_integration(self):
		"""Test integración de reglas aplicadas a múltiples DocTypes."""
		# Crear reglas para diferentes DocTypes
		self.create_test_rule(
			{
				"rule_name": "Sales Invoice Specific Rule",
				"rule_code": "SI_SPECIFIC_001",
				"apply_to_doctype": "Sales Invoice",
			}
		)

		self.create_test_rule(
			{
				"rule_name": "Payment Entry Specific Rule",
				"rule_code": "PE_SPECIFIC_001",
				"apply_to_doctype": "Payment Entry",
			}
		)

		# Verificar que cada regla se aplica solo a su DocType correspondiente
		from facturacion_mexico.motor_reglas.doctype.fiscal_validation_rule.fiscal_validation_rule import (
			FiscalValidationRule,
		)

		si_rules = FiscalValidationRule.get_active_rules_for_doctype("Sales Invoice")
		pe_rules = FiscalValidationRule.get_active_rules_for_doctype("Payment Entry")

		# Verificar separación por DocType
		si_codes = [rule["rule_code"] for rule in si_rules]
		pe_codes = [rule["rule_code"] for rule in pe_rules]

		self.assertIn("SI_SPECIFIC_001", si_codes)
		self.assertNotIn("SI_SPECIFIC_001", pe_codes)
		self.assertIn("PE_SPECIFIC_001", pe_codes)
		self.assertNotIn("PE_SPECIFIC_001", si_codes)

	def test_rule_with_field_reference_integration(self):
		"""Test integración de reglas con referencias a campos."""
		# Crear regla que compara campos entre sí
		rule_doc = self.create_test_rule(
			{
				"rule_name": "Field Reference Rule",
				"rule_code": "FIELD_REF_001",
				"conditions": [
					{
						"condition_type": "Field",
						"field_name": "grand_total",
						"operator": "greater_than",
						"value": "net_total",  # Comparar con otro campo
						"value_type": "Field Reference",
					}
				],
				"actions": [
					{
						"action_type": "Set Field",
						"target_field": "remarks",
						"action_value": "Grand total exceeds net total",
					}
				],
			}
		)

		# Mock document con campos relacionados
		mock_doc = MagicMock()
		mock_doc.doctype = "Sales Invoice"
		mock_doc.name = "TEST-FIELD-REF-001"
		mock_doc.grand_total = 1500
		mock_doc.net_total = 1200  # Menor que grand_total
		mock_doc.remarks = ""

		# Ejecutar regla
		result = rule_doc.execute_rule(mock_doc)

		# Debe ejecutarse porque grand_total > net_total
		self.assertTrue(result.get("success"))
		self.assertTrue(result.get("executed"))

	def test_rule_execution_with_hooks_integration(self):
		"""Test integración con hooks de Frappe."""
		# Esta prueba simula la integración con hooks de validación
		rule_doc = self.create_test_rule(
			{
				"rule_name": "Hooks Integration Rule",
				"rule_code": "HOOKS_INTEGRATION_001",
				"apply_to_doctype": "Sales Invoice",
			}
		)

		# Mock document
		mock_doc = MagicMock()
		mock_doc.doctype = "Sales Invoice"
		mock_doc.name = "TEST-HOOKS-001"
		mock_doc.grand_total = 1500

		# Simular llamada desde hook de validación
		from facturacion_mexico.motor_reglas.hooks_handlers.document_validation import (
			validate_document_with_rules,
		)

		# Mock de la función de validación
		with patch("frappe.get_all") as mock_get_all:
			mock_get_all.return_value = [
				{"name": rule_doc.name, "rule_code": "HOOKS_INTEGRATION_001", "priority": 50}
			]

			# Ejecutar validación via hooks
			result = validate_document_with_rules(mock_doc)

			# Validar resultado
			self.assertIsInstance(result, dict)

	def test_complex_logical_expression_integration(self):
		"""Test integración de expresiones lógicas complejas."""
		# Crear regla con lógica compleja: (A AND B) OR (C AND D)
		rule_doc = self.create_test_rule(
			{
				"rule_name": "Complex Logic Rule",
				"rule_code": "COMPLEX_LOGIC_001",
				"conditions": [
					{
						"condition_type": "Field",
						"field_name": "grand_total",
						"operator": "greater_than",
						"value": "1000",
						"value_type": "Static",
						"logical_operator": "AND",
						"group_start": True,
					},
					{
						"condition_type": "Field",
						"field_name": "customer_name",
						"operator": "contains",
						"value": "PUBLICO",
						"value_type": "Static",
						"logical_operator": "OR",
						"group_end": True,
					},
					{
						"condition_type": "Field",
						"field_name": "status",
						"operator": "equals",
						"value": "Draft",
						"value_type": "Static",
						"logical_operator": "AND",
						"group_start": True,
					},
					{
						"condition_type": "Field",
						"field_name": "docstatus",
						"operator": "equals",
						"value": "0",
						"value_type": "Static",
						"group_end": True,
					},
				],
				"actions": [
					{
						"action_type": "Set Field",
						"target_field": "remarks",
						"action_value": "Complex logic validation passed",
					}
				],
			}
		)

		# Test con documento que cumple primera parte de la lógica
		mock_doc1 = MagicMock()
		mock_doc1.doctype = "Sales Invoice"
		mock_doc1.name = "TEST-COMPLEX-001"
		mock_doc1.grand_total = 1500  # > 1000
		mock_doc1.customer_name = "PUBLICO GENERAL"  # contains PUBLICO
		mock_doc1.status = "Paid"  # No cumple segunda parte
		mock_doc1.docstatus = 1
		mock_doc1.remarks = ""

		result1 = rule_doc.execute_rule(mock_doc1)
		self.assertTrue(result1.get("success"))
		self.assertTrue(result1.get("executed"))  # Debe ejecutarse por primera parte

		# Test con documento que cumple segunda parte de la lógica
		mock_doc2 = MagicMock()
		mock_doc2.doctype = "Sales Invoice"
		mock_doc2.name = "TEST-COMPLEX-002"
		mock_doc2.grand_total = 500  # < 1000
		mock_doc2.customer_name = "PRIVADO"  # No contains PUBLICO
		mock_doc2.status = "Draft"  # = Draft
		mock_doc2.docstatus = 0  # = 0
		mock_doc2.remarks = ""

		result2 = rule_doc.execute_rule(mock_doc2)
		self.assertTrue(result2.get("success"))
		self.assertTrue(result2.get("executed"))  # Debe ejecutarse por segunda parte


if __name__ == "__main__":
	unittest.main()
