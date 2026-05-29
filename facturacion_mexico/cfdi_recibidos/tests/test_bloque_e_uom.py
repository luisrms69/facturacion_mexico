import unittest

import frappe

from facturacion_mexico.cfdi_recibidos.services.uom_policy import (
	SAT_UOMS,
	get_sat_uom_list,
	is_sat_uom,
	validate_sat_uom,
)
from facturacion_mexico.setup.enforce_sat_uom import enforce_sat_uom_policy

_TEST_UOM = "_BloqueE TestNonSAT"


class TestUOMPolicy(unittest.TestCase):
	def test_is_sat_uom_sat(self):
		self.assertTrue(is_sat_uom("H87 - Pieza"))
		self.assertTrue(is_sat_uom("MON - Mes"))
		self.assertTrue(is_sat_uom("NA - No Aplica"))

	def test_is_sat_uom_no_sat(self):
		self.assertFalse(is_sat_uom("Nos"))
		self.assertFalse(is_sat_uom("Unit"))
		self.assertFalse(is_sat_uom(""))

	def test_validate_sat_uom_no_sat_throws(self):
		with self.assertRaises(frappe.ValidationError):
			validate_sat_uom("Nos")

	def test_validate_sat_uom_no_sat_incluye_context(self):
		try:
			validate_sat_uom("Nos", context="Concepto 1")
			self.fail("Debió lanzar ValidationError")
		except frappe.ValidationError as e:
			self.assertIn("Concepto 1", str(e))
			self.assertIn("Nos", str(e))

	def test_validate_sat_uom_sat_no_lanza(self):
		validate_sat_uom("H87 - Pieza")  # no exception

	def test_get_sat_uom_list_retorna_todas(self):
		lista = get_sat_uom_list()
		self.assertEqual(len(lista), len(SAT_UOMS))
		self.assertIn("H87 - Pieza", lista)
		self.assertIn("NA - No Aplica", lista)

	def test_get_sat_uom_list_ordenada(self):
		lista = get_sat_uom_list()
		self.assertEqual(lista, sorted(lista))


class TestEnforceSatUom(unittest.TestCase):
	def setUp(self):
		if not frappe.db.exists("UOM", _TEST_UOM):
			doc = frappe.get_doc({"doctype": "UOM", "uom_name": _TEST_UOM, "enabled": 1})
			doc.insert(ignore_permissions=True)
			frappe.db.commit()

	def tearDown(self):
		if frappe.db.exists("UOM", _TEST_UOM):
			frappe.db.delete("UOM", {"name": _TEST_UOM})
			frappe.db.commit()

	def test_enforce_deshabilita_no_sat(self):
		frappe.db.set_value("UOM", _TEST_UOM, "enabled", 1, update_modified=False)
		frappe.db.commit()
		result = enforce_sat_uom_policy(is_install=False)
		enabled_after = frappe.db.get_value("UOM", _TEST_UOM, "enabled")
		self.assertEqual(int(enabled_after), 0)
		self.assertGreaterEqual(result["deshabilitadas"], 1)

	def test_enforce_preserva_sat_uoms(self):
		frappe.db.set_value("UOM", "H87 - Pieza", "enabled", 1, update_modified=False)
		frappe.db.commit()
		enforce_sat_uom_policy(is_install=False)
		enabled_after = frappe.db.get_value("UOM", "H87 - Pieza", "enabled")
		self.assertEqual(int(enabled_after), 1)

	def test_enforce_reactiva_sat_deshabilitada(self):
		frappe.db.set_value("UOM", "MON - Mes", "enabled", 0, update_modified=False)
		frappe.db.commit()
		result = enforce_sat_uom_policy(is_install=False)
		enabled_after = frappe.db.get_value("UOM", "MON - Mes", "enabled")
		self.assertEqual(int(enabled_after), 1)
		self.assertGreaterEqual(result["sat_corregidas"], 1)

	def test_enforce_preserva_test_uoms(self):
		test_uom = "_Test UOM"
		if not frappe.db.exists("UOM", test_uom):
			self.skipTest(f"{test_uom} no existe en este site")
		enabled_before = frappe.db.get_value("UOM", test_uom, "enabled")
		enforce_sat_uom_policy(is_install=False)
		enabled_after = frappe.db.get_value("UOM", test_uom, "enabled")
		self.assertEqual(enabled_before, enabled_after)

	def test_enforce_idempotente(self):
		enforce_sat_uom_policy(is_install=False)
		result2 = enforce_sat_uom_policy(is_install=False)
		self.assertEqual(result2["deshabilitadas"], 0)
		self.assertEqual(result2["sat_corregidas"], 0)

	def test_enforce_no_borra_registros(self):
		count_before = frappe.db.count("UOM")
		enforce_sat_uom_policy(is_install=False)
		count_after = frappe.db.count("UOM")
		self.assertEqual(count_before, count_after)

	def test_enforce_migrate_no_cambia_stock_settings(self):
		stock_uom_before = frappe.db.get_single_value("Stock Settings", "stock_uom") or ""
		enforce_sat_uom_policy(is_install=False)
		stock_uom_after = frappe.db.get_single_value("Stock Settings", "stock_uom") or ""
		self.assertEqual(stock_uom_before, stock_uom_after)

	def test_enforce_install_cambia_stock_uom_si_no_sat(self):
		stock_uom_before = frappe.db.get_single_value("Stock Settings", "stock_uom") or ""
		if stock_uom_before in SAT_UOMS:
			self.skipTest("stock_uom ya es SAT — no aplica este caso")
		try:
			enforce_sat_uom_policy(is_install=True)
			stock_uom_after = frappe.db.get_single_value("Stock Settings", "stock_uom") or ""
			self.assertEqual(stock_uom_after, "H87 - Pieza")
		finally:
			if stock_uom_before:
				frappe.db.set_single_value("Stock Settings", "stock_uom", stock_uom_before)
				frappe.db.commit()
