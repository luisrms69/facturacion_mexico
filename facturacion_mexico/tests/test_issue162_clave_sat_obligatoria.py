"""
Tests para issue #162: eliminación del fallback "01010101" para Clave SAT Producto/Servicio.

Cubre tres capas de defensa:
  A) _validate_items_clave_sat_for_timbrado (módulo timbrado_api)
  B) FFM.validate() → _validate_items_clave_sat
  C) _prepare_facturapi_data → defensa final en el loop

Usa documentos reales (Items, Sales Invoices) — sin mocks de frappe.db.* ni frappe.get_doc (RG-003).
"""

from pathlib import Path
from unittest.mock import MagicMock

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.facturacion_fiscal.timbrado_api import _validate_items_clave_sat_for_timbrado


def _item_group():
	return frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "Products"


class TestValidateItemsClavesSATTimbrado(FrappeTestCase):
	"""Capa A: tests para _validate_items_clave_sat_for_timbrado (función modular).

	Usa Items reales. La SI se representa como MagicMock con .items conteniendo
	item_codes reales — no se mockea frappe.db.*.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		suffix = frappe.generate_hash()[:6]
		group = _item_group()

		cls.item_con_clave = f"TEST-SAT-A-{suffix}"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": cls.item_con_clave,
				"item_name": cls.item_con_clave,
				"item_group": group,
				"stock_uom": "Nos",
				"fm_producto_servicio_sat": "84111506",
			}
		).insert(ignore_permissions=True)

		cls.item_sin_clave = f"TEST-NOSAT-A-{suffix}"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": cls.item_sin_clave,
				"item_name": cls.item_sin_clave,
				"item_group": group,
				"stock_uom": "Nos",
			}
		).insert(ignore_permissions=True)

	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()
		frappe.db.delete("Item", cls.item_con_clave)
		frappe.db.delete("Item", cls.item_sin_clave)
		frappe.db.commit()

	def _make_si(self, codes):
		si = MagicMock()
		si.items = [frappe._dict(item_code=c, item_name=c) for c in codes]
		return si

	def test_pasa_cuando_todos_tienen_clave_sat(self):
		"""No error cuando todos los ítems tienen fm_producto_servicio_sat."""
		_validate_items_clave_sat_for_timbrado(self._make_si([self.item_con_clave]))

	def test_bloquea_cuando_un_item_sin_clave_sat(self):
		"""ValidationError cuando al menos un ítem carece de clave SAT."""
		with self.assertRaises(frappe.ValidationError) as ctx:
			_validate_items_clave_sat_for_timbrado(self._make_si([self.item_con_clave, self.item_sin_clave]))
		self.assertIn(self.item_sin_clave, str(ctx.exception))

	def test_bloquea_cuando_todos_los_items_sin_clave_sat(self):
		"""ValidationError reporta todos los ítems faltantes en un solo error."""
		item_b = f"TEST-NOSAT-B-{frappe.generate_hash()[:6]}"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_b,
				"item_name": item_b,
				"item_group": _item_group(),
				"stock_uom": "Nos",
			}
		).insert(ignore_permissions=True)
		try:
			with self.assertRaises(frappe.ValidationError) as ctx:
				_validate_items_clave_sat_for_timbrado(self._make_si([self.item_sin_clave, item_b]))
			error_text = str(ctx.exception)
			self.assertIn(self.item_sin_clave, error_text)
			self.assertIn(item_b, error_text)
		finally:
			frappe.db.delete("Item", item_b)
			frappe.db.commit()

	def test_pasa_con_lista_vacia_de_items(self):
		"""SI sin ítems no dispara la validación."""
		_validate_items_clave_sat_for_timbrado(self._make_si([]))


class TestPrepareFActurapiDataSinFallback(FrappeTestCase):
	"""Capa C: verifica que el fallback '01010101' fue eliminado del código fuente."""

	def test_no_existe_fallback_01010101_en_codigo(self):
		"""El string '01010101' no debe aparecer como fallback en timbrado_api.py."""
		import re

		ruta = Path(__file__).parent.parent / "facturacion_fiscal" / "timbrado_api.py"
		contenido = ruta.read_text(encoding="utf-8")

		patron_fallback = re.search(r'fm_producto_servicio_sat\s+or\s+["\']01010101["\']', contenido)
		self.assertIsNone(
			patron_fallback,
			"El fallback 'or \"01010101\"' todavía existe en timbrado_api.py — no fue eliminado.",
		)

	def test_product_key_usa_campo_directo(self):
		"""product_key en el payload debe usar fm_producto_servicio_sat directamente."""
		import re

		ruta = Path(__file__).parent.parent / "facturacion_fiscal" / "timbrado_api.py"
		contenido = ruta.read_text(encoding="utf-8")

		patron_directo = re.search(r'"product_key":\s*item_doc\.fm_producto_servicio_sat\s*,', contenido)
		self.assertIsNotNone(
			patron_directo,
			"No se encontró 'product_key: item_doc.fm_producto_servicio_sat' sin fallback.",
		)


class TestFFMValidateClavesSAT(FrappeTestCase):
	"""Capa B: tests para FFM._validate_items_clave_sat.

	Usa Items y Sales Invoices reales — sin mocks de frappe.get_doc (RG-003).
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		suffix = frappe.generate_hash()[:6]
		group = _item_group()

		# Items — ambos se crean CON clave SAT para pasar el hook de SI
		cls.item_con_clave = f"TEST-SAT-C-{suffix}"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": cls.item_con_clave,
				"item_name": cls.item_con_clave,
				"item_group": group,
				"stock_uom": "Nos",
				"fm_producto_servicio_sat": "84111506",
			}
		).insert(ignore_permissions=True)

		# Item para el caso malo: se crea con clave para poder insertar el SI;
		# la clave se elimina DESPUÉS de crear el SI para simular dato corrupto.
		cls.item_para_si_malo = f"TEST-SAT-TEMP-C-{suffix}"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": cls.item_para_si_malo,
				"item_name": cls.item_para_si_malo,
				"item_group": group,
				"stock_uom": "Nos",
				"fm_producto_servicio_sat": "84111506",
			}
		).insert(ignore_permissions=True)

		# Company, Customer y Cost Center mínimos para crear SI
		cls.company = frappe.db.get_value("Company", {}, "name") or "_Test Company"

		cls.cost_center = frappe.db.get_value("Cost Center", {"is_group": 0, "company": cls.company}, "name")

		cls.customer = "_Test Customer"
		if not frappe.db.exists("Customer", cls.customer):
			frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": cls.customer,
					"customer_type": "Individual",
					"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
					or "Individual",
					"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name")
					or "All Territories",
				}
			).insert(ignore_permissions=True)

		si_ok = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": cls.customer,
				"company": cls.company,
				"cost_center": cls.cost_center,
				"items": [
					{
						"item_code": cls.item_con_clave,
						"qty": 1,
						"rate": 100,
						"uom": "Nos",
						"cost_center": cls.cost_center,
					}
				],
			}
		)
		si_ok.insert(ignore_permissions=True, ignore_mandatory=True)
		cls.si_con_clave = si_ok.name

		# SI para caso malo: se inserta mientras el item tiene clave SAT,
		# luego se elimina la clave del item para que FFM._validate_items_clave_sat falle.
		si_fail = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": cls.customer,
				"company": cls.company,
				"cost_center": cls.cost_center,
				"items": [
					{
						"item_code": cls.item_para_si_malo,
						"qty": 1,
						"rate": 100,
						"uom": "Nos",
						"cost_center": cls.cost_center,
					}
				],
			}
		)
		si_fail.insert(ignore_permissions=True, ignore_mandatory=True)
		cls.si_sin_clave = si_fail.name

		# Ahora eliminar la clave SAT del item — FFM.validate() leerá estado actual del Item
		frappe.db.set_value("Item", cls.item_para_si_malo, "fm_producto_servicio_sat", None)

	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()
		for si in [cls.si_con_clave, cls.si_sin_clave]:
			if frappe.db.exists("Sales Invoice", si):
				frappe.db.delete("Sales Invoice", si)
		for item in [cls.item_con_clave, cls.item_para_si_malo]:
			if frappe.db.exists("Item", item):
				frappe.db.delete("Item", item)
		frappe.db.commit()

	def _make_ffm(self, si_name):
		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
			FacturaFiscalMexico,
		)

		ffm = FacturaFiscalMexico.__new__(FacturaFiscalMexico)
		ffm.sales_invoice = si_name
		return ffm

	def test_pasa_cuando_todos_tienen_clave_sat(self):
		"""_validate_items_clave_sat no lanza error con ítems con clave SAT."""
		if not self.company:
			self.skipTest("No hay Company configurada en el site de tests")
		ffm = self._make_ffm(self.si_con_clave)
		ffm._validate_items_clave_sat()

	def test_bloquea_cuando_item_sin_clave_sat(self):
		"""_validate_items_clave_sat lanza ValidationError cuando falta clave SAT.
		item_para_si_malo fue creado con clave para poder insertar el SI;
		la clave se eliminó en setUpClass para simular un ítem corrupto/sin configurar.
		"""
		if not self.company:
			self.skipTest("No hay Company configurada en el site de tests")
		ffm = self._make_ffm(self.si_sin_clave)
		with self.assertRaises(frappe.ValidationError) as ctx:
			ffm._validate_items_clave_sat()
		self.assertIn(self.item_para_si_malo, str(ctx.exception))

	def test_no_valida_cuando_no_hay_sales_invoice(self):
		"""_validate_items_clave_sat retorna sin error si sales_invoice está vacío."""
		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
			FacturaFiscalMexico,
		)

		ffm = FacturaFiscalMexico.__new__(FacturaFiscalMexico)
		ffm.sales_invoice = None
		ffm._validate_items_clave_sat()
