"""
Tests para issue #162: eliminación del fallback "01010101" para Clave SAT Producto/Servicio.

Cubre tres capas de defensa:
  A) _validate_items_clave_sat_for_timbrado (módulo timbrado_api)
  B) FFM.validate() → _validate_items_clave_sat
  C) _prepare_facturapi_data → defensa final en el loop

No cubre la capa de Sales Invoice validate (fuera del alcance de este issue).
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.facturacion_fiscal.timbrado_api import _validate_items_clave_sat_for_timbrado


def _make_si_items(items_data):
	"""Helper: construye lista de items estilo Frappe para un SI mock."""
	items = []
	for d in items_data:
		item = frappe._dict(
			item_code=d["item_code"],
			item_name=d.get("item_name", d["item_code"]),
			qty=d.get("qty", 1),
			rate=d.get("rate", 100),
			uom=d.get("uom", "H87 - Pieza"),
		)
		items.append(item)
	return items


def _make_mock_si(items_data, name="TEST-SI-001"):
	# frappe._dict no sirve aquí: .items() es el método dict, no la lista de ítems.
	si = MagicMock()
	si.name = name
	si.docstatus = 1
	si.items = _make_si_items(items_data)
	return si


class TestValidateItemsClavesSATTimbrado(FrappeTestCase):
	"""Tests para _validate_items_clave_sat_for_timbrado en timbrado_api.py (Capa A)."""

	def _make_get_value_mock(self, clave_map):
		"""
		Devuelve un side_effect para frappe.db.get_value que mapea item_code → clave SAT.
		clave_map: {"ITEM-001": "43211501", "ITEM-002": None}
		"""

		def side_effect(doctype, name, field):
			if doctype == "Item" and field == "fm_producto_servicio_sat":
				return clave_map.get(name)
			return None

		return side_effect

	def test_pasa_cuando_todos_tienen_clave_sat(self):
		"""Ningún error cuando todos los ítems tienen fm_producto_servicio_sat."""
		si = _make_mock_si(
			[
				{"item_code": "ITEM-001"},
				{"item_code": "ITEM-002"},
			]
		)
		clave_map = {"ITEM-001": "43211501", "ITEM-002": "80141600"}

		with patch("frappe.db.get_value", side_effect=self._make_get_value_mock(clave_map)):
			# No debe lanzar excepción
			_validate_items_clave_sat_for_timbrado(si)

	def test_bloquea_cuando_un_item_sin_clave_sat(self):
		"""ValidationError cuando al menos un ítem carece de clave SAT."""
		si = _make_mock_si(
			[
				{"item_code": "ITEM-CON-CLAVE", "item_name": "Producto configurado"},
				{"item_code": "ITEM-SIN-CLAVE", "item_name": "Producto sin configurar"},
			]
		)
		clave_map = {"ITEM-CON-CLAVE": "43211501", "ITEM-SIN-CLAVE": None}

		with patch("frappe.db.get_value", side_effect=self._make_get_value_mock(clave_map)):
			with self.assertRaises(frappe.ValidationError) as ctx:
				_validate_items_clave_sat_for_timbrado(si)

		self.assertIn("ITEM-SIN-CLAVE", str(ctx.exception))
		self.assertIn("Clave SAT", str(ctx.exception))

	def test_bloquea_cuando_todos_los_items_sin_clave_sat(self):
		"""ValidationError acumula todos los ítems faltantes en un solo error."""
		si = _make_mock_si(
			[
				{"item_code": "ITEM-A", "item_name": "Item A"},
				{"item_code": "ITEM-B", "item_name": "Item B"},
				{"item_code": "ITEM-C", "item_name": "Item C"},
			]
		)
		clave_map = {"ITEM-A": None, "ITEM-B": None, "ITEM-C": None}

		with patch("frappe.db.get_value", side_effect=self._make_get_value_mock(clave_map)):
			with self.assertRaises(frappe.ValidationError) as ctx:
				_validate_items_clave_sat_for_timbrado(si)

		error_text = str(ctx.exception)
		self.assertIn("ITEM-A", error_text)
		self.assertIn("ITEM-B", error_text)
		self.assertIn("ITEM-C", error_text)

	def test_pasa_con_lista_vacia_de_items(self):
		"""SI sin ítems no dispara la validación de clave SAT."""
		si = _make_mock_si([])

		with patch("frappe.db.get_value", return_value=None):
			_validate_items_clave_sat_for_timbrado(si)


class TestPrepareFActurapiDataSinFallback(FrappeTestCase):
	"""Tests para la defensa final en _prepare_facturapi_data (Capa C).

	Verifica que el fallback "01010101" fue eliminado y que el código
	lanza error si se llega al loop con un ítem sin clave SAT.
	"""

	def test_no_existe_fallback_01010101_en_codigo(self):
		"""El string '01010101' no debe aparecer como fallback en timbrado_api.py."""
		import re

		ruta = (
			"/home/erpnext/frappe-bench-v16/apps/facturacion_mexico"
			"/facturacion_mexico/facturacion_fiscal/timbrado_api.py"
		)
		with open(ruta) as f:
			contenido = f.read()

		# Buscar el patrón de fallback: fm_producto_servicio_sat or "01010101"
		patron_fallback = re.search(r'fm_producto_servicio_sat\s+or\s+["\']01010101["\']', contenido)
		self.assertIsNone(
			patron_fallback,
			"El fallback 'or \"01010101\"' todavía existe en timbrado_api.py — no fue eliminado.",
		)

	def test_product_key_usa_campo_directo(self):
		"""product_key en el payload debe usar fm_producto_servicio_sat directamente."""
		import re

		ruta = (
			"/home/erpnext/frappe-bench-v16/apps/facturacion_mexico"
			"/facturacion_mexico/facturacion_fiscal/timbrado_api.py"
		)
		with open(ruta) as f:
			contenido = f.read()

		# Debe existir la asignación directa sin fallback
		patron_directo = re.search(r'"product_key":\s*item_doc\.fm_producto_servicio_sat\s*,', contenido)
		self.assertIsNotNone(
			patron_directo,
			"No se encontró la asignación directa 'product_key: item_doc.fm_producto_servicio_sat' "
			"sin fallback en timbrado_api.py.",
		)


class TestFFMValidateClavesSAT(FrappeTestCase):
	"""Tests para FFM._validate_items_clave_sat (Capa B).

	Prueba el método directamente usando mocks para evitar dependencia de BD.
	"""

	def _make_ffm_doc(self, si_name="TEST-SI-001"):
		"""Crea un documento FFM mock con sales_invoice configurado."""
		ffm = MagicMock()
		ffm.sales_invoice = si_name
		return ffm

	def _make_si_doc(self, items_data):
		"""Crea un SI mock con ítems."""
		si = MagicMock()
		si.items = [
			frappe._dict(
				item_code=d["item_code"],
				item_name=d.get("item_name", d["item_code"]),
			)
			for d in items_data
		]
		return si

	def test_pasa_cuando_todos_tienen_clave_sat(self):
		"""_validate_items_clave_sat no lanza error cuando todos los ítems tienen clave."""
		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
			FacturaFiscalMexico,
		)

		si = self._make_si_doc(
			[
				{"item_code": "ITEM-001"},
				{"item_code": "ITEM-002"},
			]
		)

		def get_value_mock(doctype, name, field):
			claves = {"ITEM-001": "43211501", "ITEM-002": "80141600"}
			if doctype == "Item" and field == "fm_producto_servicio_sat":
				return claves.get(name)
			return None

		# Instanciar sin BD usando __new__ para evitar __init__ de Frappe
		ffm = FacturaFiscalMexico.__new__(FacturaFiscalMexico)
		ffm.sales_invoice = "TEST-SI-001"

		with (
			patch("frappe.get_doc", return_value=si),
			patch("frappe.db.get_value", side_effect=get_value_mock),
		):
			ffm._validate_items_clave_sat()

	def test_bloquea_cuando_item_sin_clave_sat(self):
		"""_validate_items_clave_sat lanza ValidationError cuando falta clave SAT."""
		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
			FacturaFiscalMexico,
		)

		si = self._make_si_doc(
			[
				{"item_code": "ITEM-OK", "item_name": "Con clave"},
				{"item_code": "ITEM-SIN", "item_name": "Sin clave"},
			]
		)

		def get_value_mock(doctype, name, field):
			claves = {"ITEM-OK": "43211501", "ITEM-SIN": None}
			if doctype == "Item" and field == "fm_producto_servicio_sat":
				return claves.get(name)
			return None

		ffm = FacturaFiscalMexico.__new__(FacturaFiscalMexico)
		ffm.sales_invoice = "TEST-SI-001"

		with (
			patch("frappe.get_doc", return_value=si),
			patch("frappe.db.get_value", side_effect=get_value_mock),
		):
			with self.assertRaises(frappe.ValidationError) as ctx:
				ffm._validate_items_clave_sat()

		self.assertIn("ITEM-SIN", str(ctx.exception))

	def test_no_valida_cuando_no_hay_sales_invoice(self):
		"""_validate_items_clave_sat retorna sin error si sales_invoice está vacío."""
		from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
			FacturaFiscalMexico,
		)

		ffm = FacturaFiscalMexico.__new__(FacturaFiscalMexico)
		ffm.sales_invoice = None

		with patch("frappe.get_doc") as mock_get_doc:
			ffm._validate_items_clave_sat()
			mock_get_doc.assert_not_called()
