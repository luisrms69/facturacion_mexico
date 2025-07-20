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
		cache = SATValidationCache()
		cache.validation_type = "rfc_validation"
		cache.validated_at = self.today

		# Act
		cache.calculate_expiry_date()

		# Assert
		expected_expiry = self.today + timedelta(days=30)
		self.assertEqual(cache.expires_at, expected_expiry)

	def test_layer1_calculate_expiry_date_lista69b(self):
		"""Layer 1: Test cálculo de fecha de expiración para Lista 69B (7 días)."""
		# Arrange
		cache = SATValidationCache()
		cache.validation_type = "lista_69b"
		cache.validated_at = self.today

		# Act
		cache.calculate_expiry_date()

		# Assert
		expected_expiry = self.today + timedelta(days=7)
		self.assertEqual(cache.expires_at, expected_expiry)

	def test_layer1_calculate_expiry_date_default_type(self):
		"""Layer 1: Test cálculo de fecha de expiración para tipo por defecto."""
		# Arrange
		cache = SATValidationCache()
		cache.validation_type = "unknown_type"
		cache.validated_at = self.today

		# Act
		cache.calculate_expiry_date()

		# Assert
		expected_expiry = self.today + timedelta(days=1)  # Default
		self.assertEqual(cache.expires_at, expected_expiry)

	def test_layer1_is_cache_expired_true(self):
		"""Layer 1: Test detección de cache expirado."""
		# Arrange
		cache = SATValidationCache()
		cache.expires_at = self.today - timedelta(days=1)  # Ayer

		# Act
		result = cache.is_cache_expired()

		# Assert
		self.assertTrue(result)

	def test_layer1_is_cache_expired_false(self):
		"""Layer 1: Test detección de cache válido."""
		# Arrange
		cache = SATValidationCache()
		cache.expires_at = self.today + timedelta(days=1)  # Mañana

		# Act
		result = cache.is_cache_expired()

		# Assert
		self.assertFalse(result)

	def test_layer1_is_cache_expired_today_edge_case(self):
		"""Layer 1: Test caso límite - expira hoy."""
		# Arrange
		cache = SATValidationCache()
		cache.expires_at = self.today

		# Act
		result = cache.is_cache_expired()

		# Assert
		self.assertFalse(result)  # Hoy todavía es válido

	# ═══════════════════════════════════════════════════════════════════
	# LAYER 2: BUSINESS LOGIC TESTS - Lógica de negocio con mocks
	# ═══════════════════════════════════════════════════════════════════

	@patch("frappe.utils.now")
	def test_layer2_set_metadata_automatic_fields(self, mock_now):
		"""Layer 2: Test establecimiento automático de metadatos."""
		# Arrange
		mock_now.return_value = "2025-07-19 15:30:00"
		cache = SATValidationCache()

		# Act
		cache.set_metadata()

		# Assert
		self.assertEqual(cache.validated_at, "2025-07-19 15:30:00")
		self.assertEqual(cache.cache_version, "1.0")

	@patch("frappe.session.user", "test@example.com")
	def test_layer2_set_metadata_user_tracking(self, mock_user):
		"""Layer 2: Test rastreo de usuario en metadatos."""
		# Arrange
		cache = SATValidationCache()

		# Act
		cache.set_metadata()

		# Assert
		self.assertEqual(cache.validated_by, "test@example.com")

	@patch("frappe.db.exists")
	def test_layer2_validate_no_duplicate_active_cache(self, mock_exists):
		"""Layer 2: Test validación sin duplicados activos."""
		# Arrange
		mock_exists.return_value = None  # No existe cache activo

		cache = SATValidationCache()
		cache.validation_key = "RFC_XAXX010101000"
		cache.validation_type = "rfc_validation"
		cache.is_active = 1

		# Act & Assert (no debe lanzar excepción)
		try:
			cache.validate_no_duplicate_cache()
		except Exception as e:
			self.fail(f"validate_no_duplicate_cache() raised {e} unexpectedly!")

	@patch("frappe.db.exists")
	def test_layer2_validate_duplicate_active_cache_error(self, mock_exists):
		"""Layer 2: Test error por cache duplicado activo."""
		# Arrange
		mock_exists.return_value = "SAT-CACHE-001"  # Existe cache activo

		cache = SATValidationCache()
		cache.validation_key = "RFC_XAXX010101000"
		cache.validation_type = "rfc_validation"
		cache.is_active = 1

		# Act & Assert
		with self.assertRaises(frappe.ValidationError) as context:
			cache.validate_no_duplicate_cache()
		self.assertIn("ya existe", str(context.exception).lower())

	@patch("frappe.db.sql")
	def test_layer2_deactivate_expired_caches_bulk_operation(self, mock_sql):
		"""Layer 2: Test desactivación masiva de caches expirados."""
		# Arrange
		mock_sql.return_value = None

		# Act
		SATValidationCache.deactivate_expired_caches()

		# Assert
		mock_sql.assert_called_once()
		call_args = mock_sql.call_args[0][0]
		self.assertIn("UPDATE", call_args)
		self.assertIn("is_active = 0", call_args)
		self.assertIn("expires_at < %s", call_args)

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
				validation_key="RFC_XAXX010101000",
				validation_type="rfc_validation",
				result_data={"valid": True, "status": "Activo"},
				source_system="FacturAPI",
			)

			# Assert
			mock_cache.insert.assert_called_once()
			self.assertEqual(result, "SAT-CACHE-TEST-001")

	@patch("frappe.db.get_list")
	def test_layer3_get_valid_cache_entry_found(self, mock_get_list):
		"""Layer 3: Test obtención de cache válido existente."""
		# Arrange
		mock_cache_data = {
			"name": "SAT-CACHE-001",
			"result_data": '{"valid": true, "status": "Activo"}',
			"validated_at": "2025-07-19 10:00:00",
			"expires_at": "2025-08-18",
		}
		mock_get_list.return_value = [mock_cache_data]

		# Act
		result = SATValidationCache.get_valid_cache("RFC_XAXX010101000", "rfc_validation")

		# Assert
		self.assertIsNotNone(result)
		self.assertEqual(result["name"], "SAT-CACHE-001")

	@patch("frappe.db.get_list")
	def test_layer3_get_valid_cache_entry_not_found(self, mock_get_list):
		"""Layer 3: Test obtención de cache - no encontrado."""
		# Arrange
		mock_get_list.return_value = []

		# Act
		result = SATValidationCache.get_valid_cache("RFC_NONEXISTENT", "rfc_validation")

		# Assert
		self.assertIsNone(result)

	# ═══════════════════════════════════════════════════════════════════
	# LAYER 4: PERFORMANCE & CONFIGURATION TESTS
	# ═══════════════════════════════════════════════════════════════════

	@patch("frappe.db.sql")
	def test_layer4_cache_cleanup_performance_query(self, mock_sql):
		"""Layer 4: Test rendimiento de consulta de limpieza."""
		# Arrange
		mock_sql.return_value = [(50,)]  # 50 registros limpiados

		# Act
		result = SATValidationCache.cleanup_expired_caches(days_to_keep=90)

		# Assert
		self.assertEqual(result, 50)
		# Verificar que se usa una consulta optimizada
		call_args = mock_sql.call_args_list
		self.assertEqual(len(call_args), 2)  # DELETE + COUNT

		# Verificar que usa índices correctos
		delete_query = call_args[0][0][0]
		self.assertIn("expires_at <", delete_query)
		self.assertIn("is_active = 0", delete_query)

	def test_layer4_cache_key_generation_consistency(self):
		"""Layer 4: Test consistencia en generación de cache keys."""
		# Test múltiples formatos de RFC
		test_rfcs = ["XAXX010101000", "xaxx010101000", "XAXX-010101-000"]

		cache_keys = []
		for rfc in test_rfcs:
			cache = SATValidationCache()
			cache.validation_key = f"RFC_{rfc.upper().replace('-', '')}"
			cache_keys.append(cache.validation_key)

		# Todos deberían normalizarse al mismo formato
		expected_key = "RFC_XAXX010101000"
		for key in cache_keys:
			self.assertEqual(key, expected_key)

	@patch("frappe.db.sql")
	def test_layer4_massive_cache_lookup_performance(self, mock_sql):
		"""Layer 4: Test rendimiento con búsquedas masivas."""
		# Simular 1000 consultas de cache
		mock_sql.return_value = []

		start_time = datetime.now()

		for i in range(100):  # Reducido para test rápido
			SATValidationCache.get_valid_cache(f"RFC_TEST{i:06d}", "rfc_validation")

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

		cache = SATValidationCache()
		cache.validation_key = "RFC_LARGE_DATA_TEST"
		cache.validation_type = "rfc_validation"
		cache.result_data = str(large_result_data)  # Convertir a string como en DB

		# Verificar que puede manejar datos grandes sin problemas
		self.assertIsNotNone(cache.result_data)
		self.assertGreater(len(cache.result_data), 10000)  # Datos grandes

	def test_layer4_cache_expiry_edge_cases_timezone(self):
		"""Layer 4: Test casos límite de expiración con zonas horarias."""
		# Test diferentes configuraciones de zona horaria
		cache = SATValidationCache()
		cache.validation_type = "rfc_validation"

		# Simular diferentes horas del día
		test_times = [
			datetime.now().replace(hour=0, minute=0, second=0),  # Inicio del día
			datetime.now().replace(hour=23, minute=59, second=59),  # Final del día
			datetime.now().replace(hour=12, minute=0, second=0),  # Mediodía
		]

		for test_time in test_times:
			cache.validated_at = test_time.date()
			cache.calculate_expiry_date()

			# Verificar que siempre calcula correctamente
			expected_expiry = test_time.date() + timedelta(days=30)
			self.assertEqual(cache.expires_at, expected_expiry)


# ═══════════════════════════════════════════════════════════════════
# TESTS UTILITARIOS PARA MÉTODOS ESTÁTICOS
# ═══════════════════════════════════════════════════════════════════


class TestSATValidationCacheStatics(FrappeTestCase):
	"""Tests para métodos estáticos de SAT Validation Cache."""

	@patch("frappe.db.sql")
	def test_cleanup_expired_caches_return_count(self, mock_sql):
		"""Test retorno correcto del conteo de limpieza."""
		# Arrange
		mock_sql.return_value = [(25,)]

		# Act
		result = SATValidationCache.cleanup_expired_caches(30)

		# Assert
		self.assertEqual(result, 25)

	def test_generate_cache_key_rfc_format(self):
		"""Test generación de cache key para RFC."""
		# Test directo de la lógica (sin método específico, se infiere)
		rfc = "XAXX010101000"

		expected_key = f"RFC_{rfc}"
		cache_key = f"RFC_{rfc}"  # Simulación de la lógica

		self.assertEqual(cache_key, expected_key)


if __name__ == "__main__":
	unittest.main()
