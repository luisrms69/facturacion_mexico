"""
Unit Tests - Layer 1: Parsers
Tests unitarios para parsers del sistema de addendas
"""

import unittest

import frappe

from facturacion_mexico.addendas.parsers.xml_builder import AddendaXMLBuilder
from facturacion_mexico.addendas.tests.test_base import AddendaTestBase


class TestAddendaXMLBuilder(AddendaTestBase):
	"""Tests unitarios para AddendaXMLBuilder."""

	def setUp(self):
		"""Configuración para cada test."""
		super().setUp()
		self.sample_template = """<?xml version="1.0" encoding="UTF-8"?>
<addenda>
	<informacion>
		<folio>{{ cfdi_uuid }}</folio>
		<fecha>{{ cfdi_fecha }}</fecha>
		<total>{{ cfdi_total }}</total>
		<proveedor>{{ emisor_nombre }}</proveedor>
	</informacion>
	<cliente>
		<rfc>{{ receptor_rfc }}</rfc>
		<nombre>{{ receptor_nombre }}</nombre>
	</cliente>
</addenda>"""

		self.sample_variables = {
			"cfdi_uuid": "12345678-1234-1234-1234-123456789012",
			"cfdi_fecha": "2025-07-20",
			"cfdi_total": "1000.00",
			"emisor_nombre": "Test Company S.A. de C.V.",
			"receptor_rfc": "XAXX010101000",
			"receptor_nombre": "Test Cliente S.A.",
		}

		self.sample_cfdi_data = {
			"uuid": "12345678-1234-1234-1234-123456789012",
			"fecha": "2025-07-20T10:30:00",
			"total": "1000.00",
			"emisor_rfc": "TEST123456789",
			"emisor_nombre": "Test Company S.A. de C.V.",
			"receptor_rfc": "XAXX010101000",
			"receptor_nombre": "Test Cliente S.A.",
		}

	def test_builder_initialization(self):
		"""Test: Inicialización del builder."""
		builder = AddendaXMLBuilder(self.sample_template, self.sample_variables, add_system_vars=False)
		self.assertEqual(builder.template_xml, self.sample_template)
		self.assertEqual(builder.variables, self.sample_variables)

	def test_builder_initialization_with_cfdi_data(self):
		"""Test: Inicialización con datos CFDI."""
		builder = AddendaXMLBuilder(self.sample_template, self.sample_variables, self.sample_cfdi_data)
		self.assertEqual(builder.cfdi_data, self.sample_cfdi_data)

	def test_replace_variables_basic(self):
		"""Test: Reemplazo básico de variables."""
		builder = AddendaXMLBuilder(self.sample_template, self.sample_variables)
		builder.replace_variables()

		result_xml = builder.build()

		# Verificar que las variables fueron reemplazadas
		for var, value in self.sample_variables.items():
			self.assertNotIn(f"{{{{ {var} }}}}", result_xml)
			self.assertIn(str(value), result_xml)

	def test_replace_variables_with_cfdi_data(self):
		"""Test: Reemplazo de variables con datos CFDI."""
		# Template que usa datos CFDI
		cfdi_template = """<addenda>
	<uuid>{{ cfdi_uuid }}</uuid>
	<emisor>{{ emisor_rfc }}</emisor>
</addenda>"""

		# Variables vacías, debería usar datos CFDI
		empty_vars = {}

		builder = AddendaXMLBuilder(cfdi_template, empty_vars, self.sample_cfdi_data)
		builder.replace_variables()

		result_xml = builder.build()

		# Verificar que usó datos CFDI
		self.assertIn(self.sample_cfdi_data["uuid"], result_xml)
		self.assertIn(self.sample_cfdi_data["emisor_rfc"], result_xml)

	def test_add_namespace(self):
		"""Test: Agregar namespace al XML."""
		namespace = "http://test.addenda.mx"
		builder = AddendaXMLBuilder(self.sample_template, self.sample_variables)
		builder.add_namespace(namespace)

		result_xml = builder.replace_variables().build()

		# Verificar que el namespace fue agregado
		self.assertIn(f'xmlns="{namespace}"', result_xml)

	def test_build_valid_xml(self):
		"""Test: Construcción de XML válido."""
		builder = AddendaXMLBuilder(self.sample_template, self.sample_variables)
		result_xml = builder.replace_variables().build()

		# Verificar que el XML resultante es válido
		self.assert_xml_valid(result_xml)

	def test_build_with_missing_variables(self):
		"""Test: Construcción con variables faltantes."""
		incomplete_vars = {
			"cfdi_uuid": "12345678-1234-1234-1234-123456789012",
			# Faltan otras variables
		}

		builder = AddendaXMLBuilder(self.sample_template, incomplete_vars)
		result_xml = builder.replace_variables().build()

		# Debería seguir siendo XML válido
		self.assert_xml_valid(result_xml)

		# Las variables no reemplazadas deberían estar vacías o mantener el placeholder
		self.assertIn(self.sample_variables["cfdi_uuid"], result_xml)

	def test_create_sample_template_static_method(self):
		"""Test: Método estático para crear template de muestra."""
		addenda_type = "Test Type"
		template_xml = AddendaXMLBuilder.create_sample_template(addenda_type)

		# Verificar que es XML válido
		self.assert_xml_valid(template_xml)

		# Verificar que contiene variables comunes
		common_variables = ["cfdi_uuid", "cfdi_fecha", "cfdi_total", "emisor_rfc"]
		for var in common_variables:
			self.assertIn(f"{{{{ {var} }}}}", template_xml)

	def test_escape_xml_special_characters(self):
		"""Test: Escape de caracteres especiales XML."""
		special_chars_vars = {
			"company_name": "Test & Company <S.A.> de C.V.",
			"description": "Producto con \"comillas\" y 'apostrofes'",
			"amount": "1,000.00",
		}

		template_with_special = """<addenda>
	<company>{{ company_name }}</company>
	<description>{{ description }}</description>
	<amount>{{ amount }}</amount>
</addenda>"""

		builder = AddendaXMLBuilder(template_with_special, special_chars_vars)
		result_xml = builder.replace_variables().build()

		# XML debería seguir siendo válido después del escape
		self.assert_xml_valid(result_xml)

		# Verificar que caracteres especiales fueron escapados
		self.assertIn("&amp;", result_xml)  # & escapado
		self.assertIn("&lt;", result_xml)  # < escapado
		self.assertIn("&gt;", result_xml)  # > escapado

	def test_performance_large_template(self):
		"""Test: Rendimiento con template grande."""
		# Crear template grande
		large_template_parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<addenda>"]

		# Agregar muchos elementos
		for i in range(200):
			large_template_parts.append(f"<item{i:03d}>{{{{ item_{i:03d} }}</item{i:03d}>")

		large_template_parts.append("</addenda>")
		large_template = "\n".join(large_template_parts)

		# Crear variables correspondientes
		large_variables = {f"item_{i:03d}": f"Value {i}" for i in range(200)}

		builder = AddendaXMLBuilder(large_template, large_variables)
		result, execution_time = self.measure_execution_time(lambda: builder.replace_variables().build())

		# Debería completarse rápidamente
		self.assertLess(execution_time, 2.0, f"Building took {execution_time:.2f} seconds, expected < 2.0")

		# Verificar que el resultado es válido
		self.assert_xml_valid(result)

	def test_method_chaining(self):
		"""Test: Encadenamiento de métodos."""
		namespace = "http://test.addenda.mx"

		# Probar encadenamiento de métodos
		result_xml = (
			AddendaXMLBuilder(self.sample_template, self.sample_variables)
			.add_namespace(namespace)
			.replace_variables()
			.build()
		)

		# Verificar resultado
		self.assert_xml_valid(result_xml)
		self.assertIn(f'xmlns="{namespace}"', result_xml)

		# Verificar que variables fueron reemplazadas
		for value in self.sample_variables.values():
			self.assertIn(str(value), result_xml)

	def test_variable_priority_cfdi_over_variables(self):
		"""Test: Prioridad de variables CFDI sobre variables normales."""
		# Variables normales con valores diferentes a CFDI
		conflicting_vars = {
			"cfdi_uuid": "WRONG-UUID",
			"emisor_rfc": "WRONG-RFC",
		}

		template = """<addenda>
	<uuid>{{ cfdi_uuid }}</uuid>
	<rfc>{{ emisor_rfc }}</rfc>
</addenda>"""

		builder = AddendaXMLBuilder(template, conflicting_vars, self.sample_cfdi_data)
		result_xml = builder.replace_variables().build()

		# Debería usar valores de CFDI, no de variables normales
		self.assertIn(self.sample_cfdi_data["uuid"], result_xml)
		self.assertIn(self.sample_cfdi_data["emisor_rfc"], result_xml)
		self.assertNotIn("WRONG-UUID", result_xml)
		self.assertNotIn("WRONG-RFC", result_xml)

	def test_empty_template_handling(self):
		"""Test: Manejo de template vacío."""
		empty_template = ""
		builder = AddendaXMLBuilder(empty_template, self.sample_variables)

		result_xml = builder.replace_variables().build()
		self.assertEqual(result_xml, "")

	def test_template_without_variables(self):
		"""Test: Template sin variables."""
		static_template = """<?xml version="1.0" encoding="UTF-8"?>
<addenda>
	<staticElement>Static Value</staticElement>
	<anotherElement>Another Static Value</anotherElement>
</addenda>"""

		builder = AddendaXMLBuilder(static_template, {})
		result_xml = builder.replace_variables().build()

		# Debería retornar el template original
		self.assert_xml_valid(result_xml)
		self.assertIn("Static Value", result_xml)
		self.assertIn("Another Static Value", result_xml)


if __name__ == "__main__":
	unittest.main()
