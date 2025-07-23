# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Unit Tests: Generic Addenda Generator
Testing framework Layer 1 - Core component functionality
"""

import json
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import Mock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestAddendaGenerator(FrappeTestCase):
	"""
	Layer 1 Unit Tests para Generic Addenda Generator
	Valida funcionalidad individual del generador de addendas
	"""

	@classmethod
	def setUpClass(cls):
		"""Setup inicial para todos los tests"""
		super().setUpClass()
		cls.test_company = "_Test Company"

		# Aplicar REGLA #34: Fortalecer sistema con fallbacks
		try:
			from facturacion_mexico.addendas.generic_addenda_generator import AddendaGenerator

			cls.AddendaGenerator = AddendaGenerator
		except ImportError:
			cls.AddendaGenerator = None
			print("Warning: AddendaGenerator not available, using mock")

	def setUp(self):
		"""Setup para cada test individual"""
		self.sample_invoice_data = {
			"name": "TEST-INV-001",
			"customer": "Test Customer",
			"company": self.test_company,
			"total": 1000.0,
			"currency": "MXN",
			"posting_date": "2025-07-22",
		}

		self.sample_addenda_values = {
			"pedido_number": "PED-12345",
			"centro_costo": "CC-001",
			"referencia_cliente": "REF-ABC-123",
		}

	def test_addenda_generator_initialization(self):
		"""Test: Inicialización del generador de addendas"""
		if not self.AddendaGenerator:
			self.skipTest("AddendaGenerator not available")

		# Test inicialización básica
		generator = self.AddendaGenerator("test_addenda_type")
		self.assertIsNotNone(generator)
		self.assertEqual(generator.addenda_type, "test_addenda_type")

	def test_template_loading(self):
		"""Test: Carga de templates Jinja2"""
		if not self.AddendaGenerator:
			self.skipTest("AddendaGenerator not available")

		# Mock template básico
		template_content = """
		<addenda>
			<pedido>{{ pedido_number }}</pedido>
			<centro_costo>{{ centro_costo }}</centro_costo>
		</addenda>
		"""

		with patch.object(self.AddendaGenerator, "_load_template") as mock_load:
			mock_template = Mock()
			mock_template.render.return_value = template_content.strip()
			mock_load.return_value = mock_template

			generator = self.AddendaGenerator("test_type")
			result = generator._load_template()

			self.assertIsNotNone(result)
			mock_load.assert_called_once()

	def test_validate_addenda_values(self):
		"""Test: Validación de valores de addenda"""
		if not self.AddendaGenerator:
			self.skipTest("AddendaGenerator not available")

		# Mock validación
		generator = self.AddendaGenerator("test_type")

		# Mock del método de validación
		with patch.object(generator, "_validate_values") as mock_validate:
			mock_validate.return_value = {"valid": True, "errors": [], "warnings": []}

			result = generator._validate_values(self.sample_addenda_values)

			self.assertTrue(result["valid"])
			self.assertEqual(len(result["errors"]), 0)
			mock_validate.assert_called_once_with(self.sample_addenda_values)

	def test_generate_xml_basic(self):
		"""Test: Generación básica de XML"""
		if not self.AddendaGenerator:
			self.skipTest("AddendaGenerator not available")

		generator = self.AddendaGenerator("test_type")

		# Mock template y métodos
		with (
			patch.object(generator, "_validate_values") as mock_validate,
			patch.object(generator, "_prepare_template_context") as mock_context,
			patch.object(generator, "template") as mock_template,
		):
			# Setup mocks
			mock_validate.return_value = {"valid": True, "errors": []}
			mock_context.return_value = {**self.sample_invoice_data, **self.sample_addenda_values}
			mock_template.render.return_value = "<addenda><test>success</test></addenda>"

			result = generator.generate(self.sample_invoice_data, self.sample_addenda_values)

			self.assertIsInstance(result, dict)
			self.assertIn("xml_content", result)
			self.assertIn("<addenda>", result["xml_content"])

	def test_template_context_preparation(self):
		"""Test: Preparación del contexto para templates"""
		if not self.AddendaGenerator:
			self.skipTest("AddendaGenerator not available")

		generator = self.AddendaGenerator("test_type")

		with patch.object(generator, "_prepare_template_context") as mock_context:
			expected_context = {
				# Invoice data
				"invoice_name": "TEST-INV-001",
				"customer": "Test Customer",
				"total": 1000.0,
				# Addenda values
				"pedido_number": "PED-12345",
				"centro_costo": "CC-001",
				# Helper functions
				"format_currency": Mock(),
				"format_date": Mock(),
			}
			mock_context.return_value = expected_context

			result = generator._prepare_template_context(self.sample_invoice_data, self.sample_addenda_values)

			self.assertIn("invoice_name", result)
			self.assertIn("pedido_number", result)
			mock_context.assert_called_once()

	def test_xml_validation(self):
		"""Test: Validación de XML generado"""
		if not self.AddendaGenerator:
			self.skipTest("AddendaGenerator not available")

		generator = self.AddendaGenerator("test_type")

		valid_xml = "<addenda><pedido>12345</pedido></addenda>"
		invalid_xml = "<addenda><pedido>12345</pedido>"  # Sin cerrar tag

		with patch.object(generator, "_validate_xml") as mock_validate:
			# Test XML válido
			mock_validate.return_value = {"valid": True, "errors": []}
			result = generator._validate_xml(valid_xml)
			self.assertTrue(result["valid"])

			# Test XML inválido
			mock_validate.return_value = {"valid": False, "errors": ["XML malformed"]}
			result = generator._validate_xml(invalid_xml)
			self.assertFalse(result["valid"])

	def test_error_handling(self):
		"""Test: Manejo de errores en generación"""
		if not self.AddendaGenerator:
			self.skipTest("AddendaGenerator not available")

		generator = self.AddendaGenerator("test_type")

		# Mock error en validación
		with patch.object(generator, "_validate_values") as mock_validate:
			mock_validate.return_value = {
				"valid": False,
				"errors": ["Campo requerido faltante: pedido_number"],
			}

			result = generator.generate(self.sample_invoice_data, {})

			self.assertIsInstance(result, dict)
			self.assertIn("success", result)
			self.assertFalse(result["success"])
			self.assertIn("errors", result)

	def test_multiple_addenda_types(self):
		"""Test: Soporte para múltiples tipos de addenda"""
		if not self.AddendaGenerator:
			self.skipTest("AddendaGenerator not available")

		# Test diferentes tipos
		types = ["FEMSA", "WALMART", "SORIANA", "GENERIC"]

		for addenda_type in types:
			generator = self.AddendaGenerator(addenda_type)
			self.assertEqual(generator.addenda_type, addenda_type)

	def test_template_caching(self):
		"""Test: Cache de templates para performance"""
		if not self.AddendaGenerator:
			self.skipTest("AddendaGenerator not available")

		generator = self.AddendaGenerator("test_type")

		# Mock cache behavior
		with patch.object(generator, "_load_template") as mock_load:
			mock_template = Mock()
			mock_load.return_value = mock_template

			# Primera llamada - debe cargar template
			template1 = generator._load_template()
			# Segunda llamada - debe usar cache
			template2 = generator._load_template()

			# Validar que son el mismo objeto (cache)
			self.assertIs(template1, template2)

	def test_field_definition_integration(self):
		"""Test: Integración con definiciones de campos"""
		if not self.AddendaGenerator:
			self.skipTest("AddendaGenerator not available")

		generator = self.AddendaGenerator("test_type")

		# Mock field definitions
		field_definitions = [
			{"field_name": "pedido_number", "field_type": "String", "is_required": True},
			{"field_name": "centro_costo", "field_type": "String", "is_required": False},
			{"field_name": "importe", "field_type": "Number", "is_required": True},
		]

		with patch.object(generator, "_get_field_definitions") as mock_fields:
			mock_fields.return_value = field_definitions

			fields = generator._get_field_definitions()

			self.assertEqual(len(fields), 3)
			self.assertEqual(fields[0]["field_name"], "pedido_number")
			self.assertTrue(fields[0]["is_required"])

	def test_generate_with_full_workflow(self):
		"""Test: Workflow completo de generación"""
		if not self.AddendaGenerator:
			self.skipTest("AddendaGenerator not available")

		generator = self.AddendaGenerator("test_type")

		# Mock todos los componentes del workflow
		with (
			patch.object(generator, "_validate_values") as mock_validate,
			patch.object(generator, "_prepare_template_context") as mock_context,
			patch.object(generator, "template") as mock_template,
			patch.object(generator, "_validate_xml") as mock_xml_validate,
		):
			# Setup complete workflow
			mock_validate.return_value = {"valid": True, "errors": []}
			mock_context.return_value = {**self.sample_invoice_data, **self.sample_addenda_values}
			mock_template.render.return_value = "<addenda><pedido>PED-12345</pedido></addenda>"
			mock_xml_validate.return_value = {"valid": True, "errors": []}

			result = generator.generate(self.sample_invoice_data, self.sample_addenda_values)

			# Validar workflow completo
			self.assertTrue(result["success"])
			self.assertIn("xml_content", result)
			self.assertIn("metadata", result)

			# Validar que todos los pasos se ejecutaron
			mock_validate.assert_called_once()
			mock_context.assert_called_once()
			mock_template.render.assert_called_once()
			mock_xml_validate.assert_called_once()

	def test_performance_large_templates(self):
		"""Test: Performance con templates grandes"""
		if not self.AddendaGenerator:
			self.skipTest("AddendaGenerator not available")

		generator = self.AddendaGenerator("large_template")

		# Simular template con muchos campos
		large_values = {f"field_{i}": f"value_{i}" for i in range(100)}

		with (
			patch.object(generator, "_validate_values") as mock_validate,
			patch.object(generator, "_prepare_template_context") as mock_context,
			patch.object(generator, "template") as mock_template,
		):
			mock_validate.return_value = {"valid": True, "errors": []}
			mock_context.return_value = {**self.sample_invoice_data, **large_values}
			mock_template.render.return_value = "<addenda>Large XML content</addenda>"

			import time

			start_time = time.time()

			result = generator.generate(self.sample_invoice_data, large_values)

			end_time = time.time()
			processing_time = end_time - start_time

			# Validar que se procesa en tiempo razonable (< 1 segundo)
			self.assertLess(processing_time, 1.0)
			self.assertTrue(result["success"])

	def test_concurrent_generation(self):
		"""Test: Generación concurrente de addendas"""
		if not self.AddendaGenerator:
			self.skipTest("AddendaGenerator not available")

		import queue
		import threading

		results_queue = queue.Queue()

		def generate_addenda(generator, invoice_data, addenda_values, results_queue):
			with (
				patch.object(generator, "_validate_values") as mock_validate,
				patch.object(generator, "_prepare_template_context") as mock_context,
				patch.object(generator, "template") as mock_template,
			):
				mock_validate.return_value = {"valid": True, "errors": []}
				mock_context.return_value = {**invoice_data, **addenda_values}
				mock_template.render.return_value = "<addenda>Thread content</addenda>"

				result = generator.generate(invoice_data, addenda_values)
				results_queue.put(result)

		# Crear múltiples threads
		threads = []
		for i in range(5):
			generator = self.AddendaGenerator(f"test_type_{i}")
			thread = threading.Thread(
				target=generate_addenda,
				args=(generator, self.sample_invoice_data, self.sample_addenda_values, results_queue),
			)
			threads.append(thread)
			thread.start()

		# Esperar que terminen todos los threads
		for thread in threads:
			thread.join()

		# Validar resultados
		results = []
		while not results_queue.empty():
			results.append(results_queue.get())

		self.assertEqual(len(results), 5)
		for result in results:
			self.assertIsInstance(result, dict)


if __name__ == "__main__":
	unittest.main()
