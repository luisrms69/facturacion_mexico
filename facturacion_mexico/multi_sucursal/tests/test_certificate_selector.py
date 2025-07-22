# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 1 Unit Tests - Certificate Selector
Sprint 6: Tests para el selector de certificados multi-sucursal
"""

import json
import unittest
from datetime import date, timedelta

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.multi_sucursal.certificate_selector import (
	MultibranchCertificateManager,
	get_available_certificates,
	get_branch_certificate_status,
	select_certificate_for_invoice,
)


class TestCertificateSelector(FrappeTestCase):
	"""Tests para Certificate Selector Multi-Sucursal"""

	@classmethod
	def setUpClass(cls):
		"""Setup para toda la clase de tests"""
		super().setUpClass()

		# Crear empresa de test si no existe
		if not frappe.db.exists("Company", "_Test Company Certificate Selector"):
			company = frappe.new_doc("Company")
			company.company_name = "_Test Company Certificate Selector"
			company.abbr = "TCCS"
			company.default_currency = "MXN"
			company.country = "Mexico"
			company.insert(ignore_permissions=True)
			frappe.db.commit()

	def setUp(self):
		"""Setup para cada test individual"""
		frappe.clear_cache()

		# Variables de test
		self.test_company = "_Test Company Certificate Selector"
		self.test_branch = "_Test Branch Certificate Selector"

		# Crear sucursal de test con configuración fiscal
		self.create_test_branch()

	def tearDown(self):
		"""Cleanup después de cada test"""
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

	def create_test_branch(self):
		"""Crear sucursal de test con configuración fiscal"""
		try:
			if not frappe.db.exists("Branch", self.test_branch):
				branch = frappe.new_doc("Branch")
				branch.branch = self.test_branch
				branch.company = self.test_company
				branch.fm_enable_fiscal = 1
				branch.fm_lugar_expedicion = "01000"
				branch.fm_share_certificates = 1  # Compartir certificados por defecto
				branch.insert(ignore_permissions=True)
				frappe.db.commit()
		except Exception as e:
			print(f"Warning: Could not create test branch: {e!s}")

	def test_multibranch_certificate_manager_creation(self):
		"""Test: Crear instancia del MultibranchCertificateManager"""
		manager = MultibranchCertificateManager(self.test_company, self.test_branch)

		self.assertEqual(manager.company, self.test_company)
		self.assertEqual(manager.branch, self.test_branch)

	def test_get_available_certificates_basic(self):
		"""Test: Obtener certificados disponibles básicos"""
		manager = MultibranchCertificateManager(self.test_company, self.test_branch)
		certificates = manager.get_available_certificates()

		# Debe retornar una lista (puede estar vacía en testing)
		self.assertIsInstance(certificates, list)

	def test_certificate_sharing_logic(self):
		"""Test: Lógica de compartir certificados"""
		# Test 1: Branch con certificados compartidos habilitados
		manager = MultibranchCertificateManager(self.test_company, self.test_branch)
		branch_config = manager._get_branch_certificate_config()

		self.assertIsNotNone(branch_config)
		self.assertTrue(branch_config.get("share_certificates", True))

		# Test 2: Crear branch sin certificados compartidos
		test_branch_no_share = "_Test Branch No Share"

		try:
			branch = frappe.new_doc("Branch")
			branch.branch = test_branch_no_share
			branch.company = self.test_company
			branch.fm_enable_fiscal = 1
			branch.fm_lugar_expedicion = "01000"
			branch.fm_share_certificates = 0  # No compartir
			branch.insert(ignore_permissions=True)

			manager_no_share = MultibranchCertificateManager(self.test_company, test_branch_no_share)
			branch_config_no_share = manager_no_share._get_branch_certificate_config()

			self.assertFalse(branch_config_no_share.get("share_certificates", True))

		except Exception as e:
			self.fail(f"Error testing certificate sharing logic: {e!s}")

	def test_certificate_health_summary(self):
		"""Test: Resumen de salud de certificados"""
		manager = MultibranchCertificateManager(self.test_company, self.test_branch)
		health_summary = manager.get_certificate_health_summary()

		# Verificar estructura del resumen
		expected_keys = [
			"total_certificates",
			"healthy",
			"warning",
			"critical",
			"expired",
			"shared_certificates",
			"specific_certificates",
			"expiring_soon",
			"recommended_certificate",
		]

		for key in expected_keys:
			self.assertIn(key, health_summary)

		# Verificar tipos de datos
		self.assertIsInstance(health_summary["total_certificates"], int)
		self.assertIsInstance(health_summary["healthy"], int)

	def test_certificate_priority_calculation(self):
		"""Test: Cálculo de prioridad de certificados"""
		manager = MultibranchCertificateManager(self.test_company, self.test_branch)

		# Certificado saludable compartido
		cert_healthy = {"is_shared": True, "valid_to": date.today() + timedelta(days=180), "is_active": True}

		# Certificado que vence pronto
		cert_expiring = {"is_shared": True, "valid_to": date.today() + timedelta(days=15), "is_active": True}

		priority_healthy = manager._calculate_certificate_priority(cert_healthy)
		priority_expiring = manager._calculate_certificate_priority(cert_expiring)

		self.assertGreater(
			priority_healthy,
			priority_expiring,
			"Certificado saludable debe tener mayor prioridad que uno por vencer",
		)

	def test_certificate_health_status_calculation(self):
		"""Test: Cálculo de estado de salud de certificados"""
		manager = MultibranchCertificateManager(self.test_company, self.test_branch)

		# Certificado saludable
		cert_healthy = {"is_active": True, "valid_to": date.today() + timedelta(days=180)}

		status_healthy = manager._get_certificate_health_status(cert_healthy)
		self.assertEqual(status_healthy, "healthy")

		# Certificado vencido
		cert_expired = {"is_active": True, "valid_to": date.today() - timedelta(days=1)}

		status_expired = manager._get_certificate_health_status(cert_expired)
		self.assertEqual(status_expired, "expired")

		# Certificado crítico (vence en pocos días)
		cert_critical = {"is_active": True, "valid_to": date.today() + timedelta(days=10)}

		status_critical = manager._get_certificate_health_status(cert_critical)
		self.assertEqual(status_critical, "critical")

		# Certificado inactivo
		cert_inactive = {"is_active": False, "valid_to": date.today() + timedelta(days=180)}

		status_inactive = manager._get_certificate_health_status(cert_inactive)
		self.assertEqual(status_inactive, "inactive")

	def test_select_best_certificate(self):
		"""Test: Selección del mejor certificado"""
		manager = MultibranchCertificateManager(self.test_company, self.test_branch)

		# En modo desarrollo puede retornar certificados de ejemplo
		best_cert = manager.select_best_certificate("CSD")

		# Puede ser None si no hay certificados disponibles
		if best_cert:
			self.assertIsInstance(best_cert, dict)
			self.assertIn("id", best_cert)
			self.assertIn("name", best_cert)

	def test_certificate_validation(self):
		"""Test: Validación de disponibilidad de certificados"""
		manager = MultibranchCertificateManager(self.test_company, self.test_branch)

		# Test con certificado inexistente
		is_available, reason = manager.validate_certificate_availability("nonexistent_cert")
		self.assertFalse(is_available)
		self.assertIn("no encontrado", reason.lower())

	def test_branch_specific_certificates(self):
		"""Test: Certificados específicos de sucursal"""
		manager = MultibranchCertificateManager(self.test_company, self.test_branch)

		# Crear configuración fiscal con certificados específicos
		try:
			# Buscar si ya existe configuración
			existing_config = frappe.db.get_value(
				"Configuracion Fiscal Sucursal", {"branch": self.test_branch}
			)

			if existing_config:
				config_doc = frappe.get_doc("Configuracion Fiscal Sucursal", existing_config)
			else:
				config_doc = frappe.new_doc("Configuracion Fiscal Sucursal")
				config_doc.branch = self.test_branch
				config_doc.company = self.test_company

			# Agregar certificados específicos
			test_cert_ids = ["cert_001", "cert_002"]
			config_doc.certificate_ids = json.dumps(test_cert_ids)
			config_doc.save(ignore_permissions=True)

			# Obtener certificados específicos
			branch_certs = manager._get_branch_specific_certificates()

			# Verificar que se obtuvieron certificados
			self.assertGreater(len(branch_certs), 0, "Debe obtener certificados específicos de sucursal")

			# Verificar estructura de certificados
			for cert in branch_certs:
				self.assertIn("id", cert)
				self.assertIn("name", cert)
				self.assertIn("source", cert)
				self.assertEqual(cert["source"], "branch")
				self.assertEqual(cert["branch"], self.test_branch)

		except Exception as e:
			self.fail(f"Error testing branch specific certificates: {e!s}")

	def test_get_available_certificates_wrapper_function(self):
		"""Test: Función wrapper get_available_certificates"""
		# Test sin sucursal (solo global)
		global_certs = get_available_certificates(self.test_company)
		self.assertIsInstance(global_certs, list)

		# Test con sucursal específica
		branch_certs = get_available_certificates(self.test_company, self.test_branch)
		self.assertIsInstance(branch_certs, list)

	def test_api_get_branch_certificate_status(self):
		"""Test: API get_branch_certificate_status"""
		# Test con sucursal fiscal válida
		result = get_branch_certificate_status(self.test_branch)

		self.assertIsInstance(result, dict)
		self.assertIn("success", result)

		if result["success"]:
			self.assertIn("data", result)
			self.assertIn("branch", result["data"])
			self.assertIn("certificates", result["data"])
			self.assertIn("health_summary", result["data"])

	def test_api_select_certificate_for_invoice(self):
		"""Test: API select_certificate_for_invoice"""
		# Test selección de certificado para factura
		result = select_certificate_for_invoice(self.test_branch, "CSD")

		self.assertIsInstance(result, dict)
		self.assertIn("success", result)
		self.assertIn("message", result)

		# En modo desarrollo puede encontrar certificados de ejemplo
		if result["success"]:
			self.assertIn("certificate", result)
			self.assertIsNotNone(result["certificate"])

	def test_certificate_filtering_by_type(self):
		"""Test: Filtrado de certificados por tipo"""
		manager = MultibranchCertificateManager(self.test_company, self.test_branch)

		# Test filtros por tipo
		csd_certs = manager.get_available_certificates("CSD")
		fiel_certs = manager.get_available_certificates("FIEL")

		self.assertIsInstance(csd_certs, list)
		self.assertIsInstance(fiel_certs, list)

		# Verificar que los certificados tienen el tipo correcto
		for cert in csd_certs:
			if "type" in cert:
				self.assertEqual(cert["type"], "CSD")

		for cert in fiel_certs:
			if "type" in cert:
				self.assertEqual(cert["type"], "FIEL")

	def test_certificate_manager_without_branch(self):
		"""Test: Certificate Manager sin sucursal específica (solo global)"""
		manager = MultibranchCertificateManager(self.test_company)

		self.assertEqual(manager.company, self.test_company)
		self.assertIsNone(manager.branch)

		# Debe poder obtener certificados globales
		global_certs = manager.get_available_certificates()
		self.assertIsInstance(global_certs, list)


if __name__ == "__main__":
	unittest.main()
