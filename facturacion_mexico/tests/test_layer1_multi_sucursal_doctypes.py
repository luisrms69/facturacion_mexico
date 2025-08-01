# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 1 Multi Sucursal DocTypes Tests
Tests básicos para verificar DocTypes del sistema Multi-Sucursal Sprint 6
"""

import unittest

import frappe


class TestLayer1MultiSucursalDocTypes(unittest.TestCase):
	"""Tests de DocTypes Multi-Sucursal básicos - Layer 1"""

	@classmethod
	def setUpClass(cls):
		"""Setup inicial para todos los tests"""
		frappe.clear_cache()

	def test_configuracion_fiscal_sucursal_doctype(self):
		"""Test: DocType Configuracion Fiscal Sucursal existe y funciona"""
		# Verificar que el DocType existe
		self.assertTrue(frappe.db.exists("DocType", "Configuracion Fiscal Sucursal"))

		# Verificar campos obligatorios del DocType
		doctype_meta = frappe.get_meta("Configuracion Fiscal Sucursal")
		field_names = [field.fieldname for field in doctype_meta.fields]

		# Campos básicos esperados (basados en implementación real)
		expected_fields = [
			"branch", "company", "serie_fiscal",
			"folio_warning_threshold", "folio_critical_threshold",
			"folio_current", "certificate_ids"
		]

		for field in expected_fields:
			self.assertIn(field, field_names,
				f"Campo '{field}' debe existir en Configuracion Fiscal Sucursal")

	def test_configuracion_fiscal_sucursal_creation(self):
		"""Test: Puede crear instancia del DocType"""
		try:
			config = frappe.new_doc("Configuracion Fiscal Sucursal")
			self.assertIsNotNone(config)

			# Verificar que tiene métodos básicos
			self.assertTrue(hasattr(config, 'validate'))
			self.assertTrue(hasattr(config, 'before_save'))

		except Exception as e:
			self.fail(f"No se puede crear Configuracion Fiscal Sucursal: {e}")

	def test_configuracion_fiscal_sucursal_links(self):
		"""Test: DocType tiene links correctos configurados"""
		doctype_meta = frappe.get_meta("Configuracion Fiscal Sucursal")

		# Buscar campos de tipo Link
		link_fields = [field for field in doctype_meta.fields if field.fieldtype == "Link"]

		# Verificar links esperados
		expected_links = {
			"branch": "Branch",
			"company": "Company"
		}

		for field in link_fields:
			if field.fieldname in expected_links:
				self.assertEqual(field.options, expected_links[field.fieldname],
					f"Campo '{field.fieldname}' debe tener link a '{expected_links[field.fieldname]}'")

	def test_configuracion_fiscal_sucursal_validations(self):
		"""Test: DocType tiene validaciones básicas configuradas"""
		doctype_meta = frappe.get_meta("Configuracion Fiscal Sucursal")

		# Verificar campos obligatorios
		mandatory_fields = [field.fieldname for field in doctype_meta.fields if field.reqd]

		# Al menos branch debe ser obligatorio
		self.assertIn("branch", mandatory_fields,
			"Campo 'branch' debe ser obligatorio")

	def test_configuracion_fiscal_sucursal_permissions(self):
		"""Test: DocType tiene permisos básicos configurados"""
		doctype_name = "Configuracion Fiscal Sucursal"

		# Verificar que el DocType tiene permisos configurados
		try:
			doctype_meta = frappe.get_meta(doctype_name)

			# Skip child tables (istable=1) as they don't have their own permissions
			if doctype_meta.istable:
				return

			permissions = doctype_meta.permissions

			# Debe tener al menos un permiso configurado
			self.assertGreater(len(permissions), 0,
				f"DocType '{doctype_name}' debe tener permisos configurados")
		except Exception as e:
			self.fail(f"Error verificando permisos de '{doctype_name}': {e}")

	def test_configuracion_fiscal_sucursal_naming(self):
		"""Test: DocType tiene naming configurado"""
		doctype_meta = frappe.get_meta("Configuracion Fiscal Sucursal")

		# Verificar que tiene autoname o naming_series
		has_naming = (
			doctype_meta.autoname or
			any(field.fieldname == "naming_series" for field in doctype_meta.fields)
		)

		self.assertTrue(has_naming,
			"Configuracion Fiscal Sucursal debe tener naming configurado")

	def test_configuracion_fiscal_sucursal_database_table(self):
		"""Test: DocType está correctamente registrado en base de datos"""
		doctype_name = "Configuracion Fiscal Sucursal"

		# Verificar que existe en tabDocType
		exists_in_db = frappe.db.get_value("DocType", doctype_name, "name")
		self.assertEqual(exists_in_db, doctype_name,
			f"DocType '{doctype_name}' debe estar registrado en base de datos")

		# Solo verificar que el DocType metadata es accesible
		try:
			doctype_meta = frappe.get_meta(doctype_name)
			self.assertIsNotNone(doctype_meta, f"Metadata de '{doctype_name}' debe ser accesible")
		except Exception as e:
			self.fail(f"Error accediendo metadata de '{doctype_name}': {e}")

	def test_configuracion_fiscal_sucursal_method_exists(self):
		"""Test: Métodos principales del DocType están disponibles"""
		try:
			# Importar la clase del DocType
			from facturacion_mexico.multi_sucursal.doctype.configuracion_fiscal_sucursal.configuracion_fiscal_sucursal import (
				ConfiguracionFiscalSucursal,
			)

			# Verificar que la clase existe
			self.assertIsNotNone(ConfiguracionFiscalSucursal)

			# Verificar métodos esperados
			expected_methods = [
				'validate_branch_configuration',
				'validate_folio_thresholds',
				'evaluate_attention_needed'
			]

			for method in expected_methods:
				self.assertTrue(hasattr(ConfiguracionFiscalSucursal, method),
					f"Método '{method}' debe existir en ConfiguracionFiscalSucursal")

		except ImportError as e:
			self.fail(f"No se puede importar ConfiguracionFiscalSucursal: {e}")

	def test_configuracion_fiscal_sucursal_fields_types(self):
		"""Test: Tipos de campos son correctos"""
		doctype_meta = frappe.get_meta("Configuracion Fiscal Sucursal")

		# Verificar tipos de campos específicos
		field_types = {field.fieldname: field.fieldtype for field in doctype_meta.fields}

		expected_types = {
			"branch": "Link",
			"company": "Link",
			"folio_warning_threshold": ["Int", "Float"],  # Puede ser cualquiera de estos
			"folio_critical_threshold": ["Int", "Float"],
			"is_default_branch": "Check"
		}

		for fieldname, expected_type in expected_types.items():
			if fieldname in field_types:
				actual_type = field_types[fieldname]
				if isinstance(expected_type, list):
					self.assertIn(actual_type, expected_type,
						f"Campo '{fieldname}' debe ser tipo {expected_type}, es '{actual_type}'")
				else:
					self.assertEqual(actual_type, expected_type,
						f"Campo '{fieldname}' debe ser tipo '{expected_type}', es '{actual_type}'")

	def test_configuracion_fiscal_sucursal_doctype_properties(self):
		"""Test: Propiedades del DocType están correctamente configuradas"""
		doctype_meta = frappe.get_meta("Configuracion Fiscal Sucursal")

		# Verificar propiedades básicas
		self.assertIsNotNone(doctype_meta.module, "DocType debe tener módulo asignado")
		self.assertEqual(doctype_meta.module, "Multi Sucursal",
			"DocType debe pertenecer al módulo 'Multi Sucursal'")

		# Verificar que es editable (no es submittable por defecto para configuración)
		self.assertFalse(doctype_meta.is_submittable,
			"Configuracion Fiscal Sucursal no debe ser submittable")


if __name__ == "__main__":
	unittest.main()
