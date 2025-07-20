"""
Business Logic Tests - Layer 2
Tests de lógica de negocio para el sistema de addendas
"""

import unittest
from unittest.mock import patch

import frappe

from facturacion_mexico.addendas.tests.test_base import AddendaTestBase


class TestAddendaBusinessLogic(AddendaTestBase):
	"""Tests de lógica de negocio para addendas."""

	def setUp(self):
		"""Configuración para cada test."""
		super().setUp()
		self.sales_invoice = self.create_test_sales_invoice()
		self.addenda_config = self.create_test_addenda_configuration()
		self.addenda_template = self.create_test_addenda_template()

	def test_addenda_type_validation_rules(self):
		"""Test: Reglas de validación de tipos de addenda."""
		# Test crear tipo con versión duplicada
		with self.assertRaises(frappe.ValidationError):
			duplicate_type = frappe.get_doc(
				{
					"doctype": "Addenda Type",
					"name": "Duplicate Test",
					"description": "Tipo duplicado",
					"version": "1.0",  # Misma versión que Generic Test
				}
			)
			duplicate_type.insert()

		# Test tipo con XSD inválido
		with self.assertRaises(frappe.ValidationError):
			invalid_xsd_type = frappe.get_doc(
				{
					"doctype": "Addenda Type",
					"name": "Invalid XSD Test",
					"description": "Tipo con XSD inválido",
					"version": "1.1",
					"xsd_schema": "<invalid>xml schema",
				}
			)
			invalid_xsd_type.insert()

	def test_addenda_configuration_business_rules(self):
		"""Test: Reglas de negocio para configuraciones."""
		# Test configuración duplicada activa
		with self.assertRaises(frappe.ValidationError):
			duplicate_config = frappe.get_doc(
				{
					"doctype": "Addenda Configuration",
					"customer": self.test_customer,
					"addenda_type": self.test_addenda_types[0],
					"is_active": 1,
					"priority": 1,
				}
			)
			duplicate_config.insert()

		# Test rango de fechas inválido
		with self.assertRaises(frappe.ValidationError):
			invalid_date_config = frappe.get_doc(
				{
					"doctype": "Addenda Configuration",
					"customer": self.test_customer,
					"addenda_type": self.test_addenda_types[1],
					"is_active": 1,
					"effective_date": "2025-12-31",
					"expiry_date": "2025-01-01",  # Fecha fin antes que inicio
				}
			)
			invalid_date_config.insert()

	def test_customer_addenda_requirements(self):
		"""Test: Determinación de requerimientos de addenda por cliente."""
		from facturacion_mexico.addendas.api import get_addenda_requirements

		# Cliente con configuración activa
		requirements = get_addenda_requirements(self.test_customer)

		self.assertTrue(requirements["requires_addenda"])
		self.assertIsNotNone(requirements["configuration"])
		self.assertTrue(requirements["auto_apply"])

		# Cliente sin configuración
		test_customer_no_addenda = "Customer Without Addenda"
		if not frappe.db.exists("Customer", test_customer_no_addenda):
			customer = frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": test_customer_no_addenda,
					"customer_type": "Company",
					"customer_group": "Commercial",
					"territory": "Mexico",
				}
			)
			customer.insert(ignore_permissions=True)

		requirements_none = get_addenda_requirements(test_customer_no_addenda)

		self.assertFalse(requirements_none["requires_addenda"])
		self.assertIsNone(requirements_none["configuration"])
		self.assertFalse(requirements_none["auto_apply"])

	def test_addenda_generation_workflow(self):
		"""Test: Flujo completo de generación de addenda."""
		from facturacion_mexico.addendas.api import generate_addenda_xml

		# Generar addenda para factura
		result = generate_addenda_xml(self.sales_invoice, validate_output=True)

		self.assertTrue(result["success"])
		self.assertIsNotNone(result["xml"])
		self.assertEqual(result["addenda_type"], self.test_addenda_types[0])
		self.assertIn("validation", result)

		# Verificar que el XML generado es válido
		self.assert_xml_valid(result["xml"])

		# Verificar que contiene elementos esperados
		self.assert_xml_contains(result["xml"], "//addenda")
		self.assert_xml_contains(result["xml"], "//informacion")

	def test_addenda_template_validation_business_logic(self):
		"""Test: Lógica de negocio para validación de templates."""
		template_doc = frappe.get_doc("Addenda Template", self.addenda_template)

		# Test validación contra XSD
		validation_result = template_doc.validate_against_xsd()

		self.assertIn("valid", validation_result)
		self.assertIn("message", validation_result)
		self.assertIn("errors", validation_result)

		# Test preview con datos de muestra
		preview = template_doc.preview_template()
		self.assert_xml_valid(preview)

		# Test obtener variables del template
		variables = template_doc.get_template_variables()
		self.assertIsInstance(variables, list)
		self.assertIn("cfdi_uuid", variables)

	def test_product_mapping_business_logic(self):
		"""Test: Lógica de negocio para mapeo de productos."""
		# Crear mapeo de producto
		mapping_doc = frappe.get_doc(
			{
				"doctype": "Addenda Product Mapping",
				"customer": self.test_customer,
				"item": self.test_items[0],
				"customer_item_code": "CUST-001",
				"customer_item_description": "Custom Description",
				"customer_uom": "PCS",
				"additional_data": '{"categoria": "electronics", "peso": 1.5}',
				"is_active": 1,
			}
		)
		mapping_doc.insert(ignore_permissions=True)

		# Test obtener datos del mapeo
		mapping_data = mapping_doc.get_mapping_data()

		self.assertEqual(mapping_data["customer_code"], "CUST-001")
		self.assertEqual(mapping_data["additional_data"]["categoria"], "electronics")
		self.assertEqual(mapping_data["additional_data"]["peso"], 1.5)

		# Test buscar mapeo
		from facturacion_mexico.addendas.doctype.addenda_product_mapping.addenda_product_mapping import (
			AddendaProductMapping,
		)

		found_mapping = AddendaProductMapping.find_mapping(self.test_customer, self.test_items[0])
		self.assertIsNotNone(found_mapping)
		self.assertEqual(found_mapping["customer_item_code"], "CUST-001")

	def test_field_value_resolution_logic(self):
		"""Test: Lógica de resolución de valores de campos."""
		# Crear configuración con valores dinámicos
		config_doc = frappe.get_doc("Addenda Configuration", self.addenda_config)

		# Agregar valor de campo dinámico
		field_value = config_doc.append("field_values")
		field_value.field_definition = "test_field"
		field_value.is_dynamic = 1
		field_value.dynamic_source = "Sales Invoice"
		field_value.dynamic_field = "name"
		config_doc.save()

		# Test resolución de valores
		invoice_doc = frappe.get_doc("Sales Invoice", self.sales_invoice)
		context_data = {"sales_invoice": invoice_doc}

		resolved_values = config_doc.get_resolved_field_values(context_data)

		self.assertIn("test_field", resolved_values)
		self.assertEqual(resolved_values["test_field"], self.sales_invoice)

	def test_addenda_validation_levels(self):
		"""Test: Niveles de validación de addendas."""
		from facturacion_mexico.addendas.api import validate_addenda_xml_api

		# XML válido
		valid_xml = """<?xml version="1.0" encoding="UTF-8"?>
<addenda>
	<informacion>
		<folio>12345</folio>
		<fecha>2025-07-20</fecha>
		<total>1000.00</total>
	</informacion>
</addenda>"""

		# Test validación
		result = validate_addenda_xml_api(valid_xml, self.test_addenda_types[0])

		self.assertTrue(result["success"])
		self.assertIn("validation", result)

	def test_date_range_active_configuration(self):
		"""Test: Configuración activa por rango de fechas."""
		config_doc = frappe.get_doc("Addenda Configuration", self.addenda_config)

		# Test configuración activa para hoy
		self.assertTrue(config_doc.is_active_for_date())

		# Test configuración no activa para fecha futura
		future_date = frappe.utils.add_days(frappe.utils.today(), 365)
		config_doc.expiry_date = frappe.utils.add_days(frappe.utils.today(), 30)
		config_doc.save()

		self.assertFalse(config_doc.is_active_for_date(future_date))

	def test_priority_based_configuration_selection(self):
		"""Test: Selección de configuración basada en prioridad."""
		# Crear segunda configuración con mayor prioridad (menor número)
		high_priority_config = frappe.get_doc(
			{
				"doctype": "Addenda Configuration",
				"customer": self.test_customer,
				"addenda_type": self.test_addenda_types[1],  # Diferente tipo
				"is_active": 1,
				"priority": 0,  # Mayor prioridad
				"auto_apply": 1,
				"validation_level": "Error",
				"effective_date": frappe.utils.today(),
			}
		)
		high_priority_config.insert(ignore_permissions=True)

		from facturacion_mexico.addendas.doctype.addenda_configuration.addenda_configuration import (
			AddendaConfiguration,
		)

		# Debería retornar la configuración de mayor prioridad
		active_config = AddendaConfiguration.get_active_configuration(self.test_customer)

		self.assertIsNotNone(active_config)
		self.assertEqual(active_config["priority"], 0)

	def test_error_notification_business_logic(self):
		"""Test: Lógica de notificaciones de error."""
		config_doc = frappe.get_doc("Addenda Configuration", self.addenda_config)
		config_doc.notify_on_error = 1
		config_doc.error_recipients = "test@example.com"
		config_doc.save()

		# Mock para evitar envío real de email
		with patch("frappe.sendmail") as mock_sendmail:
			config_doc.send_error_notification("Test error message", self.sales_invoice)

			# Verificar que se intentó enviar email
			mock_sendmail.assert_called_once()
			call_args = mock_sendmail.call_args

			self.assertIn("test@example.com", call_args[1]["recipients"])
			self.assertIn("Error en Addenda", call_args[1]["subject"])

	def test_configuration_testing_functionality(self):
		"""Test: Funcionalidad de testing de configuraciones."""
		config_doc = frappe.get_doc("Addenda Configuration", self.addenda_config)

		# Test configuración con factura real
		test_result = config_doc.test_configuration(self.sales_invoice)

		self.assertTrue(test_result["success"])
		self.assertIn("resolved_values", test_result)
		self.assertIn("validation_results", test_result)
		self.assertIn("valid_fields", test_result)
		self.assertIn("total_fields", test_result)

		# Test configuración sin factura (datos de prueba)
		test_result_mock = config_doc.test_configuration()

		self.assertTrue(test_result_mock["success"])


if __name__ == "__main__":
	unittest.main()
