# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 1 Addenda DocTypes Tests
Tests básicos para verificar DocTypes del sistema de Addendas.
"""

import unittest

import frappe


class TestLayer1AddendaDocTypes(unittest.TestCase):
	"""Tests de DocTypes de Addendas básicos - Layer 1"""

	@classmethod
	def setUpClass(cls):
		frappe.clear_cache()

	def test_addenda_type_doctype(self):
		"""Test: DocType Addenda Type existe con campos requeridos"""
		self.assertTrue(frappe.db.exists("DocType", "Addenda Type"))
		meta = frappe.get_meta("Addenda Type")
		field_names = [f.fieldname for f in meta.fields]
		for field in [
			"description",
			"version",
			"xml_template",
			"is_active",
			"field_definitions",
			"namespace",
		]:
			self.assertIn(field, field_names, f"Campo '{field}' debe existir en Addenda Type")

	def test_addenda_template_doctype(self):
		"""Test: DocType Addenda Template existe"""
		self.assertTrue(frappe.db.exists("DocType", "Addenda Template"))

	def test_addenda_field_definition_doctype(self):
		"""Test: DocType Addenda Field Definition existe con campos requeridos"""
		self.assertTrue(frappe.db.exists("DocType", "Addenda Field Definition"))
		meta = frappe.get_meta("Addenda Field Definition")
		field_names = [f.fieldname for f in meta.fields]
		for field in ["field_name", "field_label", "field_type", "is_mandatory"]:
			self.assertIn(field, field_names, f"Campo '{field}' debe existir en Addenda Field Definition")

	def test_addenda_field_value_doctype(self):
		"""Test: DocType Addenda Field Value existe con campos requeridos"""
		self.assertTrue(frappe.db.exists("DocType", "Addenda Field Value"))
		meta = frappe.get_meta("Addenda Field Value")
		field_names = [f.fieldname for f in meta.fields]
		for field in ["field_definition", "field_value"]:
			self.assertIn(field, field_names, f"Campo '{field}' debe existir en Addenda Field Value")

	def test_addenda_type_permissions(self):
		"""Test: Addenda Type tiene permisos configurados"""
		meta = frappe.get_meta("Addenda Type")
		self.assertGreater(len(meta.permissions), 0, "Addenda Type debe tener permisos configurados")


if __name__ == "__main__":
	unittest.main()
