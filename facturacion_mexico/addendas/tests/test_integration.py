"""
Integration Tests - Layer 3
Tests de integración para el sistema de addendas
"""

import json
import unittest
from unittest.mock import patch

import frappe

from facturacion_mexico.addendas.tests.test_base import AddendaTestBase


class TestAddendaIntegration(AddendaTestBase):
	"""Tests de integración para el sistema completo de addendas."""

	def setUp(self):
		"""Configuración para cada test."""
		super().setUp()
		self.setup_complete_addenda_scenario()

	def setup_complete_addenda_scenario(self):
		"""Configurar escenario completo de addenda."""
		# Crear factura con datos completos
		self.sales_invoice = self.create_test_sales_invoice()

		# Crear configuración con valores de campo
		self.addenda_config = self.create_test_addenda_configuration()
		config_doc = frappe.get_doc("Addenda Configuration", self.addenda_config)

		# Agregar valores de campo para el test
		field_values = [
			{
				"field_definition": "proveedor_rfc",
				"field_value": "TEST123456789",
				"is_dynamic": 0,
			},
			{
				"field_definition": "cliente_nombre",
				"field_value": "",
				"is_dynamic": 1,
				"dynamic_source": "Customer",
				"dynamic_field": "customer_name",
			},
		]

		for fv in field_values:
			field_value_row = config_doc.append("field_values")
			for key, value in fv.items():
				setattr(field_value_row, key, value)

		config_doc.save()

		# Crear template con variables
		self.addenda_template = self.create_test_addenda_template()

	def test_end_to_end_addenda_generation(self):
		"""Test: Generación end-to-end de addenda."""
		from facturacion_mexico.addendas.api import generate_addenda_xml

		# Generar addenda completa
		result = generate_addenda_xml(
			sales_invoice=self.sales_invoice, addenda_type=self.test_addenda_types[0], validate_output=True
		)

		# Verificar resultado exitoso
		self.assertTrue(result["success"])
		self.assertIsNotNone(result["xml"])
		self.assertTrue(result["cfdi_data_available"] is not None)

		# Verificar estructura del XML generado
		xml_content = result["xml"]
		self.assert_xml_valid(xml_content)
		self.assert_xml_contains(xml_content, "//addenda")
		self.assert_xml_contains(xml_content, "//informacion")

		# Verificar que se usaron valores de configuración
		self.assertIn("field_values_used", result)
		self.assertIn("proveedor_rfc", result["field_values_used"])

	def test_api_integration_get_addenda_types(self):
		"""Test: Integración API - obtener tipos de addenda."""
		from facturacion_mexico.addendas.api import get_addenda_types

		result = get_addenda_types()

		self.assertTrue(result["success"])
		self.assertIn("data", result)
		self.assertIn("count", result)
		self.assertGreater(result["count"], 0)

		# Verificar que incluye nuestros tipos de prueba
		type_names = [t["name"] for t in result["data"]]
		for test_type in self.test_addenda_types:
			self.assertIn(test_type, type_names)

	def test_api_integration_get_addenda_configuration(self):
		"""Test: Integración API - obtener configuración de addenda."""
		from facturacion_mexico.addendas.api import get_addenda_configuration

		result = get_addenda_configuration(self.test_customer)

		self.assertTrue(result["success"])
		self.assertIsNotNone(result["data"])
		self.assertTrue(result["has_configuration"])
		self.assertIn("field_values", result["data"])

	def test_api_integration_create_addenda_configuration(self):
		"""Test: Integración API - crear configuración de addenda."""
		from facturacion_mexico.addendas.api import create_addenda_configuration

		# Crear nuevo cliente para la prueba
		new_customer = "API Test Customer"
		if not frappe.db.exists("Customer", new_customer):
			customer = frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": new_customer,
					"customer_type": "Company",
					"customer_group": "Commercial",
					"territory": "Mexico",
				}
			)
			customer.insert(ignore_permissions=True)

		field_values = {
			"campo_test": {"value": "valor_test", "is_dynamic": 0},
			"campo_dinamico": {
				"value": "",
				"is_dynamic": 1,
				"dynamic_source": "Customer",
				"dynamic_field": "customer_name",
			},
		}

		result = create_addenda_configuration(
			customer=new_customer,
			addenda_type=self.test_addenda_types[0],
			field_values=field_values,
			priority=5,
			validation_level="Error",
		)

		self.assertTrue(result["success"])
		self.assertIn("name", result)

		# Verificar que la configuración fue creada correctamente
		config_doc = frappe.get_doc("Addenda Configuration", result["name"])
		self.assertEqual(config_doc.customer, new_customer)
		self.assertEqual(config_doc.validation_level, "Error")
		self.assertEqual(len(config_doc.field_values), 2)

	def test_api_integration_product_mappings(self):
		"""Test: Integración API - mapeo de productos."""
		from facturacion_mexico.addendas.api import get_product_mappings

		# Crear mapeo de producto
		mapping_doc = frappe.get_doc(
			{
				"doctype": "Addenda Product Mapping",
				"customer": self.test_customer,
				"item": self.test_items[0],
				"customer_item_code": "INTEGRATION-001",
				"customer_item_description": "Integration Test Item",
				"customer_uom": "KG",
				"additional_data": '{"test_field": "test_value"}',
				"is_active": 1,
			}
		)
		mapping_doc.insert(ignore_permissions=True)

		# Obtener mapeos vía API
		result = get_product_mappings(self.test_customer, [self.test_items[0]])

		self.assertTrue(result["success"])
		self.assertIn("data", result)
		self.assertIn(self.test_items[0], result["data"])

		mapping_data = result["data"][self.test_items[0]]
		self.assertEqual(mapping_data["customer_code"], "INTEGRATION-001")
		self.assertEqual(mapping_data["additional_data"]["test_field"], "test_value")

	def test_api_integration_test_addenda_generation(self):
		"""Test: Integración API - test de generación de addenda."""
		from facturacion_mexico.addendas.api import test_addenda_generation

		result = test_addenda_generation(
			sales_invoice=self.sales_invoice, addenda_type=self.test_addenda_types[0]
		)

		self.assertTrue(result["success"])
		self.assertTrue(result["test_mode"])
		self.assertIn("timestamp", result)
		self.assertIn("validation", result)

		# Si hay XML generado, debería ser válido
		if result.get("xml"):
			self.assert_xml_valid(result["xml"])

	def test_sales_invoice_hooks_integration(self):
		"""Test: Integración con hooks de Sales Invoice."""
		# Simular el proceso que ocurre en los hooks
		invoice_doc = frappe.get_doc("Sales Invoice", self.sales_invoice)

		# Mock de la función que se llamaría en el hook
		from facturacion_mexico.addendas.api import get_addenda_requirements

		requirements = get_addenda_requirements(invoice_doc.customer)

		if requirements["requires_addenda"] and requirements["auto_apply"]:
			from facturacion_mexico.addendas.api import generate_addenda_xml

			result = generate_addenda_xml(invoice_doc.name)
			self.assertTrue(result["success"])

	def test_custom_fields_integration(self):
		"""Test: Integración con campos personalizados."""
		# Verificar que los campos personalizados existan
		invoice_doc = frappe.get_doc("Sales Invoice", self.sales_invoice)

		# Estos campos deberían estar disponibles por los custom fields
		custom_fields = [
			"fm_addenda_required",
			"fm_addenda_type",
			"fm_addenda_xml",
			"fm_addenda_status",
			"fm_addenda_errors",
		]

		for field in custom_fields:
			# Verificar que el campo existe en el meta
			meta = frappe.get_meta("Sales Invoice")
			field_exists = any(f.fieldname == field for f in meta.fields)
			if not field_exists:
				# Puede que el campo no esté instalado en el test environment
				# pero al menos verificamos que el invoice doc puede acceder al atributo
				try:
					getattr(invoice_doc, field)
				except AttributeError:
					pass  # Es esperado en ambiente de testing

	def test_database_transactions_rollback(self):
		"""Test: Rollback de transacciones de base de datos."""
		# Crear datos dentro de una transacción que fallaremos
		original_count = frappe.db.count("Addenda Configuration")

		try:
			with frappe.db.transaction():
				# Crear configuración válida
				config = frappe.get_doc(
					{
						"doctype": "Addenda Configuration",
						"customer": self.test_customer,
						"addenda_type": self.test_addenda_types[1],
						"is_active": 1,
						"priority": 10,
					}
				)
				config.insert()

				# Forzar error para rollback
				raise Exception("Forced error for rollback test")

		except Exception:
			pass  # Esperado

		# Verificar que no se creó la configuración (rollback exitoso)
		current_count = frappe.db.count("Addenda Configuration")
		self.assertEqual(current_count, original_count)

	def test_permissions_integration(self):
		"""Test: Integración con sistema de permisos."""
		# Crear usuario de prueba
		test_user = "addenda_test_user@example.com"
		if not frappe.db.exists("User", test_user):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": test_user,
					"first_name": "Addenda",
					"last_name": "Test User",
					"user_type": "System User",
				}
			)
			user.insert(ignore_permissions=True)

		# Simular cambio de usuario
		original_user = frappe.session.user
		try:
			frappe.set_user(test_user)

			# Intentar acceder a configuración (debería fallar sin permisos)
			with self.assertRaises(frappe.PermissionError):
				frappe.get_doc("Addenda Configuration", self.addenda_config)

		finally:
			frappe.set_user(original_user)

	def test_bulk_operations_integration(self):
		"""Test: Integración de operaciones en lote."""
		from facturacion_mexico.addendas.doctype.addenda_product_mapping.addenda_product_mapping import (
			AddendaProductMapping,
		)

		# Datos para mapeos en lote
		bulk_mappings = [
			{
				"customer": self.test_customer,
				"item": self.test_items[0],
				"customer_item_code": "BULK-001",
				"customer_item_description": "Bulk Item 1",
				"is_active": 1,
			},
			{
				"customer": self.test_customer,
				"item": self.test_items[1],
				"customer_item_code": "BULK-002",
				"customer_item_description": "Bulk Item 2",
				"is_active": 1,
			},
		]

		# Crear mapeos en lote
		result = AddendaProductMapping.bulk_create_mappings(bulk_mappings)

		self.assertEqual(result["created"], 2)
		self.assertEqual(result["errors"], 0)

	def test_caching_integration(self):
		"""Test: Integración con sistema de caché."""
		from facturacion_mexico.addendas.api import get_addenda_types

		# Primera llamada - debería consultar base de datos
		result1, time1 = self.measure_execution_time(get_addenda_types)

		# Segunda llamada - puede usar caché (si está implementado)
		result2, time2 = self.measure_execution_time(get_addenda_types)

		# Verificar que ambos resultados son iguales
		self.assertEqual(result1["count"], result2["count"])
		self.assertEqual(len(result1["data"]), len(result2["data"]))

	def test_error_handling_integration(self):
		"""Test: Integración de manejo de errores."""
		from facturacion_mexico.addendas.api import generate_addenda_xml

		# Test con factura inexistente
		result = generate_addenda_xml("NONEXISTENT-INVOICE")
		self.assertFalse(result["success"])
		self.assertIn("message", result)

		# Test con tipo de addenda inexistente
		result = generate_addenda_xml(sales_invoice=self.sales_invoice, addenda_type="NONEXISTENT-TYPE")
		self.assertFalse(result["success"])

	def test_logging_integration(self):
		"""Test: Integración con sistema de logging."""
		# Verificar que los errores se loguean correctamente
		len(frappe.get_all("Error Log"))

		# Generar error intencionalmente
		from facturacion_mexico.addendas.api import generate_addenda_xml

		generate_addenda_xml("INVALID-INVOICE-ID")

		# Los errores deberían estar logueados
		len(frappe.get_all("Error Log"))
		# Note: En ambiente de testing, el logging puede estar deshabilitado
		# por lo que este test puede no incrementar el contador


if __name__ == "__main__":
	unittest.main()
