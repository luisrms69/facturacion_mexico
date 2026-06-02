"""
Tests para ensure_fiscal_subgroups en item_groups.py.

Verifica:
- Subgrupos se crean correctamente bajo su parent fiscal
- Idempotencia: segunda llamada no crea duplicados
- Subgrupos existentes con parent diferente son reportados como conflicto, no modificados
- Subgrupos custom preexistentes bajo el mismo parent no son tocados
- Ningún grupo existente es borrado, modificado o movido
"""

import unittest

import frappe

from facturacion_mexico.setup.item_groups import (
	SUBGRUPOS_FISCALES,
	_ensure_subgroup,
	ensure_fiscal_item_groups,
	ensure_fiscal_subgroups,
)

TEST_PARENT = "Artículos con IVA al 0%"
TEST_CHILD = "Frutas y verduras"
TEST_CUSTOM = "TEST-Custom-Group-" + frappe.generate_hash()[:6]
TEST_CONFLICT = "TEST-Conflict-Group-" + frappe.generate_hash()[:6]


class TestEnsureFiscalSubgroups(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_fiscal_item_groups()

	def test_subgroups_created_under_correct_parent(self):
		"""Todos los subgrupos del esqueleto existen bajo su parent correcto."""
		for parent, children in SUBGRUPOS_FISCALES.items():
			self.assertTrue(
				frappe.db.exists("Item Group", parent),
				f"Parent '{parent}' debe existir",
			)
			for child in children:
				actual_parent = frappe.db.get_value("Item Group", child, "parent_item_group")
				self.assertEqual(
					actual_parent,
					parent,
					f"'{child}' debe estar bajo '{parent}', está bajo '{actual_parent}'",
				)

	def test_idempotent_second_call(self):
		"""Segunda llamada no crea duplicados ni modifica existentes."""
		ensure_fiscal_subgroups()
		result2 = ensure_fiscal_subgroups()
		self.assertEqual(result2["creados"], 0, "Segunda llamada no debe crear nada")
		self.assertEqual(len(result2["conflictos"]), 0, "Segunda llamada no debe reportar conflictos nuevos")

	def test_existing_custom_subgroup_preserved(self):
		"""Un subgrupo custom preexistente bajo el mismo parent no es borrado ni modificado."""
		if not frappe.db.exists("Item Group", TEST_CUSTOM):
			doc = frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": TEST_CUSTOM,
					"parent_item_group": TEST_PARENT,
					"is_group": 0,
				}
			)
			doc.insert(ignore_permissions=True)
			frappe.db.commit()

		ensure_fiscal_subgroups()

		self.assertTrue(
			frappe.db.exists("Item Group", TEST_CUSTOM),
			"El subgrupo custom no debe ser borrado",
		)
		actual_parent = frappe.db.get_value("Item Group", TEST_CUSTOM, "parent_item_group")
		self.assertEqual(actual_parent, TEST_PARENT, "El subgrupo custom no debe ser movido")

	def test_conflict_reported_not_fixed(self):
		"""Subgrupo con parent diferente al esperado es reportado como conflicto, no movido."""
		root = (
			frappe.db.get_value("Item Group", {"parent_item_group": ""}, "name")
			or frappe.db.sql(
				"SELECT name FROM `tabItem Group` WHERE (parent_item_group IS NULL OR parent_item_group='') LIMIT 1"
			)[0][0]
		)

		if not frappe.db.exists("Item Group", TEST_CONFLICT):
			doc = frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": TEST_CONFLICT,
					"parent_item_group": root,
					"is_group": 0,
				}
			)
			doc.insert(ignore_permissions=True)
			frappe.db.commit()

		created, conflict = _ensure_subgroup(TEST_CONFLICT, TEST_PARENT)

		self.assertFalse(created, "No debe crear si ya existe")
		self.assertIsNotNone(conflict, "Debe reportar conflicto")
		self.assertEqual(conflict["name"], TEST_CONFLICT)
		self.assertEqual(conflict["expected_parent"], TEST_PARENT)
		self.assertEqual(conflict["actual_parent"], root)

		actual_parent = frappe.db.get_value("Item Group", TEST_CONFLICT, "parent_item_group")
		self.assertEqual(actual_parent, root, "El grupo en conflicto NO debe ser movido")

	def test_no_group_deleted_on_migrate(self):
		"""ensure_fiscal_subgroups no borra ningún Item Group existente."""
		before = {r[0] for r in frappe.db.sql("SELECT name FROM `tabItem Group`")}
		ensure_fiscal_subgroups()
		after = {r[0] for r in frappe.db.sql("SELECT name FROM `tabItem Group`")}
		deleted = before - after
		self.assertEqual(len(deleted), 0, f"Grupos borrados: {deleted}")

	@classmethod
	def tearDownClass(cls):
		for name in [TEST_CUSTOM, TEST_CONFLICT]:
			if frappe.db.exists("Item Group", name):
				frappe.delete_doc("Item Group", name, force=True)
		frappe.db.commit()
		super().tearDownClass()
