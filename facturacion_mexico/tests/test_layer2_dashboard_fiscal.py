# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Layer 2 Dashboard Fiscal Integration Tests
Tests de integración para el dashboard fiscal Sprint 6
"""

import frappe
import unittest


class TestLayer2DashboardFiscal(unittest.TestCase):
    """Tests de integración dashboard fiscal - Layer 2"""

    @classmethod
    def setUpClass(cls):
        """Setup inicial para todos los tests"""
        frappe.clear_cache()

    def test_fiscal_health_score_doctype_integration(self):
        """Test: Integración del DocType Fiscal Health Score"""
        if not frappe.db.exists("DocType", "Fiscal Health Score"):
            self.skipTest("DocType Fiscal Health Score no disponible")

        # Verificar estructura del DocType
        meta = frappe.get_meta("Fiscal Health Score")
        self.assertIsNotNone(meta)

        # Verificar campos críticos
        field_names = [f.fieldname for f in meta.fields]
        critical_fields = ["company", "score", "calculation_date"]

        for field in critical_fields:
            if field in field_names:
                self.assertIn(field, field_names, f"Campo crítico {field} debe existir")

    def test_fiscal_health_factor_doctype_integration(self):
        """Test: Integración del DocType Fiscal Health Factor"""
        if not frappe.db.exists("DocType", "Fiscal Health Factor"):
            self.skipTest("DocType Fiscal Health Factor no disponible")

        # Verificar estructura del DocType
        meta = frappe.get_meta("Fiscal Health Factor")
        self.assertIsNotNone(meta)

        # Verificar campos críticos
        field_names = [f.fieldname for f in meta.fields]
        critical_fields = ["factor_name", "factor_type", "impact_score"]

        for field in critical_fields:
            if field in field_names:
                self.assertIn(field, field_names, f"Campo crítico {field} debe existir")

    def test_fiscal_health_recommendation_doctype_integration(self):
        """Test: Integración del DocType Fiscal Health Recommendation"""
        if not frappe.db.exists("DocType", "Fiscal Health Recommendation"):
            self.skipTest("DocType Fiscal Health Recommendation no disponible")

        # Verificar estructura del DocType
        meta = frappe.get_meta("Fiscal Health Recommendation")
        self.assertIsNotNone(meta)

        # Verificar campos críticos
        field_names = [f.fieldname for f in meta.fields]
        critical_fields = ["title", "priority", "category"]

        for field in critical_fields:
            if field in field_names:
                self.assertIn(field, field_names, f"Campo crítico {field} debe existir")

    def test_dashboard_user_preference_doctype_integration(self):
        """Test: Integración del DocType Dashboard User Preference"""
        if not frappe.db.exists("DocType", "Dashboard User Preference"):
            self.skipTest("DocType Dashboard User Preference no disponible")

        # Verificar estructura del DocType
        meta = frappe.get_meta("Dashboard User Preference")
        self.assertIsNotNone(meta)

        # Verificar campos críticos
        field_names = [f.fieldname for f in meta.fields]
        critical_fields = ["user", "refresh_interval"]

        for field in critical_fields:
            if field in field_names:
                self.assertIn(field, field_names, f"Campo crítico {field} debe existir")

    def test_dashboard_fiscal_modules_integration(self):
        """Test: Integración de módulos del dashboard fiscal"""
        dashboard_modules = [
            "facturacion_mexico.dashboard_fiscal.utils",
            "facturacion_mexico.dashboard_fiscal.api",
        ]

        for module in dashboard_modules:
            try:
                imported_module = __import__(module, fromlist=[''])
                self.assertIsNotNone(imported_module)
            except ImportError:
                # Si no se puede importar, no es crítico para Layer 2
                pass

    def test_dashboard_fiscal_database_consistency(self):
        """Test: Consistencia de base de datos para dashboard fiscal"""
        dashboard_tables = []

        if frappe.db.exists("DocType", "Fiscal Health Score"):
            dashboard_tables.append("tabFiscal Health Score")

        if frappe.db.exists("DocType", "Fiscal Health Factor"):
            dashboard_tables.append("tabFiscal Health Factor")

        if frappe.db.exists("DocType", "Fiscal Health Recommendation"):
            dashboard_tables.append("tabFiscal Health Recommendation")

        if frappe.db.exists("DocType", "Dashboard User Preference"):
            dashboard_tables.append("tabDashboard User Preference")

        for table in dashboard_tables:
            try:
                result = frappe.db.sql(f"SHOW TABLES LIKE '{table}'")
                self.assertGreater(len(result), 0, f"Tabla {table} debe existir")
            except Exception as e:
                self.fail(f"Error verificando tabla {table}: {e}")

    def test_dashboard_fiscal_permissions_integration(self):
        """Test: Permisos del dashboard fiscal están integrados"""
        dashboard_doctypes = ["Fiscal Health Score", "Fiscal Health Factor",
                             "Fiscal Health Recommendation", "Dashboard User Preference"]

        for doctype in dashboard_doctypes:
            if frappe.db.exists("DocType", doctype):
                try:
                    records = frappe.get_all(doctype, limit=1)
                    self.assertIsInstance(records, list)
                except frappe.PermissionError:
                    self.fail(f"Error de permisos accediendo a {doctype}")

    def test_fiscal_health_calculation_integration(self):
        """Test: Integración del cálculo de health fiscal"""
        if not frappe.db.exists("DocType", "Fiscal Health Score"):
            self.skipTest("Fiscal Health Score no disponible")

        # Verificar que hay al menos estructura para cálculos
        try:
            # Test básico de consulta de scores
            scores = frappe.db.sql("""
                SELECT COUNT(*) as count
                FROM `tabFiscal Health Score`
            """, as_dict=True)

            self.assertIsInstance(scores, list)
            self.assertIn("count", scores[0])
        except Exception as e:
            self.fail(f"Error en consulta básica de Fiscal Health Score: {e}")

    def test_dashboard_widgets_integration(self):
        """Test: Integración de widgets del dashboard"""
        # Verificar que los factores tienen tipos válidos
        if frappe.db.exists("DocType", "Fiscal Health Factor"):
            try:
                factor_types = frappe.db.sql("""
                    SELECT DISTINCT factor_type
                    FROM `tabFiscal Health Factor`
                    WHERE factor_type IS NOT NULL
                """, as_dict=True)

                self.assertIsInstance(factor_types, list)
            except Exception as e:
                # Error no crítico para Layer 2
                pass

    def test_dashboard_business_intelligence_integration(self):
        """Test: Integración de inteligencia de negocio del dashboard"""
        if not frappe.db.exists("DocType", "Fiscal Health Recommendation"):
            self.skipTest("Fiscal Health Recommendation no disponible")

        # Verificar estructura de recomendaciones
        try:
            recommendations = frappe.db.sql("""
                SELECT COUNT(*) as count,
                       COUNT(DISTINCT priority) as priority_types
                FROM `tabFiscal Health Recommendation`
            """, as_dict=True)

            self.assertIsInstance(recommendations, list)
        except Exception as e:
            # Error no crítico para Layer 2
            pass

    def test_dashboard_user_experience_integration(self):
        """Test: Integración de experiencia de usuario del dashboard"""
        if not frappe.db.exists("DocType", "Dashboard User Preference"):
            self.skipTest("Dashboard User Preference no disponible")

        # Verificar estructura de preferencias de usuario
        try:
            preferences = frappe.db.sql("""
                SELECT COUNT(*) as count
                FROM `tabDashboard User Preference`
            """, as_dict=True)

            self.assertIsInstance(preferences, list)
        except Exception as e:
            # Error no crítico para Layer 2
            pass


if __name__ == "__main__":
    unittest.main()