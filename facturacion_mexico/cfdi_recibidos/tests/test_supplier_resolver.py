"""
Tests de SupplierResolver — Fase 2.

unittest.TestCase con contexto Frappe activo.
Crea y limpia registros reales en BD de pruebas.
"""

import unittest

import frappe

from facturacion_mexico.cfdi_recibidos.services.supplier_resolver import resolve_supplier

TEST_RFC = "PROV9001011AA"
TEST_COMPANY = "_Test Company"
TEST_UUID_BASE = "SUPP0001-0001-0001-0001-"


def _get_or_create_supplier(rfc: str) -> str:
	"""Obtiene o crea un Supplier de prueba con el RFC dado."""
	existing = frappe.db.get_value("Supplier", {"tax_id": rfc}, "name")
	if existing:
		return existing

	supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
	if not supplier_group:
		sg = frappe.new_doc("Supplier Group")
		sg.supplier_group_name = "Test Suppliers"
		sg.insert(ignore_permissions=True)
		frappe.db.commit()
		supplier_group = sg.name

	sup = frappe.new_doc("Supplier")
	sup.supplier_name = f"Proveedor Test {rfc}"
	sup.supplier_group = supplier_group
	sup.tax_id = rfc
	sup.insert(ignore_permissions=True)
	frappe.db.commit()
	return sup.name


def _make_cfdi(uuid_suffix: str, supplier_rfc: str, company: str) -> str:
	"""Crea un CFDI Recibido mínimo para pruebas."""
	doc = frappe.new_doc("CFDI Recibido")
	doc.company = company
	doc.uuid = f"{TEST_UUID_BASE}{uuid_suffix}"
	doc.supplier_rfc = supplier_rfc
	doc.supplier_name = "Proveedor Test"
	doc.receiver_rfc = frappe.db.get_value("Company", company, "tax_id") or "RFC000000000"
	doc.status = "Parseado"
	doc.cfdi_type = "I"
	doc.xml_hash = frappe.generate_hash()[:64]
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _cleanup(uuid_suffix: str):
	name = frappe.db.get_value("CFDI Recibido", {"uuid": f"{TEST_UUID_BASE}{uuid_suffix}"}, "name")
	if name:
		frappe.delete_doc("CFDI Recibido", name, force=True)
		frappe.db.commit()


class TestSupplierResolverAuto(unittest.TestCase):
	def setUp(self):
		self.supplier = _get_or_create_supplier(TEST_RFC)
		self.cfdi = _make_cfdi("000A", TEST_RFC, TEST_COMPANY)

	def tearDown(self):
		_cleanup("000A")

	def test_resuelve_por_rfc(self):
		result = resolve_supplier(self.cfdi)
		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["supplier"], self.supplier)

	def test_asigna_supplier_al_doc(self):
		resolve_supplier(self.cfdi)
		supplier_en_doc = frappe.db.get_value("CFDI Recibido", self.cfdi, "supplier")
		self.assertEqual(supplier_en_doc, self.supplier)

	def test_status_avanza(self):
		resolve_supplier(self.cfdi)
		status = frappe.db.get_value("CFDI Recibido", self.cfdi, "status")
		self.assertNotEqual(status, "Falta proveedor")


class TestSupplierResolverSinMatch(unittest.TestCase):
	def setUp(self):
		self.cfdi = _make_cfdi("000B", "RFC_SIN_MATCH_999", TEST_COMPANY)

	def tearDown(self):
		_cleanup("000B")

	def test_status_falta_proveedor(self):
		result = resolve_supplier(self.cfdi)
		self.assertEqual(result["status"], "falta_proveedor")
		self.assertIsNone(result["supplier"])

	def test_doc_queda_falta_proveedor(self):
		resolve_supplier(self.cfdi)
		status = frappe.db.get_value("CFDI Recibido", self.cfdi, "status")
		self.assertEqual(status, "Falta proveedor")


class TestSupplierResolverManual(unittest.TestCase):
	def setUp(self):
		self.supplier = _get_or_create_supplier(TEST_RFC)
		# CFDI con RFC distinto al del supplier — solo vinculación manual puede resolverlo
		self.cfdi = _make_cfdi("000C", "RFC_DIFERENTE_ABC", TEST_COMPANY)

	def tearDown(self):
		_cleanup("000C")

	def test_vinculacion_manual_aunque_rfc_no_coincida(self):
		result = resolve_supplier(self.cfdi, supplier_override=self.supplier)
		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["supplier"], self.supplier)

	def test_supplier_asignado_manualmente(self):
		resolve_supplier(self.cfdi, supplier_override=self.supplier)
		supplier_en_doc = frappe.db.get_value("CFDI Recibido", self.cfdi, "supplier")
		self.assertEqual(supplier_en_doc, self.supplier)
