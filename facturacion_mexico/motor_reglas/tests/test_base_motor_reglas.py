"""
Base Test Class - Motor de Reglas
Clase base para tests del motor de reglas fiscales
"""

import unittest
from unittest.mock import MagicMock, patch

import frappe

# from frappe.utils import add_days, today  # Removed unused imports


class MotorReglasTestBase(unittest.TestCase):
	"""Clase base para tests del motor de reglas."""

	@classmethod
	def setUpClass(cls):
		"""Setup inicial para la clase de tests."""
		cls.test_company = "Test Company Motor Reglas"
		cls.test_rules = []
		cls.test_documents = []

		# Crear empresa de prueba
		try:
			if not frappe.db.exists("Company", cls.test_company):
				company_doc = frappe.get_doc(
					{
						"doctype": "Company",
						"company_name": cls.test_company,
						"default_currency": "MXN",
						"country": "Mexico",
					}
				)
				company_doc.insert(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(f"Error creating test company: {e}")

	def setUp(self):
		"""Setup para cada test individual."""
		frappe.set_user("Administrator")
		self.test_rules = []
		self.test_documents = []

	def tearDown(self):
		"""Cleanup después de cada test."""
		try:
			# Limpiar reglas de prueba
			for rule_name in self.test_rules:
				try:
					if frappe.db.exists("Fiscal Validation Rule", rule_name):
						frappe.delete_doc(
							"Fiscal Validation Rule", rule_name, force=True, ignore_permissions=True
						)
				except Exception:
					# Ignorar errores de limpieza individual
					pass

			# Limpiar documentos de prueba
			for doctype, doc_name in self.test_documents:
				try:
					if frappe.db.exists(doctype, doc_name):
						frappe.delete_doc(doctype, doc_name, force=True, ignore_permissions=True)
				except Exception:
					# Ignorar errores de limpieza individual
					pass

			# Limpiar logs de ejecución
			self.cleanup_execution_logs()

		except Exception as e:
			frappe.log_error(f"Error en cleanup de tests: {e}")

	@classmethod
	def tearDownClass(cls):
		"""Cleanup final de la clase."""
		try:
			# Limpiar empresa de prueba si no está en uso
			companies_in_use = frappe.db.count("Fiscal Validation Rule", {"company": cls.test_company})
			if companies_in_use == 0:
				if frappe.db.exists("Company", cls.test_company):
					frappe.delete_doc("Company", cls.test_company, force=True, ignore_permissions=True)
		except Exception:
			# Ignorar errores al limpiar empresa de test
			pass

	def create_test_rule(self, rule_config):
		"""Crear regla de prueba."""
		default_config = {
			"doctype": "Fiscal Validation Rule",
			"rule_name": "Test Rule",
			"rule_code": "TEST_RULE_001",
			"description": "Test rule for unit testing",
			"rule_type": "Validation",
			"apply_to_doctype": "Sales Invoice",
			"is_active": 1,
			"priority": 50,
			"severity": "Error",
			"error_message": "Test validation error",
			"conditions": [
				{
					"condition_type": "Field",
					"field_name": "grand_total",
					"operator": "greater_than",
					"value": "1000",
					"value_type": "Static",
				}
			],
			"actions": [
				{
					"action_type": "Set Field",
					"target_field": "fm_validation_status",
					"value": "Validated",
					"value_type": "Static",
				}
			],
		}

		# Merge configuración
		default_config.update(rule_config)

		# Crear documento
		rule_doc = frappe.get_doc(default_config)
		rule_doc.insert(ignore_permissions=True)

		# Agregar a lista de cleanup
		self.test_rules.append(rule_doc.name)

		return rule_doc

	def create_test_condition(self, rule_doc, condition_config):
		"""Crear condición de prueba para una regla."""
		default_condition = {
			"condition_type": "Field",
			"field_name": "grand_total",
			"operator": "greater_than",
			"value": "1000",
			"value_type": "Static",
		}

		default_condition.update(condition_config)
		rule_doc.append("conditions", default_condition)

		return rule_doc

	def create_test_action(self, rule_doc, action_config):
		"""Crear acción de prueba para una regla."""
		default_action = {
			"action_type": "Show Error",
			"action_value": "Test error message",
			"continue_on_error": 0,
			"log_action": 1,
		}

		default_action.update(action_config)
		rule_doc.append("actions", default_action)

		return rule_doc

	def create_test_item(self, item_config=None):
		"""Crear Item de prueba."""
		default_config = {
			"doctype": "Item",
			"item_code": "Test Item",
			"item_name": "Test Item Motor Reglas",
			"item_group": "All Item Groups",
			"stock_uom": "Nos",
			"is_stock_item": 0,
			"maintain_stock": 0,
		}

		if item_config:
			default_config.update(item_config)

		# Verificar si ya existe
		if frappe.db.exists("Item", default_config["item_code"]):
			return frappe.get_doc("Item", default_config["item_code"])

		try:
			item_doc = frappe.get_doc(default_config)
			item_doc.insert(ignore_permissions=True)

			# Agregar a lista de cleanup
			self.test_documents.append(("Item", item_doc.name))

			return item_doc
		except Exception:
			# Si falla, intentar obtener el existente
			if frappe.db.exists("Item", default_config["item_code"]):
				return frappe.get_doc("Item", default_config["item_code"])
			raise

	def create_test_sales_invoice(self, invoice_config=None):
		"""Crear Sales Invoice de prueba."""
		# Crear Item necesario primero
		self.create_test_item()

		default_config = {
			"doctype": "Sales Invoice",
			"customer": "Test Customer",
			"company": self.test_company,
			"currency": "MXN",
			"cfdi_use": "G03",  # Campo obligatorio para México - Gastos en General
			"items": [{"item_code": "Test Item", "qty": 1, "rate": 1000, "amount": 1000}],
		}

		if invoice_config:
			default_config.update(invoice_config)

		# Crear documento
		with patch("frappe.db.get_single_value") as mock_single_value:
			mock_single_value.return_value = 0

			invoice_doc = frappe.get_doc(default_config)
			invoice_doc.insert(ignore_permissions=True)

			# Agregar a lista de cleanup
			self.test_documents.append(("Sales Invoice", invoice_doc.name))

			return invoice_doc

	def create_test_customer(self, customer_config=None):
		"""Crear Customer de prueba."""
		default_config = {
			"doctype": "Customer",
			"customer_name": "Test Customer Motor Reglas",
			"customer_type": "Individual",
		}

		if customer_config:
			default_config.update(customer_config)

		# Crear documento
		customer_doc = frappe.get_doc(default_config)
		customer_doc.insert(ignore_permissions=True)

		# Agregar a lista de cleanup
		self.test_documents.append(("Customer", customer_doc.name))

		return customer_doc

	def cleanup_execution_logs(self):
		"""Limpiar logs de ejecución de tests."""
		try:
			# Limpiar logs que contengan "test" en el nombre
			test_logs = frappe.get_all(
				"Rule Execution Log",
				filters=[["rule", "like", "%test%"], ["OR", ["document_name", "like", "%test%"]]],
				pluck="name",
			)

			for log_name in test_logs:
				try:
					frappe.delete_doc("Rule Execution Log", log_name, force=True, ignore_permissions=True)
				except Exception:
					# Ignorar errores de limpieza individual
					pass
		except Exception:
			pass

	def mock_settings(self):
		"""Crear mock settings para tests."""
		settings_mock = MagicMock()
		settings_mock.enable_global_invoices = 1
		settings_mock.global_invoice_serie = "FG-TEST"

		return settings_mock

	def assert_validation_passed(self, result):
		"""Assert que validación pasó exitosamente."""
		self.assertTrue(result.get("success"), "Validation should pass")
		self.assertTrue(result.get("executed"), "Rules should be executed")

	def assert_validation_failed(self, result, expected_error=None):
		"""Assert que validación falló."""
		self.assertFalse(result.get("success"), "Validation should fail")
		if expected_error:
			self.assertIn(
				expected_error, str(result.get("error", "")), "Error message should contain expected text"
			)

	def get_rule_execution_stats(self, rule_name):
		"""Obtener estadísticas de ejecución de regla."""
		stats = frappe.db.sql(
			"""
			SELECT
				COUNT(*) as total_executions,
				AVG(execution_time) as avg_execution_time,
				SUM(CASE WHEN result = 'Success' THEN 1 ELSE 0 END) as successful,
				SUM(CASE WHEN result = 'Failed' THEN 1 ELSE 0 END) as failed
			FROM `tabRule Execution Log`
			WHERE rule = %s
		""",
			rule_name,
			as_dict=True,
		)[0]

		return stats

	def create_complex_test_rule(self):
		"""Crear regla compleja de prueba con múltiples condiciones y acciones."""
		rule_doc = self.create_test_rule(
			{
				"rule_name": "Complex Test Rule",
				"rule_code": "COMPLEX_TEST_001",
				"description": "Complex rule for advanced testing",
				"rule_type": "Validation",
				"apply_to_doctype": "Sales Invoice",
				"severity": "Warning",
			}
		)

		# Múltiples condiciones con operadores lógicos
		self.create_test_condition(
			rule_doc,
			{
				"condition_type": "Field",
				"field_name": "grand_total",
				"operator": "greater_than",
				"value": "5000",
				"value_type": "Static",
				"logical_operator": "AND",
			},
		)

		self.create_test_condition(
			rule_doc,
			{
				"condition_type": "Field",
				"field_name": "customer_name",
				"operator": "contains",
				"value": "PUBLICO",
				"value_type": "Static",
				"logical_operator": "OR",
			},
		)

		self.create_test_condition(
			rule_doc,
			{
				"condition_type": "Field",
				"field_name": "status",
				"operator": "equals",
				"value": "Draft",
				"value_type": "Static",
			},
		)

		# Múltiples acciones
		self.create_test_action(
			rule_doc,
			{"action_type": "Show Warning", "action_value": "Factura de alto valor para cliente público"},
		)

		self.create_test_action(
			rule_doc,
			{
				"action_type": "Set Field",
				"target_field": "remarks",
				"action_value": "Revisión requerida para cliente público",
			},
		)

		rule_doc.save()
		return rule_doc
