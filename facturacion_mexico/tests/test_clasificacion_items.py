"""
Tests unitarios para clasificación de items por categoría fiscal.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.setup.item_groups import (
	CATEGORIAS_IEPS,
	ITEM_GROUP_CATEGORIA,
	TABLA_MAESTRA_GRUPOS_FISCALES,
)
from facturacion_mexico.utils.clasificacion_items import clasificar_items_documento


class TestClasificacionItems(FrappeTestCase):
	"""Tests para función clasificación items documento."""

	def test_item_group_categoria_map_completo(self):
		"""Verificar que ITEM_GROUP_CATEGORIA contiene todos los grupos."""
		# Verificar grupos IEPS
		self.assertEqual(ITEM_GROUP_CATEGORIA["Artículos IEPS Alcohol"], "Alcohol")
		self.assertEqual(ITEM_GROUP_CATEGORIA["Artículos IEPS Azúcar"], "Azucar")

		# Verificar grupos Retenciones
		self.assertEqual(ITEM_GROUP_CATEGORIA["Servicios Profesionales (Honorarios)"], "Retenciones")

		# Verificar grupos Resto
		self.assertEqual(ITEM_GROUP_CATEGORIA["Artículos con IVA al 0%"], "Resto")
		self.assertEqual(ITEM_GROUP_CATEGORIA["Artículos Exentos"], "Resto")

	def test_categorias_ieps_constante(self):
		"""Verificar que CATEGORIAS_IEPS contiene las 4 categorías."""
		self.assertEqual(len(CATEGORIAS_IEPS), 4)
		self.assertIn("Alcohol", CATEGORIAS_IEPS)
		self.assertIn("Azucar", CATEGORIAS_IEPS)
		self.assertIn("Combustibles", CATEGORIAS_IEPS)
		self.assertIn("Tabaco", CATEGORIAS_IEPS)

	def test_clasificar_documento_vacio(self):
		"""Documento sin items → no tiene categorías."""
		doc = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": "_Test Customer",
				"company": "_Test Company",
				"items": [],
			}
		)

		clasificacion = clasificar_items_documento(doc)

		self.assertFalse(clasificacion["tiene_ieps"])
		self.assertFalse(clasificacion["tiene_retenciones"])
		self.assertEqual(clasificacion["categorias"], [])
		self.assertEqual(clasificacion["items_por_categoria"], {})

	def test_clasificar_item_resto_default(self):
		"""Item con grupo desconocido → categoría Resto."""
		# Crear item test con grupo genérico
		item_code = f"TEST-ITEM-{frappe.generate_hash(length=6)}"
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": "Test Item Resto",
				"item_group": "All Item Groups",  # Grupo genérico
				"stock_uom": "H87 - Pieza",
			}
		)
		item.insert(ignore_permissions=True)

		# Crear Sales Invoice con este item
		doc = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": "_Test Customer",
				"company": "_Test Company",
				"items": [{"item_code": item_code, "qty": 1, "rate": 100}],
			}
		)

		clasificacion = clasificar_items_documento(doc)

		# Verificar clasificación
		self.assertFalse(clasificacion["tiene_ieps"])
		self.assertFalse(clasificacion["tiene_retenciones"])
		self.assertIn("Resto", clasificacion["categorias"])
		self.assertIn(item_code, clasificacion["items_por_categoria"]["Resto"])

	def test_clasificar_item_ieps_alcohol(self):
		"""Item con Item Group IEPS Alcohol → categoría Alcohol."""
		# Crear item test con grupo IEPS Alcohol
		item_code = f"TEST-ALCOHOL-{frappe.generate_hash(length=6)}"
		grupo_alcohol = "Artículos IEPS Alcohol"

		# Asegurar que existe el Item Group
		if not frappe.db.exists("Item Group", grupo_alcohol):
			frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": grupo_alcohol,
					"parent_item_group": "All Item Groups",
					"is_group": 1,
				}
			).insert(ignore_permissions=True)

		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": "Test Cerveza",
				"item_group": grupo_alcohol,
				"stock_uom": "H87 - Pieza",
			}
		)
		item.insert(ignore_permissions=True)

		# Crear Sales Invoice
		doc = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": "_Test Customer",
				"company": "_Test Company",
				"items": [{"item_code": item_code, "qty": 6, "rate": 50}],
			}
		)

		clasificacion = clasificar_items_documento(doc)

		# Verificar clasificación
		self.assertTrue(clasificacion["tiene_ieps"])
		self.assertFalse(clasificacion["tiene_retenciones"])
		self.assertIn("Alcohol", clasificacion["categorias"])
		self.assertIn(item_code, clasificacion["items_por_categoria"]["Alcohol"])

	def test_clasificar_item_retenciones(self):
		"""Item con Item Group Retenciones → categoría Retenciones."""
		# Crear item test con grupo Retenciones
		item_code = f"TEST-HONORARIOS-{frappe.generate_hash(length=6)}"
		grupo_honorarios = "Servicios Profesionales (Honorarios)"

		# Asegurar que existe el Item Group
		if not frappe.db.exists("Item Group", grupo_honorarios):
			frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": grupo_honorarios,
					"parent_item_group": "All Item Groups",
					"is_group": 1,
				}
			).insert(ignore_permissions=True)

		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": "Test Servicio Profesional",
				"item_group": grupo_honorarios,
				"stock_uom": "H87 - Pieza",
			}
		)
		item.insert(ignore_permissions=True)

		# Crear Sales Invoice
		doc = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": "_Test Customer",
				"company": "_Test Company",
				"items": [{"item_code": item_code, "qty": 10, "rate": 500}],
			}
		)

		clasificacion = clasificar_items_documento(doc)

		# Verificar clasificación
		self.assertFalse(clasificacion["tiene_ieps"])
		self.assertTrue(clasificacion["tiene_retenciones"])
		self.assertIn("Retenciones", clasificacion["categorias"])
		self.assertIn(item_code, clasificacion["items_por_categoria"]["Retenciones"])

	def test_clasificar_documento_mixto_ieps_retenciones(self):
		"""Documento con IEPS + Retenciones → detecta ambas categorías."""
		# Crear item IEPS
		item_ieps = f"TEST-AZUCAR-{frappe.generate_hash(length=6)}"
		grupo_azucar = "Artículos IEPS Azúcar"
		grupo_honorarios = "Servicios Profesionales (Honorarios)"

		if not frappe.db.exists("Item Group", grupo_azucar):
			frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": grupo_azucar,
					"parent_item_group": "All Item Groups",
					"is_group": 1,
				}
			).insert(ignore_permissions=True)

		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_ieps,
				"item_name": "Test Refresco",
				"item_group": grupo_azucar,
				"stock_uom": "H87 - Pieza",
			}
		).insert(ignore_permissions=True)

		# Crear item Retenciones
		item_ret = f"TEST-SERVICIO-{frappe.generate_hash(length=6)}"

		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_ret,
				"item_name": "Test Consultoría",
				"item_group": grupo_honorarios,
				"stock_uom": "H87 - Pieza",
			}
		).insert(ignore_permissions=True)

		# Crear Sales Invoice mixto
		doc = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": "_Test Customer",
				"company": "_Test Company",
				"items": [
					{"item_code": item_ieps, "qty": 24, "rate": 15},
					{"item_code": item_ret, "qty": 5, "rate": 1000},
				],
			}
		)

		clasificacion = clasificar_items_documento(doc)

		# Verificar clasificación mixta
		self.assertTrue(clasificacion["tiene_ieps"])
		self.assertTrue(clasificacion["tiene_retenciones"])
		self.assertIn("Azucar", clasificacion["categorias"])
		self.assertIn("Retenciones", clasificacion["categorias"])
		self.assertIn(item_ieps, clasificacion["items_por_categoria"]["Azucar"])
		self.assertIn(item_ret, clasificacion["items_por_categoria"]["Retenciones"])
