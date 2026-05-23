"""
Tests de ConceptClassifier y CFDI Concepto Mapping — Fase 2.

unittest.TestCase con contexto Frappe activo.
"""

import unittest

import frappe

from facturacion_mexico.cfdi_recibidos.services.concept_classifier import (
	classify_concepts,
	get_rule_for_concept,
)

TEST_COMPANY = "_Test Company"
TEST_RFC = "CNA201211FM9"
TEST_SAT_KEY = "43231500"
UUID_BASE = "CLSF0001-0001-0001-0001-"


def _make_cfdi(uuid_suffix: str, conceptos: list | None = None) -> str:
	doc = frappe.new_doc("CFDI Recibido")
	doc.company = TEST_COMPANY
	doc.uuid = f"{UUID_BASE}{uuid_suffix}"
	doc.supplier_rfc = TEST_RFC
	doc.supplier_name = "Test Supplier"
	doc.receiver_rfc = frappe.db.get_value("Company", TEST_COMPANY, "tax_id") or "RFC000000000"
	doc.status = "Parseado"
	doc.cfdi_type = "I"
	doc.xml_hash = frappe.generate_hash()[:64]
	for c in conceptos or []:
		doc.append("conceptos", c)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _make_rule(supplier_rfc: str, sat_key: str, target_type: str, **kwargs) -> str:
	doc = frappe.new_doc("CFDI Concepto Mapping")
	doc.supplier_rfc = supplier_rfc
	doc.sat_product_key = sat_key
	doc.target_type = target_type
	doc.is_active = 1
	for k, v in kwargs.items():
		setattr(doc, k, v)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _cleanup_cfdi(uuid_suffix: str):
	name = frappe.db.get_value("CFDI Recibido", {"uuid": f"{UUID_BASE}{uuid_suffix}"}, "name")
	if name:
		frappe.delete_doc("CFDI Recibido", name, force=True)
		frappe.db.commit()


def _cleanup_rules(supplier_rfc: str, sat_key: str = ""):
	filters = {"supplier_rfc": supplier_rfc}
	if sat_key:
		filters["sat_product_key"] = sat_key
	names = frappe.db.get_all("CFDI Concepto Mapping", filters=filters, pluck="name")
	for name in names:
		frappe.delete_doc("CFDI Concepto Mapping", name, force=True)
	if names:
		frappe.db.commit()


def _get_expense_account() -> str:
	"""Devuelve una cuenta de gasto válida en el site de pruebas."""
	for filters in [
		{"account_type": "Expense Account", "company": TEST_COMPANY, "is_group": 0},
		{"root_type": "Expense", "company": TEST_COMPANY, "is_group": 0},
		{"root_type": "Expense", "is_group": 0},
	]:
		account = frappe.db.get_value("Account", filters, "name")
		if account:
			return account
	frappe.throw("No se encontró ninguna cuenta de tipo Expense en el site de pruebas")


class TestMappingValidation(unittest.TestCase):
	def test_item_requiere_target_item(self):
		doc = frappe.new_doc("CFDI Concepto Mapping")
		doc.supplier_rfc = "TEST000000AAA"
		doc.target_type = "Item"
		with self.assertRaises(Exception):
			doc.insert(ignore_permissions=True)

	def test_expense_account_requiere_target_account(self):
		doc = frappe.new_doc("CFDI Concepto Mapping")
		doc.supplier_rfc = "TEST000000AAA"
		doc.target_type = "ExpenseAccount"
		with self.assertRaises(Exception):
			doc.insert(ignore_permissions=True)

	def test_child_no_tiene_mapped_fields(self):
		meta = frappe.get_meta("CFDI Recibido Concepto")
		field_names = [f.fieldname for f in meta.fields]
		self.assertNotIn("mapped_type", field_names)
		self.assertNotIn("mapped_item", field_names)
		self.assertNotIn("mapped_account", field_names)
		self.assertNotIn("mapped_cost_center", field_names)
		self.assertNotIn("classification_status", field_names)


