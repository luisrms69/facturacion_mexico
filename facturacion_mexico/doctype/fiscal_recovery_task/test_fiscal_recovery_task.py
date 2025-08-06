# Copyright (c) 2025, Frappe Technologies and Contributors
# See license.txt

"""
Tests para Fiscal Recovery Task
Tests críticos de recuperación automática y límites de reintentos
"""

import unittest
from datetime import datetime, timedelta

import frappe
from frappe.tests.utils import FrappeTestCase


class TestFiscalRecoveryTask(FrappeTestCase):
	"""Tests para Fiscal Recovery Task - Recuperación Automática y Límites"""

	def setUp(self):
		"""Setup para cada test - limpiar datos previos"""
		frappe.set_user("Administrator")

		# Limpiar recovery tasks de test previos
		frappe.db.sql("DELETE FROM `tabFiscal Recovery Task` WHERE task_type LIKE 'test_%'")
		frappe.db.commit()

	def test_doctype_creation_with_defaults(self):
		"""
		Test: Crear DocType con valores por defecto inteligentes

		Validaciones:
		- naming_series funciona correctamente
		- created_by_system se establece automáticamente
		- defaults según task_type (timeout_recovery = high priority)
		- max_attempts default = 3
		"""
		# Crear recovery task básica
		task_doc = frappe.new_doc("Fiscal Recovery Task")
		task_doc.task_type = "timeout_recovery"
		task_doc.reference_doctype = "FacturAPI Response Log"
		task_doc.reference_name = "TEST-LOG-001"
		task_doc.scheduled_time = frappe.utils.add_to_date(frappe.utils.now(), minutes=5)

		# Insertar
		task_doc.insert(ignore_permissions=True)

		# Validaciones
		self.assertTrue(task_doc.name.startswith("RECOVERY-"), "Naming series debe funcionar")
		self.assertEqual(task_doc.created_by_system, "Administrator")
		self.assertEqual(task_doc.priority, "high", "timeout_recovery debe ser high priority")
		self.assertEqual(task_doc.max_attempts, 3, "max_attempts default debe ser 3")
		self.assertEqual(task_doc.status, "pending", "status inicial debe ser pending")

		print(f"✅ DocType creado: {task_doc.name} con priority: {task_doc.priority}")

	def test_scheduled_time_future_validation(self):
		"""
		Test: Validar que scheduled_time debe estar en el futuro

		Validaciones:
		- scheduled_time en el pasado genera error
		- scheduled_time en el futuro se acepta
		- Mensaje de error claro
		"""
		# Test con tiempo pasado (debe fallar)
		task_doc = frappe.new_doc("Fiscal Recovery Task")
		task_doc.task_type = "test_past_time"
		task_doc.reference_doctype = "Test DocType"
		task_doc.reference_name = "TEST-001"
		task_doc.scheduled_time = frappe.utils.add_to_date(frappe.utils.now(), minutes=-5)

		with self.assertRaises(frappe.ValidationError):
			task_doc.insert(ignore_permissions=True)

		# Test con tiempo futuro (debe funcionar)
		task_doc2 = frappe.new_doc("Fiscal Recovery Task")
		task_doc2.task_type = "test_future_time"
		task_doc2.reference_doctype = "Test DocType"
		task_doc2.reference_name = "TEST-002"
		task_doc2.scheduled_time = frappe.utils.add_to_date(frappe.utils.now(), minutes=5)

		# Debe insertar sin problemas
		task_doc2.insert(ignore_permissions=True)

		print("✅ Validación de scheduled_time en futuro funciona correctamente")

	def test_duplicate_task_prevention(self):
		"""
		Test: Prevenir tareas duplicadas para el mismo documento

		Validaciones:
		- No se pueden crear dos tareas pending/processing para mismo documento
		- Tareas completed/failed sí se pueden duplicar
		- Error claro cuando se intenta duplicar
		"""
		# Crear primera tarea
		task1 = frappe.new_doc("Fiscal Recovery Task")
		task1.task_type = "test_duplicate_check"
		task1.reference_doctype = "Test DocType"
		task1.reference_name = "DUPLICATE-TEST"
		task1.scheduled_time = frappe.utils.add_to_date(frappe.utils.now(), minutes=5)
		task1.insert(ignore_permissions=True)

		# Intentar crear segunda tarea para mismo documento (debe fallar)
		task2 = frappe.new_doc("Fiscal Recovery Task")
		task2.task_type = "test_duplicate_check"
		task2.reference_doctype = "Test DocType"
		task2.reference_name = "DUPLICATE-TEST"
		task2.scheduled_time = frappe.utils.add_to_date(frappe.utils.now(), minutes=10)

		with self.assertRaises(frappe.ValidationError):
			task2.insert(ignore_permissions=True)

		# Si primera tarea está completed, sí se puede crear otra
		task1.status = "completed"
		task1.save(ignore_permissions=True)

		# Ahora sí debe funcionar
		task2.insert(ignore_permissions=True)

		print("✅ Prevención de tareas duplicadas funciona correctamente")

	def test_max_attempts_limit_validation(self):
		"""
		Test: Validar límite máximo de attempts

		Validaciones:
		- max_attempts no puede exceder 5
		- attempts que exceden max_attempts marcan como exceeded_attempts
		- Escalación automática cuando se excede
		"""
		# Test con max_attempts demasiado alto
		task_doc = frappe.new_doc("Fiscal Recovery Task")
		task_doc.task_type = "test_max_attempts"
		task_doc.reference_doctype = "Test DocType"
		task_doc.reference_name = "MAX-TEST"
		task_doc.max_attempts = 10  # Excede límite
		task_doc.scheduled_time = frappe.utils.add_to_date(frappe.utils.now(), minutes=5)

		with self.assertRaises(frappe.ValidationError):
			task_doc.insert(ignore_permissions=True)

		# Test con attempts que exceden max
		task_doc2 = frappe.new_doc("Fiscal Recovery Task")
		task_doc2.task_type = "test_exceeded_attempts"
		task_doc2.reference_doctype = "Test DocType"
		task_doc2.reference_name = "EXCEEDED-TEST"
		task_doc2.max_attempts = 3
		task_doc2.attempts = 4  # Excede max_attempts
		task_doc2.scheduled_time = frappe.utils.add_to_date(frappe.utils.now(), minutes=5)
		task_doc2.insert(ignore_permissions=True)

		# Debe haber marcado como exceeded_attempts
		self.assertEqual(task_doc2.status, "exceeded_attempts")

		print("✅ Validación de límites max_attempts funciona correctamente")

	def test_mark_as_processing_functionality(self):
		"""
		Test: Verificar funcionalidad mark_as_processing

		Validaciones:
		- Actualiza status a "processing"
		- Establece last_attempt timestamp
		- Commit automático para evitar concurrencia
		"""
		# Crear tarea
		task_doc = frappe.new_doc("Fiscal Recovery Task")
		task_doc.task_type = "test_processing"
		task_doc.reference_doctype = "Test DocType"
		task_doc.reference_name = "PROCESSING-TEST"
		task_doc.scheduled_time = frappe.utils.add_to_date(frappe.utils.now(), minutes=5)
		task_doc.insert(ignore_permissions=True)

		# Marcar como processing
		task_doc.mark_as_processing()

		# Validaciones
		self.assertEqual(task_doc.status, "processing")
		self.assertTrue(task_doc.last_attempt, "last_attempt debe estar establecido")

		# Recargar para verificar que se guardó
		task_doc.reload()
		self.assertEqual(task_doc.status, "processing")

		print("✅ mark_as_processing funciona correctamente")

	def test_mark_as_completed_functionality(self):
		"""
		Test: Verificar funcionalidad mark_as_completed

		Validaciones:
		- Actualiza status a "completed"
		- Guarda resolution_notes
		- Actualiza processing_notes con log
		"""
		# Crear tarea
		task_doc = frappe.new_doc("Fiscal Recovery Task")
		task_doc.task_type = "test_completion"
		task_doc.reference_doctype = "Test DocType"
		task_doc.reference_name = "COMPLETION-TEST"
		task_doc.scheduled_time = frappe.utils.add_to_date(frappe.utils.now(), minutes=5)
		task_doc.insert(ignore_permissions=True)

		# Marcar como completada
		resolution_notes = "Problema resuelto - PAC respondió exitosamente"
		task_doc.mark_as_completed(resolution_notes)

		# Validaciones
		self.assertEqual(task_doc.status, "completed")
		self.assertEqual(task_doc.resolution_notes, resolution_notes)
		self.assertTrue(task_doc.processing_notes, "processing_notes debe contener log")
		self.assertIn("COMPLETADO", task_doc.processing_notes)

		print("✅ mark_as_completed funciona correctamente")

	def test_mark_as_failed_with_retry(self):
		"""
		Test: Verificar funcionalidad mark_as_failed con reintento

		Validaciones:
		- Incrementa attempts counter
		- Guarda error_message y error_details
		- Reagenda para retry si should_retry=True
		- Aplica backoff exponencial
		"""
		# Crear tarea
		task_doc = frappe.new_doc("Fiscal Recovery Task")
		task_doc.task_type = "test_failed_retry"
		task_doc.reference_doctype = "Test DocType"
		task_doc.reference_name = "FAILED-RETRY-TEST"
		task_doc.scheduled_time = frappe.utils.add_to_date(frappe.utils.now(), minutes=5)
		task_doc.insert(ignore_permissions=True)

		original_scheduled = task_doc.scheduled_time

		# Marcar como fallida con retry
		error_details = {"error_code": "TIMEOUT", "response_time": 30000}
		task_doc.mark_as_failed("Timeout del PAC", error_details, should_retry=True)

		# Validaciones
		self.assertEqual(task_doc.attempts, 1)
		self.assertEqual(task_doc.status, "pending")  # Reagendada
		self.assertEqual(task_doc.last_error, "Timeout del PAC")
		self.assertTrue(task_doc.error_details, "error_details debe estar guardado")
		self.assertNotEqual(task_doc.scheduled_time, original_scheduled, "Debe reagendar")
		self.assertTrue(task_doc.processing_notes, "processing_notes debe contener log")

		print(f"✅ mark_as_failed con retry funciona - reagendado para {task_doc.scheduled_time}")

	def test_mark_as_failed_exceeds_attempts(self):
		"""
		Test: Verificar comportamiento cuando se exceden max_attempts

		Validaciones:
		- Status cambia a "exceeded_attempts"
		- escalated_flag se activa automáticamente
		- Se asigna a Fiscal Manager si existe
		"""
		# Crear tarea con max_attempts = 2 para test rápido
		task_doc = frappe.new_doc("Fiscal Recovery Task")
		task_doc.task_type = "test_exceeded_attempts"
		task_doc.reference_doctype = "Test DocType"
		task_doc.reference_name = "EXCEEDED-TEST"
		task_doc.max_attempts = 2
		task_doc.scheduled_time = frappe.utils.add_to_date(frappe.utils.now(), minutes=5)
		task_doc.insert(ignore_permissions=True)

		# Primer fallo
		task_doc.mark_as_failed("Error 1", should_retry=True)
		self.assertEqual(task_doc.status, "pending")  # Debe reagendar

		# Segundo fallo (excede max_attempts)
		task_doc.mark_as_failed("Error 2", should_retry=True)

		# Validaciones
		self.assertEqual(task_doc.status, "exceeded_attempts")
		self.assertTrue(task_doc.escalated_flag, "Debe estar escalado")
		self.assertEqual(task_doc.attempts, 2)

		print("✅ Escalación automática por max_attempts funciona correctamente")

	def test_static_create_timeout_recovery_task(self):
		"""
		Test: Verificar método estático para crear timeout recovery

		Validaciones:
		- Método crea tarea correctamente
		- Configuración específica para timeouts
		- Priority = high automático
		"""
		# Usar método estático
		task_doc = FiscalRecoveryTask.create_timeout_recovery_task(
			response_log_name="PAC-LOG-TEST-001", original_request_id="test-uuid-12345"
		)

		# Validaciones
		self.assertEqual(task_doc.task_type, "timeout_recovery")
		self.assertEqual(task_doc.reference_doctype, "FacturAPI Response Log")
		self.assertEqual(task_doc.reference_name, "PAC-LOG-TEST-001")
		self.assertEqual(task_doc.priority, "high")
		self.assertEqual(task_doc.original_request_id, "test-uuid-12345")
		self.assertTrue(task_doc.recovery_data, "recovery_data debe estar configurado")

		print(f"✅ Método estático create_timeout_recovery_task funciona: {task_doc.name}")

	def test_static_create_sync_error_task(self):
		"""
		Test: Verificar método estático para crear sync error recovery

		Validaciones:
		- Método crea tarea correctamente
		- Configuración específica para sync errors
		- Priority = medium por defecto
		"""
		# Usar método estático
		task_doc = FiscalRecoveryTask.create_sync_error_task(
			doctype="Sales Invoice",
			name="SI-TEST-001",
			error_description="Estados desincronizados entre Sales Invoice y Factura Fiscal",
		)

		# Validaciones
		self.assertEqual(task_doc.task_type, "sync_error")
		self.assertEqual(task_doc.reference_doctype, "Sales Invoice")
		self.assertEqual(task_doc.reference_name, "SI-TEST-001")
		self.assertEqual(task_doc.priority, "medium")
		self.assertEqual(task_doc.last_error, "Estados desincronizados entre Sales Invoice y Factura Fiscal")

		print(f"✅ Método estático create_sync_error_task funciona: {task_doc.name}")

	def test_state_transition_validation(self):
		"""
		Test: Verificar validación de transiciones de estado

		Validaciones:
		- Transiciones válidas se permiten
		- Transiciones inválidas generan error
		- Estados finales no permiten cambios
		"""
		# Crear tarea
		task_doc = frappe.new_doc("Fiscal Recovery Task")
		task_doc.task_type = "test_transitions"
		task_doc.reference_doctype = "Test DocType"
		task_doc.reference_name = "TRANSITION-TEST"
		task_doc.scheduled_time = frappe.utils.add_to_date(frappe.utils.now(), minutes=5)
		task_doc.insert(ignore_permissions=True)

		# Transición válida: pending → processing
		task_doc.status = "processing"
		task_doc.save(ignore_permissions=True)  # Debe funcionar

		# Transición válida: processing → completed
		task_doc.status = "completed"
		task_doc.save(ignore_permissions=True)  # Debe funcionar

		# Transición inválida: completed → pending (estado final)
		task_doc.status = "pending"
		with self.assertRaises(frappe.ValidationError):
			task_doc.save(ignore_permissions=True)

		print("✅ Validación de transiciones de estado funciona correctamente")

	def test_get_processing_summary(self):
		"""
		Test: Verificar método get_processing_summary para debugging

		Validaciones:
		- Retorna información clave estructurada
		- Incluye métricas importantes
		- Formato útil para debugging
		"""
		# Crear tarea con varios datos
		task_doc = frappe.new_doc("Fiscal Recovery Task")
		task_doc.task_type = "test_summary"
		task_doc.reference_doctype = "Test DocType"
		task_doc.reference_name = "SUMMARY-TEST"
		task_doc.priority = "high"
		task_doc.attempts = 2
		task_doc.max_attempts = 3
		task_doc.last_error = "Error de prueba para verificar summary"
		task_doc.scheduled_time = frappe.utils.add_to_date(frappe.utils.now(), minutes=5)
		task_doc.insert(ignore_permissions=True)

		# Obtener summary
		summary = task_doc.get_processing_summary()

		# Validaciones
		self.assertEqual(summary["task_type"], "test_summary")
		self.assertEqual(summary["priority"], "high")
		self.assertEqual(summary["attempts"], "2/3")
		self.assertEqual(summary["reference"], "Test DocType: SUMMARY-TEST")
		self.assertIn("Error de prueba", summary["last_error_summary"])

		print("✅ get_processing_summary proporciona información completa")

	def tearDown(self):
		"""Cleanup después de cada test"""
		frappe.db.sql("DELETE FROM `tabFiscal Recovery Task` WHERE task_type LIKE 'test_%'")
		frappe.db.commit()


# Importar la clase para que esté disponible para testing
from facturacion_mexico.doctype.fiscal_recovery_task.fiscal_recovery_task import FiscalRecoveryTask
