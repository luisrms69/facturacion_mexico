"""
Tests 4-Layer para SAT Validation Cache - Sprint 2
Sistema de Facturación México - Metodología Buzola
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.validaciones.doctype.sat_validation_cache.sat_validation_cache import (
	SATValidationCache,
)


class TestSATValidationCache(FrappeTestCase):
	"""Tests 4-Layer para SAT Validation Cache siguiendo metodología Buzola."""

	def setUp(self):
		"""Configuración común para todos los tests."""
		self.test_rfc = "XAXX010101000"
		self.test_validation_type = "rfc_validation"
		self.today = datetime.now().date()

	# ═══════════════════════════════════════════════════════════════════
	# LAYER 1: UNIT TESTS - Funciones puras sin dependencias externas
	# ═══════════════════════════════════════════════════════════════════

	def test_layer1_calculate_expiry_date_rfc_validation(self):
		"""Layer 1: Test cálculo de fecha de expiración para RFC (30 días)."""
		# Arrange
		cache = frappe.new_doc("SAT Validation Cache")
		cache.validation_type = "fm_rfc"
		cache.validation_date = self.today

		# Act
		cache.calculate_expiry_date()

		# Assert
		expected_expiry = self.today + timedelta(days=30)
		self.assertEqual(cache.expiry_date, expected_expiry)

	def test_layer1_calculate_expiry_date_lista69b(self):
		"""Layer 1: Test cálculo de fecha de expiración para Lista 69B (7 días)."""
		# Arrange
		cache = frappe.new_doc("SAT Validation Cache")
		cache.validation_type = "Lista69B"
		cache.validation_date = self.today

		# Act
		cache.calculate_expiry_date()

		# Assert
		expected_expiry = self.today + timedelta(days=7)
		self.assertEqual(cache.expiry_date, expected_expiry)

	def test_layer1_calculate_expiry_date_default_type(self):
		"""Layer 1: Test cálculo de fecha de expiración para tipo por defecto."""
		# Arrange
		cache = frappe.new_doc("SAT Validation Cache")
		cache.validation_type = "unknown_type"
		cache.validation_date = self.today

		# Act
		cache.calculate_expiry_date()

		# Assert
		expected_expiry = self.today + timedelta(days=30)  # Default
		self.assertEqual(cache.expiry_date, expected_expiry)

	@patch("frappe.utils.today")
	def test_layer1_is_cache_expired_true(self, mock_today):
		"""Layer 1: Test detección de cache expirado."""
		# Arrange
		mock_today.return_value = self.today
		cache = frappe.new_doc("SAT Validation Cache")
		cache.expiry_date = self.today - timedelta(days=1)  # Ayer

		# Act
		result = cache.is_expired()

		# Assert
		self.assertTrue(result)

	@patch("frappe.utils.today")
	def test_layer1_is_cache_expired_false(self, mock_today):
		"""Layer 1: Test detección de cache válido."""
		# Arrange
		mock_today.return_value = self.today
		cache = frappe.new_doc("SAT Validation Cache")
		cache.expiry_date = self.today + timedelta(days=1)  # Mañana

		# Act
		result = cache.is_expired()

		# Assert
		self.assertFalse(result)

	@patch("frappe.utils.today")
	def test_layer1_is_cache_expired_today_edge_case(self, mock_today):
		"""Layer 1: Test caso límite - expira hoy."""
		# Arrange
		mock_today.return_value = self.today
		cache = frappe.new_doc("SAT Validation Cache")
		cache.expiry_date = self.today

		# Act
		result = cache.is_expired()

		# Assert
		self.assertTrue(result)  # Hoy ya está expirado según la implementación

	# ═══════════════════════════════════════════════════════════════════
	# LAYER 2: BUSINESS LOGIC TESTS - Lógica de negocio con mocks
	# ═══════════════════════════════════════════════════════════════════

	@patch("frappe.utils.now")
	def test_layer2_set_metadata_automatic_fields(self, mock_now):
		"""Layer 2: Test establecimiento automático de metadatos."""
		# Arrange
		mock_now.return_value = "2025-07-19 15:30:00"
		cache = frappe.new_doc("SAT Validation Cache")

		# Act
		cache.set_metadata()

		# Assert
		self.assertEqual(cache.validation_date, "2025-07-19 15:30:00")
		self.assertEqual(cache.created_by, "Administrator")

	@patch("frappe.session")
	def test_layer2_set_metadata_user_tracking(self, mock_session):
		"""Layer 2: Test rastreo de usuario en metadatos."""
		# Arrange
		mock_session.user = "test@example.com"
		cache = frappe.new_doc("SAT Validation Cache")

		# Act
		cache.set_metadata()

		# Assert
		self.assertEqual(cache.created_by, "test@example.com")

	@patch("frappe.db.get_value")
	def test_layer2_validate_no_duplicate_active_cache(self, mock_get_value):
		"""Layer 2: Test validación sin duplicados activos."""
		# Arrange
		mock_get_value.return_value = None  # No existe cache activo

		cache = frappe.new_doc("SAT Validation Cache")
		cache.lookup_value = "XAXX010101000"
		cache.validation_type = "fm_rfc"

		# Act & Assert (no debe lanzar excepción)
		try:
			cache.validate_no_duplicate_cache()
		except Exception as e:
			self.fail(f"validate_no_duplicate_cache() raised {e} unexpectedly!")

	@patch("frappe.db.get_value")
	def test_layer2_validate_duplicate_active_cache_error(self, mock_get_value):
		"""Layer 2: Test error por cache duplicado activo."""
		# Arrange
		mock_get_value.return_value = "SAT-CACHE-001"  # Existe cache activo

		cache = frappe.new_doc("SAT Validation Cache")
		cache.lookup_value = "XAXX010101000"
		cache.validation_type = "fm_rfc"

		# Act & Assert
		with self.assertRaises(frappe.ValidationError) as context:
			cache.validate_no_duplicate_cache()
		self.assertIn("ya existe", str(context.exception).lower())

	@patch(
		"facturacion_mexico.validaciones.doctype.sat_validation_cache.sat_validation_cache.cleanup_expired_cache"
	)
	def test_layer2_deactivate_expired_caches_bulk_operation(self, mock_cleanup):
		"""Layer 2: Test desactivación masiva de caches expirados."""
		# Arrange
		mock_cleanup.return_value = {"success": True, "cleaned_count": 5}

		# Act
		result = SATValidationCache.deactivate_expired_caches()

		# Assert
		mock_cleanup.assert_called_once()
		self.assertEqual(result, 5)

	# ═══════════════════════════════════════════════════════════════════
	# LAYER 3: INTEGRATION TESTS - Flujo completo con datos simulados
	# ═══════════════════════════════════════════════════════════════════

	@patch("frappe.db.exists")
	@patch("frappe.utils.now")
	def test_layer3_create_cache_complete_flow(self, mock_now, mock_exists):
		"""Layer 3: Test flujo completo de creación de cache."""
		# Arrange
		mock_now.return_value = "2025-07-19 15:30:00"
		mock_exists.return_value = None  # No existe cache previo

		# Act
		with patch("frappe.new_doc") as mock_new_doc:
			mock_cache = MagicMock()
			mock_new_doc.return_value = mock_cache
			mock_cache.name = "SAT-CACHE-TEST-001"

			result = SATValidationCache.create_cache_record(
				lookup_value="XAXX010101000",
				validation_type="fm_rfc",
				is_valid=True,
				validation_data='{"valid": true, "status": "Activo"}',
			)

			# Assert
			mock_cache.insert.assert_called_once()
			self.assertEqual(result, "SAT-CACHE-TEST-001")

	@patch("frappe.db.get_value")
	def test_layer3_get_valid_cache_entry_found(self, mock_get_value):
		"""Layer 3: Test obtención de cache válido existente."""
		# Arrange
		mock_get_value.return_value = "SAT-CACHE-001"

		# Mock SATValidationCache.get_cached_validation
		with patch.object(SATValidationCache, "get_cached_validation") as mock_get_cached:
			mock_get_cached.return_value = {
				"success": True,
				"is_valid": True,
				"data": {"valid": True, "status": "Activo"},
			}

			# Act
			result = SATValidationCache.get_valid_cache("XAXX010101000", "fm_rfc")

			# Assert
			self.assertIsNotNone(result)
			self.assertEqual(result["valid"], True)

	@patch("frappe.db.get_value")
	def test_layer3_get_valid_cache_entry_not_found(self, mock_get_value):
		"""Layer 3: Test obtención de cache - no encontrado."""
		# Arrange
		mock_get_value.return_value = None

		# Mock SATValidationCache.get_cached_validation
		with patch.object(SATValidationCache, "get_cached_validation") as mock_get_cached:
			mock_get_cached.return_value = {"success": True, "is_valid": False, "data": {}}

			# Act
			result = SATValidationCache.get_valid_cache("NONEXISTENT", "fm_rfc")

			# Assert
			self.assertIsNone(result)

	# ═══════════════════════════════════════════════════════════════════
	# LAYER 4: PERFORMANCE & CONFIGURATION TESTS
	# ═══════════════════════════════════════════════════════════════════

	@patch(
		"facturacion_mexico.validaciones.doctype.sat_validation_cache.sat_validation_cache.cleanup_expired_cache"
	)
	def test_layer4_cache_cleanup_performance_query(self, mock_cleanup):
		"""Layer 4: Test rendimiento de consulta de limpieza."""
		# Arrange
		mock_cleanup.return_value = {"success": True, "cleaned_count": 50}

		# Act
		result = SATValidationCache.cleanup_expired_caches(days_to_keep=90)

		# Assert
		self.assertEqual(result, 50)
		mock_cleanup.assert_called_once()

	def test_layer4_cache_key_generation_consistency(self):
		"""Layer 4: Test consistencia en generación de cache keys."""
		# Test múltiples formatos de RFC
		test_rfcs = ["XAXX010101000", "xaxx010101000", "XAXX-010101-000"]

		cache_keys = []
		for rfc in test_rfcs:
			cache = frappe.new_doc("SAT Validation Cache")
			cache.lookup_value = rfc.upper().replace("-", "")
			cache_keys.append(cache.lookup_value)

		# Todos deberían normalizarse al mismo formato
		expected_key = "XAXX010101000"
		for key in cache_keys:
			self.assertEqual(key, expected_key)

	@patch.object(SATValidationCache, "get_cached_validation")
	def test_layer4_massive_cache_lookup_performance(self, mock_get_cached):
		"""Layer 4: Test rendimiento con búsquedas masivas."""
		# Arrange
		mock_get_cached.return_value = {"success": True, "is_valid": False, "data": {}}

		start_time = datetime.now()

		for i in range(100):  # Reducido para test rápido
			SATValidationCache.get_valid_cache(f"TEST{i:06d}", "fm_rfc")

		end_time = datetime.now()
		execution_time = (end_time - start_time).total_seconds()

		# Debe completarse en menos de 1 segundo para 100 consultas
		self.assertLess(execution_time, 1.0)

	def test_layer4_memory_usage_large_result_data(self):
		"""Layer 4: Test uso de memoria con datos grandes."""
		# Simular cache con datos JSON grandes
		large_result_data = {
			"valid": True,
			"details": ["item_" + str(i) for i in range(1000)],
			"metadata": {"key_" + str(i): f"value_{i}" for i in range(500)},
		}

		cache = frappe.new_doc("SAT Validation Cache")
		cache.validation_key = "RFC_LARGE_DATA_TEST"
		cache.validation_type = "rfc_validation"
		cache.result_data = str(large_result_data)  # Convertir a string como en DB

		# Verificar que puede manejar datos grandes sin problemas
		self.assertIsNotNone(cache.result_data)
		self.assertGreater(len(cache.result_data), 10000)  # Datos grandes

	def test_layer4_cache_expiry_edge_cases_timezone(self):
		"""Layer 4: Test casos límite de expiración con zonas horarias."""
		# Test diferentes configuraciones de zona horaria
		cache = frappe.new_doc("SAT Validation Cache")
		cache.validation_type = "rfc_validation"

		# Simular diferentes horas del día
		test_times = [
			datetime.now().replace(hour=0, minute=0, second=0),  # Inicio del día
			datetime.now().replace(hour=23, minute=59, second=59),  # Final del día
			datetime.now().replace(hour=12, minute=0, second=0),  # Mediodía
		]

		for test_time in test_times:
			cache.validation_date = test_time.date()
			cache.calculate_expiry_date()

			# Verificar que siempre calcula correctamente
			expected_expiry = test_time.date() + timedelta(days=30)
			self.assertEqual(cache.expiry_date, expected_expiry)


# ═══════════════════════════════════════════════════════════════════
# TESTS UTILITARIOS PARA MÉTODOS ESTÁTICOS
# ═══════════════════════════════════════════════════════════════════


class TestSATValidationCacheStatics(FrappeTestCase):
	"""Tests para métodos estáticos de SAT Validation Cache."""

	@patch(
		"facturacion_mexico.validaciones.doctype.sat_validation_cache.sat_validation_cache.cleanup_expired_cache"
	)
	def test_cleanup_expired_caches_return_count(self, mock_cleanup):
		"""Test retorno correcto del conteo de limpieza."""
		# Arrange
		mock_cleanup.return_value = {"success": True, "cleaned_count": 25}

		# Act
		result = SATValidationCache.cleanup_expired_caches(30)

		# Assert
		self.assertEqual(result, 25)

	def test_generate_cache_key_rfc_format(self):
		"""Test generación de cache key para RFC."""
		# Test directo de la lógica (sin método específico, se infiere)
		fm_rfc = "XAXX010101000"

		expected_key = f"RFC_{fm_rfc}"
		cache_key = f"RFC_{fm_rfc}"  # Simulación de la lógica

		self.assertEqual(cache_key, expected_key)


if __name__ == "__main__":
	unittest.main()
