import unittest

import frappe

from facturacion_mexico.facturacion_fiscal.services.invoice_uom_validator import (
	validate_invoice_items_uom,
)


class _FakeItem:
	def __init__(self, idx: int, item_code: str, item_name: str, uom: str):
		self.idx = idx
		self.item_code = item_code
		self.item_name = item_name
		self.uom = uom


class TestValidateInvoiceItemsUOM(unittest.TestCase):
	def test_uom_sat_unica_linea_ok(self):
		items = [_FakeItem(1, "SRV-001", "Servicio de limpieza", "E48 - Servicio")]
		validate_invoice_items_uom(items)  # no debe lanzar

	def test_multiples_uoms_sat_ok(self):
		items = [
			_FakeItem(1, "ITEM-A", "Producto A", "H87 - Pieza"),
			_FakeItem(2, "ITEM-B", "Producto B", "KGM - Kilogramo"),
			_FakeItem(3, "ITEM-C", "Servicio", "E48 - Servicio"),
		]
		validate_invoice_items_uom(items)  # no debe lanzar

	def test_uom_no_sat_lanza_error(self):
		items = [_FakeItem(1, "ITEM-X", "Producto X", "Nos")]
		with self.assertRaises(frappe.ValidationError) as ctx:
			validate_invoice_items_uom(items)
		msg = str(ctx.exception)
		self.assertIn("Nos", msg)
		self.assertIn("ITEM-X", msg)
		self.assertIn("Línea 1", msg)

	def test_multiples_no_sat_lista_todas(self):
		items = [
			_FakeItem(1, "ITEM-A", "Prod A", "Nos"),
			_FakeItem(2, "ITEM-B", "Prod B", "Unit"),
			_FakeItem(3, "ITEM-C", "Prod C", "H87 - Pieza"),  # válida — no debe aparecer
		]
		with self.assertRaises(frappe.ValidationError) as ctx:
			validate_invoice_items_uom(items)
		msg = str(ctx.exception)
		self.assertIn("ITEM-A", msg)
		self.assertIn("Nos", msg)
		self.assertIn("ITEM-B", msg)
		self.assertIn("Unit", msg)
		self.assertNotIn("ITEM-C", msg)

	def test_uom_vacia_lanza_error(self):
		items = [_FakeItem(1, "ITEM-Y", "Producto Y", "")]
		with self.assertRaises(frappe.ValidationError) as ctx:
			validate_invoice_items_uom(items)
		msg = str(ctx.exception)
		self.assertIn("ITEM-Y", msg)
		self.assertIn("Línea 1", msg)

	def test_mensaje_incluye_item_name(self):
		items = [_FakeItem(2, "GASTO-OPR-001", "Energía eléctrica", "Nos")]
		with self.assertRaises(frappe.ValidationError) as ctx:
			validate_invoice_items_uom(items)
		msg = str(ctx.exception)
		self.assertIn("Energía eléctrica", msg)
		self.assertIn("Línea 2", msg)

	def test_lista_vacia_ok(self):
		validate_invoice_items_uom([])  # sin líneas — no debe lanzar

	def test_mensaje_dice_antes_de_timbrar(self):
		items = [_FakeItem(1, "ITEM-Z", "Item Z", "Nos")]
		with self.assertRaises(frappe.ValidationError) as ctx:
			validate_invoice_items_uom(items)
		self.assertIn("timbrar", str(ctx.exception))
