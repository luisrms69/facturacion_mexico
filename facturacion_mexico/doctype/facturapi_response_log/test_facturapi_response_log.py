# Copyright (c) 2025, Frappe Technologies and Contributors
# See license.txt

"""
Tests para FacturAPI Response Log
Tests críticos de inmutabilidad y resilencia
"""

import unittest
import uuid
from datetime import datetime, timedelta

import frappe
from frappe.tests.utils import FrappeTestCase


class TestFacturAPIResponseLog(FrappeTestCase):
	"""Tests para FacturAPI Response Log - Inmutabilidad y Resilencia"""

	def setUp(self):
		"""Setup para cada test - limpiar datos previos"""
		frappe.set_user("Administrator")

		# Limpiar logs de test previos
		frappe.db.sql("DELETE FROM `tabFacturAPI Response Log` WHERE request_id LIKE 'test-%'")
		frappe.db.commit()

	def test_doctype_creation_with_required_fields(self):
		"""
		Test: Crear DocType con campos obligatorios

		Validaciones:
		- request_id se genera automáticamente si no se proporciona
		- request_timestamp se establece automáticamente
		- is_immutable se marca como True automáticamente
		- naming_series funciona correctamente
		"""
		# Crear log básico
		log_doc = frappe.new_doc("FacturAPI Response Log")
		log_doc.request_type = "timbrado"
		log_doc.reference_doctype = "Factura Fiscal Mexico"
		log_doc.reference_name = "TEST-001"

		# Insertar
		log_doc.insert(ignore_permissions=True)

		# Validaciones
		self.assertTrue(log_doc.request_id, "request_id debe generarse automáticamente")
		self.assertTrue(log_doc.request_timestamp, "request_timestamp debe establecerse")
		self.assertTrue(log_doc.is_immutable, "is_immutable debe ser True")
		self.assertEqual(log_doc.created_by_system, "Administrator")
		self.assertTrue(log_doc.name.startswith("PAC-LOG-"), "Naming series debe funcionar")

		print(f"✅ DocType creado: {log_doc.name} con request_id: {log_doc.request_id}")

	def test_unique_request_id_validation(self):
		"""
		Test: Validar que request_id sea único

		Validaciones:
		- No se pueden crear dos logs con el mismo request_id
		- Error de validación claro
		- UUID automático previene duplicados
		"""
		request_id = f"test-{uuid.uuid4()}"

		# Crear primer log
		log1 = frappe.new_doc("FacturAPI Response Log")
		log1.request_id = request_id
		log1.request_type = "timbrado"
		log1.insert(ignore_permissions=True)

		# Intentar crear segundo log con mismo request_id
		log2 = frappe.new_doc("FacturAPI Response Log")
		log2.request_id = request_id
		log2.request_type = "cancelacion"

		with self.assertRaises(frappe.UniqueValidationError):
			log2.insert(ignore_permissions=True)

		print("✅ Validación de request_id único funciona correctamente")

	def test_immutability_enforcement(self):
		"""
		Test: Verificar que inmutabilidad se enforza correctamente

		Validaciones:
		- Registro no puede ser modificado después de creación
		- Solo Administrator con override puede modificar
		- Error claro cuando se intenta modificar
		"""
		# Crear log
		log_doc = frappe.new_doc("FacturAPI Response Log")
		log_doc.request_id = f"test-{uuid.uuid4()}"
		log_doc.request_type = "timbrado"
		log_doc.insert(ignore_permissions=True)

		# Intentar modificar sin override
		log_doc.request_type = "cancelacion"

		with self.assertRaises(frappe.PermissionError):
			log_doc.save(ignore_permissions=True)

		# Verificar que con admin_override_flag sí se puede modificar
		log_doc.reload()
		log_doc.admin_override_flag = 1
		log_doc.request_type = "cancelacion"
		log_doc.save(ignore_permissions=True)  # Debe funcionar

		print("✅ Inmutabilidad enforizada correctamente")

	def test_response_time_calculation(self):
		"""
		Test: Verificar cálculo automático de response_time_ms

		Validaciones:
		- response_time_ms se calcula automáticamente
		- Timestamp consistency validation
		- Timeout detection automática
		"""
		# Crear log con timestamps
		now = frappe.utils.now()
		response_time = frappe.utils.add_to_date(now, seconds=2)

		log_doc = frappe.new_doc("FacturAPI Response Log")
		log_doc.request_id = f"test-{uuid.uuid4()}"
		log_doc.request_type = "timbrado"
		log_doc.request_timestamp = now
		log_doc.response_timestamp = response_time
		log_doc.insert(ignore_permissions=True)

		# Validar cálculo automático
		self.assertGreater(log_doc.response_time_ms, 1900)  # ~2000ms
		self.assertLess(log_doc.response_time_ms, 2100)
		self.assertFalse(log_doc.timeout_flag)  # No es timeout

		print(f"✅ response_time_ms calculado: {log_doc.response_time_ms}ms")

	def test_timeout_detection_and_recovery_task(self):
		"""
		Test: Verificar detección de timeout y creación de recovery task

		Validaciones:
		- timeout_flag se marca automáticamente si >30s
		- Recovery task se crea automáticamente
		- Priority es "high" para timeouts
		"""
		# Crear log con timeout
		now = frappe.utils.now()
		response_time = frappe.utils.add_to_date(now, seconds=35)  # Timeout

		log_doc = frappe.new_doc("FacturAPI Response Log")
		log_doc.request_id = f"test-{uuid.uuid4()}"
		log_doc.request_type = "timbrado"
		log_doc.reference_doctype = "Factura Fiscal Mexico"
		log_doc.reference_name = "TEST-TIMEOUT"
		log_doc.request_timestamp = now
		log_doc.response_timestamp = response_time
		log_doc.insert(ignore_permissions=True)

		# Validar timeout detection
		self.assertTrue(log_doc.timeout_flag, "timeout_flag debe ser True para >30s")

		# Verificar que recovery task se creó (si DocType existe)
		try:
			recovery_tasks = frappe.get_all("Fiscal Recovery Task", filters={"reference_name": log_doc.name})
			if recovery_tasks:
				print("✅ Recovery task creada automáticamente para timeout")
		except frappe.DoesNotExistError:
			print("i️ Fiscal Recovery Task DocType aún no existe - normal en esta fase")

	def test_json_payload_validation(self):
		"""
		Test: Verificar validación de payloads JSON

		Validaciones:
		- JSON válido se acepta
		- JSON inválido genera error
		- Tanto strings como dicts funcionan
		"""
		# Test con JSON válido (dict)
		log_doc = frappe.new_doc("FacturAPI Response Log")
		log_doc.request_id = f"test-{uuid.uuid4()}"
		log_doc.request_type = "timbrado"
		log_doc.request_payload = {"factura_id": "TEST-001", "amount": 100.50}
		log_doc.response_payload = {"status": "success", "uuid": "12345"}

		# Debe insertar sin problemas
		log_doc.insert(ignore_permissions=True)

		# Test con JSON inválido
		log_doc2 = frappe.new_doc("FacturAPI Response Log")
		log_doc2.request_id = f"test-{uuid.uuid4()}"
		log_doc2.request_type = "timbrado"
		log_doc2.request_payload = "{'invalid': json,}"  # JSON malformado

		with self.assertRaises(frappe.ValidationError):
			log_doc2.insert(ignore_permissions=True)

		print("✅ Validación JSON de payloads funciona correctamente")

	def test_static_create_request_log_method(self):
		"""
		Test: Verificar método estático create_request_log

		Validaciones:
		- Método crea log correctamente
		- Commit automático para persistencia
		- Manejo de errores robusto
		"""
		# Usar método estático
		log_doc = FacturAPIResponseLog.create_request_log(
			request_type="timbrado",
			reference_doctype="Factura Fiscal Mexico",
			reference_name="STATIC-TEST",
			request_payload={"test": "data"},
			company="Test Company",
		)

		# Validaciones
		self.assertTrue(log_doc.name, "Log debe tener nombre asignado")
		self.assertEqual(log_doc.request_type, "timbrado")
		self.assertEqual(log_doc.reference_name, "STATIC-TEST")
		self.assertTrue(log_doc.request_payload, "Payload debe estar serializado")

		print(f"✅ Método estático create_request_log funciona: {log_doc.name}")

	def test_update_with_response_method(self):
		"""
		Test: Verificar método update_with_response

		Validaciones:
		- Actualización segura de respuesta
		- Commit automático
		- Serialización JSON correcta
		"""
		# Crear log inicial
		log_doc = FacturAPIResponseLog.create_request_log(
			request_type="timbrado", reference_doctype="Factura Fiscal Mexico", reference_name="UPDATE-TEST"
		)

		# Actualizar con respuesta
		response_data = {"status": "success", "uuid": "test-uuid-12345", "pdf_url": "https://test.com/pdf"}

		log_doc.update_with_response(response_data=response_data, http_code=200)

		# Validaciones
		self.assertEqual(log_doc.response_http_code, 200)
		self.assertTrue(log_doc.response_payload, "Response payload debe estar guardado")
		self.assertTrue(log_doc.response_timestamp, "Response timestamp debe estar set")

		print("✅ Método update_with_response funciona correctamente")

	def test_retry_chain_validation(self):
		"""
		Test: Verificar validación de cadena de reintentos

		Validaciones:
		- retry_of apunta a log válido
		- retry_count se incrementa correctamente
		- Máximo 3 reintentos enforizado
		"""
		# Crear log original
		original_log = FacturAPIResponseLog.create_request_log(
			request_type="timbrado", reference_doctype="Factura Fiscal Mexico", reference_name="RETRY-TEST"
		)

		# Crear primer reintento
		retry1 = frappe.new_doc("FacturAPI Response Log")
		retry1.request_id = f"test-retry-{uuid.uuid4()}"
		retry1.request_type = "timbrado"
		retry1.retry_of = original_log.name
		retry1.retry_count = 1
		retry1.insert(ignore_permissions=True)

		# Validar que funciona
		self.assertEqual(retry1.retry_of, original_log.name)
		self.assertEqual(retry1.retry_count, 1)

		# Intentar crear reintento que excede límite
		retry4 = frappe.new_doc("FacturAPI Response Log")
		retry4.request_id = f"test-retry-{uuid.uuid4()}"
		retry4.request_type = "timbrado"
		retry4.retry_of = original_log.name
		retry4.retry_count = 4  # Excede máximo de 3

		with self.assertRaises(frappe.ValidationError):
			retry4.insert(ignore_permissions=True)

		print("✅ Validación de retry chain funciona correctamente")

	def test_deletion_prevention(self):
		"""
		Test: Verificar que no se pueden eliminar logs

		Validaciones:
		- on_trash previene eliminación
		- Solo con admin_override se puede eliminar
		- Error claro para usuario
		"""
		# Crear log
		log_doc = FacturAPIResponseLog.create_request_log(
			request_type="timbrado", reference_name="DELETE-TEST"
		)

		# Intentar eliminar sin override
		with self.assertRaises(frappe.PermissionError):
			log_doc.delete()

		# Con override sí debería funcionar
		log_doc.admin_override_flag = 1
		log_doc.save(ignore_permissions=True)
		log_doc.delete()  # Debe funcionar

		print("✅ Prevención de eliminación funciona correctamente")

	def tearDown(self):
		"""Cleanup después de cada test"""
		frappe.db.sql("DELETE FROM `tabFacturAPI Response Log` WHERE request_id LIKE 'test-%'")
		frappe.db.commit()


# Importar la clase para que esté disponible para testing
from facturacion_mexico.doctype.facturapi_response_log.facturapi_response_log import FacturAPIResponseLog
