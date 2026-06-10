import unittest

import frappe

from facturacion_mexico.cfdi_recibidos.services.uom_policy import (
	normalize_uom_to_sat_code,
	try_normalize_uom_to_sat_code,
)
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

	# ── Normalización de UOM (backward-compat legacy facturacion_mx) ─────────────

	def test_legacy_h87_pieza_pasa_validacion(self):
		# Sitios migrados de facturacion_mx tienen UOM "H87 Pieza" sin guion.
		# ERPNext no permite cambiar UOM de Items con transacciones; se normaliza aquí.
		items = [_FakeItem(1, "LLAN-001", "Llanta", "H87 Pieza")]
		validate_invoice_items_uom(items)  # no debe lanzar

	def test_canonico_h87_pieza_pasa_validacion(self):
		items = [_FakeItem(1, "LLAN-001", "Llanta", "H87 - Pieza")]
		validate_invoice_items_uom(items)

	def test_codigo_puro_h87_pasa_validacion(self):
		items = [_FakeItem(1, "LLAN-001", "Llanta", "H87")]
		validate_invoice_items_uom(items)

	def test_legacy_kgm_pasa_validacion(self):
		items = [_FakeItem(1, "PROD-001", "Producto", "KGM Kilogramo")]
		validate_invoice_items_uom(items)

	def test_legacy_e48_pasa_validacion(self):
		items = [_FakeItem(1, "SRV-001", "Servicio", "E48 Unidad de Servicio")]
		validate_invoice_items_uom(items)


class TestNormalizeUomToSatCode(unittest.TestCase):
	def test_canonico_extrae_codigo(self):
		self.assertEqual(normalize_uom_to_sat_code("H87 - Pieza"), "H87")
		self.assertEqual(normalize_uom_to_sat_code("KGM - Kilogramo"), "KGM")
		self.assertEqual(normalize_uom_to_sat_code("E48 - Servicio"), "E48")

	def test_legacy_extrae_codigo(self):
		self.assertEqual(normalize_uom_to_sat_code("H87 Pieza"), "H87")
		self.assertEqual(normalize_uom_to_sat_code("KGM Kilogramo"), "KGM")
		self.assertEqual(normalize_uom_to_sat_code("E48 Unidad de Servicio"), "E48")

	def test_codigo_puro_extrae_codigo(self):
		self.assertEqual(normalize_uom_to_sat_code("H87"), "H87")
		self.assertEqual(normalize_uom_to_sat_code("KGM"), "KGM")

	def test_invalido_lanza_error(self):
		with self.assertRaises(frappe.ValidationError):
			normalize_uom_to_sat_code("Pieza")
		with self.assertRaises(frappe.ValidationError):
			normalize_uom_to_sat_code("Nos")
		with self.assertRaises(frappe.ValidationError):
			normalize_uom_to_sat_code("Unit")
		with self.assertRaises(frappe.ValidationError):
			normalize_uom_to_sat_code("")

	def test_try_retorna_none_para_invalido(self):
		self.assertIsNone(try_normalize_uom_to_sat_code("Pieza"))
		self.assertIsNone(try_normalize_uom_to_sat_code("Nos"))
		self.assertIsNone(try_normalize_uom_to_sat_code(""))

	def test_try_retorna_codigo_para_valido(self):
		self.assertEqual(try_normalize_uom_to_sat_code("H87 - Pieza"), "H87")
		self.assertEqual(try_normalize_uom_to_sat_code("H87 Pieza"), "H87")
		self.assertEqual(try_normalize_uom_to_sat_code("H87"), "H87")
