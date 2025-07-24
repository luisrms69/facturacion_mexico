# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 1 Addenda DocTypes Tests
Tests básicos para verificar DocTypes del sistema de Addendas Sprint 6
"""

import frappe
import unittest


class TestLayer1AddendaDocTypes(unittest.TestCase):
	"""Tests de DocTypes de Addendas básicos - Layer 1"""

	@classmethod
	def setUpClass(cls):
		"""Setup inicial para todos los tests"""
		frappe.clear_cache()

	def test_addenda_type_doctype(self):
		"""Test: DocType Addenda Type existe y funciona"""
		# Verificar que el DocType existe
		self.assertTrue(frappe.db.exists("DocType", "Addenda Type"))

		# Verificar campos obligatorios del DocType
		doctype_meta = frappe.get_meta("Addenda Type")
		field_names = [field.fieldname for field in doctype_meta.fields]

		# Campos básicos esperados
		expected_fields = [
			"addenda_name", "customer", "xml_template",
			"is_active", "validation_schema"
		]

		for field in expected_fields:
			self.assertIn(field, field_names,
				f"Campo '{field}' debe existir en Addenda Type")

	def test_addenda_configuration_doctype(self):
		"""Test: DocType Addenda Configuration existe y funciona"""
		# Verificar que el DocType existe
		self.assertTrue(frappe.db.exists("DocType", "Addenda Configuration"))

		# Verificar estructura básica
		doctype_meta = frappe.get_meta("Addenda Configuration")
		self.assertIsNotNone(doctype_meta)

		# Verificar que puede crear instancia
		try:
			config = frappe.new_doc("Addenda Configuration")
			self.assertIsNotNone(config)
		except Exception as e:
			self.fail(f"No se puede crear Addenda Configuration: {e}")

	def test_addenda_template_doctype(self):
		"""Test: DocType Addenda Template existe y funciona"""
		# Verificar que el DocType existe
		self.assertTrue(frappe.db.exists("DocType", "Addenda Template"))

		# Verificar campos de template
		doctype_meta = frappe.get_meta("Addenda Template")
		field_names = [field.fieldname for field in doctype_meta.fields]

		expected_fields = ["template_name", "template_content", "template_type"]
		for field in expected_fields:
			self.assertIn(field, field_names,
				f"Campo '{field}' debe existir en Addenda Template")

	def test_addenda_field_definition_doctype(self):
		"""Test: DocType Addenda Field Definition existe y funciona"""
		# Verificar que el DocType existe
		self.assertTrue(frappe.db.exists("DocType", "Addenda Field Definition"))

		# Verificar campos de definición
		doctype_meta = frappe.get_meta("Addenda Field Definition")
		field_names = [field.fieldname for field in doctype_meta.fields]

		expected_fields = ["field_name", "field_type", "is_mandatory"]
		for field in expected_fields:
			self.assertIn(field, field_names,
				f"Campo '{field}' debe existir en Addenda Field Definition")

	def test_addenda_field_value_doctype(self):
		"""Test: DocType Addenda Field Value existe y funciona"""
		# Verificar que el DocType existe
		self.assertTrue(frappe.db.exists("DocType", "Addenda Field Value"))

		# Verificar estructura básica
		doctype_meta = frappe.get_meta("Addenda Field Value")
		self.assertIsNotNone(doctype_meta)

		# Verificar que tiene campos de valor
		field_names = [field.fieldname for field in doctype_meta.fields]
		expected_fields = ["field_name", "field_value"]

		for field in expected_fields:
			self.assertIn(field, field_names,
				f"Campo '{field}' debe existir en Addenda Field Value")

	def test_addenda_product_mapping_doctype(self):
		"""Test: DocType Addenda Product Mapping existe y funciona"""
		# Verificar que el DocType existe
		self.assertTrue(frappe.db.exists("DocType", "Addenda Product Mapping"))

		# Verificar campos de mapeo
		doctype_meta = frappe.get_meta("Addenda Product Mapping")
		field_names = [field.fieldname for field in doctype_meta.fields]

		expected_fields = ["item_code", "addenda_product_code"]
		for field in expected_fields:
			self.assertIn(field, field_names,
				f"Campo '{field}' debe existir en Addenda Product Mapping")

	def test_doctypes_permissions_basic(self):
		"""Test: DocTypes de Addenda tienen permisos básicos configurados"""
		addenda_doctypes = [
			"Addenda Type", "Addenda Configuration", "Addenda Template",
			"Addenda Field Definition", "Addenda Field Value",
			"Addenda Product Mapping"
		]

		for doctype in addenda_doctypes:
			# Verificar que el DocType tiene permisos configurados
			permissions = frappe.get_all("Custom DocPerm",
				filters={"parent": doctype}, fields=["role", "read", "write"])

			# Debe tener al menos un permiso configurado
			self.assertGreater(len(permissions), 0,
				f"DocType '{doctype}' debe tener permisos configurados")

	def test_doctypes_naming_series(self):
		"""Test: DocTypes que requieren naming series lo tienen configurado"""
		# DocTypes que deben tener naming series
		naming_doctypes = ["Addenda Type", "Addenda Configuration"]

		for doctype in naming_doctypes:
			doctype_meta = frappe.get_meta(doctype)

			# Verificar que tiene autoname o naming_series
			has_naming = (
				doctype_meta.autoname or
				any(field.fieldname == "naming_series" for field in doctype_meta.fields)
			)

			self.assertTrue(has_naming,
				f"DocType '{doctype}' debe tener naming configurado")

	def test_doctypes_database_integrity(self):
		"""Test: DocTypes están correctamente registrados en base de datos"""
		addenda_doctypes = [
			"Addenda Type", "Addenda Configuration", "Addenda Template",
			"Addenda Field Definition", "Addenda Field Value",
			"Addenda Product Mapping"
		]

		for doctype in addenda_doctypes:
			# Verificar que existe en tabDocType
			exists_in_db = frappe.db.get_value("DocType", doctype, "name")
			self.assertEqual(exists_in_db, doctype,
				f"DocType '{doctype}' debe estar registrado en base de datos")

			# Verificar que la tabla correspondiente existe
			table_name = f"tab{doctype.replace(' ', '')}"
			try:
				frappe.db.sql(f"SELECT 1 FROM `{table_name}` LIMIT 1")
			except Exception as e:
				self.fail(f"Tabla '{table_name}' para DocType '{doctype}' no existe: {e}")


if __name__ == "__main__":
	unittest.main()