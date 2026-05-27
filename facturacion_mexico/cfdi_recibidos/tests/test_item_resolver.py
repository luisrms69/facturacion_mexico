from unittest.mock import call, patch

from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.cfdi_recibidos.services.item_resolver import ItemResolver

_BASE = dict(
	sat_product_key="80111500",
	no_identificacion="PROD-001",
	item_group="Honorarios a personas morales residentes nacionales",
	company="Test Company",
	supplier="SUPP-001",
	supplier_rfc="AAA010101AAA",
)


def _gv(mapping=None, item_supplier=None):
	"""Genera side_effect para frappe.db.get_value despachando por doctype."""

	def _fn(doctype, filters, fieldname, **kwargs):
		if doctype == "CFDI Concepto Mapping":
			return mapping
		if doctype == "Item Supplier":
			return item_supplier
		return None

	return _fn


def _ga(candidates=None):
	"""Genera side_effect para frappe.db.get_all despachando por doctype."""
	candidates = candidates or []

	def _fn(doctype, filters=None, pluck=None, **kwargs):
		if doctype == "Item":
			return candidates
		return []

	return _fn


class TestNivel1Mapeado(FrappeTestCase):
	def setUp(self):
		self.r = ItemResolver()

	def test_mapeado_activo_retorna_item(self):
		with patch("frappe.db.get_value", side_effect=_gv("GASTO-SRV-007")):
			with patch("frappe.db.get_all", side_effect=_ga()):
				result = self.r.propose(**_BASE)
		self.assertEqual(result["item_code"], "GASTO-SRV-007")
		self.assertEqual(result["item_resolution"], "Mapeado")

	def test_mapeado_inactivo_no_retorna(self):
		# is_active=0 en BD → el filtro is_active=1 no matchea → get_value retorna None
		# El resolver cae a nivel 3 (nivel 2 también miss: supplier_part_no no coincide)
		with patch("frappe.db.get_value", side_effect=_gv(None, None)):
			with patch("frappe.db.get_all", side_effect=_ga(["GASTO-SRV-007"])):
				result = self.r.propose(**_BASE)
		self.assertEqual(result["item_resolution"], "Genérico")

	def test_expense_account_no_retorna(self):
		# target_type='ExpenseAccount' en BD → el filtro target_type='Item' no matchea
		with patch("frappe.db.get_value", side_effect=_gv(None, None)):
			with patch("frappe.db.get_all", side_effect=_ga(["GASTO-SRV-007"])):
				result = self.r.propose(**_BASE)
		self.assertNotEqual(result.get("item_resolution"), "Mapeado")

	def test_nivel1_gana_niveles_inferiores_no_se_consultan(self):
		with (
			patch("frappe.db.get_value", side_effect=_gv("GASTO-SRV-007")),
			patch("frappe.db.get_all") as mock_ga,
		):
			result = self.r.propose(**_BASE)
		mock_ga.assert_not_called()
		self.assertEqual(result["item_code"], "GASTO-SRV-007")
		self.assertEqual(result["item_resolution"], "Mapeado")


class TestNivel2Especifico(FrappeTestCase):
	def setUp(self):
		self.r = ItemResolver()

	def test_especifico_por_no_identificacion(self):
		with patch("frappe.db.get_value", side_effect=_gv(None, "ITEM-ESPECIFICO")):
			with patch("frappe.db.get_all", side_effect=_ga()):
				result = self.r.propose(**_BASE)
		self.assertEqual(result["item_code"], "ITEM-ESPECIFICO")
		self.assertEqual(result["item_resolution"], "Específico")

	def test_salta_si_no_identificacion_vacio(self):
		kwargs = {**_BASE, "no_identificacion": ""}
		with patch("frappe.db.get_value", side_effect=_gv(None, None)) as mock_gv:
			with patch("frappe.db.get_all", side_effect=_ga(["GASTO-SRV-007"])):
				result = self.r.propose(**kwargs)
		calls_item_supplier = [c for c in mock_gv.call_args_list if c[0][0] == "Item Supplier"]
		self.assertEqual(len(calls_item_supplier), 0, "Item Supplier no debe consultarse")
		self.assertEqual(result["item_resolution"], "Genérico")


class TestNivel3Generico(FrappeTestCase):
	def setUp(self):
		self.r = ItemResolver()

	def test_generico_por_item_group(self):
		with patch("frappe.db.get_value", side_effect=_gv(None, None)):
			with patch("frappe.db.get_all", side_effect=_ga(["GASTO-SRV-007"])):
				result = self.r.propose(**_BASE)
		self.assertEqual(result["item_code"], "GASTO-SRV-007")
		self.assertEqual(result["item_resolution"], "Genérico")

	def test_multiples_candidatos_no_elige(self):
		with patch("frappe.db.get_value", side_effect=_gv(None, None)):
			with patch("frappe.db.get_all", side_effect=_ga(["GASTO-SRV-007", "GASTO-SRV-008"])):
				result = self.r.propose(**_BASE)
		self.assertIsNone(result["item_code"])
		self.assertIsNone(result["item_resolution"])

	def test_sin_match_retorna_vacio(self):
		with patch("frappe.db.get_value", side_effect=_gv(None, None)):
			with patch("frappe.db.get_all", side_effect=_ga([])):
				result = self.r.propose(**_BASE)
		self.assertIsNone(result["item_code"])
		self.assertIsNone(result["item_resolution"])