class TestMatchingExacto(unittest.TestCase):
	def setUp(self):
		self.account = _get_expense_account()
		self.rule = _make_rule(
			TEST_RFC,
			TEST_SAT_KEY,
			"ExpenseAccount",
			target_account=self.account,
		)
		self.cfdi = _make_cfdi(
			"001A",
			[
				{
					"sat_product_key": TEST_SAT_KEY,
					"description": "Servicio",
					"quantity": 1,
					"unit_key": "E48",
					"unit": "Servicio",
					"unit_price": 100,
					"amount": 100,
					"discount": 0,
					"tax_object": "02",
					"taxes_json": "{}",
				}
			],
		)

	def tearDown(self):
		_cleanup_cfdi("001A")
		_cleanup_rules(TEST_RFC, TEST_SAT_KEY)

	def test_matching_exacto(self):
		rule = get_rule_for_concept(TEST_COMPANY, TEST_RFC, TEST_SAT_KEY)
		self.assertIsNotNone(rule)

	def test_classify_todos_listo(self):
		result = classify_concepts(self.cfdi)
		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["matched"], 1)
		self.assertEqual(result["unmatched"], 0)

	def test_status_doc_listo(self):
		classify_concepts(self.cfdi)
		status = frappe.db.get_value("CFDI Recibido", self.cfdi, "status")
		self.assertEqual(status, "Listo")


class TestMatchingFallback(unittest.TestCase):
	def setUp(self):
		self.account = _get_expense_account()
		# Regla con sat_product_key vacío — aplica a cualquier clave del proveedor
		self.rule = _make_rule(TEST_RFC, "", "ExpenseAccount", target_account=self.account)
		self.cfdi = _make_cfdi(
			"001B",
			[
				{
					"sat_product_key": "99999999",
					"description": "Otro servicio",
					"quantity": 1,
					"unit_key": "E48",
					"unit": "S",
					"unit_price": 50,
					"amount": 50,
					"discount": 0,
					"tax_object": "02",
					"taxes_json": "{}",
				}
			],
		)

	def tearDown(self):
		_cleanup_cfdi("001B")
		_cleanup_rules(TEST_RFC, "")

	def test_fallback_proveedor_sin_sat_key(self):
		rule = get_rule_for_concept(TEST_COMPANY, TEST_RFC, "99999999")
		self.assertIsNotNone(rule)

	def test_classify_listo_via_fallback(self):
		result = classify_concepts(self.cfdi)
		self.assertEqual(result["status"], "ok")


class TestSinMatch(unittest.TestCase):
	def setUp(self):
		self.cfdi = _make_cfdi(
			"001C",
			[
				{
					"sat_product_key": "SINMATCH00",
					"description": "Sin regla",
					"quantity": 1,
					"unit_key": "E48",
					"unit": "S",
					"unit_price": 10,
					"amount": 10,
					"discount": 0,
					"tax_object": "02",
					"taxes_json": "{}",
				}
			],
		)

	def tearDown(self):
		_cleanup_cfdi("001C")

	def test_sin_match_retorna_falta_clasif(self):
		result = classify_concepts(self.cfdi)
		self.assertEqual(result["status"], "falta_clasif")
		self.assertEqual(result["unmatched"], 1)

	def test_status_doc_falta_clasif(self):
		classify_concepts(self.cfdi)
		status = frappe.db.get_value("CFDI Recibido", self.cfdi, "status")
		self.assertEqual(status, "Falta clasif.")

	def test_child_no_recibe_clasificacion(self):
		classify_concepts(self.cfdi)
		doc = frappe.get_doc("CFDI Recibido", self.cfdi)
		for c in doc.conceptos:
			self.assertFalse(hasattr(c, "mapped_type"))
			self.assertFalse(hasattr(c, "mapped_item"))
