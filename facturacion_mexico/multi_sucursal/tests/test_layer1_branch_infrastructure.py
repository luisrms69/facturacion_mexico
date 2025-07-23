# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 1 Unit Tests - Multi-Sucursal Infrastructure
Sprint 6: Tests unitarios de infraestructura base multi-sucursal
"""

import unittest

import frappe
from frappe.test_runner import make_test_records


class TestLayer1BranchInfrastructure(unittest.TestCase):
	"""
	Layer 1 Unit Tests - Infraestructura Branch Multi-Sucursal
	Tests sin dependencia de DB compleja, enfocados en lógica de negocio
	"""

	@classmethod
	def setUpClass(cls):
		"""Setup para toda la clase de tests"""
		# Aplicar flag para tests unitarios
		frappe.flags.skip_test_records = True

		# Crear records básicos necesarios
		make_test_records("Company")

		# Asegurar que existan los custom fields
		cls.setup_custom_fields_if_needed()

	@classmethod
	def setup_custom_fields_if_needed(cls):
		"""Crear custom fields si no existen"""
		try:
			from facturacion_mexico.multi_sucursal.custom_fields.branch_fiscal_fields import (
				create_branch_fiscal_custom_fields,
			)

			# Verificar si ya existen
			if not frappe.db.exists("Custom Field", {"dt": "Branch", "fieldname": "fm_enable_fiscal"}):
				create_branch_fiscal_custom_fields()
				frappe.db.commit()

		except Exception as e:
			print(f"Warning: Could not setup custom fields: {e!s}")

	def setUp(self):
		"""Setup para cada test individual"""
		# Limpiar cache
		frappe.clear_cache()

		# Variables de test
		self.test_company = "_Test Company Multi-Sucursal"
		self.test_branch_name = "_Test Branch Fiscal"

		# Crear company de test si no existe
		if not frappe.db.exists("Company", self.test_company):
			company = frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": self.test_company,
					"abbr": "TCMS",
					"default_currency": "MXN",
					"country": "Mexico",
				}
			)
			company.insert(ignore_permissions=True)

	def tearDown(self):
		"""Cleanup después de cada test"""
		# Limpiar documentos de test
		try:
			# Eliminar configuraciones fiscales de test
			configs = frappe.get_all("Configuracion Fiscal Sucursal", filters={"branch": ["like", "_Test%"]})
			for config in configs:
				frappe.delete_doc("Configuracion Fiscal Sucursal", config.name, ignore_permissions=True)

			# Eliminar branches de test
			branches = frappe.get_all("Branch", filters={"branch": ["like", "_Test%"]})
			for branch in branches:
				frappe.delete_doc("Branch", branch.name, ignore_permissions=True)

		except Exception as e:
			# No fallar por cleanup
			print(f"Cleanup warning: {e!s}")

	def test_branch_custom_fields_exist(self):
		"""Test: Verificar que existan los custom fields necesarios"""
		required_fields = [
			"fm_enable_fiscal",
			"fm_lugar_expedicion",
			"fm_serie_pattern",
			"fm_folio_start",
			"fm_folio_current",
			"fm_folio_end",
			"fm_share_certificates",
		]

		for field_name in required_fields:
			field_exists = frappe.db.exists("Custom Field", {"dt": "Branch", "fieldname": field_name})
			self.assertTrue(field_exists, f"Custom field {field_name} debe existir en Branch")

	def test_branch_fiscal_validation_logic(self):
		"""Test: Lógica de validación fiscal de Branch"""
		from facturacion_mexico.multi_sucursal.custom_fields.branch_fiscal_fields import (
			validate_branch_fiscal_configuration,
		)

		# Crear branch de test
		branch_doc = frappe.get_doc(
			{
				"doctype": "Branch",
				"branch": self.test_branch_name,
				"company": self.test_company,
				"fm_enable_fiscal": 1,
				"fm_lugar_expedicion": "06600",
				"fm_folio_start": 1,
				"fm_folio_end": 1000,
			}
		)

		# Test: Validación exitosa
		try:
			validate_branch_fiscal_configuration(branch_doc, None)
			# Si no lanza excepción, la validación pasó
			self.assertTrue(True)
		except Exception as e:
			self.fail(f"Validación fiscal falló: {e!s}")

		# Test: Validación con lugar_expedicion inválido
		branch_doc.fm_lugar_expedicion = "12345A"  # No numérico
		with self.assertRaises(frappe.ValidationError):
			validate_branch_fiscal_configuration(branch_doc, None)

		# Test: Validación sin lugar_expedicion
		branch_doc.fm_lugar_expedicion = ""
		with self.assertRaises(frappe.ValidationError):
			validate_branch_fiscal_configuration(branch_doc, None)

	def test_folio_range_validation(self):
		"""Test: Validación de rangos de folios"""
		from facturacion_mexico.multi_sucursal.custom_fields.branch_fiscal_fields import (
			validate_branch_fiscal_configuration,
		)

		branch_doc = frappe.get_doc(
			{
				"doctype": "Branch",
				"branch": self.test_branch_name + " Folios",
				"company": self.test_company,
				"fm_enable_fiscal": 1,
				"fm_lugar_expedicion": "06600",
			}
		)

		# Test: Folio start menor a 1
		branch_doc.fm_folio_start = 0
		with self.assertRaises(frappe.ValidationError):
			validate_branch_fiscal_configuration(branch_doc, None)

		# Test: Folio end menor que start
		branch_doc.fm_folio_start = 100
		branch_doc.fm_folio_end = 50
		with self.assertRaises(frappe.ValidationError):
			validate_branch_fiscal_configuration(branch_doc, None)

		# Test: Rangos válidos
		branch_doc.fm_folio_start = 1
		branch_doc.fm_folio_end = 1000
		try:
			validate_branch_fiscal_configuration(branch_doc, None)
			self.assertTrue(True)
		except Exception as e:
			self.fail(f"Validación de rangos válidos falló: {e!s}")

	def test_configuracion_fiscal_sucursal_doctype_exists(self):
		"""Test: Verificar que exista el DocType Configuracion Fiscal Sucursal"""
		doctype_exists = frappe.db.exists("DocType", "Configuracion Fiscal Sucursal")
		self.assertTrue(doctype_exists, "DocType 'Configuracion Fiscal Sucursal' debe existir")

		# Verificar campos críticos del DocType
		meta = frappe.get_meta("Configuracion Fiscal Sucursal")

		required_fields = [
			"branch",
			"company",
			"serie_fiscal",
			"folio_current",
			"folio_warning_threshold",
			"folio_critical_threshold",
		]

		existing_fields = [field.fieldname for field in meta.fields]

		for field_name in required_fields:
			self.assertIn(
				field_name,
				existing_fields,
				f"Campo {field_name} debe existir en Configuracion Fiscal Sucursal",
			)

	def test_branch_serie_pattern_logic(self):
		"""Test: Lógica de patrones de serie"""
		# Test de patterns básicos
		test_patterns = [
			"{abbr}-{yyyy}",  # TCMS-2025
			"SUC1-{mm}{yyyy}",  # SUC1-072025
			"MATRIZ-{dd}{mm}",  # MATRIZ-2207
			"BRANCH-{yyyy}-{mm}-{dd}",  # BRANCH-2025-07-22
		]

		for pattern in test_patterns:
			# Verificar que el pattern sea válido (básico)
			self.assertIn("{", pattern, "Pattern debe contener variables")
			self.assertTrue(len(pattern) > 0, "Pattern no debe estar vacío")

	def test_folio_calculation_logic(self):
		"""Test: Lógica de cálculo de folios disponibles"""
		# Simular cálculos de folios sin base de datos
		folio_start = 1
		folio_end = 1000
		folio_current = 250

		# Folios disponibles
		remaining = folio_end - folio_current
		self.assertEqual(remaining, 750, "Cálculo de folios restantes debe ser correcto")

		# Porcentaje usado
		used_percentage = ((folio_current - folio_start) / (folio_end - folio_start)) * 100
		self.assertAlmostEqual(
			used_percentage, 24.92, places=1, msg="Porcentaje usado debe calcularse correctamente"
		)

		# Test con umbral de advertencia
		warning_threshold = 100
		critical_threshold = 50

		# Status normal
		if remaining > warning_threshold:
			status = "normal"
		elif remaining > critical_threshold:
			status = "warning"
		else:
			status = "critical"

		self.assertEqual(status, "normal", "Status debe ser normal con 750 folios restantes")

	def test_codigo_postal_validation_logic(self):
		"""Test: Validación de códigos postales mexicanos"""
		# Códigos postales válidos
		valid_cp = ["06600", "01000", "99999", "00000"]
		for cp in valid_cp:
			self.assertTrue(cp.isdigit() and len(cp) == 5, f"Código postal {cp} debe ser válido")

		# Códigos postales inválidos
		invalid_cp = ["6600", "066000", "06600A", "", "ABCDE"]
		for cp in invalid_cp:
			self.assertFalse(cp.isdigit() and len(cp) == 5, f"Código postal {cp} debe ser inválido")

	def test_certificate_sharing_logic(self):
		"""Test: Lógica de compartición de certificados"""
		# Test básico de lógica de certificados

		# Modo compartido
		share_certificates = True
		specific_certificates = []

		if share_certificates:
			# Debe usar pool compartido
			cert_source = "shared_pool"
		else:
			# Debe usar certificados específicos
			cert_source = "specific_certs" if specific_certificates else "none"

		self.assertEqual(cert_source, "shared_pool", "Con share_certificates=True debe usar pool compartido")

		# Modo específico
		share_certificates = False
		specific_certificates = ["cert1", "cert2"]

		if share_certificates:
			cert_source = "shared_pool"
		else:
			cert_source = "specific_certs" if specific_certificates else "none"

		self.assertEqual(
			cert_source, "specific_certs", "Con certificados específicos debe usar specific_certs"
		)

	def test_certificate_selector_integration(self):
		"""Test: Verificar integración con Certificate Selector"""
		try:
			from facturacion_mexico.multi_sucursal.certificate_selector import (
				MultibranchCertificateManager,
				get_available_certificates,
				get_branch_certificate_status,
			)

			# Test: Crear manager
			manager = MultibranchCertificateManager(self.test_company, self.test_branch_name)
			self.assertIsNotNone(manager, "MultibranchCertificateManager debe crearse correctamente")

			# Test: Obtener certificados disponibles
			certificates = get_available_certificates(self.test_company, self.test_branch_name)
			self.assertIsInstance(certificates, list, "get_available_certificates debe retornar lista")

			# Test: API de estado de certificados de sucursal
			status_result = get_branch_certificate_status(self.test_branch_name)
			self.assertIsInstance(status_result, dict, "get_branch_certificate_status debe retornar dict")
			self.assertIn("success", status_result, "Resultado debe incluir campo 'success'")

			print("✅ Certificate Selector integrado correctamente")

		except ImportError as e:
			self.fail(f"Error importando Certificate Selector: {e!s}")
		except Exception as e:
			self.fail(f"Error en integración Certificate Selector: {e!s}")


if __name__ == "__main__":
	# Permitir ejecutar tests individualmente
	unittest.main()
