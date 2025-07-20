"""
Base Test Class for Addendas Module - Sprint 3
Framework de testing 4-Layer: Unit, Business Logic, Integration, Performance
"""

import json
import time
from typing import Any, Optional

import frappe
from frappe.test_runner import make_test_records
from frappe.tests.utils import FrappeTestCase


class AddendaTestBase(FrappeTestCase):
	"""Clase base para tests del módulo de addendas."""

	@classmethod
	def setUpClass(cls):
		"""Configuración inicial para todos los tests."""
		super().setUpClass()
		cls.setup_test_data()

	@classmethod
	def setup_test_data(cls):
		"""Configurar datos de prueba necesarios."""
		# Crear registros de prueba básicos usando make_test_records
		cls.setup_test_dependencies()
		cls.create_test_customer()
		cls.create_test_items()
		cls.create_test_addenda_types()

	@classmethod
	def setup_test_dependencies(cls):
		"""Configurar dependencias necesarias para los tests."""
		try:
			# Crear registros de prueba estándar de ERPNext
			make_test_records("Territory")
			make_test_records("Customer Group")
			make_test_records("Item Group")
			make_test_records("UOM")
			make_test_records("Account")
			make_test_records("Company")
		except Exception:
			# Si falla make_test_records, crear manualmente los registros mínimos
			cls.create_minimal_test_fixtures()

	@classmethod
	def create_minimal_test_fixtures(cls):
		"""Crear fixtures mínimos necesarios."""
		# Crear Territory de prueba
		if not frappe.db.exists("Territory", "_Test Territory"):
			territory = frappe.get_doc(
				{
					"doctype": "Territory",
					"territory_name": "_Test Territory",
					"is_group": 0,
					"parent_territory": "All Territories",
				}
			)
			territory.insert(ignore_permissions=True)

		# Crear Customer Group de prueba
		if not frappe.db.exists("Customer Group", "Commercial"):
			customer_group = frappe.get_doc(
				{
					"doctype": "Customer Group",
					"customer_group_name": "Commercial",
					"is_group": 0,
					"parent_customer_group": "All Customer Groups",
				}
			)
			customer_group.insert(ignore_permissions=True)

		# Crear Item Groups de prueba
		for group_name in ["Products", "Services"]:
			if not frappe.db.exists("Item Group", group_name):
				item_group = frappe.get_doc(
					{
						"doctype": "Item Group",
						"item_group_name": group_name,
						"is_group": 0,
						"parent_item_group": "All Item Groups",
					}
				)
				item_group.insert(ignore_permissions=True)

		# Crear UOM de prueba
		if not frappe.db.exists("UOM", "Nos"):
			uom = frappe.get_doc({"doctype": "UOM", "uom_name": "Nos", "must_be_whole_number": 1})
			uom.insert(ignore_permissions=True)

	@classmethod
	def create_test_customer(cls):
		"""Crear cliente de prueba."""
		customer_name = "Test Customer Addenda"
		if not frappe.db.exists("Customer", customer_name):
			# Verificar que territory existe, sino usar uno disponible
			territory = "_Test Territory"
			if not frappe.db.exists("Territory", territory):
				# Buscar un territory existente o usar All Territories
				existing_territories = frappe.get_all("Territory", filters={"is_group": 0}, limit=1)
				territory = existing_territories[0].name if existing_territories else "All Territories"

			# Verificar customer group
			customer_group = "Commercial"
			if not frappe.db.exists("Customer Group", customer_group):
				existing_groups = frappe.get_all("Customer Group", filters={"is_group": 0}, limit=1)
				customer_group = existing_groups[0].name if existing_groups else "All Customer Groups"

			customer = frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": customer_name,
					"customer_type": "Company",
					"customer_group": customer_group,
					"territory": territory,
					"tax_id": "TEST123456789",
				}
			)
			customer.insert(ignore_permissions=True)
		cls.test_customer = customer_name

	@classmethod
	def create_test_items(cls):
		"""Crear items de prueba."""
		# Verificar Item Groups disponibles
		products_group = "Products"
		if not frappe.db.exists("Item Group", products_group):
			existing_groups = frappe.get_all("Item Group", filters={"is_group": 0}, limit=1)
			products_group = existing_groups[0].name if existing_groups else "All Item Groups"

		services_group = "Services"
		if not frappe.db.exists("Item Group", services_group):
			services_group = products_group  # Usar el mismo si Services no existe

		# Verificar UOM
		stock_uom = "Nos"
		if not frappe.db.exists("UOM", stock_uom):
			existing_uoms = frappe.get_all("UOM", limit=1)
			stock_uom = existing_uoms[0].name if existing_uoms else "Each"

		items = [
			{
				"item_code": "TEST-ITEM-001",
				"item_name": "Test Item for Addenda",
				"item_group": products_group,
				"stock_uom": stock_uom,
				"is_sales_item": 1,
				"is_purchase_item": 1,
			},
			{
				"item_code": "TEST-ITEM-002",
				"item_name": "Test Service Item",
				"item_group": services_group,
				"stock_uom": stock_uom,
				"is_sales_item": 1,
				"is_purchase_item": 0,
			},
		]

		cls.test_items = []
		for item_data in items:
			if not frappe.db.exists("Item", item_data["item_code"]):
				item = frappe.get_doc({"doctype": "Item", **item_data})
				item.insert(ignore_permissions=True)
			cls.test_items.append(item_data["item_code"])

	@classmethod
	def create_test_addenda_types(cls):
		"""Crear tipos de addenda de prueba."""
		# Usar los tipos de addenda que ya existen de los fixtures
		# En lugar de crear nuevos, reutilizar Generic y Liverpool
		if frappe.db.exists("Addenda Type", "Generic"):
			cls.test_addenda_types = ["Generic", "Liverpool"]
		else:
			# Solo si no existen, crear tipos básicos
			generic_type = {
				"doctype": "Addenda Type",
				"description": "Tipo genérico para pruebas",
				"version": "1.0",
				"namespace": "http://test.addenda.mx/generic",
				"is_active": 1,
				"requires_product_mapping": 0,
			}

			try:
				addenda_type = frappe.get_doc(generic_type)
				addenda_type.insert(ignore_permissions=True)
				generic_name = addenda_type.name
			except Exception:
				generic_name = "Generic"

			liverpool_type = {
				"doctype": "Addenda Type",
				"description": "Tipo Liverpool para pruebas",
				"version": "2.1",
				"namespace": "http://test.addenda.mx/liverpool",
				"is_active": 1,
				"requires_product_mapping": 1,
			}

			try:
				addenda_type = frappe.get_doc(liverpool_type)
				addenda_type.insert(ignore_permissions=True)
				liverpool_name = addenda_type.name
			except Exception:
				liverpool_name = "Liverpool"

			cls.test_addenda_types = [generic_name, liverpool_name]

	def create_test_sales_invoice(self, customer: str | None = None) -> str:
		"""Crear factura de prueba."""
		customer = customer or self.test_customer

		invoice = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": customer,
				"posting_date": frappe.utils.today(),
				"due_date": frappe.utils.add_days(frappe.utils.today(), 30),
				"items": [
					{
						"item_code": self.test_items[0],
						"qty": 1,
						"rate": 100.0,
					}
				],
				"taxes_and_charges": "",
				"cfdi_use": "G01",  # Uso CFDI requerido para México
			}
		)
		invoice.insert(ignore_permissions=True)
		return invoice.name

	def create_test_addenda_configuration(
		self, customer: str | None = None, addenda_type: str | None = None
	) -> str:
		"""Crear configuración de addenda de prueba."""
		customer = customer or self.test_customer
		addenda_type = addenda_type or self.test_addenda_types[0]

		config = frappe.get_doc(
			{
				"doctype": "Addenda Configuration",
				"customer": customer,
				"addenda_type": addenda_type,
				"is_active": 1,
				"priority": 1,
				"auto_apply": 1,
				"validation_level": "Warning",
				"effective_date": frappe.utils.today(),
			}
		)
		config.insert(ignore_permissions=True)
		return config.name

	def create_test_addenda_template(self, addenda_type: str | None = None) -> str:
		"""Crear template de addenda de prueba."""
		addenda_type = addenda_type or self.test_addenda_types[0]

		template_xml = """<?xml version="1.0" encoding="UTF-8"?>
<addenda>
	<informacion>
		<folio>{{ cfdi_uuid }}</folio>
		<fecha>{{ cfdi_fecha }}</fecha>
		<total>{{ cfdi_total }}</total>
	</informacion>
	<proveedor>
		<rfc>{{ emisor_rfc }}</rfc>
		<nombre>{{ emisor_nombre }}</nombre>
	</proveedor>
</addenda>"""

		template = frappe.get_doc(
			{
				"doctype": "Addenda Template",
				"addenda_type": addenda_type,
				"template_name": "Test Template",
				"version": "1.0",
				"description": "Template de prueba",
				"template_xml": template_xml,
				"is_default": 1,
			}
		)
		template.insert(ignore_permissions=True)
		return template.name

	def assert_xml_valid(self, xml_content: str, message: str = "XML should be valid"):
		"""Validar que el XML sea válido."""
		try:
			from lxml import etree

			etree.fromstring(xml_content.encode("utf-8"))
		except Exception as e:
			self.fail(f"{message}: {e}")

	def assert_xml_contains(self, xml_content: str, xpath: str, expected_value: str | None = None):
		"""Validar que el XML contenga un xpath específico."""
		try:
			from lxml import etree

			root = etree.fromstring(xml_content.encode("utf-8"))
			elements = root.xpath(xpath)

			self.assertTrue(len(elements) > 0, f"XPath '{xpath}' not found in XML")

			if expected_value is not None:
				element_text = elements[0].text if hasattr(elements[0], "text") else str(elements[0])
				self.assertEqual(element_text, expected_value, f"XPath '{xpath}' value mismatch")

		except Exception as e:
			self.fail(f"Error validating XML with XPath '{xpath}': {e}")

	def measure_execution_time(self, func, *args, **kwargs) -> tuple[Any, float]:
		"""Medir tiempo de ejecución de una función."""
		start_time = time.time()
		result = func(*args, **kwargs)
		execution_time = time.time() - start_time
		return result, execution_time

	def tearDown(self):
		"""Limpieza después de cada test."""
		super().tearDown()
		# Limpiar datos de prueba creados durante el test
		self.cleanup_test_data()

	def cleanup_test_data(self):
		"""Limpiar datos de prueba."""
		# Limpiar configuraciones de addenda de prueba
		configs = frappe.get_all(
			"Addenda Configuration", filters={"customer": ["like", "%Test%"]}, pluck="name"
		)
		for config in configs:
			try:
				frappe.delete_doc("Addenda Configuration", config, force=True, ignore_permissions=True)
			except Exception:
				pass

		# Limpiar templates de prueba
		templates = frappe.get_all(
			"Addenda Template", filters={"template_name": ["like", "%Test%"]}, pluck="name"
		)
		for template in templates:
			try:
				frappe.delete_doc("Addenda Template", template, force=True, ignore_permissions=True)
			except Exception:
				pass

		# Limpiar facturas de prueba
		invoices = frappe.get_all("Sales Invoice", filters={"customer": ["like", "%Test%"]}, pluck="name")
		for invoice in invoices:
			try:
				frappe.delete_doc("Sales Invoice", invoice, force=True, ignore_permissions=True)
			except Exception:
				pass
