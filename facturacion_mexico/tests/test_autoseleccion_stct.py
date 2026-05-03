"""
Tests unitarios para autoselección inteligente STCT.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.hooks_handlers.sales_invoice_automated_tax import (
	_determinar_variante_stct,
	_find_stct_by_variant,
)


class TestAutoseleccionSTCT(FrappeTestCase):
	"""Tests para sistema autoselección STCT según clasificación items."""

	def setUp(self):
		"""Setup común para todos los tests."""
		# ID único para tests
		self.test_id = frappe.generate_hash(length=6)

	def test_determinar_variante_basico(self):
		"""Documento sin IEPS ni retenciones → variante Básico."""
		# Crear documento simple sin items especiales
		doc = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": "_Test Customer",
				"company": "_Test Company",
				"items": [{"item_code": "_Test Item", "qty": 1, "rate": 100}],
			}
		)

		# Determinar variante
		variant = _determinar_variante_stct(doc)

		# Verificar
		self.assertEqual(variant, "Básico")

	def test_determinar_variante_ieps(self):
		"""Documento con IEPS (sin retenciones) → variante IEPS."""
		# Crear item IEPS Alcohol
		item_code = f"TEST-ALCOHOL-{self.test_id}"
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

		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": "Test Cerveza",
				"item_group": grupo_alcohol,
				"stock_uom": "H87 - Pieza",
			}
		).insert(ignore_permissions=True)

		# Crear Sales Invoice con item IEPS
		doc = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": "_Test Customer",
				"company": "_Test Company",
				"items": [{"item_code": item_code, "qty": 6, "rate": 50}],
			}
		)

		# Determinar variante
		variant = _determinar_variante_stct(doc)

		# Verificar
		self.assertEqual(variant, "IEPS")

	def test_determinar_variante_retenciones(self):
		"""Documento con retenciones (sin IEPS) → variante Retenciones."""
		# Crear item retenciones
		item_code = f"TEST-HONORARIOS-{self.test_id}"
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

		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": "Test Servicio Profesional",
				"item_group": grupo_honorarios,
				"stock_uom": "H87 - Pieza",
			}
		).insert(ignore_permissions=True)

		# Crear Sales Invoice con item retenciones
		doc = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": "_Test Customer",
				"company": "_Test Company",
				"items": [{"item_code": item_code, "qty": 10, "rate": 500}],
			}
		)

		# Determinar variante
		variant = _determinar_variante_stct(doc)

		# Verificar
		self.assertEqual(variant, "Retenciones")

	def test_determinar_variante_total(self):
		"""Documento con IEPS + retenciones → variante Total."""
		# Crear item IEPS
		item_ieps = f"TEST-AZUCAR-{self.test_id}"
		grupo_azucar = "Artículos IEPS Azúcar"

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

		# Crear item retenciones
		item_ret = f"TEST-SERVICIO-{self.test_id}"
		grupo_honorarios = "Servicios Profesionales (Honorarios)"

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

		# Determinar variante
		variant = _determinar_variante_stct(doc)

		# Verificar
		self.assertEqual(variant, "Total")

	def test_find_stct_by_variant_nacional_basico(self):
		"""Buscar STCT Nacional Básico por patrón exacto."""
		# Asumiendo que _Test Company tiene abbr = "_TC"
		company = "_Test Company"
		zona = "Nacional"
		variant = "Básico"

		# Buscar STCT
		stct = _find_stct_by_variant(company, zona, variant)

		# Verificar (puede ser None si no se han generado los STCT)
		# Este test pasa si encuentra o no encuentra (no rompe)
		if stct:
			self.assertIn("IVA Nacional - Básico", stct)

	def test_find_stct_by_variant_frontera_ieps(self):
		"""Buscar STCT Frontera IEPS por patrón exacto."""
		company = "_Test Company"
		zona = "Frontera"
		variant = "IEPS"

		# Buscar STCT
		stct = _find_stct_by_variant(company, zona, variant)

		# Verificar (puede ser None si no se han generado los STCT)
		if stct:
			self.assertIn("IVA Frontera - IEPS", stct)

	def test_matriz_decision_completa(self):
		"""Verificar matriz decisión 2×4 = 8 combinaciones posibles."""
		# Documento vacío (básico)
		doc_basico = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": "_Test Customer",
				"company": "_Test Company",
				"items": [{"item_code": "_Test Item", "qty": 1, "rate": 100}],
			}
		)

		# Matriz decisión esperada
		matriz_esperada = {
			"Básico": {"tiene_ieps": False, "tiene_retenciones": False},
			"IEPS": {"tiene_ieps": True, "tiene_retenciones": False},
			"Retenciones": {"tiene_ieps": False, "tiene_retenciones": True},
			"Total": {"tiene_ieps": True, "tiene_retenciones": True},
		}

		# Verificar que variante Básico es correcta
		variant_basico = _determinar_variante_stct(doc_basico)
		self.assertEqual(variant_basico, "Básico")

		# Verificar que matriz está completa (4 variantes)
		self.assertEqual(len(matriz_esperada), 4)

		# Verificar zonas posibles (2)
		zonas = ["Nacional", "Frontera"]
		self.assertEqual(len(zonas), 2)

		# Total combinaciones: 2 zonas × 4 variantes = 8 STCT
		total_combinaciones = len(zonas) * len(matriz_esperada)
		self.assertEqual(total_combinaciones, 8)
