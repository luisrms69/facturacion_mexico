# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 1 Addenda DocTypes Tests
Tests básicos para verificar DocTypes del sistema de Addendas Sprint 6
"""

import unittest

import frappe


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

		# Campos básicos esperados (basados en implementación real)
		expected_fields = [
			"name", "description", "version", "xml_template",
			"is_active", "field_definitions", "namespace"
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

		expected_fields = ["name1", "template_name", "template_xml", "addenda_type"]
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

		expected_fields = ["field_name", "field_label", "field_type", "is_mandatory"]
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
		expected_fields = ["field_definition", "field_value"]

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

		expected_fields = ["item", "item_code", "customer_item_code"]
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
			try:
				doctype_meta = frappe.get_meta(doctype)

				# Skip child tables (istable=1) as they don't have their own permissions
				if doctype_meta.istable:
					continue

				permissions = doctype_meta.permissions

				# Debe tener al menos un permiso configurado
				self.assertGreater(len(permissions), 0,
					f"DocType '{doctype}' debe tener permisos configurados")
			except Exception as e:
				self.fail(f"Error verificando permisos de '{doctype}': {e}")

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

			# Solo verificar que el DocType metadata es accesible
			try:
				doctype_meta = frappe.get_meta(doctype)
				self.assertIsNotNone(doctype_meta, f"Metadata de '{doctype}' debe ser accesible")
			except Exception as e:
				self.fail(f"Error accediendo metadata de '{doctype}': {e}")


if __name__ == "__main__":
	unittest.main()
