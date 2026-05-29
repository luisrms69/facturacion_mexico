import unittest

import frappe

from facturacion_mexico.cfdi_recibidos.services.item_validator import validate_expense_item

_IG_NAME = "_BloqueE2 TestIG"
_ITEM_SAT = "_BloqueE2-ITEM-SAT"
_ITEM_NO_SAT = "_BloqueE2-ITEM-NOSAT"
_ITEM_EMPTY_UOM = "_BloqueE2-ITEM-EMPTY"


def _ensure_gastos_group() -> str:
	if not frappe.db.exists("Item Group", "Gastos"):
		root = frappe.db.get_value("Item Group", {"parent_item_group": ""}, "name") or "All Item Groups"
		g = frappe.new_doc("Item Group")
		g.item_group_name = "Gastos"
		g.parent_item_group = root
		g.insert(ignore_permissions=True)
		frappe.db.commit()
	return "Gastos"


def _ensure_item_group() -> str:
	_ensure_gastos_group()
	if frappe.db.exists("Item Group", _IG_NAME):
		return _IG_NAME
	doc = frappe.new_doc("Item Group")
	doc.item_group_name = _IG_NAME
	doc.parent_item_group = "Gastos"
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return _IG_NAME


def _create_item(item_code: str, stock_uom: str) -> str:
	if frappe.db.exists("Item", item_code):
		frappe.db.set_value("Item", item_code, "stock_uom", stock_uom)
		frappe.db.commit()
		return item_code
	ig = _ensure_item_group()
	doc = frappe.new_doc("Item")
	doc.item_code = item_code
	doc.item_name = item_code
	doc.item_group = ig
	doc.is_stock_item = 0
	doc.is_purchase_item = 1
	doc.is_sales_item = 0
	doc.stock_uom = stock_uom
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return item_code


def _delete_item(item_code: str):
	if frappe.db.exists("Item", item_code):
		frappe.db.delete("Item", {"name": item_code})
		frappe.db.commit()


class TestItemValidatorUOM(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_create_item(_ITEM_SAT, "H87 - Pieza")
		_create_item(_ITEM_NO_SAT, "Nos")

	@classmethod
	def tearDownClass(cls):
		_delete_item(_ITEM_SAT)
		_delete_item(_ITEM_NO_SAT)
		_delete_item(_ITEM_EMPTY_UOM)
		super().tearDownClass()

	def test_item_uom_no_sat_retorna_false(self):
		ok, msg = validate_expense_item(_ITEM_NO_SAT)
		self.assertFalse(ok)
		self.assertIn("SAT", msg)
		self.assertIn("Nos", msg)

	def test_item_uom_sat_retorna_true(self):
		ok, msg = validate_expense_item(_ITEM_SAT)
		self.assertTrue(ok)
		self.assertEqual(msg, "")

	def test_item_uom_vacio_retorna_false(self):
		frappe.db.set_value("Item", _ITEM_SAT, "stock_uom", "")
		frappe.db.commit()
		try:
			ok, msg = validate_expense_item(_ITEM_SAT)
			self.assertFalse(ok)
			self.assertIn("SAT", msg)
		finally:
			frappe.db.set_value("Item", _ITEM_SAT, "stock_uom", "H87 - Pieza")
			frappe.db.commit()


class TestGetExpenseItemsUOMFilter(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_create_item(_ITEM_SAT, "H87 - Pieza")
		_create_item(_ITEM_NO_SAT, "Nos")

	@classmethod
	def tearDownClass(cls):
		_delete_item(_ITEM_SAT)
		_delete_item(_ITEM_NO_SAT)
		super().tearDownClass()

	def _search(self, txt="BloqueE2") -> list[str]:
		from facturacion_mexico.cfdi_recibidos.queries import get_expense_items

		rows = get_expense_items(
			doctype="Item",
			txt=txt,
			searchfield="name",
			start=0,
			page_len=50,
			filters={},
		)
		return [r[0] for r in rows]

	def test_excluye_item_uom_no_sat(self):
		results = self._search()
		self.assertNotIn(_ITEM_NO_SAT, results)

	def test_incluye_item_uom_sat(self):
		results = self._search()
		self.assertIn(_ITEM_SAT, results)

	def test_ambos_presentes_solo_sat_aparece(self):
		results = self._search()
		self.assertIn(_ITEM_SAT, results)
		self.assertNotIn(_ITEM_NO_SAT, results)
