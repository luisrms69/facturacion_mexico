"""
Tests para ensure_cfdi_received_expense_item_groups.

Verifica creación idempotente del árbol de Item Groups de gasto.
"""

import unittest

import frappe

from facturacion_mexico.setup.cfdi_received_expense_item_groups import (
	_GROUPS,
	_UMBRELLA,
	ensure_cfdi_received_expense_item_groups,
)

_ALL_PARENT_NAMES = [g["name"] for g in _GROUPS]
_ALL_CHILD_NAMES = [child for g in _GROUPS for child in g["children"]]


def _cleanup():
	for child in _ALL_CHILD_NAMES:
		if frappe.db.exists("Item Group", child):
			frappe.delete_doc("Item Group", child, force=True)
	for parent in reversed(_ALL_PARENT_NAMES):
		if frappe.db.exists("Item Group", parent):
			frappe.delete_doc("Item Group", parent, force=True)
	if frappe.db.exists("Item Group", _UMBRELLA):
		frappe.delete_doc("Item Group", _UMBRELLA, force=True)
	frappe.db.commit()


class TestEnsureExpenseItemGroups(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_cleanup()

	@classmethod
	def tearDownClass(cls):
		# Dejar los grupos creados — son útiles en el site de tests
		super().tearDownClass()

	def test_crea_grupo_paraguas(self):
		ensure_cfdi_received_expense_item_groups()
		self.assertTrue(frappe.db.exists("Item Group", _UMBRELLA))
		is_group = frappe.db.get_value("Item Group", _UMBRELLA, "is_group")
		self.assertEqual(is_group, 1)

	def test_crea_once_grupos_padre(self):
		ensure_cfdi_received_expense_item_groups()
		for name in _ALL_PARENT_NAMES:
			self.assertTrue(frappe.db.exists("Item Group", name), f"Padre faltante: {name}")
			is_group = frappe.db.get_value("Item Group", name, "is_group")
			self.assertEqual(is_group, 1, f"{name} debe ser is_group=1")

	def test_crea_84_subcategorias(self):
		ensure_cfdi_received_expense_item_groups()
		self.assertEqual(len(_ALL_CHILD_NAMES), 84)
		for name in _ALL_CHILD_NAMES:
			self.assertTrue(frappe.db.exists("Item Group", name), f"Subcategoría faltante: {name}")

	def test_subcategorias_bajo_padre_correcto(self):
		ensure_cfdi_received_expense_item_groups()
		checks = [
			("Sueldos y salarios", "Nómina y prestaciones"),
			("Honorarios al consejo de administración", "Servicios administrativos y profesionales"),
			("Arrendamiento a residentes del extranjero", "Arrendamientos"),
			("Energía eléctrica", "Servicios básicos y operación"),
			("Papelería y artículos de oficina", "Servicios básicos y operación"),
			("Combustibles y lubricantes", "Movilidad, viáticos y combustibles"),
			("Regalías sujetas al 30%", "Regalías y propiedad intelectual"),
			("Fletes del extranjero", "Logística, fletes e importación"),
			("Otros gastos generales", "Construcción, urbanización y otros"),
		]
		for child, expected_parent in checks:
			actual = frappe.db.get_value("Item Group", child, "parent_item_group")
			self.assertEqual(
				actual, expected_parent, f"{child}: padre esperado={expected_parent}, actual={actual}"
			)

	def test_padres_bajo_paraguas(self):
		ensure_cfdi_received_expense_item_groups()
		for name in _ALL_PARENT_NAMES:
			parent = frappe.db.get_value("Item Group", name, "parent_item_group")
			self.assertEqual(parent, _UMBRELLA, f"{name} debe estar bajo {_UMBRELLA}")

	def test_idempotente_no_duplica(self):
		ensure_cfdi_received_expense_item_groups()
		ensure_cfdi_received_expense_item_groups()
		for name in _ALL_CHILD_NAMES:
			count = frappe.db.count("Item Group", {"item_group_name": name})
			self.assertEqual(count, 1, f"Item Group duplicado: {name}")

	def test_retorna_resumen(self):
		result = ensure_cfdi_received_expense_item_groups()
		for key in ["creados", "existentes", "conflictos"]:
			self.assertIn(key, result)
		self.assertIsInstance(result["conflictos"], list)

	def test_segunda_ejecucion_cero_creados(self):
		ensure_cfdi_received_expense_item_groups()
		result = ensure_cfdi_received_expense_item_groups()
		self.assertEqual(result["creados"], 0)
		self.assertEqual(len(result["conflictos"]), 0)
