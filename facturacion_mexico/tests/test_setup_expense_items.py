"""
Tests para ensure_cfdi_received_expense_items.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.setup.cfdi_received_expense_item_groups import (
	ensure_cfdi_received_expense_item_groups,
)
from facturacion_mexico.setup.cfdi_received_expense_items import (
	_ITEMS,
	ensure_cfdi_received_expense_items,
)


class TestEnsureCFDIExpenseItems(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_cfdi_received_expense_item_groups()
		cls._cleanup_items()
		ensure_cfdi_received_expense_items()

	@classmethod
	def tearDownClass(cls):
		cls._cleanup_items()
		super().tearDownClass()

	@classmethod
	def _cleanup_items(cls):
		codes = [d["item_code"] for d in _ITEMS]
		for code in codes:
			if frappe.db.exists("Item", code):
				frappe.delete_doc("Item", code, ignore_permissions=True, force=True)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit

	def test_catalogo_tiene_entradas_validas(self):
		# 84 base + 21 overlay operativo = 105
		self.assertEqual(len(_ITEMS), 105)
		codes = [i["item_code"] for i in _ITEMS]
		self.assertEqual(len(codes), len(set(codes)), "item_codes duplicados en _ITEMS")

	def test_todos_los_items_fueron_creados(self):
		for item_def in _ITEMS:
			self.assertTrue(
				frappe.db.exists("Item", item_def["item_code"]),
				f"Item {item_def['item_code']} no fue creado",
			)

	def test_idempotencia(self):
		result = ensure_cfdi_received_expense_items()
		self.assertEqual(result["creados"], 0)
		self.assertEqual(result["existentes"], len(_ITEMS))

	def test_item_nom_001_campos_clave(self):
		item = frappe.get_doc("Item", "GASTO-NOM-001")
		self.assertEqual(item.item_name, "Sueldos y salarios")
		self.assertEqual(item.item_group, "Sueldos y salarios")
		self.assertEqual(item.stock_uom, "MON - Mes")
		self.assertEqual(item.is_stock_item, 0)
		self.assertEqual(item.is_purchase_item, 1)
		self.assertEqual(item.is_sales_item, 0)

	def test_item_opr_003_energia_electrica_uom_kwh(self):
		item = frappe.get_doc("Item", "GASTO-OPR-003")
		self.assertEqual(item.item_name, "Energía eléctrica")
		self.assertEqual(item.item_group, "Energía eléctrica")
		self.assertEqual(item.stock_uom, "KWH - Kilowatt hora")

	def test_item_srv_007_honorarios_pm_uom_e48(self):
		item = frappe.get_doc("Item", "GASTO-SRV-007")
		self.assertEqual(item.item_name, "Honorarios a personas morales residentes nacionales")
		self.assertEqual(item.stock_uom, "E48 - Servicio")
		self.assertEqual(item.is_purchase_item, 1)
		self.assertEqual(item.is_stock_item, 0)

	def test_item_mov_001_combustibles_uom_ltr(self):
		item = frappe.get_doc("Item", "GASTO-MOV-001")
		self.assertEqual(item.item_name, "Combustibles y lubricantes")
		self.assertEqual(item.stock_uom, "LTR - Litro")

	def test_item_arr_001_arrendamiento_uom_mon(self):
		item = frappe.get_doc("Item", "GASTO-ARR-001")
		self.assertEqual(item.item_name, "Arrendamiento a personas físicas residentes nacionales")
		self.assertEqual(item.stock_uom, "MON - Mes")

	def test_item_seg_001_seguros_uom_ann(self):
		item = frappe.get_doc("Item", "GASTO-SEG-001")
		self.assertEqual(item.item_name, "Seguros y fianzas")
		self.assertEqual(item.stock_uom, "ANN - Año")
		self.assertEqual(item.is_purchase_item, 1)

	def test_todos_los_items_son_de_gasto(self):
		for item_def in _ITEMS:
			item = frappe.get_doc("Item", item_def["item_code"])
			self.assertEqual(item.is_stock_item, 0, f"{item_def['item_code']}: is_stock_item debe ser 0")
			self.assertEqual(
				item.is_purchase_item, 1, f"{item_def['item_code']}: is_purchase_item debe ser 1"
			)
			self.assertEqual(item.is_sales_item, 0, f"{item_def['item_code']}: is_sales_item debe ser 0")
