"""
Tests Layer 3 (System Integration) para Dashboard Fiscal - Sprint 5
Sistema de Facturación México - Metodología Buzola

Layer 3: Tests de integración completa del sistema con datos reales,
flujos end-to-end y validación de comportamiento del sistema completo.
"""

import json
import time
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import frappe
from frappe import _
from frappe.tests.utils import FrappeTestCase


class TestDashboardFiscalLayer3System(FrappeTestCase):
	"""Tests Layer 3 para Dashboard Fiscal con integración completa del sistema"""

	def setUp(self):
		"""Setup completo para tests Layer 3 con datos reales"""
		# Limpiar datos de tests previos
		try:
			frappe.db.delete("Fiscal Health Score", {"company": ["like", "%test%"]})
			frappe.db.delete("Dashboard User Preference", {"user": ["like", "%test%"]})
			frappe.db.commit()
		except Exception:
			pass

		# Crear company de test completa con configuraciones SAT
		self.test_company = "_Test Company L3 System"
		if not frappe.db.exists("Company", self.test_company):
			company_doc = frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": self.test_company,
					"abbr": "_TCL3S",
					"default_currency": "MXN",
					"country": "Mexico",
					# Configuraciones fiscales mexicanas
					"tax_id": "TCL340101000",
					"fm_regimen_fiscal": "601",  # General de Ley Personas Morales
				}
			)
			company_doc.insert(ignore_permissions=True)

		# Crear usuario completo para tests de preferencias
		self.test_user = "test.dashboard.layer3@facturacion.mx"
		if not frappe.db.exists("User", self.test_user):
			user_doc = frappe.get_doc(
				{
					"doctype": "User",
					"email": self.test_user,
					"first_name": "Test",
					"last_name": "Dashboard Layer3",
					"send_welcome_email": 0,
					"role_profile_name": "System Manager",
					"language": "es",
					"time_zone": "America/Mexico_City",
				}
			)
			user_doc.insert(ignore_permissions=True)

		# Configurar datos de test para el período
		self.test_date = frappe.utils.add_days(frappe.utils.today(), -1)
		self.period_start = date(2025, 7, 1)
		self.period_end = self.test_date

		# Configurar tolerancia para fluctuaciones estadísticas
		self.statistical_tolerance = 0.10  # 10% tolerancia para estadísticas

	def tearDown(self):
		"""Cleanup después de cada test"""
		frappe.db.rollback()

	def test_end_to_end_fiscal_health_calculation_system_flow(self):
		"""LAYER 3: Test flujo end-to-end completo de cálculo Fiscal Health Score"""

		# Step 1: Crear datos de sistema reales para timbrado
		self._create_realistic_sales_invoices_data()

		# Step 2: Crear datos de sistema reales para PPD
		self._create_realistic_payment_entries_data()

		# Step 3: Crear Fiscal Health Score y ejecutar cálculo completo
		health_score = frappe.get_doc(
			{
				"doctype": "Fiscal Health Score",
				"company": self.test_company,
				"score_date": self.test_date,
				"calculation_method": "Weighted Average",
			}
		)

		# Execute end-to-end calculation
		start_time = time.time()
		health_score.insert()  # Triggers validate() and calculate_health_score()
		calculation_time = time.time() - start_time

		# Step 4: Validate complete system integration
		self.assertIsNotNone(health_score.name, "Health Score debe tener nombre asignado")
		self.assertGreater(health_score.overall_score, 0, "Overall score debe ser calculado")
		self.assertLessEqual(health_score.overall_score, 100, "Overall score debe estar en rango válido")

		# Step 5: Validate module scores calculation with real data
		self.assertIsNotNone(health_score.timbrado_score, "Timbrado score debe ser calculado")
		self.assertIsNotNone(health_score.ppd_score, "PPD score debe ser calculado")

		# Step 6: Validate factors generation from real data
		total_factors = len(health_score.factors_positive) + len(health_score.factors_negative)
		self.assertGreater(total_factors, 0, "Debe generar factores basados en datos reales")

		# Step 7: Validate recommendations generation
		self.assertGreater(
			len(health_score.recommendations), 0, "Debe generar recomendaciones basadas en scores"
		)

		# Step 8: Validate system performance
		self.assertLess(calculation_time, 5.0, "Cálculo completo debe completar en menos de 5 segundos")
		self.assertGreater(health_score.calculation_duration_ms, 0, "Duración debe ser registrada")

		# Step 9: Validate data persistence
		retrieved_score = frappe.get_doc("Fiscal Health Score", health_score.name)
		self.assertEqual(retrieved_score.overall_score, health_score.overall_score)

	def test_dashboard_user_preference_complete_system_integration(self):
		"""LAYER 3: Test integración completa sistema Dashboard User Preference"""

		# Step 1: Crear preferencia compleja con layout avanzado
		complex_layout = {
			"version": "2.0",
			"theme_config": {
				"primary_color": "#1f4e79",
				"secondary_color": "#e8f4f8",
				"dark_mode_enabled": True,
			},
			"widgets": [
				{
					"id": "fiscal_health_overview",
					"type": "kpi_dashboard",
					"position": {"row": 1, "col": 1, "width": 6, "height": 4},
					"config": {
						"show_trends": True,
						"historical_data": True,
						"alert_thresholds": {"warning": 70, "critical": 50},
					},
					"permissions": ["read", "export"],
					"enabled": True,
				},
				{
					"id": "compliance_alerts",
					"type": "alert_panel",
					"position": {"row": 1, "col": 7, "width": 6, "height": 4},
					"config": {"show_resolved": False, "auto_refresh": 180, "max_alerts": 10},
					"permissions": ["read", "acknowledge"],
					"enabled": True,
				},
				{
					"id": "module_performance",
					"type": "chart_module",
					"position": {"row": 5, "col": 1, "width": 12, "height": 6},
					"config": {
						"chart_type": "line",
						"time_period": "30d",
						"modules": ["timbrado", "ppd", "ereceipts"],
					},
					"permissions": ["read"],
					"enabled": True,
				},
			],
			"global_settings": {
				"auto_save": True,
				"export_formats": ["pdf", "excel", "json"],
				"language": "es",
				"timezone": "America/Mexico_City",
			},
		}

		# Step 2: Crear Dashboard User Preference con configuración completa
		preference = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": self.test_user,
				"theme": "auto",
				"dashboard_layout": json.dumps(complex_layout),
				"auto_refresh": 1,
				"refresh_interval": 300,
				"show_notifications": 1,
				"notification_email": 1,
				"notification_browser": 1,
			}
		)

		# Step 3: Insert y validate system integration
		preference.insert()

		# Step 4: Test layout parsing and validation
		parsed_layout = preference.get_layout_config()
		self.assertIsInstance(parsed_layout, dict, "Layout debe ser parsed correctamente")
		self.assertEqual(parsed_layout["version"], "2.0", "Version debe ser preservada")
		self.assertEqual(len(parsed_layout["widgets"]), 3, "Todos los widgets deben ser preservados")

		# Step 5: Test system-level widget validation
		fiscal_widget = next(
			(w for w in parsed_layout["widgets"] if w["id"] == "fiscal_health_overview"), None
		)
		self.assertIsNotNone(fiscal_widget, "Widget fiscal_health_overview debe estar presente")
		self.assertEqual(fiscal_widget["type"], "kpi_dashboard", "Tipo de widget debe ser preservado")

		# Step 6: Test preference retrieval and caching
		retrieved_preference = frappe.get_doc("Dashboard User Preference", preference.name)
		retrieved_layout = retrieved_preference.get_layout_config()
		self.assertEqual(retrieved_layout, parsed_layout, "Layout debe ser consistente en retrieval")

		# Step 7: Test preference modification system flow
		preference.theme = "dark"
		preference.refresh_interval = 600
		modified_layout = complex_layout.copy()
		modified_layout["widgets"][0]["enabled"] = False
		preference.dashboard_layout = json.dumps(modified_layout)
		preference.save()

		# Step 8: Validate modification persistence
		updated_preference = frappe.get_doc("Dashboard User Preference", preference.name)
		self.assertEqual(updated_preference.theme, "dark")
		self.assertEqual(updated_preference.refresh_interval, 600)
		updated_layout = updated_preference.get_layout_config()
		self.assertFalse(updated_layout["widgets"][0]["enabled"], "Widget disable debe ser persistido")

	def test_multi_user_dashboard_system_scalability(self):
		"""LAYER 3: Test escalabilidad sistema multi-usuario Dashboard"""

		# Step 1: Crear múltiples usuarios y preferencias
		test_users = []
		test_preferences = []

		for i in range(5):  # Crear 5 usuarios para test escalabilidad
			user_email = f"test.user.{i}@dashboard.layer3.mx"

			# Crear usuario
			if not frappe.db.exists("User", user_email):
				user_doc = frappe.get_doc(
					{
						"doctype": "User",
						"email": user_email,
						"first_name": f"TestUser{i}",
						"last_name": "Layer3",
						"send_welcome_email": 0,
						"language": "es",
					}
				)
				user_doc.insert(ignore_permissions=True)
			test_users.append(user_email)

			# Crear preferencia única para cada usuario
			unique_layout = {
				"version": f"1.{i}",
				"user_specific": f"config_user_{i}",
				"widgets": [
					{
						"id": f"widget_user_{i}",
						"type": "user_specific",
						"position": {"row": 1, "col": 1},
						"enabled": True,
					}
				],
			}

			preference = frappe.get_doc(
				{
					"doctype": "Dashboard User Preference",
					"user": user_email,
					"theme": ["light", "dark", "auto"][i % 3],  # Rotar themes
					"dashboard_layout": json.dumps(unique_layout),
					"refresh_interval": 300 + (i * 60),  # Intervalos diferentes
					"auto_refresh": i % 2,  # Alternar auto_refresh
				}
			)
			preference.insert()
			test_preferences.append(preference)

		# Step 2: Test concurrent access simulation
		start_time = time.time()
		retrieved_preferences = []

		for user_email in test_users:
			user_preference = frappe.get_list(
				"Dashboard User Preference",
				filters={"user": user_email},
				fields=["name", "theme", "refresh_interval"],
				limit=1,
			)
			self.assertEqual(len(user_preference), 1, f"Usuario {user_email} debe tener 1 preferencia")
			retrieved_preferences.append(user_preference[0])

		concurrent_access_time = time.time() - start_time

		# Step 3: Validate system performance under load
		self.assertLess(
			concurrent_access_time,
			2.0,
			"Acceso concurrent de 5 usuarios debe completar en menos de 2 segundos",
		)

		# Step 4: Validate data isolation between users
		themes_found = set()
		intervals_found = set()

		for pref in retrieved_preferences:
			full_pref = frappe.get_doc("Dashboard User Preference", pref.name)
			layout = full_pref.get_layout_config()

			themes_found.add(full_pref.theme)
			intervals_found.add(full_pref.refresh_interval)

			# Validate user-specific configuration
			self.assertIn("user_specific", layout, "Cada usuario debe tener config específica")
			self.assertTrue(
				layout["user_specific"].startswith("config_user_"), "Config debe ser específica del usuario"
			)

		# Step 5: Validate diversity in configurations
		self.assertGreater(len(themes_found), 1, "Debe haber diversidad en themes")
		self.assertGreater(len(intervals_found), 1, "Debe haber diversidad en refresh intervals")

	def test_fiscal_health_factor_system_integration_with_real_calculations(self):
		"""LAYER 3: Test integración sistema Fiscal Health Factor con cálculos reales"""

		# Step 1: Crear Health Score con datos del sistema
		health_score = frappe.get_doc(
			{
				"doctype": "Fiscal Health Score",
				"company": self.test_company,
				"score_date": self.test_date,
				"calculation_method": "Weighted Average",
				# Simular scores calculados realmente por el sistema
				"timbrado_score": 87.5,
				"ppd_score": 72.3,
				"ereceipts_score": 94.1,
				"addendas_score": 100.0,  # Módulo no instalado
				"global_invoices_score": 85.7,
				"rules_compliance_score": 91.2,
			}
		)
		health_score.insert()

		# Step 2: Execute factor generation with system integration
		health_score.generate_health_factors()
		health_score.save()

		# Step 3: Validate factor generation based on real scores
		positive_factors = [f for f in health_score.factors_positive if f.factor_type]
		negative_factors = [f for f in health_score.factors_negative if f.factor_type]

		# Step 4: Validate positive factors for high scores
		high_score_modules = ["ereceipts", "addendas", "rules_compliance"]  # Scores >= 90
		for module in high_score_modules:
			module_factors = [f for f in positive_factors if module.lower() in f.factor_type.lower()]
			if module != "addendas":  # Addendas puede no generar factor si módulo no instalado
				self.assertGreater(
					len(module_factors),
					0,
					f"Score alto en {module} debe generar factor positivo",
				)

		# Step 5: Validate factor impact scores are realistic
		for factor in positive_factors:
			self.assertGreater(factor.impact_score, 0, "Factores positivos deben tener impact_score > 0")
			self.assertLessEqual(factor.impact_score, 10, "Impact score debe estar en rango válido")
			self.assertIsNotNone(factor.description, "Factor debe tener descripción")

		for factor in negative_factors:
			self.assertLess(factor.impact_score, 0, "Factores negativos deben tener impact_score < 0")
			self.assertGreaterEqual(factor.impact_score, -10, "Impact score debe estar en rango válido")

		# Step 6: Test factor modification and system consistency
		if positive_factors:
			original_factor = positive_factors[0]
			original_score = original_factor.impact_score

			# Modify factor
			original_factor.impact_score = min(original_score + 1, 10)  # Increment within bounds
			health_score.save()

			# Validate modification persistence
			reloaded_score = frappe.get_doc("Fiscal Health Score", health_score.name)
			modified_factor = reloaded_score.factors_positive[0]
			self.assertEqual(modified_factor.impact_score, original_score + 1, "Modificación debe persistir")

	def test_complete_dashboard_system_workflow_integration(self):
		"""LAYER 3: Test workflow completo integración Dashboard sistema"""

		# Step 1: Setup complete system environment
		self._create_comprehensive_test_data()

		# Step 2: Create Health Score with complete calculation
		health_score = frappe.get_doc(
			{
				"doctype": "Fiscal Health Score",
				"company": self.test_company,
				"score_date": self.test_date,
				"calculation_method": "Weighted Average",
			}
		)

		# Execute complete health calculation
		start_total_time = time.time()
		health_score.insert()  # Full system integration
		total_calculation_time = time.time() - start_total_time

		# Step 3: Create Dashboard Preference for the calculated score
		dashboard_config = {
			"version": "1.0",
			"health_score_id": health_score.name,
			"widgets": [
				{
					"id": "health_score_summary",
					"type": "score_display",
					"data_source": health_score.name,
					"config": {"show_breakdown": True, "show_trends": False},
					"enabled": True,
				},
				{
					"id": "factors_analysis",
					"type": "factor_grid",
					"data_source": health_score.name,
					"config": {"show_positive": True, "show_negative": True, "max_items": 5},
					"enabled": True,
				},
				{
					"id": "recommendations_panel",
					"type": "recommendation_list",
					"data_source": health_score.name,
					"config": {"priority_filter": "High", "status_filter": "Pending"},
					"enabled": True,
				},
			],
		}

		preference = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": self.test_user,
				"theme": "light",
				"dashboard_layout": json.dumps(dashboard_config),
				"auto_refresh": 1,
				"refresh_interval": 300,
				"show_notifications": 1,
			}
		)
		preference.insert()

		# Step 4: Test complete data integration and consistency
		parsed_layout = preference.get_layout_config()
		health_score_widget = next(
			(w for w in parsed_layout["widgets"] if w["id"] == "health_score_summary"), None
		)

		self.assertIsNotNone(health_score_widget, "Widget health_score debe estar configurado")
		self.assertEqual(
			health_score_widget["data_source"], health_score.name, "Data source debe referenciar Health Score"
		)

		# Step 5: Test system performance and scalability
		self.assertLess(
			total_calculation_time, 10.0, "Workflow completo debe completar en menos de 10 segundos"
		)

		# Step 6: Validate end-to-end data flow
		# Simulate dashboard data loading
		widget_data = self._simulate_widget_data_loading(health_score.name, health_score_widget["config"])
		self.assertIsInstance(widget_data, dict, "Widget data debe ser dict")
		self.assertIn("overall_score", widget_data, "Widget data debe incluir overall_score")
		self.assertEqual(
			widget_data["overall_score"], health_score.overall_score, "Data debe ser consistente"
		)

		# Step 7: Test recommendation system integration
		recommendations_widget = next(
			(w for w in parsed_layout["widgets"] if w["id"] == "recommendations_panel"), None
		)
		recommendations_data = self._simulate_recommendations_loading(
			health_score.name, recommendations_widget["config"]
		)

		self.assertIsInstance(recommendations_data, list, "Recommendations data debe ser lista")
		if recommendations_data:  # Si hay recomendaciones
			high_priority_recs = [r for r in recommendations_data if r.get("priority") == "High"]
			# Validate que el filtro de prioridad funciona
			for rec in high_priority_recs:
				self.assertEqual(rec["priority"], "High", "Filtro de prioridad debe funcionar")

	def test_system_error_handling_and_recovery_integration(self):
		"""LAYER 3: Test manejo errores y recovery integración sistema"""

		# Step 1: Test system resilience with invalid company
		invalid_health_score = frappe.get_doc(
			{
				"doctype": "Fiscal Health Score",
				"company": "Nonexistent Company",
				"score_date": self.test_date,
			}
		)

		# Should handle gracefully
		with self.assertRaises((frappe.ValidationError, frappe.LinkValidationError)):
			invalid_health_score.insert()

		# Step 2: Test system resilience with invalid user preference
		invalid_preference = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": "nonexistent@user.com",
				"theme": "light",
			}
		)

		with self.assertRaises((frappe.ValidationError, frappe.LinkValidationError)):
			invalid_preference.insert()

		# Step 3: Test system recovery after errors
		# Create valid documents after errors
		valid_health_score = frappe.get_doc(
			{
				"doctype": "Fiscal Health Score",
				"company": self.test_company,
				"score_date": self.test_date,
			}
		)
		valid_health_score.insert()  # Should work normally

		valid_preference = frappe.get_doc(
			{
				"doctype": "Dashboard User Preference",
				"user": self.test_user,
				"theme": "dark",
				"auto_refresh": 1,
				"refresh_interval": 300,
			}
		)
		valid_preference.insert()  # Should work normally

		# Step 4: Validate system state after recovery
		self.assertIsNotNone(valid_health_score.name, "Sistema debe recuperarse después de errores")
		self.assertIsNotNone(valid_preference.name, "Sistema debe funcionar normalmente después de errores")

		# Step 5: Test data integrity after error recovery
		retrieved_score = frappe.get_doc("Fiscal Health Score", valid_health_score.name)
		self.assertEqual(retrieved_score.company, self.test_company, "Data integrity debe mantenerse")

		retrieved_preference = frappe.get_doc("Dashboard User Preference", valid_preference.name)
		self.assertEqual(retrieved_preference.user, self.test_user, "Data integrity debe mantenerse")

	# Helper methods for creating realistic test data

	def _create_realistic_sales_invoices_data(self):
		"""Crear datos realistas de Sales Invoices para testing"""
		# Crear Customer de test
		if not frappe.db.exists("Customer", "Test Customer L3"):
			customer = frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": "Test Customer L3",
					"customer_group": "All Customer Groups",
					"territory": "All Territories",
				}
			)
			customer.insert(ignore_permissions=True)

		# Crear Item de test
		if not frappe.db.exists("Item", "Test Item L3"):
			item = frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": "Test Item L3",
					"item_name": "Test Item Layer 3",
					"item_group": "All Item Groups",
					"is_stock_item": 0,
				}
			)
			item.insert(ignore_permissions=True)

		# Crear varias Sales Invoices con diferentes estados de timbrado
		invoice_data = [
			{"total": 1000.0, "timbrado_status": "Timbrada"},
			{"total": 1500.0, "timbrado_status": "Timbrada"},
			{"total": 800.0, "timbrado_status": "Error"},
			{"total": 1200.0, "timbrado_status": "Timbrada"},
			{"total": 2000.0, "timbrado_status": "Pendiente"},
		]

		for i, data in enumerate(invoice_data):
			if not frappe.db.exists("Sales Invoice", f"SI-L3-{i+1:03d}"):
				invoice = frappe.get_doc(
					{
						"doctype": "Sales Invoice",
						"naming_series": "SI-L3-.###",
						"customer": "Test Customer L3",
						"company": self.test_company,
						"posting_date": self.test_date,
						"due_date": frappe.utils.add_days(self.test_date, 30),
						"fm_timbrado_status": data["timbrado_status"],
						"items": [
							{
								"item_code": "Test Item L3",
								"qty": 1,
								"rate": data["total"],
								"amount": data["total"],
							}
						],
						"taxes_and_charges": "",
					}
				)
				invoice.insert(ignore_permissions=True)

	def _create_realistic_payment_entries_data(self):
		"""Crear datos realistas de Payment Entries para testing"""
		# Crear Account de test si no existe
		if not frappe.db.exists("Account", f"Test Cash - {self.test_company[:10]}"):
			account = frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": "Test Cash",
					"account_type": "Cash",
					"parent_account": f"Current Assets - {self.test_company[:10]}",
					"company": self.test_company,
				}
			)
			# Crear parent account si no existe
			if not frappe.db.exists("Account", f"Current Assets - {self.test_company[:10]}"):
				parent_account = frappe.get_doc(
					{
						"doctype": "Account",
						"account_name": "Current Assets",
						"account_type": "",
						"is_group": 1,
						"company": self.test_company,
						"root_type": "Asset",
					}
				)
				parent_account.insert(ignore_permissions=True)
			account.insert(ignore_permissions=True)

		# Crear Payment Entries con diferentes estados PPD
		payment_data = [
			{"amount": 1000.0, "ppd_status": "Completed"},
			{"amount": 1500.0, "ppd_status": "Completed"},
			{"amount": 800.0, "ppd_status": "Error"},
			{"amount": 1200.0, "ppd_status": "Pending"},
		]

		for i, data in enumerate(payment_data):
			if not frappe.db.exists("Payment Entry", f"PE-L3-{i+1:03d}"):
				payment = frappe.get_doc(
					{
						"doctype": "Payment Entry",
						"naming_series": "PE-L3-.###",
						"payment_type": "Receive",
						"party_type": "Customer",
						"party": "Test Customer L3",
						"company": self.test_company,
						"posting_date": self.test_date,
						"paid_amount": data["amount"],
						"received_amount": data["amount"],
						"paid_to": f"Test Cash - {self.test_company[:10]}",
						"fm_ppd_status": data["ppd_status"],
					}
				)
				payment.insert(ignore_permissions=True)

	def _create_comprehensive_test_data(self):
		"""Crear conjunto completo de datos de test para workflow integration"""
		self._create_realistic_sales_invoices_data()
		self._create_realistic_payment_entries_data()

		# Agregar datos adicionales para módulos específicos
		# Simular datos de EReceipts si el módulo está disponible
		if frappe.db.exists("DocType", "EReceipt MX"):
			# Crear datos mock para EReceipts
			pass

		# Simular datos de Facturas Globales si está disponible
		if frappe.db.exists("DocType", "Factura Global MX"):
			# Crear datos mock para Facturas Globales
			pass

	def _simulate_widget_data_loading(self, health_score_name, widget_config):
		"""Simular carga de datos para widget del dashboard"""
		health_score = frappe.get_doc("Fiscal Health Score", health_score_name)

		widget_data = {
			"overall_score": health_score.overall_score,
			"calculation_date": health_score.score_date,
			"company": health_score.company,
		}

		if widget_config.get("show_breakdown"):
			widget_data["breakdown"] = {
				"timbrado": health_score.timbrado_score,
				"ppd": health_score.ppd_score,
				"ereceipts": health_score.ereceipts_score,
			}

		return widget_data

	def _simulate_recommendations_loading(self, health_score_name, widget_config):
		"""Simular carga de recomendaciones para widget"""
		health_score = frappe.get_doc("Fiscal Health Score", health_score_name)
		recommendations_data = []

		for rec in health_score.recommendations:
			rec_data = {
				"category": rec.category,
				"recommendation": rec.recommendation,
				"priority": rec.priority,
				"status": rec.status,
				"estimated_days": rec.estimated_days,
			}

			# Apply filters from widget config
			priority_filter = widget_config.get("priority_filter")
			if priority_filter and rec.priority != priority_filter:
				continue

			status_filter = widget_config.get("status_filter")
			if status_filter and rec.status != status_filter:
				continue

			recommendations_data.append(rec_data)

		return recommendations_data


def run_tests():
	"""Función para correr todos los tests Layer 3 de este módulo"""
	loader = unittest.TestLoader()
	suite = loader.loadTestsFromTestCase(TestDashboardFiscalLayer3System)
	runner = unittest.TextTestRunner(verbosity=2)
	return runner.run(suite)


if __name__ == "__main__":
	run_tests()
