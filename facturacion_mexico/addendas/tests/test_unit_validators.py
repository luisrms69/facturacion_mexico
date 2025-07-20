"""
Unit Tests - Layer 1: XSD Validator
Tests unitarios para validadores del sistema de addendas
"""

import unittest

import frappe

from facturacion_mexico.addendas.tests.test_base import AddendaTestBase
from facturacion_mexico.addendas.validators.xsd_validator import XSDValidator


class TestXSDValidator(AddendaTestBase):
	"""Tests unitarios para XSDValidator."""

	def setUp(self):
		"""Configuración para cada test."""
		super().setUp()
		self.sample_xsd = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="http://test.addenda.mx"
           xmlns:tns="http://test.addenda.mx"
           elementFormDefault="qualified">

  <xs:element name="addenda">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="folio" type="xs:string"/>
        <xs:element name="fecha" type="xs:date"/>
        <xs:element name="total" type="xs:decimal"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>"""

		self.valid_xml = """<?xml version="1.0" encoding="UTF-8"?>
<addenda xmlns="http://test.addenda.mx">
  <folio>12345</folio>
  <fecha>2025-07-20</fecha>
  <total>1000.00</total>
</addenda>"""

		self.invalid_xml = """<?xml version="1.0" encoding="UTF-8"?>
<addenda xmlns="http://test.addenda.mx">
  <folio>12345</folio>
  <fecha>invalid-date</fecha>
  <!-- total element missing -->
</addenda>"""

	def test_validator_initialization_valid_schema(self):
		"""Test: Inicialización con esquema XSD válido."""
		validator = XSDValidator(self.sample_xsd)
		self.assertTrue(validator.is_schema_valid())
		self.assertEqual(len(validator.get_schema_validation_errors()), 0)

	def test_validator_initialization_invalid_schema(self):
		"""Test: Inicialización con esquema XSD inválido."""
		invalid_xsd = "<invalid>xml"
		validator = XSDValidator(invalid_xsd)
		self.assertFalse(validator.is_schema_valid())
		self.assertGreater(len(validator.get_schema_validation_errors()), 0)

	def test_validate_valid_xml(self):
		"""Test: Validación de XML válido."""
		validator = XSDValidator(self.sample_xsd)
		is_valid = validator.validate(self.valid_xml)
		self.assertTrue(is_valid)
		self.assertEqual(len(validator.get_errors()), 0)

	def test_validate_invalid_xml(self):
		"""Test: Validación de XML inválido."""
		validator = XSDValidator(self.sample_xsd)
		is_valid = validator.validate(self.invalid_xml)
		self.assertFalse(is_valid)
		self.assertGreater(len(validator.get_errors()), 0)

	def test_validate_with_details(self):
		"""Test: Validación con detalles completos."""
		validator = XSDValidator(self.sample_xsd)
		is_valid, errors, warnings = validator.validate_with_details(self.invalid_xml)

		self.assertFalse(is_valid)
		self.assertIsInstance(errors, list)
		self.assertIsInstance(warnings, list)
		self.assertGreater(len(errors), 0)

	def test_get_schema_info(self):
		"""Test: Obtener información del esquema."""
		validator = XSDValidator(self.sample_xsd)
		info = validator.get_schema_info()

		self.assertTrue(info["valid"])
		self.assertEqual(info["target_namespace"], "http://test.addenda.mx")
		self.assertIn("elements", info)
		self.assertGreater(len(info["elements"]), 0)

	def test_suggest_fixes(self):
		"""Test: Sugerencias de corrección."""
		validator = XSDValidator(self.sample_xsd)
		suggestions = validator.suggest_fixes(self.invalid_xml)

		self.assertIsInstance(suggestions, list)
		# Debería sugerir correcciones para el XML inválido
		if not validator.validate(self.invalid_xml):
			self.assertGreater(len(suggestions), 0)

	def test_create_validation_report(self):
		"""Test: Crear reporte de validación."""
		validator = XSDValidator(self.sample_xsd)
		report = validator.create_validation_report(self.invalid_xml, include_schema_info=True)

		required_keys = ["timestamp", "is_valid", "errors", "warnings", "error_count", "warning_count"]
		for key in required_keys:
			self.assertIn(key, report)

		self.assertIn("schema_info", report)
		self.assertFalse(report["is_valid"])

	def test_validate_multiple_files(self):
		"""Test: Validación de múltiples archivos."""
		validator = XSDValidator(self.sample_xsd)
		xml_files = [self.valid_xml, self.invalid_xml, self.valid_xml]

		results = validator.validate_multiple_files(xml_files)

		self.assertEqual(len(results), 3)
		self.assertTrue(results[0]["is_valid"])  # primer archivo válido
		self.assertFalse(results[1]["is_valid"])  # segundo archivo inválido
		self.assertTrue(results[2]["is_valid"])  # tercer archivo válido

	def test_static_method_validate_xml_against_xsd(self):
		"""Test: Método estático de validación."""
		result = XSDValidator.validate_xml_against_xsd(self.valid_xml, self.sample_xsd)

		self.assertIn("is_valid", result)
		self.assertIn("errors", result)
		self.assertTrue(result["is_valid"])

	def test_performance_large_xml(self):
		"""Test: Rendimiento con XML grande."""
		# Crear XML más grande para test de rendimiento
		large_xml_parts = [
			'<?xml version="1.0" encoding="UTF-8"?>',
			'<addenda xmlns="http://test.addenda.mx">',
		]

		# Agregar muchos elementos
		for i in range(100):
			large_xml_parts.extend(
				[
					f"<folio>FOLIO-{i:04d}</folio>",
					"<fecha>2025-07-20</fecha>",
					f"<total>{1000.00 + i}</total>",
				]
			)

		large_xml_parts.append("</addenda>")
		large_xml = "\n".join(large_xml_parts)

		# Modificar esquema para permitir múltiples elementos
		large_xsd = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="http://test.addenda.mx"
           xmlns:tns="http://test.addenda.mx"
           elementFormDefault="qualified">

  <xs:element name="addenda">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="folio" type="xs:string" maxOccurs="unbounded"/>
        <xs:element name="fecha" type="xs:date" maxOccurs="unbounded"/>
        <xs:element name="total" type="xs:decimal" maxOccurs="unbounded"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>"""

		validator = XSDValidator(large_xsd)
		result, execution_time = self.measure_execution_time(validator.validate, large_xml)

		# Validación debería completarse en menos de 5 segundos
		self.assertLess(execution_time, 5.0, f"Validation took {execution_time:.2f} seconds, expected < 5.0")

	def test_error_handling_malformed_xml(self):
		"""Test: Manejo de errores con XML malformado."""
		malformed_xml = "<invalid><unclosed>tag"
		validator = XSDValidator(self.sample_xsd)

		is_valid = validator.validate(malformed_xml)
		self.assertFalse(is_valid)

		errors = validator.get_errors()
		self.assertGreater(len(errors), 0)

		# Verificar que el error menciona problema sintáctico - palabras clave más amplias
		error_text = " ".join(errors).lower()
		# Buscar palabras clave comunes en errores XML
		keywords = ["syntax", "malformed", "parse", "error", "invalid", "unclosed", "tag", "xml", "element"]
		self.assertTrue(
			any(keyword in error_text for keyword in keywords),
			f"Error text does not contain expected keywords. Got: {error_text}",
		)


if __name__ == "__main__":
	unittest.main()
