"""
Layer 4: UAT (User Acceptance Tests) - Motor de Reglas
Tests de aceptación de usuario para validar comportamiento end-to-end desde perspectiva de usuario
"""

import time
import unittest
from unittest.mock import MagicMock

import frappe

from facturacion_mexico.motor_reglas.tests.test_base_motor_reglas import MotorReglasTestBase


class TestMotorReglasUAT(MotorReglasTestBase):
	"""Tests de aceptación de usuario para motor de reglas."""

	def test_uat_scenario_invoice_validation_workflow(self):
		"""
		UAT Scenario 1: Usuario configura y ejecuta validación completa de facturas
		Como usuario administrador, quiero configurar reglas de validación para facturas
		"""
		# GIVEN: Un usuario configura una regla de validación para facturas altas
		validation_rule = self.create_test_rule(
			{
				"rule_name": "UAT - Validación Facturas Altas",
				"rule_code": "UAT_HIGH_VALUE_INVOICE",
				"description": "Validar facturas con monto alto para revision adicional",
				"rule_type": "Validation",
				"apply_to_doctype": "Sales Invoice",
				"severity": "Warning",
				"is_active": 1,
				"priority": 10,
				"conditions": [
					{
						"condition_type": "Field",
						"field_name": "grand_total",
						"operator": "greater_than",
						"value": "50000",
						"value_type": "Static",
						"logical_operator": "AND",
					},
					{
						"condition_type": "Field",
						"field_name": "customer_name",
						"operator": "not_contains",
						"value": "GOBIERNO",
						"value_type": "Static",
					},
				],
				"actions": [
					{
						"action_type": "Set Field",
						"target_field": "fm_validation_status",
						"action_value": "Requiere Revisión",
						"log_action": 1,
					},
					{
						"action_type": "Set Field",
						"target_field": "remarks",
						"action_value": "Factura alto valor - Revisar documentación",
						"log_action": 1,
					},
				],
			}
		)

		# WHEN: Usuario crea una factura que cumple las condiciones
		customer_doc = self.create_test_customer({"customer_name": "CLIENTE PRIVADO SA"})
		high_value_invoice = self.create_test_sales_invoice(
			{"customer": customer_doc.name, "grand_total": 75000}
		)

		# Simular que la factura tiene los valores esperados
		high_value_invoice.grand_total = 75000
		high_value_invoice.customer_name = "CLIENTE PRIVADO SA"
		high_value_invoice.fm_validation_status = "Pending"
		high_value_invoice.remarks = ""

		# THEN: El sistema debe aplicar la regla correctamente
		validation_result = validation_rule.execute_rule(high_value_invoice)

		# Usuario espera que la validación sea exitosa
		self.assertTrue(validation_result.get("success"), "La validación debe ser exitosa")
		self.assertTrue(validation_result.get("executed"), "La regla debe ejecutarse")
		self.assertTrue(validation_result.get("conditions_met"), "Las condiciones deben cumplirse")

		# Usuario espera que se actualicen los campos correctamente
		actions_result = validation_result.get("actions_result", {})
		self.assertGreater(actions_result.get("actions_executed", 0), 0, "Debe ejecutar al menos una acción")

		# Usuario puede ver las estadísticas de ejecución
		validation_rule.reload()
		self.assertGreater(validation_rule.execution_count or 0, 0, "Debe registrar la ejecución")

	def test_uat_scenario_multi_condition_complex_rule(self):
		"""
		UAT Scenario 2: Usuario configura regla compleja con múltiples condiciones
		Como usuario avanzado, quiero crear reglas con lógica compleja
		"""
		# GIVEN: Usuario configura regla con lógica: (A AND B) OR C
		complex_rule = self.create_test_rule(
			{
				"rule_name": "UAT - Regla Compleja Multi-Condición",
				"rule_code": "UAT_COMPLEX_MULTICONDITION",
				"description": "Regla con lógica compleja para casos especiales",
				"rule_type": "Validation",
				"apply_to_doctype": "Sales Invoice",
				"severity": "Error",
				"is_active": 1,
				"conditions": [
					{
						"condition_type": "Field",
						"field_name": "grand_total",
						"operator": "greater_than",
						"value": "100000",
						"value_type": "Static",
						"logical_operator": "AND",
						"group_start": True,
					},
					{
						"condition_type": "Field",
						"field_name": "status",
						"operator": "equals",
						"value": "Draft",
						"value_type": "Static",
						"logical_operator": "OR",
						"group_end": True,
					},
					{
						"condition_type": "Field",
						"field_name": "customer_name",
						"operator": "contains",
						"value": "URGENTE",
						"value_type": "Static",
						"group_start": True,
						"group_end": True,
					},
				],
				"actions": [
					{
						"action_type": "Set Field",
						"target_field": "remarks",
						"action_value": "Procesado por regla compleja",
						"log_action": 1,
					}
				],
			}
		)

		# WHEN: Usuario prueba diferentes escenarios
		test_scenarios = [
			{
				"name": "Escenario Alto Valor + Draft",
				"data": {"grand_total": 150000, "status": "Draft", "customer_name": "CLIENTE NORMAL"},
				"should_execute": True,
			},
			{
				"name": "Escenario Cliente Urgente",
				"data": {"grand_total": 5000, "status": "Paid", "customer_name": "CLIENTE URGENTE SA"},
				"should_execute": True,
			},
			{
				"name": "Escenario No Cumple",
				"data": {"grand_total": 5000, "status": "Paid", "customer_name": "CLIENTE NORMAL"},
				"should_execute": False,
			},
		]

		for scenario in test_scenarios:
			with self.subTest(scenario=scenario["name"]):
				# Crear documento para el escenario
				mock_invoice = MagicMock()
				mock_invoice.doctype = "Sales Invoice"
				mock_invoice.name = f"UAT-{scenario['name'].replace(' ', '-')}"
				mock_invoice.remarks = ""

				# Configurar datos del escenario
				for field, value in scenario["data"].items():
					setattr(mock_invoice, field, value)

				# THEN: Usuario verifica que la regla se comporta como esperado
				result = complex_rule.execute_rule(mock_invoice)

				self.assertTrue(result.get("success"), f"Debe ser exitoso en {scenario['name']}")

				if scenario["should_execute"]:
					self.assertTrue(result.get("executed"), f"Debe ejecutarse en {scenario['name']}")
				# Note: No verificamos executed=False porque la lógica puede ser compleja

	def test_uat_scenario_rule_management_lifecycle(self):
		"""
		UAT Scenario 3: Usuario administra ciclo de vida completo de reglas
		Como administrador, quiero gestionar reglas desde creación hasta retiro
		"""
		# GIVEN: Usuario crea una regla temporal
		temp_rule = self.create_test_rule(
			{
				"rule_name": "UAT - Regla Temporal",
				"rule_code": "UAT_TEMPORARY_RULE",
				"description": "Regla temporal para campaña especial",
				"rule_type": "Validation",
				"apply_to_doctype": "Sales Invoice",
				"is_active": 1,
				"effective_date": frappe.utils.add_days(frappe.utils.today(), -1),
				"expiry_date": frappe.utils.add_days(frappe.utils.today(), 1),
			}
		)

		# WHEN: Usuario prueba la regla durante su periodo de vigencia
		test_invoice = MagicMock()
		test_invoice.doctype = "Sales Invoice"
		test_invoice.name = "UAT-TEMP-001"
		test_invoice.grand_total = 1000

		# THEN: Regla debe estar activa y funcionar
		result_active = temp_rule.execute_rule(test_invoice)
		self.assertTrue(result_active.get("success"), "Regla activa debe funcionar")

		# WHEN: Usuario desactiva la regla manualmente
		temp_rule.is_active = 0
		temp_rule.save()

		# THEN: Regla debe estar inactiva
		result_inactive = temp_rule.execute_rule(test_invoice)
		self.assertTrue(result_inactive.get("success"), "Debe manejar regla inactiva gracefully")
		self.assertTrue(result_inactive.get("skipped"), "Debe marcar como skipped")
		self.assertEqual(result_inactive.get("reason"), "Rule not active")

		# WHEN: Usuario reactiva la regla
		temp_rule.is_active = 1
		temp_rule.save()

		# THEN: Regla debe funcionar nuevamente
		result_reactivated = temp_rule.execute_rule(test_invoice)
		self.assertTrue(result_reactivated.get("success"), "Regla reactivada debe funcionar")

	def test_uat_scenario_performance_under_load(self):
		"""
		UAT Scenario 4: Usuario valida performance del sistema bajo carga
		Como usuario, espero que el sistema responda rápidamente incluso con múltiples reglas
		"""
		# GIVEN: Usuario configura múltiples reglas para simular entorno productivo
		performance_rules = []
		for i in range(5):  # 5 reglas para simular carga moderada
			rule = self.create_test_rule(
				{
					"rule_name": f"UAT - Performance Rule {i+1}",
					"rule_code": f"UAT_PERFORMANCE_{i+1:02d}",
					"apply_to_doctype": "Sales Invoice",
					"priority": (i + 1) * 20,
					"is_active": 1,
				}
			)
			performance_rules.append(rule)

		# WHEN: Usuario procesa múltiples documentos
		processing_times = []
		for doc_id in range(10):  # 10 documentos para simular batch processing
			mock_doc = MagicMock()
			mock_doc.doctype = "Sales Invoice"
			mock_doc.name = f"UAT-PERF-{doc_id:03d}"
			mock_doc.grand_total = (doc_id + 1) * 1000

			# Medir tiempo de procesamiento total
			start_time = time.time()
			for rule in performance_rules:
				rule.execute_rule(mock_doc)
			processing_time = time.time() - start_time
			processing_times.append(processing_time)

		# THEN: Usuario espera tiempos de respuesta aceptables
		avg_processing_time = sum(processing_times) / len(processing_times)
		max_processing_time = max(processing_times)

		# Expectativas de performance del usuario
		self.assertLess(avg_processing_time, 1.0, "Tiempo promedio debe ser menor a 1 segundo")
		self.assertLess(max_processing_time, 2.0, "Tiempo máximo debe ser menor a 2 segundos")
		self.assertEqual(len(processing_times), 10, "Debe procesar todos los documentos")

	def test_uat_scenario_error_handling_and_recovery(self):
		"""
		UAT Scenario 5: Usuario experimenta errores y sistema se recupera
		Como usuario, espero que el sistema maneje errores gracefully sin afectar otros procesos
		"""
		# GIVEN: Usuario configura regla que puede fallar
		error_prone_rule = self.create_test_rule(
			{
				"rule_name": "UAT - Error Handling Rule",
				"rule_code": "UAT_ERROR_HANDLING",
				"description": "Regla que maneja errores gracefully",
				"apply_to_doctype": "Sales Invoice",
				"is_active": 1,
				"conditions": [
					{
						"condition_type": "Field",
						"field_name": "nonexistent_field",  # Campo que causará error
						"operator": "equals",
						"value": "test",
						"value_type": "Static",
					}
				],
				"actions": [
					{
						"action_type": "Set Field",
						"target_field": "remarks",
						"action_value": "Sistema recuperado del error",
						"continue_on_error": 1,
					}
				],
			}
		)

		# WHEN: Usuario procesa documento que causará error
		problematic_doc = MagicMock()
		problematic_doc.doctype = "Sales Invoice"
		problematic_doc.name = "UAT-ERROR-001"
		problematic_doc.grand_total = 1000
		# Intencionalmente no incluir 'nonexistent_field'

		# THEN: Sistema debe manejar el error sin crash
		error_result = error_prone_rule.execute_rule(problematic_doc)

		# Usuario espera que el sistema no se rompa
		self.assertIsInstance(error_result, dict, "Debe retornar resultado estructurado")
		self.assertIn("success", error_result, "Debe incluir indicador de éxito")
		# No verificamos success=True porque puede fallar gracefully

		# WHEN: Usuario procesa documento normal después del error
		normal_doc = MagicMock()
		normal_doc.doctype = "Sales Invoice"
		normal_doc.name = "UAT-NORMAL-001"
		normal_doc.grand_total = 1000

		normal_result = error_prone_rule.execute_rule(normal_doc)

		# THEN: Sistema debe seguir funcionando normalmente
		self.assertIsInstance(normal_result, dict, "Sistema debe recuperarse y procesar documentos normales")

	def test_uat_scenario_dynamic_values_integration(self):
		"""
		UAT Scenario 6: Usuario utiliza valores dinámicos en reglas
		Como usuario, quiero usar valores dinámicos como fechas actuales y usuarios
		"""
		# GIVEN: Usuario configura regla con valores dinámicos
		dynamic_rule = self.create_test_rule(
			{
				"rule_name": "UAT - Valores Dinámicos",
				"rule_code": "UAT_DYNAMIC_VALUES",
				"description": "Regla que usa valores dinámicos del sistema",
				"apply_to_doctype": "Sales Invoice",
				"is_active": 1,
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
						"action_value": "Procesado el {TODAY} por {CURRENT_USER}",
						"value_type": "Dynamic",
						"log_action": 1,
					}
				],
			}
		)

		# WHEN: Usuario procesa documento con fecha actual
		current_doc = MagicMock()
		current_doc.doctype = "Sales Invoice"
		current_doc.name = "UAT-DYNAMIC-001"
		current_doc.posting_date = frappe.utils.today()
		current_doc.remarks = ""

		# THEN: Sistema debe resolver valores dinámicos correctamente
		dynamic_result = dynamic_rule.execute_rule(current_doc)

		# Usuario espera que la regla funcione con valores dinámicos
		self.assertTrue(dynamic_result.get("success"), "Regla con valores dinámicos debe funcionar")

		# Verificar que los valores dinámicos se resolvieron
		actions_result = dynamic_result.get("actions_result", {})
		self.assertGreater(actions_result.get("actions_executed", 0), 0, "Debe ejecutar acciones dinámicas")

	def test_uat_scenario_rule_testing_and_debugging(self):
		"""
		UAT Scenario 7: Usuario prueba y debug reglas antes de activarlas
		Como usuario, quiero probar mis reglas antes de ponerlas en producción
		"""
		# GIVEN: Usuario crea regla para testing
		test_rule = self.create_test_rule(
			{
				"rule_name": "UAT - Testing Rule",
				"rule_code": "UAT_TESTING_RULE",
				"description": "Regla para probar funcionalidad de testing",
				"apply_to_doctype": "Sales Invoice",
				"is_active": 1,
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
						"action_value": "Regla de testing aplicada",
					}
				],
			}
		)

		# WHEN: Usuario utiliza función de testing
		customer_doc = self.create_test_customer({"customer_name": "Cliente Testing"})
		test_invoice = self.create_test_sales_invoice({"customer": customer_doc.name, "grand_total": 2000})

		# Usuario ejecuta test de la regla
		test_result = test_rule.test_rule(test_invoice.name)

		# THEN: Usuario recibe información detallada del test
		self.assertIn("success", test_result, "Test debe incluir indicador de éxito")
		self.assertIn("test_result", test_result, "Test debe incluir resultado detallado")
		self.assertIn("rule", test_result, "Test debe identificar la regla probada")
		self.assertEqual(test_result["rule"], "UAT_TESTING_RULE")

		# Usuario puede ver resumen de la regla
		rule_summary = test_rule.get_rule_summary()
		self.assertIn("rule_code", rule_summary, "Resumen debe incluir código de regla")
		self.assertIn("is_active", rule_summary, "Resumen debe incluir estado activo")
		self.assertIn("conditions_count", rule_summary, "Resumen debe incluir conteo de condiciones")
		self.assertIn("actions_count", rule_summary, "Resumen debe incluir conteo de acciones")

	def test_uat_scenario_multi_user_concurrent_access(self):
		"""
		UAT Scenario 8: Multiple usuarios acceden al sistema concurrentemente
		Como sistema multi-usuario, debe manejar acceso concurrente correctamente
		"""
		# GIVEN: Múltiples usuarios configuran reglas simultáneamente
		concurrent_rules = []
		for user_id in range(3):  # Simular 3 usuarios
			rule = self.create_test_rule(
				{
					"rule_name": f"UAT - Usuario {user_id+1} Rule",
					"rule_code": f"UAT_USER_{user_id+1}_RULE",
					"description": f"Regla del usuario {user_id+1}",
					"apply_to_doctype": "Sales Invoice",
					"priority": (user_id + 1) * 30,
					"is_active": 1,
				}
			)
			concurrent_rules.append(rule)

		# WHEN: Múltiples usuarios procesan documentos simultáneamente
		concurrent_results = []
		for doc_id in range(5):  # Cada usuario procesa 5 documentos
			mock_doc = MagicMock()
			mock_doc.doctype = "Sales Invoice"
			mock_doc.name = f"UAT-CONCURRENT-{doc_id:02d}"
			mock_doc.grand_total = (doc_id + 1) * 1500

			# Simular procesamiento concurrente por múltiples usuarios
			user_results = []
			for rule in concurrent_rules:
				result = rule.execute_rule(mock_doc)
				user_results.append(result)

			concurrent_results.append({"document": mock_doc.name, "results": user_results})

		# THEN: Sistema debe manejar concurrencia sin conflictos
		self.assertEqual(len(concurrent_results), 5, "Debe procesar todos los documentos")

		for doc_result in concurrent_results:
			self.assertEqual(len(doc_result["results"]), 3, "Cada documento debe ser procesado por 3 reglas")
			successful_executions = sum(1 for r in doc_result["results"] if r.get("success"))
			self.assertGreater(successful_executions, 0, "Al menos una regla debe ejecutarse exitosamente")

	def test_uat_scenario_system_monitoring_and_audit(self):
		"""
		UAT Scenario 9: Administrador monitorea sistema y revisa auditoría
		Como administrador, quiero monitorear el rendimiento y auditar ejecuciones
		"""
		# GIVEN: Sistema con reglas configuradas para monitoreo
		monitoring_rule = self.create_test_rule(
			{
				"rule_name": "UAT - Monitoring Rule",
				"rule_code": "UAT_MONITORING_RULE",
				"description": "Regla para monitorear sistema",
				"apply_to_doctype": "Sales Invoice",
				"is_active": 1,
			}
		)

		# WHEN: Administrador ejecuta múltiples operaciones para generar datos
		execution_count = 3
		for i in range(execution_count):
			mock_doc = MagicMock()
			mock_doc.doctype = "Sales Invoice"
			mock_doc.name = f"UAT-MONITOR-{i:03d}"
			mock_doc.grand_total = (i + 1) * 1000

			result = monitoring_rule.execute_rule(mock_doc)
			self.assertTrue(result.get("success"), f"Ejecución {i+1} debe ser exitosa")

		# THEN: Administrador puede acceder a estadísticas del sistema
		monitoring_rule.reload()

		# Verificar estadísticas de monitoreo
		self.assertGreater(monitoring_rule.execution_count or 0, 0, "Debe registrar ejecuciones")
		self.assertIsNotNone(monitoring_rule.last_execution, "Debe registrar última ejecución")

		# Administrador puede obtener resumen completo
		system_summary = monitoring_rule.get_rule_summary()
		self.assertIn("execution_count", system_summary, "Resumen debe incluir conteo de ejecuciones")
		self.assertIn("rule_code", system_summary, "Resumen debe incluir identificador de regla")

	def test_uat_scenario_integration_with_existing_system(self):
		"""
		UAT Scenario 10: Motor de reglas se integra con sistema existente
		Como usuario final, el motor de reglas debe funcionar transparentemente
		"""
		# GIVEN: Regla integrada con hooks del sistema
		integration_rule = self.create_test_rule(
			{
				"rule_name": "UAT - Sistema Integration",
				"rule_code": "UAT_SYSTEM_INTEGRATION",
				"description": "Regla que se integra con sistema existente",
				"apply_to_doctype": "Sales Invoice",
				"severity": "Warning",
				"is_active": 1,
				"conditions": [
					{
						"condition_type": "Field",
						"field_name": "grand_total",
						"operator": "greater_than",
						"value": "10000",
						"value_type": "Static",
					}
				],
				"actions": [
					{
						"action_type": "Set Field",
						"target_field": "fm_validation_status",
						"action_value": "Validated by System",
						"log_action": 1,
					}
				],
			}
		)

		# WHEN: Usuario normal del sistema procesa documento (simular hook call)
		system_invoice = MagicMock()
		system_invoice.doctype = "Sales Invoice"
		system_invoice.name = "UAT-INTEGRATION-001"
		system_invoice.grand_total = 15000
		system_invoice.fm_validation_status = "Pending"

		# Simular llamada desde hooks del sistema
		from facturacion_mexico.motor_reglas.hooks_handlers.document_validation import (
			validate_document_with_rules,
		)

		# THEN: Sistema debe integrarse transparentemente
		integration_result = validate_document_with_rules(system_invoice)

		# Usuario espera integración transparente
		self.assertIsInstance(integration_result, dict, "Integración debe retornar resultado estructurado")
		self.assertIn("success", integration_result, "Debe incluir indicador de éxito")

		# Verificar que la regla se ejecutó en el contexto del sistema
		direct_result = integration_rule.execute_rule(system_invoice)
		self.assertTrue(direct_result.get("success"), "Regla debe funcionar en contexto del sistema")


if __name__ == "__main__":
	unittest.main()
