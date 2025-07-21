"""
Layer 3: System Tests - Motor de Reglas
Tests de sistema completo para validar comportamiento end-to-end
"""

import time
import unittest
from unittest.mock import MagicMock, patch

import frappe

from facturacion_mexico.motor_reglas.tests.test_base_motor_reglas import MotorReglasTestBase


class TestMotorReglasSystem(MotorReglasTestBase):
	"""Tests de sistema completo para motor de reglas."""

	def test_complete_invoice_validation_workflow(self):
		"""Test workflow completo de validación de facturas."""
		# Crear reglas del sistema real para validación de facturas
		validation_rule = self.create_test_rule(
			{
				"rule_name": "Sistema Validación Facturas",
				"rule_code": "SYS_INVOICE_VALIDATION",
				"description": "Validación completa del sistema para facturas",
				"rule_type": "Validation",
				"apply_to_doctype": "Sales Invoice",
				"severity": "Error",
				"is_active": 1,
				"priority": 10,
				"conditions": [
					{
						"condition_type": "Field",
						"field_name": "grand_total",
						"operator": "greater_than",
						"value": "0",
						"value_type": "Static",
						"logical_operator": "AND",
					},
					{
						"condition_type": "Field",
						"field_name": "customer",
						"operator": "is_set",
						"value": "",
						"value_type": "Static",
						"logical_operator": "AND",
					},
					{
						"condition_type": "Field",
						"field_name": "status",
						"operator": "not_equals",
						"value": "Cancelled",
						"value_type": "Static",
					},
				],
				"actions": [
					{
						"action_type": "Set Field",
						"target_field": "fm_validation_status",
						"action_value": "System Validated",
						"log_action": 1,
					},
					{
						"action_type": "Set Field",
						"target_field": "remarks",
						"action_value": "Sistema validado automáticamente",
						"log_action": 1,
					},
				],
			}
		)

		# Simular documento real del sistema
		system_invoice = MagicMock()
		system_invoice.doctype = "Sales Invoice"
		system_invoice.name = "SYS-INV-001"
		system_invoice.grand_total = 15000.00
		system_invoice.customer = "Cliente Sistema Real"
		system_invoice.status = "Draft"
		system_invoice.fm_validation_status = "Pending"
		system_invoice.remarks = ""

		# Ejecutar validación completa del sistema
		start_time = time.time()
		validation_result = validation_rule.execute_rule(system_invoice)
		execution_time = time.time() - start_time

		# Validar resultado del sistema
		self.assertTrue(validation_result.get("success"))
		self.assertTrue(validation_result.get("executed"))
		self.assertTrue(validation_result.get("conditions_met"))
		self.assertLess(execution_time, 1.0, "Sistema debe procesar en menos de 1 segundo")

		# Validar que se crearon logs de ejecución
		self.assertIn("actions_result", validation_result)
		actions_result = validation_result["actions_result"]
		self.assertGreater(actions_result.get("actions_executed", 0), 0)

	def test_high_volume_rules_performance(self):
		"""Test performance del sistema con alto volumen de reglas."""
		# Crear múltiples reglas del sistema
		system_rules = []
		for i in range(10):
			rule = self.create_test_rule(
				{
					"rule_name": f"Sistema Regla {i+1}",
					"rule_code": f"SYS_RULE_{i+1:03d}",
					"apply_to_doctype": "Sales Invoice",
					"priority": (i * 10) + 10,
					"is_active": 1,
					"conditions": [
						{
							"condition_type": "Field",
							"field_name": "grand_total",
							"operator": "greater_than",
							"value": str(i * 1000),
							"value_type": "Static",
						}
					],
					"actions": [
						{
							"action_type": "Set Field",
							"target_field": "remarks",
							"action_value": f"Procesado por regla sistema {i+1}",
						}
					],
				}
			)
			system_rules.append(rule)

		# Simular procesamiento de múltiples documentos
		documents_processed = []
		total_start_time = time.time()

		for doc_id in range(5):
			mock_doc = MagicMock()
			mock_doc.doctype = "Sales Invoice"
			mock_doc.name = f"SYS-PERF-{doc_id:03d}"
			mock_doc.grand_total = (doc_id + 1) * 2000
			mock_doc.remarks = ""

			# Ejecutar todas las reglas del sistema
			doc_start_time = time.time()
			results = []
			for rule in system_rules:
				result = rule.execute_rule(mock_doc)
				results.append(result)

			doc_execution_time = time.time() - doc_start_time
			documents_processed.append(
				{"document": mock_doc.name, "execution_time": doc_execution_time, "results": results}
			)

		total_execution_time = time.time() - total_start_time

		# Validar performance del sistema
		self.assertEqual(len(documents_processed), 5)
		self.assertLess(total_execution_time, 5.0, "Sistema debe procesar 5 docs en menos de 5 segundos")

		# Validar que cada documento fue procesado correctamente
		for doc_result in documents_processed:
			self.assertLess(doc_result["execution_time"], 2.0, "Cada documento en menos de 2 segundos")
			successful_executions = sum(1 for r in doc_result["results"] if r.get("success"))
			self.assertGreater(successful_executions, 0, "Al menos una regla debe ejecutarse")

	def test_system_rule_caching_effectiveness(self):
		"""Test efectividad del sistema de caché en condiciones reales."""
		# Crear regla del sistema con caché
		cached_rule = self.create_test_rule(
			{
				"rule_name": "Sistema Caché Efectivo",
				"rule_code": "SYS_CACHE_EFFECTIVE",
				"apply_to_doctype": "Sales Invoice",
				"is_active": 1,
			}
		)

		# Primera ejecución - sin caché
		start_time = time.time()
		cached_rule.compile_rule_cache()
		cache_compile_time = time.time() - start_time

		# Simular múltiples ejecuciones con caché
		mock_doc = MagicMock()
		mock_doc.doctype = "Sales Invoice"
		mock_doc.name = "SYS-CACHE-001"
		mock_doc.grand_total = 5000

		cached_executions = []
		for _ in range(10):
			start_time = time.time()
			cached_rule.execute_rule(mock_doc)  # Execute rule to test caching
			execution_time = time.time() - start_time
			cached_executions.append(execution_time)

		# Validar efectividad del caché
		self.assertLess(cache_compile_time, 0.5, "Compilación de caché debe ser rápida")
		avg_cached_time = sum(cached_executions) / len(cached_executions)
		self.assertLess(avg_cached_time, 0.1, "Ejecuciones con caché deben ser muy rápidas")

		# Verificar consistencia de resultados
		for i in range(5):
			consistency_result = cached_rule.execute_rule(mock_doc)
			self.assertTrue(consistency_result.get("success"), f"Ejecución {i+1} debe ser consistente")

	def test_system_error_recovery_and_resilience(self):
		"""Test recuperación de errores y resistencia del sistema."""
		# Crear regla que puede fallar
		error_prone_rule = self.create_test_rule(
			{
				"rule_name": "Sistema Recuperación Errores",
				"rule_code": "SYS_ERROR_RECOVERY",
				"apply_to_doctype": "Sales Invoice",
				"is_active": 1,
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
						"action_value": "Sistema recuperado del error",
						"continue_on_error": 1,
					}
				],
			}
		)

		# Simular documentos con datos válidos e inválidos
		test_scenarios = [
			{
				"name": "SYS-ERROR-VALID",
				"data": {"grand_total": 1000, "customer": "Valid Customer"},
				"expected_success": True,
			},
			{
				"name": "SYS-ERROR-INVALID",
				"data": {"grand_total": None, "customer": None},
				"expected_success": True,  # Debe recuperarse gracefully
			},
			{
				"name": "SYS-ERROR-EMPTY",
				"data": {},
				"expected_success": True,  # Debe manejar datos vacíos
			},
		]

		recovery_results = []
		for scenario in test_scenarios:
			mock_doc = MagicMock()
			mock_doc.doctype = "Sales Invoice"
			mock_doc.name = scenario["name"]

			# Configurar datos del escenario
			for key, value in scenario["data"].items():
				setattr(mock_doc, key, value)

			# Ejecutar regla y capturar resultado
			try:
				result = error_prone_rule.execute_rule(mock_doc)
				recovery_results.append(
					{
						"scenario": scenario["name"],
						"success": result.get("success", False),
						"error": result.get("error"),
						"recovered": True,
					}
				)
			except Exception as e:
				recovery_results.append(
					{"scenario": scenario["name"], "success": False, "error": str(e), "recovered": False}
				)

		# Validar recuperación del sistema
		for result in recovery_results:
			self.assertTrue(
				result["recovered"], f"Sistema debe recuperarse en escenario {result['scenario']}"
			)

		# Validar que el sistema sigue funcionando después de errores
		normal_doc = MagicMock()
		normal_doc.doctype = "Sales Invoice"
		normal_doc.name = "SYS-ERROR-FINAL"
		normal_doc.grand_total = 2000

		final_result = error_prone_rule.execute_rule(normal_doc)
		self.assertIsInstance(final_result, dict, "Sistema debe seguir funcionando después de errores")

	def test_system_concurrent_rule_execution(self):
		"""Test ejecución concurrente de reglas del sistema."""
		# Crear reglas para prueba de concurrencia
		concurrent_rules = []
		for i in range(5):
			rule = self.create_test_rule(
				{
					"rule_name": f"Sistema Concurrente {i+1}",
					"rule_code": f"SYS_CONCURRENT_{i+1:02d}",
					"apply_to_doctype": "Sales Invoice",
					"priority": (i + 1) * 20,
					"is_active": 1,
					"conditions": [
						{
							"condition_type": "Field",
							"field_name": "grand_total",
							"operator": "greater_than",
							"value": "100",
							"value_type": "Static",
						}
					],
					"actions": [
						{
							"action_type": "Set Field",
							"target_field": "remarks",
							"action_value": f"Procesado concurrentemente {i+1}",
							"log_action": 1,
						}
					],
				}
			)
			concurrent_rules.append(rule)

		# Simular múltiples documentos procesándose "concurrentemente"
		concurrent_documents = []
		for doc_id in range(3):
			mock_doc = MagicMock()
			mock_doc.doctype = "Sales Invoice"
			mock_doc.name = f"SYS-CONCURRENT-{doc_id:02d}"
			mock_doc.grand_total = (doc_id + 1) * 1500
			mock_doc.remarks = ""
			concurrent_documents.append(mock_doc)

		# Ejecutar reglas en simulación de concurrencia
		execution_results = []
		start_time = time.time()

		for doc in concurrent_documents:
			doc_results = []
			for rule in concurrent_rules:
				result = rule.execute_rule(doc)
				doc_results.append(result)
			execution_results.append({"document": doc.name, "results": doc_results})

		total_time = time.time() - start_time

		# Validar comportamiento concurrente
		self.assertEqual(len(execution_results), 3, "Todos los documentos deben procesarse")
		self.assertLess(total_time, 3.0, "Procesamiento concurrente debe ser eficiente")

		# Validar integridad de datos en ejecución concurrente
		for doc_result in execution_results:
			successful_rules = sum(1 for r in doc_result["results"] if r.get("success"))
			self.assertGreater(successful_rules, 0, "Al menos una regla debe ejecutarse por documento")

	def test_system_integration_with_frappe_framework(self):
		"""Test integración completa con Frappe Framework."""
		# Crear regla que integra con features de Frappe
		frappe_integration_rule = self.create_test_rule(
			{
				"rule_name": "Sistema Integración Frappe",
				"rule_code": "SYS_FRAPPE_INTEGRATION",
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
						"target_field": "fm_validation_timestamp",
						"action_value": "NOW",
						"value_type": "Dynamic",
						"log_action": 1,
					}
				],
			}
		)

		# Mock document con integración Frappe
		frappe_doc = MagicMock()
		frappe_doc.doctype = "Sales Invoice"
		frappe_doc.name = "SYS-FRAPPE-001"
		frappe_doc.posting_date = frappe.utils.today()
		frappe_doc.fm_validation_timestamp = None

		# Ejecutar con contexto Frappe completo
		with patch("frappe.utils.now_datetime") as mock_now:
			mock_now.return_value = "2025-07-21 10:30:00"

			result = frappe_integration_rule.execute_rule(frappe_doc)

			# Validar integración exitosa
			self.assertTrue(result.get("success"))
			self.assertTrue(result.get("executed"))

		# Validar que se usaron funciones de Frappe
		self.assertIn("actions_result", result)

	def test_system_rule_lifecycle_management(self):
		"""Test gestión completa del ciclo de vida de reglas."""
		# Crear regla con ciclo de vida completo
		lifecycle_rule = self.create_test_rule(
			{
				"rule_name": "Sistema Ciclo Vida",
				"rule_code": "SYS_LIFECYCLE_001",
				"apply_to_doctype": "Sales Invoice",
				"is_active": 1,
				"effective_date": frappe.utils.add_days(frappe.utils.today(), -1),
				"expiry_date": frappe.utils.add_days(frappe.utils.today(), 1),
			}
		)

		# Test regla activa dentro de fechas de vigencia
		mock_doc = MagicMock()
		mock_doc.doctype = "Sales Invoice"
		mock_doc.name = "SYS-LIFECYCLE-001"
		mock_doc.grand_total = 1000

		active_result = lifecycle_rule.execute_rule(mock_doc)
		self.assertTrue(active_result.get("success"))
		self.assertNotEqual(active_result.get("skipped"), True)

		# Test regla fuera de vigencia (simular fecha futura)
		lifecycle_rule.expiry_date = frappe.utils.add_days(frappe.utils.today(), -1)
		lifecycle_rule.save()

		expired_result = lifecycle_rule.execute_rule(mock_doc)
		self.assertTrue(expired_result.get("success"))
		self.assertTrue(expired_result.get("skipped"))
		self.assertEqual(expired_result.get("reason"), "Rule expired")

		# Test desactivación de regla
		lifecycle_rule.is_active = 0
		lifecycle_rule.save()

		inactive_result = lifecycle_rule.execute_rule(mock_doc)
		self.assertTrue(inactive_result.get("success"))
		self.assertTrue(inactive_result.get("skipped"))
		self.assertEqual(inactive_result.get("reason"), "Rule not active")

	def test_system_statistics_and_monitoring(self):
		"""Test sistema de estadísticas y monitoreo completo."""
		# Crear regla para monitoreo
		monitoring_rule = self.create_test_rule(
			{
				"rule_name": "Sistema Monitoreo",
				"rule_code": "SYS_MONITORING_001",
				"apply_to_doctype": "Sales Invoice",
				"is_active": 1,
			}
		)

		# Ejecutar múltiples veces para generar estadísticas
		execution_times = []
		for i in range(5):
			mock_doc = MagicMock()
			mock_doc.doctype = "Sales Invoice"
			mock_doc.name = f"SYS-MONITOR-{i:03d}"
			mock_doc.grand_total = (i + 1) * 1000

			start_time = time.time()
			result = monitoring_rule.execute_rule(mock_doc)
			execution_time = time.time() - start_time
			execution_times.append(execution_time)

			self.assertTrue(result.get("success"))

		# Recargar regla para obtener estadísticas actualizadas
		monitoring_rule.reload()

		# Validar estadísticas del sistema
		self.assertGreaterEqual(monitoring_rule.execution_count or 0, 5)
		self.assertIsNotNone(monitoring_rule.last_execution)
		self.assertGreater(monitoring_rule.average_execution_time or 0, 0)

		# Validar consistencia de estadísticas
		avg_recorded = monitoring_rule.average_execution_time
		avg_measured = sum(execution_times) / len(execution_times) * 1000  # Convert to ms
		# Permitir diferencia del 50% debido a overhead del sistema
		self.assertLess(
			abs(avg_recorded - avg_measured) / avg_measured,
			0.5,
			"Estadísticas deben ser aproximadamente correctas",
		)

	def test_system_api_integration_end_to_end(self):
		"""Test integración end-to-end con APIs del sistema."""
		# Crear regla accesible via API
		api_rule = self.create_test_rule(
			{
				"rule_name": "Sistema API E2E",
				"rule_code": "SYS_API_E2E_001",
				"apply_to_doctype": "Sales Invoice",
				"is_active": 1,
			}
		)

		# Test API de obtener reglas activas
		from facturacion_mexico.motor_reglas.doctype.fiscal_validation_rule.fiscal_validation_rule import (
			FiscalValidationRule,
		)

		active_rules = FiscalValidationRule.get_active_rules_for_doctype("Sales Invoice")
		rule_codes = [rule["rule_code"] for rule in active_rules]
		self.assertIn("SYS_API_E2E_001", rule_codes)

		# Test API de testing de reglas
		mock_doc = MagicMock()
		mock_doc.doctype = "Sales Invoice"
		mock_doc.name = "SYS-API-TEST-001"
		mock_doc.grand_total = 5000

		# Simular llamada API para test de regla
		api_test_result = api_rule.test_rule("SYS-API-TEST-001")

		# Validar respuesta de API
		self.assertIsInstance(api_test_result, dict)
		self.assertIn("success", api_test_result)
		self.assertIn("rule", api_test_result)
		self.assertEqual(api_test_result["rule"], "SYS_API_E2E_001")

		# Test API de resumen de regla
		rule_summary = api_rule.get_rule_summary()
		self.assertIn("rule_code", rule_summary)
		self.assertIn("execution_count", rule_summary)
		self.assertIn("is_active", rule_summary)
		self.assertEqual(rule_summary["rule_code"], "SYS_API_E2E_001")

	def test_system_scalability_under_load(self):
		"""Test escalabilidad del sistema bajo carga."""
		# Crear conjunto de reglas para test de carga
		load_rules = []
		for i in range(20):  # 20 reglas para simular carga
			rule = self.create_test_rule(
				{
					"rule_name": f"Sistema Carga {i+1}",
					"rule_code": f"SYS_LOAD_{i+1:03d}",
					"apply_to_doctype": "Sales Invoice",
					"priority": (i + 1) * 5,
					"is_active": 1,
				}
			)
			load_rules.append(rule)

		# Simular carga de procesamiento
		load_test_start = time.time()
		processed_docs = 0
		failed_executions = 0

		for doc_batch in range(10):  # 10 batches de documentos
			batch_start = time.time()

			for doc_id in range(5):  # 5 documentos por batch
				mock_doc = MagicMock()
				mock_doc.doctype = "Sales Invoice"
				mock_doc.name = f"SYS-LOAD-B{doc_batch:02d}-D{doc_id:02d}"
				mock_doc.grand_total = (doc_batch * 5 + doc_id + 1) * 500

				# Ejecutar todas las reglas por documento
				for rule in load_rules:
					try:
						result = rule.execute_rule(mock_doc)
						if not result.get("success"):
							failed_executions += 1
					except Exception:
						failed_executions += 1

				processed_docs += 1

			batch_time = time.time() - batch_start
			# Cada batch debe procesar en tiempo razonable
			self.assertLess(batch_time, 5.0, f"Batch {doc_batch} debe procesar en menos de 5 segundos")

		total_load_time = time.time() - load_test_start

		# Validar escalabilidad
		self.assertEqual(processed_docs, 50, "Deben procesarse todos los documentos")
		self.assertLess(total_load_time, 30.0, "Carga completa debe procesar en menos de 30 segundos")
		failure_rate = failed_executions / (processed_docs * len(load_rules))
		self.assertLess(failure_rate, 0.1, "Tasa de fallos debe ser menor al 10%")

		# Validar que el sistema sigue respondiendo después de la carga
		post_load_doc = MagicMock()
		post_load_doc.doctype = "Sales Invoice"
		post_load_doc.name = "SYS-POST-LOAD-001"
		post_load_doc.grand_total = 10000

		post_load_result = load_rules[0].execute_rule(post_load_doc)
		self.assertTrue(post_load_result.get("success"), "Sistema debe seguir funcionando después de carga")


if __name__ == "__main__":
	unittest.main()
