# Testing Framework 4-Layer para Dashboard Fiscal
"""
Dashboard Fiscal - Complete Testing Framework

Layer 1: Unit Tests - Pruebas individuales de componentes
Layer 2: Integration Tests - Pruebas de integración entre módulos
Layer 3: System Tests - Pruebas end-to-end del sistema completo
Layer 4: Acceptance Tests - Pruebas de aceptación de usuario y E2E

Para ejecutar todos los tests:
    python -m frappe.testing.framework run_complete_test_suite

Para ejecutar layers específicos:
    python run_complete_test_suite.py layer1
    python run_complete_test_suite.py integration
    python run_complete_test_suite.py acceptance
"""

# Import all test modules for automatic discovery
from . import (
	test_layer2_cache_integration,
	test_layer2_modules_integration,
	test_layer3_performance,
	test_layer3_system,
	test_layer4_acceptance,
	test_layer4_e2e,
)

__all__ = [
	"test_layer2_cache_integration",
	"test_layer2_modules_integration",
	"test_layer3_performance",
	"test_layer3_system",
	"test_layer4_acceptance",
	"test_layer4_e2e",
]
